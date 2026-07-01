#!/usr/bin/env python3
"""Validate mined CSUR rhetoric patterns before CSUR synthesis."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_KEYS = [
    "abstract_moves",
    "introduction_moves",
    "section_patterns",
    "table_functions",
    "paragraph_patterns",
    "forbidden_surface_forms",
]

SECTION_PATTERN_HINTS = ["opening", "body", "closing", "structure"]


def validate_csur_style_patterns(text: str) -> dict:
    lower = text.lower()
    missing = [key for key in REQUIRED_KEYS if key not in lower]
    missing_hints = [hint for hint in SECTION_PATTERN_HINTS if hint not in lower]
    move_lines = [
        line for line in text.splitlines()
        if re.match(r"\s*[-*]\s+\S+", line) or re.match(r"\s{2,}[a-zA-Z0-9_-]+:", line)
    ]
    too_thin = len(move_lines) < 8
    valid = not missing and not missing_hints and not too_thin
    return {
        "valid": valid,
        "missing": missing,
        "missing_section_pattern_hints": missing_hints,
        "move_lines": len(move_lines),
        "too_thin": too_thin,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patterns", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_csur_style_patterns(args.patterns.read_text(encoding="utf-8"))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
