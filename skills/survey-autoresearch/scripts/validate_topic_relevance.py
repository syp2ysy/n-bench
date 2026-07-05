#!/usr/bin/env python3
"""Validate worker-produced topic relevance audits for source selection."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .validate_coverage import TARGETS, read_jsonl
except ImportError:  # pragma: no cover
    from validate_coverage import TARGETS, read_jsonl


VALID_GRADES = {"core", "direct_related_survey", "adjacent_background", "generic_background", "out_of_scope"}
VALID_DEPTHS = {"A", "B", "C", "exclude"}
VALID_ROLES = {"core", "related_survey", "background", "exclude"}
VALID_SECONDARY_DECISIONS = {"confirm_core", "downgrade_to_C", "exclude", "direct_related_survey"}
DEPTH_RANK = {"exclude": 0, "C": 1, "B": 2, "A": 3}
DIRECT_RELATED_AB_LIMIT = {"short": 1, "full": 4, "csur": 6}


def _paper_id(row: dict) -> str:
    return str(row.get("paper_id") or "").strip()


def _candidate_id(row: dict) -> str:
    return str(row.get("candidate_id") or row.get("source_candidate_id") or row.get("paper_id") or "").strip()


def _depth(row: dict) -> str:
    return str(row.get("depth") or row.get("level") or "").upper().strip()


def normalize_family(value) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())


def audit_by_paper(audit_rows: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in audit_rows:
        pid = _paper_id(row)
        if pid and pid not in result:
            result[pid] = row
    return result


def _has_text_evidence(evidence) -> bool:
    if not isinstance(evidence, list) or not evidence:
        return False
    for item in evidence:
        if not isinstance(item, dict):
            return False
        if not str(item.get("field") or "").strip() or not str(item.get("text") or "").strip():
            return False
    return True


def _audit_schema_errors(row: dict, idx: int) -> list[str]:
    errors: list[str] = []
    pid = _paper_id(row)
    if not pid:
        errors.append(f"missing_paper_id:{idx}")
    if not _candidate_id(row):
        errors.append(f"missing_candidate_id:{pid or idx}")
    if not _has_text_evidence(row.get("evidence_used")):
        errors.append(f"missing_evidence_used:{pid or idx}")
    if str(row.get("relevance_grade") or "") not in VALID_GRADES:
        errors.append(f"invalid_relevance_grade:{pid or idx}")
    if str(row.get("allowed_depth") or "") not in VALID_DEPTHS:
        errors.append(f"invalid_allowed_depth:{pid or idx}")
    if str(row.get("allowed_role") or "") not in VALID_ROLES:
        errors.append(f"invalid_allowed_role:{pid or idx}")
    if "family_label_supported" not in row or not isinstance(row.get("family_label_supported"), bool):
        errors.append(f"invalid_family_label_supported:{pid or idx}")
    if not str(row.get("corrected_family") or "").strip():
        errors.append(f"missing_corrected_family:{pid or idx}")
    if not str(row.get("rationale") or "").strip():
        errors.append(f"missing_rationale:{pid or idx}")
    for field in ["positive_topic_signals", "negative_drift_signals"]:
        if field not in row or not isinstance(row.get(field), list):
            errors.append(f"invalid_{field}:{pid or idx}")
    grade = str(row.get("relevance_grade") or "")
    allowed_depth = str(row.get("allowed_depth") or "")
    allowed_role = str(row.get("allowed_role") or "")
    if grade in {"generic_background", "out_of_scope"} and allowed_depth in {"A", "B"}:
        errors.append(f"background_depth_too_high:{pid or idx}")
    if grade == "out_of_scope" and allowed_role != "exclude":
        errors.append(f"out_of_scope_role_not_exclude:{pid or idx}")
    if grade == "direct_related_survey" and allowed_role != "related_survey":
        errors.append(f"direct_survey_role_mismatch:{pid or idx}")
    return errors


def _required_raw_ids(raw_candidates: list[dict]) -> set[str]:
    return {_paper_id(row) for row in raw_candidates if _paper_id(row)}


def _required_retained_ids(papers: list[dict]) -> set[str]:
    return {_paper_id(row) for row in papers if _paper_id(row)}


def _ab_depths(citation_plan: list[dict]) -> dict[str, str]:
    return {
        _paper_id(row): _depth(row)
        for row in citation_plan
        if _paper_id(row) and _depth(row) in {"A", "B"}
    }


def _actual_depth_exceeds_allowed(actual: str, allowed: str) -> bool:
    return DEPTH_RANK.get(actual, 0) > DEPTH_RANK.get(allowed, 0)


def _verified_paper_ids(papers: list[dict] | None) -> set[str]:
    ids: set[str] = set()
    for paper in papers or []:
        pid = _paper_id(paper)
        if not pid:
            continue
        verified = paper.get("verified") is True or str(paper.get("verification_status") or "").lower() == "verified"
        if verified:
            ids.add(pid)
    return ids


def topic_relevance_support(
    audit_rows: list[dict],
    citation_plan: list[dict] | None = None,
    raw_candidates: list[dict] | None = None,
    papers: list[dict] | None = None,
) -> dict:
    audits = audit_by_paper(audit_rows)
    raw_ids = _required_raw_ids(raw_candidates or []) if raw_candidates is not None else set(audits)
    retained_ids = _required_retained_ids(papers or []) if papers is not None else set(audits)
    verified_ids = _verified_paper_ids(papers or []) if papers is not None else set(audits)
    ab_ids = set(_ab_depths(citation_plan or []).keys())
    raw_family_support = Counter()
    retained_family_support = Counter()
    verified_family_support = Counter()
    ab_family_support = Counter()
    verified_related_surveys = 0
    all_related_surveys = 0
    qualified_ab_ids: list[str] = []
    for pid, audit in audits.items():
        grade = str(audit.get("relevance_grade") or "")
        family = normalize_family(audit.get("corrected_family"))
        if audit.get("family_label_supported") is True and grade == "core" and family:
            if pid in raw_ids:
                raw_family_support[family] += 1
            if pid in retained_ids:
                retained_family_support[family] += 1
            if pid in verified_ids:
                verified_family_support[family] += 1
            if pid in ab_ids:
                ab_family_support[family] += 1
        if grade == "direct_related_survey" and str(audit.get("allowed_role") or "") == "related_survey":
            all_related_surveys += 1
            if pid in retained_ids and pid in verified_ids:
                verified_related_surveys += 1
        if pid in ab_ids and grade == "core" and audit.get("family_label_supported") is True:
            qualified_ab_ids.append(pid)
    return {
        "families": dict(retained_family_support),
        "raw_family_support": dict(raw_family_support),
        "retained_family_support": dict(retained_family_support),
        "verified_family_support": dict(verified_family_support),
        "ab_family_support": dict(ab_family_support),
        "core_family_support": dict(ab_family_support),
        "related_surveys": verified_related_surveys,
        "all_related_surveys": all_related_surveys,
        "verified_related_surveys": verified_related_surveys,
        "qualified_ab_ids": sorted(qualified_ab_ids),
    }


def _rich_evidence_fields(audit: dict) -> set[str]:
    return {
        str(item.get("field") or "").strip().lower()
        for item in audit.get("evidence_used") or []
        if isinstance(item, dict) and str(item.get("field") or "").strip()
    }


def _topic_boundary_rationale_present(audit: dict) -> bool:
    text = " ".join(
        [
            str(audit.get("rationale") or ""),
            " ".join(str(item) for item in audit.get("positive_topic_signals") or []),
        ]
    ).lower()
    boundary_terms = [
        "topic boundary",
        "visual intermediate",
        "image-as-workspace",
        "visual scratchpad",
        "image-grounded",
        "reasoning action",
        "visual tool",
        "workspace",
    ]
    return any(term in text for term in boundary_terms)


def _audit_session_id(audit: dict) -> str:
    return str(audit.get("subagent_session_id") or "").strip()


def second_audit_trigger_reasons(audit: dict, actual_depth: str) -> list[str]:
    if actual_depth not in {"A", "B"}:
        return []
    if str(audit.get("relevance_grade") or "") != "core" or audit.get("family_label_supported") is not True:
        return []
    reasons: list[str] = []
    evidence_fields = _rich_evidence_fields(audit)
    title_query_only = evidence_fields and evidence_fields <= {"title", "query"}
    if title_query_only:
        reasons.append("title_query_only_evidence")
    if audit.get("negative_drift_signals"):
        reasons.append("negative_drift_signals_present")
    role_text = str(audit.get("current_role") or audit.get("survey_role") or "").lower()
    title_text = str(audit.get("title") or "").lower()
    if str(audit.get("allowed_role") or "") == "core" and (
        "survey" in role_text
        or "review" in role_text
        or "survey" in title_text
        or "review" in title_text
    ):
        reasons.append("survey_or_review_labeled_core")
    if str(audit.get("allowed_depth") or "") in {"A", "B"} and not _topic_boundary_rationale_present(audit):
        reasons.append("missing_topic_boundary_rationale")
    return reasons


def _secondary_audit_by_paper(secondary_audits: list[dict] | None) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in secondary_audits or []:
        pid = _paper_id(row)
        if pid:
            result[pid] = row
    return result


def _has_rich_secondary_evidence(record: dict) -> bool:
    fields = _rich_evidence_fields(record)
    return bool(fields - {"title", "query"})


def secondary_audit_record_errors(record: dict, primary_audit: dict | None, actual_depth: str) -> list[str]:
    errors: list[str] = []
    pid = _paper_id(record)
    if not pid:
        errors.append("missing_secondary_paper_id")
    if str(record.get("decision") or "") not in VALID_SECONDARY_DECISIONS:
        errors.append("invalid_secondary_decision")
    if str(record.get("allowed_depth") or "") not in VALID_DEPTHS:
        errors.append("invalid_secondary_allowed_depth")
    if str(record.get("allowed_role") or "") not in VALID_ROLES:
        errors.append("invalid_secondary_allowed_role")
    if not _has_text_evidence(record.get("evidence_used")):
        errors.append("missing_secondary_evidence_used")
    elif not _has_rich_secondary_evidence(record):
        errors.append("secondary_evidence_title_query_only")
    if not str(record.get("rationale") or "").strip():
        errors.append("missing_secondary_rationale")
    if not isinstance(record.get("trigger_reasons"), list) or not record.get("trigger_reasons"):
        errors.append("missing_secondary_trigger_reasons")
    primary_session = _audit_session_id(primary_audit or {})
    record_primary = str(record.get("primary_audit_session_id") or "").strip()
    secondary_session = str(record.get("subagent_session_id") or "").strip()
    expected_reasons = set(second_audit_trigger_reasons(primary_audit or {}, actual_depth))
    if expected_reasons and not primary_session:
        errors.append("missing_primary_audit_session_id")
    if expected_reasons and not record_primary:
        errors.append("missing_secondary_primary_audit_session_id")
    if primary_session and record_primary and record_primary != primary_session:
        errors.append("primary_audit_session_mismatch")
    if primary_session and secondary_session == primary_session:
        errors.append("secondary_audit_not_independent")
    if not secondary_session:
        errors.append("missing_secondary_subagent_session_id")
    supplied_reasons = {str(item) for item in record.get("trigger_reasons") or []}
    if expected_reasons and not expected_reasons.issubset(supplied_reasons):
        errors.append("secondary_audit_missing_trigger_responses")
    decision = str(record.get("decision") or "")
    allowed_depth = str(record.get("allowed_depth") or "")
    allowed_role = str(record.get("allowed_role") or "")
    if decision == "confirm_core" and (allowed_depth not in {"A", "B"} or allowed_role != "core"):
        errors.append("confirm_core_role_depth_mismatch")
    if decision == "downgrade_to_C" and (allowed_depth != "C" or allowed_role not in {"background", "related_survey"}):
        errors.append("downgrade_role_depth_mismatch")
    if decision == "exclude" and (allowed_depth != "exclude" or allowed_role != "exclude"):
        errors.append("exclude_role_depth_mismatch")
    if decision == "direct_related_survey" and (allowed_depth != "C" or allowed_role != "related_survey"):
        errors.append("direct_survey_role_depth_mismatch")
    return errors


def validate_topic_relevance(
    raw_candidates: list[dict],
    papers: list[dict],
    citation_plan: list[dict],
    audit_rows: list[dict],
    survey_type_plan: str | dict | None = None,
    target: str = "full",
    secondary_audits: list[dict] | None = None,
) -> dict:
    errors: list[str] = []
    schema_errors: list[str] = []
    if not audit_rows:
        return {
            "valid": False,
            "errors": ["topic_relevance_audit_missing"],
            "schema_errors": [],
            "missing_raw_candidate_audits": sorted(_required_raw_ids(raw_candidates))[:50],
            "missing_retained_paper_audits": sorted(_required_retained_ids(papers))[:50],
            "missing_ab_paper_audits": sorted(_ab_depths(citation_plan))[:50],
            "invalid_ab_paper_ids": [],
            "summary": {
                "audit_count": 0,
                "invalid_ab_count": 0,
                "related_survey_count": 0,
                "core_ab_count": 0,
            },
        }

    seen_pids: set[str] = set()
    duplicate_pids: list[str] = []
    for idx, row in enumerate(audit_rows, start=1):
        pid = _paper_id(row)
        if pid in seen_pids:
            duplicate_pids.append(pid)
        if pid:
            seen_pids.add(pid)
        schema_errors.extend(_audit_schema_errors(row, idx))
    if duplicate_pids:
        schema_errors.append("duplicate_topic_relevance_audits")

    audits = audit_by_paper(audit_rows)
    secondaries = _secondary_audit_by_paper(secondary_audits)
    raw_ids = _required_raw_ids(raw_candidates)
    retained_ids = _required_retained_ids(papers)
    ab_depths = _ab_depths(citation_plan)
    missing_raw = sorted(raw_ids - set(audits))
    missing_retained = sorted(retained_ids - set(audits))
    missing_ab = sorted(set(ab_depths) - set(audits))
    if missing_raw:
        errors.append("missing_raw_candidate_topic_relevance_audits")
    if missing_retained:
        errors.append("missing_retained_paper_topic_relevance_audits")
    if missing_ab:
        errors.append("missing_ab_topic_relevance_audits")
    if schema_errors:
        errors.append("invalid_topic_relevance_audit")

    invalid_ab: list[str] = []
    direct_ab: list[str] = []
    core_ab: list[str] = []
    second_audit_required: list[str] = []
    second_audit_reasons: dict[str, list[str]] = {}
    secondary_audit_errors: list[str] = []
    valid_secondaries: dict[str, dict] = {}
    for pid, secondary in secondaries.items():
        if pid not in ab_depths:
            continue
        record_errors = secondary_audit_record_errors(secondary, audits.get(pid), ab_depths[pid])
        if record_errors:
            secondary_audit_errors.extend(f"{error}:{pid}" for error in record_errors)
        else:
            valid_secondaries[pid] = secondary
    if secondary_audit_errors:
        errors.append("invalid_topic_relevance_second_audit")
    for pid, actual_depth in ab_depths.items():
        audit = audits.get(pid)
        if not audit:
            invalid_ab.append(pid)
            continue
        secondary = valid_secondaries.get(pid)
        if secondary:
            decision = str(secondary.get("decision") or "")
            allowed_depth = str(secondary.get("allowed_depth") or "")
            primary_grade = str(audit.get("relevance_grade") or "")
            primary_allowed_depth = str(audit.get("allowed_depth") or "")
            primary_core = primary_grade == "core" and audit.get("family_label_supported") is True and not _actual_depth_exceeds_allowed(actual_depth, primary_allowed_depth)
            if decision == "confirm_core" and primary_core and not _actual_depth_exceeds_allowed(actual_depth, allowed_depth):
                core_ab.append(pid)
                continue
            if decision == "direct_related_survey" and primary_grade in {"core", "direct_related_survey"} and not _actual_depth_exceeds_allowed(actual_depth, allowed_depth):
                direct_ab.append(pid)
                continue
            invalid_ab.append(pid)
            continue
        grade = str(audit.get("relevance_grade") or "")
        allowed_depth = str(audit.get("allowed_depth") or "")
        if grade == "core" and audit.get("family_label_supported") is True and not _actual_depth_exceeds_allowed(actual_depth, allowed_depth):
            core_ab.append(pid)
            trigger_reasons = second_audit_trigger_reasons(audit, actual_depth)
            if trigger_reasons:
                second_audit_required.append(pid)
                second_audit_reasons[pid] = trigger_reasons
            continue
        if grade == "direct_related_survey" and not _actual_depth_exceeds_allowed(actual_depth, allowed_depth):
            direct_ab.append(pid)
            continue
        invalid_ab.append(pid)
    if invalid_ab:
        errors.append("ab_topic_relevance_failed")
    if second_audit_required:
        errors.append("topic_relevance_second_audit_required")
    if len(direct_ab) > DIRECT_RELATED_AB_LIMIT[target]:
        errors.append("direct_related_survey_ab_over_limit")
    support = topic_relevance_support(audit_rows, citation_plan, raw_candidates, papers)
    if support["related_surveys"] < TARGETS[target]["related_surveys"]:
        errors.append("related_survey_relevance_failed")

    summary = {
        "audit_count": len(audit_rows),
        "raw_candidate_count": len(raw_ids),
        "retained_paper_count": len(retained_ids),
        "ab_count": len(ab_depths),
        "invalid_ab_count": len(sorted(set(invalid_ab))),
        "core_ab_count": len(core_ab),
        "direct_related_ab_count": len(direct_ab),
        "related_survey_count": support["related_surveys"],
        "verified_related_survey_count": support["verified_related_surveys"],
        "all_related_survey_count": support["all_related_surveys"],
        "grade_counts": dict(Counter(str(row.get("relevance_grade") or "") for row in audit_rows)),
        "family_support": support["core_family_support"],
    }
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "schema_errors": sorted(set(schema_errors)),
        "missing_raw_candidate_audits": missing_raw[:50],
        "missing_retained_paper_audits": missing_retained[:50],
        "missing_ab_paper_audits": missing_ab[:50],
        "invalid_ab_paper_ids": sorted(set(invalid_ab)),
        "direct_related_ab_paper_ids": sorted(direct_ab),
        "core_ab_paper_ids": sorted(core_ab),
        "second_audit_required_paper_ids": sorted(set(second_audit_required)),
        "second_audit_trigger_reasons_by_paper": {pid: second_audit_reasons[pid] for pid in sorted(second_audit_reasons)},
        "secondary_audit_errors": sorted(set(secondary_audit_errors)),
        "support": support,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-candidates", required=True, type=Path)
    parser.add_argument("--papers", required=True, type=Path)
    parser.add_argument("--citation-plan", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--second-audits", type=Path)
    parser.add_argument("--survey-type-plan", type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    result = validate_topic_relevance(
        read_jsonl(args.raw_candidates),
        read_jsonl(args.papers),
        read_jsonl(args.citation_plan),
        read_jsonl(args.audit),
        args.survey_type_plan.read_text(encoding="utf-8") if args.survey_type_plan and args.survey_type_plan.exists() else "",
        args.target,
        secondary_audits=read_jsonl(args.second_audits) if args.second_audits and args.second_audits.exists() else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
