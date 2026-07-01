#!/usr/bin/env python3
"""Validate that review-body case studies are prose, not raw paper-card dumps."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CASE_HEADING_RE = re.compile(
    r"^#{3,4}\s+.*(?:worked example|case study|case box|case-study|案例|个案|机制解剖).*$",
    flags=re.IGNORECASE | re.MULTILINE,
)

RAW_FIELD_LABEL_RE = re.compile(
    r"^\s*(?:[-*]\s*)?"
    r"(?:paper id|problem|memory record|write policy|read policy|update(?: policy)?|"
    r"controller interface|benchmark(?:\s*/\s*task)?|ablation evidence|failure mode|"
    r"design lesson|问题|记忆记录|写入策略|读取策略|更新策略|控制接口|基准|消融证据|失败模式|设计启示)"
    r"\s*[:：]",
    flags=re.IGNORECASE | re.MULTILINE,
)

BANNED_TEMPLATE_PHRASES = [
    "该工作在本文中被读作",
    "记录重点是",
    "本文要求把该工作放入",
    "若原文没有完整报告，则将其作为证据缺口",
    "及其相关任务族",
    "the paper teaches that",
    "must be specified through record schema",
    "otherwise memory cannot be distinguished",
]

MECHANISM_TERMS = [
    "mechanism",
    "record",
    "write",
    "read",
    "retrieve",
    "retrieval",
    "interface",
    "机制",
    "记录",
    "写入",
    "读取",
    "检索",
    "接口",
]

EVIDENCE_TERMS = [
    "benchmark",
    "ablation",
    "baseline",
    "evidence",
    "experiment",
    "control",
    "评测",
    "基准",
    "消融",
    "对照",
    "证据",
    "实验",
]

LIMITATION_TERMS = [
    "limitation",
    "failure",
    "stale",
    "false recall",
    "confound",
    "trade-off",
    "局限",
    "限制",
    "失败",
    "失效",
    "混淆",
    "权衡",
]


def _split_case_blocks(text: str) -> list[str]:
    matches = list(CASE_HEADING_RE.finditer(text))
    blocks: list[str] = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        next_h2 = re.search(r"^##\s+", text[match.end():end], flags=re.MULTILINE)
        if next_h2:
            end = match.end() + next_h2.start()
        blocks.append(text[match.start():end].strip())
    return blocks


def _plain_len(text: str) -> int:
    cleaned = re.sub(r"[#>*`|\-_\s]+", "", text)
    return len(cleaned)


def _paragraphs(block: str) -> list[str]:
    body_lines = [
        line for line in block.splitlines()
        if not line.strip().startswith("#") and not line.strip().startswith("|")
    ]
    body = "\n".join(body_lines).strip()
    return [para.strip() for para in re.split(r"\n\s*\n", body) if para.strip()]


def _has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term in lower or term in text for term in terms)


def validate_case_study_prose(text: str, target: str = "full") -> dict:
    if target not in {"full", "csur"}:
        return {"valid": True, "required": False, "failed_checks": []}

    blocks = _split_case_blocks(text)
    errors: list[str] = []
    for idx, block in enumerate(blocks, start=1):
        field_labels = RAW_FIELD_LABEL_RE.findall(block)
        banned = [phrase for phrase in BANNED_TEMPLATE_PHRASES if phrase.lower() in block.lower()]
        paragraphs = _paragraphs(block)
        if len(field_labels) > 2:
            errors.append(f"case {idx}: raw_field_labels={len(field_labels)}")
        if banned:
            errors.append(f"case {idx}: banned_template_phrases={','.join(banned)}")
        if _plain_len(block) < 450 or len(paragraphs) < 2:
            errors.append(f"case {idx}: too_thin_for_case_study_prose")
        if not _has_any(block, MECHANISM_TERMS):
            errors.append(f"case {idx}: missing_mechanism_explanation")
        if not _has_any(block, EVIDENCE_TERMS):
            errors.append(f"case {idx}: missing_evaluation_or_evidence")
        if not _has_any(block, LIMITATION_TERMS):
            errors.append(f"case {idx}: missing_limitation_or_failure")

    failed = []
    joined = "\n".join(errors)
    if "raw_field_labels" in joined:
        failed.append("raw_field_labels")
    if "banned_template_phrases" in joined:
        failed.append("banned_template_phrases")
    if any(item not in {"raw_field_labels", "banned_template_phrases"} for item in failed):
        pass
    if errors and not failed:
        failed.append("case_study_specificity")
    elif any("too_thin" in error or "missing_" in error for error in errors):
        failed.append("case_study_specificity")

    return {
        "valid": not failed,
        "required": True,
        "target": target,
        "failed_checks": failed,
        "case_studies": len(blocks),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_case_study_prose(args.review.read_text(encoding="utf-8"), args.target)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
