#!/usr/bin/env python3
"""Validate claim records against known paper identifiers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TRACE_FIELDS = {
    "what_it_teaches_the_survey",
    "mechanism_or_contribution",
    "method_summary",
    "evidence_spans",
}


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _paper_cards_by_id(paper_cards: list[dict] | None) -> dict[str, dict]:
    return {
        item["paper_id"]: item
        for item in (paper_cards or [])
        if item.get("paper_id")
    }


def validate_claim_records(
    claims: list[dict],
    known_paper_ids: set[str],
    paper_cards: list[dict] | None = None,
) -> dict:
    errors: list[str] = []
    valid_claims = 0
    card_by_id = _paper_cards_by_id(paper_cards)
    require_card_trace = paper_cards is not None
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
            if require_card_trace:
                card = card_by_id.get(paper_id)
                if not card:
                    claim_errors.append(f"missing paper_card for {paper_id}")
                    continue
                declared_fields = (claim.get("paper_card_fields") or {}).get(paper_id, [])
                if declared_fields:
                    missing_fields = [
                        field for field in declared_fields
                        if field not in TRACE_FIELDS or not _nonempty(card.get(field))
                    ]
                    if missing_fields:
                        claim_errors.append(
                            f"paper_card trace fields unavailable for {paper_id}: {','.join(missing_fields)}"
                        )
                elif not any(_nonempty(card.get(field)) for field in TRACE_FIELDS):
                    claim_errors.append(f"paper_card for {paper_id} lacks trace fields")
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
