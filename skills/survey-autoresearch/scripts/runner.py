#!/usr/bin/env python3
"""Thin v2 public runner that preserves the hardened legacy driver."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .paper_card_store import mirror_paper_cards
    from .run_state import sync_run_state
    from .survey_driver import run_until_complete as run_legacy_driver
    from .task_queue import sync_tasks
    from .topic_profile import prepare_topic_profile_request
except ImportError:  # pragma: no cover
    from paper_card_store import mirror_paper_cards
    from run_state import sync_run_state
    from survey_driver import run_until_complete as run_legacy_driver
    from task_queue import sync_tasks
    from topic_profile import prepare_topic_profile_request


def run_until_complete(task_dir: Path, target: str = "full", max_steps: int = 25) -> dict:
    topic_profile = task_dir / "state" / "topic_profile.json"
    if not topic_profile.exists() or not topic_profile.read_text(encoding="utf-8").strip():
        driver = prepare_topic_profile_request(task_dir, target)
    else:
        driver = run_legacy_driver(task_dir, target, max_steps)
    tasks = sync_tasks(task_dir)
    if (task_dir / "state" / "paper_mechanism_cards.jsonl").exists():
        mirror_paper_cards(task_dir)
    run_state = sync_run_state(task_dir, target)
    return {
        **driver,
        "component": "runner",
        "legacy_component": driver.get("component"),
        "task_queue": {
            "status": tasks.get("status"),
            "task_count": (tasks.get("summary") or {}).get("task_count", 0),
            "pending_task_count": (tasks.get("summary") or {}).get("pending_task_count", 0),
        },
        "run_state_path": "state/run_state.json",
        "tasks_path": "state/tasks.jsonl",
        "research_assets": run_state.get("research_assets"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--run-until-complete", action="store_true")
    parser.add_argument("--max-steps", type=int, default=25)
    args = parser.parse_args()
    if not args.run_until_complete:
        result = {"component": "runner", "status": "invalid", "error": "choose --run-until-complete"}
    else:
        result = run_until_complete(args.task_dir, args.target, args.max_steps)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
