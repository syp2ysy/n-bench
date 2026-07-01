#!/usr/bin/env python3
"""Validate paper-level scientific mechanism cards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CORE_FIELDS = [
    "paper_id",
    "title",
    "survey_role",
    "motivation",
    "problem_setting",
    "method_overview",
    "architecture_or_pipeline",
    "memory_design",
    "experimental_setup",
    "main_results",
    "limitations_and_confounders",
    "comparison_to_prior_work",
    "how_it_changes_the_survey_argument",
    "evidence_spans",
]

A_LEVEL_EXTRA_FIELDS = [
    "task_definition",
    "benchmark_or_environment",
    "implementation_details",
]

MEMORY_DESIGN_FIELDS = [
    "record_schema",
    "write_trigger",
    "storage",
    "read_key",
    "update_policy",
    "controller_interface",
]

EXPERIMENTAL_FIELDS = [
    "datasets_envs",
    "metrics",
    "baselines",
    "ablations",
]

RESULT_FIELDS = ["claim", "evidence", "strength"]


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def ab_paper_ids(citation_plan: list[dict] | None) -> set[str]:
    return {
        item.get("paper_id")
        for item in (citation_plan or [])
        if (item.get("depth") or "").upper() in {"A", "B"} and item.get("paper_id")
    }


def _card_level(card: dict, citation_depth: dict[str, str]) -> str:
    return str(card.get("level") or citation_depth.get(card.get("paper_id"), "") or "").upper()


def validate_paper_mechanism_cards(cards: list[dict], citation_plan: list[dict] | None = None) -> dict:
    errors: list[str] = []
    valid_cards = 0
    citation_depth = {
        item.get("paper_id"): (item.get("depth") or "").upper()
        for item in (citation_plan or [])
        if item.get("paper_id")
    }
    seen = {card.get("paper_id") for card in cards if card.get("paper_id")}
    missing_cards = sorted(ab_paper_ids(citation_plan) - seen)
    for idx, card in enumerate(cards, start=1):
        paper_id = card.get("paper_id") or f"mechanism_card_{idx}"
        card_errors: list[str] = []
        level = _card_level(card, citation_depth)
        for field in CORE_FIELDS:
            if not _nonempty(card.get(field)):
                card_errors.append(f"missing {field}")
        if level == "A":
            for field in A_LEVEL_EXTRA_FIELDS:
                if not _nonempty(card.get(field)):
                    card_errors.append(f"missing A-level field {field}")
        memory_design = card.get("memory_design") or {}
        if not isinstance(memory_design, dict):
            card_errors.append("memory_design must be object")
        else:
            missing = [field for field in MEMORY_DESIGN_FIELDS if not _nonempty(memory_design.get(field))]
            if missing:
                card_errors.append("missing memory_design fields " + ",".join(missing))
        experimental_setup = card.get("experimental_setup") or {}
        if not isinstance(experimental_setup, dict):
            card_errors.append("experimental_setup must be object")
        else:
            missing = [field for field in EXPERIMENTAL_FIELDS if not _nonempty(experimental_setup.get(field))]
            if level == "A" and missing:
                card_errors.append("missing experimental_setup fields " + ",".join(missing))
        for result_idx, result in enumerate(_as_list(card.get("main_results")), start=1):
            if not isinstance(result, dict):
                card_errors.append(f"main_results[{result_idx}] must be object")
                continue
            missing = [field for field in RESULT_FIELDS if not _nonempty(result.get(field))]
            if missing:
                card_errors.append(f"main_results[{result_idx}] missing " + ",".join(missing))
        if card_errors:
            errors.append(f"{paper_id}: " + "; ".join(card_errors))
        else:
            valid_cards += 1
    for paper_id in missing_cards:
        errors.append(f"{paper_id}: missing paper_mechanism_card for A/B paper")
    return {
        "valid": bool(cards) and not errors,
        "total_cards": len(cards),
        "valid_cards": valid_cards,
        "invalid_cards": len(cards) - valid_cards,
        "missing_paper_mechanism_cards": missing_cards,
        "errors": errors,
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-mechanism-cards", required=True, type=Path)
    parser.add_argument("--citation-plan", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_paper_mechanism_cards(
        read_jsonl(args.paper_mechanism_cards),
        citation_plan=read_jsonl(args.citation_plan) if args.citation_plan else None,
    )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
