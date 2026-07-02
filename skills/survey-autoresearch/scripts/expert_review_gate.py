#!/usr/bin/env python3
"""Validate independent expert review reports for final survey readiness."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path


REQUIRED_PERSONAS = {
    "Domain Expert Reviewer",
    "Survey Architect Reviewer",
    "Evidence/Factuality Reviewer",
    "Newcomer/Tutorial Reviewer",
    "Style/Publication Reviewer",
}

REQUIRED_DIMENSIONS = {
    "narrative_coherence",
    "paper_understanding_depth",
    "field_native_taxonomy_quality",
    "method_taxonomy_quality",
    "benchmark_and_evaluation_quality",
    "evidence_factuality_and_citation_accuracy",
    "synthesis_not_catalog",
    "publication_prose",
    "newcomer_value",
    "expert_value",
}

VALID_ROUTES = {
    "paper_understanding",
    "synthesis_dossiers",
    "argument_graph",
    "section_evidence_plan",
    "article_quality",
    "source_verification",
    "coverage",
    "claim_evidence",
    "benchmark_dossiers",
}

BLOCKING_SEVERITIES = {"major", "blocking"}
MIN_REVIEW_QUOTES = 5
MIN_AUDIT_ITEMS = 10


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_json(path: Path) -> dict:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _score(value) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0 or score > 10:
        return None
    return score


def _threshold(target: str) -> float:
    if target == "csur":
        return 9.0
    if target == "full":
        return 8.5
    return 0.0


def _weakness_valid(weakness: dict) -> bool:
    return all(str(weakness.get(field) or "").strip() for field in ["severity", "evidence_quote", "why_it_matters", "route_to", "repair_action"]) and str(weakness.get("route_to")) in VALID_ROUTES


def _article_sections(review_text: str) -> list[str]:
    sections = []
    for match in re.finditer(r"^##\s+(.+?)\s*$", review_text or "", flags=re.MULTILINE):
        title = match.group(1).strip()
        if not re.search(r"references|appendix|参考文献|附录", title, flags=re.IGNORECASE):
            sections.append(title)
    return sections


def _normalize(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _quote_in_text(quote: str, review_text: str) -> bool:
    quote = re.sub(r"\s+", " ", str(quote or "").strip())
    if len(quote) < 18:
        return False
    return quote in re.sub(r"\s+", " ", review_text or "")


def _nonempty_text(value, min_chars: int = 24) -> bool:
    return len(str(value or "").strip()) >= min_chars


def _valid_audit_items(items, min_items: int = MIN_AUDIT_ITEMS) -> bool:
    if not isinstance(items, list) or len(items) < min_items:
        return False
    valid = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if _nonempty_text(item.get("finding") or item.get("comment") or item.get("assessment"), 20) and str(item.get("verdict") or "").strip():
            valid += 1
    return valid >= min_items


def validate_expert_reviews(
    reports: list[dict],
    target: str = "full",
    iteration_status: dict | None = None,
    review_text: str = "",
    claims: list[dict] | None = None,
    mechanism_cards: list[dict] | None = None,
    section_plans: list[dict] | None = None,
) -> dict:
    if target == "short":
        return {
            "valid": True,
            "required": False,
            "errors": [],
            "total_reviews": len(reports),
            "median_score": None,
            "threshold": _threshold(target),
        }
    errors: list[str] = []
    invalid_reports: dict[str, list[str]] = {}
    if len(reports) < 3:
        errors.append("too_few_expert_reviews")

    personas = [str(report.get("persona") or "") for report in reports]
    duplicate_personas = sorted({persona for persona in personas if persona and personas.count(persona) > 1})
    if duplicate_personas:
        errors.append("duplicate_reviewer_personas")
    missing_personas = sorted(REQUIRED_PERSONAS - set(personas))
    if len(reports) >= 5 and missing_personas:
        errors.append("missing_required_personas")

    scores: list[float] = []
    unresolved_major: list[dict] = []
    weakness_routes: list[dict] = []
    article_sections = _article_sections(review_text)
    require_full_article_audit = target in {"full", "csur"}
    summaries = []
    dimension_fingerprints = []
    for idx, report in enumerate(reports, start=1):
        reviewer_id = str(report.get("reviewer_id") or f"review_{idx}")
        item_errors = []
        if not str(report.get("reviewer_id") or "").strip():
            item_errors.append("missing_reviewer_id")
        if not str(report.get("persona") or "").strip():
            item_errors.append("missing_persona")
        score = _score(report.get("overall_score"))
        if score is None:
            item_errors.append("invalid_overall_score")
        else:
            scores.append(score)
        dimensions = report.get("dimension_scores")
        if not isinstance(dimensions, dict):
            item_errors.append("missing_dimension_scores")
        else:
            dimension_fingerprints.append(json.dumps(dimensions, sort_keys=True))
            missing_dimensions = sorted(REQUIRED_DIMENSIONS - set(dimensions))
            if missing_dimensions:
                item_errors.append("missing_dimensions:" + ",".join(missing_dimensions))
            invalid_dimensions = [name for name, value in dimensions.items() if _score(value) is None]
            if invalid_dimensions:
                item_errors.append("invalid_dimension_scores:" + ",".join(sorted(invalid_dimensions)))
        summaries.append(_normalize(report.get("summary")))
        if require_full_article_audit:
            trace = report.get("review_trace") or {}
            if not isinstance(trace, dict) or trace.get("reviewed_full_article") is not True:
                item_errors.append("missing_full_article_review_trace")
            if review_text and int(trace.get("article_chars_read") or 0) < int(len(review_text) * 0.9):
                item_errors.append("article_chars_read_too_low")
            sections_reviewed = [str(section) for section in report.get("sections_reviewed") or []]
            missing_sections = [section for section in article_sections if section not in sections_reviewed]
            if article_sections and missing_sections:
                item_errors.append("missing_sections_reviewed:" + ",".join(missing_sections[:5]))
            section_comments = report.get("section_comments") or {}
            if not isinstance(section_comments, dict):
                item_errors.append("missing_section_comments")
            else:
                thin_comments = [
                    section for section in article_sections
                    if section not in section_comments or not _nonempty_text(section_comments.get(section), 24)
                ]
                if thin_comments:
                    item_errors.append("thin_section_comments:" + ",".join(thin_comments[:5]))
            quotes = report.get("quoted_evidence_from_review") or []
            if not isinstance(quotes, list) or len(quotes) < MIN_REVIEW_QUOTES:
                item_errors.append("too_few_review_quotes")
            elif review_text:
                missing_quotes = [str(quote)[:40] for quote in quotes if not _quote_in_text(str(quote), review_text)]
                if missing_quotes:
                    item_errors.append("quotes_not_found_in_review:" + ",".join(missing_quotes[:3]))
            persona = str(report.get("persona") or "")
            if persona == "Domain Expert Reviewer" and not _valid_audit_items(report.get("paper_mechanism_audits")):
                item_errors.append("missing_paper_mechanism_audits")
            if persona == "Evidence/Factuality Reviewer" and not _valid_audit_items(report.get("claim_citation_audits")):
                item_errors.append("missing_claim_citation_audits")
            if persona == "Survey Architect Reviewer":
                audit = report.get("flow_taxonomy_audit") or {}
                if not isinstance(audit, dict) or not all(_nonempty_text(audit.get(field), 30) for field in ["section_flow", "taxonomy_coherence", "synthesis_vs_catalog"]):
                    item_errors.append("missing_flow_taxonomy_audit")
            if persona == "Newcomer/Tutorial Reviewer":
                audit = report.get("tutorial_audit") or {}
                if not isinstance(audit, dict) or not all(_nonempty_text(audit.get(field), 30) for field in ["glossary_clarity", "running_example_usefulness", "confusing_terms"]):
                    item_errors.append("missing_tutorial_audit")
            if persona == "Style/Publication Reviewer":
                audit = report.get("style_audit") or {}
                if not isinstance(audit, dict) or not all(_nonempty_text(audit.get(field), 30) for field in ["repetition", "artifact_leakage", "table_interpretation", "transition_quality"]):
                    item_errors.append("missing_style_audit")
        weaknesses = report.get("blocking_weaknesses") or []
        if not isinstance(weaknesses, list):
            item_errors.append("invalid_blocking_weaknesses")
            weaknesses = []
        for weakness in weaknesses:
            if not isinstance(weakness, dict) or not _weakness_valid(weakness):
                item_errors.append("invalid_weakness")
                continue
            route = {
                "reviewer_id": reviewer_id,
                "persona": report.get("persona"),
                "severity": weakness.get("severity"),
                "route_to": weakness.get("route_to"),
                "repair_action": weakness.get("repair_action"),
                "evidence_quote": weakness.get("evidence_quote"),
            }
            weakness_routes.append(route)
            if str(weakness.get("severity")).lower() in BLOCKING_SEVERITIES:
                unresolved_major.append(route)
        if report.get("pass_recommendation") is not True and not weaknesses and score is not None and score >= _threshold(target):
            item_errors.append("missing_pass_recommendation")
        if item_errors:
            invalid_reports[reviewer_id] = sorted(set(item_errors))

    if invalid_reports:
        errors.append("invalid_expert_review_reports")
    if require_full_article_audit and len(reports) >= 2:
        nonempty_summaries = [summary for summary in summaries if summary]
        if len(set(nonempty_summaries)) < max(2, len(nonempty_summaries) - 1):
            errors.append("non_independent_reviewer_summaries")
        if dimension_fingerprints and len(set(dimension_fingerprints)) == 1:
            errors.append("identical_dimension_scores")
    median_score = statistics.median(scores) if scores else None
    threshold = _threshold(target)
    if median_score is None or median_score < threshold:
        errors.append("median_score_below_threshold")
    if unresolved_major:
        errors.append("unresolved_major_weaknesses")

    status = iteration_status or {}
    quality_limited = False
    try:
        current = float(status.get("last_median_score"))
        previous = float(status.get("previous_median_score"))
        quality_limited = current < threshold and current >= 8.0 and abs(current - previous) < 0.2
    except (TypeError, ValueError):
        quality_limited = False
    if quality_limited:
        errors.append("quality_limited_stop_rule")

    return {
        "valid": not errors,
        "required": True,
        "errors": sorted(set(errors)),
        "total_reviews": len(reports),
        "median_score": median_score,
        "threshold": threshold,
        "missing_personas": missing_personas,
        "duplicate_personas": duplicate_personas,
        "invalid_reports": invalid_reports,
        "unresolved_major_weaknesses": unresolved_major,
        "weakness_routes": weakness_routes,
        "quality_limited": quality_limited,
        "article_sections_required": len(article_sections),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expert-review-reports", required=True, type=Path)
    parser.add_argument("--review-iteration-status", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--claims", type=Path)
    parser.add_argument("--paper-mechanism-cards", type=Path)
    parser.add_argument("--section-evidence-plans", type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    result = validate_expert_reviews(
        read_jsonl(args.expert_review_reports),
        args.target,
        read_json(args.review_iteration_status) if args.review_iteration_status else None,
        args.review.read_text(encoding="utf-8") if args.review and args.review.exists() else "",
        read_jsonl(args.claims) if args.claims else None,
        read_jsonl(args.paper_mechanism_cards) if args.paper_mechanism_cards else None,
        read_jsonl(args.section_evidence_plans) if args.section_evidence_plans else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
