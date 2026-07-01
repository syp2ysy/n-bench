#!/usr/bin/env python3
"""Summarize claim strengths as an evidence ladder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


STRENGTHS = ["hypothesizes", "may indicate", "suggests", "shows", "demonstrates"]


def derive_evidence_ladder(claims: list[dict]) -> dict:
    counts = {strength: 0 for strength in STRENGTHS}
    for claim in claims:
        strength = str(claim.get("strength") or "").lower()
        if strength in counts:
            counts[strength] += 1
    strongest = None
    for strength in reversed(STRENGTHS):
        if counts[strength]:
            strongest = strength
            break
    return {
        "counts": counts,
        "strongest": strongest,
        "total_claims": sum(counts.values()),
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def render_markdown(ladder: dict) -> str:
    rows = "\n".join(f"| {strength} | {count} |" for strength, count in ladder["counts"].items())
    return (
        "# Evidence Ladder\n\n"
        "| Strength | Claim count |\n"
        "| --- | ---: |\n"
        f"{rows}\n\n"
        f"Strongest claim strength present: {ladder.get('strongest') or 'none'}.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()
    ladder = derive_evidence_ladder(read_jsonl(args.claims))
    text = render_markdown(ladder) if args.markdown else json.dumps(ladder, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
