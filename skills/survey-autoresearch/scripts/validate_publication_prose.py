#!/usr/bin/env python3
"""Validate that review.md reads like article prose rather than artifact paste."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from .validate_case_study_prose import RAW_FIELD_LABEL_RE, validate_case_study_prose
    from .validate_table_interpretation import validate_table_interpretation
except ImportError:  # pragma: no cover - standalone script mode
    from validate_case_study_prose import RAW_FIELD_LABEL_RE, validate_case_study_prose
    from validate_table_interpretation import validate_table_interpretation


RAW_ARTIFACT_PHRASES = [
    "本节面向",
    "下面的 glossary",
    "下面的表",
    "这个表的作用",
    "这个矩阵",
    "核心文献吸收矩阵",
    "本文如何使用它",
    "该工作在本文中被读作",
    "记录重点是",
    "本文要求把该工作放入",
    "若原文没有完整报告，则将其作为证据缺口",
    "及其相关任务族",
    "state file",
    "state-file",
    "workflow log",
    "artifact",
    "dossier",
    "paper card",
    "node card",
    "section card",
    "gate check",
    "the paper teaches that",
    "must be specified through record schema",
    "otherwise memory cannot be distinguished",
    "paper id:",
    "benchmark / task:",
]

SECTION_SKIP_TERMS = [
    "abstract",
    "introduction",
    "related surveys",
    "references",
    "bibliography",
    "appendix",
    "conclusion",
    "摘要",
    "引言",
    "相关综述",
    "参考文献",
    "附录",
    "结论",
]

ARGUMENT_MARKERS = [
    "compared",
    "whereas",
    "while",
    "however",
    "therefore",
    "consequently",
    "trade-off",
    "trade-offs",
    "implication",
    "evidence",
    "benchmark",
    "protocol",
    "claim",
    "comparison",
    "design",
    "evaluation",
    "相比",
    "不同于",
    "然而",
    "因此",
    "由此",
    "权衡",
    "启示",
    "设计",
    "评测",
]


def _plain(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"\|.*\|", " ", text)
    return re.sub(r"\s+", " ", re.sub(r"[#>*`_\-]+", " ", text)).strip()


def _major_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))
    sections: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[match.end():end].strip()))
    return sections


def _has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term in lower or term in text for term in terms)


def _section_flow_errors(text: str) -> list[str]:
    errors: list[str] = []
    for heading, body in _major_sections(text):
        heading_lower = heading.lower()
        if any(term in heading_lower or term in heading for term in SECTION_SKIP_TERMS):
            continue
        opening = re.split(r"^#{3,6}\s+|^\|", body, maxsplit=1, flags=re.MULTILINE)[0]
        opening_plain = _plain(opening)
        if len(opening_plain) < 140:
            errors.append(f"{heading}: opening_thesis_too_thin")
        closing_plain = _plain(body[-900:])
        if len(closing_plain) > 120 and not _has_any(closing_plain, ARGUMENT_MARKERS):
            errors.append(f"{heading}: missing_closing_implication")
    return errors


def validate_publication_prose(text: str, target: str = "full") -> dict:
    if target not in {"full", "csur"}:
        return {"valid": True, "required": False, "failed_checks": []}

    lower = text.lower()
    raw_phrases = [phrase for phrase in RAW_ARTIFACT_PHRASES if phrase.lower() in lower]
    raw_field_labels = RAW_FIELD_LABEL_RE.findall(text)
    case_status = validate_case_study_prose(text, target=target)
    table_status = validate_table_interpretation(text, target=target)
    section_errors = _section_flow_errors(text)

    failed = []
    if raw_phrases or len(raw_field_labels) > 2:
        failed.append("raw_artifact_language")
    if not case_status["valid"]:
        failed.append("case_study_prose")
    if not table_status["valid"]:
        failed.append("table_interpretation")
    if section_errors:
        failed.append("section_argument_flow")

    return {
        "valid": not failed,
        "required": True,
        "target": target,
        "failed_checks": failed,
        "raw_artifact_phrases": raw_phrases,
        "raw_field_label_count": len(raw_field_labels),
        "case_study_prose": case_status,
        "table_interpretation": table_status,
        "section_argument_flow_errors": section_errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_publication_prose(args.review.read_text(encoding="utf-8"), args.target)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
