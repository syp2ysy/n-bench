#!/usr/bin/env python3
"""Score papers with the Literature Quality Score used by survey-autoresearch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEPTH_RANK = {"D": 0, "exclude": 0, "C": 1, "B": 2, "A": 3}


def recency_score(months: float | int | None) -> float:
    if months is None:
        return 3.0
    if months <= 6:
        return 10.0
    if months <= 12:
        return 8.0
    if months <= 24:
        return 5.0
    if months <= 36:
        return 3.0
    return 2.0


def citation_score(cites_per_month: float | int | None) -> float:
    if cites_per_month is None:
        return 3.0
    if cites_per_month >= 50:
        return 10.0
    if cites_per_month >= 10:
        return 8.0
    if cites_per_month >= 3:
        return 6.0
    if cites_per_month > 0:
        return 4.0
    return 3.0


def venue_score(tier: str | None) -> float:
    tier = (tier or "").lower()
    return {
        "top": 10.0,
        "top-tier": 10.0,
        "strong": 7.0,
        "main": 7.0,
        "workshop": 4.0,
        "preprint": 3.0,
    }.get(tier, 5.0)


def institution_score(tier: str | None) -> float:
    tier = (tier or "").lower()
    return {
        "top_lab": 10.0,
        "top-lab": 10.0,
        "top_uni": 9.0,
        "top-university": 9.0,
        "known": 6.0,
        "unknown": 4.0,
    }.get(tier, 5.0)


def acceptance_score(status: str | None) -> float:
    status = (status or "").lower()
    return {
        "accepted": 10.0,
        "published": 10.0,
        "peer_reviewed": 10.0,
        "under_review": 5.0,
        "preprint": 3.0,
        "none": 3.0,
    }.get(status, 5.0)


def numeric_score(value, default: float = 5.0) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return 10.0 if value else 3.0
    try:
        return max(0.0, min(10.0, float(value)))
    except (TypeError, ValueError):
        text = str(value).strip().lower()
        return {
            "high": 9.0,
            "strong": 8.0,
            "medium": 6.0,
            "low": 3.0,
            "none": 0.0,
        }.get(text, default)


def role_centrality(role: str | None) -> float:
    role = (role or "").lower()
    if role in {"foundational", "seminal"}:
        return 10.0
    if role in {"system", "bridge"}:
        return 8.0
    if role in {"benchmark", "ablation", "negative", "failure"}:
        return 7.5
    if role in {"survey", "frontier"}:
        return 7.0
    if role == "application":
        return 5.5
    return 5.0


def has_survey_role_fields(paper: dict) -> bool:
    return any(
        field in paper
        for field in [
            "survey_role",
            "conceptual_centrality",
            "mechanism_clarity",
            "evidence_strength",
            "taxonomy_coverage_value",
            "benchmark_or_ablation_value",
            "venue_or_verification",
        ]
    )


def survey_role_components(paper: dict) -> dict:
    role = paper.get("survey_role")
    mechanism_default = 8.0 if paper.get("method_summary") or paper.get("mechanism_or_contribution") else 5.0
    evidence_default = 8.0 if paper.get("accepted") or paper.get("verified") or paper.get("ablations") else 5.0
    taxonomy_default = 8.0 if paper.get("taxonomy_cell") or paper.get("system_node") or paper.get("memory_node") else 5.0
    benchmark_default = 8.0 if paper.get("benchmark_or_dataset") or paper.get("metrics") or paper.get("ablations") else 5.0
    venue_default = acceptance_score(paper.get("acceptance_status") or ("accepted" if paper.get("accepted") else None))
    return {
        "conceptual_centrality": numeric_score(
            paper.get("conceptual_centrality"),
            default=role_centrality(role),
        ),
        "mechanism_clarity": numeric_score(paper.get("mechanism_clarity"), default=mechanism_default),
        "evidence_strength": numeric_score(paper.get("evidence_strength"), default=evidence_default),
        "taxonomy_coverage_value": numeric_score(
            paper.get("taxonomy_coverage_value"),
            default=taxonomy_default,
        ),
        "benchmark_or_ablation_value": numeric_score(
            paper.get("benchmark_or_ablation_value"),
            default=benchmark_default,
        ),
        "venue_or_verification": numeric_score(paper.get("venue_or_verification"), default=venue_default),
    }


def lqs_bucket(lqs: float) -> str:
    if lqs >= 7.0:
        return "must-cite"
    if lqs >= 5.0:
        return "conditional"
    return "drop"


def score_paper(paper: dict) -> dict:
    if has_survey_role_fields(paper):
        components = survey_role_components(paper)
        lqs = (
            components["conceptual_centrality"] * 0.25
            + components["mechanism_clarity"] * 0.20
            + components["evidence_strength"] * 0.20
            + components["taxonomy_coverage_value"] * 0.15
            + components["benchmark_or_ablation_value"] * 0.10
            + components["venue_or_verification"] * 0.10
        )
        model = "survey-role"
    else:
        components = {
            "recency": recency_score(paper.get("recency_months")),
            "citation_impact": citation_score(paper.get("citations_per_month")),
            "venue": venue_score(paper.get("venue_tier")),
            "institution": institution_score(paper.get("institution_tier")),
            "acceptance": acceptance_score(paper.get("acceptance_status")),
        }
        lqs = (
            components["recency"] * 0.30
            + components["citation_impact"] * 0.25
            + components["venue"] * 0.20
            + components["institution"] * 0.10
            + components["acceptance"] * 0.15
        )
        model = "metadata-baseline"
    scored = dict(paper)
    scored["lqs_components"] = components
    scored["lqs"] = round(lqs, 2)
    scored["lqs_bucket"] = lqs_bucket(lqs)
    scored["lqs_model"] = model
    return scored


def classify_depth(scored_paper: dict, role: str = "") -> str:
    bucket = scored_paper.get("lqs_bucket") or lqs_bucket(float(scored_paper.get("lqs", 0)))
    role = role.lower()
    if bucket == "drop":
        depth = "D"
    elif "section" in role or "protagonist" in role or "seminal" in role:
        depth = "A" if bucket == "must-cite" else "B"
    elif "support" in role or "context" in role:
        depth = "C"
    elif bucket == "must-cite":
        depth = "B"
    else:
        depth = "C"
    allowed = str(scored_paper.get("topic_allowed_depth") or scored_paper.get("allowed_depth") or "").strip()
    if allowed and DEPTH_RANK.get(depth, 0) > DEPTH_RANK.get(allowed, 0):
        return "D" if allowed == "exclude" else allowed
    return depth


def iter_jsonl(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with args.output.open("w", encoding="utf-8") as handle:
        for paper in iter_jsonl(args.input):
            handle.write(json.dumps(score_paper(paper), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
