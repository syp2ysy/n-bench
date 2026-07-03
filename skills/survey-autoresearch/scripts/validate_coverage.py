#!/usr/bin/env python3
"""Validate discovery sufficiency and retained literature coverage."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


TARGETS = {
    "short": {"raw_candidates": 50, "verified": 20, "a": 3, "b": 8, "related_surveys": 2, "search_routes": 4},
    "full": {"raw_candidates": 200, "verified": 150, "a": 25, "b": 70, "related_surveys": 6, "search_routes": 8},
    "csur": {"raw_candidates": 400, "verified": 200, "a": 40, "b": 100, "related_surveys": 10, "search_routes": 12},
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_json(path: Path) -> dict:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def is_verified(paper: dict) -> bool:
    return paper.get("verified") is True or str(paper.get("verification_status", "")).lower() == "verified"


def _role_text(item: dict) -> str:
    return str(item.get("survey_role") or item.get("role") or item.get("type") or "").lower()


def _title_text(item: dict) -> str:
    return str(item.get("title") or "").lower()


def _is_related_survey(item: dict) -> bool:
    role = _role_text(item)
    title = _title_text(item)
    return role == "survey" or "survey" in title or "review" in title


def _candidate_ids(raw_candidates: list[dict]) -> set[str]:
    ids = set()
    for candidate in raw_candidates:
        if candidate.get("candidate_id"):
            ids.add(str(candidate["candidate_id"]))
        if candidate.get("paper_id"):
            ids.add(str(candidate["paper_id"]))
    return ids


def _citation_depth_counts(citation_plan: list[dict]) -> Counter:
    return Counter(str(item.get("depth") or item.get("level") or "").upper() for item in citation_plan)


def validate_coverage(
    raw_candidates: list[dict],
    search_routes: list[dict],
    lqs_scores: list[dict],
    corpus_expansion: dict,
    papers: list[dict],
    citation_plan: list[dict],
    target: str = "full",
) -> dict:
    thresholds = TARGETS[target]
    missing: list[str] = []
    discovery_missing: list[str] = []
    retained_missing: list[str] = []

    raw_count = len(raw_candidates)
    route_count = len(search_routes)
    lqs_count = len(lqs_scores)
    verified = sum(1 for paper in papers if is_verified(paper))
    depth_counts = _citation_depth_counts(citation_plan)
    related_surveys = max(
        sum(1 for item in raw_candidates if _is_related_survey(item)),
        sum(1 for paper in papers if _is_related_survey(paper)),
    )

    if raw_count < thresholds["raw_candidates"]:
        discovery_missing.append("raw_candidates")
    if route_count < thresholds["search_routes"]:
        discovery_missing.append("search_routes")
    if raw_count >= thresholds["raw_candidates"] and lqs_count < thresholds["raw_candidates"]:
        discovery_missing.append("lqs_scores")
    if related_surveys < thresholds["related_surveys"]:
        discovery_missing.append("related_surveys")

    expansion_required = corpus_expansion.get("required") is True
    expansion_status = str(corpus_expansion.get("status") or "not_required")
    visible_external_count = int(corpus_expansion.get("visible_external_count") or 0)
    retained_candidate_count = int(corpus_expansion.get("retained_candidate_count") or raw_count or 0)
    if expansion_required and expansion_status != "complete":
        discovery_missing.append("corpus_expansion_incomplete")
    if (
        not expansion_required
        and visible_external_count
        and retained_candidate_count
        and visible_external_count > retained_candidate_count * 1.5
    ):
        discovery_missing.append("corpus_expansion_required")

    if verified < thresholds["verified"]:
        retained_missing.append("verified_refs")
    if depth_counts["A"] < thresholds["a"]:
        retained_missing.append("a_level_refs")
    if depth_counts["B"] < thresholds["b"]:
        retained_missing.append("b_level_refs")

    candidate_ids = _candidate_ids(raw_candidates)
    unlinked_papers = []
    for paper in papers:
        source_candidate_id = str(paper.get("source_candidate_id") or "")
        if not source_candidate_id or source_candidate_id not in candidate_ids:
            unlinked_papers.append(str(paper.get("paper_id") or paper.get("title") or "<unknown>"))
    if papers and unlinked_papers:
        retained_missing.append("paper_candidate_linkage")

    family_counts = Counter(
        str(p.get("family") or p.get("topic_axis") or p.get("survey_role") or "unassigned")
        for p in papers
    )
    if target in {"full", "csur"} and papers and family_counts.get("unassigned", 0) == len(papers):
        retained_missing.append("all_coverage_unassigned")

    scenario_counts = Counter(
        str(p.get("scenario") or p.get("domain_context") or p.get("capability") or "unassigned")
        for p in papers
        if p.get("scenario") or p.get("domain_context") or p.get("capability")
    )
    benchmark_refs = sum(
        1 for paper in papers
        if _role_text(paper) == "benchmark" or "benchmark" in _title_text(paper)
    )

    missing.extend(discovery_missing)
    missing.extend(retained_missing)
    discovery_valid = not discovery_missing
    retained_valid = not retained_missing
    return {
        "valid": discovery_valid and retained_valid,
        "discovery_sufficient": discovery_valid,
        "coverage_expanded": retained_valid,
        "missing": missing,
        "discovery_missing": discovery_missing,
        "retained_missing": retained_missing,
        "thresholds": thresholds,
        "raw_candidates": raw_count,
        "search_routes": route_count,
        "lqs_scores": lqs_count,
        "verified_refs": verified,
        "a_refs": depth_counts["A"],
        "b_refs": depth_counts["B"],
        "c_refs": depth_counts["C"],
        "related_surveys": related_surveys,
        "benchmark_refs": benchmark_refs,
        "families": dict(family_counts),
        "scenarios": dict(scenario_counts),
        "corpus_expansion_required": expansion_required,
        "corpus_expansion_status": expansion_status,
        "unlinked_papers": unlinked_papers[:50],
    }


def render_markdown(status: dict) -> str:
    rows = [
        ("raw_candidates", status.get("raw_candidates", 0)),
        ("search_routes", status.get("search_routes", 0)),
        ("verified_refs", status.get("verified_refs", 0)),
        ("a_refs", status.get("a_refs", 0)),
        ("b_refs", status.get("b_refs", 0)),
        ("related_surveys", status.get("related_surveys", 0)),
        ("benchmark_refs", status.get("benchmark_refs", 0)),
        ("corpus_expansion_status", status.get("corpus_expansion_status", "")),
    ]
    lines = ["# Coverage Matrix", "", "| Metric | Value |", "| --- | --- |"]
    lines.extend(f"| {key} | {value} |" for key, value in rows)
    lines.append("")
    lines.append(f"Discovery sufficient: {status.get('discovery_sufficient')}")
    lines.append(f"Coverage expanded: {status.get('coverage_expanded')}")
    if status.get("missing"):
        lines.append("")
        lines.append("Missing: " + ", ".join(status["missing"]))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-candidates", required=True, type=Path)
    parser.add_argument("--search-routes", required=True, type=Path)
    parser.add_argument("--lqs-scores", required=True, type=Path)
    parser.add_argument("--corpus-expansion", required=True, type=Path)
    parser.add_argument("--papers", required=True, type=Path)
    parser.add_argument("--citation-plan", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    status = validate_coverage(
        read_jsonl(args.raw_candidates),
        read_jsonl(args.search_routes),
        read_jsonl(args.lqs_scores),
        read_json(args.corpus_expansion),
        read_jsonl(args.papers),
        read_jsonl(args.citation_plan),
        args.target,
    )
    if args.output:
        args.output.write_text(render_markdown(status), encoding="utf-8")
    print(json.dumps(status, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if status["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
