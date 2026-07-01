#!/usr/bin/env python3
"""Small BibTeX normalization helper for smoke checks."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def normalize_bibtex(text: str) -> str:
    entries = [entry.strip() for entry in re.split(r"\n(?=@)", text) if entry.strip()]
    entries.sort(key=lambda item: item.split("{", 1)[1].split(",", 1)[0].lower() if "{" in item else item.lower())
    return "\n\n".join(entries) + ("\n" if entries else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(normalize_bibtex(args.input.read_text(encoding="utf-8")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
