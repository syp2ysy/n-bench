#!/usr/bin/env python3
"""Build and validate coverage summaries for survey-autoresearch."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


TARGETS = {
    "short": {"verified": 0, "a": 0, "b": 0, "related_surveys": 0},
    "full": {"verified": 150, "a": 25, "b": 70, "related_surveys": 6},
    "csur": {"verified": 200, "a": 40, "b": 100, "related_surveys": 10},
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def is_verified(paper: dict) -> bool:
    return paper.get("verified") is True or str(paper.get("verification_status", "")).lower() == "verified"


def build_coverage(papers: list[dict], citation_plan: list[dict], target: str = "full") -> dict:
    thresholds = TARGETS[target]
    depth_counts = Counter(str(item.get("depth") or item.get("level") or "").upper() for item in citation_plan)
    paper_by_id = {str(p.get("paper_id")): p for p in papers if p.get("paper_id")}
    verified = sum(1 for paper in papers if is_verified(paper))
    related_surveys = sum(
        1 for paper in papers
        if str(paper.get("survey_role") or paper.get("role") or "").lower() == "survey"
    )
    family_counts = Counter(
        str(p.get("family") or p.get("topic_axis") or p.get("survey_role") or "unassigned")
        for p in papers
    )
    scenario_counts = Counter(
        str(p.get("scenario") or p.get("domain_context") or p.get("capability") or "unassigned")
        for p in papers
        if p.get("scenario") or p.get("domain_context") or p.get("capability")
    )
    benchmark_refs = sum(
        1 for paper in papers
        if str(paper.get("survey_role") or paper.get("role") or "").lower() == "benchmark"
        or "benchmark" in str(paper.get("title") or "").lower()
    )
    missing = []
    if verified < thresholds["verified"]:
        missing.append("verified_refs")
    if depth_counts["A"] < thresholds["a"]:
        missing.append("a_level_refs")
    if depth_counts["B"] < thresholds["b"]:
        missing.append("b_level_refs")
    if related_surveys < thresholds["related_surveys"]:
        missing.append("related_surveys")
    unassigned = family_counts.get("unassigned", 0)
    if target in {"full", "csur"} and papers and unassigned == len(papers):
        missing.append("all_coverage_unassigned")
    return {
        "valid": not missing,
        "missing": missing,
        "thresholds": thresholds,
        "verified_refs": verified,
        "a_refs": depth_counts["A"],
        "b_refs": depth_counts["B"],
        "c_refs": depth_counts["C"],
        "related_surveys": related_surveys,
        "benchmark_refs": benchmark_refs,
        "families": dict(family_counts),
        "scenarios": dict(scenario_counts),
        "paper_ids_in_plan": sum(1 for item in citation_plan if str(item.get("paper_id")) in paper_by_id),
    }


def render_markdown(status: dict) -> str:
    lines = ["# Coverage Matrix", "", "| Metric | Value |", "| --- | --- |"]
    for key in ["verified_refs", "a_refs", "b_refs", "c_refs", "related_surveys"]:
        lines.append(f"| {key} | {status.get(key, 0)} |")
    lines.append("")
    lines.append("## Families")
    lines.append("")
    lines.append("| Family | Count |")
    lines.append("| --- | --- |")
    for family, count in sorted(status.get("families", {}).items()):
        lines.append(f"| {family} | {count} |")
    if status.get("scenarios"):
        lines.append("")
        lines.append("## Scenarios")
        lines.append("")
        lines.append("| Scenario | Count |")
        lines.append("| --- | --- |")
        for scenario, count in sorted(status.get("scenarios", {}).items()):
            lines.append(f"| {scenario} | {count} |")
    lines.append("")
    lines.append(f"Benchmark references: {status.get('benchmark_refs', 0)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", required=True, type=Path)
    parser.add_argument("--citation-plan", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    status = build_coverage(read_jsonl(args.papers), read_jsonl(args.citation_plan), args.target)
    if args.output:
        args.output.write_text(render_markdown(status), encoding="utf-8")
    print(json.dumps(status, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if status["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
