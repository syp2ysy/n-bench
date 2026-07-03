#!/usr/bin/env python3
"""Prepare independent expert-review packets without fabricating reviews."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_REVIEWERS = [
    ("domain_expert", "Domain Expert Reviewer"),
    ("survey_architect", "Survey Architect Reviewer"),
    ("evidence_factuality", "Evidence/Factuality Reviewer"),
    ("newcomer_tutorial", "Newcomer/Tutorial Reviewer"),
    ("style_publication", "Style/Publication Reviewer"),
]


def read_json(path: Path) -> dict:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def freeze_review_round(task_dir: Path, review_round_id: str | None = None) -> dict:
    state = task_dir / "state"
    outputs = task_dir / "outputs"
    round_id = review_round_id or f"round-{utc_now()}"
    artifacts = [
        outputs / "review.md",
        outputs / "appendix.md",
        state / "argument_graph.yml",
        state / "section_evidence_plans.jsonl",
    ]
    frozen = {str(path.relative_to(task_dir)): sha256_file(path) for path in artifacts}
    status = {
        "review_round_id": round_id,
        "status": "frozen",
        "review_freeze": {
            "review_round_id": round_id,
            "started_at": utc_now(),
            "frozen_artifacts": frozen,
            "article_hash": frozen.get("outputs/review.md", ""),
        },
        "all_reports_received": False,
        "reviewers_expected": len(REQUIRED_REVIEWERS),
        "reviewers_returned": 0,
        "repaired_article_hash": None,
    }
    write_json(state / "expert_review_round_status.json", status)
    return status


def dispatch_packets(task_dir: Path, review_round_id: str | None = None) -> dict:
    state = task_dir / "state"
    packets_dir = state / "expert_review_packets"
    packets_dir.mkdir(exist_ok=True)
    status = read_json(state / "expert_review_round_status.json")
    if not status.get("review_freeze"):
        status = freeze_review_round(task_dir, review_round_id)
    round_id = str(status.get("review_round_id") or review_round_id or "round-1")
    invocations = []
    for reviewer_id, persona in REQUIRED_REVIEWERS:
        packet_path = packets_dir / f"{reviewer_id}.json"
        packet = {
            "review_round_id": round_id,
            "reviewer_id": reviewer_id,
            "persona": persona,
            "instructions": (
                "Use a fresh context. Read the article and selected evidence artifacts. "
                "Do not read previous reviewer reports or repair actions from this round. "
                "Return one JSONL row matching expert_review_contract.md."
            ),
            "inputs": [
                "outputs/review.md",
                "outputs/appendix.md",
                "state/paper_mechanism_cards.jsonl",
                "state/claim_evidence_spans.jsonl",
                "outputs/contribution_tree.yml",
                "state/argument_graph.yml",
                "state/section_evidence_plans.jsonl",
            ],
            "forbidden_inputs": ["previous reviewer reports", "state/expert_review_reports.jsonl", "repair actions from this round"],
            "output": "state/expert_review_reports.jsonl",
        }
        write_json(packet_path, packet)
        invocations.append(
            {
                "review_round_id": round_id,
                "reviewer_id": reviewer_id,
                "persona": persona,
                "fresh_context": False,
                "subagent_session_id": "",
                "inputs": packet["inputs"],
                "forbidden_inputs": packet["forbidden_inputs"],
                "output": packet["output"],
                "status": "dispatched",
                "packet": str(packet_path.relative_to(task_dir)),
                "timestamp": utc_now(),
            }
        )
    write_jsonl(state / "expert_review_invocations.jsonl", invocations)
    return {"status": "dispatched", "review_round_id": round_id, "packets": len(invocations)}


def collect_status(task_dir: Path) -> dict:
    state = task_dir / "state"
    status = read_json(state / "expert_review_round_status.json")
    reports = read_jsonl(state / "expert_review_reports.jsonl")
    invocations = read_jsonl(state / "expert_review_invocations.jsonl")
    returned_ids = {str(report.get("reviewer_id") or "") for report in reports}
    updated = []
    for invocation in invocations:
        item = dict(invocation)
        if str(item.get("reviewer_id") or "") in returned_ids and item.get("status") == "dispatched":
            item["status"] = "returned"
        updated.append(item)
    if updated:
        write_jsonl(state / "expert_review_invocations.jsonl", updated)
    returned = len(returned_ids)
    status["reviewers_returned"] = returned
    status["all_reports_received"] = returned >= len(REQUIRED_REVIEWERS)
    status["status"] = "all_reports_received" if status["all_reports_received"] else "collecting_reviews"
    write_json(state / "expert_review_round_status.json", status)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--review-round-id")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--dispatch", action="store_true")
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        result = freeze_review_round(args.task_dir, args.review_round_id)
    elif args.dispatch:
        result = dispatch_packets(args.task_dir, args.review_round_id)
    elif args.collect:
        result = collect_status(args.task_dir)
    else:
        result = {"error": "choose --freeze, --dispatch, or --collect"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
