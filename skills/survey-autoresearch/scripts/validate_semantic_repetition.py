#!/usr/bin/env python3
"""Detect repetition that usually means a review is padding depth."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


REPEATED_TEMPLATE_PATTERNS = [
    r"因此，?未来综述和方法论文都应把[^。]{1,40}写成一等对象",
    r"future surveys and method papers should treat[^.]{1,80}as a first-class object",
    r"this paragraph repeats the same design implication",
    r"深入讨论[:：]",
]


def _normalize(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\[[^\]]+\]", " ", value)
    value = re.sub(r"\([^)]{0,80}\)", " ", value)
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _plain_blocks(text: str) -> list[str]:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    blocks: list[str] = []
    for raw in re.split(r"\n\s*\n", text):
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("|") or re.match(r"^#{1,6}\s+", stripped):
            continue
        plain = _normalize(stripped)
        if len(plain) >= 140:
            blocks.append(plain)
    return blocks


def _ngrams(text: str, n: int = 5) -> set[str]:
    tokens = text.split()
    if len(tokens) < n:
        return set(tokens)
    return {" ".join(tokens[idx: idx + n]) for idx in range(len(tokens) - n + 1)}


def _similarity(left: str, right: str) -> float:
    left_grams = _ngrams(left)
    right_grams = _ngrams(right)
    if not left_grams or not right_grams:
        return 0.0
    return len(left_grams & right_grams) / max(1, min(len(left_grams), len(right_grams)))


def validate_semantic_repetition(text: str, target: str = "full") -> dict:
    if target not in {"full", "csur"}:
        return {"valid": True, "required": False, "failed_checks": []}

    headings = [
        _normalize(match.group(2))
        for match in re.finditer(r"^(#{2,4})\s+(.+?)\s*$", text, flags=re.MULTILINE)
        if _normalize(match.group(2)) not in {"references", "bibliography", "参考文献"}
    ]
    heading_counts = Counter(headings)
    duplicate_headings = {
        heading: count for heading, count in heading_counts.items() if count > 1 and heading
    }

    template_counts: dict[str, int] = {}
    for pattern in REPEATED_TEMPLATE_PATTERNS:
        count = len(re.findall(pattern, text, flags=re.IGNORECASE))
        if count > 2:
            template_counts[pattern] = count

    blocks = _plain_blocks(text)
    repeated_pairs: list[dict] = []
    for left_idx, left in enumerate(blocks):
        for right_idx in range(left_idx + 1, min(len(blocks), left_idx + 80)):
            score = _similarity(left, blocks[right_idx])
            if score >= 0.58:
                repeated_pairs.append({
                    "left": left_idx + 1,
                    "right": right_idx + 1,
                    "similarity": round(score, 3),
                })
                break
        if len(repeated_pairs) >= 5:
            break

    tail = text[int(len(text) * 0.75):] if text else ""
    tail_depth_headings = len(re.findall(r"^#{2,4}\s+.*(?:深入讨论|extended synthesis|cross-task)", tail, flags=re.IGNORECASE | re.MULTILINE))

    failed = []
    if duplicate_headings:
        failed.append("duplicate_headings")
    if template_counts:
        failed.append("repeated_templates")
    if repeated_pairs:
        failed.append("repeated_paragraphs")
    if tail_depth_headings >= 3:
        failed.append("tail_padding_repetition")

    return {
        "valid": not failed,
        "required": True,
        "target": target,
        "failed_checks": failed,
        "duplicate_headings": duplicate_headings,
        "repeated_templates": template_counts,
        "repeated_paragraph_pairs": repeated_pairs,
        "tail_depth_headings": tail_depth_headings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_semantic_repetition(args.review.read_text(encoding="utf-8"), args.target)
    text = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
