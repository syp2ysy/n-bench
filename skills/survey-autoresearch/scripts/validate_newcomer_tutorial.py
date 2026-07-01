#!/usr/bin/env python3
"""Validate newcomer tutorial layer: glossary plus running example."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


GLOSSARY_TERMS = [
    "embodied memory",
    "episodic memory",
    "semantic memory",
    "spatial memory",
    "procedural",
    "semantic map",
    "topological graph",
    "3d scene memory",
    "retrieval memory",
    "vla working memory",
    "stale memory",
    "oracle memory",
    "wrong-memory",
    "memory-causal ablation",
]
RUNNING_STEPS = ["capture", "representation", "storage", "retrieval", "update", "controller", "evaluation"]


def validate_newcomer_tutorial(review_text: str, glossary_text: str, running_example_text: str) -> dict:
    combined_glossary = glossary_text.lower()
    combined_example = running_example_text.lower()
    review_lower = review_text.lower()
    missing_terms = [term for term in GLOSSARY_TERMS if term not in combined_glossary]
    missing_steps = [step for step in RUNNING_STEPS if step not in combined_example]
    has_tutorial_section = bool(re.search(r"^##\s+.*(tutorial|primer|入门|术语)", review_text, flags=re.IGNORECASE | re.MULTILINE))
    has_running_example_in_review = "running example" in review_lower or "贯穿例子" in review_text or "例子" in review_text
    failed = []
    if not has_tutorial_section:
        failed.append("missing_tutorial_section")
    if missing_terms:
        failed.append("missing_glossary_terms")
    if missing_steps:
        failed.append("missing_running_example_steps")
    if not has_running_example_in_review:
        failed.append("running_example_not_absorbed")
    return {
        "valid": not failed,
        "required": True,
        "failed_checks": failed,
        "missing_glossary_terms": missing_terms,
        "missing_running_example_steps": missing_steps,
        "tutorial_section": has_tutorial_section,
        "running_example_in_review": has_running_example_in_review,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--glossary", required=True, type=Path)
    parser.add_argument("--running-example", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_newcomer_tutorial(
        args.review.read_text(encoding="utf-8"),
        args.glossary.read_text(encoding="utf-8") if args.glossary.exists() else "",
        args.running_example.read_text(encoding="utf-8") if args.running_example.exists() else "",
    )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
