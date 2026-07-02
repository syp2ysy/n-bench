#!/usr/bin/env python3
"""Validate section-level source re-check plans."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .verify_sources import read_jsonl
    from .validate_argument_graph import parse_structured_text
except ImportError:  # pragma: no cover
    from verify_sources import read_jsonl
    from validate_argument_graph import parse_structured_text


REQUIRED_FIELDS = [
    "section_id",
    "title",
    "argument_node",
    "section_claim",
    "scenario_definitions_used",
    "anchor_papers",
    "must_include_evidence_spans",
    "must_not_overclaim",
]


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _article_sections(article_plan: str) -> list[str]:
    sections: list[str] = []
    in_body = False
    for raw in article_plan.splitlines():
        line = raw.strip()
        lower = line.lower()
        if lower.startswith("## "):
            in_body = "article body" in lower
            continue
        if in_body and line.startswith("- "):
            sections.append(line[2:].strip())
        elif in_body and len(line) > 2 and line[0].isdigit() and "." in line[:4]:
            sections.append(line.split(".", 1)[1].strip())
    return sections


def validate_section_evidence_plans(plans: list[dict], argument_graph, article_plan: str, claims: list[dict], mechanism_cards: list[dict], target: str = "full") -> dict:
    graph = parse_structured_text(argument_graph) if isinstance(argument_graph, str) else (argument_graph or {})
    nodes = graph.get("argument_nodes") or {}
    article_sections = _article_sections(article_plan)
    card_ids = {str(card.get("paper_id")) for card in mechanism_cards if card.get("paper_id")}
    claim_ids = {str(claim.get("claim_id") or claim.get("id")) for claim in claims if claim.get("claim_id") or claim.get("id")}
    by_title = {str(plan.get("title")): plan for plan in plans if plan.get("title")}
    errors: list[str] = []
    invalid: dict[str, list[str]] = {}
    if target != "short" and not plans:
        errors.append("missing_section_evidence_plans")
    missing_sections = [section for section in article_sections if section not in by_title]
    if target != "short" and missing_sections:
        errors.append("article_sections_missing_plans")
    for plan in plans:
        title = str(plan.get("title") or plan.get("section_id") or "<missing>")
        item_errors = []
        for field in REQUIRED_FIELDS:
            if not _nonempty(plan.get(field)):
                item_errors.append(f"missing_{field}")
        node_id = str(plan.get("argument_node") or "")
        if nodes and node_id not in nodes:
            item_errors.append("unknown_argument_node")
        anchor_papers = [str(pid) for pid in plan.get("anchor_papers") or []]
        if not anchor_papers and not _nonempty(plan.get("explicit_reason_no_anchor")):
            item_errors.append("missing_anchor_papers")
        unknown_papers = [pid for pid in anchor_papers + [str(pid) for pid in plan.get("supporting_papers") or []] if pid and pid not in card_ids]
        if unknown_papers:
            item_errors.append("unknown_papers:" + ",".join(sorted(set(unknown_papers))))
        section_kind = title.lower() + " " + " ".join(str(x).lower() for x in plan.get("method_families_used") or [])
        if any(term in section_kind for term in ["method", "family", "方法"]):
            if not _nonempty(plan.get("required_comparisons")):
                item_errors.append("missing_required_comparisons")
        if any(term in title.lower() for term in ["benchmark", "evaluation", "评测", "benchmark"]):
            for field in ["protocol", "metric", "baseline", "confounder"]:
                if not _nonempty(plan.get(field)):
                    item_errors.append(f"missing_{field}")
        missing_claims = [str(cid) for cid in plan.get("must_include_evidence_spans") or [] if str(cid) not in claim_ids]
        if missing_claims:
            item_errors.append("unknown_claim_spans:" + ",".join(missing_claims))
        if item_errors:
            invalid[title] = item_errors
    return {
        "valid": not errors and not invalid,
        "errors": errors + (["invalid_section_evidence_plans"] if invalid else []),
        "total_plans": len(plans),
        "article_sections": len(article_sections),
        "missing_sections": missing_sections,
        "invalid_plans": invalid,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section-evidence-plans", required=True, type=Path)
    parser.add_argument("--argument-graph", required=True, type=Path)
    parser.add_argument("--article-plan", required=True, type=Path)
    parser.add_argument("--claims", required=True, type=Path)
    parser.add_argument("--paper-mechanism-cards", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    result = validate_section_evidence_plans(
        read_jsonl(args.section_evidence_plans),
        args.argument_graph.read_text(encoding="utf-8"),
        args.article_plan.read_text(encoding="utf-8"),
        read_jsonl(args.claims),
        read_jsonl(args.paper_mechanism_cards),
        args.target,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
