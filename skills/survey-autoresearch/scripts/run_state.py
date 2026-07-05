#!/usr/bin/env python3
"""Derive the compact v2 run-state summary from authoritative artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .gate_engine import evaluate_all
    from .run_expert_reviews import read_json, read_jsonl, write_json
    from .status_schema import STATUS_SCHEMA_VERSION
except ImportError:  # pragma: no cover
    from gate_engine import evaluate_all
    from run_expert_reviews import read_json, read_jsonl, write_json
    from status_schema import STATUS_SCHEMA_VERSION


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _exists_status(path: Path) -> str:
    if path.is_dir():
        return "ready" if any(path.iterdir()) else "empty"
    if path.exists():
        return "ready" if path.read_text(encoding="utf-8").strip() else "empty"
    return "missing"


def derive_run_state(task_dir: Path, target: str = "full") -> dict:
    state = task_dir / "state"
    outputs = task_dir / "outputs"
    progress = read_json(state / "progress.json")
    gates = evaluate_all(task_dir, target)
    runtime_intent = read_json(state / "runtime_active_intent.json")
    task_rows = read_jsonl(state / "tasks.jsonl")
    failure_rows = read_jsonl(state / "failure_ledger.jsonl")
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "component": "run_state",
        "target": target,
        "topic": progress.get("topic"),
        "status": gates.get("status"),
        "next_action": gates.get("next_action"),
        "blocked_by_phase": gates.get("blocked_by_phase"),
        "workflow": {
            "public_entrypoint": "runner.py",
            "gate_engine": "gate_engine.py",
            "task_queue": "tasks.jsonl",
            "legacy_driver": "survey_driver.py",
            "runtime_dispatcher": "runtime_dispatcher.py",
        },
        "research_assets": {
            "topic_profile": {"canonical": "state/topic_profile.json", "status": _exists_status(state / "topic_profile.json")},
            "corpus": {
                "raw_candidates": len(read_jsonl(state / "raw_candidates.jsonl")),
                "papers": len(read_jsonl(state / "papers.jsonl")),
                "citation_plan": len(read_jsonl(state / "citation_plan.jsonl")),
            },
            "paper_cards": {
                "canonical": "state/paper_cards",
                "legacy_source": "state/paper_mechanism_cards.jsonl",
                "status": _exists_status(state / "paper_cards"),
                "card_count": len(list((state / "paper_cards").glob("*.json"))) if (state / "paper_cards").exists() else 0,
            },
            "knowledge_tree": {"canonical": "outputs/knowledge_tree.yml", "legacy_source": "outputs/contribution_tree.yml", "status": _exists_status(outputs / "knowledge_tree.yml")},
            "spine_decision": {"canonical": "state/spine_decision.md", "status": _exists_status(state / "spine_decision.md")},
            "survey_candidate": {"canonical": "outputs/survey_candidate.md", "status": _exists_status(outputs / "survey_candidate.md")},
            "failure_ledger": {
                "canonical": "state/failure_ledger.jsonl",
                "status": _exists_status(state / "failure_ledger.jsonl"),
                "unresolved_count": len([row for row in failure_rows if row.get("status") != "resolved"]),
            },
        },
        "runtime": {
            "active_intent": runtime_intent,
            "task_count": len(task_rows),
            "pending_task_count": len([row for row in task_rows if row.get("status") in {"pending", "pending_spawn"}]),
        },
        "gates": gates.get("summary", {}),
        "updated_at": _utc_now(),
    }


def sync_run_state(task_dir: Path, target: str = "full") -> dict:
    result = derive_run_state(task_dir, target)
    write_json(task_dir / "state" / "run_state.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--sync", action="store_true")
    args = parser.parse_args()
    result = sync_run_state(args.task_dir, args.target) if args.sync else derive_run_state(args.task_dir, args.target)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
