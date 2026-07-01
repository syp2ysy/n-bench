#!/usr/bin/env python3
"""Validate paper-level worked examples for tutorial survey synthesis."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


THRESHOLDS = {"full": 12, "csur": 25}
REQUIRED_TERMS = [
    "problem",
    "memory record",
    "write policy",
    "read policy",
    "update",
    "controller interface",
    "benchmark",
    "ablation",
    "failure mode",
    "design lesson",
]
GENERIC_ONLY = [
    "task success or answer accuracy",
    "memory ablation effect",
    "may not isolate memory",
]


def _split_examples(text: str) -> list[str]:
    matches = list(re.finditer(r"^#{3,4}\s+.*worked example.*$", text, flags=re.IGNORECASE | re.MULTILINE))
    blocks: list[str] = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        blocks.append(text[match.start():end])
    return blocks


def _known_ids(paper_cards: list[dict] | None) -> set[str]:
    return {str(item["paper_id"]) for item in paper_cards or [] if item.get("paper_id")}


def validate_worked_examples(text: str, paper_cards: list[dict] | None = None, target: str = "full") -> dict:
    if target not in {"full", "csur"}:
        return {"valid": True, "required": False, "failed_checks": []}
    examples = _split_examples(text)
    known_ids = _known_ids(paper_cards)
    errors: list[str] = []
    for idx, block in enumerate(examples, start=1):
        lower = block.lower()
        missing = [term for term in REQUIRED_TERMS if term not in lower]
        if missing:
            errors.append(f"example {idx}: incomplete_example missing {','.join(missing)}")
        if known_ids and not any(paper_id in block for paper_id in known_ids):
            errors.append(f"example {idx}: missing known paper_id")
        if any(phrase in lower for phrase in GENERIC_ONLY) and len(block) < 800:
            errors.append(f"example {idx}: generic template evidence")
    failed = []
    if len(examples) < THRESHOLDS[target]:
        failed.append("insufficient_examples")
    if errors:
        failed.append("invalid_examples")
    return {
        "valid": not failed,
        "required": True,
        "target": target,
        "failed_checks": failed,
        "examples": len(examples),
        "min_examples": THRESHOLDS[target],
        "errors": errors,
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worked-examples", required=True, type=Path)
    parser.add_argument("--paper-cards", type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cards = read_jsonl(args.paper_cards) if args.paper_cards else None
    result = validate_worked_examples(args.worked_examples.read_text(encoding="utf-8"), cards, args.target)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
