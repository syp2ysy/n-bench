#!/usr/bin/env python3
"""Plan auditable full-text source routes for A/B papers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_jsonl, write_jsonl, write_json
    from .status_schema import STATUS_SCHEMA_VERSION, status_envelope
    from .validate_paper_understanding import depth_ids
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_jsonl, write_jsonl, write_json
    from status_schema import STATUS_SCHEMA_VERSION, status_envelope
    from validate_paper_understanding import depth_ids


COMPONENT = "full_text_source_planner"


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _clean_url(value) -> str:
    return str(value or "").strip()


def _candidate_urls(paper: dict) -> list[dict]:
    candidates: list[dict] = []
    arxiv_id = str(paper.get("arxiv_id") or "").strip()
    if arxiv_id:
        candidates.append({"source_kind": "arxiv_pdf", "url": f"https://arxiv.org/pdf/{arxiv_id}"})
        candidates.append({"source_kind": "paper_html", "url": f"https://arxiv.org/abs/{arxiv_id}"})
    for field, kind in [
        ("openreview_url", "openreview_pdf"),
        ("official_url", "official_pdf_or_html"),
        ("url", "official_pdf_or_html"),
    ]:
        url = _clean_url(paper.get(field))
        if url:
            candidates.append({"source_kind": kind, "url": url})
    doi = str(paper.get("doi") or "").strip()
    if doi:
        candidates.append({"source_kind": "publisher_html", "url": f"https://doi.org/{doi}"})
    for source in paper.get("verified_sources") or []:
        if isinstance(source, dict):
            url = _clean_url(source.get("url") or source.get("source_url"))
            if url:
                candidates.append({"source_kind": str(source.get("source_kind") or source.get("source_type") or "verified_source"), "url": url})
    seen = set()
    result = []
    for candidate in candidates:
        key = candidate["url"]
        if key and key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def build_full_text_fetch_plan(task_dir: Path) -> dict:
    state = _state(task_dir)
    papers = {str(paper.get("paper_id")): paper for paper in read_jsonl(state / "papers.jsonl") if paper.get("paper_id")}
    required_ids = sorted(depth_ids(read_jsonl(state / "citation_plan.jsonl")))
    rows = []
    status_rows = []
    for pid in required_ids:
        paper = papers.get(pid, {})
        candidates = _candidate_urls(paper)
        row = {
            "paper_id": pid,
            "title": paper.get("title"),
            "candidate_urls": [candidate["url"] for candidate in candidates],
            "source_candidates": candidates,
            "status": "planned" if candidates else "blocked_no_full_text_route",
        }
        rows.append(row)
        status_rows.append({**row, "access_status": "not_attempted", "extraction_status": "not_attempted", "captured_excerpts": []})
    write_jsonl(state / "full_text_fetch_plan.jsonl", rows)
    write_jsonl(state / "full_text_fetch_status.jsonl", status_rows)
    summary = {
        "planned_paper_count": len(rows),
        "with_candidate_url_count": len([row for row in rows if row["candidate_urls"]]),
        "blocked_no_route_count": len([row for row in rows if not row["candidate_urls"]]),
    }
    result = {
        **status_envelope(
            COMPONENT,
            "planned",
            next_action="spawn_paper_understanding_agents",
            terminal=False,
            blocked=False,
            summary=summary,
        ),
        "summary": summary,
    }
    write_json(state / "full_text_source_plan_status.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    args = parser.parse_args()
    result = build_full_text_fetch_plan(args.task_dir)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
