#!/usr/bin/env python3
"""Check that review.md is organized as an article, not an artifact bundle."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SKIP_SECTION_TERMS = [
    "abstract",
    "introduction",
    "related surveys",
    "references",
    "bibliography",
    "appendix",
    "conclusion",
    "tutorial",
    "primer",
    "critical analysis",
    "摘要",
    "引言",
    "相关综述",
    "参考文献",
    "附录",
    "结论",
    "glossary",
    "trace",
    "matrix",
    "guidelines",
    "术语",
    "矩阵",
    "指南",
]

RAW_MATRIX_TERMS = [
    "核心文献吸收矩阵",
    "本文如何使用它",
    "full coverage matrix",
    "raw coverage matrix",
    "paper-card matrix",
    "paper card matrix",
    "state-file",
    "state file",
]

OPENING_MARKERS = [
    "tension",
    "problem",
    "question",
    "why",
    "gap",
    "trade-off",
    "claim",
    "thesis",
    "evidence",
    "mechanism",
    "evaluation",
    "interface",
    "taxonomy",
    "benchmark",
    "design",
    "张力",
    "问题",
    "为什么",
    "缺口",
    "权衡",
    "论点",
    "主张",
    "证据",
    "机制",
    "评测",
    "接口",
    "分类",
    "基准",
    "设计",
]

COMPARISON_MARKERS = [
    "compared",
    "compare",
    "compares",
    "comparison",
    "rather than",
    "whereas",
    "while",
    "however",
    "trade-off",
    "different",
    "contrast",
    "separate",
    "distinguish",
    "selection",
    "guide",
    "相比",
    "不同于",
    "然而",
    "但是",
    "权衡",
    "对比",
    "区分",
    "选择",
    "指南",
]

IMPLICATION_MARKERS = [
    "therefore",
    "consequently",
    "implication",
    "suggests",
    "should",
    "decide",
    "lets a reader",
    "reveals",
    "design",
    "evaluation",
    "agenda",
    "concrete",
    "mature",
    "因此",
    "由此",
    "启示",
    "意味着",
    "应该",
    "设计",
    "评测",
    "议程",
    "具体",
    "成熟",
]


def _plain(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("|"))
    text = re.sub(r"^#{1,6}\s+.*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"[>*`_\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))
    sections: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[match.end():end].strip()))
    return sections


def _has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term in lower or term in text for term in terms)


def _opening_text(body: str) -> str:
    split = re.split(r"^#{3,6}\s+|^\|", body, maxsplit=1, flags=re.MULTILINE)
    return _plain(split[0])


def _closing_text(body: str) -> str:
    plain = _plain(body)
    return plain[-900:]


def validate_global_coherence(text: str, target: str = "full", article_plan_text: str | None = None) -> dict:
    if target not in {"full", "csur"}:
        return {"valid": True, "required": False, "failed_checks": []}

    lower = text.lower()
    raw_terms = [term for term in RAW_MATRIX_TERMS if term.lower() in lower or term in text]

    section_errors: list[str] = []
    comparison_errors: list[str] = []
    implication_errors: list[str] = []
    article_sections = [
        (heading, body)
        for heading, body in _sections(text)
        if not any(term in heading.lower() or term in heading for term in SKIP_SECTION_TERMS)
    ]
    for heading, body in article_sections:
        opening = _opening_text(body)
        if len(opening) < 180 or not _has_any(opening[:900], OPENING_MARKERS):
            section_errors.append(f"{heading}: weak_opening_thesis")
        body_plain = _plain(body)
        if len(body_plain) >= 600 and not _has_any(body_plain, COMPARISON_MARKERS):
            comparison_errors.append(f"{heading}: missing_comparison_move")
        closing = _closing_text(body)
        if len(closing) >= 180 and not _has_any(closing, IMPLICATION_MARKERS):
            implication_errors.append(f"{heading}: missing_closing_implication")

    table_blocks = list(re.finditer(r"(?:^\|.*\|\n)+", text, flags=re.MULTILINE))
    orphan_tables: list[int] = []
    for idx, table in enumerate(table_blocks, start=1):
        before = _plain(text[max(0, table.start() - 700): table.start()])
        after = _plain(text[table.end(): min(len(text), table.end() + 700)])
        if len(before) < 120 or len(after) < 120:
            orphan_tables.append(idx)

    article_plan_missing = False
    if article_plan_text is not None:
        article_plan_missing = len(_plain(article_plan_text)) < 400

    failed = []
    if raw_terms:
        failed.append("raw_coverage_matrix_in_review")
    if section_errors:
        failed.append("section_flow")
    if comparison_errors:
        failed.append("missing_comparison_moves")
    if implication_errors:
        failed.append("missing_closing_implications")
    if orphan_tables:
        failed.append("uninterpreted_tables")
    if article_plan_missing:
        failed.append("article_plan_missing")

    return {
        "valid": not failed,
        "required": True,
        "target": target,
        "failed_checks": failed,
        "raw_matrix_terms": raw_terms,
        "section_flow_errors": section_errors,
        "comparison_errors": comparison_errors,
        "implication_errors": implication_errors,
        "uninterpreted_tables": orphan_tables,
        "article_plan_checked": article_plan_text is not None,
        "article_plan_missing": article_plan_missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--article-plan", type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan_text = args.article_plan.read_text(encoding="utf-8") if args.article_plan and args.article_plan.exists() else None
    result = validate_global_coherence(
        args.review.read_text(encoding="utf-8"),
        target=args.target,
        article_plan_text=plan_text,
    )
    text = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
