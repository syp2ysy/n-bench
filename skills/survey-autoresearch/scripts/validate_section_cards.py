#!/usr/bin/env python3
"""Validate section-card plans used to draft argument-driven survey sections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ACCEPTED_STRUCTURES = [
    "总-分-总",
    "general-specific-general",
    "claim-evidence-implication",
    "capability-protocol-confounder-gap",
    "definition-dimensions-examples-implication",
]


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


def validate_section_cards(cards: list[dict]) -> dict:
    errors: list[str] = []
    valid_cards = 0
    for idx, card in enumerate(cards, start=1):
        card_id = card.get("section_id") or f"section_card_{idx}"
        card_errors: list[str] = []
        for field in [
            "section_id",
            "title",
            "reader_question",
            "section_thesis",
            "opening_move",
            "closing_move",
            "required_display_item",
        ]:
            if not _nonempty(card.get(field)):
                card_errors.append(f"missing {field}")
        structure = str(card.get("structure") or "").lower()
        if not any(pattern.lower() in structure for pattern in ACCEPTED_STRUCTURES):
            card_errors.append("structure must be 总-分-总 or an accepted argument pattern")
        moves = card.get("subsection_moves")
        if not _nonempty(moves):
            card_errors.append("missing subsection_moves")
        elif not isinstance(moves, list):
            card_errors.append("subsection_moves must be a list")
        else:
            for move_idx, move in enumerate(moves, start=1):
                if not isinstance(move, dict):
                    card_errors.append(f"subsection_moves[{move_idx}] must be an object")
                    continue
                for field in ["subsection", "claim", "required_comparison", "implication"]:
                    if not _nonempty(move.get(field)):
                        card_errors.append(f"subsection_moves[{move_idx}] missing {field}")
                papers = [paper for paper in _as_list(move.get("papers")) if _nonempty(paper)]
                if len(papers) < 2 and not _nonempty(move.get("gap_reason")):
                    card_errors.append(f"subsection_moves[{move_idx}] needs at least 2 papers or gap_reason")
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
    parser.add_argument("--section-cards", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_section_cards(read_jsonl(args.section_cards))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
