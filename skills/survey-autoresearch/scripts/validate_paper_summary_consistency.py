#!/usr/bin/env python3
"""Check whether mechanism-card summaries are supported by evidence notes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


STRONG_WORDS = {"demonstrates", "demonstrate", "proves", "prove", "establishes", "establish"}


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _flatten_text(value) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(v) for v in value)
    return str(value or "")


def _tokens(text: str) -> list[str]:
    return [tok.lower() for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{2,}", text)]


def _covered(term: str, evidence_text: str) -> bool:
    term_lower = term.lower()
    if term_lower in evidence_text:
        return True
    tokens = _tokens(term)
    if not tokens:
        return False
    return all(token in evidence_text for token in tokens[:3])


def validate_paper_summary_consistency(cards: list[dict]) -> dict:
    errors: list[str] = []
    invalid_papers: list[str] = []
    for idx, card in enumerate(cards, start=1):
        paper_id = card.get("paper_id") or f"mechanism_card_{idx}"
        card_errors: list[str] = []
        evidence_text = _flatten_text(card.get("evidence_spans")).lower()
        experimental = card.get("experimental_setup") or {}
        for ablation in _as_list(experimental.get("ablations")):
            if ablation and not _covered(str(ablation), evidence_text):
                card_errors.append(f"unsupported ablation {ablation}")
        for baseline in _as_list(experimental.get("baselines")):
            if baseline and not _covered(str(baseline), evidence_text):
                card_errors.append(f"unsupported baseline {baseline}")
        for result in _as_list(card.get("main_results")):
            if not isinstance(result, dict):
                continue
            strength = str(result.get("strength") or "").lower()
            claim = str(result.get("claim") or "").lower()
            if strength == "demonstrates" and not any(word in evidence_text for word in ["ablation", "controlled", "direct", "formal", "table", "experiment"]):
                card_errors.append("strong result lacks direct evidence cue")
            if any(word in claim for word in STRONG_WORDS) and strength not in {"demonstrates", "shows"}:
                card_errors.append("claim wording stronger than result strength")
        role = str(card.get("survey_role") or "").lower()
        if role == "benchmark" and card.get("method_overview") and "benchmark" not in str(card.get("method_overview")).lower():
            if not card.get("unsupported_role_override"):
                card_errors.append("benchmark paper described like method without override")
        if card_errors:
            invalid_papers.append(paper_id)
            errors.append(f"{paper_id}: " + "; ".join(card_errors))
    return {
        "valid": not errors,
        "total_cards": len(cards),
        "invalid_papers": sorted(set(invalid_papers)),
        "errors": errors,
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-mechanism-cards", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_paper_summary_consistency(read_jsonl(args.paper_mechanism_cards))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
