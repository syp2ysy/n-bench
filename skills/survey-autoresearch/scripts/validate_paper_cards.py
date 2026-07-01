#!/usr/bin/env python3
"""Validate deep paper-card records for survey synthesis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FIELDS = [
    "paper_id",
    "survey_role",
    "problem",
    "method_summary",
    "mechanism_or_contribution",
    "what_it_teaches_the_survey",
]

MECHANISM_FIELDS = [
    "system_node",
    "memory_node",
    "representation",
    "inputs",
    "outputs",
    "write_policy",
    "read_policy",
    "update_or_consolidation",
    "controller_interface",
    "planner_interface",
]

ALLOWED_ROLES = {
    "foundational",
    "system",
    "benchmark",
    "application",
    "negative",
    "failure",
    "survey",
    "bridge",
    "frontier",
    "ablation",
}


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


def validate_paper_cards(cards: list[dict]) -> dict:
    errors: list[str] = []
    valid_cards = 0
    seen: set[str] = set()
    for idx, card in enumerate(cards, start=1):
        card_id = card.get("paper_id") or f"paper_card_{idx}"
        card_errors: list[str] = []
        if card.get("paper_id") in seen:
            card_errors.append("duplicate paper_id")
        if card.get("paper_id"):
            seen.add(card["paper_id"])
        for field in REQUIRED_FIELDS:
            if not _nonempty(card.get(field)):
                card_errors.append(f"missing {field}")
        role = str(card.get("survey_role") or "").lower()
        if role and role not in ALLOWED_ROLES:
            card_errors.append(f"unknown survey_role {role}")
        if not (_nonempty(card.get("system_node")) or _nonempty(card.get("memory_node"))):
            card_errors.append("missing system_node")
        mechanism_count = sum(1 for field in MECHANISM_FIELDS if _nonempty(card.get(field)))
        if mechanism_count < 4:
            card_errors.append("needs at least 4 mechanism fields")
        if not _as_list(card.get("failure_modes")):
            card_errors.append("missing failure_modes")
        if not _as_list(card.get("limitations")):
            card_errors.append("missing limitations")
        if not _as_list(card.get("evidence_spans")):
            card_errors.append("missing evidence_spans")
        if card_errors:
            errors.append(f"{card_id}: " + "; ".join(card_errors))
        else:
            valid_cards += 1
    return {
        "valid": bool(cards) and not errors,
        "total_cards": len(cards),
        "valid_cards": valid_cards,
        "invalid_cards": len(cards) - valid_cards,
        "errors": errors,
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-cards", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_paper_cards(read_jsonl(args.paper_cards))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
