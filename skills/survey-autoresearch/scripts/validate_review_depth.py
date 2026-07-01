#!/usr/bin/env python3
"""Validate final-review tutorial depth for full and CSUR survey targets."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


THRESHOLDS = {
    "full": {
        "min_chars": 35_000,
        "min_tables": 8,
        "min_h3": 10,
        "min_worked_examples": 12,
        "min_benchmark_entries": 10,
        "min_method_families": 8,
    },
    "csur": {
        "min_chars": 60_000,
        "min_tables": 12,
        "min_h3": 18,
        "min_worked_examples": 25,
        "min_benchmark_entries": 18,
        "min_method_families": 10,
    },
}


def _table_rows_after_heading(text: str, heading_pattern: str) -> int:
    match = re.search(heading_pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return 0
    tail = text[match.end():]
    next_heading = re.search(r"^##\s+", tail, flags=re.MULTILINE)
    section = tail[: next_heading.start()] if next_heading else tail
    rows = [
        line for line in section.splitlines()
        if line.strip().startswith("|") and "---" not in line and line.count("|") >= 3
    ]
    return max(0, len(rows) - 1)


def validate_review_depth(review_text: str, target: str = "full") -> dict:
    if target not in {"full", "csur"}:
        return {"valid": True, "required": False, "failed_checks": []}

    cfg = THRESHOLDS[target]
    h3_count = len(re.findall(r"^###\s+", review_text, flags=re.MULTILINE))
    table_count = review_text.count("| ---")
    worked_examples = len(re.findall(r"^#{3,4}\s+.*worked example", review_text, flags=re.IGNORECASE | re.MULTILINE))
    benchmark_entries = _table_rows_after_heading(review_text, r"^##\s+.*benchmark")
    method_families = _table_rows_after_heading(review_text, r"^##\s+.*method taxonomy|^##\s+.*方法")
    has_tutorial = bool(re.search(r"tutorial primer|入门|术语|glossary", review_text, flags=re.IGNORECASE))
    has_running_example = bool(re.search(r"running example|贯穿例子|例子", review_text, flags=re.IGNORECASE))
    has_system_model = bool(re.search(r"system model|系统模型|system nodes?|系统节点", review_text, flags=re.IGNORECASE))
    has_failure_table = bool(re.search(r"failure mode|失败模式|失效", review_text, flags=re.IGNORECASE)) and table_count > 0

    checks = {
        "length": len(review_text) >= cfg["min_chars"],
        "tables": table_count >= cfg["min_tables"],
        "h3_subsections": h3_count >= cfg["min_h3"],
        "worked_examples": worked_examples >= cfg["min_worked_examples"],
        "benchmark_entries": benchmark_entries >= cfg["min_benchmark_entries"],
        "method_families": method_families >= cfg["min_method_families"],
        "tutorial_primer": has_tutorial,
        "running_example": has_running_example,
        "system_model": has_system_model,
        "failure_modes": has_failure_table,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "valid": not failed,
        "required": True,
        "target": target,
        "failed_checks": failed,
        "checks": checks,
        "chars": len(review_text),
        "min_chars": cfg["min_chars"],
        "table_count": table_count,
        "h3_count": h3_count,
        "worked_examples": worked_examples,
        "benchmark_entries": benchmark_entries,
        "method_families": method_families,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_review_depth(args.review.read_text(encoding="utf-8"), target=args.target)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
