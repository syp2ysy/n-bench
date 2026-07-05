#!/usr/bin/env python3
"""Run the survey-autoresearch completion gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from .verify_sources import read_jsonl, validate_sources
    from .validate_paper_understanding import validate_paper_understanding
    from .validate_claim_evidence import validate_claim_evidence
    from .phase_gate import evaluate_phase_barriers
    from .validate_coverage import read_json, validate_coverage
    from .validate_topic_relevance import validate_topic_relevance
    from .validate_argument_graph import parse_structured_text, validate_argument_graph
    from .validate_article_quality import validate_article_quality
    from .validate_scenario_definitions import validate_scenario_definitions
    from .validate_synthesis_dossiers import read_dossier_dir, validate_synthesis_dossiers
    from .validate_section_evidence_plans import validate_section_evidence_plans
    from .validate_exemplar_alignment import validate_exemplar_alignment
    from .validate_related_survey_alignment import validate_related_survey_alignment
    from .expert_review_gate import read_json as read_json_file, validate_expert_reviews
    from .build_contribution_tree import validate_contribution_tree
except ImportError:  # pragma: no cover
    from verify_sources import read_jsonl, validate_sources
    from validate_paper_understanding import validate_paper_understanding
    from validate_claim_evidence import validate_claim_evidence
    from phase_gate import evaluate_phase_barriers
    from validate_coverage import read_json, validate_coverage
    from validate_topic_relevance import validate_topic_relevance
    from validate_argument_graph import parse_structured_text, validate_argument_graph
    from validate_article_quality import validate_article_quality
    from validate_scenario_definitions import validate_scenario_definitions
    from validate_synthesis_dossiers import read_dossier_dir, validate_synthesis_dossiers
    from validate_section_evidence_plans import validate_section_evidence_plans
    from validate_exemplar_alignment import validate_exemplar_alignment
    from validate_related_survey_alignment import validate_related_survey_alignment
    from expert_review_gate import read_json as read_json_file, validate_expert_reviews
    from build_contribution_tree import validate_contribution_tree


def text_or_empty(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def exists_nonempty(path: Path) -> bool:
    return path.exists() and path.read_text(encoding="utf-8").strip() != ""


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def article_plan_status(article_plan: str) -> dict:
    required = ["article body", "article displays", "appendix", "internal"]
    lower = article_plan.lower()
    missing = [term for term in required if term not in lower]
    return {"valid": not missing, "missing": missing}


def survey_type_status(plan: dict | str) -> dict:
    data = parse_structured_text(plan) if isinstance(plan, str) else (plan or {})
    primary = str(data.get("primary_type") or data.get("primary_survey_type") or "").strip()
    secondary = data.get("secondary_lenses") or []
    if isinstance(secondary, str):
        secondary = [secondary]
    allowed = {"system-object", "method-family", "benchmark/evaluation", "risk/threat", "application-domain"}
    missing = []
    if primary not in allowed:
        missing.append("primary_type")
    for field in ["why_this_type", "article_skeleton", "excluded_templates"]:
        if not data.get(field):
            missing.append(field)
    return {
        "valid": not missing,
        "missing": missing,
        "primary_type": primary,
        "secondary_lenses": secondary,
    }


def synthesis_dossier_status(outputs_dir: Path, target: str, survey_type: dict) -> dict:
    if target == "short":
        return {"valid": True, "required": False, "missing": []}
    primary = survey_type.get("primary_type", "")
    secondary = set(survey_type.get("secondary_lenses", []))
    required = [outputs_dir / "related_survey_matrix.md"]
    if primary in {"system-object", "method-family"} or "method-family" in secondary:
        required.append(outputs_dir / "method_family_dossiers")
    if primary == "benchmark/evaluation" or "benchmark/evaluation" in secondary:
        required.append(outputs_dir / "benchmark_dossiers")
    if primary == "risk/threat" or "risk/threat" in secondary:
        required.append(outputs_dir / "risk_dossiers")
    if primary == "application-domain" or "application-domain" in secondary:
        required.append(outputs_dir / "application_dossiers")
    missing = []
    for path in required:
        if path.suffix:
            if not exists_nonempty(path):
                missing.append(str(path.name))
        else:
            if not path.exists() or not list(path.glob("*")):
                missing.append(str(path.name))
    return {"valid": not missing, "required": True, "missing": missing}


def rendered_artifacts(outputs_dir: Path) -> list[tuple[str, str]]:
    artifacts = []
    for path in sorted(outputs_dir.glob("*.html")):
        if "dashboard" in str(path).lower():
            continue
        artifacts.append((str(path), text_or_empty(path)))
    return artifacts


def final_survey_artifacts(outputs_dir: Path) -> list[str]:
    return [
        str(path)
        for path in [outputs_dir / "survey.md", outputs_dir / "survey.html"]
        if path.exists()
    ]


def release_manifest(outputs_dir: Path) -> dict:
    path = outputs_dir / "release_manifest.json"
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"released": False, "invalid": True}


def legacy_review_artifacts(outputs_dir: Path) -> list[str]:
    legacy_stem = "review"
    return [
        str(outputs_dir / name)
        for name in [legacy_stem + ".md", legacy_stem + "_body_draft.md", legacy_stem + ".html"]
        if (outputs_dir / name).exists()
    ]


def evaluate_gates(task_dir: Path, target: str = "full") -> dict:
    state = task_dir / "state"
    outputs = task_dir / "outputs"
    candidate_hash = sha256_file(outputs / "survey_candidate.md")
    raw_candidates = read_jsonl(state / "raw_candidates.jsonl")
    search_routes = read_jsonl(state / "search_routes.jsonl")
    lqs_scores = read_jsonl(state / "lqs_scores.jsonl")
    corpus_expansion = read_json(state / "corpus_expansion.json")
    papers = read_jsonl(state / "papers.jsonl")
    citation_plan = read_jsonl(state / "citation_plan.jsonl")
    mechanism_cards = read_jsonl(state / "paper_mechanism_cards.jsonl")
    full_text_sources = read_jsonl(state / "full_text_sources.jsonl")
    contribution_statements = read_jsonl(state / "paper_contribution_statements.jsonl")
    claims = read_jsonl(state / "claim_evidence_spans.jsonl")
    section_plans = read_jsonl(state / "section_evidence_plans.jsonl")
    taxonomy_alignment = read_jsonl(state / "taxonomy_alignment.jsonl")
    comparative_evidence_matrix = read_jsonl(state / "comparative_evidence_matrix.jsonl")
    expansion_audit = read_jsonl(state / "expansion_audit.jsonl")
    expert_reviews = read_jsonl(state / "expert_review_reports.jsonl")
    expert_invocations = read_jsonl(state / "expert_review_invocations.jsonl")
    repair_actions = read_jsonl(state / "repair_actions.jsonl")
    regression_checks = read_jsonl(state / "regression_checks.jsonl")
    expert_round_status = read_json_file(state / "expert_review_round_status.json")
    expert_adjudication = read_json_file(state / "expert_review_adjudication.json")
    targeted_rereviews = read_jsonl(state / "targeted_rereview_reports.jsonl")
    review_iteration_status = read_json_file(state / "review_iteration_status.json")
    topic_relevance_audit = read_jsonl(state / "topic_relevance_audit.jsonl")
    topic_relevance_second_audits = read_jsonl(state / "topic_relevance_second_audits.jsonl")
    article_plan = text_or_empty(outputs / "article_plan.md")
    survey_body_draft = text_or_empty(outputs / "survey_body_draft.md")
    argument_text = text_or_empty(state / "argument_graph.yml")
    argument_graph = parse_structured_text(argument_text)
    scenario_text = text_or_empty(state / "scenario_definitions.yml")
    survey_type_text = text_or_empty(state / "survey_type_plan.yml")
    survey_type = survey_type_status(survey_type_text)
    review_text = text_or_empty(outputs / "survey_candidate.md")
    release = release_manifest(outputs)

    gate_1 = validate_sources(papers, citation_plan, target)
    gate_2 = validate_paper_understanding(mechanism_cards, citation_plan, full_text_sources)
    gate_3 = validate_claim_evidence(
        claims,
        mechanism_cards,
        section_plans if target != "short" else None,
        full_text_sources=full_text_sources,
        article_text=review_text,
    )
    gate_4_coverage = validate_coverage(
        raw_candidates,
        search_routes,
        lqs_scores,
        corpus_expansion,
        papers,
        citation_plan,
        target,
        survey_type_plan=survey_type_text,
        contribution_tree=text_or_empty(outputs / "contribution_tree.yml"),
        topic_relevance_audit=topic_relevance_audit if topic_relevance_audit else None,
    )
    gate_4_topic = validate_topic_relevance(
        raw_candidates,
        papers,
        citation_plan,
        topic_relevance_audit,
        survey_type_text,
        target,
        secondary_audits=topic_relevance_second_audits,
    )
    gate_4 = {
        **gate_4_coverage,
        "valid": gate_4_coverage["valid"] and gate_4_topic["valid"],
        "topic_relevance": gate_4_topic,
        "topic_relevance_valid": gate_4_topic["valid"],
    }
    dossier_status = synthesis_dossier_status(outputs, target, survey_type)
    scenario_status = validate_scenario_definitions(scenario_text, target, mechanism_cards)
    synthesis_status = validate_synthesis_dossiers(
        read_dossier_dir(outputs / "method_family_dossiers"),
        read_dossier_dir(outputs / "benchmark_dossiers"),
        scenario_text,
        mechanism_cards,
        target,
        comparative_evidence_matrix,
    )
    gate_5 = validate_argument_graph(argument_graph, article_plan)
    exemplar_status = validate_exemplar_alignment(
        survey_type_text,
        argument_graph if isinstance(argument_graph, dict) else {},
        article_plan,
        target,
        taxonomy_alignment,
        mechanism_cards,
    )
    related_survey_status = validate_related_survey_alignment(
        taxonomy_alignment,
        mechanism_cards,
        target,
        papers=papers,
        topic_relevance_audit=topic_relevance_audit,
        citation_plan=citation_plan,
    )
    section_plan_status = validate_section_evidence_plans(
        section_plans,
        argument_graph if isinstance(argument_graph, dict) else {},
        article_plan,
        claims,
        mechanism_cards,
        target,
    )
    contribution_tree_status = validate_contribution_tree(
        contribution_statements,
        text_or_empty(outputs / "contribution_tree.yml"),
        citation_plan,
        argument_graph if isinstance(argument_graph, dict) else {},
        target,
    )
    plan_status = article_plan_status(article_plan)
    gate_7 = validate_expert_reviews(
        expert_reviews,
        target,
        review_iteration_status,
        review_text,
        claims,
        mechanism_cards,
        section_plans,
        expert_invocations,
        repair_actions,
        regression_checks,
        expert_round_status,
        expert_adjudication,
        targeted_rereviews,
    )
    gate_6 = validate_article_quality(
        review_text,
        article_plan=article_plan,
        argument_graph=argument_graph if isinstance(argument_graph, dict) else {},
        claims=claims,
        target=target,
        rendered_artifacts=rendered_artifacts(outputs),
        expansion_audit=expansion_audit,
        draft_text=survey_body_draft,
        legacy_artifacts=legacy_review_artifacts(outputs),
        premature_final_artifacts=[] if gate_7["valid"] else final_survey_artifacts(outputs),
        appendix_text=text_or_empty(outputs / "appendix.md") if (outputs / "appendix.md").exists() else None,
    )
    phase_barriers = evaluate_phase_barriers(task_dir, target)

    gates = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "candidate_hash": candidate_hash,
        "gate_1_source_identity": {"passed": gate_1["valid"], **gate_1},
        "gate_2_paper_understanding": {"passed": gate_2["valid"], **gate_2},
        "gate_3_claim_evidence": {"passed": gate_3["valid"], **gate_3},
        "gate_4_coverage": {"passed": gate_4["valid"], **gate_4},
        "gate_5_argument_graph": {
            "passed": (
                gate_5["valid"]
                and dossier_status["valid"]
                and scenario_status["valid"]
                and synthesis_status["valid"]
                and section_plan_status["valid"]
                and contribution_tree_status["valid"]
                and plan_status["valid"]
                and survey_type["valid"]
                and exemplar_status["valid"]
                and related_survey_status["valid"]
            ),
            **gate_5,
            "survey_type": survey_type,
            "exemplar_alignment": exemplar_status,
            "related_survey_alignment": related_survey_status,
            "synthesis_dossiers": dossier_status,
            "scenario_definitions": scenario_status,
            "synthesis_dossier_quality": synthesis_status,
            "section_evidence_plans": section_plan_status,
            "contribution_tree": contribution_tree_status,
            "article_plan": plan_status,
        },
        "gate_6_article_quality": {"passed": gate_6["valid"], **gate_6},
        "gate_7_expert_review": {"passed": gate_7["valid"], **gate_7},
        "phase_barriers": phase_barriers,
    }
    gates["all_blocking_gates_passed"] = all(
        gates[name]["passed"] for name in [
            "gate_1_source_identity",
            "gate_2_paper_understanding",
            "gate_3_claim_evidence",
            "gate_4_coverage",
            "gate_5_argument_graph",
            "gate_6_article_quality",
            "gate_7_expert_review",
        ]
    ) and phase_barriers["all_required_phases_passed"]
    gates["release_allowed"] = bool(gates["all_blocking_gates_passed"] and gate_7["valid"])
    gates["release_manifest"] = release
    gates["survey_complete"] = bool(gates["release_allowed"] and release.get("released") is True)
    if gates["survey_complete"]:
        gates["completion_level"] = "publication_ready"
    elif gates["release_allowed"]:
        gates["completion_level"] = "automatic_checked"
    elif all(gates[name]["passed"] for name in [
        "gate_1_source_identity",
        "gate_2_paper_understanding",
        "gate_3_claim_evidence",
        "gate_4_coverage",
        "gate_5_argument_graph",
        "gate_6_article_quality",
    ]):
        gates["completion_level"] = "automatic_checked"
    else:
        gates["completion_level"] = "draft"
    if not phase_barriers["all_required_phases_passed"]:
        gates["blocked_by_phase"] = phase_barriers["blocked_by_phase"]
        gates["allowed_next_phase"] = phase_barriers["allowed_next_phase"]
    return gates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_gates(args.task_dir, args.target)
    text = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["all_blocking_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
