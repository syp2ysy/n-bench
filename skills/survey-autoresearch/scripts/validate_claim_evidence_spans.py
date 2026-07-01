#!/usr/bin/env python3
"""Validate claim-to-evidence-span alignment and strength calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


STRENGTH_RANK = {
    "hypothesizes": 0,
    "may indicate": 1,
    "suggests": 2,
    "shows": 3,
    "demonstrates": 4,
}


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _rank(value: str) -> int:
    return STRENGTH_RANK.get(str(value or "").strip().lower(), -1)


def _known_papers(cards: list[dict]) -> set[str]:
    return {card["paper_id"] for card in cards or [] if card.get("paper_id")}


def validate_claim_evidence_spans(claims: list[dict], mechanism_cards: list[dict] | None = None) -> dict:
    errors: list[str] = []
    known = _known_papers(mechanism_cards or [])
    for idx, claim in enumerate(claims, start=1):
        claim_id = claim.get("claim_id") or f"claim_{idx}"
        claim_errors: list[str] = []
        for field in ["claim", "claim_type", "paper_ids", "strength", "evidence_spans"]:
            if not _nonempty(claim.get(field)):
                claim_errors.append(f"missing {field}")
        paper_ids = set(_as_list(claim.get("paper_ids")))
        if known:
            unknown = sorted(paper_ids - known)
            if unknown:
                claim_errors.append("unknown paper_ids " + ",".join(unknown))
        claim_rank = _rank(claim.get("strength"))
        if claim_rank < 0:
            claim_errors.append("unknown claim strength")
        span_ranks: list[int] = []
        span_papers: set[str] = set()
        for span_idx, span in enumerate(_as_list(claim.get("evidence_spans")), start=1):
            if not isinstance(span, dict):
                claim_errors.append(f"evidence_spans[{span_idx}] must be object")
                continue
            missing = [
                field for field in ["paper_id", "section_or_page", "evidence_summary", "supports", "strength"]
                if not _nonempty(span.get(field))
            ]
            if missing:
                claim_errors.append(f"evidence_spans[{span_idx}] missing " + ",".join(missing))
            span_papers.add(span.get("paper_id"))
            span_rank = _rank(span.get("strength"))
            if span_rank < 0:
                claim_errors.append(f"evidence_spans[{span_idx}] unknown strength")
            else:
                span_ranks.append(span_rank)
        if paper_ids and not paper_ids.issubset(span_papers):
            claim_errors.append("paper_ids not covered by evidence_spans")
        if claim_rank >= 0 and span_ranks and claim_rank > max(span_ranks):
            claim_errors.append("claim strength exceeds evidence strength")
        if claim_rank == STRENGTH_RANK["demonstrates"] and not any(
            span.get("supports") == "direct" and _rank(span.get("strength")) >= STRENGTH_RANK["demonstrates"]
            for span in _as_list(claim.get("evidence_spans"))
            if isinstance(span, dict)
        ):
            claim_errors.append("demonstrates requires direct demonstrates evidence")
        if claim_errors:
            errors.append(f"{claim_id}: " + "; ".join(claim_errors))
    return {
        "valid": bool(claims) and not errors,
        "total_claims": len(claims),
        "errors": errors,
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", required=True, type=Path)
    parser.add_argument("--paper-mechanism-cards", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_claim_evidence_spans(
        read_jsonl(args.claims),
        read_jsonl(args.paper_mechanism_cards) if args.paper_mechanism_cards else None,
    )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
