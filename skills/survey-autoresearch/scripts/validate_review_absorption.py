#!/usr/bin/env python3
"""Check whether final review absorbs deep artifacts instead of only coexisting with them."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _ab_ids(citation_plan: list[dict]) -> set[str]:
    return {
        item["paper_id"]
        for item in citation_plan
        if item.get("paper_id") and str(item.get("depth") or "").upper() in {"A", "B"}
    }


def _contains_identifier(text: str, paper_id: str, title: str | None) -> bool:
    if paper_id and paper_id in text:
        return True
    if title:
        title_words = [word for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{3,}", title) if len(word) > 3]
        return bool(title_words) and sum(1 for word in title_words[:5] if word.lower() in text.lower()) >= min(2, len(title_words))
    return False


def _strip_tables(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("|"))


TITLE_STOP_WORDS = {
    "paper",
    "system",
    "survey",
    "method",
    "model",
    "benchmark",
    "memory",
    "review",
    "approach",
    "framework",
}


def _title_words(title: str | None) -> list[str]:
    if not title:
        return []
    return [
        word
        for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{3,}", title)
        if len(word) > 3 and word.lower() not in TITLE_STOP_WORDS
    ]


def _context_window(text: str, paper_id: str, title: str | None, radius: int = 900) -> str:
    candidates = []
    if title:
        candidates.append(re.escape(title))
        title_words = _title_words(title)
        if title_words:
            candidates.append(r".{0,120}".join(re.escape(word) for word in title_words[:3]))
    if paper_id:
        candidates.append(re.escape(paper_id))
    for pattern in candidates:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            start = max(0, match.start() - radius)
            end = min(len(text), match.end() + radius)
            return text[start:end]
    if title:
        title_words = _title_words(title)
        lower = text.lower()
        for word in title_words[:5]:
            idx = lower.find(word.lower())
            if idx < 0:
                continue
            local = lower[max(0, idx - 160): min(len(lower), idx + 160)]
            hits = sum(1 for candidate in title_words[:5] if candidate.lower() in local)
            if hits >= min(2, len(title_words[:5])):
                start = max(0, idx - radius)
                end = min(len(text), idx + len(word) + radius)
                return text[start:end]
    return ""


MECHANISM_TERMS = [
    "mechanism",
    "record",
    "write",
    "read",
    "retrieve",
    "retrieval",
    "update",
    "interface",
    "controller",
    "planner",
    "policy",
    "memory object",
    "机制",
    "记录",
    "写入",
    "读取",
    "检索",
    "更新",
    "接口",
    "控制器",
    "规划器",
]

EVIDENCE_TERMS = [
    "benchmark",
    "metric",
    "ablation",
    "baseline",
    "evidence",
    "oracle",
    "wrong-memory",
    "stale-memory",
    "no-memory",
    "基准",
    "指标",
    "消融",
    "对照",
    "证据",
]

LIMITATION_TERMS = [
    "limitation",
    "failure",
    "confounder",
    "weak",
    "unclear",
    "latency",
    "stale",
    "false recall",
    "限制",
    "失败",
    "混淆",
    "不足",
    "延迟",
    "过期",
]

NODE_TERMS = [
    "taxonomy",
    "node",
    "family",
    "representation",
    "system model",
    "method family",
    "分类",
    "节点",
    "方法族",
    "表征",
    "系统模型",
]


def _has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower or term in text for term in terms)


def _paper_context_status(prose_text: str, paper_id: str, card: dict) -> dict:
    context = _context_window(prose_text, paper_id, card.get("title"))
    if not context:
        return {"absorbed": False, "missing": ["prose_mention"], "context_chars": 0}
    checks = {
        "mechanism": _has_any(context, MECHANISM_TERMS),
        "evidence": _has_any(context, EVIDENCE_TERMS),
        "limitation": _has_any(context, LIMITATION_TERMS),
        "node_or_taxonomy": _has_any(context, NODE_TERMS),
    }
    missing = [name for name, passed in checks.items() if not passed]
    return {
        "absorbed": not missing,
        "missing": missing,
        "context_chars": len(context),
        "checks": checks,
    }


def validate_review_absorption(task_dir: Path, target: str = "full") -> dict:
    if target not in {"full", "csur"}:
        return {"valid": True, "required": False, "failed_checks": []}
    state_dir = task_dir / "state"
    outputs_dir = task_dir / "outputs"
    review = (outputs_dir / "review.md").read_text(encoding="utf-8") if (outputs_dir / "review.md").exists() else ""
    citation_plan = read_jsonl(state_dir / "citation_plan.jsonl")
    cards = read_jsonl(state_dir / "paper_cards.jsonl")
    card_by_id = {item.get("paper_id"): item for item in cards if item.get("paper_id")}
    required_ids = _ab_ids(citation_plan)
    appendix_text = ""
    for name in ["coverage_matrix.md", "appendix.md", "worked_examples.md", "node_paper_matrix.md"]:
        path = outputs_dir / name
        if path.exists():
            appendix_text += "\n" + path.read_text(encoding="utf-8")
    review_or_appendix = review + "\n" + appendix_text
    missing_papers = [
        paper_id
        for paper_id in sorted(required_ids)
        if not _contains_identifier(review_or_appendix, paper_id, card_by_id.get(paper_id, {}).get("title"))
    ]

    prose_review = _strip_tables(review)
    paper_context = {
        paper_id: _paper_context_status(prose_review, paper_id, card_by_id.get(paper_id, {}))
        for paper_id in sorted(required_ids)
        if paper_id in card_by_id and _contains_identifier(review, paper_id, card_by_id.get(paper_id, {}).get("title"))
    }
    contextual_absorbed = [
        paper_id for paper_id, status in paper_context.items() if status["absorbed"]
    ]
    papers_without_context = [
        paper_id for paper_id, status in paper_context.items() if not status["absorbed"]
    ]
    min_contextual = min(len(required_ids), 4 if target == "full" else 6)

    required_review_terms = {
        "worked_examples": ["worked example", "worked-example", "worked paper", "case study", "case studies", "机制解剖", "案例", "paper example"],
        "benchmark_landscape": ["benchmark landscape", "memory pressure", "confounders", "baseline", "基准"],
        "method_taxonomy": ["method taxonomy", "write trigger", "read key", "update policy", "controller interface", "方法"],
        "node_matrix": ["node", "representative papers", "mechanism pattern", "evaluation signal", "系统节点"],
        "newcomer": ["tutorial primer", "glossary", "running example", "入门", "术语", "贯穿例子"],
    }
    missing_terms = [
        name for name, terms in required_review_terms.items()
        if not any(term.lower() in review.lower() for term in terms)
    ]
    required_files = [
        "worked_examples.md",
        "benchmark_landscape.md",
        "method_taxonomy.md",
        "node_paper_matrix.md",
        "glossary.md",
        "running_example.md",
        "evaluation_protocol.md",
        "design_guidelines.md",
        "coverage_matrix.md",
    ]
    missing_files = [
        f"outputs/{name}" for name in required_files
        if not (outputs_dir / name).exists() or not (outputs_dir / name).read_text(encoding="utf-8").strip()
    ]
    dossier_dir = outputs_dir / "section_dossiers"
    dossier_count = len(list(dossier_dir.glob("*.md"))) if dossier_dir.exists() else 0
    failed = []
    if missing_papers:
        failed.append("missing_worked_paper_absorption")
    if len(contextual_absorbed) < min_contextual:
        failed.append("insufficient_contextual_absorption")
    if missing_terms:
        failed.append("missing_review_artifact_absorption")
    if "newcomer" in missing_terms:
        failed.append("missing_newcomer_artifact_absorption")
    if missing_files or dossier_count == 0:
        failed.append("missing_newcomer_artifact_absorption")
    return {
        "valid": not failed,
        "required": True,
        "target": target,
        "failed_checks": failed,
        "missing_papers": missing_papers,
        "contextual_absorbed": contextual_absorbed,
        "papers_without_context": papers_without_context,
        "paper_context": paper_context,
        "min_contextual_absorption": min_contextual,
        "missing_review_terms": missing_terms,
        "missing_files": missing_files,
        "section_dossiers": dossier_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_review_absorption(args.task_dir, args.target)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
