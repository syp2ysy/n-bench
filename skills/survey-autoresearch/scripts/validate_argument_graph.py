#!/usr/bin/env python3
"""Validate the article-level argument graph for survey synthesis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .validate_topic_diagnosis import parse_structured_text
except ImportError:  # pragma: no cover
    from validate_topic_diagnosis import parse_structured_text


NODE_FIELDS = ["claim", "evidence", "leads_to", "section", "strength"]


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def validate_argument_graph(data_or_text) -> dict:
    data = parse_structured_text(data_or_text) if isinstance(data_or_text, str) else (data_or_text or {})
    errors: list[str] = []
    for field in ["central_thesis", "field_shift", "gap_in_existing_surveys", "argument_nodes", "section_order", "takeaway_findings"]:
        if not _nonempty(data.get(field)):
            errors.append(f"missing {field}")
    nodes = data.get("argument_nodes") or {}
    if not isinstance(nodes, dict):
        errors.append("argument_nodes must be object")
        nodes = {}
    sections = set(_as_list(data.get("section_order")))
    node_ids = set(nodes)
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            errors.append(f"{node_id}: node must be object")
            continue
        missing = [
            field for field in NODE_FIELDS
            if (field == "leads_to" and field not in node)
            or (field != "leads_to" and not _nonempty(node.get(field)))
        ]
        if missing:
            errors.append(f"{node_id}: missing " + ",".join(missing))
        for target in _as_list(node.get("leads_to")):
            if target and target not in node_ids:
                errors.append(f"{node_id}: leads_to unknown node {target}")
        if node.get("section") and sections and node.get("section") not in sections:
            errors.append(f"{node_id}: section not in section_order")
    sections_with_nodes = {node.get("section") for node in nodes.values() if isinstance(node, dict)}
    missing_sections = sorted(section for section in sections if section not in sections_with_nodes)
    if missing_sections:
        errors.append("section_order entries without argument nodes " + ",".join(missing_sections))
    return {
        "valid": not errors,
        "errors": errors,
        "nodes": len(nodes),
        "sections": len(sections),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--argument-graph", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_argument_graph(args.argument_graph.read_text(encoding="utf-8"))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
