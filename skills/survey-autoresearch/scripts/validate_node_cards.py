#!/usr/bin/env python3
"""Validate system-node cards used before deep survey synthesis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


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


def validate_node_cards(cards: list[dict]) -> dict:
    errors: list[str] = []
    valid_cards = 0
    for idx, card in enumerate(cards, start=1):
        node = card.get("node") or f"node_card_{idx}"
        card_errors: list[str] = []
        for field in ["node", "role_in_system", "inputs", "outputs"]:
            if not _nonempty(card.get(field)):
                card_errors.append(f"missing {field}")
        if not (_nonempty(card.get("why_it_matters")) or _nonempty(card.get("why_it_matters_in_embodiment"))):
            card_errors.append("missing why_it_matters")
        if not _as_list(card.get("main_design_families")):
            card_errors.append("missing main_design_families")
        if len(_as_list(card.get("representative_papers"))) < 2:
            card_errors.append("representative_papers needs at least 2 entries")
        if not _as_list(card.get("failure_modes")):
            card_errors.append("missing failure_modes")
        if not _as_list(card.get("evaluation_signals")):
            card_errors.append("missing evaluation_signals")
        if card_errors:
            errors.append(f"{node}: " + "; ".join(card_errors))
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
    parser.add_argument("--node-cards", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_node_cards(read_jsonl(args.node_cards))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
