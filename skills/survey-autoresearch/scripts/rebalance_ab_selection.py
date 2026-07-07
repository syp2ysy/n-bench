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
    from .validate_coverage import TARGETS, validate_coverage
    from .validate_topic_relevance import DEPTH_RANK, audit_by_paper, normalize_family
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_json, read_jsonl, write_jsonl
    from validate_coverage import TARGETS, validate_coverage
    from validate_topic_relevance import DEPTH_RANK, audit_by_paper, normalize_family


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash_rows(rows: list[dict]) -> str:
    payload = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _score_by_paper(lqs_scores: list[dict]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for row in lqs_scores:
        pid = str(row.get("paper_id") or row.get("candidate_id") or "").strip()
        if not pid:
            continue
        raw_score = row.get("lqs", row.get("score", row.get("lqs_score", 0)))
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 0.0
        scores[pid] = max(scores.get(pid, 0.0), score)
    return scores


def _candidate_lookup(raw_candidates: list[dict]) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for row in raw_candidates:
        keys = [
            row.get("paper_id"),
            row.get("arxiv_id"),
            row.get("arxiv"),
            row.get("doi"),
            row.get("url"),
            row.get("official_url"),
            row.get("landing_page_url"),
            row.get("pdf_url"),
            row.get("candidate_id"),
            row.get("source_candidate_id"),
        ]
        for raw_key in keys:
            key = str(raw_key or "").strip()
            if key and key not in lookup:
                lookup[key] = row
    return lookup


def _selection_sort_key(row: dict, audit: dict, score_by_id: dict[str, float]) -> tuple:
    pid = str(audit.get("paper_id") or row.get("paper_id") or "")
    cid = str(audit.get("candidate_id") or row.get("candidate_id") or "")
    score = max(score_by_id.get(pid, 0.0), score_by_id.get(cid, 0.0))
    try:
        year = int(row.get("year") or audit.get("year") or 0)
    except (TypeError, ValueError):
        year = 0
    title = str(row.get("title") or audit.get("title") or pid)
    return (-score, -year, title, pid)


def _paper_from_audit(candidate: dict, audit: dict) -> dict:
    pid = str(audit.get("paper_id") or candidate.get("paper_id") or "").strip()
    cid = str(audit.get("candidate_id") or candidate.get("candidate_id") or pid).strip()
    family = str(audit.get("corrected_family") or candidate.get("family") or candidate.get("topic_axis") or "unassigned").strip()
    grade = str(audit.get("relevance_grade") or "")
    role = str(audit.get("allowed_role") or "")
    if role == "core":
        survey_role = "method"
    elif role == "related_survey":
        survey_role = "survey"
    elif role == "background":
        survey_role = "background"
    else:
        survey_role = "exclude"
    paper = {
        "paper_id": pid,
        "source_candidate_id": cid,
        "title": candidate.get("title") or audit.get("title") or pid,
        "authors": candidate.get("authors") or [],
        "year": candidate.get("year"),
        "abstract": candidate.get("abstract") or candidate.get("summary") or "",
        "url": candidate.get("url") or candidate.get("pdf_url") or candidate.get("landing_page_url") or "",
        "doi": candidate.get("doi") or "",
        "arxiv_id": candidate.get("arxiv_id") or candidate.get("arxiv") or "",
        "source": candidate.get("source") or "",
        "venue": candidate.get("venue") or candidate.get("venue_name") or "",
        "verified": True,
        "verification_status": "verified",
        "verified_sources": candidate.get("verified_sources") or [candidate.get("source") or "topic_relevance_audit"],
        "verification_note": "Initialized from worker-produced topic relevance audit and discovery metadata.",
        "survey_role": survey_role,
        "family": family,
        "topic_axis": family,
        "topic_relevance_grade": grade,
        "topic_relevance_allowed_depth": audit.get("allowed_depth"),
    }
    return {key: value for key, value in paper.items() if value not in (None, "", [])}


def _norm_identity(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _identity_keys(row: dict) -> set[str]:
    keys: set[str] = set()
    for key in ["doi", "arxiv_id", "url", "official_url", "landing_page_url", "pdf_url", "title"]:
        value = _norm_identity(row.get(key))
        if value:
            keys.add(f"{key}:{value}" if key == "title" else value)
    return keys


def _raw_candidate_id(candidate: dict) -> str:
    return str(candidate.get("candidate_id") or candidate.get("paper_id") or candidate.get("source_candidate_id") or "").strip()


def _repair_paper_candidate_linkage(papers: list[dict], raw_candidates: list[dict]) -> tuple[list[dict], list[dict]]:
    candidate_ids = {
        str(candidate.get(key) or "").strip()
        for candidate in raw_candidates
        for key in ["candidate_id", "paper_id", "source_candidate_id"]
        if str(candidate.get(key) or "").strip()
    }
    identity_lookup: dict[str, dict] = {}
    for candidate in raw_candidates:
        for key in _identity_keys(candidate):
            identity_lookup.setdefault(key, candidate)
    repaired: list[dict] = []
    decisions: list[dict] = []
    for paper in papers:
        row = dict(paper)
        source_candidate_id = str(row.get("source_candidate_id") or "").strip()
        if source_candidate_id and source_candidate_id in candidate_ids:
            repaired.append(row)
            continue
        match = next((identity_lookup.get(key) for key in _identity_keys(row) if identity_lookup.get(key)), None)
        candidate_id = _raw_candidate_id(match or {})
        if candidate_id:
            row["source_candidate_id"] = candidate_id
            decisions.append(
                {
                    "decided_at": _utc_now(),
                    "decision": "repair_paper_candidate_linkage",
                    "paper_id": row.get("paper_id"),
                    "source_candidate_id_before": source_candidate_id,
                    "source_candidate_id_after": candidate_id,
                    "matched_title": (match or {}).get("title"),
                }
            )
        repaired.append(row)
    return repaired, decisions


def sync_related_surveys_from_topic_audit(task_dir: Path, target: str = "full") -> dict:
    """Retain worker-audited direct related surveys as C-level survey records."""

    state = _state(task_dir)
    raw_candidates = read_jsonl(state / "raw_candidates.jsonl")
    papers = read_jsonl(state / "papers.jsonl")
    citation_plan = read_jsonl(state / "citation_plan.jsonl")
    audit_rows = read_jsonl(state / "topic_relevance_audit.jsonl")
    if not raw_candidates or not audit_rows:
        return {"status": "blocked", "error": "raw_candidates_or_topic_audit_missing"}
    before_papers_hash = _hash_rows(papers)
    before_citation_hash = _hash_rows(citation_plan)
    papers, linkage_decisions = _repair_paper_candidate_linkage(papers, raw_candidates)
    candidate_by_id = _candidate_lookup(raw_candidates)
    citation_ids = {str(row.get("paper_id") or "") for row in citation_plan}
    retained_ids = {str(row.get("paper_id") or "") for row in papers}
    retained_identity = {key for paper in papers for key in _identity_keys(paper)}
    added_papers: list[dict] = []
    added_citation: list[dict] = []
    for audit in audit_rows:
        if str(audit.get("relevance_grade") or "") != "direct_related_survey":
            continue
        if str(audit.get("allowed_role") or "") != "related_survey":
            continue
        pid = str(audit.get("paper_id") or "").strip()
        if not pid or pid in retained_ids:
            continue
        candidate = candidate_by_id.get(pid) or candidate_by_id.get(str(audit.get("candidate_id") or "")) or {}
        if not candidate:
            continue
        identity = _identity_keys(candidate) | _identity_keys(audit)
        if identity & retained_identity:
            continue
        paper = _paper_from_audit(candidate, audit)
        paper["survey_role"] = "survey"
        paper["selection_reason"] = "related_survey_topic_audit_sync"
        papers.append(paper)
        retained_ids.add(pid)
        retained_identity.update(_identity_keys(paper) | identity)
        added_papers.append(paper)
        if pid not in citation_ids:
            citation_row = {
                "paper_id": pid,
                "depth": "C",
                "role": "related_survey",
                "topic_relevance_grade": "direct_related_survey",
                "family": normalize_family(audit.get("corrected_family")),
                "selection_reason": "related_survey_topic_audit_sync",
            }
            citation_plan.append(citation_row)
            citation_ids.add(pid)
            added_citation.append(citation_row)
    if not added_papers and not linkage_decisions:
        return {
            "status": "no_op",
            "paper_count": len(papers),
            "citation_plan_count": len(citation_plan),
        }
    write_jsonl(state / "papers.jsonl", papers)
    write_jsonl(state / "citation_plan.jsonl", citation_plan)
    after_papers_hash = _hash_rows(papers)
    after_citation_hash = _hash_rows(citation_plan)
    decision = {
        "decided_at": _utc_now(),
        "decision": "sync_related_surveys_from_topic_audit",
        "target": target,
        "added_paper_ids": [row.get("paper_id") for row in added_papers],
        "added_citation_ids": [row.get("paper_id") for row in added_citation],
        "linkage_repair_count": len(linkage_decisions),
        "papers_hash_before": before_papers_hash,
        "papers_hash_after": after_papers_hash,
        "citation_plan_hash_before": before_citation_hash,
        "citation_plan_hash_after": after_citation_hash,
    }
    write_jsonl(state / "related_survey_sync_decisions.jsonl", read_jsonl(state / "related_survey_sync_decisions.jsonl") + [decision])
    if linkage_decisions:
        write_jsonl(state / "candidate_linkage_repair_decisions.jsonl", read_jsonl(state / "candidate_linkage_repair_decisions.jsonl") + linkage_decisions)
    coverage = validate_coverage(
        raw_candidates,
        read_jsonl(state / "search_routes.jsonl"),
        read_jsonl(state / "lqs_scores.jsonl"),
        read_json(state / "corpus_expansion.json"),
        papers,
        citation_plan,
        target,
        survey_type_plan=(state / "survey_type_plan.yml").read_text(encoding="utf-8") if (state / "survey_type_plan.yml").exists() else "",
        contribution_tree=(task_dir / "outputs" / "contribution_tree.yml").read_text(encoding="utf-8") if (task_dir / "outputs" / "contribution_tree.yml").exists() else "",
        topic_relevance_audit=audit_rows,
    )
    return {
        "status": "synced" if coverage.get("valid") else "synced_but_coverage_invalid",
        "decision": decision,
        "coverage_valid": coverage.get("valid"),
        "coverage_errors": coverage.get("missing") or coverage.get("retained_missing") or [],
    }


def initialize_ab_selection_from_topic_audit(task_dir: Path, target: str = "full") -> dict:
    """Create the first retained corpus/citation plan from worker topic audits.

    This runs only when there is no existing retained corpus or citation plan. It
    consumes worker-produced relevance grades and allowed depths; it does not make
    independent topic judgments.
    """
    state = _state(task_dir)
    existing_papers = read_jsonl(state / "papers.jsonl")
    existing_citation = read_jsonl(state / "citation_plan.jsonl")
    if existing_papers or existing_citation:
        return {
            "status": "skipped_existing_selection",
            "paper_count": len(existing_papers),
            "citation_plan_count": len(existing_citation),
        }
    raw_candidates = read_jsonl(state / "raw_candidates.jsonl")
    audit_rows = read_jsonl(state / "topic_relevance_audit.jsonl")
    if not raw_candidates:
        return {"status": "blocked", "error": "raw_candidates_missing"}
    if not audit_rows:
        return {"status": "blocked", "error": "topic_relevance_audit_missing"}
    audits = audit_by_paper(audit_rows)
    candidate_by_id = _candidate_lookup(raw_candidates)
    score_by_id = _score_by_paper(read_jsonl(state / "lqs_scores.jsonl"))
    retained_papers: list[dict] = []
    for pid, audit in audits.items():
        if str(audit.get("relevance_grade") or "") == "out_of_scope" or str(audit.get("allowed_depth") or "") == "exclude":
            continue
        candidate = candidate_by_id.get(pid) or candidate_by_id.get(str(audit.get("candidate_id") or "")) or {}
        retained_papers.append(_paper_from_audit(candidate, audit))

    if len(retained_papers) < TARGETS[target]["verified"]:
        return {
            "status": "blocked",
            "error": "insufficient_topic_qualified_verified_papers",
            "retained_count": len(retained_papers),
            "required": TARGETS[target]["verified"],
        }

    retained_ids = {str(row.get("paper_id") or "") for row in retained_papers}
    eligible_a = []
    eligible_b = []
    related = []
    background = []
    for pid in sorted(retained_ids):
        audit = audits.get(pid, {})
        candidate = candidate_by_id.get(pid) or candidate_by_id.get(str(audit.get("candidate_id") or "")) or {}
        grade = str(audit.get("relevance_grade") or "")
        allowed_depth = str(audit.get("allowed_depth") or "")
        if grade == "core" and audit.get("family_label_supported") is True and allowed_depth == "A":
            eligible_a.append((candidate, audit))
        elif grade == "core" and audit.get("family_label_supported") is True and allowed_depth in {"A", "B"}:
            eligible_b.append((candidate, audit))
        elif grade == "direct_related_survey":
            related.append((candidate, audit))
        else:
            background.append((candidate, audit))
    eligible_a.sort(key=lambda item: _selection_sort_key(item[0], item[1], score_by_id))
    eligible_b.sort(key=lambda item: _selection_sort_key(item[0], item[1], score_by_id))
    related.sort(key=lambda item: _selection_sort_key(item[0], item[1], score_by_id))
    background.sort(key=lambda item: _selection_sort_key(item[0], item[1], score_by_id))

    a_target = TARGETS[target]["a"]
    b_target = TARGETS[target]["b"]
    a_ids = [str(audit.get("paper_id")) for _, audit in eligible_a[:a_target]]
    if len(a_ids) < a_target:
        return {"status": "blocked", "error": "insufficient_topic_qualified_a_papers", "available": len(a_ids), "required": a_target}
    selected = set(a_ids)
    b_pool = [(candidate, audit) for candidate, audit in eligible_a[a_target:] + eligible_b if str(audit.get("paper_id")) not in selected]
    b_pool.sort(key=lambda item: _selection_sort_key(item[0], item[1], score_by_id))
    b_ids = [str(audit.get("paper_id")) for _, audit in b_pool[:b_target]]
    if len(b_ids) < b_target:
        return {"status": "blocked", "error": "insufficient_topic_qualified_b_papers", "available": len(b_ids), "required": b_target}
    depth_by_id = {pid: "A" for pid in a_ids}
    depth_by_id.update({pid: "B" for pid in b_ids})
    citation_plan: list[dict] = []
    ordered_pairs = eligible_a + eligible_b + related + background
    seen: set[str] = set()
    for candidate, audit in ordered_pairs:
        pid = str(audit.get("paper_id") or "").strip()
        if not pid or pid in seen or pid not in retained_ids:
            continue
        seen.add(pid)
        row = {
            "paper_id": pid,
            "depth": depth_by_id.get(pid, "C"),
            "role": "core" if pid in depth_by_id else str(audit.get("allowed_role") or "background"),
            "topic_relevance_grade": audit.get("relevance_grade"),
            "family": normalize_family(audit.get("corrected_family")),
            "selection_reason": "initial_topic_relevance_selection",
        }
        citation_plan.append(row)
    before_papers_hash = _hash_rows([])
    before_citation_hash = _hash_rows([])
    after_papers_hash = _hash_rows(retained_papers)
    after_citation_hash = _hash_rows(citation_plan)
    write_jsonl(state / "papers.jsonl", retained_papers)
    write_jsonl(state / "citation_plan.jsonl", citation_plan)
    decision = {
        "decided_at": _utc_now(),
        "decision": "initialize_ab_selection_from_topic_audit",
        "target": target,
        "paper_count": len(retained_papers),
        "citation_plan_count": len(citation_plan),
        "a_count": len(a_ids),
        "b_count": len(b_ids),
        "related_survey_count": sum(1 for _, audit in related),
        "papers_hash_before": before_papers_hash,
        "papers_hash_after": after_papers_hash,
        "citation_plan_hash_before": before_citation_hash,
        "citation_plan_hash_after": after_citation_hash,
    }
    write_jsonl(state / "initial_selection_decisions.jsonl", read_jsonl(state / "initial_selection_decisions.jsonl") + [decision])
    coverage = validate_coverage(
        raw_candidates,
        read_jsonl(state / "search_routes.jsonl"),
        read_jsonl(state / "lqs_scores.jsonl"),
        read_json(state / "corpus_expansion.json"),
        retained_papers,
        citation_plan,
        target,
        survey_type_plan=(state / "survey_type_plan.yml").read_text(encoding="utf-8") if (state / "survey_type_plan.yml").exists() else "",
        contribution_tree=(task_dir / "outputs" / "contribution_tree.yml").read_text(encoding="utf-8") if (task_dir / "outputs" / "contribution_tree.yml").exists() else "",
        topic_relevance_audit=audit_rows,
    )
    return {
        "status": "initialized" if coverage.get("valid") else "initialized_but_coverage_invalid",
        "decision": decision,
        "coverage_valid": coverage.get("valid"),
        "coverage_errors": coverage.get("missing") or coverage.get("retained_missing") or [],
    }


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
