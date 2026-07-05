#!/usr/bin/env python3
"""Compact task-queue facade over runtime dispatcher rows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_jsonl, write_json, write_jsonl
    from .runtime_dispatcher import collect_pending as dispatcher_collect_pending
    from .runtime_dispatcher import collect_status as dispatcher_collect_status
    from .runtime_dispatcher import mark_spawned as dispatcher_mark_spawned
    from .runtime_dispatcher import record_agent_output as dispatcher_record_agent_output
    from .status_schema import status_envelope
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_jsonl, write_json, write_jsonl
    from runtime_dispatcher import collect_pending as dispatcher_collect_pending
    from runtime_dispatcher import collect_status as dispatcher_collect_status
    from runtime_dispatcher import mark_spawned as dispatcher_mark_spawned
    from runtime_dispatcher import record_agent_output as dispatcher_record_agent_output
    from status_schema import status_envelope


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


PHASE_BY_REQUEST_TYPE = {
    "topic_profile": "topic_profile",
    "discovery": "corpus",
    "topic_relevance": "corpus",
    "topic_relevance_second_audit": "corpus",
    "paper_understanding": "paper_understanding",
    "knowledge_tree": "knowledge_tree",
    "spine_planner": "knowledge_tree",
    "gate7_reviewer": "review",
    "gate7_repair": "review_repair",
    "gate7_targeted_rereview": "review_repair",
}


def _safe_task_id(value: object) -> str:
    text = str(value or "task").strip()
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text) or "task"


def _task_packet(task_dir: Path, row: dict) -> str:
    state = task_dir / "state"
    packets = state / "task_packets"
    packets.mkdir(exist_ok=True)
    request_type = str(row.get("request_type") or "unknown")
    phase = PHASE_BY_REQUEST_TYPE.get(request_type, "runtime")
    task_id = str(row.get("request_id") or "")
    packet = {
        "schema_version": 1,
        "task_id": task_id,
        "phase": phase,
        "request_type": request_type,
        "status": row.get("status"),
        "agent_type": row.get("agent_type") or request_type,
        "fork_context": bool(row.get("fork_context", False)),
        "batch_id": row.get("batch_id"),
        "source_file": row.get("source_file"),
        "source_request_id": row.get("source_request_id"),
        "phase_generation": row.get("phase_generation"),
        "expected_result_schema_version": row.get("expected_result_schema_version"),
        "record_command": row.get("record_command"),
        "message": row.get("message"),
        "payload": row.get("payload") or {},
        "updated_at": _utc_now(),
    }
    relative = Path("state") / "task_packets" / f"{_safe_task_id(task_id)}.json"
    write_json(task_dir / relative, packet)
    return str(relative)


def _expected_outputs(row: dict) -> list[str]:
    payload = row.get("payload") or {}
    outputs = payload.get("expected_changed_artifacts") or payload.get("expected_output_artifacts") or payload.get("outputs") or []
    if isinstance(outputs, str):
        return [outputs]
    return [str(item) for item in outputs if str(item).strip()]


def _task_from_queue_row(task_dir: Path, row: dict) -> dict:
    request_type = str(row.get("request_type") or "unknown")
    status = str(row.get("status") or "pending_spawn")
    packet = _task_packet(task_dir, row)
    return {
        "task_id": row.get("request_id"),
        "phase": PHASE_BY_REQUEST_TYPE.get(request_type, "runtime"),
        "status": "pending" if status == "pending_spawn" else status,
        "agent": row.get("agent_type") or request_type,
        "request_type": request_type,
        "packet": packet,
        "inputs": [item for item in [row.get("source_file"), packet] if item],
        "outputs": _expected_outputs(row),
        "validator": row.get("payload", {}).get("expected_acceptance_validators") or row.get("payload", {}).get("expected_validators") or [],
        "retry_of": row.get("previous_request_id"),
        "created_by": "task_queue",
        "failure_reason": row.get("error"),
        "batch_id": row.get("batch_id"),
        "phase_generation": row.get("phase_generation"),
        "source_request_id": row.get("source_request_id"),
    }


def sync_tasks(task_dir: Path) -> dict:
    status = dispatcher_collect_status(task_dir)
    rows = status.get("queue") or read_jsonl(task_dir / "state" / "runtime_dispatch_queue.jsonl")
    active_rows = [row for row in rows if not str(row.get("status") or "").startswith("stale")]
    tasks = [_task_from_queue_row(task_dir, row) for row in active_rows]
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


def _with_tasks(task_dir: Path, component_result: dict) -> dict:
    tasks = sync_tasks(task_dir)
    public_result = {key: value for key, value in component_result.items() if key not in {"pending_requests", "queue"}}
    return {
        **public_result,
        "component": "task_queue",
        "tasks_path": "state/tasks.jsonl",
        "tasks": tasks.get("tasks") or [],
        "task_summary": tasks.get("summary") or {},
        "dispatcher_component": component_result.get("component"),
    }


def collect_pending(task_dir: Path) -> dict:
    result = dispatcher_collect_pending(task_dir)
    return _with_tasks(task_dir, result)


def collect_status(task_dir: Path) -> dict:
    result = dispatcher_collect_status(task_dir)
    return _with_tasks(task_dir, result)


def mark_spawned(task_dir: Path, request_id: str, agent_id: str) -> dict:
    result = dispatcher_mark_spawned(task_dir, request_id, agent_id)
    return _with_tasks(task_dir, result)


def record_agent_output(task_dir: Path, request_id: str, output_file: Path) -> dict:
    result = dispatcher_record_agent_output(task_dir, request_id, output_file)
    return _with_tasks(task_dir, result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--collect-pending", action="store_true")
    parser.add_argument("--collect-status", action="store_true")
    parser.add_argument("--mark-spawned")
    parser.add_argument("--agent-id")
    parser.add_argument("--record-agent-output")
    parser.add_argument("--output-file", type=Path)
    args = parser.parse_args()
    if args.collect_pending:
        result = collect_pending(args.task_dir)
    elif args.collect_status:
        result = collect_status(args.task_dir)
    elif args.mark_spawned:
        result = mark_spawned(args.task_dir, args.mark_spawned, args.agent_id or "")
    elif args.record_agent_output:
        if not args.output_file:
            result = {"component": "task_queue", "status": "invalid", "error": "missing_output_file"}
        else:
            result = record_agent_output(args.task_dir, args.record_agent_output, args.output_file)
    else:
        result = sync_tasks(args.task_dir)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
