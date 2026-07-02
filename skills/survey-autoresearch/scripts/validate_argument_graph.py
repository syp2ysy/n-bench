#!/usr/bin/env python3
"""Validate the article argument graph."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def parse_structured_text(text: str):
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        data: dict[str, object] = {}
        current = None
        for line in stripped.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if ":" in line and not line.startswith(" "):
                key, value = line.split(":", 1)
                current = key.strip()
                data[current] = value.strip() or []
            elif current and line.strip().startswith("-"):
                data.setdefault(current, [])
                if isinstance(data[current], list):
                    data[current].append(line.strip()[1:].strip())
        return data


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def validate_argument_graph(graph_or_text, article_plan: str = "") -> dict:
    graph = parse_structured_text(graph_or_text) if isinstance(graph_or_text, str) else (graph_or_text or {})
    errors: list[str] = []
    for field in ["central_thesis", "field_shift", "gap_in_existing_surveys", "argument_nodes", "section_order"]:
        if not graph.get(field):
            errors.append(f"missing_{field}")
    nodes = graph.get("argument_nodes") or {}
    if not isinstance(nodes, dict) or not nodes:
        errors.append("invalid_argument_nodes")
        nodes = {}
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            errors.append(f"{node_id}:invalid_node")
            continue
        for field in ["claim", "evidence", "implication", "section"]:
            if not node.get(field):
                errors.append(f"{node_id}:missing_{field}")
    section_order = [str(section) for section in (graph.get("section_order") or [])]
    if section_order and nodes:
        node_sections = {str(node.get("section")) for node in nodes.values() if isinstance(node, dict)}
        missing = [section for section in section_order if section not in node_sections]
        if missing:
            errors.append("section_order_not_mapped:" + ",".join(missing))
    if article_plan and section_order:
        plan = _plain(article_plan)
        missing_in_plan = [section for section in section_order if section.lower() not in plan]
        if missing_in_plan:
            errors.append("article_plan_missing_sections:" + ",".join(missing_in_plan))
    return {
        "valid": not errors,
        "errors": errors,
        "nodes": len(nodes),
        "sections": len(section_order),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--argument-graph", required=True, type=Path)
    parser.add_argument("--article-plan", type=Path)
    args = parser.parse_args()
    result = validate_argument_graph(
        args.argument_graph.read_text(encoding="utf-8"),
        args.article_plan.read_text(encoding="utf-8") if args.article_plan and args.article_plan.exists() else "",
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
