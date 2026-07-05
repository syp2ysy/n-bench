#!/usr/bin/env python3
"""Drive local Gate 7 loop actions until completion or a true external blocker."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .build_repair_plan import build_repair_plan
    from .gate7_runtime_executor import prepare_runtime_repair
    from .gate7_loop import (
        adjudicate_reports,
        collect_gate7_status,
        make_reviewer_prompts,
        make_targeted_rereview_prompts,
        reset_gate7_round_for_full_rerun,
    )
    from .gate_check import evaluate_gates
    from .promote_survey_release import promote_release
    from .run_expert_reviews import freeze_review_round, write_json, write_jsonl
    from .status_schema import status_envelope
except ImportError:  # pragma: no cover
    from build_repair_plan import build_repair_plan
    from gate7_runtime_executor import prepare_runtime_repair
    from gate7_loop import adjudicate_reports, collect_gate7_status, make_reviewer_prompts, make_targeted_rereview_prompts, reset_gate7_round_for_full_rerun
    from gate_check import evaluate_gates
    from promote_survey_release import promote_release
    from run_expert_reviews import freeze_review_round, write_json, write_jsonl
    from status_schema import status_envelope


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


def _sha256_text(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_driver_history(task_dir: Path, result: dict, actions: list[str]) -> dict:
    state = _state(task_dir)
    runtime_action = _read_json(state / "gate7_runtime_action.json")
    row = {
        "ts": _utc_now(),
        "status": result.get("status"),
        "next_action": result.get("next_action"),
        "actions": actions,
        "candidate_hash": _sha256_file(task_dir / "outputs" / "survey_candidate.md"),
        "repair_plan_hash": _sha256_text(state / "gate7_repair_plan.json"),
        "runtime_action_hash": _sha256_text(state / "gate7_runtime_action.json"),
        "active_batch_id": runtime_action.get("active_batch_id"),
        "blocker_fingerprint": "|".join(
            str(value or "")
            for value in [
                result.get("status"),
                result.get("next_action"),
                result.get("blocked_by_phase"),
                runtime_action.get("active_batch_id"),
            ]
        ),
    }
    history_path = state / "gate7_driver_history.jsonl"
    history = _read_jsonl(history_path)
    history.append(row)
    write_jsonl(history_path, history)
    if len(history) >= 3:
        last_three = history[-3:]
        same_blocker = len({item.get("blocker_fingerprint") for item in last_three}) == 1
        same_hashes = len({
            (
                item.get("candidate_hash"),
                item.get("repair_plan_hash"),
                item.get("runtime_action_hash"),
                item.get("active_batch_id"),
            )
            for item in last_three
        }) == 1
        if same_blocker and same_hashes and str(result.get("status") or "") not in {"complete", "quality_limited_stop"}:
            return {
                **status_envelope(
                    "gate7_driver",
                    "blocked_repeated_no_progress",
                    next_action="inspect_gate7_loop",
                    terminal=True,
                    blocked=True,
                    blocked_by_phase=result.get("blocked_by_phase"),
                    active_batch_id=runtime_action.get("active_batch_id"),
                    summary={
                        "action_count": len(actions),
                        "active_batch_id": runtime_action.get("active_batch_id"),
                        "history_count": len(history),
                        "blocker_fingerprint": row["blocker_fingerprint"],
                    },
                ),
                "blocker_fingerprint": row["blocker_fingerprint"],
                "history_count": len(history),
                "actions": actions,
            }
    return result


def _driver_terminal(status: str) -> bool:
    return status in {
        "complete",
        "quality_limited_stop",
        "blocked_repeated_no_progress",
        "blocked_no_progress",
        "blocked_unknown_action",
    }


def _driver_blocked(status: str, result: dict) -> bool:
    if status in {"complete", "quality_limited_stop"}:
        return False
    if result.get("blocked_by_phase"):
        return True
    if status.startswith("blocked") or status.startswith("waiting"):
        return True
    return status in {"regression_checks_required", "gate_check_failed_after_repair"}


def _driver_summary(task_dir: Path, result: dict, actions: list[str]) -> dict:
    runtime_action = _read_json(_state(task_dir) / "gate7_runtime_action.json")
    summary = {
        "action_count": len(actions),
        "last_action": actions[-1] if actions else None,
        "spawn_request_count": result.get("spawn_request_count", runtime_action.get("spawn_request_count")),
        "active_batch_id": result.get("active_batch_id") or runtime_action.get("active_batch_id"),
        "rerun_policy": result.get("rerun_policy") or runtime_action.get("rerun_policy"),
    }
    if isinstance(runtime_action.get("summary"), dict):
        for key, value in runtime_action["summary"].items():
            summary.setdefault(key, value)
    return summary


def _finish(task_dir: Path, result: dict, actions: list[str]) -> dict:
    status = str(result.get("status") or "unknown")
    summary = _driver_summary(task_dir, result, actions)
    envelope = status_envelope(
            "gate7_driver",
            status,
            next_action=result.get("next_action"),
            terminal=_driver_terminal(status),
            blocked=_driver_blocked(status, result),
            blocked_by_phase=result.get("blocked_by_phase"),
            active_batch_id=result.get("active_batch_id") or summary.get("active_batch_id"),
            summary=summary,
    )
    result = {
        **result,
        **envelope,
        "actions": actions,
    }
    return _append_driver_history(task_dir, result, actions)


def _write_spawn_requests(task_dir: Path, payload: dict, action: str) -> dict:
    state = _state(task_dir)
    prompts = payload.get("reviewer_prompts") or payload.get("targeted_rereview_prompts") or []
    if action == "spawn_reviewers":
        record_command = f"python3 scripts/gate7_loop.py --task-dir {task_dir.resolve()} --record-review <result.json> --subagent-session-id <subagent-session-id>"
    else:
        record_command = f"python3 scripts/gate7_loop.py --task-dir {task_dir.resolve()} --record-targeted-rereview <result.json> --subagent-session-id <subagent-session-id>"
    requests = [
        {
            "request_id": f"spawn-{idx:03d}",
            "next_action": action,
            "agent_type": prompt.get("agent_type") or "explorer",
            "fork_context": False,
            "review_round_id": prompt.get("review_round_id"),
            "reviewer_id": prompt.get("reviewer_id"),
            "weakness_id": prompt.get("weakness_id"),
            "record_command": record_command,
            "message": prompt.get("message"),
            "status": "pending_spawn",
        }
        for idx, prompt in enumerate(prompts, start=1)
    ]
    write_json(state / "gate7_spawn_requests.json", {"next_action": action, "spawn_requests": requests})
    return {
        "status": "blocked_subagent_spawn_required",
        "next_action": action,
        "spawn_request_count": len(requests),
        "spawn_requests": requests,
    }


def _write_regression_requests(task_dir: Path) -> dict:
    state = _state(task_dir)
    plan_path = state / "gate7_repair_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() and plan_path.read_text(encoding="utf-8").strip() else {}
    requests = [
        {
            "weakness_id": item.get("weakness_id"),
            "repair_id": item.get("repair_id"),
            "acceptance_validators": item.get("acceptance_validators") or [],
            "status": "pending_regression_check",
        }
        for item in plan.get("repair_items") or []
    ]
    write_jsonl(state / "gate7_regression_requests.jsonl", requests)
    return {"status": "regression_checks_required", "next_action": "run_regression_checks", "regression_request_count": len(requests)}


def _write_gate_summary(task_dir: Path, target: str) -> dict:
    result = evaluate_gates(task_dir, target)
    output = _state(task_dir) / f"gate_check_{target}.json"
    write_json(output, result)
    return result


def run_until_complete(task_dir: Path, target: str = "full", max_steps: int = 25) -> dict:
    actions = []
    for _ in range(max_steps):
        status = collect_gate7_status(task_dir)
        action = status.get("next_action")
        actions.append(action)
        if action == "complete":
            return _finish(task_dir, {"status": "complete", "next_action": "complete"}, actions)
        if action == "quality_limited_stop":
            iteration = _read_json(_state(task_dir) / "review_iteration_status.json")
            return _finish(task_dir, {"status": "quality_limited_stop", "next_action": "quality_limited_stop", "review_iteration_status": iteration}, actions)
        if action == "freeze":
            freeze_review_round(task_dir)
            continue
        if action == "spawn_reviewers":
            return _finish(task_dir, _write_spawn_requests(task_dir, make_reviewer_prompts(task_dir), "spawn_reviewers"), actions)
        if action == "wait_all_reports":
            return _finish(task_dir, {"status": "waiting_for_expert_reviews", "next_action": "wait_all_reports"}, actions)
        if action == "adjudicate":
            adjudicate_reports(task_dir)
            continue
        if action == "repair_with_evidence":
            plan = build_repair_plan(task_dir, target)
            return _finish(task_dir, prepare_runtime_repair(task_dir, plan), actions)
        if action == "spawn_repair_agents":
            return _finish(task_dir, prepare_runtime_repair(task_dir), actions)
        if action == "run_regression_checks":
            return _finish(task_dir, _write_regression_requests(task_dir), actions)
        if action == "reset_full_review_round":
            reset_gate7_round_for_full_rerun(task_dir)
            continue
        if action == "spawn_targeted_rereviewers":
            return _finish(task_dir, _write_spawn_requests(task_dir, make_targeted_rereview_prompts(task_dir), "spawn_targeted_rereviewers"), actions)
        if action == "rerun_gate_check":
            gate_summary = _write_gate_summary(task_dir, target)
            if not gate_summary.get("all_blocking_gates_passed"):
                return _finish(task_dir, {
                    "status": "gate_check_failed_after_repair",
                    "next_action": gate_summary.get("allowed_next_phase") or "repair_with_evidence",
                    "blocked_by_phase": gate_summary.get("blocked_by_phase"),
                }, actions)
            continue
        if action == "promote_release":
            promote_release(task_dir, target)
            continue
        return _finish(task_dir, {"status": "blocked_unknown_action", "next_action": action}, actions)
    return _finish(task_dir, {"status": "blocked_no_progress", "next_action": "inspect_gate7_loop"}, actions)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["full", "csur"], default="full")
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
