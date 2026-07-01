#!/usr/bin/env python3
"""Reject generic paper cards that satisfy schema but lack paper-specific mechanisms."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


GENERIC_PHRASES = [
    "task success or answer accuracy",
    "memory ablation effect",
    "grounding/latency/update signals where reported",
    "may not isolate memory from perception",
    "records are written from observations",
    "memory is read by semantic",
    "when available",
]


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _looks_specific(card: dict) -> bool:
    title = str(card.get("title") or "")
    mechanism = str(card.get("mechanism_or_contribution") or "")
    datasets = " ".join(str(item) for item in card.get("datasets_or_envs") or [])
    baselines = " ".join(str(item) for item in card.get("baselines") or [])
    ablations = " ".join(str(item) for item in card.get("ablations") or [])
    text = " ".join([mechanism, datasets, baselines, ablations])
    title_tokens = [tok.lower() for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{2,}", title)]
    has_title_token = any(tok in text.lower() for tok in title_tokens[:6])
    has_specific_marker = bool(re.search(r"\b(table|section|benchmark|dataset|module|graph|map|planner|policy|retrieval|oracle|wrong|stale|no-memory)\b", text, flags=re.IGNORECASE))
    return has_title_token or has_specific_marker


def validate_card_specificity(cards: list[dict]) -> dict:
    errors: list[str] = []
    for idx, card in enumerate(cards, start=1):
        paper_id = card.get("paper_id") or f"card_{idx}"
        joined = " ".join(
            str(card.get(field) or "")
            for field in ["mechanism_or_contribution", "write_policy", "read_policy", "update_or_consolidation", "controller_interface"]
        ).lower()
        if any(phrase in joined for phrase in GENERIC_PHRASES):
            errors.append(f"{paper_id}: generic_card uses template phrases")
        if not _looks_specific(card):
            errors.append(f"{paper_id}: generic_card lacks paper-specific mechanism markers")
        if not _nonempty(card.get("evidence_spans")):
            errors.append(f"{paper_id}: missing evidence_spans")
    return {
        "valid": bool(cards) and not errors,
        "total_cards": len(cards),
        "errors": errors,
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-cards", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_card_specificity(read_jsonl(args.paper_cards))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
