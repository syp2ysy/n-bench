#!/usr/bin/env python3
"""Downgrade unavailable A/B papers and promote replacements from verified C papers."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_json, read_jsonl, write_jsonl
    from .validate_coverage import validate_coverage
    from .validate_topic_relevance import DEPTH_RANK, audit_by_paper
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_json, read_jsonl, write_jsonl
    from validate_coverage import validate_coverage
    from validate_topic_relevance import DEPTH_RANK, audit_by_paper


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash_rows(rows: list[dict]) -> str:
    payload = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verified_paper_ids(task_dir: Path) -> set[str]:
    ids = set()
    for paper in read_jsonl(_state(task_dir) / "papers.jsonl"):
        if (
            str(paper.get("paper_id") or "").strip()
            and (paper.get("verified") is True or str(paper.get("verification_status") or "").lower() == "verified")
        ):
            ids.add(str(paper["paper_id"]))
    return ids


def _topic_relevance_replacement_ids(task_dir: Path, desired_depth: str) -> set[str] | None:
    audits = audit_by_paper(read_jsonl(_state(task_dir) / "topic_relevance_audit.jsonl"))
    if not audits:
        return None
    allowed: set[str] = set()
    desired_rank = DEPTH_RANK.get(desired_depth, 0)
    for pid, audit in audits.items():
        if str(audit.get("relevance_grade") or "") != "core":
            continue
        if audit.get("family_label_supported") is not True:
            continue
        if DEPTH_RANK.get(str(audit.get("allowed_depth") or ""), 0) >= desired_rank:
            allowed.add(pid)
    return allowed


def rebalance_ab_selection(task_dir: Path, blocked_paper_ids: list[str], target: str = "full", reason: str = "full_text") -> dict:
    state = _state(task_dir)
    citation_plan = read_jsonl(state / "citation_plan.jsonl")
    before_hash = _hash_rows(citation_plan)
    blocked = {str(pid) for pid in blocked_paper_ids if str(pid).strip()}
    verified_ids = _verified_paper_ids(task_dir)
    decisions = []
    for row in citation_plan:
        pid = str(row.get("paper_id") or "")
        old_depth = str(row.get("depth") or row.get("level") or "").upper()
        if pid not in blocked or old_depth not in {"A", "B"}:
            continue
        topic_allowed = _topic_relevance_replacement_ids(task_dir, old_depth) if reason == "topic_relevance" else None
        replacement = next(
            (
                candidate for candidate in citation_plan
                if str(candidate.get("paper_id") or "") not in blocked
                and str(candidate.get("paper_id") or "") in verified_ids
                and str(candidate.get("depth") or candidate.get("level") or "").upper() == "C"
                and (topic_allowed is None or str(candidate.get("paper_id") or "") in topic_allowed)
            ),
            None,
        )
        if replacement is None:
            return {"status": "blocked", "error": "no_verified_c_replacement", "blocked_paper_id": pid, "reason": reason}
        row["depth"] = "C"
        row["evidence_limited"] = True
        row["downgrade_reason"] = "topic_relevance_failed_for_a_b" if reason == "topic_relevance" else "full_text_unavailable_or_insufficient_for_a_b"
        replacement["depth"] = old_depth
        decisions.append(
            {
                "decided_at": _utc_now(),
                "downgraded_paper_id": pid,
                "replacement_paper_id": replacement.get("paper_id"),
                "old_depth": old_depth,
                "new_depth": "C",
                "replacement_depth": old_depth,
                "reason": "topic_relevance_failed_for_a_b" if reason == "topic_relevance" else "full_text_unavailable_or_insufficient_for_a_b",
            }
        )
    if not decisions:
        return {"status": "no_op", "blocked_paper_ids": sorted(blocked)}
    after_hash = _hash_rows(citation_plan)
    for decision in decisions:
        decision["citation_plan_hash_before"] = before_hash
        decision["citation_plan_hash_after"] = after_hash
    write_jsonl(state / "citation_plan.jsonl", citation_plan)
    write_jsonl(state / "ab_rebalance_decisions.jsonl", read_jsonl(state / "ab_rebalance_decisions.jsonl") + decisions)
    coverage = validate_coverage(
        read_jsonl(state / "raw_candidates.jsonl"),
        read_jsonl(state / "search_routes.jsonl"),
        read_jsonl(state / "lqs_scores.jsonl"),
        read_json(state / "corpus_expansion.json"),
        read_jsonl(state / "papers.jsonl"),
        citation_plan,
        target,
        survey_type_plan=(state / "survey_type_plan.yml").read_text(encoding="utf-8") if (state / "survey_type_plan.yml").exists() else "",
        contribution_tree=(task_dir / "outputs" / "contribution_tree.yml").read_text(encoding="utf-8") if (task_dir / "outputs" / "contribution_tree.yml").exists() else "",
        topic_relevance_audit=read_jsonl(state / "topic_relevance_audit.jsonl") or None,
    )
    return {
        "status": "rebalanced" if coverage.get("valid") else "rebalanced_but_coverage_invalid",
        "decision_count": len(decisions),
        "decisions": decisions,
        "coverage_valid": coverage.get("valid"),
        "coverage_errors": coverage.get("missing") or coverage.get("retained_missing") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--blocked-paper-ids", required=True, help="Comma-separated paper ids to downgrade")
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--reason", choices=["full_text", "topic_relevance"], default="full_text")
    args = parser.parse_args()
    result = rebalance_ab_selection(args.task_dir, [item.strip() for item in args.blocked_paper_ids.split(",") if item.strip()], args.target, args.reason)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
