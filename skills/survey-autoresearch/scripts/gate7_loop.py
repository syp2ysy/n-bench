#!/usr/bin/env python3
"""Manage Gate 7 expert-review loop state without fabricating reviewer output."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import REQUIRED_REVIEWERS, freeze_review_round, read_json, read_jsonl, write_json, write_jsonl
    from .expert_review_gate import REQUIRED_DIMENSIONS, REQUIRED_PERSONAS, ROUTE_EVIDENCE_REQUIREMENTS, VALID_ROUTES
    from .status_schema import STATUS_SCHEMA_VERSION, status_envelope
except ImportError:  # pragma: no cover
    from run_expert_reviews import REQUIRED_REVIEWERS, freeze_review_round, read_json, read_jsonl, write_json, write_jsonl
    from expert_review_gate import REQUIRED_DIMENSIONS, REQUIRED_PERSONAS, ROUTE_EVIDENCE_REQUIREMENTS, VALID_ROUTES
    from status_schema import STATUS_SCHEMA_VERSION, status_envelope


REVIEW_INPUTS = [
    "outputs/survey_candidate.md",
    "outputs/appendix.md",
    "state/paper_mechanism_cards.jsonl",
    "state/claim_evidence_spans.jsonl",
    "outputs/contribution_tree.yml",
    "state/taxonomy_alignment.jsonl",
    "state/argument_graph.yml",
    "state/section_evidence_plans.jsonl",
]

FORBIDDEN_INPUTS = [
    "previous reviewer reports",
    "state/expert_review_reports.jsonl",
    "repair actions from this round",
    "state/repair_actions.jsonl",
]

PERSONA_AUDIT_FIELDS = {
    "Domain Expert Reviewer": "paper_mechanism_audits",
    "Survey Architect Reviewer": "flow_taxonomy_audit",
    "Evidence/Factuality Reviewer": "claim_citation_audits",
    "Newcomer/Tutorial Reviewer": "tutorial_audit",
    "Style/Publication Reviewer": "style_audit",
}

ADJUDICATION_SCHEMA_VERSION = 2
ROUND_ARCHIVE_FILES = [
    "expert_review_reports.jsonl",
    "expert_review_invocations.jsonl",
    "expert_review_adjudication.json",
    "repair_actions.jsonl",
    "regression_checks.jsonl",
    "targeted_rereview_reports.jsonl",
    "gate7_repair_plan.json",
    "gate7_repair_batches.json",
    "gate7_repair_results.jsonl",
    "gate7_driver_history.jsonl",
    "gate7_regression_requests.jsonl",
    "gate7_runtime_action.json",
    "gate7_spawn_requests.json",
]


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _reports_hash(reports: list[dict]) -> str:
    payload = json.dumps(reports, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _nonempty_file(path: Path) -> bool:
    return path.exists() and path.read_text(encoding="utf-8").strip() != ""


def _release_manifest_fresh(task_dir: Path, manifest: dict) -> bool:
    outputs = task_dir / "outputs"
    candidate_md = outputs / "survey_candidate.md"
    final_md = outputs / "survey.md"
    final_html = outputs / "survey.html"
    return (
        manifest.get("released") is True
        and str(manifest.get("released_at") or "").strip() != ""
        and str(manifest.get("gate_check_hash") or "").strip() != ""
        and _nonempty_file(final_md)
        and _nonempty_file(final_html)
        and str(manifest.get("candidate_hash") or "") == _sha256_file(candidate_md)
        and str(manifest.get("survey_hash") or "") == _sha256_file(final_md)
        and str(manifest.get("survey_html_hash") or "") == _sha256_file(final_html)
    )


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _route_required_evidence(route: str) -> set[str]:
    return set(ROUTE_EVIDENCE_REQUIREMENTS.get(route, {"section_evidence_plans"}))


def _required_evidence(route: str, requested) -> list[str]:
    values = set()
    if isinstance(requested, list):
        values.update(str(item) for item in requested if str(item).strip())
    elif isinstance(requested, str) and requested.strip():
        values.add(requested.strip())
    values.update(_route_required_evidence(route))
    return sorted(values)


def _major_source_ids(reports: list[dict]) -> set[str]:
    source_ids: set[str] = set()
    for report in reports:
        reviewer_id = str(report.get("reviewer_id") or "").strip()
        for idx, weakness in enumerate(report.get("blocking_weaknesses") or [], start=1):
            if not isinstance(weakness, dict):
                continue
            if str(weakness.get("severity") or "").lower() not in {"major", "blocking"}:
                continue
            local_id = str(weakness.get("weakness_id") or f"W{idx}").strip()
            if reviewer_id and local_id:
                source_ids.add(f"{reviewer_id}:{local_id}")
            elif local_id:
                source_ids.add(local_id)
    return source_ids


def _empty_adjudication(review_round_id: str | None = None) -> dict:
    return {
        "schema_version": ADJUDICATION_SCHEMA_VERSION,
        "review_round_id": review_round_id,
        "review_reports_hash": "",
        "adjudicated_at": None,
        "all_major_weaknesses_adjudicated": False,
        "canonical_weaknesses": [],
    }


def _needs_adjudication_rebuild(reports: list[dict], adjudication: dict) -> bool:
    reported_source_ids = _major_source_ids(reports)
    if not reported_source_ids:
        return False
    canonical = adjudication.get("canonical_weaknesses")
    if not isinstance(canonical, list) or not canonical:
        return True
    if adjudication.get("schema_version") != ADJUDICATION_SCHEMA_VERSION:
        return True
    if str(adjudication.get("review_reports_hash") or "") != _reports_hash(reports):
        return True
    covered_source_ids: set[str] = set()
    for item in canonical:
        if not isinstance(item, dict):
            return True
        weakness_id = str(item.get("weakness_id") or "")
        if not re.fullmatch(r"CW\d{3}", weakness_id):
            return True
        route = str(item.get("route_to") or "article_quality")
        required = set(str(value) for value in item.get("required_evidence_check") or [])
        if not _route_required_evidence(route) <= required:
            return True
        source_ids = [str(value) for value in item.get("source_weakness_ids") or [] if str(value).strip()]
        if not source_ids or any(":" not in source_id for source_id in source_ids):
            return True
        covered_source_ids.update(source_ids)
    return not reported_source_ids <= covered_source_ids


def _ensure_round(task_dir: Path, review_round_id: str | None = None) -> dict:
    status = read_json(_state(task_dir) / "expert_review_round_status.json")
    if not status.get("review_freeze"):
        status = freeze_review_round(task_dir, review_round_id)
    return status


def _score(value) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if 0 <= score <= 10 else None


def _reviewer_schema_text() -> str:
    dimensions = ", ".join(sorted(REQUIRED_DIMENSIONS))
    routes = ", ".join(sorted(VALID_ROUTES))
    return (
        "JSON schema requirements:\n"
        "- Root object keys: reviewer_id, persona, overall_score, pass_recommendation, "
        "dimension_scores, dimension_audits, review_trace, sections_reviewed, "
        "section_comments, quoted_evidence_from_review, blocking_weaknesses, and the "
        "persona-specific audit field.\n"
        f"- dimension_scores is an object with exactly these legal dimension keys: {dimensions}.\n"
        "- dimension_audits is a list with one object per dimension. Each object needs: "
        "dimension, score, verdict, evidence_quotes, failure_cases, why_it_matters, "
        "repair_recommendation, route_to.\n"
        f"- Legal route_to values are: {routes}.\n"
        "- blocking_weaknesses is a list. Each weakness object needs: weakness_id, severity "
        "(minor, major, or blocking), evidence_quote, why_it_matters, route_to, repair_action, "
        "affected_sections, affected_papers, affected_claims, and optional required_evidence_check. "
        "affected_papers and affected_claims may be empty lists for article/style issues but the "
        "keys must be present.\n"
        "- Persona-specific audit field: Domain Expert Reviewer -> paper_mechanism_audits; "
        "Survey Architect Reviewer -> flow_taxonomy_audit; Evidence/Factuality Reviewer -> "
        "claim_citation_audits; Newcomer/Tutorial Reviewer -> tutorial_audit; "
        "Style/Publication Reviewer -> style_audit.\n"
        "- Before returning, check that the JSON object follows this schema. Return JSON only."
    )


def _reviewer_prompt(task_dir: Path, round_id: str, reviewer_id: str, persona: str) -> str:
    return (
        "You are an independent Gate 7 reviewer for survey-autoresearch.\n"
        "Use a fresh context. Do not read previous reviewer reports or repair actions.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Reviewer id: {reviewer_id}\n"
        f"Persona: {persona}\n"
        f"Review round id: {round_id}\n"
        "Allowed inputs:\n"
        + "\n".join(f"- {path}" for path in REVIEW_INPUTS)
        + "\n\nReturn exactly one JSON object suitable for one line of "
        "state/expert_review_reports.jsonl. Include reviewer_id, persona, overall_score, "
        "pass_recommendation, dimension_scores, dimension_audits, review_trace, "
        "sections_reviewed, section_comments, quoted_evidence_from_review, "
        "blocking_weaknesses, and the persona-specific audit required by "
        "references/expert_gate_contract.md. Do not use markdown.\n\n"
        + _reviewer_schema_text()
    )


def precheck_review_report(report: dict) -> dict:
    errors: list[str] = []
    if not isinstance(report, dict):
        return {"status": "invalid", "errors": ["report_not_object"]}
    reviewer_id = str(report.get("reviewer_id") or "").strip()
    persona = str(report.get("persona") or "").strip()
    if not reviewer_id:
        errors.append("missing_reviewer_id")
    if persona not in REQUIRED_PERSONAS:
        errors.append("invalid_persona")
    if _score(report.get("overall_score")) is None:
        errors.append("invalid_overall_score")
    if not isinstance(report.get("pass_recommendation"), bool):
        errors.append("invalid_pass_recommendation")
    dimensions = report.get("dimension_scores")
    if not isinstance(dimensions, dict):
        errors.append("missing_dimension_scores")
    else:
        missing = sorted(REQUIRED_DIMENSIONS - set(dimensions))
        if missing:
            errors.append("missing_dimension_scores:" + ",".join(missing))
        invalid = sorted(name for name, value in dimensions.items() if _score(value) is None)
        if invalid:
            errors.append("invalid_dimension_scores:" + ",".join(invalid))
    audits = report.get("dimension_audits")
    if not isinstance(audits, list):
        errors.append("missing_dimension_audits")
    else:
        audit_dims = set()
        for idx, audit in enumerate(audits, start=1):
            if not isinstance(audit, dict):
                errors.append(f"invalid_dimension_audit:{idx}")
                continue
            dim = str(audit.get("dimension") or "").strip().lower().replace(" ", "_").replace("/", "_")
            if dim:
                audit_dims.add(dim)
            if dim not in REQUIRED_DIMENSIONS:
                errors.append(f"invalid_dimension_audit_dimension:{idx}")
            if _score(audit.get("score")) is None:
                errors.append(f"invalid_dimension_audit_score:{idx}")
            if str(audit.get("route_to") or "") not in VALID_ROUTES:
                errors.append(f"invalid_dimension_audit_route:{idx}")
            for field in ["verdict", "evidence_quotes", "why_it_matters", "repair_recommendation"]:
                if not audit.get(field):
                    errors.append(f"missing_dimension_audit_{field}:{idx}")
        missing_audits = sorted(REQUIRED_DIMENSIONS - audit_dims)
        if missing_audits:
            errors.append("missing_dimension_audits:" + ",".join(missing_audits))
    weaknesses = report.get("blocking_weaknesses")
    if not isinstance(weaknesses, list):
        errors.append("invalid_blocking_weaknesses")
    else:
        for idx, weakness in enumerate(weaknesses, start=1):
            if not isinstance(weakness, dict):
                errors.append(f"invalid_blocking_weakness:{idx}")
                continue
            for field in ["weakness_id", "severity", "evidence_quote", "why_it_matters", "route_to", "repair_action"]:
                if not str(weakness.get(field) or "").strip():
                    errors.append(f"missing_weakness_{field}:{idx}")
            if str(weakness.get("route_to") or "") not in VALID_ROUTES:
                errors.append(f"invalid_weakness_route:{idx}")
            for field in ["affected_sections", "affected_papers", "affected_claims"]:
                if field not in weakness:
                    errors.append(f"missing_weakness_{field}:{idx}")
                elif not isinstance(weakness.get(field), list):
                    errors.append(f"invalid_weakness_{field}:{idx}")
    persona_field = PERSONA_AUDIT_FIELDS.get(persona)
    if persona_field and not report.get(persona_field):
        errors.append(f"missing_persona_audit:{persona_field}")
    return {"status": "invalid" if errors else "valid", "errors": sorted(set(errors))}


def make_reviewer_prompts(task_dir: Path, review_round_id: str | None = None) -> dict:
    status = _ensure_round(task_dir, review_round_id)
    round_id = str(status.get("review_round_id") or review_round_id or "round-1")
    prompts = []
    invocations = []
    for reviewer_id, persona in REQUIRED_REVIEWERS:
        prompts.append(
            {
                "review_round_id": round_id,
                "reviewer_id": reviewer_id,
                "persona": persona,
                "agent_type": "explorer",
                "fork_context": False,
                "message": _reviewer_prompt(task_dir, round_id, reviewer_id, persona),
            }
        )
        invocations.append(
            {
                "review_round_id": round_id,
                "reviewer_id": reviewer_id,
                "persona": persona,
                "fresh_context": False,
                "subagent_session_id": "",
                "inputs": REVIEW_INPUTS,
                "forbidden_inputs": FORBIDDEN_INPUTS,
                "output": "state/expert_review_reports.jsonl",
                "status": "ready_to_spawn",
            }
        )
    write_jsonl(_state(task_dir) / "expert_review_invocations.jsonl", invocations)
    return {
        "status": "ready_to_spawn",
        "execution_note": "Main agent must call multi_agent_v1.spawn_agent with fork_context=false for each reviewer prompt.",
        "review_round_id": round_id,
        "reviewer_prompts": prompts,
    }


def record_review_report(task_dir: Path, report: dict, subagent_session_id: str) -> dict:
    precheck = precheck_review_report(report)
    if precheck["status"] != "valid":
        return {"status": "invalid", "error": "invalid_review_report", "precheck": precheck}
    state = _state(task_dir)
    status = _ensure_round(task_dir)
    round_id = str(status.get("review_round_id") or report.get("review_round_id") or "round-1")
    reviewer_id = str(report.get("reviewer_id") or "").strip()
    persona = str(report.get("persona") or "").strip()
    if not reviewer_id or not persona:
        return {"status": "invalid", "error": "missing_reviewer_id_or_persona"}
    reports = [row for row in read_jsonl(state / "expert_review_reports.jsonl") if str(row.get("reviewer_id") or "") != reviewer_id]
    reports.append(report)
    write_jsonl(state / "expert_review_reports.jsonl", reports)
    invocations = read_jsonl(state / "expert_review_invocations.jsonl")
    by_id = {str(item.get("reviewer_id") or ""): dict(item) for item in invocations}
    invocation = by_id.get(reviewer_id, {})
    invocation.update(
        {
            "review_round_id": round_id,
            "reviewer_id": reviewer_id,
            "persona": persona,
            "fresh_context": True,
            "subagent_session_id": subagent_session_id,
            "inputs": REVIEW_INPUTS,
            "forbidden_inputs": FORBIDDEN_INPUTS,
            "output": "state/expert_review_reports.jsonl",
            "status": "returned",
        }
    )
    by_id[reviewer_id] = invocation
    ordered = [by_id.get(reviewer_id, {}) for reviewer_id, _ in REQUIRED_REVIEWERS if reviewer_id in by_id]
    write_jsonl(state / "expert_review_invocations.jsonl", ordered)
    returned = len({str(row.get("reviewer_id") or "") for row in reports})
    status["reviewers_returned"] = returned
    status["all_reports_received"] = returned >= len(REQUIRED_REVIEWERS)
    status["status"] = "all_reports_received" if status["all_reports_received"] else "collecting_reviews"
    status.pop("expert_review_blocked_by_unavailable_independent_review", None)
    write_json(state / "expert_review_round_status.json", status)
    return {"status": "recorded", "reviewer_id": reviewer_id, "reviewers_returned": returned}


def adjudicate_reports(task_dir: Path) -> dict:
    state = _state(task_dir)
    reports = read_jsonl(state / "expert_review_reports.jsonl")
    status = read_json(state / "expert_review_round_status.json")
    canonical_by_key: dict[tuple, dict] = {}
    for report in reports:
        reviewer_id = str(report.get("reviewer_id") or "")
        for idx, weakness in enumerate(report.get("blocking_weaknesses") or [], start=1):
            if not isinstance(weakness, dict):
                continue
            severity = str(weakness.get("severity") or "").lower()
            if severity not in {"major", "blocking"}:
                continue
            local_id = str(weakness.get("weakness_id") or f"W{idx}").strip()
            source_id = f"{reviewer_id}:{local_id}" if reviewer_id else local_id
            route = str(weakness.get("route_to") or "article_quality")
            affected_sections = list(weakness.get("affected_sections") or ["article"])
            affected_papers = list(weakness.get("affected_papers") or [])
            affected_claims = list(weakness.get("affected_claims") or [])
            repair_key = re.sub(r"\s+", " ", str(weakness.get("repair_action") or weakness.get("repair_acceptance_criteria") or "").lower()).strip()[:120]
            cluster_key = (
                route,
                tuple(sorted(str(item) for item in affected_sections)),
                tuple(sorted(str(item) for item in affected_papers)),
                tuple(sorted(str(item) for item in affected_claims)),
                repair_key,
            )
            canonical_id = f"CW{len(canonical_by_key) + 1:03d}"
            required = _required_evidence(route, weakness.get("required_evidence_check"))
            item = canonical_by_key.setdefault(
                cluster_key,
                {
                    "weakness_id": canonical_id,
                    "severity": severity,
                    "source_reviewers": [],
                    "source_weakness_ids": [],
                    "affected_sections": affected_sections,
                    "affected_papers": affected_papers,
                    "affected_claims": affected_claims,
                    "route_to": route,
                    "required_evidence_check": required,
                    "repair_acceptance_criteria": weakness.get("repair_acceptance_criteria") or weakness.get("repair_action") or "The weakness is resolved without unsupported claims.",
                },
            )
            if severity == "blocking":
                item["severity"] = "blocking"
            if reviewer_id and reviewer_id not in item["source_reviewers"]:
                item["source_reviewers"].append(reviewer_id)
            if source_id not in item["source_weakness_ids"]:
                item["source_weakness_ids"].append(source_id)
            for field, values in [("affected_sections", affected_sections), ("affected_papers", affected_papers), ("affected_claims", affected_claims)]:
                merged = list(item.get(field) or [])
                for value in values:
                    if value not in merged:
                        merged.append(value)
                item[field] = merged
            merged_required = list(item.get("required_evidence_check") or [])
            for value in required:
                if value not in merged_required:
                    merged_required.append(value)
            item["required_evidence_check"] = sorted(merged_required)
    adjudication = {
        "schema_version": ADJUDICATION_SCHEMA_VERSION,
        "review_round_id": status.get("review_round_id") or "round-1",
        "review_reports_hash": _reports_hash(reports),
        "adjudicated_at": _utc_now(),
        "all_major_weaknesses_adjudicated": True,
        "canonical_weaknesses": list(canonical_by_key.values()),
    }
    write_json(state / "expert_review_adjudication.json", adjudication)
    return {**adjudication, "canonical_weakness_count": len(canonical_by_key)}


def _canonical_weakness_id(task_dir: Path, weakness_id: str) -> str:
    adjudication = read_json(_state(task_dir) / "expert_review_adjudication.json")
    matches = []
    for weakness in adjudication.get("canonical_weaknesses") or []:
        canonical_id = str(weakness.get("weakness_id") or "")
        source_ids = [str(value) for value in weakness.get("source_weakness_ids") or []]
        if weakness_id == canonical_id or weakness_id in source_ids or any(source_id.split(":", 1)[-1] == weakness_id for source_id in source_ids):
            matches.append(canonical_id)
    return matches[0] if len(set(matches)) == 1 else weakness_id


def record_repair_action(task_dir: Path, repair: dict) -> dict:
    weakness_id = str(repair.get("weakness_id") or "").strip()
    if not weakness_id:
        return {"status": "invalid", "error": "missing_weakness_id"}
    weakness_id = _canonical_weakness_id(task_dir, weakness_id)
    repair = {**repair, "weakness_id": weakness_id}
    missing = [
        field for field in ["evidence_rechecked", "changed_artifacts", "repair_action", "status"]
        if not repair.get(field)
    ]
    if missing:
        return {"status": "invalid", "error": "missing_" + ",".join(missing)}
    evidence = repair.get("evidence_rechecked")
    if not isinstance(evidence, list) or not evidence:
        return {"status": "invalid", "error": "missing_evidence_rechecked"}
    if any(not isinstance(item, dict) or item.get("supports_repair") is not True for item in evidence):
        return {"status": "invalid", "error": "invalid_evidence_rechecked"}
    state = _state(task_dir)
    repairs = [row for row in read_jsonl(state / "repair_actions.jsonl") if str(row.get("weakness_id") or "") != weakness_id]
    repairs.append(repair)
    status = _ensure_round(task_dir)
    repaired_hash = _sha256_file(task_dir / "outputs" / "survey_candidate.md")
    frozen_hash = str(((status.get("review_freeze") or {}).get("article_hash")) or "")
    if not repaired_hash:
        return {"status": "invalid", "error": "missing_survey_candidate_md"}
    if frozen_hash and repaired_hash == frozen_hash:
        return {"status": "invalid", "error": "repair_did_not_change_candidate"}
    write_jsonl(state / "repair_actions.jsonl", repairs)
    status["repaired_article_hash"] = repaired_hash
    write_json(state / "expert_review_round_status.json", status)
    return {"status": "recorded", "weakness_id": weakness_id, "repaired_article_hash": repaired_hash}


def record_regression_check(task_dir: Path, check: dict) -> dict:
    weakness_id = str(check.get("weakness_id") or "").strip()
    if not weakness_id:
        return {"status": "invalid", "error": "missing_weakness_id"}
    weakness_id = _canonical_weakness_id(task_dir, weakness_id)
    check = {**check, "weakness_id": weakness_id}
    missing = [field for field in ["status", "command", "result"] if not check.get(field)]
    if missing:
        return {"status": "invalid", "error": "missing_" + ",".join(missing)}
    state = _state(task_dir)
    checks = [row for row in read_jsonl(state / "regression_checks.jsonl") if str(row.get("weakness_id") or "") != weakness_id]
    checks.append(check)
    write_jsonl(state / "regression_checks.jsonl", checks)
    return {"status": "recorded", "weakness_id": weakness_id, "check_status": check.get("status")}


def _resolved_weakness_ids(rows: list[dict]) -> set[str]:
    return {
        str(row.get("weakness_id") or "")
        for row in rows
        if str(row.get("weakness_id") or "") and str(row.get("verdict") or "") == "resolved"
    }


def _targeted_prompt(weakness: dict, repair: dict, round_id: str) -> str:
    weakness_id = str(weakness.get("weakness_id") or "")
    return (
        "You are a targeted Gate 7 rereviewer for survey-autoresearch.\n"
        "Use a fresh context. Check only the assigned repaired weakness, the changed artifacts, "
        "and the evidence refs named in the repair action. Do not read previous reviewer reports "
        "except the canonical weakness and repair record provided here.\n"
        f"Review round id: {round_id}\n"
        f"Weakness id: {weakness_id}\n"
        f"Canonical weakness: {json.dumps(weakness, ensure_ascii=False, sort_keys=True)}\n"
        f"Repair action: {json.dumps(repair, ensure_ascii=False, sort_keys=True)}\n"
        "Return exactly one JSON object for state/targeted_rereview_reports.jsonl with: "
        "weakness_id, reviewer_id, persona, checked_changed_artifacts, checked_evidence_refs, "
        "verdict, evidence_quote_after_repair, remaining_risk, and article_hash. Verdict must be "
        "resolved, still_unresolved, or introduced_regression. Do not use markdown."
    )


def make_targeted_rereview_prompts(task_dir: Path) -> dict:
    state = _state(task_dir)
    status = read_json(state / "expert_review_round_status.json")
    adjudication = read_json(state / "expert_review_adjudication.json")
    repairs = read_jsonl(state / "repair_actions.jsonl")
    rereviews = read_jsonl(state / "targeted_rereview_reports.jsonl")
    repairs_by_id = {str(row.get("weakness_id") or ""): row for row in repairs if row.get("weakness_id")}
    resolved_ids = _resolved_weakness_ids(rereviews)
    prompts = []
    for weakness in adjudication.get("canonical_weaknesses") or []:
        weakness_id = str(weakness.get("weakness_id") or "")
        if not weakness_id or weakness_id in resolved_ids:
            continue
        repair = repairs_by_id.get(weakness_id)
        if not repair:
            continue
        prompts.append(
            {
                "review_round_id": status.get("review_round_id") or adjudication.get("review_round_id") or "round-1",
                "weakness_id": weakness_id,
                "agent_type": "explorer",
                "fork_context": False,
                "message": _targeted_prompt(weakness, repair, str(status.get("review_round_id") or "round-1")),
            }
        )
    return {
        "status": "ready_to_spawn" if prompts else "no_targeted_rereviews_needed",
        "next_action": "spawn_targeted_rereviewers" if prompts else "rerun_gate_check",
        "targeted_rereview_prompts": prompts,
    }


def record_targeted_rereview(task_dir: Path, report: dict, subagent_session_id: str) -> dict:
    weakness_id = str(report.get("weakness_id") or "").strip()
    if not weakness_id:
        return {"status": "invalid", "error": "missing_weakness_id"}
    weakness_id = _canonical_weakness_id(task_dir, weakness_id)
    row = {**report, "weakness_id": weakness_id}
    row["fresh_context"] = True
    row["subagent_session_id"] = subagent_session_id
    rows = [item for item in read_jsonl(_state(task_dir) / "targeted_rereview_reports.jsonl") if str(item.get("weakness_id") or "") != weakness_id]
    rows.append(row)
    write_jsonl(_state(task_dir) / "targeted_rereview_reports.jsonl", rows)
    return {"status": "recorded", "weakness_id": weakness_id}


def _all_canonical_weaknesses_repaired(adjudication: dict, repairs: list[dict]) -> bool:
    needed = {
        str(item.get("weakness_id") or "")
        for item in adjudication.get("canonical_weaknesses") or []
        if str(item.get("weakness_id") or "")
    }
    repaired = {
        str(item.get("weakness_id") or "")
        for item in repairs
        if str(item.get("status") or "").lower() in {"resolved", "accepted limitation", "accepted_limitation"}
    }
    return bool(needed) and needed <= repaired


def _candidate_changed_since_plan(task_dir: Path, plan: dict) -> bool:
    planned_hash = str(plan.get("candidate_hash") or "")
    current_hash = _sha256_file(task_dir / "outputs" / "survey_candidate.md")
    return bool(planned_hash and current_hash and planned_hash != current_hash)


def reset_gate7_round_for_full_rerun(task_dir: Path) -> dict:
    state = _state(task_dir)
    status = read_json(state / "expert_review_round_status.json")
    adjudication = read_json(state / "expert_review_adjudication.json")
    plan = read_json(state / "gate7_repair_plan.json")
    round_id = str(status.get("review_round_id") or adjudication.get("review_round_id") or plan.get("review_round_id") or "round-1")
    candidate_hash = _sha256_file(task_dir / "outputs" / "survey_candidate.md")
    archive_root = state / "gate7_rounds"
    archive_root.mkdir(exist_ok=True)
    safe_round = re.sub(r"[^A-Za-z0-9_.-]+", "-", round_id).strip("-") or "round"
    archive = archive_root / f"{safe_round}-{candidate_hash[:12] or 'nohash'}"
    suffix = 2
    while archive.exists():
        archive = archive_root / f"{safe_round}-{candidate_hash[:12] or 'nohash'}-{suffix}"
        suffix += 1
    archive.mkdir(parents=True)
    for filename in ROUND_ARCHIVE_FILES:
        path = state / filename
        if path.exists():
            (archive / filename).write_bytes(path.read_bytes())
    write_json(
        archive / "archive_manifest.json",
        {
            "archived_at": _utc_now(),
            "review_round_id": round_id,
            "candidate_hash_after_repair": candidate_hash,
            "reason": "full_gate7_round",
        },
    )
    for filename in [
        "expert_review_reports.jsonl",
        "expert_review_invocations.jsonl",
        "repair_actions.jsonl",
        "regression_checks.jsonl",
        "targeted_rereview_reports.jsonl",
        "gate7_repair_results.jsonl",
        "gate7_driver_history.jsonl",
        "gate7_regression_requests.jsonl",
    ]:
        (state / filename).write_text("", encoding="utf-8")
    write_json(state / "expert_review_adjudication.json", _empty_adjudication(None))
    write_json(
        state / "expert_review_round_status.json",
        {
            "review_round_id": None,
            "status": "not_started",
            "review_freeze": {},
            "all_reports_received": False,
            "reviewers_expected": len(REQUIRED_REVIEWERS),
            "reviewers_returned": 0,
            "repaired_article_hash": None,
            "previous_review_round_id": round_id,
            "previous_round_archive": str(archive),
        },
    )
    write_json(
        state / "gate7_repair_plan.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "review_round_id": None,
            "candidate_hash": None,
            "major_rebuild_required": False,
            "rerun_policy": None,
            "repair_items": [],
            "summary": {
                "repair_item_count": 0,
                "rollback_phase_counts": {},
                "first_rollback_phase": None,
                "route_counts": {},
                "rerun_policy": None,
                "major_rebuild_required": False,
            },
        },
    )
    runtime_summary = {
        "batch_count": 0,
        "active_batch_id": None,
        "active_rollback_phase": None,
        "pending_batch_count": 0,
        "resolved_batch_count": 0,
        "rerun_policy": None,
        "major_rebuild_required": False,
    }
    write_json(
        state / "gate7_runtime_action.json",
        {
            **status_envelope(
                "gate7_runtime_executor",
                "full_reround_prepared",
                next_action="freeze",
                terminal=False,
                blocked=False,
                active_batch_id=None,
                summary=runtime_summary,
            ),
            "status": "full_reround_prepared",
            "next_action": "freeze",
            "previous_review_round_id": round_id,
            "previous_round_archive": str(archive),
            "candidate_hash": candidate_hash,
        },
    )
    write_json(
        state / "gate7_repair_batches.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "active_batch_id": None,
            "batches": [],
            "summary": runtime_summary,
        },
    )
    write_json(state / "gate7_spawn_requests.json", {"next_action": None, "spawn_requests": []})
    return {
        "status": "full_reround_prepared",
        "next_action": "freeze",
        "archive_dir": str(archive),
        "candidate_hash": candidate_hash,
    }


def collect_gate7_status(task_dir: Path) -> dict:
    state = _state(task_dir)
    reports = read_jsonl(state / "expert_review_reports.jsonl")
    status = read_json(state / "expert_review_round_status.json")
    adjudication = read_json(state / "expert_review_adjudication.json")
    repair_plan = read_json(state / "gate7_repair_plan.json")
    repair_batches = read_json(state / "gate7_repair_batches.json")
    iteration_status = read_json(state / "review_iteration_status.json")
    repairs = read_jsonl(state / "repair_actions.jsonl")
    regression_checks = read_jsonl(state / "regression_checks.jsonl")
    rereviews = read_jsonl(state / "targeted_rereview_reports.jsonl")
    release_manifest = read_json(task_dir / "outputs" / "release_manifest.json")
    gate_summary = read_json(state / "gate_check_full.json")
    current_candidate_hash = _sha256_file(task_dir / "outputs" / "survey_candidate.md")
    gate_fresh = (
        gate_summary.get("release_allowed") is True
        and gate_summary.get("all_blocking_gates_passed") is True
        and str(gate_summary.get("generated_at") or "").strip()
        and str(gate_summary.get("candidate_hash") or "") == current_candidate_hash
    )
    if _release_manifest_fresh(task_dir, release_manifest):
        next_action = "complete"
    elif str(iteration_status.get("status") or "") == "quality_limited" and not gate_fresh:
        next_action = "quality_limited_stop"
    elif gate_fresh:
        next_action = "promote_release"
    elif not status.get("review_freeze"):
        next_action = "freeze"
    elif not reports:
        next_action = "spawn_reviewers"
    elif len(reports) < len(REQUIRED_REVIEWERS):
        next_action = "wait_all_reports"
    elif _needs_adjudication_rebuild(reports, adjudication):
        next_action = "adjudicate"
    elif not adjudication.get("canonical_weaknesses") and any(row.get("blocking_weaknesses") for row in reports):
        next_action = "adjudicate"
    elif repair_batches.get("batches") and not all(batch.get("status") == "resolved" for batch in repair_batches.get("batches") or []):
        next_action = "spawn_repair_agents"
    elif adjudication.get("canonical_weaknesses") and not repairs:
        next_action = "repair_with_evidence"
    elif (
        repair_plan.get("rerun_policy") == "full_gate7_round"
        and repairs
        and adjudication.get("canonical_weaknesses")
    ):
        if not _all_canonical_weaknesses_repaired(adjudication, repairs) or not _all_repaired_weaknesses_have_passing_checks(adjudication, regression_checks):
            next_action = "run_regression_checks"
        elif _candidate_changed_since_plan(task_dir, repair_plan):
            next_action = "reset_full_review_round"
        else:
            next_action = "repair_with_evidence"
    elif repairs and adjudication.get("canonical_weaknesses") and not _all_repaired_weaknesses_have_passing_checks(adjudication, regression_checks):
        next_action = "run_regression_checks"
    elif repairs and not rereviews:
        next_action = "spawn_targeted_rereviewers"
    elif repairs and adjudication.get("canonical_weaknesses"):
        unresolved = [
            item for item in adjudication.get("canonical_weaknesses") or []
            if str(item.get("weakness_id") or "") not in _resolved_weakness_ids(rereviews)
        ]
        next_action = "spawn_targeted_rereviewers" if unresolved else "rerun_gate_check"
    else:
        next_action = "rerun_gate_check"
    return {
        "status": status.get("status") or "unknown",
        "reviewers_returned": len({str(row.get("reviewer_id") or "") for row in reports}),
        "reviewers_expected": len(REQUIRED_REVIEWERS),
        "next_action": next_action,
    }


def _all_repaired_weaknesses_have_passing_checks(adjudication: dict, checks: list[dict]) -> bool:
    needed = {
        str(item.get("weakness_id") or "")
        for item in adjudication.get("canonical_weaknesses") or []
        if str(item.get("weakness_id") or "")
    }
    passed = {
        str(item.get("weakness_id") or "")
        for item in checks
        if str(item.get("status") or "").lower() == "passed"
    }
    return bool(needed) and needed <= passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--review-round-id")
    parser.add_argument("--make-reviewer-prompts", action="store_true")
    parser.add_argument("--record-review", type=Path)
    parser.add_argument("--precheck-review", type=Path)
    parser.add_argument("--subagent-session-id")
    parser.add_argument("--collect-status", action="store_true")
    parser.add_argument("--adjudicate", action="store_true")
    parser.add_argument("--make-targeted-rereview-prompts", action="store_true")
    parser.add_argument("--record-repair", type=Path)
    parser.add_argument("--record-regression-check", type=Path)
    parser.add_argument("--record-targeted-rereview", type=Path)
    args = parser.parse_args()
    if args.make_reviewer_prompts:
        result = make_reviewer_prompts(args.task_dir, args.review_round_id)
    elif args.precheck_review:
        result = precheck_review_report(json.loads(args.precheck_review.read_text(encoding="utf-8")))
    elif args.record_review:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_review_report(args.task_dir, json.loads(args.record_review.read_text(encoding="utf-8")), args.subagent_session_id)
    elif args.adjudicate:
        result = adjudicate_reports(args.task_dir)
    elif args.make_targeted_rereview_prompts:
        result = make_targeted_rereview_prompts(args.task_dir)
    elif args.record_repair:
        result = record_repair_action(args.task_dir, json.loads(args.record_repair.read_text(encoding="utf-8")))
    elif args.record_regression_check:
        result = record_regression_check(args.task_dir, json.loads(args.record_regression_check.read_text(encoding="utf-8")))
    elif args.record_targeted_rereview:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_targeted_rereview(args.task_dir, json.loads(args.record_targeted_rereview.read_text(encoding="utf-8")), args.subagent_session_id)
    elif args.collect_status:
        result = collect_gate7_status(args.task_dir)
    else:
        result = {"status": "invalid", "error": "choose an action"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
