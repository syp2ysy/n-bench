#!/usr/bin/env python3
"""Validate that review-body tables are introduced and interpreted in prose."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


INTERPRETATION_TERMS = [
    "this table",
    "the table",
    "shows",
    "indicates",
    "implies",
    "therefore",
    "consequently",
    "comparison",
    "trade-off",
    "take-away",
    "implication",
    "matrix",
    "trace",
    "terms",
    "表",
    "显示",
    "说明",
    "意味着",
    "因此",
    "由此",
    "比较",
    "权衡",
    "启示",
    "矩阵",
    "追踪",
    "术语",
]


def _line_offsets(text: str) -> list[int]:
    offsets = []
    total = 0
    for line in text.splitlines(True):
        offsets.append(total)
        total += len(line)
    return offsets


def _table_blocks(text: str) -> list[tuple[int, int]]:
    lines = text.splitlines(True)
    offsets = _line_offsets(text)
    blocks: list[tuple[int, int]] = []
    idx = 0
    while idx < len(lines):
        if lines[idx].lstrip().startswith("|"):
            start_idx = idx
            while idx < len(lines) and lines[idx].lstrip().startswith("|"):
                idx += 1
            block = "".join(lines[start_idx:idx])
            if "| ---" in block or "|---" in block:
                start = offsets[start_idx]
                end = offsets[idx - 1] + len(lines[idx - 1])
                blocks.append((start, end))
        else:
            idx += 1
    return blocks


def _has_interpretation(text: str) -> bool:
    lower = text.lower()
    return any(term in lower or term in text for term in INTERPRETATION_TERMS)


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[#>*`|_\-]+", " ", text)).strip()


def validate_table_interpretation(text: str, target: str = "full") -> dict:
    if target not in {"full", "csur"}:
        return {"valid": True, "required": False, "failed_checks": []}

    blocks = _table_blocks(text)
    errors: list[str] = []
    for idx, (start, end) in enumerate(blocks, start=1):
        before_start = max(0, start - 650)
        before = text[before_start:start]
        after_end = min(len(text), end + 850)
        after = text[end:after_end]
        next_h2 = re.search(r"^##\s+", after, flags=re.MULTILINE)
        if next_h2:
            after = after[: next_h2.start()]
        if len(_plain(before)) < 80:
            errors.append(f"table_{idx} missing before-table introduction")
        if len(_plain(after)) < 90 or not _has_interpretation(after):
            errors.append(f"table_{idx} missing after-table interpretation")

    failed = []
    if errors:
        failed.append("table_interpretation")
    return {
        "valid": not failed,
        "required": True,
        "target": target,
        "failed_checks": failed,
        "tables": len(blocks),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_table_interpretation(args.review.read_text(encoding="utf-8"), args.target)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
