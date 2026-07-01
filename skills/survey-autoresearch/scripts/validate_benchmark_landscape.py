#!/usr/bin/env python3
"""Validate benchmark landscape tables for tutorial survey outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_COLUMNS = [
    "benchmark",
    "task family",
    "environment",
    "memory pressure",
    "required memory fields",
    "metrics",
    "baselines",
    "memory-specific ablations",
    "confounders",
]
MIN_ROWS = {"full": 10, "csur": 18}


def _table(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    header: list[str] = []
    rows: list[list[str]] = []
    for idx, line in enumerate(lines):
        cells = [cell.strip().lower() for cell in line.strip("|").split("|")]
        if not header and "---" not in line:
            header = cells
            continue
        if header and "---" not in line:
            rows.append(cells)
    return header, rows


def validate_benchmark_landscape(text: str, target: str = "full") -> dict:
    if target not in {"full", "csur"}:
        return {"valid": True, "required": False, "failed_checks": []}
    header, rows = _table(text)
    missing = [col for col in REQUIRED_COLUMNS if col not in header]
    incomplete_rows = [
        idx for idx, row in enumerate(rows, start=1)
        if len(row) < len(header) or not all(cell.strip() for cell in row[: min(len(row), len(header))])
    ]
    failed = []
    if missing:
        failed.append("missing_columns")
    if len(rows) < MIN_ROWS[target]:
        failed.append("insufficient_entries")
    if incomplete_rows:
        failed.append("incomplete_rows")
    return {
        "valid": not failed,
        "required": True,
        "target": target,
        "failed_checks": failed,
        "missing_columns": missing,
        "entries": len(rows),
        "min_entries": MIN_ROWS[target],
        "incomplete_rows": incomplete_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-landscape", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_benchmark_landscape(args.benchmark_landscape.read_text(encoding="utf-8"), args.target)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
