#!/usr/bin/env python3
"""Build an evidence-first Gate 7 repair plan from adjudicated weaknesses."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .expert_review_gate import REQUIRED_DIMENSIONS, ROUTE_EVIDENCE_REQUIREMENTS
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
except ImportError:  # pragma: no cover
    from expert_review_gate import REQUIRED_DIMENSIONS, ROUTE_EVIDENCE_REQUIREMENTS
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl


ROUTE_REPAIR_METADATA = {
    "source_verification": {
        "rollback_phase": "source_verification",
        "changed_artifacts": ["state/papers.jsonl", "state/full_text_sources.jsonl"],
        "acceptance_validators": ["verify_sources", "phase_gate:source_verification"],
    },
    "coverage": {
        "rollback_phase": "source_verification",
        "changed_artifacts": ["state/raw_candidates.jsonl", "state/search_routes.jsonl", "state/corpus_expansion.json", "state/citation_plan.jsonl"],
        "acceptance_validators": ["validate_coverage", "phase_gate:source_verification"],
    },
    "paper_understanding": {
        "rollback_phase": "paper_understanding",
        "changed_artifacts": ["state/paper_mechanism_cards.jsonl", "state/full_text_sources.jsonl"],
        "acceptance_validators": ["validate_paper_understanding", "phase_gate:paper_understanding"],
    },
    "claim_evidence": {
        "rollback_phase": "synthesis",
        "changed_artifacts": ["state/claim_evidence_spans.jsonl", "state/full_text_sources.jsonl", "state/section_evidence_plans.jsonl"],
        "acceptance_validators": ["validate_claim_evidence", "phase_gate:synthesis"],
    },
    "synthesis_dossiers": {
        "rollback_phase": "synthesis",
        "changed_artifacts": ["outputs/method_family_dossiers", "outputs/contribution_tree.yml", "state/claim_evidence_spans.jsonl"],
        "acceptance_validators": ["validate_synthesis_dossiers", "build_contribution_tree", "phase_gate:synthesis"],
    },
    "benchmark_dossiers": {
        "rollback_phase": "synthesis",
        "changed_artifacts": ["outputs/benchmark_dossiers", "state/claim_evidence_spans.jsonl"],
        "acceptance_validators": ["validate_synthesis_dossiers", "phase_gate:synthesis"],
    },
    "argument_graph": {
        "rollback_phase": "argument",
        "changed_artifacts": ["state/argument_graph.yml", "outputs/article_plan.md", "state/section_evidence_plans.jsonl"],
        "acceptance_validators": ["validate_argument_graph", "validate_section_evidence_plans", "phase_gate:argument"],
    },
    "section_evidence_plan": {
        "rollback_phase": "argument",
        "changed_artifacts": ["state/section_evidence_plans.jsonl", "outputs/article_plan.md", "outputs/survey_candidate.md"],
        "acceptance_validators": ["validate_section_evidence_plans", "validate_claim_evidence", "phase_gate:argument"],
    },
    "article_quality": {
        "rollback_phase": "article",
        "changed_artifacts": ["outputs/survey_candidate.md", "outputs/survey_candidate.html", "outputs/appendix.md"],
        "acceptance_validators": ["validate_article_quality", "render_survey_html", "phase_gate:article"],
    },
}

FULL_REROUND_ROUTES = {
    "source_verification",
    "coverage",
    "paper_understanding",
    "claim_evidence",
    "synthesis_dossiers",
    "benchmark_dossiers",
    "argument_graph",
    "section_evidence_plan",
}

REPAIR_PLAN_SCHEMA_VERSION = 1
ROLLBACK_PHASE_ORDER = ["source_verification", "paper_understanding", "synthesis", "argument", "article"]


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _score(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _threshold(target: str) -> float:
    if target == "csur":
        return 9.0
    if target == "full":
        return 8.5
    return 0.0


def _dimension_medians(reports: list[dict]) -> dict[str, float | None]:
    values_by_name: dict[str, list[float]] = {name: [] for name in REQUIRED_DIMENSIONS}
    for report in reports:
        dimensions = report.get("dimension_scores")
        if not isinstance(dimensions, dict):
            continue
        for name in REQUIRED_DIMENSIONS:
            score = _score(dimensions.get(name))
            if score is not None:
                values_by_name[name].append(score)
    return {name: _median(values) for name, values in values_by_name.items()}


def _overall_median(reports: list[dict]) -> float | None:
    scores = [_score(report.get("overall_score")) for report in reports]
    return _median([score for score in scores if score is not None])


def _route_counts(weaknesses: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for weakness in weaknesses:
        route = str(weakness.get("route_to") or "article_quality")
        counts[route] = counts.get(route, 0) + 1
    return counts


def _rollback_phase_counts(repair_items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in repair_items:
        phase = str(item.get("rollback_phase") or "article")
        counts[phase] = counts.get(phase, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: _phase_key(item[0])))


def _phase_key(phase: str) -> tuple[int, str]:
    try:
        return (ROLLBACK_PHASE_ORDER.index(phase), phase)
    except ValueError:
        return (len(ROLLBACK_PHASE_ORDER), phase)


def _first_rollback_phase(repair_items: list[dict]) -> str | None:
    phases = {str(item.get("rollback_phase") or "article") for item in repair_items}
    if not phases:
        return None
    return sorted(phases, key=_phase_key)[0]


def _repair_plan_summary(
    repair_items: list[dict],
    route_counts: dict[str, int],
    rerun_policy: str,
    major_rebuild_required: bool,
) -> dict:
    return {
        "repair_item_count": len(repair_items),
        "rollback_phase_counts": _rollback_phase_counts(repair_items),
        "first_rollback_phase": _first_rollback_phase(repair_items),
        "route_counts": route_counts,
        "rerun_policy": rerun_policy,
        "major_rebuild_required": major_rebuild_required,
    }


def _repair_item(weakness: dict, idx: int) -> dict:
    route = str(weakness.get("route_to") or "article_quality")
    metadata = ROUTE_REPAIR_METADATA.get(route, ROUTE_REPAIR_METADATA["article_quality"])
    required = set()
    if isinstance(weakness.get("required_evidence_check"), list):
        required.update(str(value) for value in weakness.get("required_evidence_check") or [] if str(value).strip())
    required.update(ROUTE_EVIDENCE_REQUIREMENTS.get(route, {"section_evidence_plans"}))
    return {
        "repair_id": f"RR{idx:03d}",
        "weakness_id": str(weakness.get("weakness_id") or f"CW{idx:03d}"),
        "severity": str(weakness.get("severity") or "major"),
        "route_to": route,
        "source_reviewers": list(weakness.get("source_reviewers") or []),
        "source_weakness_ids": list(weakness.get("source_weakness_ids") or []),
        "affected_sections": list(weakness.get("affected_sections") or []),
        "affected_papers": list(weakness.get("affected_papers") or []),
        "affected_claims": list(weakness.get("affected_claims") or []),
        "required_evidence_check": sorted(required),
        "rollback_phase": metadata["rollback_phase"],
        "changed_artifacts": list(metadata["changed_artifacts"]),
        "acceptance_validators": list(metadata["acceptance_validators"]),
        "repair_acceptance_criteria": str(weakness.get("repair_acceptance_criteria") or "Resolve the weakness without unsupported claims."),
    }


def _history_replace(history: list[dict], entry: dict) -> list[dict]:
    key = (str(entry.get("review_round_id") or ""), str(entry.get("candidate_hash") or ""))
    kept = [
        row for row in history
        if (str(row.get("review_round_id") or ""), str(row.get("candidate_hash") or "")) != key
    ]
    kept.append(entry)
    return kept


def _write_iteration_status(task_dir: Path, history: list[dict], target: str, current_status: str) -> dict:
    state = task_dir / "state"
    medians = [row.get("median_score") for row in history if row.get("median_score") is not None]
    last = medians[-1] if medians else None
    previous = medians[-2] if len(medians) >= 2 else None
    quality_limited = False
    if last is not None and previous is not None:
        threshold = _threshold(target)
        quality_limited = last < threshold and last >= 8.0 and abs(float(last) - float(previous)) < 0.2
    status = {
        "round": len(history),
        "last_median_score": last,
        "previous_median_score": previous,
        "status": "quality_limited" if quality_limited else current_status,
    }
    write_json(state / "review_iteration_status.json", status)
    return status


def build_repair_plan(task_dir: Path, target: str = "full") -> dict:
    state = task_dir / "state"
    outputs = task_dir / "outputs"
    adjudication = read_json(state / "expert_review_adjudication.json")
    round_status = read_json(state / "expert_review_round_status.json")
    reports = read_jsonl(state / "expert_review_reports.jsonl")
    weaknesses = [item for item in adjudication.get("canonical_weaknesses") or [] if isinstance(item, dict)]
    median_score = _overall_median(reports)
    dimension_medians = _dimension_medians(reports)
    route_counts = _route_counts(weaknesses)
    repair_items = [_repair_item(weakness, idx) for idx, weakness in enumerate(weaknesses, start=1)]
    route_requires_full_round = any(item["route_to"] in FULL_REROUND_ROUTES for item in repair_items)
    low_score_major_failure = median_score is not None and median_score < 8.0
    major_rebuild_required = bool(low_score_major_failure or route_requires_full_round)
    rerun_policy = "full_gate7_round" if major_rebuild_required else "targeted_rereview"
    plan = {
        "schema_version": REPAIR_PLAN_SCHEMA_VERSION,
        "review_round_id": round_status.get("review_round_id") or adjudication.get("review_round_id") or "round-1",
        "candidate_hash": _sha256_file(outputs / "survey_candidate.md"),
        "target": target,
        "median_score": median_score,
        "dimension_medians": dimension_medians,
        "canonical_weakness_count": len(weaknesses),
        "route_counts": route_counts,
        "major_rebuild_required": major_rebuild_required,
        "low_score_major_failure": low_score_major_failure,
        "rerun_policy": rerun_policy,
        "next_action": "rollback_repair" if major_rebuild_required else "targeted_repair",
        "repair_items": repair_items,
    }
    plan["summary"] = _repair_plan_summary(repair_items, route_counts, rerun_policy, major_rebuild_required)
    write_json(state / "gate7_repair_plan.json", plan)
    history_path = state / "expert_review_round_history.jsonl"
    history_entry = {
        "review_round_id": plan["review_round_id"],
        "candidate_hash": plan["candidate_hash"],
        "median_score": median_score,
        "dimension_medians": dimension_medians,
        "canonical_weaknesses": weaknesses,
        "route_counts": route_counts,
        "rerun_policy": rerun_policy,
        "major_rebuild_required": major_rebuild_required,
    }
    history = _history_replace(read_jsonl(history_path), history_entry)
    write_jsonl(history_path, history)
    _write_iteration_status(
        task_dir,
        history,
        target,
        "major_rebuild_required" if major_rebuild_required else "targeted_repair_required",
    )
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_repair_plan(args.task_dir, args.target)
    text = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
