#!/usr/bin/env python3
"""Heuristic review scorecard for tutorial-survey completeness."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _score(text: str, terms: list[str], base: int = 0) -> int:
    lower = text.lower()
    hits = sum(1 for term in terms if term.lower() in lower)
    return min(10, base + hits)


def score_review(review_text: str, target: str = "full") -> dict:
    length_bonus = 2 if len(review_text) >= (35_000 if target == "full" else 60_000) else 0
    scores = {
        "newcomer_score": _score(
            review_text,
            ["tutorial primer", "glossary", "running example", "memory record", "oracle memory", "wrong-memory"],
            base=length_bonus,
        ),
        "method_depth_score": _score(
            review_text,
            ["worked example", "write policy", "read policy", "update policy", "controller interface", "failure mode", "design lesson"],
            base=length_bonus,
        ),
        "benchmark_utility_score": _score(
            review_text,
            ["memory pressure", "metrics", "baselines", "memory-specific ablations", "confounders", "oracle-memory"],
            base=length_bonus,
        ),
        "csur_style_score": _score(
            review_text,
            ["method taxonomy", "benchmark landscape", "evaluation protocol", "open problems", "related surveys", "critical analysis"],
            base=length_bonus,
        ),
    }
    passed = all(value >= 8 for value in scores.values())
    return {
        "passed": passed,
        "target": target,
        "scores": scores,
        "chars": len(review_text),
        "worked_examples": len(re.findall(r"worked example", review_text, flags=re.IGNORECASE)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = score_review(args.review.read_text(encoding="utf-8"), args.target)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
