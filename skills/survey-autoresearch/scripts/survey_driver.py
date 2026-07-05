#!/usr/bin/env python3
"""Drive survey-autoresearch phase actions until completion or a real blocker."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .discovery_runtime_executor import prepare_discovery_batches
    from .full_text_source_planner import build_full_text_fetch_plan
    from .gate7_driver import run_until_complete as run_gate7_until_complete
    from .paper_understanding_runtime_executor import prepare_paper_understanding_batches
    from .phase_gate import evaluate_phase_barriers
    from .rebalance_ab_selection import rebalance_ab_selection
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .status_schema import STATUS_SCHEMA_VERSION
    from .status_schema import status_envelope
    from .topic_relevance_runtime_executor import prepare_topic_relevance_batches, prepare_topic_relevance_second_audit_batches
except ImportError:  # pragma: no cover
    from discovery_runtime_executor import prepare_discovery_batches
    from full_text_source_planner import build_full_text_fetch_plan
    from gate7_driver import run_until_complete as run_gate7_until_complete
    from paper_understanding_runtime_executor import prepare_paper_understanding_batches
    from phase_gate import evaluate_phase_barriers
    from rebalance_ab_selection import rebalance_ab_selection
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from status_schema import STATUS_SCHEMA_VERSION
    from status_schema import status_envelope
    from topic_relevance_runtime_executor import prepare_topic_relevance_batches, prepare_topic_relevance_second_audit_batches


COMPONENT = "survey_driver"

REQUEST_TYPES_BY_ACTION = {
    "spawn_discovery_agents": ["discovery"],
    "spawn_topic_relevance_agents": ["topic_relevance"],
    "spawn_topic_relevance_second_audit_agents": ["topic_relevance_second_audit"],
    "spawn_paper_understanding_agents": ["paper_understanding"],
    "spawn_reviewers": ["gate7_reviewer"],
    "spawn_repair_agents": ["gate7_repair"],
    "spawn_targeted_rereviewers": ["gate7_targeted_rereview"],
}


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _source_hashes(task_dir: Path) -> dict:
    state = _state(task_dir)
    outputs = task_dir / "outputs"
    return {
        "raw_candidates": _sha256_file(state / "raw_candidates.jsonl"),
        "papers": _sha256_file(state / "papers.jsonl"),
        "citation_plan": _sha256_file(state / "citation_plan.jsonl"),
        "topic_relevance_audit": _sha256_file(state / "topic_relevance_audit.jsonl"),
        "paper_mechanism_cards": _sha256_file(state / "paper_mechanism_cards.jsonl"),
        "full_text_sources": _sha256_file(state / "full_text_sources.jsonl"),
        "survey_candidate": _sha256_file(outputs / "survey_candidate.md"),
        "gate7_repair_plan": _sha256_file(state / "gate7_repair_plan.json"),
    }


def _stable_hash(value) -> str:
    payload = json.dumps(value or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reset_downstream_runtime_for_topic_audit(task_dir: Path) -> None:
    state = _state(task_dir)
    write_json(
        state / "paper_understanding_spawn_requests.json",
        {"next_action": None, "spawn_requests": []},
    )
    write_json(
        state / "paper_understanding_runtime_action.json",
        status_envelope(
            "paper_understanding_runtime_executor",
            "stale_blocked_by_topic_relevance",
            next_action="run_survey_driver",
            terminal=False,
            blocked=True,
            blocked_by_phase="source_verification",
            active_batch_id=None,
            summary={"stale_reason": "source_verification_requires_topic_relevance_audit"},
        ),
    )
    write_json(
        state / "gate7_spawn_requests.json",
        {"next_action": None, "spawn_requests": []},
    )


def _write_runtime_intent(task_dir: Path, result: dict, phase_status: dict) -> None:
    next_action = str(result.get("next_action") or "")
    allowed = REQUEST_TYPES_BY_ACTION.get(next_action, [])
    active_phase = result.get("blocked_by_phase") or phase_status.get("blocked_by_phase")
    hashes = _source_hashes(task_dir)
    generation_payload = {
        "active_phase": active_phase,
        "next_action": next_action,
        "allowed_request_types": allowed,
        "source_hashes": hashes,
    }
    write_json(
        _state(task_dir) / "runtime_active_intent.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "active_phase": active_phase,
            "next_action": next_action if allowed else None,
            "allowed_request_types": allowed,
            "phase_generation": _stable_hash(generation_payload) if allowed else "",
            "source_hashes": hashes if allowed else {},
            "generated_at": _utc_now(),
        },
    )
    if next_action == "spawn_topic_relevance_agents":
        _reset_downstream_runtime_for_topic_audit(task_dir)


def _finish(task_dir: Path, result: dict, actions: list[str], phase_status: dict | None = None) -> dict:
    phase_status = phase_status or {}
    summary = dict(result.get("summary") or {})
    summary.setdefault("action_count", len(actions))
    summary.setdefault("last_action", actions[-1] if actions else None)
    envelope = status_envelope(
        COMPONENT,
        str(result.get("status") or "blocked_phase_action_required"),
        next_action=result.get("next_action"),
        terminal=bool(result.get("terminal", False)),
        blocked=bool(result.get("blocked", True)),
        blocked_by_phase=result.get("blocked_by_phase") or phase_status.get("blocked_by_phase"),
        active_batch_id=result.get("active_batch_id"),
        summary=summary,
    )
    output = {**result, **envelope, "actions": actions}
    _write_runtime_intent(task_dir, output, phase_status)
    _append_history(task_dir, output, phase_status)
    return output


def _append_history(task_dir: Path, result: dict, phase_status: dict) -> None:
    state = _state(task_dir)
    row = {
        "ts": _utc_now(),
        "status": result.get("status"),
        "next_action": result.get("next_action"),
        "blocked_by_phase": result.get("blocked_by_phase") or phase_status.get("blocked_by_phase"),
        "active_batch_id": result.get("active_batch_id"),
        "candidate_hash": _sha256_file(task_dir / "outputs" / "survey_candidate.md"),
        "paper_cards_hash": _sha256_file(state / "paper_mechanism_cards.jsonl"),
        "full_text_sources_hash": _sha256_file(state / "full_text_sources.jsonl"),
    }
    row["blocker_fingerprint"] = "|".join(str(row.get(key) or "") for key in ["status", "next_action", "blocked_by_phase", "active_batch_id"])
    history_path = state / "survey_driver_history.jsonl"
    write_jsonl(history_path, read_jsonl(history_path) + [row])


def _repeated_blocker(task_dir: Path) -> dict | None:
    history = read_jsonl(_state(task_dir) / "survey_driver_history.jsonl")
    if len(history) < 3:
        return None
    last_three = history[-3:]
    same_blocker = len({item.get("blocker_fingerprint") for item in last_three}) == 1
    same_hashes = len({
        (
            item.get("candidate_hash"),
            item.get("paper_cards_hash"),
            item.get("full_text_sources_hash"),
            item.get("active_batch_id"),
        )
        for item in last_three
    }) == 1
    if not (same_blocker and same_hashes):
        return None
    return {
        "status": "blocked_repeated_no_progress",
        "next_action": "inspect_survey_driver",
        "terminal": True,
        "blocked": True,
        "blocker_fingerprint": last_three[-1].get("blocker_fingerprint"),
        "history_count": len(history),
    }


def _delegate_gate7(task_dir: Path, target: str, max_steps: int) -> dict:
    gate7 = run_gate7_until_complete(task_dir, target if target in {"full", "csur"} else "full", max_steps)
    summary = dict(gate7.get("summary") or {})
    summary["delegated_component"] = "gate7_driver"
    return {
        **gate7,
        "summary": summary,
        "terminal": bool(gate7.get("terminal", False)),
        "blocked": bool(gate7.get("blocked", True)),
    }


def _pending_rebalance(task_dir: Path) -> tuple[list[str], list[str]]:
    state = _state(task_dir)
    status = read_json(state / "runtime_rebalance_status.json")
    handled = {str(item) for item in status.get("handled_result_hashes") or [] if str(item).strip()}
    ids: set[str] = set()
    hashes: list[str] = []
    for row in read_jsonl(state / "runtime_agent_results.jsonl"):
        result_hash = str(row.get("result_hash") or "")
        if row.get("status") != "rebalance_required" or not result_hash or result_hash in handled:
            continue
        hashes.append(result_hash)
        for paper_id in row.get("unavailable_paper_ids") or []:
            if str(paper_id).strip():
                ids.add(str(paper_id).strip())
    return sorted(ids), hashes


def _mark_rebalance_handled(task_dir: Path, hashes: list[str], result: dict) -> None:
    state = _state(task_dir)
    status = read_json(state / "runtime_rebalance_status.json")
    handled = [str(item) for item in status.get("handled_result_hashes") or [] if str(item).strip()]
    for item in hashes:
        if item not in handled:
            handled.append(item)
    write_json(
        state / "runtime_rebalance_status.json",
        {
            "handled_result_hashes": handled,
            "last_rebalance": {
                "ts": _utc_now(),
                "result": result,
            },
        },
    )


def run_until_complete(task_dir: Path, target: str = "full", max_steps: int = 25) -> dict:
    actions: list[str] = []
    for _ in range(max_steps):
        rebalance_ids, rebalance_hashes = _pending_rebalance(task_dir)
        if rebalance_ids:
            actions.append("rebalance_ab_selection")
            rebalance = rebalance_ab_selection(task_dir, rebalance_ids, target)
            if str(rebalance.get("status") or "").startswith("blocked"):
                return _finish(
                    task_dir,
                    {
                        "status": "blocked_rebalance_required",
                        "next_action": "inspect_unavailable_papers",
                        "terminal": True,
                        "blocked": True,
                        "blocked_by_phase": "paper_understanding",
                        "summary": {"rebalance": rebalance, "blocked_paper_ids": rebalance_ids},
                    },
                    actions,
                )
            _mark_rebalance_handled(task_dir, rebalance_hashes, rebalance)
            build_full_text_fetch_plan(task_dir)
            runtime = prepare_paper_understanding_batches(task_dir)
            return _finish(task_dir, runtime, actions, {"blocked_by_phase": "paper_understanding"})
        repeated = _repeated_blocker(task_dir)
        if repeated:
            return _finish(task_dir, repeated, actions)
        phase_status = evaluate_phase_barriers(task_dir, target)
        blocked_by = phase_status.get("blocked_by_phase")
        next_action = phase_status.get("next_action") or phase_status.get("allowed_next_phase")
        actions.append(str(next_action))
        if not blocked_by:
            return _finish(
                task_dir,
                {
                    "status": "complete",
                    "next_action": "complete",
                    "terminal": True,
                    "blocked": False,
                    "summary": {"last_passed_phase": phase_status.get("last_passed_phase")},
                },
                actions,
                phase_status,
            )
        if blocked_by == "discovery" and next_action == "discovery":
            runtime = prepare_discovery_batches(task_dir)
            return _finish(task_dir, runtime, actions, phase_status)
        if blocked_by == "source_verification" and next_action == "topic_relevance_audit":
            runtime = prepare_topic_relevance_batches(task_dir)
            return _finish(task_dir, runtime, actions, phase_status)
        if blocked_by == "source_verification" and next_action == "topic_relevance_second_audit":
            runtime = prepare_topic_relevance_second_audit_batches(task_dir)
            return _finish(task_dir, runtime, actions, phase_status)
        if blocked_by == "source_verification" and next_action == "topic_relevance_rebalance":
            topic = ((phase_status.get("phases") or {}).get("source_verification") or {}).get("details", {}).get("topic_relevance", {})
            invalid_ids = topic.get("invalid_ab_paper_ids") or []
            actions.append("rebalance_topic_relevance_ab_selection")
            if not invalid_ids:
                return _finish(
                    task_dir,
                    {
                        "status": "blocked_topic_relevance_rebalance",
                        "next_action": "inspect_topic_relevance_audit",
                        "terminal": True,
                        "blocked": True,
                        "blocked_by_phase": "source_verification",
                        "summary": {"error": "missing_invalid_ab_paper_ids"},
                    },
                    actions,
                    phase_status,
                )
            rebalance = rebalance_ab_selection(task_dir, invalid_ids, target, reason="topic_relevance")
            if str(rebalance.get("status") or "").startswith("blocked"):
                return _finish(
                    task_dir,
                    {
                        "status": "blocked_topic_relevance_rebalance",
                        "next_action": "inspect_topic_relevance_replacements",
                        "terminal": True,
                        "blocked": True,
                        "blocked_by_phase": "source_verification",
                        "summary": {"rebalance": rebalance, "blocked_paper_ids": invalid_ids},
                    },
                    actions,
                    phase_status,
                )
            continue
        if blocked_by == "paper_understanding":
            runtime = prepare_paper_understanding_batches(task_dir)
            return _finish(task_dir, runtime, actions, phase_status)
        if blocked_by == "expert_review":
            return _finish(task_dir, _delegate_gate7(task_dir, target, max_steps), actions, phase_status)
        return _finish(
            task_dir,
            {
                "status": "blocked_phase_action_required",
                "next_action": next_action,
                "terminal": False,
                "blocked": True,
                "blocked_by_phase": blocked_by,
                "summary": {
                    "last_passed_phase": phase_status.get("last_passed_phase"),
                    "allowed_next_phase": phase_status.get("allowed_next_phase"),
                },
            },
            actions,
            phase_status,
        )
    return _finish(task_dir, {"status": "blocked_no_progress", "next_action": "inspect_survey_driver", "terminal": True, "blocked": True}, actions)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--run-until-complete", action="store_true")
    parser.add_argument("--max-steps", type=int, default=25)
    args = parser.parse_args()
    if not args.run_until_complete:
        result = {"status": "invalid", "error": "choose --run-until-complete"}
    else:
        result = run_until_complete(args.task_dir, args.target, args.max_steps)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
