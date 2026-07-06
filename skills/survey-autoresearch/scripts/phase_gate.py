#!/usr/bin/env python3
"""Evaluate phase barriers for survey-autoresearch runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .build_contribution_tree import validate_contribution_tree
    from .expert_review_gate import read_json as read_json_file, validate_expert_reviews
    from .validate_argument_graph import parse_structured_text, validate_argument_graph
    from .validate_article_quality import validate_article_quality
    from .validate_claim_evidence import validate_claim_evidence
    from .validate_coverage import read_json, read_jsonl, validate_coverage
    from .validate_paper_understanding import validate_paper_understanding
    from .validate_scenario_definitions import validate_scenario_definitions
    from .validate_section_evidence_plans import validate_section_evidence_plans
    from .validate_synthesis_dossiers import read_dossier_dir, validate_synthesis_dossiers
    from .validate_exemplar_alignment import validate_exemplar_alignment
    from .validate_related_survey_alignment import validate_related_survey_alignment
    from .verify_sources import validate_sources
    from .validate_topic_profile import validate_topic_profile
    from .validate_topic_relevance import validate_topic_relevance
    from .status_schema import status_envelope
except ImportError:  # pragma: no cover
    from build_contribution_tree import validate_contribution_tree
    from expert_review_gate import read_json as read_json_file, validate_expert_reviews
    from validate_argument_graph import parse_structured_text, validate_argument_graph
    from validate_article_quality import validate_article_quality
    from validate_claim_evidence import validate_claim_evidence
    from validate_coverage import read_json, read_jsonl, validate_coverage
    from validate_paper_understanding import validate_paper_understanding
    from validate_scenario_definitions import validate_scenario_definitions
    from validate_section_evidence_plans import validate_section_evidence_plans
    from validate_synthesis_dossiers import read_dossier_dir, validate_synthesis_dossiers
    from validate_exemplar_alignment import validate_exemplar_alignment
    from validate_related_survey_alignment import validate_related_survey_alignment
    from verify_sources import validate_sources
    from validate_topic_profile import validate_topic_profile
    from validate_topic_relevance import validate_topic_relevance
    from status_schema import status_envelope


PHASE_ORDER = [
    "topic_profile",
    "discovery",
    "source_verification",
    "paper_understanding",
    "synthesis",
    "argument",
    "article",
    "expert_review",
]


DOWNSTREAM_AFTER_PAPER_UNDERSTANDING = [
    "state/paper_contribution_statements.jsonl",
    "outputs/contribution_tree.yml",
    "state/scenario_definitions.yml",
    "outputs/method_family_dossiers",
    "outputs/benchmark_dossiers",
    "state/claim_evidence_spans.jsonl",
    "state/argument_graph.yml",
    "state/section_evidence_plans.jsonl",
    "outputs/article_plan.md",
    "outputs/survey_body_draft.md",
    "outputs/survey_candidate.md",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _nonempty_file(path: Path) -> bool:
    return path.exists() and path.is_file() and bool(path.read_text(encoding="utf-8").strip())


def _nonempty_dir(path: Path) -> bool:
    return path.exists() and path.is_dir() and any(path.iterdir())


def _illegal_downstream_artifacts(task_dir: Path) -> list[str]:
    found = []
    for relative in DOWNSTREAM_AFTER_PAPER_UNDERSTANDING:
        path = task_dir / relative
        if _nonempty_file(path) or _nonempty_dir(path):
            found.append(relative)
    return found


def _article_plan_status(article_plan: str) -> dict:
    required = ["article body", "article displays", "appendix", "internal"]
    lower = article_plan.lower()
    missing = [term for term in required if term not in lower]
    return {"valid": not missing, "missing": missing}


def _rendered_artifacts(outputs_dir: Path) -> list[tuple[str, str]]:
    artifacts = []
    for path in sorted(outputs_dir.glob("*.html")):
        if "dashboard" in str(path).lower():
            continue
        artifacts.append((str(path), _text(path)))
    return artifacts


def _legacy_review_artifacts(outputs_dir: Path) -> list[str]:
    legacy_stem = "review"
    return [
        str(outputs_dir / name)
        for name in [legacy_stem + ".md", legacy_stem + "_body_draft.md", legacy_stem + ".html"]
        if (outputs_dir / name).exists()
    ]


def _final_survey_artifacts(outputs_dir: Path) -> list[str]:
    return [
        str(path)
        for path in [outputs_dir / "survey.md", outputs_dir / "survey.html"]
        if path.exists()
    ]


def _load_common(task_dir: Path) -> dict:
    state = task_dir / "state"
    outputs = task_dir / "outputs"
    return {
        "state": state,
        "outputs": outputs,
        "raw_candidates": read_jsonl(state / "raw_candidates.jsonl"),
        "search_routes": read_jsonl(state / "search_routes.jsonl"),
        "lqs_scores": read_jsonl(state / "lqs_scores.jsonl"),
        "corpus_expansion": read_json(state / "corpus_expansion.json"),
        "papers": read_jsonl(state / "papers.jsonl"),
        "citation_plan": read_jsonl(state / "citation_plan.jsonl"),
        "topic_relevance_audit": read_jsonl(state / "topic_relevance_audit.jsonl"),
        "topic_relevance_second_audits": read_jsonl(state / "topic_relevance_second_audits.jsonl"),
        "mechanism_cards": read_jsonl(state / "paper_mechanism_cards.jsonl"),
        "full_text_sources": read_jsonl(state / "full_text_sources.jsonl"),
        "contribution_statements": read_jsonl(state / "paper_contribution_statements.jsonl"),
        "claims": read_jsonl(state / "claim_evidence_spans.jsonl"),
        "taxonomy_alignment": read_jsonl(state / "taxonomy_alignment.jsonl"),
        "comparative_evidence_matrix": read_jsonl(state / "comparative_evidence_matrix.jsonl"),
        "section_plans": read_jsonl(state / "section_evidence_plans.jsonl"),
        "expansion_audit": read_jsonl(state / "expansion_audit.jsonl"),
        "expert_reviews": read_jsonl(state / "expert_review_reports.jsonl"),
        "expert_invocations": read_jsonl(state / "expert_review_invocations.jsonl"),
        "repair_actions": read_jsonl(state / "repair_actions.jsonl"),
        "regression_checks": read_jsonl(state / "regression_checks.jsonl"),
        "expert_round_status": read_json_file(state / "expert_review_round_status.json"),
        "expert_adjudication": read_json_file(state / "expert_review_adjudication.json"),
        "targeted_rereviews": read_jsonl(state / "targeted_rereview_reports.jsonl"),
        "review_iteration_status": read_json_file(state / "review_iteration_status.json"),
        "article_plan": _text(outputs / "article_plan.md"),
        "survey_body_draft": _text(outputs / "survey_body_draft.md"),
        "review_text": _text(outputs / "survey_candidate.md"),
        "argument_graph": parse_structured_text(_text(state / "argument_graph.yml")),
        "argument_text": _text(state / "argument_graph.yml"),
        "scenario_text": _text(state / "scenario_definitions.yml"),
        "survey_type_text": _text(state / "survey_type_plan.yml"),
        "topic_profile": read_json(state / "topic_profile.json"),
        "contribution_tree_text": _text(outputs / "contribution_tree.yml"),
    }


def evaluate_phase_barriers(task_dir: Path, target: str = "full") -> dict:
    data = _load_common(task_dir)
    outputs = data["outputs"]

    topic_profile = validate_topic_profile(data["topic_profile"], target)
    topic_relevance = validate_topic_relevance(
        data["raw_candidates"],
        data["papers"],
        data["citation_plan"],
        data["topic_relevance_audit"],
        data["survey_type_text"],
        target,
        secondary_audits=data["topic_relevance_second_audits"],
    )
    coverage = validate_coverage(
        data["raw_candidates"],
        data["search_routes"],
        data["lqs_scores"],
        data["corpus_expansion"],
        data["papers"],
        data["citation_plan"],
        target,
        survey_type_plan=data["survey_type_text"],
        contribution_tree=data["contribution_tree_text"],
        topic_relevance_audit=data["topic_relevance_audit"] if data["topic_relevance_audit"] else None,
    )
    source_identity = validate_sources(data["papers"], data["citation_plan"], target)
    candidate_linkage_valid = "paper_candidate_linkage" not in coverage["retained_missing"]
    retained_coverage_ready = coverage["coverage_expanded"]
    source_verification_ready = source_identity["valid"] and candidate_linkage_valid and retained_coverage_ready and topic_relevance["valid"]
    paper_understanding = validate_paper_understanding(
        data["mechanism_cards"],
        data["citation_plan"],
        data["full_text_sources"],
    )
    claim_evidence = validate_claim_evidence(
        data["claims"],
        data["mechanism_cards"],
        data["section_plans"] if target != "short" else None,
        full_text_sources=data["full_text_sources"],
        article_text=data["review_text"],
    )
    contribution_tree = validate_contribution_tree(
        data["contribution_statements"],
        data["contribution_tree_text"],
        data["citation_plan"],
        data["argument_graph"] if isinstance(data["argument_graph"], dict) else {},
        target,
    )
    scenario = validate_scenario_definitions(data["scenario_text"], target, data["mechanism_cards"])
    synthesis = validate_synthesis_dossiers(
        read_dossier_dir(outputs / "method_family_dossiers"),
        read_dossier_dir(outputs / "benchmark_dossiers"),
        data["scenario_text"],
        data["mechanism_cards"],
        target,
        data["comparative_evidence_matrix"],
    )
    argument = validate_argument_graph(data["argument_graph"], data["article_plan"])
    exemplar = validate_exemplar_alignment(
        data["survey_type_text"],
        data["argument_graph"] if isinstance(data["argument_graph"], dict) else {},
        data["article_plan"],
        target,
        data["taxonomy_alignment"],
        data["mechanism_cards"],
    )
    related_survey_alignment = validate_related_survey_alignment(
        data["taxonomy_alignment"],
        data["mechanism_cards"],
        target,
        papers=data["papers"],
        topic_relevance_audit=data["topic_relevance_audit"],
        citation_plan=data["citation_plan"],
    )
    section_plans = validate_section_evidence_plans(
        data["section_plans"],
        data["argument_graph"] if isinstance(data["argument_graph"], dict) else {},
        data["article_plan"],
        data["claims"],
        data["mechanism_cards"],
        target,
    )
    article_plan = _article_plan_status(data["article_plan"])
    expert = validate_expert_reviews(
        data["expert_reviews"],
        target,
        data["review_iteration_status"],
        data["review_text"],
        data["claims"],
        data["mechanism_cards"],
        data["section_plans"],
        data["expert_invocations"],
        data["repair_actions"],
        data["regression_checks"],
        data["expert_round_status"],
        data["expert_adjudication"],
        data["targeted_rereviews"],
    )
    article = validate_article_quality(
        data["review_text"],
        article_plan=data["article_plan"],
        argument_graph=data["argument_graph"] if isinstance(data["argument_graph"], dict) else {},
        claims=data["claims"],
        target=target,
        rendered_artifacts=_rendered_artifacts(outputs),
        expansion_audit=data["expansion_audit"],
        draft_text=data["survey_body_draft"],
        legacy_artifacts=_legacy_review_artifacts(outputs),
        premature_final_artifacts=[] if expert["valid"] else _final_survey_artifacts(outputs),
        appendix_text=_text(outputs / "appendix.md") if (outputs / "appendix.md").exists() else None,
    )

    phases: dict[str, dict] = {
        "topic_profile": {
            "passed": topic_profile["valid"],
            "validator": "validate_topic_profile",
            "details": topic_profile,
        },
        "discovery": {
            "passed": topic_profile["valid"] and coverage["discovery_sufficient"],
            "validator": "validate_coverage",
            "details": {
                "topic_profile": topic_profile,
                "discovery_ready": coverage["discovery_sufficient"],
                "retained_coverage_ready": retained_coverage_ready,
                "coverage": coverage,
            },
        },
        "source_verification": {
            "passed": coverage["discovery_sufficient"] and source_verification_ready,
            "validator": "validate_sources + validate_coverage + validate_topic_relevance",
            "details": {
                "source_identity": source_identity,
                "candidate_linkage_valid": candidate_linkage_valid,
                "retained_coverage_ready": retained_coverage_ready,
                "coverage": coverage,
                "topic_relevance": topic_relevance,
            },
        },
        "paper_understanding": {
            "passed": source_verification_ready and paper_understanding["valid"],
            "validator": "validate_paper_understanding",
            "details": paper_understanding,
        },
        "synthesis": {
            "passed": paper_understanding["valid"] and claim_evidence["valid"] and contribution_tree["valid"] and scenario["valid"] and synthesis["valid"],
            "validator": "claim/contribution/scenario/synthesis validators",
            "details": {
                "claim_evidence": claim_evidence,
                "contribution_tree": contribution_tree,
                "scenario_definitions": scenario,
                "synthesis_dossiers": synthesis,
            },
        },
        "argument": {
            "passed": argument["valid"] and exemplar["valid"] and related_survey_alignment["valid"] and section_plans["valid"] and article_plan["valid"],
            "validator": "validate_argument_graph + validate_exemplar_alignment + validate_related_survey_alignment + validate_section_evidence_plans",
            "details": {
                "argument_graph": argument,
                "exemplar_alignment": exemplar,
                "related_survey_alignment": related_survey_alignment,
                "section_evidence_plans": section_plans,
                "article_plan": article_plan,
            },
        },
        "article": {
            "passed": article["valid"],
            "validator": "validate_article_quality",
            "details": article,
        },
        "expert_review": {
            "passed": expert["valid"],
            "validator": "expert_review_gate",
            "details": expert,
        },
    }

    if not phases["paper_understanding"]["passed"]:
        illegal = _illegal_downstream_artifacts(task_dir)
        if illegal:
            phases["paper_understanding"]["passed"] = False
            phases["paper_understanding"]["illegal_downstream_artifacts"] = illegal

    blocked_by = None
    for phase in PHASE_ORDER:
        if not phases[phase]["passed"]:
            blocked_by = phase
            break

    last_passed = None
    for phase in PHASE_ORDER:
        if phases[phase]["passed"]:
            last_passed = phase
        else:
            break

    allowed_next_phase = blocked_by or "complete"
    if blocked_by == "topic_profile":
        allowed_next_phase = "topic_profile"
    if blocked_by == "article":
        article_errors = set(article.get("errors") or [])
        if (
            "missing_rendered_article" in article_errors
            or "missing_appendix" in article_errors
            or int(article.get("chars") or 0) == 0
        ):
            allowed_next_phase = "article_draft"
        elif "expansion_audit_missing" in article_errors or "invalid_expansion_audit" in article_errors:
            allowed_next_phase = "expansion_audit"
        elif "article_too_short" in article_errors and article.get("expansion_audit_ready"):
            allowed_next_phase = "article_repair_after_expansion_audit"
        elif "repetitive_filler" in article_errors or "template_paragraph_repetition" in article_errors:
            allowed_next_phase = "article_quality_repair"
    if blocked_by == "source_verification" and coverage["discovery_sufficient"]:
        topic_errors = set(topic_relevance.get("errors") or [])
        if "topic_relevance_audit_missing" in topic_errors:
            allowed_next_phase = "topic_relevance_audit"
        elif (
            "ab_topic_relevance_failed" in topic_errors
            or "direct_related_survey_ab_over_limit" in topic_errors
            or "related_survey_relevance_failed" in topic_errors
        ):
            allowed_next_phase = "topic_relevance_rebalance"
        elif "topic_relevance_second_audit_required" in topic_errors:
            allowed_next_phase = "topic_relevance_second_audit"
        elif not retained_coverage_ready:
            allowed_next_phase = "coverage_repair"
    if blocked_by == "expert_review":
        expert_errors = set(expert.get("errors") or [])
        if "expert_review_not_executed" in expert_errors or "no_expert_review_reports_returned" in expert_errors or "missing_expert_review_invocations" in expert_errors:
            allowed_next_phase = "spawn_expert_reviewers"
        elif "expert_review_blocked_by_unavailable_independent_review" in expert_errors or "expert_reviews_not_all_returned" in expert_errors:
            allowed_next_phase = "expert_review_waiting"
        elif "missing_expert_review_adjudication" in expert_errors or "unadjudicated_major_weaknesses" in expert_errors or "invalid_expert_review_adjudication" in expert_errors:
            allowed_next_phase = "expert_review_adjudication"
        elif "unresolved_major_weaknesses" in expert_errors or "invalid_repair_actions" in expert_errors or "missing_regression_checks_for_repairs" in expert_errors:
            allowed_next_phase = "repair_with_evidence_check"
        elif "missing_targeted_rereviews" in expert_errors or "invalid_targeted_rereviews" in expert_errors:
            allowed_next_phase = "targeted_rereview"

    passed_count = len([phase for phase in PHASE_ORDER if phases[phase]["passed"]])
    summary = {
        "valid": blocked_by is None,
        "blocked_by_phase": blocked_by,
        "last_passed_phase": last_passed,
        "allowed_next_phase": allowed_next_phase,
        "phase_count": len(PHASE_ORDER),
        "passed_phase_count": passed_count,
    }
    return {
        **status_envelope(
            "phase_gate",
            "complete" if blocked_by is None else "blocked",
            next_action=allowed_next_phase,
            terminal=blocked_by is None,
            blocked=blocked_by is not None,
            blocked_by_phase=blocked_by,
            active_batch_id=None,
            summary=summary,
        ),
        "valid": blocked_by is None,
        "all_required_phases_passed": blocked_by is None,
        "blocked_by_phase": blocked_by,
        "last_passed_phase": last_passed,
        "allowed_next_phase": allowed_next_phase,
        "phases": phases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--phase", choices=PHASE_ORDER)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    status = evaluate_phase_barriers(args.task_dir, args.target)
    if args.phase:
        status = {"phase": args.phase, **status["phases"][args.phase]}
    text = json.dumps(status, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    if args.persist and not args.phase:
        (args.task_dir / "state" / "phase_status.json").write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if status.get("passed", status.get("valid")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
