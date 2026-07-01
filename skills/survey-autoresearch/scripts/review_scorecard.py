#!/usr/bin/env python3
"""Heuristic review scorecard for tutorial-survey completeness."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from .validate_publication_prose import validate_publication_prose
except ImportError:  # pragma: no cover - standalone script mode
    from validate_publication_prose import validate_publication_prose


def _score(text: str, terms: list[str], base: int = 0) -> int:
    lower = text.lower()
    hits = sum(1 for term in terms if term.lower() in lower)
    return min(10, base + hits)


def score_review(review_text: str, target: str = "full") -> dict:
    length_bonus = 2 if len(review_text) >= (35_000 if target == "full" else 60_000) else 0
    publication_status = validate_publication_prose(review_text, target=target)
    comparison_markers = len(
        re.findall(
            r"compared|whereas|while|however|trade-off|therefore|consequently|相比|不同于|然而|权衡|因此|由此",
            review_text,
            flags=re.IGNORECASE,
        )
    )
    case_studies = len(
        re.findall(
            r"^#{3,4}\s+.*(?:case study|case box|worked example|案例|个案|机制解剖)",
            review_text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
    )
    interpreted_tables = review_text.lower().count("this table") + review_text.count("表") + review_text.count("这个表")
    scores = {
        "newcomer_score": _score(
            review_text,
            ["tutorial primer", "glossary", "running example", "memory record", "oracle memory", "wrong-memory"],
            base=length_bonus,
        ),
        "method_depth_score": _score(
            review_text,
            ["case study", "mechanism", "controller interface", "failure mode", "limitation", "benchmark evidence", "design implication"],
            base=length_bonus + min(2, case_studies // 2),
        ),
        "benchmark_utility_score": _score(
            review_text,
            ["memory pressure", "metrics", "baselines", "memory-specific ablations", "confounders", "oracle-memory"],
            base=length_bonus + min(2, interpreted_tables // 3),
        ),
        "csur_style_score": _score(
            review_text,
            ["method taxonomy", "benchmark landscape", "evaluation protocol", "open problems", "related surveys", "critical analysis"],
            base=length_bonus,
        ),
        "publication_readiness_score": 10 if publication_status["valid"] else max(
            0,
            6 - len(publication_status.get("failed_checks", [])) - min(3, len(publication_status.get("raw_artifact_phrases", []))),
        ),
        "comparative_synthesis_score": min(10, length_bonus + comparison_markers // 3),
    }
    passed = publication_status["valid"] and all(value >= 8 for value in scores.values())
    return {
        "passed": passed,
        "target": target,
        "scores": scores,
        "chars": len(review_text),
        "case_studies": case_studies,
        "publication_prose": publication_status,
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
