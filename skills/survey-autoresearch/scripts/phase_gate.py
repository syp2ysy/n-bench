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
    from .verify_sources import validate_sources
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
    from verify_sources import validate_sources


PHASE_ORDER = [
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
    "outputs/review_body_draft.md",
    "outputs/review.md",
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
        "mechanism_cards": read_jsonl(state / "paper_mechanism_cards.jsonl"),
        "full_text_sources": read_jsonl(state / "full_text_sources.jsonl"),
        "contribution_statements": read_jsonl(state / "paper_contribution_statements.jsonl"),
        "claims": read_jsonl(state / "claim_evidence_spans.jsonl"),
        "section_plans": read_jsonl(state / "section_evidence_plans.jsonl"),
        "expert_reviews": read_jsonl(state / "expert_review_reports.jsonl"),
        "expert_invocations": read_jsonl(state / "expert_review_invocations.jsonl"),
        "repair_actions": read_jsonl(state / "repair_actions.jsonl"),
        "regression_checks": read_jsonl(state / "regression_checks.jsonl"),
        "review_iteration_status": read_json_file(state / "review_iteration_status.json"),
        "article_plan": _text(outputs / "article_plan.md"),
        "review_text": _text(outputs / "review.md"),
        "argument_graph": parse_structured_text(_text(state / "argument_graph.yml")),
        "scenario_text": _text(state / "scenario_definitions.yml"),
        "contribution_tree_text": _text(outputs / "contribution_tree.yml"),
    }


def evaluate_phase_barriers(task_dir: Path, target: str = "full") -> dict:
    data = _load_common(task_dir)
    outputs = data["outputs"]

    coverage = validate_coverage(
        data["raw_candidates"],
        data["search_routes"],
        data["lqs_scores"],
        data["corpus_expansion"],
        data["papers"],
        data["citation_plan"],
        target,
    )
    source_identity = validate_sources(data["papers"], data["citation_plan"], target)
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
    )
    contribution_tree = validate_contribution_tree(
        data["contribution_statements"],
        data["contribution_tree_text"],
        data["citation_plan"],
        data["argument_graph"] if isinstance(data["argument_graph"], dict) else {},
        target,
    )
    scenario = validate_scenario_definitions(data["scenario_text"], target)
    synthesis = validate_synthesis_dossiers(
        read_dossier_dir(outputs / "method_family_dossiers"),
        read_dossier_dir(outputs / "benchmark_dossiers"),
        data["scenario_text"],
        data["mechanism_cards"],
        target,
    )
    argument = validate_argument_graph(data["argument_graph"], data["article_plan"])
    section_plans = validate_section_evidence_plans(
        data["section_plans"],
        data["argument_graph"] if isinstance(data["argument_graph"], dict) else {},
        data["article_plan"],
        data["claims"],
        data["mechanism_cards"],
        target,
    )
    article_plan = _article_plan_status(data["article_plan"])
    article = validate_article_quality(
        data["review_text"],
        article_plan=data["article_plan"],
        argument_graph=data["argument_graph"] if isinstance(data["argument_graph"], dict) else {},
        claims=data["claims"],
        target=target,
        rendered_artifacts=_rendered_artifacts(outputs),
    )
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
    )

    phases: dict[str, dict] = {
        "discovery": {
            "passed": coverage["discovery_sufficient"],
            "validator": "validate_coverage",
            "details": coverage,
        },
        "source_verification": {
            "passed": coverage["discovery_sufficient"] and source_identity["valid"] and "paper_candidate_linkage" not in coverage["retained_missing"],
            "validator": "validate_sources + validate_coverage",
            "details": {
                "source_identity": source_identity,
                "candidate_linkage_valid": "paper_candidate_linkage" not in coverage["retained_missing"],
            },
        },
        "paper_understanding": {
            "passed": source_identity["valid"] and paper_understanding["valid"],
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
            "passed": argument["valid"] and section_plans["valid"] and article_plan["valid"],
            "validator": "validate_argument_graph + validate_section_evidence_plans",
            "details": {
                "argument_graph": argument,
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

    return {
        "valid": blocked_by is None,
        "all_required_phases_passed": blocked_by is None,
        "blocked_by_phase": blocked_by,
        "last_passed_phase": last_passed,
        "allowed_next_phase": blocked_by or "complete",
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
