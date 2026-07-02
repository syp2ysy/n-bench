#!/usr/bin/env python3
"""Validate exemplar-aligned outline design for full survey runs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from .validate_argument_graph import parse_structured_text
except ImportError:  # pragma: no cover
    from validate_argument_graph import parse_structured_text


SURVEY_TYPE_REQUIRED = [
    "exemplar_alignment",
    "community_native_taxonomy",
    "exemplar_section_patterns",
    "candidate_article_spines",
    "selected_article_spine",
    "why_not_exemplar_spine",
    "figure_first_plan",
]

ARGUMENT_GRAPH_REQUIRED = [
    "community_taxonomy_nodes",
    "taxonomy_competition",
    "paper_relation_graph",
    "exemplar_delta",
    "figure_plan",
]

ARTICLE_PLAN_REQUIRED = [
    ("taxonomy[ _-]roadmap", "taxonomy_roadmap"),
    ("method[ _-]evolution|timeline", "method_evolution_or_timeline"),
    ("data[ _-]ecosystem", "data_ecosystem"),
    ("evaluation[ _-]protocol|protocol[ _-]matrix", "evaluation_protocol_matrix"),
]


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _list_len(value) -> int:
    if isinstance(value, (list, tuple, set)):
        return len(value)
    if isinstance(value, dict):
        for key in ["items", "exemplars", "spines", "figures", "nodes"]:
            if isinstance(value.get(key), list):
                return len(value[key])
        return len(value)
    if isinstance(value, str):
        lines = [line for line in value.splitlines() if line.strip()]
        if len(lines) > 1:
            return len(lines)
        return 1 if value.strip() else 0
    return 1 if value else 0


def _contains(text: str, pattern: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _figure_plan_text(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def validate_exemplar_alignment(
    survey_type_plan,
    argument_graph,
    article_plan: str,
    target: str = "full",
) -> dict:
    if target == "short":
        return {"valid": True, "required": False, "errors": []}

    survey = parse_structured_text(survey_type_plan) if isinstance(survey_type_plan, str) else (survey_type_plan or {})
    graph = parse_structured_text(argument_graph) if isinstance(argument_graph, str) else (argument_graph or {})
    errors: list[str] = []

    missing_survey_type_fields = [field for field in SURVEY_TYPE_REQUIRED if not _nonempty(survey.get(field))]
    if missing_survey_type_fields:
        errors.append("missing_exemplar_alignment_fields")

    exemplar_alignment = survey.get("exemplar_alignment")
    if _list_len(exemplar_alignment) < 1:
        errors.append("too_few_exemplars")

    if _list_len(survey.get("community_native_taxonomy")) < 2:
        errors.append("community_native_taxonomy_too_thin")

    if _list_len(survey.get("candidate_article_spines")) < 2:
        errors.append("too_few_candidate_article_spines")

    selected_spine = str(survey.get("selected_article_spine") or "").lower()
    primary_type = str(survey.get("primary_type") or survey.get("primary_survey_type") or "").lower()
    if primary_type and selected_spine and selected_spine == primary_type:
        errors.append("selected_spine_equals_abstract_primary_type")

    figure_text = _figure_plan_text(survey.get("figure_first_plan"))
    missing_figure_items = [
        name
        for pattern, name in ARTICLE_PLAN_REQUIRED
        if not _contains(figure_text, pattern)
    ]
    if missing_figure_items:
        errors.append("figure_first_plan_incomplete")

    missing_argument_graph_fields = [field for field in ARGUMENT_GRAPH_REQUIRED if not _nonempty(graph.get(field))]
    if missing_argument_graph_fields:
        errors.append("missing_argument_graph_exemplar_fields")

    invalid_argument_nodes: dict[str, list[str]] = {}
    nodes = graph.get("argument_nodes") or {}
    if isinstance(nodes, dict):
        for node_id, node in nodes.items():
            if isinstance(node, dict) and not _nonempty(node.get("section_role")):
                invalid_argument_nodes[str(node_id)] = ["missing_section_role"]
    if invalid_argument_nodes:
        errors.append("argument_nodes_missing_section_role")

    article_lower = article_plan.lower()
    missing_article_plan_items = [
        name
        for pattern, name in ARTICLE_PLAN_REQUIRED
        if not _contains(article_lower, pattern)
    ]
    if missing_article_plan_items:
        errors.append("article_plan_missing_figure_first_items")

    taxonomy_competition = _figure_plan_text(graph.get("taxonomy_competition")).lower()
    if taxonomy_competition and not all(term in taxonomy_competition for term in ["system", "taxonom"]):
        errors.append("taxonomy_competition_missing_alternative_taxonomy")

    return {
        "valid": not errors,
        "required": True,
        "errors": sorted(set(errors)),
        "missing_survey_type_fields": missing_survey_type_fields,
        "missing_argument_graph_fields": missing_argument_graph_fields,
        "invalid_argument_nodes": invalid_argument_nodes,
        "missing_article_plan_items": missing_article_plan_items,
        "missing_figure_items": missing_figure_items,
        "selected_article_spine": survey.get("selected_article_spine"),
        "primary_type": survey.get("primary_type") or survey.get("primary_survey_type"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey-type-plan", required=True, type=Path)
    parser.add_argument("--argument-graph", required=True, type=Path)
    parser.add_argument("--article-plan", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    result = validate_exemplar_alignment(
        args.survey_type_plan.read_text(encoding="utf-8"),
        args.argument_graph.read_text(encoding="utf-8"),
        args.article_plan.read_text(encoding="utf-8"),
        args.target,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
