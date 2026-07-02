#!/usr/bin/env python3
"""Validate paper-level scientific contribution understanding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FIELDS = [
    "paper_id",
    "title",
    "survey_role",
    "level",
    "motivation",
    "problem_setting",
    "task_definition",
    "method_pipeline",
    "implementation_details",
    "experimental_setup",
    "main_results",
    "limitations_and_confounders",
    "relation_to_prior_work",
    "what_it_changes_in_the_survey_argument",
    "evidence_spans",
]

RELATION_TERMS = {
    "extends",
    "replaces",
    "contradicts",
    "benchmarks",
    "reframes",
    "surveys",
    "alternative",
    "predecessor",
    "successor",
    "conflict",
    "扩展",
    "替代",
    "冲突",
    "基准",
    "重构",
    "综述",
}

GENERIC_RELATIONS = {
    "this is related to prior work",
    "related to prior work",
    "positions the work relative to adjacent embodied-memory designs in the mechanism taxonomy",
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def depth_ids(citation_plan: list[dict]) -> set[str]:
    return {
        str(item["paper_id"])
        for item in citation_plan
        if item.get("paper_id") and str(item.get("depth") or item.get("level") or "").upper() in {"A", "B"}
    }


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _has_benchmark(card: dict) -> bool:
    return _nonempty(card.get("benchmark_or_dataset")) or _nonempty(card.get("benchmark_or_environment"))


def _valid_result(result: dict) -> bool:
    evidence = str(result.get("evidence_span") or result.get("evidence") or "")
    if not (
        _nonempty(result.get("result") or result.get("claim"))
        and _nonempty(evidence)
        and str(result.get("claim_strength") or result.get("strength") or "") in {"demonstrates", "shows", "suggests", "may indicate"}
    ):
        return False
    lowered = evidence.lower()
    return not any(term in lowered for term in ["title only", "title/abstract only", "paper title alone"])


def _has_relation_type(value) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    lowered = text.lower().rstrip(".")
    if lowered in GENERIC_RELATIONS:
        return False
    return any(term in lowered for term in RELATION_TERMS)


def validate_paper_understanding(cards: list[dict], citation_plan: list[dict] | None = None) -> dict:
    required_ids = depth_ids(citation_plan or [])
    by_id = {str(card.get("paper_id")): card for card in cards if card.get("paper_id")}
    errors: list[str] = []
    invalid_cards: dict[str, list[str]] = {}
    for pid in sorted(required_ids - set(by_id)):
        invalid_cards[pid] = ["missing_mechanism_card"]
    for card in cards:
        pid = str(card.get("paper_id") or "<missing>")
        card_errors = []
        for field in REQUIRED_FIELDS:
            if not _nonempty(card.get(field)):
                card_errors.append(f"missing_{field}")
        if not _has_benchmark(card):
            card_errors.append("missing_benchmark_or_dataset")
        if not isinstance(card.get("method_pipeline"), list) or len(card.get("method_pipeline", [])) < 2:
            card_errors.append("method_pipeline_too_thin")
        if not isinstance(card.get("implementation_details"), dict) or len(card.get("implementation_details", {})) < 2:
            card_errors.append("implementation_details_too_thin")
        if not isinstance(card.get("experimental_setup"), dict) or len(card.get("experimental_setup", {})) < 2:
            card_errors.append("experimental_setup_too_thin")
        experiment = card.get("experimental_setup") if isinstance(card.get("experimental_setup"), dict) else {}
        if not _nonempty(experiment.get("metrics")):
            card_errors.append("missing_metrics")
        if not _nonempty(experiment.get("baselines")):
            card_errors.append("missing_baselines")
        if not _nonempty(experiment.get("ablations")):
            card_errors.append("missing_ablations")
        if not _nonempty(experiment.get("evaluation_protocol")):
            card_errors.append("missing_evaluation_protocol")
        results = card.get("main_results") or []
        if not isinstance(results, list) or not results or not all(isinstance(r, dict) and _valid_result(r) for r in results):
            card_errors.append("invalid_main_results")
        limitations = card.get("limitations_and_confounders") or []
        if not isinstance(limitations, list) or len(limitations) < 2:
            card_errors.append("limitations_too_thin")
        if not _has_relation_type(card.get("relation_to_prior_work")):
            card_errors.append("generic_relation_to_prior_work")
        role = str(card.get("survey_role") or "").lower()
        result_text = " ".join(str((r or {}).get("result") or (r or {}).get("claim") or "") for r in results if isinstance(r, dict)).lower()
        if role == "survey" and any(term in result_text for term in ["outperforms", "improves", "beats", "提升", "优于"]):
            card_errors.append("survey_used_as_experimental_result")
        if role == "benchmark" and any(term in result_text for term in ["our method", "the method improves", "proposed system", "新方法"]):
            card_errors.append("benchmark_used_as_method_result")
        if card_errors:
            invalid_cards[pid] = card_errors
    if invalid_cards:
        errors.append("invalid_paper_understanding")
    return {
        "valid": not errors,
        "errors": errors,
        "total_cards": len(cards),
        "required_a_b_cards": len(required_ids),
        "invalid_cards": invalid_cards,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-mechanism-cards", required=True, type=Path)
    parser.add_argument("--citation-plan", type=Path)
    args = parser.parse_args()
    result = validate_paper_understanding(
        read_jsonl(args.paper_mechanism_cards),
        read_jsonl(args.citation_plan) if args.citation_plan else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
