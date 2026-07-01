#!/usr/bin/env python3
"""Validate system-node cards used before deep survey synthesis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


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


def _norm(value) -> str:
    return str(value or "").strip().lower()


def _paper_card_maps(paper_cards: list[dict] | None) -> tuple[set[str], set[str]]:
    paper_ids: set[str] = set()
    nodes: set[str] = set()
    for card in paper_cards or []:
        if card.get("paper_id"):
            paper_ids.add(str(card["paper_id"]))
        node = card.get("system_node") or card.get("memory_node")
        if _nonempty(node):
            nodes.add(_norm(node))
    return paper_ids, nodes


def validate_node_cards(cards: list[dict], paper_cards: list[dict] | None = None) -> dict:
    errors: list[str] = []
    valid_cards = 0
    known_paper_ids, paper_card_nodes = _paper_card_maps(paper_cards)
    node_names = {_norm(card.get("node")) for card in cards if _nonempty(card.get("node"))}
    for idx, card in enumerate(cards, start=1):
        node = card.get("node") or f"node_card_{idx}"
        card_errors: list[str] = []
        status = str(card.get("status") or "covered").lower()
        if status not in {"covered", "weak", "gap"}:
            card_errors.append("status must be covered, weak, or gap")
        for field in ["node", "role_in_system", "inputs", "outputs"]:
            if not _nonempty(card.get(field)):
                card_errors.append(f"missing {field}")
        if not (_nonempty(card.get("why_it_matters")) or _nonempty(card.get("why_it_matters_in_embodiment"))):
            card_errors.append("missing why_it_matters")
        if not _as_list(card.get("main_design_families")):
            card_errors.append("missing main_design_families")
        representative_papers = [str(item) for item in _as_list(card.get("representative_papers")) if _nonempty(item)]
        if status == "gap":
            if not _nonempty(card.get("gap_reason")):
                card_errors.append("gap node requires gap_reason")
        elif len(representative_papers) < 2:
            card_errors.append("representative_papers needs at least 2 entries")
        if known_paper_ids:
            for paper_id in representative_papers:
                if paper_id not in known_paper_ids:
                    card_errors.append(f"unknown representative_paper {paper_id}")
        if not _as_list(card.get("failure_modes")):
            card_errors.append("missing failure_modes")
        if not _as_list(card.get("evaluation_signals")):
            card_errors.append("missing evaluation_signals")
        if not _as_list(card.get("open_questions")):
            card_errors.append("missing open_questions")
        if card_errors:
            errors.append(f"{node}: " + "; ".join(card_errors))
        else:
            valid_cards += 1
    uncovered_nodes = sorted(node for node in paper_card_nodes if node not in node_names and node != "unassigned")
    for node in uncovered_nodes:
        errors.append(f"uncovered paper_card node {node}")
    return {
        "valid": bool(cards) and not errors,
        "total_cards": len(cards),
        "valid_cards": valid_cards,
        "invalid_cards": len(cards) - valid_cards,
        "uncovered_paper_card_nodes": uncovered_nodes,
        "errors": errors,
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-cards", required=True, type=Path)
    parser.add_argument("--paper-cards", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    paper_cards = read_jsonl(args.paper_cards) if args.paper_cards else None
    result = validate_node_cards(read_jsonl(args.node_cards), paper_cards=paper_cards)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
