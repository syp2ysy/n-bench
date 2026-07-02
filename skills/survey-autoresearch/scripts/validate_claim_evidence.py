#!/usr/bin/env python3
"""Validate claim-to-evidence traceability."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


STRENGTH = {"may indicate": 1, "suggests": 2, "shows": 3, "demonstrates": 4}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_claim_evidence(claims: list[dict], mechanism_cards: list[dict], section_plans: list[dict] | None = None) -> dict:
    card_ids = {str(card.get("paper_id")) for card in mechanism_cards if card.get("paper_id")}
    planned_claims = set()
    for plan in section_plans or []:
        for claim_id in plan.get("must_include_evidence_spans") or []:
            planned_claims.add(str(claim_id))
    errors: list[str] = []
    invalid_claims: dict[str, list[str]] = {}
    for claim in claims:
        claim_id = str(claim.get("claim_id") or claim.get("id") or "<missing>")
        claim_errors = []
        if not claim.get("claim"):
            claim_errors.append("missing_claim_text")
        claim_strength = str(claim.get("strength") or "").lower()
        if claim_strength not in STRENGTH:
            claim_errors.append("invalid_claim_strength")
        if section_plans is not None and STRENGTH.get(claim_strength, 0) >= STRENGTH["shows"] and claim_id not in planned_claims:
            claim_errors.append("strong_claim_missing_section_plan")
        spans = claim.get("evidence_spans") or []
        if not isinstance(spans, list) or not spans:
            claim_errors.append("missing_evidence_spans")
        for span in spans if isinstance(spans, list) else []:
            paper_id = str(span.get("paper_id") or "")
            span_strength = str(span.get("strength") or "").lower()
            if paper_id not in card_ids:
                claim_errors.append(f"unknown_paper:{paper_id}")
            if not span.get("section_or_page") or not span.get("evidence_summary"):
                claim_errors.append(f"incomplete_span:{paper_id}")
            if span_strength not in STRENGTH:
                claim_errors.append(f"invalid_span_strength:{paper_id}")
            elif claim_strength in STRENGTH and STRENGTH[claim_strength] > STRENGTH[span_strength]:
                claim_errors.append(f"claim_strength_exceeds_evidence:{paper_id}")
        if claim_errors:
            invalid_claims[claim_id] = sorted(set(claim_errors))
    if invalid_claims:
        errors.append("invalid_claim_evidence")
    return {
        "valid": not errors,
        "errors": errors,
        "total_claims": len(claims),
        "invalid_claims": invalid_claims,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", required=True, type=Path)
    parser.add_argument("--paper-mechanism-cards", required=True, type=Path)
    parser.add_argument("--section-evidence-plans", type=Path)
    args = parser.parse_args()
    result = validate_claim_evidence(
        read_jsonl(args.claims),
        read_jsonl(args.paper_mechanism_cards),
        read_jsonl(args.section_evidence_plans) if args.section_evidence_plans else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
