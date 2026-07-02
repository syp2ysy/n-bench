#!/usr/bin/env python3
"""Validate paper contribution statements and contribution-tree synthesis."""

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


STRENGTHS = {"demonstrates", "shows", "suggests", "may indicate"}
STATEMENT_REQUIRED = [
    "paper_id",
    "statement",
    "problem",
    "method",
    "result",
    "limitation",
    "evidence_strength",
    "source_ref",
]
TREE_REQUIRED = ["root_claim", "branches"]
BRANCH_REQUIRED = ["name", "motivation", "representative_papers", "core_tradeoff", "evidence_standard", "failure_risks"]


def depth_ids(citation_plan: list[dict]) -> set[str]:
    return {
        str(item["paper_id"])
        for item in citation_plan
        if item.get("paper_id") and str(item.get("depth") or item.get("level") or "").upper() in {"A", "B"}
    }


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _benchmarks(statement: dict):
    return statement.get("benchmark") or statement.get("task_or_benchmark") or statement.get("benchmarks")


def validate_contribution_tree(
    statements: list[dict],
    contribution_tree,
    citation_plan: list[dict] | None = None,
    argument_graph=None,
    target: str = "full",
) -> dict:
    if target == "short":
        return {"valid": True, "required": False, "errors": []}
    tree = parse_structured_text(contribution_tree) if isinstance(contribution_tree, str) else (contribution_tree or {})
    graph = parse_structured_text(argument_graph) if isinstance(argument_graph, str) else (argument_graph or {})
    required_ids = depth_ids(citation_plan or [])
    by_id = {str(item.get("paper_id")): item for item in statements if item.get("paper_id")}
    errors: list[str] = []
    invalid_statements: dict[str, list[str]] = {}
    invalid_branches: dict[str, list[str]] = {}

    missing_ids = sorted(required_ids - set(by_id))
    if missing_ids:
        errors.append("missing_contribution_statements")
        for pid in missing_ids:
            invalid_statements[pid] = ["missing_contribution_statement"]

    for pid, statement in by_id.items():
        if required_ids and pid not in required_ids:
            continue
        item_errors = []
        for field in STATEMENT_REQUIRED:
            if not _nonempty(statement.get(field)):
                item_errors.append(f"missing_{field}")
        if not _nonempty(_benchmarks(statement)):
            item_errors.append("missing_benchmark_or_task")
        if str(statement.get("evidence_strength") or "") not in STRENGTHS:
            item_errors.append("invalid_evidence_strength")
        if len(str(statement.get("statement") or "")) < 80:
            item_errors.append("statement_too_thin")
        if item_errors:
            invalid_statements[pid] = item_errors

    for field in TREE_REQUIRED:
        if not _nonempty(tree.get(field)):
            errors.append(f"missing_{field}")
    branches = tree.get("branches") or []
    if not isinstance(branches, list):
        errors.append("invalid_contribution_tree")
        branches = []
    statement_ids = set(by_id)
    for branch in branches:
        name = str((branch or {}).get("name") or "<missing>")
        branch_errors = []
        if not isinstance(branch, dict):
            invalid_branches[name] = ["invalid_branch"]
            continue
        for field in BRANCH_REQUIRED:
            if not _nonempty(branch.get(field)):
                branch_errors.append(f"missing_{field}")
        reps = [str(pid) for pid in branch.get("representative_papers") or []]
        if len(reps) < 1:
            branch_errors.append("missing_representative_papers")
        unknown = [pid for pid in reps if pid not in statement_ids]
        if unknown:
            branch_errors.append("unknown_representative_papers:" + ",".join(unknown))
        if branch_errors:
            invalid_branches[name] = branch_errors
    if invalid_statements:
        errors.append("invalid_contribution_statements")
    if invalid_branches or not branches:
        errors.append("invalid_contribution_tree")

    if not _nonempty(graph.get("contribution_tree")) or not _nonempty(graph.get("candidate_spines_from_contribution_tree")):
        errors.append("argument_graph_missing_contribution_tree")

    return {
        "valid": not errors,
        "required": True,
        "errors": sorted(set(errors)),
        "required_a_b_statements": len(required_ids),
        "total_statements": len(statements),
        "branches": len(branches),
        "invalid_statements": invalid_statements,
        "invalid_branches": invalid_branches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-contribution-statements", required=True, type=Path)
    parser.add_argument("--contribution-tree", required=True, type=Path)
    parser.add_argument("--citation-plan", type=Path)
    parser.add_argument("--argument-graph", type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    result = validate_contribution_tree(
        read_jsonl(args.paper_contribution_statements),
        args.contribution_tree.read_text(encoding="utf-8") if args.contribution_tree.exists() else "",
        read_jsonl(args.citation_plan) if args.citation_plan else None,
        args.argument_graph.read_text(encoding="utf-8") if args.argument_graph and args.argument_graph.exists() else None,
        args.target,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
