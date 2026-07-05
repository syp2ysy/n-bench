#!/usr/bin/env python3
"""Validate semantic related-survey alignment records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TARGET_MIN_RECORDS = {"short": 1, "full": 6, "csur": 10}
SUPPORT_FIELDS = ["method_pipeline", "benchmark_or_dataset", "main_results"]
TOP_RELATED_SURVEY_FIELDS = [
    "why_selected_as_top_related_survey",
    "coverage_overlap",
    "coverage_gap",
    "taxonomy_delta",
    "article_taxonomy_necessity",
]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _list_len(value) -> int:
    if isinstance(value, (list, tuple, set)):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, str):
        return 1 if value.strip() else 0
    return 1 if value else 0


def _paper_index(cards: list[dict] | None) -> dict[str, dict]:
    return {str(card.get("paper_id")): card for card in cards or [] if card.get("paper_id")}


def _verified_retained_papers(papers: list[dict] | None) -> set[str]:
    ids: set[str] = set()
    for paper in papers or []:
        pid = str(paper.get("paper_id") or "").strip()
        if not pid:
            continue
        if paper.get("verified") is True or str(paper.get("verification_status") or "").lower() == "verified":
            ids.add(pid)
    return ids


def _direct_related_audit_ids(topic_relevance_audit: list[dict] | None) -> set[str]:
    ids: set[str] = set()
    for row in topic_relevance_audit or []:
        pid = str(row.get("paper_id") or "").strip()
        if (
            pid
            and str(row.get("relevance_grade") or "") == "direct_related_survey"
            and str(row.get("allowed_role") or "") == "related_survey"
        ):
            ids.add(pid)
    return ids


def _support_is_evidence_backed(card: dict) -> bool:
    if card.get("full_text_accessed") is not True:
        return False
    field_map = card.get("field_evidence_map")
    if not isinstance(field_map, dict):
        return False
    for field in SUPPORT_FIELDS:
        entries = field_map.get(field)
        if not isinstance(entries, list) or not entries:
            return False
        if not any(isinstance(entry, dict) and _nonempty(entry.get("source_ref")) and _nonempty(entry.get("evidence_span") or entry.get("excerpt") or entry.get("evidence_summary")) for entry in entries):
            return False
    return True


def _mapping_errors(mapping: dict, idx: int, cards: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    for field in ["article_category", "supporting_a_b_papers"]:
        if not _nonempty(mapping.get(field)):
            errors.append(f"mapping_missing_{field}:{idx}")
    if not _nonempty(mapping.get("existing_category") or mapping.get("exemplar_category")):
        errors.append(f"mapping_missing_existing_category:{idx}")
    if not _nonempty(mapping.get("agreement") or mapping.get("delta") or mapping.get("agreement_or_delta")):
        errors.append(f"mapping_missing_agreement_or_delta:{idx}")
    if not _nonempty(mapping.get("why_delta_is_needed") or mapping.get("why_delta_is_justified") or mapping.get("justification")):
        errors.append(f"mapping_missing_delta_justification:{idx}")
    support = [str(pid) for pid in mapping.get("supporting_a_b_papers") or []]
    for pid in support:
        card = cards.get(pid)
        if not card:
            errors.append(f"mapping_unknown_supporting_paper:{idx}:{pid}")
        elif not _support_is_evidence_backed(card):
            errors.append(f"mapping_support_not_evidence_backed:{idx}:{pid}")
    return errors


def validate_related_survey_alignment(
    records: list[dict] | None,
    mechanism_cards: list[dict] | None,
    target: str = "full",
    papers: list[dict] | None = None,
    topic_relevance_audit: list[dict] | None = None,
    citation_plan: list[dict] | None = None,
) -> dict:
    records = records or []
    cards = _paper_index(mechanism_cards)
    enforce_source_topic_link = target in {"full", "csur"} and papers is not None and topic_relevance_audit is not None
    verified_retained = _verified_retained_papers(papers)
    direct_related = _direct_related_audit_ids(topic_relevance_audit)
    min_records = TARGET_MIN_RECORDS[target]
    errors: list[str] = []
    invalid_records: dict[str, list[str]] = {}

    if len(records) < min_records:
        errors.append("too_few_related_survey_alignments")

    for idx, record in enumerate(records, start=1):
        key = str(record.get("exemplar_id") or record.get("related_survey_id") or record.get("title") or f"related_survey_{idx}")
        item_errors: list[str] = []
        for field in ["title", "survey_type", "existing_taxonomy", "article_taxonomy_mapping"]:
            if not _nonempty(record.get(field)):
                item_errors.append(f"missing_{field}")
        if target in {"full", "csur"}:
            for field in TOP_RELATED_SURVEY_FIELDS:
                if not _nonempty(record.get(field)):
                    item_errors.append(f"missing_{field}")
        if enforce_source_topic_link:
            source_paper_id = str(record.get("paper_id") or record.get("source_paper_id") or "").strip()
            if not source_paper_id:
                item_errors.append("missing_related_survey_paper_id")
            else:
                if source_paper_id not in verified_retained:
                    item_errors.append("related_survey_not_verified_retained")
                if source_paper_id not in direct_related:
                    item_errors.append("related_survey_not_direct_topic_audit")
        if not _nonempty(record.get("source_ref") or record.get("evidence_ref") or record.get("verified_source")):
            item_errors.append("missing_verified_source_ref")
        if record.get("verified") is False or str(record.get("verification_status") or "verified").lower() not in {"verified", "peer-reviewed", "accepted", "arxiv"}:
            item_errors.append("unverified_related_survey")
        if _list_len(record.get("existing_taxonomy")) < 2:
            item_errors.append("existing_taxonomy_too_thin")
        if _list_len(record.get("section_extractions") or record.get("extracted_sections")) < 2:
            item_errors.append("missing_section_extractions")
        if not _nonempty(record.get("taxonomy_evidence") or record.get("taxonomy_source_ref")):
            item_errors.append("missing_taxonomy_evidence")
        mappings = record.get("article_taxonomy_mapping") or []
        if not isinstance(mappings, list) or not mappings:
            item_errors.append("missing_article_taxonomy_mapping")
        else:
            for midx, mapping in enumerate(mappings, start=1):
                if not isinstance(mapping, dict):
                    item_errors.append(f"invalid_mapping:{midx}")
                    continue
                item_errors.extend(_mapping_errors(mapping, midx, cards))
        if not _nonempty(record.get("article_delta") or record.get("delta")):
            item_errors.append("missing_article_delta")
        if not _nonempty(record.get("why_delta_is_justified")):
            item_errors.append("missing_why_delta_is_justified")
        if item_errors:
            invalid_records[key] = sorted(set(item_errors))

    if invalid_records:
        errors.append("invalid_related_survey_alignment")
    return {
        "valid": not errors,
        "required": target in TARGET_MIN_RECORDS,
        "target_min_records": min_records,
        "record_count": len(records),
        "errors": sorted(set(errors)),
        "invalid_records": invalid_records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy-alignment", required=True, type=Path)
    parser.add_argument("--paper-mechanism-cards", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    result = validate_related_survey_alignment(
        read_jsonl(args.taxonomy_alignment),
        read_jsonl(args.paper_mechanism_cards),
        args.target,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
