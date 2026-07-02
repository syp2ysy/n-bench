#!/usr/bin/env python3
"""Validate method-family and benchmark synthesis dossiers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .verify_sources import read_jsonl
    from .validate_scenario_definitions import parse_structured_text
except ImportError:  # pragma: no cover
    from verify_sources import read_jsonl
    from validate_scenario_definitions import parse_structured_text


METHOD_REQUIRED = [
    "family",
    "family_motivation",
    "assumptions",
    "representative_a_papers",
    "shared_mechanism_pattern",
    "differences_among_representative_papers",
    "relation_graph",
    "common_benchmarks",
    "evidence_strength_summary",
    "failure_modes",
    "open_questions",
    "advances_central_story",
    "scenario_links",
]

BENCHMARK_REQUIRED = [
    "benchmark",
    "capability_tested",
    "task_formulation",
    "input_output",
    "environment_dataset",
    "metrics",
    "common_baselines",
    "reported_memory_specific_ablations",
    "missing_diagnostic_controls",
    "what_it_can_support",
    "what_it_cannot_support",
    "representative_papers_using_it",
    "confounders",
    "scenario_links",
]


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def read_dossier_dir(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for item in sorted(path.glob("*")):
        if item.is_dir() or item.name.startswith("."):
            continue
        text = item.read_text(encoding="utf-8")
        parsed = parse_structured_text(text)
        if isinstance(parsed, dict) and parsed:
            rows.append(parsed)
    return rows


def _paper_ids(cards: list[dict]) -> set[str]:
    return {str(card.get("paper_id")) for card in cards if card.get("paper_id")}


def _scenario_names(scenario_definitions) -> set[str]:
    data = parse_structured_text(scenario_definitions) if isinstance(scenario_definitions, str) else (scenario_definitions or {})
    scenarios = data.get("scenarios") or data.get("contexts") or data.get("domains") or []
    names = set()
    if isinstance(scenarios, list):
        for item in scenarios:
            name = item.get("scenario") or item.get("context") or item.get("domain")
            if name:
                names.add(str(name))
    return names


def validate_synthesis_dossiers(method_dossiers: list[dict], benchmark_dossiers: list[dict], scenario_definitions, mechanism_cards: list[dict], target: str = "full") -> dict:
    errors: list[str] = []
    invalid_methods: dict[str, list[str]] = {}
    invalid_benchmarks: dict[str, list[str]] = {}
    card_ids = _paper_ids(mechanism_cards)
    scenarios = _scenario_names(scenario_definitions)
    if target != "short" and not method_dossiers:
        errors.append("missing_method_family_dossiers")
    if target != "short" and not benchmark_dossiers:
        errors.append("missing_benchmark_dossiers")
    for dossier in method_dossiers:
        name = str(dossier.get("family") or "<missing>")
        item_errors = []
        for field in METHOD_REQUIRED:
            if not _nonempty(dossier.get(field)):
                item_errors.append(f"missing_{field}")
        reps = [str(pid) for pid in dossier.get("representative_a_papers") or []]
        if len(reps) < 2 and not _nonempty(dossier.get("evidence_gap")):
            item_errors.append("too_few_representative_a_papers")
        unknown = [pid for pid in reps if pid not in card_ids]
        if unknown:
            item_errors.append("unknown_representative_papers:" + ",".join(unknown))
        if _nonempty(dossier.get("scenario_links")) and scenarios:
            unknown_scenarios = [str(s) for s in dossier.get("scenario_links") or [] if str(s) not in scenarios]
            if unknown_scenarios:
                item_errors.append("unknown_scenario_links:" + ",".join(unknown_scenarios))
        if not _has_relation_graph(dossier.get("relation_graph")):
            item_errors.append("missing_cross_paper_relation")
        if item_errors:
            invalid_methods[name] = item_errors
    for dossier in benchmark_dossiers:
        name = str(dossier.get("benchmark") or "<missing>")
        item_errors = []
        for field in BENCHMARK_REQUIRED:
            if not _nonempty(dossier.get(field)):
                item_errors.append(f"missing_{field}")
        if _nonempty(dossier.get("scenario_links")) and scenarios:
            unknown_scenarios = [str(s) for s in dossier.get("scenario_links") or [] if str(s) not in scenarios]
            if unknown_scenarios:
                item_errors.append("unknown_scenario_links:" + ",".join(unknown_scenarios))
        if item_errors:
            invalid_benchmarks[name] = item_errors
    if invalid_methods:
        errors.append("invalid_method_dossiers")
    if invalid_benchmarks:
        errors.append("invalid_benchmark_dossiers")
    return {
        "valid": not errors,
        "errors": errors,
        "method_dossiers": len(method_dossiers),
        "benchmark_dossiers": len(benchmark_dossiers),
        "invalid_methods": invalid_methods,
        "invalid_benchmarks": invalid_benchmarks,
    }


def _has_relation_graph(value) -> bool:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("source") and item.get("target") and item.get("relation"):
                return True
    if isinstance(value, str):
        return any(term in value.lower() for term in ["extends", "replaces", "contradicts", "alternative", "benchmarks", "reframes", "surveys", "trade-off", "tradeoff"])
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method-family-dossiers", required=True, type=Path)
    parser.add_argument("--benchmark-dossiers", required=True, type=Path)
    parser.add_argument("--scenario-definitions", required=True, type=Path)
    parser.add_argument("--paper-mechanism-cards", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    result = validate_synthesis_dossiers(
        read_dossier_dir(args.method_family_dossiers),
        read_dossier_dir(args.benchmark_dossiers),
        args.scenario_definitions.read_text(encoding="utf-8"),
        read_jsonl(args.paper_mechanism_cards),
        args.target,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
