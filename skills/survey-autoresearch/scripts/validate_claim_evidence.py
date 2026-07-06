#!/usr/bin/env python3
"""Validate claim-to-evidence traceability."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


STRENGTH = {"may indicate": 1, "suggests": 2, "shows": 3, "demonstrates": 4}

DEEP_READING_DEPTH = "full_text_deep_read"
BACKGROUND_CLAIM_TYPES = {"background", "coverage", "related_work", "context"}
FULL_TEXT_CLAIM_TYPES = {
    "method",
    "method_mechanism",
    "mechanism",
    "result",
    "experimental_result",
    "benchmark",
    "benchmark_property",
    "comparison",
    "limitation",
}
METADATA_EVIDENCE_TERMS = {
    "title only",
    "title/abstract only",
    "paper title alone",
    "abstract metadata",
    "abstract only",
    "metadata",
    "semantic scholar",
    "semanticscholar",
    "curated list",
    "curated-list",
    "github list",
    "paper list",
}
PSEUDO_EVIDENCE_TERMS = {
    "section-level full-text evidence",
    "section level full text evidence",
    "full-text evidence supports the section",
    "evidence supports the section",
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _is_deep_read_card(card: dict | None) -> bool:
    return bool(card) and card.get("reading_depth") == DEEP_READING_DEPTH and card.get("full_text_accessed") is True


def _is_metadata_only_span(span: dict) -> bool:
    text = " ".join(
        str(span.get(field) or "").lower()
        for field in ["section_or_page", "evidence_summary", "source_type", "evidence_span"]
    )
    return any(term in text for term in METADATA_EVIDENCE_TERMS)


def _is_pseudo_evidence_span(span: dict) -> bool:
    text = " ".join(
        str(span.get(field) or "").lower()
        for field in ["section_or_page", "evidence_summary", "excerpt", "quoted_excerpt", "evidence_span"]
    )
    return any(term in text for term in PSEUDO_EVIDENCE_TERMS)


def _source_refs(full_text_sources: list[dict] | None) -> dict[str, str]:
    refs: dict[str, str] = {}
    for source in full_text_sources or []:
        ref = str(source.get("source_ref") or source.get("id") or "").strip()
        pid = str(source.get("paper_id") or "").strip()
        if ref and pid:
            refs[ref] = pid
    return refs


def _sources_by_ref(full_text_sources: list[dict] | None) -> dict[str, dict]:
    refs: dict[str, dict] = {}
    for source in full_text_sources or []:
        ref = str(source.get("source_ref") or source.get("id") or "").strip()
        if ref:
            refs[ref] = source
    return refs


def _captured_excerpts(source: dict) -> list[dict]:
    excerpts = source.get("captured_excerpts") or source.get("excerpts") or []
    return excerpts if isinstance(excerpts, list) else []


def _word_overlap(left: str, right: str) -> int:
    left_words = {word for word in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", left.lower()) if len(word) >= 3}
    right_words = {word for word in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", right.lower()) if len(word) >= 3}
    return len(left_words & right_words)


def _span_matches_captured_source(span: dict, source: dict) -> bool:
    excerpts = _captured_excerpts(source)
    if not excerpts:
        return False
    span_excerpt = str(span.get("excerpt") or span.get("quoted_excerpt") or "").strip()
    span_location = str(span.get("section_or_page") or span.get("location") or "").strip().lower()
    for excerpt in excerpts:
        if not isinstance(excerpt, dict):
            continue
        captured_text = str(excerpt.get("excerpt") or excerpt.get("text") or "").strip()
        captured_location = str(excerpt.get("section_or_page") or excerpt.get("location") or "").strip().lower()
        if not captured_text:
            continue
        text_matches = (
            span_excerpt
            and (
                span_excerpt.lower() in captured_text.lower()
                or captured_text.lower() in span_excerpt.lower()
                or _word_overlap(span_excerpt, captured_text) >= 5
            )
        )
        location_matches = bool(span_location and captured_location and (span_location in captured_location or captured_location in span_location))
        if text_matches and (location_matches or _word_overlap(span_location, captured_location) >= 2):
            return True
    return False


def _paper_lookup(mechanism_cards: list[dict]) -> dict[str, dict]:
    result = {}
    for card in mechanism_cards:
        pid = str(card.get("paper_id") or "").strip()
        if pid:
            result[pid] = card
    return result


def _add_alias(aliases: dict[str, set[str]], value, paper_id: str) -> None:
    key = str(value or "").strip().lower()
    if key:
        aliases.setdefault(key, set()).add(paper_id)


def _citation_aliases(mechanism_cards: list[dict]) -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = {}
    for card in mechanism_cards:
        pid = str(card.get("paper_id") or "").strip()
        if not pid:
            continue
        for value in [pid, card.get("citation_key"), card.get("bibtex_key"), card.get("title")]:
            _add_alias(aliases, value, pid)
        for alias in card.get("aliases") or card.get("method_names") or []:
            _add_alias(aliases, alias, pid)
        for alias in card.get("entity_aliases") or []:
            if isinstance(alias, dict):
                _add_alias(aliases, alias.get("name") or alias.get("alias"), pid)
            else:
                _add_alias(aliases, alias, pid)
    return aliases


def _entity_expected_paper_ids(entity, aliases: dict[str, set[str]]) -> set[str]:
    if isinstance(entity, dict):
        pid = str(entity.get("paper_id") or "").strip()
        if pid:
            return {pid}
        name = str(entity.get("name") or entity.get("title") or "").strip().lower()
    else:
        name = str(entity or "").strip().lower()
    return set(aliases.get(name) or [])


def _citation_ids_in_sentence(sentence: str, aliases: dict[str, set[str]]) -> set[str]:
    ids: set[str] = set()
    for match in re.finditer(r"@([A-Za-z0-9_:\-./]+)|\b([Pp]\d{3})\b|(https?://arxiv\.org/abs/[A-Za-z0-9.\-v]+)", sentence):
        key = (match.group(1) or match.group(2) or match.group(3) or "").strip(" ,.;:()[]").lower()
        if not key:
            continue
        resolved = aliases.get(key)
        if resolved:
            ids.update(resolved)
        else:
            ids.add(key)
    return ids


def _arxiv_base(value: str) -> str:
    text = str(value or "").strip().lower().rstrip(".,;:)]")
    match = re.search(r"(?:arxiv\.org/abs/)?(\d{4}\.\d{4,5})(?:v\d+)?", text)
    return match.group(1) if match else ""


def _ids_overlap(left: set[str], right: set[str]) -> bool:
    if left & right:
        return True
    left_bases = {_arxiv_base(item) for item in left}
    right_bases = {_arxiv_base(item) for item in right}
    left_bases.discard("")
    right_bases.discard("")
    return bool(left_bases & right_bases)


ENTITY_STOPWORDS = {
    "Introduction",
    "Conclusion",
    "Conclusions",
    "Survey",
    "Table",
    "Figure",
    "Section",
    "Appendix",
    "Benchmark",
    "Method",
    "Methods",
    "Results",
    "Discussion",
    "Future",
    "This",
    "The",
}


def _looks_like_unregistered_method(entity: str) -> bool:
    text = str(entity or "").strip()
    if not text:
        return False
    if " " in text:
        return False
    if len(text) < 5:
        return False
    if re.fullmatch(r"[A-Z0-9-]+s?", text):
        return False
    if text.lower().endswith(("-style", "-family")):
        return False
    return bool(re.search(r"[A-Z].*[A-Z]|\d|-", text))


def _is_generic_alignment_entity(entity: str) -> bool:
    text = str(entity or "").strip()
    return bool(re.fullmatch(r"(SFT|RL|IoU|QA|CoT|LLM|LLMs|VLM|VLMs|LVLM|LVLMs|GRPO)", text))


def _candidate_named_entities(sentence: str) -> list[str]:
    stripped = re.sub(r"\[@?[^\]]+\]|@[A-Za-z0-9_:\-./]+|https?://\S+", " ", sentence)
    candidates: list[str] = []
    patterns = [
        r"\b(?:[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)?)(?:\s+(?:[A-Z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)?|\d+))+\b",
        r"\b[A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9-]*\b",
        r"\b[A-Za-z]+[A-Za-z-]*\d+[A-Za-z0-9-]*\b",
        r"\b[A-Z]{3,}[A-Za-z0-9-]*\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, stripped):
            entity = match.group(0).strip(" ,.;:()[]")
            if not entity or entity in ENTITY_STOPWORDS:
                continue
            if entity.lower().startswith(("section ", "figure ", "table ")):
                continue
            candidates.append(entity)
    deduped = []
    seen = set()
    for entity in candidates:
        key = entity.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(entity)
    return deduped


def _article_alignment_errors(article_text: str, aliases: dict[str, set[str]]) -> list[str]:
    if not article_text:
        return []
    errors: list[str] = []
    normalized = re.sub(r"\s+", " ", article_text)
    sentences = re.split(r"(?<=[。！？.!?])\s+", normalized)
    for sentence in sentences:
        cited = _citation_ids_in_sentence(sentence, aliases)
        if not cited:
            continue
        sentence_lower = sentence.lower()
        expected: set[str] = set()
        for entity in _candidate_named_entities(sentence):
            resolved = aliases.get(entity.lower())
            if resolved:
                if _is_generic_alignment_entity(entity):
                    continue
                if _ids_overlap(resolved, cited):
                    continue
                if len(resolved) == 1:
                    expected.update(resolved)
            elif _looks_like_unregistered_method(entity):
                errors.append(f"unregistered_named_entity_near_citation:{entity}")
        missing = sorted(expected - cited)
        if missing:
            errors.append("named_paper_citation_mismatch:" + ",".join(missing))
    return sorted(set(errors))


def _span_has_excerpt(span: dict) -> bool:
    text = str(span.get("excerpt") or span.get("quoted_excerpt") or "").strip()
    return len(text) >= 24


def validate_claim_evidence(
    claims: list[dict],
    mechanism_cards: list[dict],
    section_plans: list[dict] | None = None,
    full_text_sources: list[dict] | None = None,
    article_text: str = "",
) -> dict:
    card_ids = {str(card.get("paper_id")) for card in mechanism_cards if card.get("paper_id")}
    cards_by_id = _paper_lookup(mechanism_cards)
    aliases = _citation_aliases(mechanism_cards)
    source_refs = _source_refs(full_text_sources)
    sources_by_ref = _sources_by_ref(full_text_sources)
    planned_claims = set()
    for plan in section_plans or []:
        for claim_id in plan.get("must_include_evidence_spans") or []:
            planned_claims.add(str(claim_id))
    errors: list[str] = []
    invalid_claims: dict[str, list[str]] = {}
    for claim in claims:
        claim_id = str(claim.get("claim_id") or claim.get("id") or "<missing>")
        claim_errors = []
        if not claim.get("claim"):
            claim_errors.append("missing_claim_text")
        claim_type = str(claim.get("claim_type") or "").lower()
        claim_strength = str(claim.get("strength") or "").lower()
        if claim_strength not in STRENGTH:
            claim_errors.append("invalid_claim_strength")
        cited_paper_ids = {str(pid) for pid in claim.get("cited_paper_ids") or claim.get("paper_ids") or [] if str(pid)}
        named_entities = claim.get("named_entities") or []
        if named_entities:
            if not cited_paper_ids:
                claim_errors.append("named_entities_missing_cited_paper_ids")
            for entity in named_entities:
                expected_ids = _entity_expected_paper_ids(entity, aliases)
                if not expected_ids:
                    claim_errors.append("unknown_named_entity")
                    continue
                if not expected_ids & cited_paper_ids:
                    claim_errors.append("named_entity_citation_mismatch")
        if section_plans is not None and STRENGTH.get(claim_strength, 0) >= STRENGTH["shows"] and claim_id not in planned_claims:
            claim_errors.append("strong_claim_missing_section_plan")
        spans = claim.get("evidence_spans") or []
        if not isinstance(spans, list) or not spans:
            claim_errors.append("missing_evidence_spans")
        for span in spans if isinstance(spans, list) else []:
            paper_id = str(span.get("paper_id") or "")
            span_strength = str(span.get("strength") or "").lower()
            is_strong_or_full_text = (
                claim_type in FULL_TEXT_CLAIM_TYPES
                or (claim_type not in BACKGROUND_CLAIM_TYPES and STRENGTH.get(claim_strength, 0) >= STRENGTH["shows"])
            )
            if paper_id not in card_ids:
                claim_errors.append(f"unknown_paper:{paper_id}")
            elif is_strong_or_full_text and not _is_deep_read_card(cards_by_id.get(paper_id)):
                claim_errors.append(f"claim_requires_full_text_deep_read:{paper_id}")
            if not span.get("section_or_page") or not span.get("evidence_summary"):
                claim_errors.append(f"incomplete_span:{paper_id}")
            if _is_metadata_only_span(span) and is_strong_or_full_text:
                claim_errors.append(f"metadata_only_span_for_strong_claim:{paper_id}")
            if _is_pseudo_evidence_span(span) and is_strong_or_full_text:
                claim_errors.append(f"pseudo_evidence_span_for_strong_claim:{paper_id}")
            if is_strong_or_full_text:
                if not _span_has_excerpt(span):
                    claim_errors.append(f"strong_claim_missing_excerpt:{paper_id}")
                source_ref = str(span.get("source_ref") or "").strip()
                if full_text_sources is not None:
                    if not source_ref:
                        claim_errors.append(f"strong_claim_missing_source_ref:{paper_id}")
                    elif source_ref not in source_refs:
                        claim_errors.append(f"unknown_source_ref:{source_ref}")
                    elif source_refs[source_ref] != paper_id:
                        claim_errors.append(f"source_ref_paper_mismatch:{source_ref}")
                    elif not _span_matches_captured_source(span, sources_by_ref.get(source_ref, {})):
                        claim_errors.append(f"strong_claim_excerpt_not_in_full_text_audit:{source_ref}")
            if span_strength not in STRENGTH:
                claim_errors.append(f"invalid_span_strength:{paper_id}")
            elif claim_strength in STRENGTH and STRENGTH[claim_strength] > STRENGTH[span_strength]:
                claim_errors.append(f"claim_strength_exceeds_evidence:{paper_id}")
        span_paper_ids = {str(span.get("paper_id") or "") for span in spans if isinstance(span, dict)}
        if cited_paper_ids and not cited_paper_ids <= span_paper_ids:
            claim_errors.append("cited_papers_missing_from_evidence_spans")
        if claim_errors:
            invalid_claims[claim_id] = sorted(set(claim_errors))
    article_alignment_errors = _article_alignment_errors(article_text, aliases)
    if article_alignment_errors:
        errors.append("named_paper_citation_alignment")
    if invalid_claims:
        errors.append("invalid_claim_evidence")
    return {
        "valid": not errors,
        "errors": errors,
        "total_claims": len(claims),
        "invalid_claims": invalid_claims,
        "article_alignment_errors": article_alignment_errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", required=True, type=Path)
    parser.add_argument("--paper-mechanism-cards", required=True, type=Path)
    parser.add_argument("--section-evidence-plans", type=Path)
    parser.add_argument("--full-text-sources", type=Path)
    parser.add_argument("--survey", type=Path)
    args = parser.parse_args()
    result = validate_claim_evidence(
        read_jsonl(args.claims),
        read_jsonl(args.paper_mechanism_cards),
        read_jsonl(args.section_evidence_plans) if args.section_evidence_plans else None,
        read_jsonl(args.full_text_sources) if args.full_text_sources else None,
        args.survey.read_text(encoding="utf-8") if args.survey and args.survey.exists() else "",
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
