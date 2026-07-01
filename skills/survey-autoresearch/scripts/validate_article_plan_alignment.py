#!/usr/bin/env python3
"""Validate that article_plan.md realizes the argument graph."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from .validate_argument_graph import validate_argument_graph
    from .validate_topic_diagnosis import parse_structured_text
except ImportError:  # pragma: no cover
    from validate_argument_graph import validate_argument_graph
    from validate_topic_diagnosis import parse_structured_text


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _ordered_contains(plan_text: str, sections: list[str]) -> tuple[bool, list[str]]:
    lower = _plain(plan_text)
    cursor = 0
    missing: list[str] = []
    for section in sections:
        idx = lower.find(str(section).lower(), cursor)
        if idx < 0:
            missing.append(section)
        else:
            cursor = idx + len(str(section))
    return not missing, missing


def validate_article_plan_alignment(plan_text: str, argument_graph_or_text) -> dict:
    graph = parse_structured_text(argument_graph_or_text) if isinstance(argument_graph_or_text, str) else (argument_graph_or_text or {})
    graph_status = validate_argument_graph(graph)
    sections = [str(item) for item in (graph.get("section_order") or [])]
    has_order, missing_sections = _ordered_contains(plan_text, sections)
    lower = plan_text.lower()
    required_terms = {
        "article-facing": ["article-facing", "article facing", "正文", "article body"],
        "appendix-facing": ["appendix", "appendix-facing", "附录"],
        "evidence": ["evidence", "证据", "mechanism card", "paper mechanism"],
        "case boxes": ["case", "box", "案例", "机制解剖"],
    }
    missing_terms = [
        name for name, terms in required_terms.items()
        if not any(term in lower or term in plan_text for term in terms)
    ]
    errors = []
    if not graph_status["valid"]:
        errors.append("invalid_argument_graph")
    if not has_order:
        errors.append("missing_or_unordered_sections:" + ",".join(missing_sections))
    if missing_terms:
        errors.append("missing_article_plan_terms:" + ",".join(missing_terms))
    return {
        "valid": not errors,
        "errors": errors,
        "missing_sections": missing_sections,
        "missing_terms": missing_terms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article-plan", required=True, type=Path)
    parser.add_argument("--argument-graph", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_article_plan_alignment(
        args.article_plan.read_text(encoding="utf-8"),
        args.argument_graph.read_text(encoding="utf-8"),
    )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
