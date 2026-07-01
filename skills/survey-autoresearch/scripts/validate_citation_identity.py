#!/usr/bin/env python3
"""Validate citation identity verification for retained papers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


IDENTITY_FIELDS = ["paper_id", "title", "authors", "year"]


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _is_verified(paper: dict) -> bool:
    status = str(paper.get("verification_status") or "").lower()
    if status == "verified":
        return True
    if paper.get("verified") is True and (
        paper.get("doi")
        or paper.get("arxiv_id")
        or paper.get("openreview_url")
        or paper.get("dblp_url")
        or paper.get("semantic_scholar_id")
        or paper.get("verified_sources")
    ):
        return True
    return False


def validate_citation_identity(papers: list[dict], citation_plan: list[dict] | None = None, target: str = "full") -> dict:
    errors: list[str] = []
    paper_by_id = {paper.get("paper_id"): paper for paper in papers if paper.get("paper_id")}
    depth_by_id = {
        item.get("paper_id"): str(item.get("depth") or "").upper()
        for item in (citation_plan or [])
        if item.get("paper_id")
    }
    unverified_ab: list[str] = []
    missing_identity: list[str] = []
    for paper_id, paper in paper_by_id.items():
        missing = [field for field in IDENTITY_FIELDS if not _nonempty(paper.get(field))]
        if missing:
            missing_identity.append(paper_id)
            errors.append(f"{paper_id}: missing identity fields {','.join(missing)}")
        if depth_by_id.get(paper_id) in {"A", "B"} and not _is_verified(paper):
            unverified_ab.append(paper_id)
            errors.append(f"{paper_id}: unverified A/B paper")
    planned_missing = sorted(set(depth_by_id) - set(paper_by_id))
    for paper_id in planned_missing:
        errors.append(f"{paper_id}: citation_plan references missing paper")
    verified_count = sum(1 for paper in papers if _is_verified(paper))
    verification_rate = verified_count / len(papers) if papers else 0.0
    if target in {"full", "csur"} and verification_rate < 0.80:
        errors.append("verification_rate_below_80_percent")
    c_ids = [paper_id for paper_id, depth in depth_by_id.items() if depth == "C"]
    if c_ids:
        verified_c = sum(1 for paper_id in c_ids if _is_verified(paper_by_id.get(paper_id, {})))
        c_rate = verified_c / len(c_ids)
        if c_rate < 0.90:
            errors.append("c_level_verification_below_90_percent")
    return {
        "valid": bool(papers) and not errors,
        "total_papers": len(papers),
        "verification_rate": verification_rate,
        "unverified_a_b_papers": sorted(unverified_ab),
        "missing_identity": sorted(missing_identity),
        "errors": errors,
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", required=True, type=Path)
    parser.add_argument("--citation-plan", type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_citation_identity(
        read_jsonl(args.papers),
        read_jsonl(args.citation_plan) if args.citation_plan else None,
        target=args.target,
    )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
