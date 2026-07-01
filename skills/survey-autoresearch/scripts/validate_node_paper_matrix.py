#!/usr/bin/env python3
"""Validate system-node by paper matrix outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_COLUMNS = [
    "system node",
    "what it does",
    "representative papers",
    "mechanism pattern",
    "evidence",
    "failure mode",
    "evaluation signal",
]


def _table(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    header: list[str] = []
    rows: list[list[str]] = []
    for line in lines:
        cells = [cell.strip().lower() for cell in line.strip("|").split("|")]
        if not header and "---" not in line:
            header = cells
            continue
        if header and "---" not in line:
            rows.append(cells)
    return header, rows


def validate_node_paper_matrix(text: str) -> dict:
    header, rows = _table(text)
    missing = [col for col in REQUIRED_COLUMNS if col not in header]
    incomplete_rows = [
        idx for idx, row in enumerate(rows, start=1)
        if len(row) < len(header) or not all(cell.strip() for cell in row[: min(len(row), len(header))])
    ]
    failed = []
    if missing:
        failed.append("missing_columns")
    if len(rows) < 2:
        failed.append("insufficient_nodes")
    if incomplete_rows:
        failed.append("incomplete_rows")
    return {
        "valid": not failed,
        "required": True,
        "failed_checks": failed,
        "missing_columns": missing,
        "nodes": len(rows),
        "incomplete_rows": incomplete_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-paper-matrix", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_node_paper_matrix(args.node_paper_matrix.read_text(encoding="utf-8"))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
