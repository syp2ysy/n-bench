#!/usr/bin/env python3
"""Compact task-queue facade over runtime dispatcher rows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_jsonl, write_jsonl
    from .runtime_dispatcher import collect_status
    from .status_schema import status_envelope
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_jsonl, write_jsonl
    from runtime_dispatcher import collect_status
    from status_schema import status_envelope


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


PHASE_BY_REQUEST_TYPE = {
    "topic_profile": "topic_profile",
    "discovery": "corpus",
    "topic_relevance": "corpus",
    "topic_relevance_second_audit": "corpus",
    "paper_understanding": "paper_understanding",
    "gate7_reviewer": "review",
    "gate7_repair": "review_repair",
    "gate7_targeted_rereview": "review_repair",
}


def _task_from_queue_row(row: dict) -> dict:
    request_type = str(row.get("request_type") or "unknown")
    status = str(row.get("status") or "pending_spawn")
    return {
        "task_id": row.get("request_id"),
        "phase": PHASE_BY_REQUEST_TYPE.get(request_type, "runtime"),
        "status": "pending" if status == "pending_spawn" else status,
        "agent": row.get("agent_type") or request_type,
        "request_type": request_type,
        "inputs": [row.get("source_file")] if row.get("source_file") else [],
        "outputs": [row.get("record_command")] if row.get("record_command") else [],
        "validator": row.get("payload", {}).get("expected_acceptance_validators") or row.get("payload", {}).get("expected_validators") or [],
        "retry_of": row.get("previous_request_id"),
        "created_by": "task_queue",
        "failure_reason": row.get("error"),
        "batch_id": row.get("batch_id"),
        "phase_generation": row.get("phase_generation"),
        "source_request_id": row.get("source_request_id"),
    }


def sync_tasks(task_dir: Path) -> dict:
    status = collect_status(task_dir)
    rows = status.get("queue") or read_jsonl(task_dir / "state" / "runtime_dispatch_queue.jsonl")
    active_rows = [row for row in rows if not str(row.get("status") or "").startswith("stale")]
    tasks = [_task_from_queue_row(row) for row in active_rows]
    write_jsonl(task_dir / "state" / "tasks.jsonl", tasks)
    return {
        **status_envelope(
            "task_queue",
            "synced",
            next_action=status.get("next_action"),
            terminal=False,
            blocked=bool(status.get("blocked")),
            blocked_by_phase=status.get("blocked_by_phase"),
            summary={
                "task_count": len(tasks),
                "pending_task_count": len([task for task in tasks if task.get("status") == "pending"]),
                "stale_runtime_rows_hidden": len(rows) - len(active_rows),
                "source_component": status.get("component"),
                "synced_at": _utc_now(),
            },
        ),
        "tasks": tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--sync", action="store_true")
    args = parser.parse_args()
    result = sync_tasks(args.task_dir)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
