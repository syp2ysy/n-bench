#!/usr/bin/env python3
"""Validate that internal planning stays out of review.md."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_PLAN_BLOCKS = {
    "article_body_sections": [
        "article_body_sections",
        "article body sections",
        "article-body sections",
        "正文区块",
        "正文结构",
    ],
    "article_displays": [
        "article_displays",
        "article displays",
        "article-facing displays",
        "正文图表",
        "正文展示项",
    ],
    "appendix_sections": [
        "appendix_sections",
        "appendix sections",
        "appendix-facing",
        "附录区块",
        "附录",
    ],
    "internal_only": [
        "internal_only",
        "internal only",
        "internal-only",
        "内部专用",
        "仅内部",
    ],
}


LEAK_PATTERNS = [
    re.compile(r"\bsystem[- ]object survey\b", re.IGNORECASE),
    re.compile(r"\bprimary survey type\b", re.IGNORECASE),
    re.compile(r"\bsecondary lenses\b", re.IGNORECASE),
    re.compile(r"\b[ABC][- ]level\b", re.IGNORECASE),
    re.compile(r"\bdesign signal\b", re.IGNORECASE),
    re.compile(r"\banchor evidence\b", re.IGNORECASE),
    re.compile(r"\bevidence tier(s)?\b", re.IGNORECASE),
    re.compile(r"\bevidence ladder\b", re.IGNORECASE),
    re.compile(r"本文采用[^。\n]{0,60}survey[^。\n]{0,30}结构", re.IGNORECASE),
    re.compile(r"检索和筛选围绕"),
    re.compile(r"文献被分为"),
    re.compile(r"候选文献"),
    re.compile(r"深读文献"),
    re.compile(r"证据层级"),
    re.compile(r"调研设计"),
]


LEAK_SECTION_PATTERNS = [
    re.compile(r"调研设计"),
    re.compile(r"证据层级"),
    re.compile(r"survey methodology", re.IGNORECASE),
    re.compile(r"evidence tier(s)?", re.IGNORECASE),
    re.compile(r"search and screening", re.IGNORECASE),
    re.compile(r"检索和筛选"),
]


def _normalize_heading(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _headings(text: str) -> list[tuple[str, int, int]]:
    matches = list(re.finditer(r"^(#{2,6})\s+(.+?)\s*$", text, flags=re.MULTILINE))
    result: list[tuple[str, int, int]] = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        result.append((match.group(2).strip(), match.end(), end))
    return result


def _find_plan_blocks(plan_text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for heading, start, end in _headings(plan_text):
        normalized = _normalize_heading(heading)
        for block, aliases in REQUIRED_PLAN_BLOCKS.items():
            if any(_normalize_heading(alias) in normalized for alias in aliases):
                found[block] = plan_text[start:end].strip()
    return found


def _plain(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("|"))
    text = re.sub(r"^#{1,6}\s+.*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"[>*`_\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _internal_overlap(review_text: str, internal_text: str) -> list[str]:
    if not internal_text.strip():
        return []
    review_plain = _plain(review_text).lower()
    overlaps: list[str] = []
    for raw_line in internal_text.splitlines():
        line = re.sub(r"^[-*+\d.)\s]+", "", raw_line).strip()
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line_plain = _plain(line)
        if len(line_plain) < 28:
            continue
        if line_plain.lower() in review_plain:
            overlaps.append(line_plain[:160])
    return overlaps


def validate_article_boundary(review_text: str, article_plan_text: str = "", target: str = "full") -> dict:
    if target not in {"full", "csur"}:
        return {"valid": True, "required": False, "failed_checks": []}

    plan_blocks = _find_plan_blocks(article_plan_text)
    missing_plan_blocks = [
        block for block in REQUIRED_PLAN_BLOCKS
        if not plan_blocks.get(block, "").strip()
    ]

    leaked_terms: list[str] = []
    for pattern in LEAK_PATTERNS:
        for match in pattern.finditer(review_text):
            leaked_terms.append(match.group(0))
            break

    leaked_sections = [
        heading for heading, _start, _end in _headings(review_text)
        if any(pattern.search(heading) for pattern in LEAK_SECTION_PATTERNS)
    ]

    internal_plan_overlap = _internal_overlap(review_text, plan_blocks.get("internal_only", ""))

    failed = []
    if missing_plan_blocks:
        failed.append("article_plan_boundary_contract")
    if leaked_terms:
        failed.append("internal_planning_language")
    if leaked_sections:
        failed.append("appendix_or_internal_section_in_review")
    if internal_plan_overlap:
        failed.append("internal_plan_overlap")

    return {
        "valid": not failed,
        "required": True,
        "target": target,
        "failed_checks": failed,
        "missing_plan_blocks": missing_plan_blocks,
        "leaked_terms": leaked_terms,
        "leaked_sections": leaked_sections,
        "internal_plan_overlap": internal_plan_overlap,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--article-plan", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_article_boundary(
        args.review.read_text(encoding="utf-8"),
        args.article_plan.read_text(encoding="utf-8") if args.article_plan.exists() else "",
        target=args.target,
    )
    text = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
