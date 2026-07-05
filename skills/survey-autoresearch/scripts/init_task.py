#!/usr/bin/env python3
"""Initialize persistent state for a survey-autoresearch run."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .status_schema import STATUS_SCHEMA_VERSION, status_envelope
except ImportError:  # pragma: no cover
    from status_schema import STATUS_SCHEMA_VERSION, status_envelope


STATE_FILES = [
    "discovery_results.jsonl",
    "raw_candidates.jsonl",
    "search_routes.jsonl",
    "papers.jsonl",
    "lqs_scores.jsonl",
    "citation_plan.jsonl",
    "topic_relevance_audit.jsonl",
    "topic_relevance_second_audits.jsonl",
    "topic_relevance_results.jsonl",
    "topic_profile_results.jsonl",
    "paper_mechanism_cards.jsonl",
    "full_text_sources.jsonl",
    "paper_contribution_statements.jsonl",
    "taxonomy_alignment.jsonl",
    "comparative_evidence_matrix.jsonl",
    "claim_evidence_spans.jsonl",
    "section_evidence_plans.jsonl",
    "expansion_audit.jsonl",
    "expert_review_reports.jsonl",
    "expert_review_invocations.jsonl",
    "expert_review_round_history.jsonl",
    "survey_driver_history.jsonl",
    "paper_understanding_results.jsonl",
    "full_text_fetch_plan.jsonl",
    "full_text_fetch_status.jsonl",
    "ab_rebalance_decisions.jsonl",
    "runtime_dispatch_queue.jsonl",
    "runtime_agent_sessions.jsonl",
    "runtime_agent_results.jsonl",
    "gate7_driver_history.jsonl",
    "gate7_repair_results.jsonl",
    "repair_actions.jsonl",
    "regression_checks.jsonl",
    "gate7_regression_requests.jsonl",
    "targeted_rereview_reports.jsonl",
    "tasks.jsonl",
    "failure_ledger.jsonl",
]

LOG_FILES = [
    "orchestrator.jsonl",
    "heartbeat.jsonl",
    "search.jsonl",
    "verification.jsonl",
    "synthesis.jsonl",
]

OUTPUT_FILES = {
    "coverage_matrix.md": "",
    "related_survey_matrix.md": "",
    "references.bib": "",
    "final_report.md": "",
    "contribution_tree.yml": "",
    "release_manifest.json": json.dumps({"released": False, "survey_complete": False, "release_allowed": False}, indent=2, sort_keys=True) + "\n",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "survey-task"


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def initialize_task(
    base_dir: Path,
    topic: str,
    slug: str | None = None,
    output_mode: str = "markdown",
    target: str = "full",
) -> Path:
    task_slug = slug or slugify(topic)
    task_dir = base_dir / task_slug
    state = task_dir / "state"
    logs = task_dir / "logs"
    outputs = task_dir / "outputs"
    state.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    (state / "paper_cards").mkdir(exist_ok=True)

    now = utc_now()
    (state / "task_spec.md").write_text(
        f"# Task Spec\n\nTopic: {topic}\nTarget: {target}\nOutput mode: {output_mode}\n",
        encoding="utf-8",
    )
    write_json(
        state / "topic_profile_spawn_requests.json",
        {
            "next_action": None,
            "spawn_requests": [],
        },
    )
    (state / "survey_type_plan.yml").write_text("", encoding="utf-8")
    (state / "scenario_definitions.yml").write_text("", encoding="utf-8")
    (state / "argument_graph.yml").write_text("", encoding="utf-8")
    (state / "search_protocol.md").write_text("", encoding="utf-8")
    (state / "csur_notes.md").write_text("", encoding="utf-8")
    write_json(
        state / "progress.json",
        {
            "created_at": now,
            "updated_at": now,
            "last_seen": now,
            "status": "running",
            "iteration": 0,
            "phase": "task_lock",
            "current_phase": "task_lock",
            "last_passed_phase": None,
            "blocked_by_phase": None,
            "allowed_next_phase": "survey_type",
            "topic": topic,
            "target": target,
            "next_action": "write survey_type_plan.yml and start high-recall discovery",
        },
    )
    write_json(state / "heartbeat.json", {"last_seen": now, "source": "init_task"})
    write_json(
        state / "completion_gates.json",
        {
            "gate_1_source_identity": False,
            "gate_2_paper_understanding": False,
            "gate_3_claim_evidence": False,
            "gate_4_coverage": False,
            "gate_5_argument_graph": False,
            "gate_6_article_quality": False,
            "gate_7_expert_review": False,
            "final_survey_status": False,
        },
    )
    write_json(
        state / "run_state.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "component": "run_state",
            "target": target,
            "topic": topic,
            "status": "initialized",
            "workflow": {
                "public_entrypoint": "runner.py",
                "legacy_driver": "survey_driver.py",
                "queue": "tasks.jsonl",
            },
            "research_assets": {
                "topic_profile": {"canonical": "state/topic_profile.json", "status": "missing"},
                "paper_cards": {"canonical": "state/paper_cards", "status": "empty"},
                "knowledge_tree": {"canonical": "outputs/knowledge_tree.yml", "status": "missing"},
                "spine_decision": {"canonical": "state/spine_decision.md", "status": "missing"},
                "failure_ledger": {"canonical": "state/failure_ledger.jsonl", "status": "empty"},
            },
            "created_at": now,
            "updated_at": now,
        },
    )
    discovery_summary = {
        "batch_count": 0,
        "active_batch_id": None,
        "pending_batch_count": 0,
        "resolved_batch_count": 0,
    }
    write_json(
        state / "discovery_batches.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "active_batch_id": None,
            "batches": [],
            "summary": discovery_summary,
        },
    )
    write_json(
        state / "discovery_runtime_action.json",
        {
            **status_envelope(
                "discovery_runtime_executor",
                "not_started",
                next_action=None,
                terminal=False,
                blocked=False,
                blocked_by_phase=None,
                active_batch_id=None,
                summary=discovery_summary,
            ),
            "active_batch_id": None,
        },
    )
    write_json(
        state / "discovery_spawn_requests.json",
        {
            "next_action": None,
            "spawn_requests": [],
        },
    )
    write_json(
        state / "review_iteration_status.json",
        {
            "round": 0,
            "last_median_score": None,
            "previous_median_score": None,
            "status": "not_reviewed",
        },
    )
    write_json(
        state / "expert_review_round_status.json",
        {
            "review_round_id": None,
            "status": "not_started",
            "review_freeze": {},
            "all_reports_received": False,
            "reviewers_expected": 5,
            "reviewers_returned": 0,
            "repaired_article_hash": None,
        },
    )
    write_json(
        state / "expert_review_adjudication.json",
        {
            "schema_version": 2,
            "review_round_id": None,
            "review_reports_hash": "",
            "adjudicated_at": None,
            "all_major_weaknesses_adjudicated": False,
            "canonical_weaknesses": [],
        },
    )
    write_json(
        state / "gate7_repair_plan.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "review_round_id": None,
            "candidate_hash": None,
            "major_rebuild_required": False,
            "rerun_policy": None,
            "repair_items": [],
            "summary": {
                "repair_item_count": 0,
                "rollback_phase_counts": {},
                "first_rollback_phase": None,
                "route_counts": {},
                "rerun_policy": None,
                "major_rebuild_required": False,
            },
        },
    )
    runtime_summary = {
        "batch_count": 0,
        "active_batch_id": None,
        "active_rollback_phase": None,
        "pending_batch_count": 0,
        "resolved_batch_count": 0,
        "rerun_policy": None,
        "major_rebuild_required": False,
    }
    write_json(
        state / "gate7_runtime_action.json",
        {
            **status_envelope(
                "gate7_runtime_executor",
                "not_started",
                next_action=None,
                terminal=False,
                blocked=False,
                active_batch_id=None,
                summary=runtime_summary,
            ),
            "status": "not_started",
            "next_action": None,
            "active_batch_id": None,
        },
    )
    write_json(
        state / "gate7_repair_batches.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "active_batch_id": None,
            "batches": [],
            "summary": runtime_summary,
        },
    )
    write_json(
        state / "gate7_spawn_requests.json",
        {
            "next_action": None,
            "spawn_requests": [],
        },
    )
    paper_runtime_summary = {
        "batch_count": 0,
        "active_batch_id": None,
        "active_batch_ids": [],
        "active_paper_ids": [],
        "pending_batch_count": 0,
        "resolved_batch_count": 0,
        "paper_required_count": 0,
        "paper_completed_count": 0,
        "batch_size": 5,
    }
    write_json(
        state / "paper_understanding_batches.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "active_batch_id": None,
            "active_batch_ids": [],
            "batches": [],
            "summary": paper_runtime_summary,
        },
    )
    topic_runtime_summary = {
        "batch_count": 0,
        "active_batch_id": None,
        "active_paper_ids": [],
        "pending_batch_count": 0,
        "resolved_batch_count": 0,
        "paper_count": 0,
        "batch_size": 25,
    }
    write_json(
        state / "topic_relevance_batches.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "active_batch_id": None,
            "batches": [],
            "summary": topic_runtime_summary,
        },
    )
    write_json(
        state / "topic_relevance_second_audit_batches.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "active_batch_id": None,
            "batches": [],
            "summary": topic_runtime_summary,
        },
    )
    write_json(
        state / "topic_relevance_runtime_action.json",
        {
            **status_envelope(
                "topic_relevance_runtime_executor",
                "not_started",
                next_action=None,
                terminal=False,
                blocked=False,
                blocked_by_phase=None,
                active_batch_id=None,
                summary=topic_runtime_summary,
            ),
            "active_batch_id": None,
        },
    )
    write_json(
        state / "topic_relevance_spawn_requests.json",
        {
            "next_action": None,
            "spawn_requests": [],
        },
    )
    write_json(
        state / "paper_understanding_runtime_action.json",
        {
            **status_envelope(
                "paper_understanding_runtime_executor",
                "not_started",
                next_action=None,
                terminal=False,
                blocked=False,
                blocked_by_phase=None,
                active_batch_id=None,
                summary=paper_runtime_summary,
            ),
            "active_batch_id": None,
            "active_batch_ids": [],
        },
    )
    write_json(
        state / "paper_understanding_spawn_requests.json",
        {
            "next_action": None,
            "spawn_requests": [],
        },
    )
    write_json(
        state / "full_text_source_plan_status.json",
        {
            **status_envelope(
                "full_text_source_planner",
                "not_started",
                next_action=None,
                terminal=False,
                blocked=False,
                summary={"planned_paper_count": 0, "with_candidate_url_count": 0, "blocked_no_route_count": 0},
            )
        },
    )
    write_json(
        state / "runtime_dispatch_status.json",
        {
            **status_envelope(
                "runtime_dispatcher",
                "idle",
                next_action="run_survey_driver",
                terminal=False,
                blocked=False,
                summary={
                    "queue_count": 0,
                    "pending_spawn_count": 0,
                    "spawned_count": 0,
                    "result_recorded_count": 0,
                    "invalid_result_count": 0,
                    "rebalance_required_count": 0,
                },
            ),
            "queue": [],
        },
    )
    write_json(
        state / "runtime_active_intent.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "active_phase": None,
            "next_action": None,
            "allowed_request_types": [],
            "phase_generation": "",
            "source_hashes": {},
            "generated_at": None,
        },
    )
    write_json(
        state / "runtime_rebalance_status.json",
        {
            "handled_result_hashes": [],
            "last_rebalance": None,
        },
    )
    write_json(
        state / "phase_status.json",
        {
            **status_envelope(
                "phase_gate",
                "blocked",
                next_action="discovery",
                terminal=False,
                blocked=True,
                blocked_by_phase="discovery",
                active_batch_id=None,
                summary={
                    "valid": False,
                    "blocked_by_phase": "discovery",
                    "last_passed_phase": None,
                    "allowed_next_phase": "discovery",
                    "phase_count": 7,
                    "passed_phase_count": 0,
                },
            ),
            "valid": False,
            "all_required_phases_passed": False,
            "blocked_by_phase": "discovery",
            "last_passed_phase": None,
            "allowed_next_phase": "discovery",
            "phases": {
                "discovery": {"passed": False},
                "source_verification": {"passed": False},
                "paper_understanding": {"passed": False},
                "synthesis": {"passed": False},
                "argument": {"passed": False},
                "article": {"passed": False},
                "expert_review": {"passed": False},
            },
        },
    )
    write_json(
        state / "corpus_expansion.json",
        {
            "required": False,
            "triggered_by": [],
            "visible_external_count": 0,
            "retained_candidate_count": 0,
            "expansion_rounds": [],
            "status": "not_required",
            "waiver_reason": "",
        },
    )
    for filename in STATE_FILES:
        (state / filename).touch()
    for filename in LOG_FILES:
        (logs / filename).touch()
    for filename, content in OUTPUT_FILES.items():
        (outputs / filename).write_text(content, encoding="utf-8")
    (outputs / "method_family_dossiers").mkdir(exist_ok=True)
    (outputs / "benchmark_dossiers").mkdir(exist_ok=True)
    (outputs / "risk_dossiers").mkdir(exist_ok=True)
    (outputs / "application_dossiers").mkdir(exist_ok=True)

    with (logs / "orchestrator.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": now, "event": "task_initialized", "topic": topic}, sort_keys=True) + "\n")
    return task_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", required=True, type=Path)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--output-mode", default="markdown")
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    print(initialize_task(args.base_dir, args.topic, args.slug, args.output_mode, args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
