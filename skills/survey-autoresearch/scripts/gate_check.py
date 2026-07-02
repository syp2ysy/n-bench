#!/usr/bin/env python3
"""Run the six survey-autoresearch completion gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .verify_sources import read_jsonl, validate_sources
    from .validate_paper_understanding import validate_paper_understanding
    from .validate_claim_evidence import validate_claim_evidence
    from .build_coverage_matrix import build_coverage
    from .validate_argument_graph import parse_structured_text, validate_argument_graph
    from .validate_article_quality import validate_article_quality
    from .validate_scenario_definitions import validate_scenario_definitions
    from .validate_synthesis_dossiers import read_dossier_dir, validate_synthesis_dossiers
    from .validate_section_evidence_plans import validate_section_evidence_plans
except ImportError:  # pragma: no cover
    from verify_sources import read_jsonl, validate_sources
    from validate_paper_understanding import validate_paper_understanding
    from validate_claim_evidence import validate_claim_evidence
    from build_coverage_matrix import build_coverage
    from validate_argument_graph import parse_structured_text, validate_argument_graph
    from validate_article_quality import validate_article_quality
    from validate_scenario_definitions import validate_scenario_definitions
    from validate_synthesis_dossiers import read_dossier_dir, validate_synthesis_dossiers
    from validate_section_evidence_plans import validate_section_evidence_plans


def text_or_empty(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def exists_nonempty(path: Path) -> bool:
    return path.exists() and path.read_text(encoding="utf-8").strip() != ""


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


def evaluate_gates(task_dir: Path, target: str = "short") -> dict:
    state = task_dir / "state"
    outputs = task_dir / "outputs"
    papers = read_jsonl(state / "papers.jsonl")
    citation_plan = read_jsonl(state / "citation_plan.jsonl")
    mechanism_cards = read_jsonl(state / "paper_mechanism_cards.jsonl")
    claims = read_jsonl(state / "claim_evidence_spans.jsonl")
    section_plans = read_jsonl(state / "section_evidence_plans.jsonl")
    article_plan = text_or_empty(outputs / "article_plan.md")
    argument_text = text_or_empty(state / "argument_graph.yml")
    argument_graph = parse_structured_text(argument_text)
    scenario_text = text_or_empty(state / "scenario_definitions.yml")
    survey_type = survey_type_status(text_or_empty(state / "survey_type_plan.yml"))
    review_text = text_or_empty(outputs / "review.md")

    gate_1 = validate_sources(papers, citation_plan, target)
    gate_2 = validate_paper_understanding(mechanism_cards, citation_plan)
    gate_3 = validate_claim_evidence(claims, mechanism_cards, section_plans if target != "short" else None)
    gate_4 = build_coverage(papers, citation_plan, target)
    dossier_status = synthesis_dossier_status(outputs, target, survey_type)
    scenario_status = validate_scenario_definitions(scenario_text, target)
    synthesis_status = validate_synthesis_dossiers(
        read_dossier_dir(outputs / "method_family_dossiers"),
        read_dossier_dir(outputs / "benchmark_dossiers"),
        scenario_text,
        mechanism_cards,
        target,
    )
    gate_5 = validate_argument_graph(argument_graph, article_plan)
    section_plan_status = validate_section_evidence_plans(
        section_plans,
        argument_graph if isinstance(argument_graph, dict) else {},
        article_plan,
        claims,
        mechanism_cards,
        target,
    )
    plan_status = article_plan_status(article_plan)
    gate_6 = validate_article_quality(
        review_text,
        article_plan=article_plan,
        argument_graph=argument_graph if isinstance(argument_graph, dict) else {},
        claims=claims,
        target=target,
    )

    gates = {
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
                and plan_status["valid"]
                and survey_type["valid"]
            ),
            **gate_5,
            "survey_type": survey_type,
            "synthesis_dossiers": dossier_status,
            "scenario_definitions": scenario_status,
            "synthesis_dossier_quality": synthesis_status,
            "section_evidence_plans": section_plan_status,
            "article_plan": plan_status,
        },
        "gate_6_article_quality": {"passed": gate_6["valid"], **gate_6},
    }
    gates["all_blocking_gates_passed"] = all(
        gates[name]["passed"] for name in [
            "gate_1_source_identity",
            "gate_2_paper_understanding",
            "gate_3_claim_evidence",
            "gate_4_coverage",
            "gate_5_argument_graph",
            "gate_6_article_quality",
        ]
    )
    return gates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="short")
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
