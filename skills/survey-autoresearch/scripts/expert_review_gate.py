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
REVIEWER_REPORT_TERMS = {"expert_review_reports", "previous reviewer", "reviewer reports"}
REQUIRED_REVIEWER_COUNT = len(REQUIRED_PERSONAS)
DIMENSION_FLOOR = {"full": 8.0, "csur": 8.5}
REPAIR_ACTION_TERMS = {"repair actions", "repair_actions", "repair actions from this round"}
ROUTE_EVIDENCE_REQUIREMENTS = {
    "paper_understanding": {"paper_mechanism_cards", "full_text_source"},
    "claim_evidence": {"claim_evidence_spans", "full_text_source"},
    "source_verification": {"full_text_source", "source_verification"},
    "synthesis_dossiers": {"contribution_tree", "argument_graph"},
    "argument_graph": {"contribution_tree", "argument_graph"},
    "section_evidence_plan": {"section_evidence_plans"},
    "benchmark_dossiers": {"benchmark_dossiers", "claim_evidence_spans"},
    "coverage": {"coverage_matrix", "raw_candidates"},
    "article_quality": {"review", "claim_evidence_spans", "argument_graph"},
}


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


def _audit_dimension_name(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("/", "_")


def _dimension_audit_status(report: dict, target: str) -> tuple[list[str], dict[str, float]]:
    audits = report.get("dimension_audits")
    if not isinstance(audits, list):
        return ["missing_dimension_audits"], {}
    by_dimension: dict[str, dict] = {}
    errors: list[str] = []
    for audit in audits:
        if not isinstance(audit, dict):
            errors.append("invalid_dimension_audit")
            continue
        name = _audit_dimension_name(audit.get("dimension"))
        if name:
            by_dimension[name] = audit
    missing = sorted(REQUIRED_DIMENSIONS - set(by_dimension))
    if missing:
        errors.append("missing_dimension_audits:" + ",".join(missing))
    scores: dict[str, float] = {}
    has_major_weakness = any(
        str(weakness.get("severity") or "").lower() in BLOCKING_SEVERITIES
        for weakness in report.get("blocking_weaknesses") or []
        if isinstance(weakness, dict)
    )
    floor = DIMENSION_FLOOR.get(target, 8.0)
    for name in REQUIRED_DIMENSIONS:
        audit = by_dimension.get(name)
        if not audit:
            continue
        score = _score(audit.get("score"))
        if score is None:
            errors.append(f"invalid_dimension_audit_score:{name}")
            continue
        scores[name] = score
        verdict = str(audit.get("verdict") or "").strip().lower()
        if verdict not in {"pass", "fail", "borderline"}:
            errors.append(f"invalid_dimension_verdict:{name}")
        required_fields = ["why_it_matters", "repair_recommendation", "route_to"]
        for field in required_fields:
            if not _nonempty_text(audit.get(field), 12):
                errors.append(f"thin_dimension_audit:{name}:{field}")
        if str(audit.get("route_to") or "") not in VALID_ROUTES:
            errors.append(f"invalid_dimension_route:{name}")
        quotes = audit.get("evidence_quotes")
        if not isinstance(quotes, list) or not any(_nonempty_text(quote, 18) for quote in quotes):
            errors.append(f"missing_dimension_evidence_quotes:{name}")
        if score < floor and not has_major_weakness:
            errors.append("low_dimension_without_major_weakness")
    return sorted(set(errors)), scores


def _weakness_id(weakness: dict, route: dict | None = None) -> str:
    explicit = str((weakness or {}).get("weakness_id") or (route or {}).get("weakness_id") or "").strip()
    if explicit:
        return explicit
    text = "|".join(
        str((weakness or route or {}).get(field) or "")
        for field in ["evidence_quote", "route_to", "repair_action"]
    )
    return _normalize(text)


def _valid_invocations(
    reports: list[dict],
    invocations: list[dict] | None,
    round_status: dict | None = None,
) -> tuple[list[str], dict[str, list[str]]]:
    if not invocations:
        return ["missing_expert_review_invocations"], {}
    by_id = {str(item.get("reviewer_id") or ""): item for item in invocations if item.get("reviewer_id")}
    errors: list[str] = []
    invalid: dict[str, list[str]] = {}
    for report in reports:
        reviewer_id = str(report.get("reviewer_id") or "")
        invocation = by_id.get(reviewer_id)
        item_errors = []
        if not invocation:
            invalid[reviewer_id or "<missing>"] = ["missing_invocation"]
            continue
        if invocation.get("fresh_context") is not True:
            item_errors.append("fresh_context_not_true")
        if not str(invocation.get("subagent_session_id") or "").strip():
            item_errors.append("missing_subagent_session_id")
        if str(invocation.get("status") or "") != "returned":
            item_errors.append("review_not_returned")
        if not str(invocation.get("review_round_id") or "").strip():
            item_errors.append("missing_review_round_id")
        expected_round = str((round_status or {}).get("review_round_id") or "")
        if expected_round and str(invocation.get("review_round_id") or "") != expected_round:
            item_errors.append("review_round_mismatch")
        inputs = [str(item).lower() for item in invocation.get("inputs") or []]
        if not any("review.md" in item for item in inputs):
            item_errors.append("missing_review_input")
        if any(any(term in item for term in REVIEWER_REPORT_TERMS) for item in inputs):
            item_errors.append("reviewer_report_used_as_input")
        forbidden = " ".join(str(item).lower() for item in invocation.get("forbidden_inputs") or [])
        if not any(term in forbidden for term in REVIEWER_REPORT_TERMS):
            item_errors.append("previous_reports_not_forbidden")
        if not any(term in forbidden for term in REPAIR_ACTION_TERMS):
            item_errors.append("repair_actions_not_forbidden")
        if not str(invocation.get("output") or "").strip():
            item_errors.append("missing_output")
        if item_errors:
            invalid[reviewer_id or "<missing>"] = item_errors
    missing = [str(report.get("reviewer_id") or "<missing>") for report in reports if str(report.get("reviewer_id") or "") not in by_id]
    if missing:
        errors.append("missing_expert_review_invocations")
    if invalid:
        errors.append("invalid_expert_review_invocations")
    return errors, invalid


def _round_status_errors(
    reports: list[dict],
    round_status: dict | None,
    repair_actions: list[dict] | None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(round_status, dict) or not round_status:
        return ["missing_expert_review_round_status"]
    if round_status.get("expert_review_blocked_by_unavailable_independent_review") is True:
        errors.append("expert_review_blocked_by_unavailable_independent_review")
    freeze = round_status.get("review_freeze") or {}
    frozen = freeze.get("frozen_artifacts") if isinstance(freeze, dict) else None
    if not isinstance(freeze, dict) or not str(freeze.get("review_round_id") or "").strip() or not isinstance(frozen, dict):
        errors.append("missing_review_freeze")
    else:
        for artifact in ["outputs/review.md", "outputs/appendix.md", "state/argument_graph.yml", "state/section_evidence_plans.jsonl"]:
            if not str(frozen.get(artifact) or "").strip():
                errors.append("incomplete_review_freeze")
                break
        if not str(freeze.get("article_hash") or "").strip():
            errors.append("missing_frozen_article_hash")
    if round_status.get("all_reports_received") is not True:
        errors.append("expert_reviews_not_all_returned")
        if repair_actions:
            errors.append("repair_before_all_reviews_returned")
    if int(round_status.get("reviewers_expected") or 0) < REQUIRED_REVIEWER_COUNT:
        errors.append("too_few_expected_reviewers")
    if int(round_status.get("reviewers_returned") or 0) < REQUIRED_REVIEWER_COUNT:
        errors.append("expert_reviews_not_all_returned")
    if len(reports) < REQUIRED_REVIEWER_COUNT:
        errors.append("expert_reviews_not_all_returned")
    return sorted(set(errors))


def _adjudication_status(
    reported_major: list[dict],
    adjudication: dict | None,
) -> tuple[list[str], list[dict], dict[str, list[str]]]:
    errors: list[str] = []
    invalid: dict[str, list[str]] = {}
    if not isinstance(adjudication, dict) or not adjudication:
        return ["missing_expert_review_adjudication"], [], {}
    canonical = adjudication.get("canonical_weaknesses")
    if not isinstance(canonical, list):
        return ["invalid_expert_review_adjudication"], [], {}
    canonical_major: list[dict] = []
    covered_source_ids: set[str] = set()
    for item in canonical:
        if not isinstance(item, dict):
            errors.append("invalid_expert_review_adjudication")
            continue
        wid = str(item.get("weakness_id") or "").strip()
        item_errors = []
        for field in [
            "weakness_id",
            "severity",
            "source_reviewers",
            "affected_sections",
            "affected_papers",
            "affected_claims",
            "route_to",
            "required_evidence_check",
            "repair_acceptance_criteria",
        ]:
            if not item.get(field):
                item_errors.append(f"missing_{field}")
        if str(item.get("route_to") or "") not in VALID_ROUTES:
            item_errors.append("invalid_route_to")
        if not isinstance(item.get("source_weakness_ids") or [], list):
            item_errors.append("invalid_source_weakness_ids")
        else:
            covered_source_ids.update(str(value) for value in item.get("source_weakness_ids") or [])
        if item_errors:
            invalid[wid or "<missing>"] = item_errors
        if str(item.get("severity") or "").lower() in BLOCKING_SEVERITIES:
            canonical_major.append(item)
    if invalid:
        errors.append("invalid_canonical_weaknesses")
    reported_ids = {str(item.get("weakness_id") or "") for item in reported_major if item.get("weakness_id")}
    missing = sorted(reported_ids - covered_source_ids)
    if missing:
        errors.append("unadjudicated_major_weaknesses")
    if reported_major and adjudication.get("all_major_weaknesses_adjudicated") is not True:
        errors.append("major_weaknesses_not_marked_adjudicated")
    return sorted(set(errors)), canonical_major, invalid


def _repair_status(
    unresolved_major: list[dict],
    repair_actions: list[dict] | None,
    regression_checks: list[dict] | None,
    targeted_rereviews: list[dict] | None = None,
    round_status: dict | None = None,
) -> tuple[list[str], list[dict], dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    if not unresolved_major:
        return [], [], {}, {}, {}
    repairs_by_id = {str(item.get("weakness_id") or ""): item for item in repair_actions or [] if item.get("weakness_id")}
    checks_by_id = {}
    for check in regression_checks or []:
        if check.get("weakness_id"):
            checks_by_id.setdefault(str(check.get("weakness_id")), []).append(check)
    errors: list[str] = []
    still_unresolved = []
    rereviews_by_id = {}
    for rereview in targeted_rereviews or []:
        if rereview.get("weakness_id"):
            rereviews_by_id.setdefault(str(rereview.get("weakness_id")), []).append(rereview)
    invalid_repairs: dict[str, list[str]] = {}
    invalid_checks: dict[str, list[str]] = {}
    invalid_rereviews: dict[str, list[str]] = {}
    repaired_article_hash = str((round_status or {}).get("repaired_article_hash") or "")
    for weakness in unresolved_major:
        wid = str(weakness.get("weakness_id") or _weakness_id({}, weakness))
        repair = repairs_by_id.get(wid)
        if not repair:
            still_unresolved.append(weakness)
            continue
        repair_errors = []
        if str(repair.get("status") or "").lower() not in {"resolved", "accepted_limitation"}:
            repair_errors.append("repair_not_resolved")
        for field in ["route_to", "repair_action", "changed_artifacts", "evidence"]:
            if not repair.get(field):
                repair_errors.append(f"missing_{field}")
        evidence_rechecked = repair.get("evidence_rechecked")
        if not isinstance(evidence_rechecked, list) or not evidence_rechecked:
            repair_errors.append("missing_evidence_rechecked")
        else:
            evidence_sources = {str(item.get("source") or "") for item in evidence_rechecked if isinstance(item, dict)}
            for item in evidence_rechecked:
                if not isinstance(item, dict):
                    repair_errors.append("invalid_evidence_rechecked")
                    continue
                for field in ["source", "id", "finding"]:
                    if not _nonempty_text(item.get(field), 8):
                        repair_errors.append(f"thin_evidence_rechecked:{field}")
                if item.get("supports_repair") is not True:
                    repair_errors.append("evidence_does_not_support_repair")
            required_sources = ROUTE_EVIDENCE_REQUIREMENTS.get(str(repair.get("route_to") or str(weakness.get("route_to") or "")), set())
            if required_sources and not (evidence_sources & required_sources):
                repair_errors.append("missing_route_specific_evidence_check")
        for claim in repair.get("new_or_modified_claims") or []:
            if isinstance(claim, dict):
                if not (claim.get("claim_evidence_span_id") or claim.get("evidence_span_updated") is True):
                    repair_errors.append("strong_claim_without_evidence_update")
            else:
                repair_errors.append("invalid_new_or_modified_claim")
        if repair_errors:
            invalid_repairs[wid] = repair_errors
            still_unresolved.append(weakness)
            continue
        checks = checks_by_id.get(wid, [])
        if not checks or not any(str(check.get("status") or "").lower() == "passed" for check in checks):
            invalid_checks[wid] = ["missing_passing_regression_check"]
            still_unresolved.append(weakness)
            continue
        rereviews = rereviews_by_id.get(wid, [])
        resolved_rereview = False
        rereview_errors = []
        if not rereviews:
            rereview_errors.append("missing_targeted_rereview")
        for rereview in rereviews:
            item_errors = []
            if str(rereview.get("verdict") or "") == "introduced_regression":
                item_errors.append("introduced_regression")
            if str(rereview.get("verdict") or "") != "resolved":
                item_errors.append("targeted_rereview_not_resolved")
            for field in ["reviewer_id", "persona", "checked_changed_artifacts", "checked_evidence_refs", "evidence_quote_after_repair", "remaining_risk"]:
                if not rereview.get(field):
                    item_errors.append(f"missing_{field}")
            if repaired_article_hash and str(rereview.get("article_hash") or "") != repaired_article_hash:
                item_errors.append("targeted_rereview_article_hash_mismatch")
            if item_errors:
                rereview_errors.extend(item_errors)
            else:
                resolved_rereview = True
        if not resolved_rereview:
            invalid_rereviews[wid] = sorted(set(rereview_errors or ["missing_targeted_rereview"]))
            still_unresolved.append(weakness)
    if invalid_repairs:
        errors.append("invalid_repair_actions")
    if invalid_checks:
        errors.append("missing_regression_checks_for_repairs")
    if invalid_rereviews:
        if any("missing_targeted_rereview" in values for values in invalid_rereviews.values()):
            errors.append("missing_targeted_rereviews")
        errors.append("invalid_targeted_rereviews")
        if any("introduced_regression" in values for values in invalid_rereviews.values()):
            errors.append("introduced_regression")
    if still_unresolved:
        errors.append("unresolved_major_weaknesses")
    return errors, still_unresolved, invalid_repairs, invalid_checks, invalid_rereviews


def validate_expert_reviews(
    reports: list[dict],
    target: str = "full",
    iteration_status: dict | None = None,
    review_text: str = "",
    claims: list[dict] | None = None,
    mechanism_cards: list[dict] | None = None,
    section_plans: list[dict] | None = None,
    review_invocations: list[dict] | None = None,
    repair_actions: list[dict] | None = None,
    regression_checks: list[dict] | None = None,
    round_status: dict | None = None,
    adjudication: dict | None = None,
    targeted_rereviews: list[dict] | None = None,
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
    if len(reports) < REQUIRED_REVIEWER_COUNT:
        errors.append("too_few_expert_reviews")

    personas = [str(report.get("persona") or "") for report in reports]
    duplicate_personas = sorted({persona for persona in personas if persona and personas.count(persona) > 1})
    if duplicate_personas:
        errors.append("duplicate_reviewer_personas")
    missing_personas = sorted(REQUIRED_PERSONAS - set(personas))
    if missing_personas:
        errors.append("missing_required_personas")

    scores: list[float] = []
    reported_major: list[dict] = []
    weakness_routes: list[dict] = []
    article_sections = _article_sections(review_text)
    require_full_article_audit = target in {"full", "csur"}
    summaries = []
    dimension_fingerprints = []
    dimension_scores_by_name: dict[str, list[float]] = {name: [] for name in REQUIRED_DIMENSIONS}
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
        dimension_errors, dimension_scores = _dimension_audit_status(report, target)
        item_errors.extend(dimension_errors)
        for name, value in dimension_scores.items():
            dimension_scores_by_name.setdefault(name, []).append(value)
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
                "weakness_id": _weakness_id(weakness),
                "reviewer_id": reviewer_id,
                "persona": report.get("persona"),
                "severity": weakness.get("severity"),
                "route_to": weakness.get("route_to"),
                "repair_action": weakness.get("repair_action"),
                "evidence_quote": weakness.get("evidence_quote"),
            }
            weakness_routes.append(route)
            if str(weakness.get("severity")).lower() in BLOCKING_SEVERITIES:
                reported_major.append(route)
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
    dimension_medians = {}
    dimension_floor = DIMENSION_FLOOR.get(target, 0.0)
    for name in REQUIRED_DIMENSIONS:
        values = dimension_scores_by_name.get(name) or []
        if values:
            dimension_medians[name] = statistics.median(values)
            if dimension_medians[name] < dimension_floor:
                errors.append("dimension_median_below_threshold")
        else:
            dimension_medians[name] = None
            errors.append("missing_dimension_median")
    round_errors = _round_status_errors(reports, round_status, repair_actions)
    errors.extend(round_errors)
    invocation_errors, invalid_invocations = _valid_invocations(reports, review_invocations, round_status)
    errors.extend(invocation_errors)
    adjudication_errors, canonical_major, invalid_adjudication = _adjudication_status(reported_major, adjudication)
    errors.extend(adjudication_errors)
    unresolved_major = canonical_major or reported_major
    repair_errors, unresolved_major, invalid_repairs, invalid_regression_checks, invalid_targeted_rereviews = _repair_status(
        unresolved_major,
        repair_actions,
        regression_checks,
        targeted_rereviews,
        round_status,
    )
    errors.extend(repair_errors)

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
        "invalid_invocations": invalid_invocations,
        "round_status": round_status or {},
        "dimension_medians": dimension_medians,
        "invalid_adjudication": invalid_adjudication,
        "invalid_repair_actions": invalid_repairs,
        "invalid_regression_checks": invalid_regression_checks,
        "invalid_targeted_rereviews": invalid_targeted_rereviews,
        "unresolved_major_weaknesses": unresolved_major,
        "weakness_routes": weakness_routes,
        "canonical_major_weaknesses": canonical_major,
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
    parser.add_argument("--expert-review-invocations", type=Path)
    parser.add_argument("--repair-actions", type=Path)
    parser.add_argument("--regression-checks", type=Path)
    parser.add_argument("--expert-review-round-status", type=Path)
    parser.add_argument("--expert-review-adjudication", type=Path)
    parser.add_argument("--targeted-rereviews", type=Path)
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
        read_jsonl(args.expert_review_invocations) if args.expert_review_invocations else None,
        read_jsonl(args.repair_actions) if args.repair_actions else None,
        read_jsonl(args.regression_checks) if args.regression_checks else None,
        read_json(args.expert_review_round_status) if args.expert_review_round_status else None,
        read_json(args.expert_review_adjudication) if args.expert_review_adjudication else None,
        read_jsonl(args.targeted_rereviews) if args.targeted_rereviews else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
