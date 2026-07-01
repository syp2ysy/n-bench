#!/usr/bin/env python3
"""Report missing cross-links among deep synthesis artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _norm(value) -> str:
    return str(value or "").strip().lower()


def analyze_missing_deep_artifacts(
    citation_plan: list[dict],
    paper_cards: list[dict],
    node_cards: list[dict],
    section_cards: list[dict],
    claims: list[dict] | None = None,
    outputs_dir: Path | None = None,
) -> dict:
    ab_ids = {
        item.get("paper_id")
        for item in citation_plan
        if (item.get("depth") or "").upper() in {"A", "B"} and item.get("paper_id")
    }
    card_ids = {item.get("paper_id") for item in paper_cards if item.get("paper_id")}
    card_nodes = {
        _norm(item.get("system_node") or item.get("memory_node"))
        for item in paper_cards
        if item.get("system_node") or item.get("memory_node")
    }
    node_names = {_norm(item.get("node")) for item in node_cards if item.get("node")}
    section_ids = {str(item.get("section_id")) for item in section_cards if item.get("section_id")}
    section_titles = {str(item.get("title")) for item in section_cards if item.get("title")}
    claims_without_card_trace = []
    for claim in claims or []:
        for paper_id in claim.get("paper_ids") or []:
            if paper_id not in card_ids:
                claims_without_card_trace.append(claim.get("claim_id") or paper_id)
                break
    missing_output_artifacts: list[str] = []
    section_dossiers = 0
    if outputs_dir is not None:
        required_outputs = [
            "worked_examples.md",
            "benchmark_landscape.md",
            "method_taxonomy.md",
            "node_paper_matrix.md",
            "glossary.md",
            "running_example.md",
            "evaluation_protocol.md",
            "design_guidelines.md",
        ]
        missing_output_artifacts = [
            f"outputs/{name}"
            for name in required_outputs
            if not (outputs_dir / name).exists() or not (outputs_dir / name).read_text(encoding="utf-8").strip()
        ]
        dossier_dir = outputs_dir / "section_dossiers"
        section_dossiers = len(list(dossier_dir.glob("*.md"))) if dossier_dir.exists() else 0
        if section_dossiers == 0:
            missing_output_artifacts.append("outputs/section_dossiers")
    return {
        "missing_paper_cards": sorted(ab_ids - card_ids),
        "uncovered_system_nodes": sorted(node for node in card_nodes - node_names if node),
        "paper_cards_without_node": sorted(item.get("paper_id") for item in paper_cards if not (item.get("system_node") or item.get("memory_node"))),
        "sections_without_cards": sorted(set() if section_ids or section_titles else {"review_sections_unknown"}),
        "claims_without_card_trace": sorted(set(claims_without_card_trace)),
        "missing_output_artifacts": missing_output_artifacts,
        "section_dossiers": section_dossiers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    state = args.task_dir / "state"
    result = analyze_missing_deep_artifacts(
        read_jsonl(state / "citation_plan.jsonl"),
        read_jsonl(state / "paper_cards.jsonl"),
        read_jsonl(state / "system_node_cards.jsonl"),
        read_jsonl(state / "section_cards.jsonl"),
        read_jsonl(state / "claims.jsonl"),
        args.task_dir / "outputs",
    )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
