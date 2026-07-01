#!/usr/bin/env python3
"""Validate claim records against known paper identifiers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_claim_records(claims: list[dict], known_paper_ids: set[str]) -> dict:
    errors: list[str] = []
    valid_claims = 0
    for idx, claim in enumerate(claims, start=1):
        claim_id = claim.get("claim_id") or f"claim_{idx}"
        claim_errors = []
        paper_ids = claim.get("paper_ids") or []
        if not claim.get("claim"):
            claim_errors.append("missing claim text")
        if not paper_ids:
            claim_errors.append("missing paper_ids")
        if not claim.get("evidence"):
            claim_errors.append("missing evidence")
        for paper_id in paper_ids:
            if paper_id not in known_paper_ids:
                claim_errors.append(f"unknown paper_id {paper_id}")
        if claim_errors:
            errors.append(f"{claim_id}: " + "; ".join(claim_errors))
        else:
            valid_claims += 1
    return {
        "valid": not errors,
        "total_claims": len(claims),
        "valid_claims": valid_claims,
        "invalid_claims": len(claims) - valid_claims,
        "errors": errors,
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", required=True, type=Path)
    parser.add_argument("--papers", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    papers = read_jsonl(args.papers)
    known_ids = {item["paper_id"] for item in papers if item.get("paper_id")}
    result = validate_claim_records(read_jsonl(args.claims), known_ids)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
