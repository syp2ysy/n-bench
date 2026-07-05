#!/usr/bin/env python3
"""Mirror legacy mechanism-card JSONL into per-paper v2 card files."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_jsonl, write_json
    from .status_schema import status_envelope
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_jsonl, write_json
    from status_schema import status_envelope


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_id(value: object) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or "").strip()) or "unknown"


def _source_refs(card: dict) -> list[str]:
    refs = card.get("full_text_sources") or card.get("source_refs") or []
    if isinstance(refs, str):
        return [refs]
    return [str(ref) for ref in refs if str(ref).strip()]


def normalize_paper_card(card: dict, full_text_sources: list[dict] | None = None) -> dict:
    paper_id = str(card.get("paper_id") or "").strip()
    source_refs = _source_refs(card)
    evidence_map = card.get("field_evidence_map") or {}
    if not isinstance(evidence_map, dict):
        evidence_map = {"legacy_field_evidence_map": evidence_map}
    return {
        "schema_version": 2,
        "paper_id": paper_id,
        "identity": {
            "title": card.get("title"),
            "level": card.get("level") or card.get("survey_role"),
            "survey_role": card.get("survey_role"),
            "entity_aliases": card.get("entity_aliases") or [],
        },
        "reading_status": {
            "depth": card.get("reading_depth"),
            "full_text_accessed": bool(card.get("full_text_accessed")),
            "source_type": card.get("source_type"),
            "sections_read": card.get("sections_read") or [],
            "source_refs": source_refs,
        },
        "core_understanding": {
            "problem": card.get("problem_setting") or card.get("problem") or "",
            "motivation": card.get("motivation") or "",
            "task_definition": card.get("task_definition") or "",
            "method_pipeline": card.get("method_pipeline") or "",
            "key_design_choices": card.get("key_design_choices") or [],
            "implementation_details": card.get("implementation_details") or "",
            "evaluation_protocol": card.get("experimental_setup") or "",
            "benchmark_or_dataset": card.get("benchmark_or_dataset") or "",
            "main_results": card.get("main_results") or "",
            "limitations": card.get("limitations_and_confounders") or card.get("limitations") or "",
            "what_not_to_claim": card.get("must_not_overclaim") or [],
        },
        "evidence_map": evidence_map,
        "relation_graph": {
            "extends": card.get("extends") or [],
            "contrasts_with": card.get("contrasts_with") or [],
            "uses_benchmark_from": card.get("uses_benchmark_from") or [],
            "is_followed_by": card.get("is_followed_by") or [],
            "is_confused_with": card.get("is_confused_with") or [],
            "relation_to_prior_work": card.get("relation_to_prior_work") or "",
        },
        "survey_use": {
            "possible_sections": card.get("possible_sections") or card.get("survey_sections") or [],
            "supports_claims": card.get("supports_claims") or [],
            "changes_knowledge_tree": card.get("what_it_changes_in_the_survey_argument") or card.get("changes_knowledge_tree") or "",
            "one_sentence_contribution": card.get("one_sentence_contribution") or card.get("contribution_statement") or "",
        },
        "uncertainties": card.get("uncertainties") or [],
        "verifier_result": card.get("verifier_result") or {},
        "legacy_source": "state/paper_mechanism_cards.jsonl",
        "mirrored_at": _utc_now(),
    }


def mirror_paper_cards(task_dir: Path) -> dict:
    state = task_dir / "state"
    card_dir = state / "paper_cards"
    card_dir.mkdir(exist_ok=True)
    full_text_sources = read_jsonl(state / "full_text_sources.jsonl")
    cards = read_jsonl(state / "paper_mechanism_cards.jsonl")
    written = []
    for card in cards:
        paper_id = _safe_id(card.get("paper_id"))
        normalized = normalize_paper_card(card, full_text_sources)
        write_json(card_dir / f"{paper_id}.json", normalized)
        written.append(paper_id)
    return {
        **status_envelope(
            "paper_card_store",
            "mirrored",
            terminal=False,
            blocked=False,
            summary={"card_count": len(written), "canonical": "state/paper_cards"},
        ),
        "paper_ids": written,
    }


def validate_paper_card_store(task_dir: Path) -> dict:
    state = task_dir / "state"
    card_dir = state / "paper_cards"
    citation_plan = read_jsonl(state / "citation_plan.jsonl")
    required_ids = [str(row.get("paper_id")) for row in citation_plan if str(row.get("depth") or row.get("level") or "").upper() in {"A", "B"}]
    missing = []
    invalid = {}
    for paper_id in required_ids:
        path = card_dir / f"{_safe_id(paper_id)}.json"
        if not path.exists():
            missing.append(paper_id)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not ((data.get("survey_use") or {}).get("changes_knowledge_tree")):
            invalid[paper_id] = ["missing_survey_use_changes_knowledge_tree"]
        if not ((data.get("reading_status") or {}).get("source_refs")):
            invalid.setdefault(paper_id, []).append("missing_source_refs")
    valid = not missing and not invalid
    return {
        **status_envelope(
            "paper_card_store",
            "complete" if valid else "blocked",
            terminal=valid,
            blocked=not valid,
            blocked_by_phase=None if valid else "paper_understanding",
            summary={"required_count": len(required_ids), "missing_count": len(missing), "invalid_count": len(invalid)},
        ),
        "valid": valid,
        "missing_paper_cards": missing,
        "invalid_paper_cards": invalid,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--mirror", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.validate:
        result = validate_paper_card_store(args.task_dir)
    else:
        result = mirror_paper_cards(args.task_dir)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("valid", True) or result.get("status") == "mirrored" else 1


if __name__ == "__main__":
    raise SystemExit(main())
