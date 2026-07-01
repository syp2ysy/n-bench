#!/usr/bin/env python3
"""Check whether final review absorbs deep artifacts instead of only coexisting with them."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _ab_ids(citation_plan: list[dict]) -> set[str]:
    return {
        item["paper_id"]
        for item in citation_plan
        if item.get("paper_id") and str(item.get("depth") or "").upper() in {"A", "B"}
    }


def _contains_identifier(text: str, paper_id: str, title: str | None) -> bool:
    if paper_id and paper_id in text:
        return True
    if title:
        title_words = [word for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{3,}", title) if len(word) > 3]
        return bool(title_words) and sum(1 for word in title_words[:5] if word.lower() in text.lower()) >= min(2, len(title_words))
    return False


def validate_review_absorption(task_dir: Path, target: str = "full") -> dict:
    if target not in {"full", "csur"}:
        return {"valid": True, "required": False, "failed_checks": []}
    state_dir = task_dir / "state"
    outputs_dir = task_dir / "outputs"
    review = (outputs_dir / "review.md").read_text(encoding="utf-8") if (outputs_dir / "review.md").exists() else ""
    citation_plan = read_jsonl(state_dir / "citation_plan.jsonl")
    cards = read_jsonl(state_dir / "paper_cards.jsonl")
    card_by_id = {item.get("paper_id"): item for item in cards if item.get("paper_id")}
    required_ids = _ab_ids(citation_plan)
    missing_papers = [
        paper_id
        for paper_id in sorted(required_ids)
        if not _contains_identifier(review, paper_id, card_by_id.get(paper_id, {}).get("title"))
    ]

    required_review_terms = {
        "worked_examples": ["worked example", "worked paper", "案例", "paper example"],
        "benchmark_landscape": ["benchmark landscape", "memory pressure", "confounders", "baseline", "基准"],
        "method_taxonomy": ["method taxonomy", "write trigger", "read key", "update policy", "controller interface", "方法"],
        "node_matrix": ["node", "representative papers", "mechanism pattern", "evaluation signal", "系统节点"],
        "newcomer": ["tutorial primer", "glossary", "running example", "入门", "术语", "贯穿例子"],
    }
    missing_terms = [
        name for name, terms in required_review_terms.items()
        if not any(term.lower() in review.lower() for term in terms)
    ]
    required_files = [
        "worked_examples.md",
        "benchmark_landscape.md",
        "method_taxonomy.md",
        "node_paper_matrix.md",
        "glossary.md",
        "running_example.md",
        "evaluation_protocol.md",
        "design_guidelines.md",
    ]
    missing_files = [
        f"outputs/{name}" for name in required_files
        if not (outputs_dir / name).exists() or not (outputs_dir / name).read_text(encoding="utf-8").strip()
    ]
    dossier_dir = outputs_dir / "section_dossiers"
    dossier_count = len(list(dossier_dir.glob("*.md"))) if dossier_dir.exists() else 0
    failed = []
    if missing_papers:
        failed.append("missing_worked_paper_absorption")
    if missing_terms:
        failed.append("missing_review_artifact_absorption")
    if "newcomer" in missing_terms:
        failed.append("missing_newcomer_artifact_absorption")
    if missing_files or dossier_count == 0:
        failed.append("missing_newcomer_artifact_absorption")
    return {
        "valid": not failed,
        "required": True,
        "target": target,
        "failed_checks": failed,
        "missing_papers": missing_papers,
        "missing_review_terms": missing_terms,
        "missing_files": missing_files,
        "section_dossiers": dossier_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_review_absorption(args.task_dir, args.target)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
