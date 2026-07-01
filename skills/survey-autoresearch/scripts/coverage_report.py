#!/usr/bin/env python3
"""Build taxonomy coverage reports from citation plans."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_coverage(citation_plan: list[dict], min_ab_refs: int = 2) -> dict:
    cells: dict[str, dict] = {}
    for item in citation_plan:
        cell = item.get("taxonomy_cell") or "unassigned"
        depth = (item.get("depth") or "").upper()
        entry = cells.setdefault(
            cell,
            {"total_refs": 0, "ab_refs": 0, "paper_ids": [], "passes_min_ab_refs": False},
        )
        entry["total_refs"] += 1
        if item.get("paper_id"):
            entry["paper_ids"].append(item["paper_id"])
        if depth in {"A", "B"}:
            entry["ab_refs"] += 1

    failing = []
    for cell, entry in cells.items():
        entry["paper_ids"] = sorted(set(entry["paper_ids"]))
        entry["passes_min_ab_refs"] = entry["ab_refs"] >= min_ab_refs
        if not entry["passes_min_ab_refs"]:
            failing.append(cell)

    return {
        "cells": cells,
        "summary": {
            "total_cells": len(cells),
            "passing_cells": len(cells) - len(failing),
            "failing_cells": len(failing),
            "min_ab_refs": min_ab_refs,
        },
        "failing_cells": sorted(failing),
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--citation-plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-ab-refs", type=int, default=2)
    args = parser.parse_args()
    report = build_coverage(read_jsonl(args.citation_plan), min_ab_refs=args.min_ab_refs)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
