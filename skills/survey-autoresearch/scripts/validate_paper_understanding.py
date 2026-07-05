#!/usr/bin/env python3
"""Validate paper-level scientific contribution understanding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FIELDS = [
    "paper_id",
    "title",
    "survey_role",
    "level",
    "reading_depth",
    "full_text_accessed",
    "source_type",
    "full_text_sources",
    "sections_read",
    "evidence_span_locations",
    "deep_read_notes",
    "motivation",
    "problem_setting",
    "task_definition",
    "benchmark_or_dataset",
    "method_pipeline",
    "implementation_details",
    "experimental_setup",
    "main_results",
    "limitations_and_confounders",
    "relation_to_prior_work",
    "what_it_changes_in_the_survey_argument",
    "must_not_overclaim",
    "evidence_spans",
    "field_evidence_map",
    "entity_aliases",
]

FIELD_EVIDENCE_REQUIRED = [
    "motivation",
    "problem_setting",
    "method_pipeline",
    "benchmark_or_dataset",
    "implementation_details",
    "experimental_setup",
    "main_results",
    "limitations_and_confounders",
    "relation_to_prior_work",
]

FIELD_EVIDENCE_TERMS = {
    "motivation": {"motivation", "problem", "challenge", "gap", "need", "aim", "目标", "动机", "问题", "挑战", "缺口"},
    "problem_setting": {"problem", "task", "setting", "input", "output", "formulation", "任务", "设定", "输入", "输出"},
    "method_pipeline": {"method", "approach", "pipeline", "architecture", "model", "module", "方法", "流程", "架构", "模型"},
    "benchmark_or_dataset": {"benchmark", "dataset", "environment", "evaluation", "基准", "数据集", "环境", "评测"},
    "implementation_details": {"implementation", "backbone", "module", "training", "inference", "architecture", "实现", "训练", "推理", "模块"},
    "experimental_setup": {"experiment", "metric", "baseline", "ablation", "protocol", "实验", "指标", "基线", "消融", "协议"},
    "main_results": {"result", "outperform", "improve", "accuracy", "success", "table", "结果", "提升", "优于", "成功率", "表"},
    "limitations_and_confounders": {"limitation", "failure", "confound", "future work", "限制", "失败", "混淆", "不足"},
    "relation_to_prior_work": {"prior", "related", "extends", "compared", "survey", "previous", "相关", "已有", "扩展", "对比", "综述"},
}

FIELD_STRONG_TERMS = {
    "method_pipeline": {"method", "approach", "pipeline", "architecture", "model", "module", "system", "section 3", "方法", "流程", "架构", "模型", "系统"},
    "benchmark_or_dataset": {"benchmark", "dataset", "environment", "evaluation", "protocol", "metric", "baseline", "ablation", "基准", "数据集", "环境", "评测", "协议", "指标", "基线", "消融"},
    "main_results": {"result shows", "results show", "table", "figure", "fig.", "metric", "baseline", "comparison", "compared", "improves", "improvement", "outperform", "accuracy", "success", "结果", "表", "图", "指标", "基线", "对比", "提升", "优于", "成功率"},
}

RELATION_TERMS = {
    "extends",
    "replaces",
    "contradicts",
    "benchmarks",
    "reframes",
    "surveys",
    "alternative",
    "predecessor",
    "successor",
    "conflict",
    "扩展",
    "替代",
    "冲突",
    "基准",
    "重构",
    "综述",
}

GENERIC_RELATIONS = {
    "this is related to prior work",
    "related to prior work",
    "positions the work relative to adjacent embodied-memory designs in the mechanism taxonomy",
}

READING_DEPTH_FULL = "full_text_deep_read"
READING_DEPTH_METADATA = "abstract_metadata_only"
READING_DEPTH_UNREAD = "unavailable_or_unread"

FULL_TEXT_SOURCE_TERMS = {
    "pdf",
    "full_text_pdf",
    "official_pdf",
    "arxiv_pdf",
    "publisher_pdf",
    "acm_dl_pdf",
    "openreview_pdf",
    "paper_html",
    "full_text_html",
    "publisher_html",
}

FULL_TEXT_ACCESS_STATUSES = {"accessible", "downloaded", "extracted", "available", "ok"}
FULL_TEXT_EXTRACTION_STATUSES = {"extracted", "excerpt_captured", "partial_extracted", "parsed"}

METADATA_SOURCE_TERMS = {
    "title",
    "abstract",
    "metadata",
    "semantic scholar",
    "semanticscholar",
    "crossref",
    "dblp",
    "curated list",
    "curated-list",
    "github list",
    "github curated",
    "paper list",
    "survey table",
}

BOILERPLATE_NOISE_TERMS = {
    "acknowledgement",
    "acknowledgment",
    "funding",
    "grant",
    "supercomputing",
    "allocation",
    "arxivlabs",
    "arxiv labs",
    "license",
    "creative commons",
    "metadata",
    "this work was supported",
    "we thank",
    "致谢",
    "基金",
    "资助",
    "许可证",
}
NOISE_SENSITIVE_FIELDS = ["motivation", "main_results", "limitations_and_confounders"]
GENERIC_ENTITY_TOKENS = {
    "paper",
    "section",
    "table",
    "figure",
    "benchmark",
    "method",
    "result",
    "results",
    "baseline",
    "metric",
    "evaluation",
    "experiment",
    "experiments",
}

SECTION_GROUPS = {
    "intro_or_problem": {"intro", "introduction", "problem", "motivation", "background", "摘要", "引言", "问题"},
    "method_or_system": {"method", "methods", "system", "approach", "model", "architecture", "方法", "系统", "模型", "架构"},
    "experiment_or_evaluation": {"experiment", "experiments", "evaluation", "benchmark", "setup", "实验", "评测", "基准"},
    "results_or_limitations": {"result", "results", "discussion", "limitation", "limitations", "conclusion", "结果", "限制", "讨论", "结论"},
}

LOCATION_TERMS = {"section", "sec.", "page", "p.", "pp.", "figure", "fig.", "table", "appendix", "section ", "页", "图", "表", "节"}

GENERIC_FIELD_PATTERNS = {
    "motivation": {
        "this paper is important",
        "this paper is relevant",
        "important and relevant",
        "the paper addresses a problem in this area",
    },
    "problem_setting": {
        "a general problem",
        "a relevant task",
        "the paper studies the problem",
    },
    "deep_read_notes": {
        "read the paper",
        "paper was read",
        "full text was reviewed",
    },
    "what_it_changes_in_the_survey_argument": {
        "it is useful for the survey",
        "it supports the survey",
        "it is relevant to the argument",
    },
}

SURVEY_USE_TERMS = {
    "argument",
    "claim",
    "section",
    "spine",
    "taxonomy",
    "tree",
    "cluster",
    "evidence",
    "evaluation",
    "benchmark",
    "method",
    "failure",
    "limitation",
    "open problem",
    "control",
    "interface",
    "论证",
    "主张",
    "章节",
    "骨架",
    "分类",
    "知识树",
    "证据",
    "评测",
    "方法",
    "失败",
    "限制",
}

TEMPLATE_CARD_PATTERNS = {
    "the card records how",
    "the card explains how",
    "this card records",
    "this card explains",
    "the paper fits the survey taxonomy",
    "fits the survey taxonomy",
    "records how the article",
    "records how the survey",
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def depth_ids(citation_plan: list[dict]) -> set[str]:
    return {
        str(item["paper_id"])
        for item in citation_plan
        if item.get("paper_id") and str(item.get("depth") or item.get("level") or "").upper() in {"A", "B"}
    }


def _is_depth_ab(value) -> bool:
    return str(value or "").upper() in {"A", "B"}


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _text_blob(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_text_blob(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text_blob(v) for v in value)
    return str(value)


def _is_metadata_only_text(value) -> bool:
    text = _text_blob(value).lower()
    return any(term in text for term in METADATA_SOURCE_TERMS)


def _has_location_anchor(value) -> bool:
    text = _text_blob(value).lower()
    return any(term in text for term in LOCATION_TERMS)


def _source_by_paper(full_text_sources: list[dict] | None) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for source in full_text_sources or []:
        pid = str(source.get("paper_id") or "")
        if pid:
            result.setdefault(pid, []).append(source)
    return result


def _source_refs_for_paper(sources: list[dict]) -> set[str]:
    refs = set()
    for source in sources:
        ref = str(source.get("source_ref") or source.get("id") or "").strip()
        if ref:
            refs.add(ref)
    return refs


def _source_type_text(source: dict) -> str:
    return str(source.get("source_kind") or source.get("source_type") or "").lower()


def _captured_excerpts(source: dict) -> list[dict]:
    excerpts = source.get("captured_excerpts") or source.get("excerpts") or []
    return excerpts if isinstance(excerpts, list) else []


def _valid_full_text_source(source: dict) -> bool:
    source_type = _source_type_text(source)
    if not source_type or _is_metadata_only_text(source_type):
        return False
    if not any(term in source_type for term in FULL_TEXT_SOURCE_TERMS):
        return False
    access_status = str(source.get("access_status") or "").lower()
    if access_status and access_status not in FULL_TEXT_ACCESS_STATUSES:
        return False
    extraction_status = str(source.get("extraction_status") or "").lower()
    if extraction_status and extraction_status not in FULL_TEXT_EXTRACTION_STATUSES:
        return False
    excerpts = _captured_excerpts(source)
    if excerpts:
        for excerpt in excerpts:
            if not isinstance(excerpt, dict):
                continue
            if _nonempty(excerpt.get("excerpt")) and _has_location_anchor(excerpt.get("section_or_page") or excerpt.get("location")):
                return True
    return bool(source.get("local_text_path") or source.get("excerpt_path") or source.get("pdf_path"))


def _covered_section_groups(sections_read) -> set[str]:
    text_items = [_text_blob(item).lower() for item in _as_list(sections_read)]
    covered = set()
    for group, terms in SECTION_GROUPS.items():
        if any(any(term in item for term in terms) for item in text_items):
            covered.add(group)
    return covered


def _has_benchmark(card: dict) -> bool:
    return _nonempty(card.get("benchmark_or_dataset")) or _nonempty(card.get("benchmark_or_environment"))


def _valid_result(result: dict) -> bool:
    evidence = str(result.get("evidence_span") or result.get("evidence") or "")
    if not (
        _nonempty(result.get("result") or result.get("claim"))
        and _nonempty(evidence)
        and str(result.get("claim_strength") or result.get("strength") or "") in {"demonstrates", "shows", "suggests", "may indicate"}
    ):
        return False
    lowered = evidence.lower()
    return not any(term in lowered for term in ["title only", "title/abstract only", "paper title alone"]) and not _is_metadata_only_text(evidence)


def _field_evidence_errors(card: dict, source_refs: set[str]) -> list[str]:
    mapping = card.get("field_evidence_map")
    if not isinstance(mapping, dict) or not mapping:
        return ["missing_field_evidence_map"]
    errors = []
    for field in FIELD_EVIDENCE_REQUIRED:
        entries = mapping.get(field)
        if not isinstance(entries, list) or not entries:
            errors.append(f"missing_field_evidence:{field}")
            continue
        valid_entry = False
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            source_ref = str(entry.get("source_ref") or "").strip()
            evidence_text = _text_blob(entry)
            if not source_ref or source_ref not in source_refs:
                continue
            if _has_template_card_language(evidence_text):
                continue
            if _is_metadata_only_text(evidence_text):
                continue
            lowered_evidence = evidence_text.lower()
            if not any(term in lowered_evidence for term in FIELD_EVIDENCE_TERMS.get(field, set())):
                continue
            strong_terms = FIELD_STRONG_TERMS.get(field)
            if strong_terms and not any(term in lowered_evidence for term in strong_terms):
                continue
            if field == "main_results" and any(term in lowered_evidence for term in ["without a metric", "without metric", "without a baseline", "without baseline", "without a table", "without table", "without a result", "without result"]):
                continue
            if any(term in lowered_evidence for term in BOILERPLATE_NOISE_TERMS):
                continue
            if not _has_location_anchor(entry.get("location") or entry.get("section_or_page") or entry.get("evidence_span")):
                continue
            if not _nonempty(entry.get("evidence_span") or entry.get("excerpt") or entry.get("evidence_summary")):
                continue
            valid_entry = True
            break
        if not valid_entry:
            errors.append(f"invalid_field_evidence:{field}")
    return errors


def _entity_names_from_value(value) -> list[str]:
    text = _text_blob(value)
    candidates: list[str] = []
    if isinstance(value, (list, tuple, set)):
        for item in value:
            item_text = str(item).strip()
            if (
                item_text
                and len(item_text.split()) <= 4
                and any(ch.isupper() for ch in item_text)
                and not (item_text.lower().startswith("p") and item_text[1:].isdigit())
            ):
                candidates.append(item_text)
    elif isinstance(value, dict):
        for item in value.values():
            candidates.extend(_entity_names_from_value(item))
    for token in text.replace("(", " ").replace(")", " ").replace(",", " ").split():
        clean = token.strip(" .;:[]{}'\"")
        if clean.lower().startswith("p") and clean[1:].isdigit():
            continue
        if clean.lower() in GENERIC_ENTITY_TOKENS:
            continue
        if len(clean) >= 4 and (any(ch.isupper() for ch in clean) or "-" in clean or any(ch.isdigit() for ch in clean)):
            candidates.append(clean)
    seen = set()
    result = []
    for name in candidates:
        normalized = name.lower()
        if normalized not in seen and len(normalized) >= 4:
            seen.add(normalized)
            result.append(name)
    return result


def _alias_names(card: dict) -> set[str]:
    names = set()
    for alias in card.get("entity_aliases") or []:
        if isinstance(alias, dict):
            name = str(alias.get("name") or alias.get("alias") or "").strip().lower()
            if name:
                names.add(name)
    return names


def _field_consistency_errors(card: dict) -> list[str]:
    mapping = card.get("field_evidence_map") if isinstance(card.get("field_evidence_map"), dict) else {}
    aliases = _alias_names(card)
    checks = {
        "method_pipeline": card.get("method_pipeline"),
        "benchmark_or_dataset": card.get("benchmark_or_dataset"),
        "main_results": [r.get("result") or r.get("claim") for r in card.get("main_results") or [] if isinstance(r, dict)],
    }
    errors = []
    for field, value in checks.items():
        names = _entity_names_from_value(value)
        if not names:
            continue
        evidence_text = _text_blob(mapping.get(field)).lower()
        missing = []
        for name in names:
            lower = name.lower()
            if lower in aliases or lower in evidence_text:
                continue
            missing.append(name)
        if missing:
            errors.append(f"evidence_field_consistency:{field}")
    return errors


def _alias_errors(card: dict, source_refs: set[str]) -> list[str]:
    aliases = card.get("entity_aliases")
    if not isinstance(aliases, list) or not aliases:
        return ["missing_entity_aliases"]
    errors = []
    has_non_title_alias = False
    for idx, alias in enumerate(aliases, start=1):
        if not isinstance(alias, dict):
            errors.append(f"invalid_entity_alias:{idx}")
            continue
        name = str(alias.get("name") or alias.get("alias") or "").strip()
        alias_type = str(alias.get("type") or alias.get("kind") or "").strip().lower()
        source_ref = str(alias.get("source_ref") or "").strip()
        evidence = _text_blob(alias.get("evidence") or alias.get("evidence_span") or alias.get("source") or "")
        if not name:
            errors.append(f"missing_entity_alias_name:{idx}")
        if not alias_type:
            errors.append(f"missing_entity_alias_type:{idx}")
        if not evidence:
            errors.append(f"missing_entity_alias_evidence:{idx}")
        if not source_ref:
            errors.append(f"missing_entity_alias_source_ref:{idx}")
        elif source_refs and source_ref not in source_refs:
            errors.append(f"unknown_entity_alias_source_ref:{idx}")
        if alias_type not in {"paper_title", "title"}:
            has_non_title_alias = True
            if _is_metadata_only_text(evidence):
                errors.append(f"metadata_only_entity_alias:{idx}")
            if source_refs and source_ref not in source_refs:
                errors.append(f"entity_alias_not_full_text_backed:{idx}")
    if not has_non_title_alias:
        errors.append("entity_aliases_title_only")
    return errors


def _signature(value) -> str:
    text = _text_blob(value).lower()
    return " ".join(text.split())


def _has_relation_type(value) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    lowered = text.lower().rstrip(".")
    if lowered in GENERIC_RELATIONS:
        return False
    return any(term in lowered for term in RELATION_TERMS)


def _is_generic_field(field: str, value) -> bool:
    text = _text_blob(value).strip().lower()
    if not text:
        return False
    if field == "deep_read_notes" and len(text.split()) < 12:
        return True
    if field in {"motivation", "problem_setting", "what_it_changes_in_the_survey_argument"} and len(text.split()) < 8:
        return True
    return any(pattern in text for pattern in GENERIC_FIELD_PATTERNS.get(field, set()))


def _has_template_card_language(value) -> bool:
    text = _text_blob(value).strip().lower()
    return bool(text) and any(pattern in text for pattern in TEMPLATE_CARD_PATTERNS)


def _survey_use_errors(card: dict) -> list[str]:
    errors: list[str] = []
    changes = card.get("what_it_changes_in_the_survey_argument") or card.get("changes_knowledge_tree")
    if not _nonempty(changes):
        errors.append("missing_survey_use_changes_knowledge_tree")
    else:
        text = _text_blob(changes).lower()
        if _is_generic_field("what_it_changes_in_the_survey_argument", changes):
            errors.append("generic_survey_use_changes_knowledge_tree")
        if _has_template_card_language(changes):
            errors.append("template_survey_use_changes_knowledge_tree")
        if not any(term in text for term in SURVEY_USE_TERMS):
            errors.append("survey_use_not_tied_to_tree_or_argument")
    possible_sections = card.get("possible_sections") or card.get("survey_sections")
    if not isinstance(possible_sections, list) or not [item for item in possible_sections if _nonempty(item)]:
        errors.append("missing_possible_sections")
    contribution = card.get("one_sentence_contribution") or card.get("contribution_statement")
    if not _nonempty(contribution):
        errors.append("missing_one_sentence_contribution")
    elif _has_template_card_language(contribution):
        errors.append("template_one_sentence_contribution")
    claim_support = card.get("supports_claims") or card.get("supported_claim_types") or card.get("possible_claims")
    if not _nonempty(claim_support):
        errors.append("missing_supported_claim_hint")
    return errors


def _boilerplate_noise_fields(card: dict) -> list[str]:
    fields = []
    for field in NOISE_SENSITIVE_FIELDS:
        text = _text_blob(card.get(field)).lower()
        if text and any(term in text for term in BOILERPLATE_NOISE_TERMS):
            fields.append(field)
    return fields


def validate_paper_understanding(
    cards: list[dict],
    citation_plan: list[dict] | None = None,
    full_text_sources: list[dict] | None = None,
) -> dict:
    required_ids = depth_ids(citation_plan or [])
    by_id = {str(card.get("paper_id")): card for card in cards if card.get("paper_id")}
    sources_by_paper = _source_by_paper(full_text_sources)
    errors: list[str] = []
    invalid_cards: dict[str, list[str]] = {}
    deep_read_ids: set[str] = set()
    audited_deep_read_ids: set[str] = set()
    metadata_only_a_b_ids: set[str] = set()
    template_signatures: dict[tuple[str, str, str], list[str]] = {}
    for pid in sorted(required_ids - set(by_id)):
        invalid_cards[pid] = ["missing_mechanism_card"]
    for card in cards:
        pid = str(card.get("paper_id") or "<missing>")
        is_required_ab = pid in required_ids or _is_depth_ab(card.get("level") or card.get("depth"))
        reading_depth = str(card.get("reading_depth") or "").strip()
        if not is_required_ab:
            if reading_depth in {READING_DEPTH_METADATA, READING_DEPTH_UNREAD} or card.get("evidence_limited") is True:
                continue
        card_errors = []
        for field in REQUIRED_FIELDS:
            if not _nonempty(card.get(field)):
                card_errors.append(f"missing_{field}")
            elif is_required_ab and _is_generic_field(field, card.get(field)):
                card_errors.append(f"generic_{field}")
            elif is_required_ab and _has_template_card_language(card.get(field)):
                card_errors.append(f"template_{field}")
        if is_required_ab:
            for field in _boilerplate_noise_fields(card):
                card_errors.append(f"boilerplate_noise:{field}")
        if is_required_ab:
            paper_sources = sources_by_paper.get(pid, [])
            source_refs = _source_refs_for_paper(paper_sources)
            if not paper_sources:
                card_errors.append("missing_full_text_source_audit")
            elif not any(_valid_full_text_source(source) for source in paper_sources):
                card_errors.append("invalid_full_text_source_audit")
            else:
                audited_deep_read_ids.add(pid)
            if reading_depth != READING_DEPTH_FULL:
                card_errors.append("a_b_not_full_text_deep_read")
                metadata_only_a_b_ids.add(pid)
            if card.get("full_text_accessed") is not True:
                card_errors.append("full_text_not_accessed")
            source_type = str(card.get("source_type") or "").lower()
            if not any(term in source_type for term in FULL_TEXT_SOURCE_TERMS) or _is_metadata_only_text(source_type):
                card_errors.append("invalid_full_text_source_type")
            covered_groups = _covered_section_groups(card.get("sections_read"))
            for group in SECTION_GROUPS:
                if group not in covered_groups:
                    card_errors.append(f"missing_section_group:{group}")
            locations = _as_list(card.get("evidence_span_locations"))
            if not locations:
                card_errors.append("missing_evidence_span_locations")
            else:
                if any(_is_metadata_only_text(location) for location in locations):
                    card_errors.append("metadata_only_evidence_location")
                if not all(_has_location_anchor(location) for location in locations):
                    card_errors.append("evidence_location_not_specific")
            if _is_metadata_only_text(card.get("evidence_spans")):
                card_errors.append("metadata_only_evidence_span")
            card_errors.extend(_field_evidence_errors(card, source_refs))
            card_errors.extend(_field_consistency_errors(card))
            card_errors.extend(_alias_errors(card, source_refs))
            card_errors.extend(_survey_use_errors(card))
        if not _has_benchmark(card):
            card_errors.append("missing_benchmark_or_dataset")
        if not isinstance(card.get("method_pipeline"), list) or len(card.get("method_pipeline", [])) < 3:
            card_errors.append("method_pipeline_too_thin")
        if not isinstance(card.get("implementation_details"), dict) or len(card.get("implementation_details", {})) < 2:
            card_errors.append("implementation_details_too_thin")
        if not isinstance(card.get("experimental_setup"), dict) or len(card.get("experimental_setup", {})) < 2:
            card_errors.append("experimental_setup_too_thin")
        experiment = card.get("experimental_setup") if isinstance(card.get("experimental_setup"), dict) else {}
        if not _nonempty(experiment.get("metrics")):
            card_errors.append("missing_metrics")
        if not _nonempty(experiment.get("baselines")):
            card_errors.append("missing_baselines")
        if not _nonempty(experiment.get("ablations")):
            card_errors.append("missing_ablations")
        if not _nonempty(experiment.get("evaluation_protocol")):
            card_errors.append("missing_evaluation_protocol")
        results = card.get("main_results") or []
        if not isinstance(results, list) or not results or not all(isinstance(r, dict) and _valid_result(r) for r in results):
            card_errors.append("invalid_main_results")
        limitations = card.get("limitations_and_confounders") or []
        if not isinstance(limitations, list) or len(limitations) < 2:
            card_errors.append("limitations_too_thin")
        if not _has_relation_type(card.get("relation_to_prior_work")):
            card_errors.append("generic_relation_to_prior_work")
        role = str(card.get("survey_role") or "").lower()
        result_text = " ".join(str((r or {}).get("result") or (r or {}).get("claim") or "") for r in results if isinstance(r, dict)).lower()
        if role == "survey" and any(term in result_text for term in ["outperforms", "improves", "beats", "提升", "优于"]):
            card_errors.append("survey_used_as_experimental_result")
        if role == "benchmark" and any(term in result_text for term in ["our method", "the method improves", "proposed system", "新方法"]):
            card_errors.append("benchmark_used_as_method_result")
        if card_errors:
            invalid_cards[pid] = card_errors
        elif is_required_ab and reading_depth == READING_DEPTH_FULL:
            deep_read_ids.add(pid)
        if is_required_ab:
            result_signature = _signature([r.get("result") or r.get("claim") for r in results if isinstance(r, dict)])
            signature = (
                _signature(card.get("method_pipeline")),
                _signature(card.get("limitations_and_confounders")),
                result_signature,
            )
            if all(signature):
                template_signatures.setdefault(signature, []).append(pid)
    for ids in template_signatures.values():
        if len(ids) > 1:
            for pid in ids:
                invalid_cards.setdefault(pid, []).append("duplicate_template_mechanism_card")
    incomplete_ids = sorted(set(invalid_cards) | (required_ids - deep_read_ids))
    if invalid_cards:
        errors.append("invalid_paper_understanding")
    if required_ids and deep_read_ids != required_ids:
        errors.append("incomplete_a_b_paper_understanding")
    return {
        "valid": not errors,
        "errors": errors,
        "total_cards": len(cards),
        "required_a_b_cards": len(required_ids),
        "a_b_required_count": len(required_ids),
        "a_b_completed_count": len(deep_read_ids & required_ids),
        "a_b_full_text_deep_read_count": len(deep_read_ids & required_ids),
        "a_b_full_text_source_audited_count": len(audited_deep_read_ids & required_ids),
        "metadata_only_a_b_count": len(metadata_only_a_b_ids & required_ids),
        "paper_understanding_complete": not errors,
        "incomplete_paper_ids": incomplete_ids,
        "invalid_cards": invalid_cards,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-mechanism-cards", required=True, type=Path)
    parser.add_argument("--citation-plan", type=Path)
    parser.add_argument("--full-text-sources", type=Path)
    args = parser.parse_args()
    result = validate_paper_understanding(
        read_jsonl(args.paper_mechanism_cards),
        read_jsonl(args.citation_plan) if args.citation_plan else None,
        read_jsonl(args.full_text_sources) if args.full_text_sources else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
