#!/usr/bin/env python3
"""Score papers with the Literature Quality Score used by survey-autoresearch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


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


def lqs_bucket(lqs: float) -> str:
    if lqs >= 7.0:
        return "must-cite"
    if lqs >= 5.0:
        return "conditional"
    return "drop"


def score_paper(paper: dict) -> dict:
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
    scored = dict(paper)
    scored["lqs_components"] = components
    scored["lqs"] = round(lqs, 2)
    scored["lqs_bucket"] = lqs_bucket(lqs)
    return scored


def classify_depth(scored_paper: dict, role: str = "") -> str:
    bucket = scored_paper.get("lqs_bucket") or lqs_bucket(float(scored_paper.get("lqs", 0)))
    role = role.lower()
    if bucket == "drop":
        return "D"
    if "section" in role or "protagonist" in role or "seminal" in role:
        return "A" if bucket == "must-cite" else "B"
    if "support" in role or "context" in role:
        return "C"
    if bucket == "must-cite":
        return "B"
    return "C"


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
