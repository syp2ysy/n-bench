#!/usr/bin/env python3
"""Validate mined CSUR paragraph-level rhetoric patterns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_PATTERNS = [
    "introduction_paragraph",
    "tutorial_definition_paragraph",
    "taxonomy_opening_paragraph",
    "method_comparison_paragraph",
    "benchmark_paragraph",
    "limitation_paragraph",
    "open_challenge_paragraph",
    "conclusion_agenda_paragraph",
]
REQUIRED_FIELDS = ["when_to_use", "paragraph_moves", "evidence_from_exemplar", "forbidden_shortcut"]


def validate_csur_paragraph_patterns(text: str) -> dict:
    lower = text.lower()
    missing_patterns = [name for name in REQUIRED_PATTERNS if name not in lower]
    missing_fields = [field for field in REQUIRED_FIELDS if field not in lower]
    valid = bool(text.strip()) and not missing_patterns and not missing_fields
    return {
        "valid": valid,
        "missing_patterns": missing_patterns,
        "missing_fields": missing_fields,
        "patterns": len(REQUIRED_PATTERNS) - len(missing_patterns),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patterns", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_csur_paragraph_patterns(args.patterns.read_text(encoding="utf-8"))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
