#!/usr/bin/env python3
"""Derive compact paper-fact records from canonical paper cards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _join(value) -> str:
    items = [str(item) for item in _as_list(value) if str(item).strip()]
    return ", ".join(items)


def derive_paper_facts(cards: list[dict]) -> list[dict]:
    facts: list[dict] = []
    for card in cards:
        if not card.get("paper_id"):
            continue
        facts.append(
            {
                "paper_id": card["paper_id"],
                "method_family": card.get("method_family")
                or card.get("system_node")
                or card.get("memory_node")
                or card.get("representation")
                or "",
                "task_family": _join(card.get("evaluation_tasks") or card.get("tasks")),
                "benchmark_or_dataset": _join(card.get("datasets_or_envs") or card.get("benchmarks")),
                "metrics": _as_list(card.get("metrics")),
                "mechanism_or_contribution": card.get("mechanism_or_contribution") or card.get("method_summary") or "",
                "ablations": _as_list(card.get("ablations")),
                "limitations": card.get("limitations") if isinstance(card.get("limitations"), str) else _join(card.get("limitations")),
            }
        )
    return facts


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-cards", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    facts = derive_paper_facts(read_jsonl(args.paper_cards))
    args.output.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in facts), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
