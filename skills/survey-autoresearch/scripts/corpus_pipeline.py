#!/usr/bin/env python3
"""Public corpus facade for discovery and anti-drift selection.

This module intentionally does not judge paper semantics or invent corpus
records. It routes to the existing worker-backed executors and exposes one
compact corpus status for the v2 public spine.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .discovery_runtime_executor import collect_discovery_status, prepare_discovery_batches
    from .phase_gate import evaluate_phase_barriers
    from .run_expert_reviews import read_json, read_jsonl, write_json
    from .status_schema import status_envelope
    from .topic_relevance_runtime_executor import (
        collect_topic_relevance_status,
        prepare_topic_relevance_batches,
        prepare_topic_relevance_second_audit_batches,
    )
    from .validate_topic_profile import validate_topic_profile
except ImportError:  # pragma: no cover
    from discovery_runtime_executor import collect_discovery_status, prepare_discovery_batches
    from phase_gate import evaluate_phase_barriers
    from run_expert_reviews import read_json, read_jsonl, write_json
    from status_schema import status_envelope
    from topic_relevance_runtime_executor import (
        collect_topic_relevance_status,
        prepare_topic_relevance_batches,
        prepare_topic_relevance_second_audit_batches,
    )
    from validate_topic_profile import validate_topic_profile


COMPONENT = "corpus_pipeline"


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _count_jsonl(task_dir: Path, relative: str) -> int:
    return len(read_jsonl(task_dir / relative))


def _artifact_state(task_dir: Path, relative: str) -> str:
    path = task_dir / relative
    if not path.exists():
        return "missing"
    if path.is_file() and path.stat().st_size == 0:
        return "missing"
    if path.is_file() and not path.read_text(encoding="utf-8").strip():
        return "missing"
    return "present"


def _public_artifacts(task_dir: Path) -> dict:
    return {
        "topic_profile": _artifact_state(task_dir, "state/topic_profile.json"),
        "raw_candidates": _artifact_state(task_dir, "state/raw_candidates.jsonl"),
        "papers": _artifact_state(task_dir, "state/papers.jsonl"),
        "citation_plan": _artifact_state(task_dir, "state/citation_plan.jsonl"),
        "topic_relevance_audit": _artifact_state(task_dir, "state/topic_relevance_audit.jsonl"),
        "topic_relevance_second_audits": _artifact_state(task_dir, "state/topic_relevance_second_audits.jsonl"),
    }


def _corpus_counts(task_dir: Path) -> dict:
    return {
        "raw_candidate_count": _count_jsonl(task_dir, "state/raw_candidates.jsonl"),
        "retained_paper_count": _count_jsonl(task_dir, "state/papers.jsonl"),
        "citation_plan_count": _count_jsonl(task_dir, "state/citation_plan.jsonl"),
        "topic_audit_count": _count_jsonl(task_dir, "state/topic_relevance_audit.jsonl"),
        "second_audit_count": _count_jsonl(task_dir, "state/topic_relevance_second_audits.jsonl"),
    }


def _summary(task_dir: Path, extra: dict | None = None) -> dict:
    summary = {
        **_corpus_counts(task_dir),
        "public_artifacts": _public_artifacts(task_dir),
    }
    if extra:
        summary.update(extra)
    return summary


def _with_pipeline_status(task_dir: Path, result: dict, corpus_step: str) -> dict:
    summary = dict(result.get("summary") or {})
    status = result.get("status")
    next_action = result.get("next_action")
    if next_action == "spawn_discovery_agents" and status == "pending_discovery_runtime":
        status = "blocked_discovery_agent_spawn_required"
    elif next_action == "spawn_topic_relevance_agents" and status == "pending_topic_relevance_runtime":
        status = "blocked_topic_relevance_agent_spawn_required"
    elif next_action == "spawn_topic_relevance_second_audit_agents" and status == "pending_topic_relevance_second_audit_runtime":
        status = "blocked_topic_relevance_second_audit_agent_spawn_required"
    return {
        **result,
        "component": COMPONENT,
        "legacy_component": result.get("component"),
        "status": status,
        "corpus_step": corpus_step,
        "summary": _summary(task_dir, summary),
    }


def _topic_profile_status(task_dir: Path, target: str) -> dict:
    profile = read_json(_state(task_dir) / "topic_profile.json")
    validation = validate_topic_profile(profile, target)
    if validation.get("valid"):
        return {}
    return {
        **status_envelope(
            COMPONENT,
            "blocked_topic_profile_required",
            next_action="spawn_topic_profile_agents",
            terminal=False,
            blocked=True,
            blocked_by_phase="topic_profile",
            summary=_summary(task_dir, {"topic_profile": validation}),
        ),
        "corpus_step": "topic_profile",
        "topic_profile": validation,
    }


def _step_from_phase(task_dir: Path, target: str) -> tuple[str, dict]:
    topic_blocker = _topic_profile_status(task_dir, target)
    if topic_blocker:
        return "topic_profile", topic_blocker
    phase = evaluate_phase_barriers(task_dir, target)
    blocked_by = phase.get("blocked_by_phase")
    next_action = phase.get("allowed_next_phase") or phase.get("next_action")
    if blocked_by == "discovery" and next_action == "discovery":
        return "discovery", phase
    if blocked_by == "source_verification" and next_action in {
        "topic_relevance_audit",
        "topic_relevance_second_audit",
        "topic_relevance_rebalance",
        "coverage_repair",
    }:
        return str(next_action), phase
    if blocked_by in {None, "paper_understanding", "synthesis", "argument", "article", "expert_review"}:
        return "corpus_complete", phase
    return str(next_action or blocked_by or "inspect"), phase


def prepare(task_dir: Path, target: str = "full") -> dict:
    """Prepare the next corpus worker batch without fabricating corpus data."""
    step, details = _step_from_phase(task_dir, target)
    if step == "topic_profile":
        write_json(_state(task_dir) / "corpus_pipeline_status.json", details)
        return details
    if step == "discovery":
        result = _with_pipeline_status(task_dir, prepare_discovery_batches(task_dir), "discovery")
    elif step == "topic_relevance_audit":
        result = _with_pipeline_status(task_dir, prepare_topic_relevance_batches(task_dir), "topic_relevance_audit")
    elif step == "topic_relevance_second_audit":
        result = _with_pipeline_status(task_dir, prepare_topic_relevance_second_audit_batches(task_dir), "topic_relevance_second_audit")
    elif step == "topic_relevance_rebalance":
        result = {
            **status_envelope(
                COMPONENT,
                "blocked_topic_relevance_rebalance_required",
                next_action="runner_rebalance_topic_relevance",
                terminal=False,
                blocked=True,
                blocked_by_phase="source_verification",
                summary=_summary(task_dir, {"phase_status": details}),
            ),
            "corpus_step": "topic_relevance_rebalance",
        }
    elif step == "coverage_repair":
        result = {
            **status_envelope(
                COMPONENT,
                "blocked_coverage_repair_required",
                next_action="inspect_coverage_repair",
                terminal=False,
                blocked=True,
                blocked_by_phase="source_verification",
                summary=_summary(task_dir, {"phase_status": details}),
            ),
            "corpus_step": "coverage_repair",
        }
    elif step == "corpus_complete":
        result = {
            **status_envelope(
                COMPONENT,
                "complete",
                next_action="rerun_runner",
                terminal=True,
                blocked=False,
                summary=_summary(task_dir, {"phase_status": details}),
            ),
            "corpus_step": "corpus_complete",
        }
    else:
        result = {
            **status_envelope(
                COMPONENT,
                "blocked_corpus_inspection_required",
                next_action="inspect_gate_engine",
                terminal=False,
                blocked=True,
                blocked_by_phase=details.get("blocked_by_phase"),
                summary=_summary(task_dir, {"phase_status": details}),
            ),
            "corpus_step": step,
        }
    write_json(_state(task_dir) / "corpus_pipeline_status.json", result)
    return result


def collect_status(task_dir: Path, target: str = "full") -> dict:
    """Collect one compact status for topic boundary, discovery, and relevance."""
    step, details = _step_from_phase(task_dir, target)
    if step == "topic_profile":
        result = details
    elif step == "discovery":
        result = _with_pipeline_status(task_dir, collect_discovery_status(task_dir), "discovery")
    elif step == "topic_relevance_audit":
        result = _with_pipeline_status(task_dir, collect_topic_relevance_status(task_dir), "topic_relevance_audit")
    elif step == "topic_relevance_second_audit":
        # The existing collector reports primary audit status only, so fall back
        # to prepare-time state for the second-audit facade.
        result = prepare(task_dir, target)
    elif step == "corpus_complete":
        result = {
            **status_envelope(
                COMPONENT,
                "complete",
                next_action="rerun_runner",
                terminal=True,
                blocked=False,
                summary=_summary(task_dir, {"phase_status": details}),
            ),
            "corpus_step": "corpus_complete",
        }
    else:
        result = prepare(task_dir, target)
    write_json(_state(task_dir) / "corpus_pipeline_status.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--collect-status", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        result = prepare(args.task_dir, args.target)
    elif args.collect_status:
        result = collect_status(args.task_dir, args.target)
    else:
        result = {"component": COMPONENT, "status": "invalid", "error": "choose --prepare or --collect-status"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
