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


def validate_article_quality(review_text: str, article_plan: str = "", argument_graph: dict | None = None, claims: list[dict] | None = None, target: str = "full") -> dict:
    if target == "short":
        min_chars = 1000
    elif target == "csur":
        min_chars = 45000
    else:
        min_chars = 25000
    errors: list[str] = []
    leaked = []
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, review_text, flags=re.IGNORECASE):
            leaked.append(pattern)
    if leaked:
        errors.append("internal_or_scaffold_language")
    plain = _plain(review_text)
    if len(plain) < min_chars:
        errors.append("article_too_short")
    sections = _sections(review_text)
    if target in {"full", "csur"} and len(sections) < 6:
        errors.append("too_few_sections")
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
        "leaked_patterns": leaked,
        "weak_sections": weak_sections,
        "uninterpreted_tables": uninterpreted_tables,
        "duplicate_headings": duplicates,
        "method_sections_without_tradeoff": method_sections_without_tradeoff,
        "benchmark_sections_without_recipe": benchmark_sections_without_recipe,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--article-plan", type=Path)
    parser.add_argument("--claims", type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    claims = []
    if args.claims and args.claims.exists():
        claims = [json.loads(line) for line in args.claims.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = validate_article_quality(
        args.review.read_text(encoding="utf-8"),
        args.article_plan.read_text(encoding="utf-8") if args.article_plan and args.article_plan.exists() else "",
        claims=claims,
        target=args.target,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
