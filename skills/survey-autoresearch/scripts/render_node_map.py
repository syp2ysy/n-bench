#!/usr/bin/env python3
"""Render system-node cards as a Markdown synthesis table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def render_node_map(cards: list[dict]) -> str:
    rows = [
        "| node | role | inputs | outputs | representative papers | failure modes | evaluation signals |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for card in cards:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(card.get("node")),
                    _cell(card.get("role_in_system")),
                    _cell(card.get("inputs")),
                    _cell(card.get("outputs")),
                    _cell(card.get("representative_papers")),
                    _cell(card.get("failure_modes")),
                    _cell(card.get("evaluation_signals")),
                ]
            )
            + " |"
        )
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-cards", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = render_node_map(read_jsonl(args.node_cards))
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
