#!/usr/bin/env python3
"""Validate topic-boundary profiles before discovery starts."""

from __future__ import annotations


REQUIRED_FIELDS = [
    "topic",
    "central_question",
    "positive_anchors",
    "negative_anchors",
    "allowed_background",
    "core_claim_types",
    "search_seed_queries",
    "acceptance_rubric",
]


def _list(value) -> list:
    return value if isinstance(value, list) else []


def validate_topic_profile(profile: dict, target: str = "full") -> dict:
    errors: list[str] = []
    if not isinstance(profile, dict):
        return {"valid": False, "errors": ["topic_profile_not_object"]}
    for field in REQUIRED_FIELDS:
        value = profile.get(field)
        if value in [None, "", [], {}]:
            errors.append(f"missing_{field}")
    positive = _list(profile.get("positive_anchors"))
    negative = _list(profile.get("negative_anchors"))
    background = _list(profile.get("allowed_background"))
    claim_types = _list(profile.get("core_claim_types"))
    queries = _list(profile.get("search_seed_queries"))
    min_positive = 3 if target in {"full", "csur"} else 1
    min_queries = 3 if target in {"full", "csur"} else 1
    if len([item for item in positive if str(item).strip()]) < min_positive:
        errors.append("thin_positive_anchors")
    if len([item for item in negative if str(item).strip()]) < 1:
        errors.append("missing_negative_drift_anchors")
    if len([item for item in background if str(item).strip()]) < 1:
        errors.append("missing_allowed_background")
    if len([item for item in claim_types if str(item).strip()]) < 1:
        errors.append("missing_core_claim_types")
    if len([item for item in queries if str(item).strip()]) < min_queries:
        errors.append("thin_search_seed_queries")
    rubric = profile.get("acceptance_rubric") or {}
    if not isinstance(rubric, dict):
        errors.append("invalid_acceptance_rubric")
    else:
        for key in ["paper_relevance", "survey_spine", "paper_understanding"]:
            if not str(rubric.get(key) or "").strip():
                errors.append(f"missing_acceptance_rubric_{key}")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "positive_anchor_count": len(positive),
        "negative_anchor_count": len(negative),
        "search_seed_query_count": len(queries),
    }
