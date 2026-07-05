#!/usr/bin/env python3
"""Persist review failures as reusable root-cause ledger entries."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_json, read_jsonl, write_jsonl
    from .status_schema import status_envelope
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_json, read_jsonl, write_jsonl
    from status_schema import status_envelope


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


ROOT_CAUSE_BY_ROUTE = {
    "source_verification": "topic_drift",
    "coverage": "missing_core_paper",
    "paper_understanding": "shallow_paper_card",
    "claim_evidence": "unsupported_claim",
    "section_evidence_plan": "unsupported_claim",
    "section_evidence_plans": "unsupported_claim",
    "citation": "citation_mismatch",
    "synthesis": "taxonomy_not_field_native",
    "synthesis_dossiers": "taxonomy_not_field_native",
    "argument_graph": "taxonomy_not_field_native",
    "contribution_tree": "taxonomy_not_field_native",
    "benchmark_dossiers": "benchmark_misread",
    "article_quality": "padding_or_repetition",
}

ROUTE_CHAIN_BY_ROOT = {
    "topic_drift": "topic_profile -> corpus_pipeline -> relevance_audit",
    "missing_core_paper": "corpus_discovery -> relevance_audit -> citation_plan",
    "shallow_paper_card": "paper_reader -> paper_card_verifier",
    "unsupported_claim": "claim_evidence -> section_plan -> section_writer",
    "citation_mismatch": "evidence_verifier -> section_writer",
    "taxonomy_not_field_native": "knowledge_tree -> related_survey_alignment -> spine_planner",
    "benchmark_misread": "paper_reader -> benchmark_dossier -> knowledge_tree",
    "padding_or_repetition": "section_writer -> article_assembler",
    "weak_open_problems": "knowledge_tree -> evidence_gap_analysis",
}


def _root_cause(weakness: dict) -> str:
    route = str(weakness.get("route_to") or weakness.get("rollback_phase") or "").strip()
    return ROOT_CAUSE_BY_ROUTE.get(route, "unsupported_claim")


def _entry_from_weakness(index: int, review_round_id: str, weakness: dict) -> dict:
    root = _root_cause(weakness)
    weakness_id = str(weakness.get("weakness_id") or weakness.get("canonical_weakness_id") or f"CW{index:03d}")
    return {
        "failure_id": f"F{index:03d}",
        "review_round_id": review_round_id,
        "source_weakness_ids": weakness.get("source_weakness_ids") or weakness.get("source_reviewers") or [weakness_id],
        "canonical_weakness_id": weakness_id,
        "root_cause": root,
        "symptom": weakness.get("evidence_quote") or weakness.get("repair_acceptance_criteria") or weakness.get("why_it_matters") or "",
        "affected_artifacts": weakness.get("changed_artifacts") or weakness.get("affected_artifacts") or [],
        "affected_sections": weakness.get("affected_sections") or [],
        "affected_papers": weakness.get("affected_papers") or [],
        "affected_claims": weakness.get("affected_claims") or [],
        "repair_route": ROUTE_CHAIN_BY_ROOT.get(root, "repair_planner"),
        "failed_assumption": weakness.get("why_it_matters") or "",
        "prevention_rule": weakness.get("repair_acceptance_criteria") or weakness.get("repair_action") or "Repair must be evidence-backed and rerun the relevant gate.",
        "status": "unresolved",
        "verifier": ",".join(str(item) for item in weakness.get("source_reviewers") or []),
        "created_at": _utc_now(),
    }


def append_failures_from_adjudication(task_dir: Path) -> dict:
    state = task_dir / "state"
    adjudication = read_json(state / "expert_review_adjudication.json")
    weaknesses = [row for row in adjudication.get("canonical_weaknesses") or [] if isinstance(row, dict)]
    existing = read_jsonl(state / "failure_ledger.jsonl")
    existing_keys = {str(row.get("canonical_weakness_id") or "") for row in existing}
    review_round_id = str(adjudication.get("review_round_id") or "round-unknown")
    next_index = len(existing) + 1
    new_entries = []
    for weakness in weaknesses:
        key = str(weakness.get("weakness_id") or weakness.get("canonical_weakness_id") or "")
        if key and key in existing_keys:
            continue
        new_entries.append(_entry_from_weakness(next_index, review_round_id, weakness))
        next_index += 1
    write_jsonl(state / "failure_ledger.jsonl", existing + new_entries)
    return {
        **status_envelope(
            "failure_ledger",
            "recorded" if new_entries else "idle",
            terminal=False,
            blocked=bool(new_entries),
            summary={"new_failure_count": len(new_entries), "total_failure_count": len(existing) + len(new_entries)},
        ),
        "new_failures": new_entries,
    }


def collect_failure_ledger(task_dir: Path) -> dict:
    rows = read_jsonl(task_dir / "state" / "failure_ledger.jsonl")
    unresolved = [row for row in rows if row.get("status") != "resolved"]
    return {
        **status_envelope(
            "failure_ledger",
            "blocked" if unresolved else "complete",
            terminal=not bool(unresolved),
            blocked=bool(unresolved),
            summary={"failure_count": len(rows), "unresolved_count": len(unresolved)},
        ),
        "failures": rows,
        "unresolved_count": len(unresolved),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--append-from-adjudication", action="store_true")
    parser.add_argument("--collect-status", action="store_true")
    args = parser.parse_args()
    result = append_failures_from_adjudication(args.task_dir) if args.append_from_adjudication else collect_failure_ledger(args.task_dir)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
