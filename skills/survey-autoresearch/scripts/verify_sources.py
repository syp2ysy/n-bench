#!/usr/bin/env python3
"""Validate source identity for survey-autoresearch papers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def depth_map(citation_plan: list[dict]) -> dict[str, str]:
    result = {}
    for item in citation_plan:
        paper_id = item.get("paper_id")
        if paper_id:
            result[str(paper_id)] = str(item.get("depth") or item.get("level") or "").upper()
    return result


def is_verified(paper: dict) -> bool:
    if paper.get("verified") is True:
        return True
    if str(paper.get("verification_status", "")).lower() == "verified":
        return True
    return False


def has_identity(paper: dict) -> bool:
    required = ["paper_id", "title", "authors", "year"]
    if any(not paper.get(field) for field in required):
        return False
    source_fields = ["doi", "arxiv_id", "openreview_url", "dblp_url", "official_url", "url"]
    return any(paper.get(field) for field in source_fields) or bool(paper.get("verified_sources"))


def validate_sources(papers: list[dict], citation_plan: list[dict], target: str = "full") -> dict:
    if target == "short":
        required_c_rate = 0.0
    else:
        required_c_rate = 0.9
    depth_by_id = depth_map(citation_plan)
    papers_by_id = {str(p.get("paper_id")): p for p in papers if p.get("paper_id")}
    ab_ids = [pid for pid, depth in depth_by_id.items() if depth in {"A", "B"}]
    c_ids = [pid for pid, depth in depth_by_id.items() if depth == "C"]
    errors: list[str] = []
    missing_identity = []
    unverified_ab = []
    for pid in ab_ids:
        paper = papers_by_id.get(pid)
        if not paper or not has_identity(paper):
            missing_identity.append(pid)
        if not paper or not is_verified(paper):
            unverified_ab.append(pid)
    c_verified = sum(1 for pid in c_ids if is_verified(papers_by_id.get(pid, {})))
    c_rate = c_verified / len(c_ids) if c_ids else 1.0
    if missing_identity:
        errors.append("missing_identity_for_a_b")
    if unverified_ab:
        errors.append("unverified_a_b")
    if c_rate < required_c_rate:
        errors.append("c_verification_rate_below_target")
    return {
        "valid": not errors,
        "errors": errors,
        "papers": len(papers),
        "a_b_papers": len(ab_ids),
        "c_papers": len(c_ids),
        "missing_identity": missing_identity,
        "unverified_a_b": unverified_ab,
        "c_verification_rate": round(c_rate, 3),
        "required_c_verification_rate": required_c_rate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", required=True, type=Path)
    parser.add_argument("--citation-plan", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    result = validate_sources(read_jsonl(args.papers), read_jsonl(args.citation_plan), args.target)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
