#!/usr/bin/env python3
"""Drive survey-autoresearch phase actions until completion or a real blocker."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .article_builder import prepare_article_request
    from .argument_builder import prepare_argument_request
    from .discovery_runtime_executor import prepare_discovery_batches
    from .gate7_driver import run_until_complete as run_gate7_until_complete
    from .knowledge_tree_builder import prepare_knowledge_tree_request
    from .paper_reader import prepare_paper_reading
    from .phase_gate import evaluate_phase_barriers
    from .rebalance_ab_selection import initialize_ab_selection_from_topic_audit, rebalance_ab_selection
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .spine_planner import prepare_spine_plan_request, validate_spine_plan
    from .status_schema import STATUS_SCHEMA_VERSION
    from .status_schema import status_envelope
    from .synthesis_builder import prepare_synthesis_request
    from .topic_profile import prepare_topic_profile_request
    from .topic_relevance_runtime_executor import prepare_topic_relevance_batches, prepare_topic_relevance_second_audit_batches
except ImportError:  # pragma: no cover
    from article_builder import prepare_article_request
    from argument_builder import prepare_argument_request
    from discovery_runtime_executor import prepare_discovery_batches
    from gate7_driver import run_until_complete as run_gate7_until_complete
    from knowledge_tree_builder import prepare_knowledge_tree_request
    from paper_reader import prepare_paper_reading
    from phase_gate import evaluate_phase_barriers
    from rebalance_ab_selection import initialize_ab_selection_from_topic_audit, rebalance_ab_selection
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from spine_planner import prepare_spine_plan_request, validate_spine_plan
    from status_schema import STATUS_SCHEMA_VERSION
    from status_schema import status_envelope
    from synthesis_builder import prepare_synthesis_request
    from topic_profile import prepare_topic_profile_request
    from topic_relevance_runtime_executor import prepare_topic_relevance_batches, prepare_topic_relevance_second_audit_batches


COMPONENT = "survey_driver"

REQUEST_TYPES_BY_ACTION = {
    "spawn_topic_profile_agents": ["topic_profile"],
    "spawn_discovery_agents": ["discovery"],
    "spawn_topic_relevance_agents": ["topic_relevance"],
    "spawn_topic_relevance_second_audit_agents": ["topic_relevance_second_audit"],
    "spawn_paper_understanding_agents": ["paper_understanding"],
    "spawn_knowledge_tree_agents": ["knowledge_tree"],
    "spawn_synthesis_agents": ["synthesis"],
    "spawn_spine_planner_agents": ["spine_planner"],
    "spawn_argument_agents": ["argument"],
    "spawn_article_agents": ["article"],
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
    if path.is_dir():
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(str(child.relative_to(path)).encode("utf-8"))
            digest.update(b"\0")
            digest.update(child.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()
    digest.update(path.read_bytes())
    return digest.hexdigest()


INTENT_HASH_FILES_BY_ACTION = {
    "spawn_discovery_agents": [
        "state/task_spec.md",
        "state/topic_profile.json",
        "state/survey_type_plan.yml",
        "state/progress.json",
        "state/discovery_spawn_requests.json",
    ],
    "spawn_topic_profile_agents": [
        "state/task_spec.md",
        "state/topic_profile_spawn_requests.json",
    ],
    "spawn_topic_relevance_agents": [
        "state/raw_candidates.jsonl",
        "state/search_routes.jsonl",
        "state/lqs_scores.jsonl",
        "state/corpus_expansion.json",
        "state/papers.jsonl",
        "state/citation_plan.jsonl",
        "state/survey_type_plan.yml",
        "state/topic_relevance_spawn_requests.json",
    ],
    "spawn_topic_relevance_second_audit_agents": [
        "state/raw_candidates.jsonl",
        "state/papers.jsonl",
        "state/citation_plan.jsonl",
        "state/survey_type_plan.yml",
        "state/topic_relevance_audit.jsonl",
        "state/topic_relevance_second_audits.jsonl",
        "state/topic_relevance_spawn_requests.json",
    ],
    "spawn_paper_understanding_agents": [
        "state/papers.jsonl",
        "state/citation_plan.jsonl",
        "state/topic_relevance_audit.jsonl",
        "state/topic_relevance_second_audits.jsonl",
        "state/full_text_fetch_plan.json",
        "state/full_text_sources.jsonl",
        "state/paper_mechanism_cards.jsonl",
        "state/paper_understanding_spawn_requests.json",
    ],
    "spawn_knowledge_tree_agents": [
        "state/paper_cards",
        "state/taxonomy_alignment.jsonl",
        "outputs/knowledge_tree.yml",
        "state/paper_clusters.jsonl",
        "state/taxonomy_candidates.yml",
        "state/spine_decision.md",
        "state/knowledge_tree_spawn_requests.json",
    ],
    "spawn_synthesis_agents": [
        "state/paper_cards",
        "state/citation_plan.jsonl",
        "state/full_text_sources.jsonl",
        "outputs/knowledge_tree.yml",
        "outputs/contribution_tree.yml",
        "state/spine_decision.md",
        "state/synthesis_spawn_requests.json",
    ],
    "spawn_spine_planner_agents": [
        "state/paper_cards",
        "state/taxonomy_alignment.jsonl",
        "outputs/knowledge_tree.yml",
        "state/paper_clusters.jsonl",
        "state/taxonomy_candidates.yml",
        "state/spine_decision.md",
        "state/spine_planner_spawn_requests.json",
    ],
    "spawn_argument_agents": [
        "state/task_spec.md",
        "state/topic_profile.json",
        "state/survey_type_plan.yml",
        "state/taxonomy_alignment.jsonl",
        "state/paper_mechanism_cards.jsonl",
        "state/full_text_sources.jsonl",
        "state/scenario_definitions.yml",
        "outputs/knowledge_tree.yml",
        "state/spine_decision.md",
        "state/argument_spawn_requests.json",
    ],
    "spawn_article_agents": [
        "state/task_spec.md",
        "state/survey_type_plan.yml",
        "state/argument_graph.yml",
        "state/claim_evidence_spans.jsonl",
        "state/section_evidence_plans.jsonl",
        "state/taxonomy_alignment.jsonl",
        "state/scenario_definitions.yml",
        "outputs/article_plan.md",
        "outputs/method_family_dossiers",
        "outputs/benchmark_dossiers",
        "state/article_spawn_requests.json",
    ],
    "spawn_reviewers": [
        "outputs/survey_candidate.md",
        "outputs/appendix.md",
        "state/paper_mechanism_cards.jsonl",
        "state/claim_evidence_spans.jsonl",
        "state/section_evidence_plans.jsonl",
        "state/gate7_spawn_requests.json",
    ],
    "spawn_repair_agents": [
        "outputs/survey_candidate.md",
        "state/expert_review_adjudication.json",
        "state/gate7_repair_plan.json",
        "state/gate7_repair_batches.json",
        "state/gate7_spawn_requests.json",
    ],
    "spawn_targeted_rereviewers": [
        "outputs/survey_candidate.md",
        "state/repair_actions.jsonl",
        "state/regression_checks.jsonl",
        "state/gate7_spawn_requests.json",
    ],
}

PROGRESS_HASH_FILES = [
    "state/raw_candidates.jsonl",
    "state/search_routes.jsonl",
    "state/lqs_scores.jsonl",
    "state/corpus_expansion.json",
    "state/papers.jsonl",
    "state/citation_plan.jsonl",
    "state/topic_relevance_audit.jsonl",
    "state/topic_relevance_second_audits.jsonl",
    "state/topic_relevance_runtime_action.json",
    "state/topic_relevance_spawn_requests.json",
    "state/topic_relevance_results.jsonl",
    "state/paper_understanding_runtime_action.json",
    "state/paper_understanding_spawn_requests.json",
    "state/full_text_sources.jsonl",
    "state/paper_mechanism_cards.jsonl",
    "state/paper_cards",
    "outputs/knowledge_tree.yml",
    "state/paper_clusters.jsonl",
    "state/taxonomy_candidates.yml",
    "state/spine_decision.md",
    "state/knowledge_tree_runtime_action.json",
    "state/knowledge_tree_spawn_requests.json",
    "state/synthesis_runtime_action.json",
    "state/synthesis_spawn_requests.json",
    "state/synthesis_results.jsonl",
    "state/spine_planner_runtime_action.json",
    "state/spine_planner_spawn_requests.json",
    "state/spine_planner_results.jsonl",
    "state/argument_runtime_action.json",
    "state/argument_spawn_requests.json",
    "state/argument_results.jsonl",
    "state/article_runtime_action.json",
    "state/article_spawn_requests.json",
    "state/article_results.jsonl",
    "state/argument_graph.yml",
    "state/section_evidence_plans.jsonl",
    "state/claim_evidence_spans.jsonl",
    "outputs/article_plan.md",
    "state/gate7_runtime_action.json",
    "state/gate7_spawn_requests.json",
    "state/gate7_repair_plan.json",
    "state/runtime_active_intent.json",
    "state/runtime_dispatch_queue.jsonl",
    "state/runtime_agent_sessions.jsonl",
    "state/runtime_agent_results.jsonl",
    "outputs/survey_candidate.md",
    "outputs/survey_candidate.html",
]


def _artifact_hashes(task_dir: Path, relative_paths: list[str]) -> dict:
    return {relative: _sha256_file(task_dir / relative) for relative in relative_paths}


def _intent_source_hashes(task_dir: Path, next_action: str) -> dict:
    return _artifact_hashes(task_dir, INTENT_HASH_FILES_BY_ACTION.get(next_action, []))


def _progress_hashes(task_dir: Path) -> dict:
    return _artifact_hashes(task_dir, PROGRESS_HASH_FILES)


def _progress_hash(task_dir: Path) -> str:
    return _stable_hash(_progress_hashes(task_dir))


def _runtime_activity_summary(task_dir: Path) -> dict:
    state = _state(task_dir)
    rows = read_jsonl(state / "runtime_dispatch_queue.jsonl")
    return {
        "pending_spawn_count": len([row for row in rows if row.get("status") == "pending_spawn"]),
        "spawned_count": len([row for row in rows if row.get("status") == "spawned"]),
        "invalid_result_count": len([row for row in rows if row.get("status") == "invalid_result"]),
        "rebalance_required_count": len([row for row in rows if row.get("status") == "rebalance_required"]),
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
    hashes = _intent_source_hashes(task_dir, next_action)
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
    repeated = _maybe_repeated_blocker_after_finish(task_dir, output)
    return repeated or output


def _append_history(task_dir: Path, result: dict, phase_status: dict) -> None:
    state = _state(task_dir)
    row = {
        "ts": _utc_now(),
        "status": result.get("status"),
        "next_action": result.get("next_action"),
        "blocked_by_phase": result.get("blocked_by_phase") or phase_status.get("blocked_by_phase"),
        "active_batch_id": result.get("active_batch_id"),
        "progress_hash": _progress_hash(task_dir),
        "progress_hashes": _progress_hashes(task_dir),
        "runtime_activity": _runtime_activity_summary(task_dir),
    }
    row["blocker_fingerprint"] = "|".join(str(row.get(key) or "") for key in ["status", "next_action", "blocked_by_phase", "active_batch_id"])
    history_path = state / "survey_driver_history.jsonl"
    write_jsonl(history_path, read_jsonl(history_path) + [row])


def _maybe_repeated_blocker_after_finish(task_dir: Path, result: dict) -> dict | None:
    if str(result.get("status") or "") in {"complete", "quality_limited_stop"}:
        return None
    if str(result.get("next_action") or "") in REQUEST_TYPES_BY_ACTION:
        return None
    history = read_jsonl(_state(task_dir) / "survey_driver_history.jsonl")
    if len(history) < 3:
        return None
    last_three = history[-3:]
    if not all(item.get("progress_hash") for item in last_three):
        return None
    same_blocker = len({item.get("blocker_fingerprint") for item in last_three}) == 1
    same_progress = len({item.get("progress_hash") for item in last_three}) == 1
    runtime = _runtime_activity_summary(task_dir)
    runtime_waiting = any(runtime.get(key, 0) for key in ["pending_spawn_count", "spawned_count", "invalid_result_count", "rebalance_required_count"])
    if not (same_blocker and same_progress) or runtime_waiting:
        return None
    return {
        **status_envelope(
            COMPONENT,
            "blocked_repeated_no_progress",
            next_action="inspect_survey_driver",
            terminal=True,
            blocked=True,
            blocked_by_phase=result.get("blocked_by_phase"),
            active_batch_id=result.get("active_batch_id"),
            summary={
                "blocker_fingerprint": last_three[-1].get("blocker_fingerprint"),
                "progress_hash": last_three[-1].get("progress_hash"),
                "history_count": len(history),
            },
        ),
        "blocker_fingerprint": last_three[-1].get("blocker_fingerprint"),
        "progress_hash": last_three[-1].get("progress_hash"),
        "history_count": len(history),
        "actions": result.get("actions") or [],
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


def _topic_relevance_audit_incomplete(task_dir: Path) -> bool:
    doc = read_json(_state(task_dir) / "topic_relevance_batches.json")
    batches = doc.get("batches") or []
    if not batches:
        return False
    return any(str(batch.get("status") or "") != "resolved" for batch in batches)


def _synthesis_needs_knowledge_tree(phase_status: dict) -> bool:
    synthesis = ((phase_status.get("phases") or {}).get("synthesis") or {}).get("details") or {}
    contribution = synthesis.get("contribution_tree") or {}
    errors = set(contribution.get("errors") or [])
    if errors & {"missing_root_claim", "missing_branches"}:
        return True
    if "invalid_contribution_tree" not in errors:
        return False
    # Empty contribution statements make otherwise valid branch representatives
    # look unknown. Route that case to the synthesis worker, not back to KT.
    statement_errors = {"missing_contribution_statements", "invalid_contribution_statements"}
    return not bool(errors & statement_errors)


def _synthesis_needs_synthesis_worker(phase_status: dict) -> bool:
    synthesis = ((phase_status.get("phases") or {}).get("synthesis") or {}).get("details") or {}
    contribution = synthesis.get("contribution_tree") or {}
    scenario = synthesis.get("scenario_definitions") or {}
    dossiers = synthesis.get("synthesis_dossiers") or {}
    errors = set(contribution.get("errors") or []) | set(scenario.get("errors") or []) | set(dossiers.get("errors") or [])
    return bool(
        errors
        & {
            "missing_contribution_statements",
            "invalid_contribution_statements",
            "argument_graph_missing_contribution_tree",
            "too_few_scenarios",
            "invalid_scenario_definitions",
            "missing_comparative_evidence_matrix",
            "invalid_comparative_evidence_matrix",
            "missing_method_family_dossiers",
            "missing_benchmark_dossiers",
            "invalid_method_dossiers",
            "invalid_benchmark_dossiers",
        }
    )


def _public_spine_needs_planning(task_dir: Path, target: str) -> bool:
    status = validate_spine_plan(task_dir, target)
    if status.get("valid"):
        return False
    errors = set(status.get("errors") or [])
    if "missing_knowledge_tree" in errors or "missing_paper_cards" in errors:
        return False
    return bool(errors)


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
            runtime = prepare_paper_reading(task_dir, target, allow_source_repair_gap=True)
            return _finish(task_dir, runtime, actions, {"blocked_by_phase": "paper_understanding"})
        phase_status = evaluate_phase_barriers(task_dir, target)
        blocked_by = phase_status.get("blocked_by_phase")
        next_action = phase_status.get("next_action") or phase_status.get("allowed_next_phase")
        actions.append(str(next_action))
        if blocked_by == "topic_profile":
            runtime = prepare_topic_profile_request(task_dir, target)
            return _finish(task_dir, runtime, actions, phase_status)
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
            if _topic_relevance_audit_incomplete(task_dir):
                actions.append("continue_topic_relevance_audit_before_rebalance")
                runtime = prepare_topic_relevance_batches(task_dir)
                return _finish(task_dir, runtime, actions, phase_status)
            topic = ((phase_status.get("phases") or {}).get("source_verification") or {}).get("details", {}).get("topic_relevance", {})
            invalid_ids = topic.get("invalid_ab_paper_ids") or []
            actions.append("rebalance_topic_relevance_ab_selection")
            if not invalid_ids:
                if not read_jsonl(_state(task_dir) / "papers.jsonl") and not read_jsonl(_state(task_dir) / "citation_plan.jsonl"):
                    actions.append("initialize_ab_selection_from_topic_audit")
                    initialized = initialize_ab_selection_from_topic_audit(task_dir, target)
                    if str(initialized.get("status") or "").startswith("blocked"):
                        return _finish(
                            task_dir,
                            {
                                "status": "blocked_initial_topic_relevance_selection",
                                "next_action": "inspect_topic_relevance_audit",
                                "terminal": True,
                                "blocked": True,
                                "blocked_by_phase": "source_verification",
                                "summary": {"initial_selection": initialized},
                            },
                            actions,
                            phase_status,
                        )
                    continue
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
            runtime = prepare_paper_reading(task_dir, target)
            return _finish(task_dir, runtime, actions, phase_status)
        if blocked_by == "synthesis" and _synthesis_needs_knowledge_tree(phase_status):
            runtime = prepare_knowledge_tree_request(task_dir, target)
            return _finish(task_dir, runtime, actions, phase_status)
        if blocked_by == "synthesis" and _synthesis_needs_synthesis_worker(phase_status):
            runtime = prepare_synthesis_request(task_dir, target)
            return _finish(task_dir, runtime, actions, phase_status)
        if (not blocked_by or blocked_by in {"synthesis", "argument", "article", "expert_review"}) and _public_spine_needs_planning(task_dir, target):
            runtime = prepare_spine_plan_request(task_dir, target)
            return _finish(task_dir, runtime, actions, phase_status)
        if blocked_by == "argument":
            runtime = prepare_argument_request(task_dir, target)
            return _finish(task_dir, runtime, actions, phase_status)
        if blocked_by == "article" and next_action in {"article_draft", "article_quality_repair", "article_repair_after_expansion_audit"}:
            runtime = prepare_article_request(task_dir, target)
            return _finish(task_dir, runtime, actions, phase_status)
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
