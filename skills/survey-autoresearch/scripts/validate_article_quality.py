#!/usr/bin/env python3
"""Validate publication article quality and boundary."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FORBIDDEN_PATTERNS = [
    r"本文采用[^。\n]{0,80}survey[^。\n]{0,40}结构",
    r"\b[ABC][- ]level\b",
    r"\bdesign signal\b",
    r"\banchor evidence\b",
    r"候选文献",
    r"深读文献",
    r"检索和筛选围绕",
    r"文献被分为",
    r"证据层级",
    r"调研设计",
    r"本节面向",
    r"下面的表",
    r"该工作在本文中被读作",
    r"好的综述",
    r"好的方法",
    r"state file",
    r"gate check",
    r"paper card",
    r"article-facing",
    r"supporting material",
    r"支撑文件",
    r"正文选择",
    r"worked example\s*集合",
    r"材料保留在",
    r"完整[^。\n]{0,60}material",
    r"full node-paper material",
    r"新版\s*skill",
    r"full[- ]text\s*A/B\s*audited",
    r"source_ref",
    r"science paradigm profile",
    r"evidence norms?",
    r"run counts?",
    r"candidate counts?",
    r"本综述不再把",
    r"那种[^。\n]{0,80}视角",
    r"不是[^。\n]{0,80}文章\s*spine",
    r"更合适的主线是",
    r"cross[- ]cutting diagnostic lens",
    r"在[“\"][^”\"]{1,80}[”\"]这一问题上",
    r"HTML reference note",
    r"generated references placeholder",
    r"rendered reference note",
]

METHOD_SECTION_HEADING_TERMS = ["method", "taxonomy", "famil", "方法", "分类", "谱系", "路线"]
TRADEOFF_MARKERS = [
    r"trade[- ]?off",
    r"whereas",
    r"\bwhile\b",
    r"tension",
    r"alternative",
    r"conflict",
    r"different pipelines",
    r"相比",
    r"取舍",
    r"张力",
    r"不同路线",
    r"替代",
    r"冲突",
]
BENCHMARK_SECTION_HEADING_TERMS = ["benchmark", "evaluation", "评测", "基准", "实验"]
EVALUATION_RECIPE_MARKERS = [
    "protocol",
    "metric",
    "baseline",
    "ablation",
    "confounder",
    "control",
    "recipe",
    "协议",
    "指标",
    "基线",
    "消融",
    "混淆",
    "对照",
]
EXPANSION_REQUIRED_FIELDS = [
    "section",
    "problem_type",
    "current_quote",
    "why_expansion_is_needed",
    "allowed_expansion",
    "required_evidence_refs",
    "must_not_change",
    "estimated_added_words",
]
EXPANSION_STATUSES = {"pending", "addressed", "waived"}
CONCLUSION_HEADING_RE = re.compile(r"^(conclusion|conclusions|结论|总结|结语|take[- ]?home findings?)$", re.IGNORECASE)
BACKMATTER_HEADING_RE = re.compile(r"(references|bibliography|appendix|acknowledg|参考文献|附录|致谢)", re.IGNORECASE)
PRESCRIPTIVE_RE = re.compile(r"(未来应当|未来应该|研究者应该|本文认为|should|must|need to|needs to|ought to)", re.IGNORECASE)
CITATION_RE = re.compile(r"@\w|\\cite|\bp\d{3}\b|\[[^\]]*\d{4}[^\]]*\]", re.IGNORECASE)
SCHOLARLY_CITATION_KEY_RE = re.compile(r"@\w+|\\cite\{[^}]+\}")
COMPARISON_RE = re.compile(r"compared|comparison|whereas|while|baseline|ablation|metric|paper|study|相比|对比|基线|消融|指标|论文|研究", re.IGNORECASE)
LEGACY_STEM = "review"
LEGACY_ARTIFACT_NAMES = {LEGACY_STEM + ".md", LEGACY_STEM + "_body_draft.md", LEGACY_STEM + ".html"}
BARE_INTERNAL_PAPER_ID_RE = re.compile(r"\bP\d{3}\b")
TEMPLATE_EVIDENCE_RE = re.compile(r"(相关证据见|证据见|该类工作说明|相关工作说明)")
RELATED_SURVEY_RE = re.compile(r"(related surveys?|existing surveys?|prior surveys?|已有综述|相关综述|既有综述)", re.IGNORECASE)
TAXONOMY_ALIGNMENT_RE = re.compile(r"(taxonomy|classification|scope|coverage|delta|difference|gap|分类|范围|覆盖|差异|增量|缺口)", re.IGNORECASE)
ARTICLE_TAXONOMY_RE = re.compile(r"(this (survey|article)|our (survey|article)|本文|本综述).{0,120}(taxonomy|classification|spine|scope|coverage|分类|主线|范围|覆盖)", re.IGNORECASE)
EXISTING_TAXONOMY_RE = re.compile(r"(existing|prior|related|已有|相关|既有).{0,80}(survey|review|综述).{0,120}(taxonomy|classification|scope|coverage|分类|范围|覆盖)", re.IGNORECASE)
DELTA_RE = re.compile(r"(delta|difference|gap|increment|differs|contrast|相比|不同|差异|增量|缺口)", re.IGNORECASE)
RELATED_SURVEY_CITATION_FLOOR = {"full": 4, "csur": 6}
EXISTING_COVERAGE_RE = re.compile(r"(existing|prior|related|已有|相关|既有).{0,100}(coverage|cover|scope|covered|覆盖|范围)", re.IGNORECASE)
COVERAGE_GAP_RE = re.compile(r"(coverage gap|gap in coverage|not cover|uncovered|missing coverage|覆盖缺口|未覆盖|没有覆盖|缺口|不足)", re.IGNORECASE)
TAXONOMY_DELTA_RE = re.compile(r"(taxonomy delta|delta in taxonomy|taxonomy difference|taxonomy differs|分类差异|分类增量|taxonomy.{0,80}(delta|difference|gap|differs)|分类.{0,80}(差异|增量|缺口))", re.IGNORECASE)
TAXONOMY_NECESSITY_RE = re.compile(r"(why this article taxonomy is needed|why .*taxonomy.*(needed|necessary)|taxonomy.*(needed|necessary)|为什么.*分类.*必要|分类.*必要|taxonomy necessity)", re.IGNORECASE)


def _plain(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("|"))
    text = re.sub(r"[#>*`_\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))
    sections = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[match.end():end].strip()))
    return sections


def _table_blocks(text: str):
    return list(re.finditer(r"(?:^\|.*\|\n)+", text, flags=re.MULTILINE))


def _claim_texts(claims: list[dict]) -> list[str]:
    result = []
    for claim in claims:
        text = str(claim.get("claim") or "").strip()
        if len(text) >= 30:
            result.append(text)
    return result


def _rendered_artifact_items(rendered_artifacts) -> list[tuple[str, str]]:
    result = []
    for item in rendered_artifacts or []:
        if isinstance(item, tuple) and len(item) == 2:
            result.append((str(item[0]), str(item[1])))
        elif isinstance(item, dict):
            result.append((str(item.get("path") or item.get("name") or "<rendered>"), str(item.get("text") or item.get("content") or "")))
        else:
            result.append(("<rendered>", str(item)))
    return result


def _forbidden_hits(text: str) -> list[str]:
    return [pattern for pattern in FORBIDDEN_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE)]


def _paragraphs(text: str) -> list[str]:
    chunks = []
    for paragraph in re.split(r"\n\s*\n+", text):
        stripped = paragraph.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("```"):
            continue
        plain = _plain(stripped)
        if len(plain) >= 50:
            chunks.append(plain)
    return chunks


def _repeated_paragraphs(text: str) -> list[str]:
    counts: dict[str, int] = {}
    originals: dict[str, str] = {}
    for paragraph in _paragraphs(text):
        normalized = re.sub(r"\W+", " ", paragraph.lower()).strip()
        if len(normalized) < 50:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
        originals.setdefault(normalized, paragraph[:120])
    return [originals[key] for key, count in counts.items() if count >= 3]


def _generic_sentence_repetitions(text: str) -> list[str]:
    counts: dict[str, int] = {}
    originals: dict[str, str] = {}
    for sentence in re.split(r"(?<=[。！？.!?])\s+", _plain(text)):
        normalized = re.sub(r"\W+", " ", sentence.lower()).strip()
        if len(normalized) < 60:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
        originals.setdefault(normalized, sentence[:120])
    return [originals[key] for key, count in counts.items() if count >= 3]


def _conclusion_order_errors(sections: list[tuple[str, str]]) -> list[str]:
    errors = []
    conclusion_idx = None
    for idx, (heading, _body) in enumerate(sections):
        if CONCLUSION_HEADING_RE.search(heading.strip()):
            conclusion_idx = idx
            break
    if conclusion_idx is None:
        return errors
    for heading, _body in sections[conclusion_idx + 1:]:
        if not BACKMATTER_HEADING_RE.search(heading):
            errors.append(heading)
    return errors


def _prescriptive_padding(text: str) -> list[str]:
    counts: dict[str, int] = {}
    originals: dict[str, str] = {}
    for sentence in re.split(r"(?<=[。！？.!?])\s+", _plain(text)):
        if not PRESCRIPTIVE_RE.search(sentence):
            continue
        normalized = re.sub(r"\W+", " ", sentence.lower()).strip()
        if len(normalized) < 6:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
        originals.setdefault(normalized, sentence[:120])
    return [originals[key] for key, count in counts.items() if count >= 4]


def _section_prescriptive_padding(sections: list[tuple[str, str]]) -> list[str]:
    offenders = []
    for heading, body in sections:
        if CONCLUSION_HEADING_RE.search(heading) or BACKMATTER_HEADING_RE.search(heading):
            continue
        plain = _plain(body)
        if len(plain) < 80:
            continue
        sentences = [s for s in re.split(r"(?<=[。！？.!?])\s*", plain) if s.strip()]
        if not sentences:
            continue
        prescriptive = [s for s in sentences if PRESCRIPTIVE_RE.search(s)]
        citation_count = len(CITATION_RE.findall(body))
        comparison_count = len(COMPARISON_RE.findall(plain))
        if len(prescriptive) >= 4 and (len(prescriptive) / max(1, len(sentences))) >= 0.45 and citation_count < 2 and comparison_count < 2:
            offenders.append(heading)
    return offenders


def _bare_internal_paper_id_hits(text: str) -> list[str]:
    hits = []
    for match in BARE_INTERNAL_PAPER_ID_RE.finditer(text):
        start = max(0, match.start() - 45)
        end = min(len(text), match.end() + 45)
        hits.append(_plain(text[start:end])[:140])
        if len(hits) >= 10:
            break
    return hits


def _template_evidence_phrase_hits(text: str) -> list[str]:
    hits = []
    for match in TEMPLATE_EVIDENCE_RE.finditer(text):
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 80)
        hits.append(_plain(text[start:end])[:160])
        if len(hits) >= 10:
            break
    return hits


def _related_survey_positioning_is_complete(text: str) -> bool:
    return (
        RELATED_SURVEY_RE.search(text)
        and TAXONOMY_ALIGNMENT_RE.search(text)
        and EXISTING_TAXONOMY_RE.search(text)
        and ARTICLE_TAXONOMY_RE.search(text)
        and DELTA_RE.search(text)
        and EXISTING_COVERAGE_RE.search(text)
        and COVERAGE_GAP_RE.search(text)
        and TAXONOMY_DELTA_RE.search(text)
        and TAXONOMY_NECESSITY_RE.search(text)
    )


def _related_survey_candidate_sections(sections: list[tuple[str, str]], text: str) -> list[str]:
    matches = []
    for heading, body in sections:
        combined = f"{heading}\n{body}"
        if RELATED_SURVEY_RE.search(combined):
            matches.append(heading)
    if not matches and RELATED_SURVEY_RE.search(text):
        matches.append("<article>")
    return matches


def _related_survey_alignment_sections(sections: list[tuple[str, str]], text: str) -> list[str]:
    matches = []
    for heading, body in sections:
        combined = f"{heading}\n{body}"
        if _related_survey_positioning_is_complete(combined):
            matches.append(heading)
    if not matches and _related_survey_positioning_is_complete(text):
        matches.append("<article>")
    return matches


def _related_survey_citation_count(sections: list[tuple[str, str]], text: str) -> int:
    chunks = []
    for heading, body in sections:
        combined = f"{heading}\n{body}"
        if RELATED_SURVEY_RE.search(combined):
            chunks.append(combined)
    if not chunks and RELATED_SURVEY_RE.search(text):
        chunks.append(text)
    citations = set()
    for chunk in chunks:
        for match in SCHOLARLY_CITATION_KEY_RE.finditer(chunk):
            citations.add(match.group(0).lower())
    return len(citations)


def _legacy_artifact_errors(legacy_artifacts) -> list[str]:
    found = []
    for item in legacy_artifacts or []:
        path = Path(str(item))
        if path.name in LEGACY_ARTIFACT_NAMES:
            found.append(str(item))
    return found


def _expansion_growth_requires_audit(review_text: str, draft_text: str, expansion_audit) -> bool:
    if not draft_text.strip():
        return False
    current_chars = len(_plain(review_text))
    draft_chars = len(_plain(draft_text))
    if current_chars <= max(draft_chars + 4000, int(draft_chars * 1.35)):
        return False
    rows = expansion_audit or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") in {"addressed", "waived"} and isinstance(row.get("evidence_rechecked"), list) and row.get("evidence_rechecked"):
            return False
    return True


def _validate_expansion_audit(expansion_audit, article_too_short: bool) -> dict:
    rows = expansion_audit or []
    errors: list[str] = []
    invalid: dict[str, list[str]] = {}
    if article_too_short and not rows:
        errors.extend(["needs_expansion_audit", "expansion_audit_missing"])
        return {"valid": False, "ready": False, "errors": errors, "invalid_items": invalid, "unresolved_items": []}
    unresolved = []
    for idx, row in enumerate(rows, start=1):
        item_errors = []
        if not isinstance(row, dict):
            invalid[str(idx)] = ["invalid_expansion_item"]
            continue
        for field in EXPANSION_REQUIRED_FIELDS:
            value = row.get(field)
            if value in (None, "", [], {}):
                item_errors.append(f"missing_{field}")
        if not isinstance(row.get("required_evidence_refs"), list) or not row.get("required_evidence_refs"):
            item_errors.append("missing_required_evidence_refs")
        status = str(row.get("status") or "pending")
        if status not in EXPANSION_STATUSES:
            item_errors.append("invalid_status")
        if status in {"addressed", "waived"}:
            evidence = row.get("evidence_rechecked")
            if not isinstance(evidence, list) or not evidence:
                item_errors.append("missing_evidence_rechecked")
            else:
                for evidence_item in evidence:
                    if not isinstance(evidence_item, dict):
                        item_errors.append("invalid_evidence_rechecked")
                        continue
                    for field in ["source", "id", "finding"]:
                        if not str(evidence_item.get(field) or "").strip():
                            item_errors.append(f"thin_evidence_rechecked:{field}")
                    if evidence_item.get("supports_expansion") is not True:
                        item_errors.append("evidence_does_not_support_expansion")
            if status == "waived" and not str(row.get("waiver_reason") or "").strip():
                item_errors.append("missing_waiver_reason")
        else:
            unresolved.append(str(idx))
        if item_errors:
            invalid[str(idx)] = sorted(set(item_errors))
    if invalid:
        errors.append("invalid_expansion_audit")
    if rows and not article_too_short and unresolved:
        errors.append("expansion_items_unresolved")
    return {
        "valid": not errors,
        "ready": bool(rows) and not invalid,
        "errors": errors,
        "invalid_items": invalid,
        "unresolved_items": unresolved,
    }


def validate_article_quality(
    review_text: str,
    article_plan: str = "",
    argument_graph: dict | None = None,
    claims: list[dict] | None = None,
    target: str = "full",
    rendered_artifacts=None,
    expansion_audit=None,
    draft_text: str = "",
    legacy_artifacts=None,
    premature_final_artifacts=None,
    appendix_text: str | None = None,
) -> dict:
    if target == "short":
        min_chars = 1000
    elif target == "csur":
        min_chars = 45000
    else:
        min_chars = 25000
    errors: list[str] = []
    leaked = []
    legacy_errors = _legacy_artifact_errors(legacy_artifacts)
    if legacy_errors:
        errors.append("legacy_review_artifact_present")
    premature_final = [str(item) for item in (premature_final_artifacts or []) if str(item)]
    if premature_final:
        errors.append("premature_final_survey_artifact")
    if target in {"full", "csur"}:
        if appendix_text is None:
            errors.append("missing_appendix")
        appendix_plain = _plain(appendix_text or "")
        if len(appendix_plain) < 24:
            errors.append("empty_appendix")
    leaked = _forbidden_hits(review_text)
    if leaked:
        errors.append("internal_or_scaffold_language")
    rendered_errors = []
    rendered_items = _rendered_artifact_items(rendered_artifacts)
    if rendered_artifacts is not None and target in {"full", "csur"} and not rendered_items:
        errors.append("missing_rendered_article")
    for name, text in rendered_items:
        if "dashboard" in name.lower():
            continue
        if target in {"full", "csur"} and not text.strip():
            rendered_errors.append({"path": name, "patterns": ["empty_rendered_article"]})
            continue
        hits = _forbidden_hits(text)
        if hits:
            rendered_errors.append({"path": name, "patterns": hits})
    if rendered_errors:
        errors.append("rendered_artifact_boundary")
    plain = _plain(review_text)
    article_too_short = len(plain) < min_chars
    expansion_status = _validate_expansion_audit(expansion_audit, article_too_short)
    if article_too_short:
        errors.append("article_too_short")
    errors.extend(expansion_status["errors"])
    repeated_paragraphs = _repeated_paragraphs(review_text)
    repeated_sentences = _generic_sentence_repetitions(review_text)
    if repeated_paragraphs:
        errors.append("repetitive_filler")
    if repeated_sentences:
        errors.append("template_paragraph_repetition")
    prescriptive_padding = _prescriptive_padding(review_text)
    if prescriptive_padding:
        errors.append("prescriptive_padding")
    bare_internal_ids = _bare_internal_paper_id_hits(review_text)
    if bare_internal_ids:
        errors.append("bare_internal_paper_ids")
    template_evidence_phrases = _template_evidence_phrase_hits(review_text)
    if template_evidence_phrases:
        errors.append("template_evidence_phrasing")
    if _expansion_growth_requires_audit(review_text, draft_text, expansion_audit):
        errors.append("expansion_provenance_missing")
    sections = _sections(review_text)
    section_prescriptive_padding = _section_prescriptive_padding(sections)
    if section_prescriptive_padding:
        errors.append("section_prescriptive_padding")
    post_conclusion_body_sections = _conclusion_order_errors(sections)
    if post_conclusion_body_sections:
        errors.append("body_section_after_conclusion")
    if target in {"full", "csur"} and len(sections) < 6:
        errors.append("too_few_sections")
    related_survey_alignment_sections = _related_survey_alignment_sections(sections, review_text)
    related_survey_candidate_sections = _related_survey_candidate_sections(sections, review_text)
    related_survey_alignment_present = bool(related_survey_alignment_sections)
    if target in {"full", "csur"} and not related_survey_alignment_present:
        errors.append("thin_related_survey_positioning" if related_survey_candidate_sections else "missing_related_survey_alignment_section")
    related_survey_citation_count = _related_survey_citation_count(sections, review_text)
    related_survey_citation_floor = RELATED_SURVEY_CITATION_FLOOR.get(target, 0)
    if target in {"full", "csur"} and related_survey_alignment_present and related_survey_citation_count < related_survey_citation_floor:
        errors.append("missing_related_survey_citations")
    weak_sections = []
    for heading, body in sections:
        if any(term in heading.lower() for term in ["references", "appendix", "参考文献", "附录"]):
            continue
        opening = _plain(re.split(r"^#{3,6}\s+|^\|", body, maxsplit=1, flags=re.MULTILINE)[0])
        closing = _plain(body[-900:])
        if len(opening) < 120:
            weak_sections.append(f"{heading}:weak_opening")
        if len(closing) > 160 and not re.search(r"因此|由此|启示|意味着|should|therefore|implication|suggests", closing, re.IGNORECASE):
            weak_sections.append(f"{heading}:weak_closing")
    if weak_sections:
        errors.append("weak_section_argument")
    uninterpreted_tables = []
    for idx, table in enumerate(_table_blocks(review_text), start=1):
        before = _plain(review_text[max(0, table.start() - 600): table.start()])
        after = _plain(review_text[table.end(): min(len(review_text), table.end() + 700)])
        if len(before) < 80 or len(after) < 100:
            uninterpreted_tables.append(idx)
    if uninterpreted_tables:
        errors.append("uninterpreted_tables")
    duplicate_headings = {}
    for heading, _body in sections:
        key = heading.strip().lower()
        duplicate_headings[key] = duplicate_headings.get(key, 0) + 1
    duplicates = [heading for heading, count in duplicate_headings.items() if count > 1]
    if duplicates:
        errors.append("duplicate_headings")
    method_sections_without_tradeoff = []
    benchmark_sections_without_recipe = []
    for heading, body in sections:
        heading_lower = heading.lower()
        body_plain = _plain(body)
        body_lower = body_plain.lower()
        if any(term in heading_lower for term in METHOD_SECTION_HEADING_TERMS):
            if not any(re.search(marker, body_plain, flags=re.IGNORECASE) for marker in TRADEOFF_MARKERS):
                method_sections_without_tradeoff.append(heading)
        if any(term in heading_lower for term in BENCHMARK_SECTION_HEADING_TERMS):
            marker_count = sum(1 for marker in EVALUATION_RECIPE_MARKERS if marker in body_lower)
            has_recipe_phrase = bool(
                re.search(
                    r"minimum evaluation recipe|evaluation recipe|最低.{0,12}(实验|评测)包|最小.{0,12}(实验|评测)",
                    body_plain,
                    flags=re.IGNORECASE,
                )
            )
            if marker_count < 4 or not has_recipe_phrase:
                benchmark_sections_without_recipe.append(heading)
    if target in {"full", "csur"} and method_sections_without_tradeoff:
        errors.append("missing_section_tradeoff")
    if target in {"full", "csur"} and benchmark_sections_without_recipe:
        errors.append("missing_evaluation_recipe")
    graph_sections = []
    if argument_graph:
        graph_sections = [str(s) for s in argument_graph.get("section_order") or []]
        review_headings = " ".join(h.lower() for h, _ in sections)
        missing = [section for section in graph_sections if section.lower() not in review_headings]
        if missing:
            errors.append("argument_sections_missing_from_review")
    if claims:
        known_claims = _claim_texts(claims)
        if known_claims:
            unsupported_strong = []
            for match in re.finditer(r"[^。\n]{0,80}(demonstrates|proves|证明|表明|显著提升)[^。\n]{0,120}", review_text, flags=re.IGNORECASE):
                snippet = _plain(match.group(0))
                if not any(snippet[:40].lower() in claim.lower() or claim[:40].lower() in snippet.lower() for claim in known_claims):
                    unsupported_strong.append(snippet[:160])
            if unsupported_strong:
                errors.append("unsupported_strong_article_claims")
        else:
            errors.append("missing_claim_records_for_article")
    return {
        "valid": not errors,
        "errors": errors,
        "chars": len(plain),
        "min_chars": min_chars,
        "expansion_audit_ready": expansion_status["ready"],
        "expansion_audit_invalid_items": expansion_status["invalid_items"],
        "expansion_audit_unresolved_items": expansion_status["unresolved_items"],
        "repeated_paragraphs": repeated_paragraphs,
        "repeated_sentences": repeated_sentences,
        "prescriptive_padding": prescriptive_padding,
        "bare_internal_paper_ids": bare_internal_ids,
        "template_evidence_phrases": template_evidence_phrases,
        "section_prescriptive_padding": section_prescriptive_padding,
        "legacy_review_artifacts": legacy_errors,
        "premature_final_artifacts": premature_final,
        "post_conclusion_body_sections": post_conclusion_body_sections,
        "leaked_patterns": leaked,
        "rendered_artifact_errors": rendered_errors,
        "weak_sections": weak_sections,
        "uninterpreted_tables": uninterpreted_tables,
        "duplicate_headings": duplicates,
        "method_sections_without_tradeoff": method_sections_without_tradeoff,
        "benchmark_sections_without_recipe": benchmark_sections_without_recipe,
        "related_survey_alignment_present": related_survey_alignment_present,
        "related_survey_alignment_sections": related_survey_alignment_sections,
        "related_survey_candidate_sections": related_survey_candidate_sections,
        "related_survey_citation_count": related_survey_citation_count,
        "related_survey_citation_floor": related_survey_citation_floor,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", required=True, type=Path)
    parser.add_argument("--article-plan", type=Path)
    parser.add_argument("--claims", type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--rendered-artifact", action="append", type=Path, default=[])
    parser.add_argument("--legacy-artifact", action="append", type=Path, default=[])
    parser.add_argument("--premature-final-artifact", action="append", type=Path, default=[])
    parser.add_argument("--expansion-audit", type=Path)
    parser.add_argument("--survey-body-draft", type=Path)
    args = parser.parse_args()
    claims = []
    if args.claims and args.claims.exists():
        claims = [json.loads(line) for line in args.claims.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = validate_article_quality(
        args.survey.read_text(encoding="utf-8"),
        args.article_plan.read_text(encoding="utf-8") if args.article_plan and args.article_plan.exists() else "",
        claims=claims,
        target=args.target,
        rendered_artifacts=[(str(path), path.read_text(encoding="utf-8")) for path in args.rendered_artifact if path.exists()],
        legacy_artifacts=[str(path) for path in args.legacy_artifact if path.exists()],
        premature_final_artifacts=[str(path) for path in args.premature_final_artifact if path.exists()],
        expansion_audit=(
            [json.loads(line) for line in args.expansion_audit.read_text(encoding="utf-8").splitlines() if line.strip()]
            if args.expansion_audit and args.expansion_audit.exists()
            else None
        ),
        draft_text=args.survey_body_draft.read_text(encoding="utf-8") if args.survey_body_draft and args.survey_body_draft.exists() else "",
        appendix_text=(args.survey.parent / "appendix.md").read_text(encoding="utf-8") if (args.survey.parent / "appendix.md").exists() else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
