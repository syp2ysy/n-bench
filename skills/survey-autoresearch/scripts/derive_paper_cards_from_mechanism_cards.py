#!/usr/bin/env python3
"""Derive legacy paper_cards.jsonl records from paper_mechanism_cards.jsonl."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _join_list(value) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value or "")


def derive_paper_cards(mechanism_cards: list[dict]) -> list[dict]:
    cards: list[dict] = []
    for card in mechanism_cards:
        memory = card.get("memory_design") or {}
        experimental = card.get("experimental_setup") or {}
        cards.append(
            {
                "paper_id": card.get("paper_id"),
                "title": card.get("title"),
                "survey_role": card.get("survey_role"),
                "problem": card.get("problem_setting") or card.get("motivation"),
                "method_summary": card.get("method_overview"),
                "system_node": card.get("system_node") or card.get("memory_node") or "",
                "mechanism_or_contribution": card.get("method_overview"),
                "inputs": card.get("inputs") or [],
                "outputs": card.get("outputs") or [],
                "representation": card.get("representation") or memory.get("storage") or "",
                "write_policy": memory.get("write_trigger") or "",
                "read_policy": memory.get("read_key") or "",
                "update_or_consolidation": memory.get("update_policy") or "",
                "controller_interface": memory.get("controller_interface") or "",
                "evaluation_tasks": card.get("benchmark_or_environment") or experimental.get("datasets_envs") or [],
                "datasets_or_envs": experimental.get("datasets_envs") or card.get("benchmark_or_environment") or [],
                "metrics": experimental.get("metrics") or [],
                "baselines": experimental.get("baselines") or [],
                "ablations": experimental.get("ablations") or [],
                "failure_modes": card.get("failure_modes") or card.get("limitations_and_confounders") or [],
                "limitations": card.get("limitations_and_confounders") or [],
                "what_it_teaches_the_survey": card.get("how_it_changes_the_survey_argument") or "",
                "evidence_spans": card.get("evidence_spans") or [],
            }
        )
    return cards


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-mechanism-cards", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    cards = derive_paper_cards(read_jsonl(args.paper_mechanism_cards))
    args.output.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in cards), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
