#!/usr/bin/env python3
"""Normalize worker spawn requests and route returned JSON to recorders."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .discovery_runtime_executor import record_discovery_result
    from .gate7_loop import record_review_report, record_targeted_rereview
    from .gate7_runtime_executor import record_runtime_repair_result
    from .knowledge_tree_builder import record_knowledge_tree_result
    from .paper_reader import record_result as record_paper_reader_result
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .spine_planner import record_spine_plan_result
    from .status_schema import status_envelope
    from .topic_profile import record_topic_profile_result
    from .topic_relevance_runtime_executor import record_topic_relevance_result, record_topic_relevance_second_audit_result
except ImportError:  # pragma: no cover
    from discovery_runtime_executor import record_discovery_result
    from gate7_loop import record_review_report, record_targeted_rereview
    from gate7_runtime_executor import record_runtime_repair_result
    from knowledge_tree_builder import record_knowledge_tree_result
    from paper_reader import record_result as record_paper_reader_result
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from spine_planner import record_spine_plan_result
    from status_schema import status_envelope
    from topic_profile import record_topic_profile_result
    from topic_relevance_runtime_executor import record_topic_relevance_result, record_topic_relevance_second_audit_result


COMPONENT = "runtime_dispatcher"
QUEUE_FILE = "runtime_dispatch_queue.jsonl"
SESSIONS_FILE = "runtime_agent_sessions.jsonl"
RESULTS_FILE = "runtime_agent_results.jsonl"
STATUS_FILE = "runtime_dispatch_status.json"
INTENT_FILE = "runtime_active_intent.json"


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_hash(value) -> str:
    payload = json.dumps(value or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_status(task_dir: Path, result: dict) -> dict:
    write_json(_state(task_dir) / STATUS_FILE, result)
    return result


def _active_intent(task_dir: Path) -> dict:
    intent = read_json(_state(task_dir) / INTENT_FILE)
    allowed = [str(item) for item in intent.get("allowed_request_types") or [] if str(item).strip()]
    generation = str(intent.get("phase_generation") or "")
    if not allowed or not generation:
        return {**intent, "valid": False, "allowed_request_types": [], "phase_generation": ""}
    return {**intent, "valid": True, "allowed_request_types": allowed, "phase_generation": generation}


def _record_command(task_dir: Path, request_type: str) -> str:
    if request_type == "topic_profile":
        return f"python3 scripts/topic_profile.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>"
    if request_type == "discovery":
        return f"python3 scripts/discovery_runtime_executor.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>"
    if request_type == "topic_relevance":
        return f"python3 scripts/topic_relevance_runtime_executor.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>"
    if request_type == "topic_relevance_second_audit":
        return f"python3 scripts/topic_relevance_runtime_executor.py --task-dir {task_dir.resolve()} --record-second-audit <result.json> --subagent-session-id <subagent-session-id>"
    if request_type == "knowledge_tree":
        return f"python3 scripts/knowledge_tree_builder.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>"
    if request_type == "spine_planner":
        return f"python3 scripts/spine_planner.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>"
    elif request_type == "paper_understanding":
        script = "paper_reader.py"
    elif request_type == "gate7_repair":
        script = "gate7_runtime_executor.py"
    elif request_type == "gate7_reviewer":
        return f"python3 scripts/gate7_loop.py --task-dir {task_dir.resolve()} --record-review <result.json> --subagent-session-id <subagent-session-id>"
    elif request_type == "gate7_targeted_rereview":
        return f"python3 scripts/gate7_loop.py --task-dir {task_dir.resolve()} --record-targeted-rereview <result.json> --subagent-session-id <subagent-session-id>"
    else:
        return ""
    return f"python3 scripts/{script} --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>"


def _request_type(source_file: str, next_action: str, request: dict) -> str:
    if source_file.endswith("topic_profile_spawn_requests.json"):
        return "topic_profile"
    if source_file.endswith("discovery_spawn_requests.json"):
        return "discovery"
    if source_file.endswith("topic_relevance_spawn_requests.json"):
        if next_action == "spawn_topic_relevance_second_audit_agents":
            return "topic_relevance_second_audit"
        return "topic_relevance"
    if source_file.endswith("paper_understanding_spawn_requests.json"):
        return "paper_understanding"
    if source_file.endswith("knowledge_tree_spawn_requests.json"):
        return "knowledge_tree"
    if source_file.endswith("spine_planner_spawn_requests.json"):
        return "spine_planner"
    if next_action == "spawn_repair_agents" or str(request.get("request_id") or "").startswith("repair-"):
        return "gate7_repair"
    if next_action == "spawn_reviewers":
        return "gate7_reviewer"
    if next_action == "spawn_targeted_rereviewers":
        return "gate7_targeted_rereview"
    return "unknown"


def _source_requests(task_dir: Path, intent: dict) -> list[dict]:
    state = _state(task_dir)
    allowed_types = set(intent.get("allowed_request_types") or [])
    phase_generation = str(intent.get("phase_generation") or "")
    sources = [
        ("state/topic_profile_spawn_requests.json", read_json(state / "topic_profile_spawn_requests.json")),
        ("state/discovery_spawn_requests.json", read_json(state / "discovery_spawn_requests.json")),
        ("state/topic_relevance_spawn_requests.json", read_json(state / "topic_relevance_spawn_requests.json")),
        ("state/paper_understanding_spawn_requests.json", read_json(state / "paper_understanding_spawn_requests.json")),
        ("state/knowledge_tree_spawn_requests.json", read_json(state / "knowledge_tree_spawn_requests.json")),
        ("state/spine_planner_spawn_requests.json", read_json(state / "spine_planner_spawn_requests.json")),
        ("state/gate7_spawn_requests.json", read_json(state / "gate7_spawn_requests.json")),
    ]
    rows: list[dict] = []
    for source_file, payload in sources:
        next_action = str(payload.get("next_action") or "")
        for request in payload.get("spawn_requests") or []:
            if not isinstance(request, dict):
                continue
            request_type = _request_type(source_file, next_action, request)
            if request_type not in allowed_types:
                continue
            source_request_id = str(request.get("request_id") or f"{request_type}-{len(rows) + 1:03d}")
            fingerprint = _stable_hash({"source_file": source_file, "next_action": next_action, "phase_generation": phase_generation, "request": request})
            request_id = f"{request_type}-{source_request_id}-{fingerprint[:12]}"
            row = {
                "request_id": request_id,
                "request_key": f"{request_type}:{source_request_id}:{fingerprint[:12]}",
                "source_request_id": source_request_id,
                "request_type": request_type,
                "phase_generation": phase_generation,
                "source_file": source_file,
                "source_fingerprint": fingerprint,
                "record_command": request.get("record_command") or _record_command(task_dir, request_type),
                "agent_type": request.get("agent_type") or "worker",
                "fork_context": bool(request.get("fork_context", False)),
                "expected_result_schema_version": request.get("result_schema_version"),
                "status": "pending_spawn",
                "spawned_agent_id": "",
                "batch_id": request.get("batch_id"),
                "review_round_id": request.get("review_round_id"),
                "reviewer_id": request.get("reviewer_id"),
                "weakness_id": request.get("weakness_id"),
                "payload": request,
                "message": request.get("message"),
            }
            rows.append(row)
    return rows


def _next_retry_id(existing: dict[str, dict], base_request_id: str) -> str:
    attempt = 2
    while f"{base_request_id}-retry{attempt:02d}" in existing:
        attempt += 1
    return f"{base_request_id}-retry{attempt:02d}"


def _live_row_for_source(existing: dict[str, dict], row: dict) -> dict | None:
    for current in existing.values():
        if current.get("source_fingerprint") != row.get("source_fingerprint"):
            continue
        if current.get("request_type") != row.get("request_type"):
            continue
        if current.get("phase_generation") != row.get("phase_generation"):
            continue
        status = str(current.get("status") or "")
        if status.startswith("stale"):
            continue
        if status in {"pending_spawn", "spawned", "invalid_result", "rebalance_required", "result_recorded"}:
            return current
    return None


def _merge_source_row(current: dict, row: dict) -> None:
    preserved = {
        "status": current.get("status") or row["status"],
        "spawned_agent_id": current.get("spawned_agent_id", ""),
        "spawned_at": current.get("spawned_at"),
        "result_hash": current.get("result_hash"),
        "recorded_at": current.get("recorded_at"),
        "error": current.get("error"),
        "reactivated_at": current.get("reactivated_at"),
        "previous_request_id": current.get("previous_request_id"),
        "attempt": current.get("attempt"),
    }
    current.update(row)
    current.update({key: value for key, value in preserved.items() if value not in [None, ""]})


def _sync_queue(task_dir: Path) -> list[dict]:
    state = _state(task_dir)
    intent = _active_intent(task_dir)
    existing = {str(row.get("request_id") or ""): row for row in read_jsonl(state / QUEUE_FILE) if row.get("request_id")}
    ordered_ids = [str(row.get("request_id")) for row in read_jsonl(state / QUEUE_FILE) if row.get("request_id")]
    if intent.get("valid"):
        for row in _source_requests(task_dir, intent):
            live = _live_row_for_source(existing, row)
            if live:
                _merge_source_row(live, row)
                continue
            current = existing.get(row["request_id"])
            if current:
                status = str(current.get("status") or "")
                if status == "stale_superseded" and not current.get("spawned_agent_id"):
                    current.update(row)
                    current["status"] = "pending_spawn"
                    current["spawned_agent_id"] = ""
                    current.pop("spawned_at", None)
                    current.pop("result_hash", None)
                    current.pop("recorded_at", None)
                    current.pop("error", None)
                    current["reactivated_at"] = _utc_now()
                elif status.startswith("stale") and current.get("spawned_agent_id"):
                    retry_id = _next_retry_id(existing, row["request_id"])
                    retry = dict(row)
                    retry["request_id"] = retry_id
                    retry["previous_request_id"] = row["request_id"]
                    retry["attempt"] = int(current.get("attempt") or 1) + 1
                    existing[retry_id] = retry
                    ordered_ids.append(retry_id)
                else:
                    _merge_source_row(current, row)
            else:
                existing[row["request_id"]] = row
                ordered_ids.append(row["request_id"])
    allowed = set(intent.get("allowed_request_types") or [])
    generation = str(intent.get("phase_generation") or "")
    for row in existing.values():
        if row.get("status") == "pending_spawn" and (
            not intent.get("valid")
            or row.get("request_type") not in allowed
            or str(row.get("phase_generation") or "") != generation
        ):
            row["status"] = "stale_superseded"
            row["error"] = "runtime_intent_changed"
        elif row.get("status") == "spawned" and (
            not intent.get("valid")
            or row.get("request_type") not in allowed
            or str(row.get("phase_generation") or "") != generation
        ):
            row["status"] = "stale_spawned"
            row["error"] = "runtime_intent_changed_after_spawn"
    rows = [existing[request_id] for request_id in ordered_ids if request_id in existing]
    write_jsonl(state / QUEUE_FILE, rows)
    return rows


def _summary(rows: list[dict]) -> dict:
    return {
        "queue_count": len(rows),
        "pending_spawn_count": len([row for row in rows if row.get("status") == "pending_spawn"]),
        "spawned_count": len([row for row in rows if row.get("status") == "spawned"]),
        "result_recorded_count": len([row for row in rows if row.get("status") == "result_recorded"]),
        "invalid_result_count": len([row for row in rows if row.get("status") == "invalid_result"]),
        "rebalance_required_count": len([row for row in rows if row.get("status") == "rebalance_required"]),
        "stale_count": len([row for row in rows if str(row.get("status") or "").startswith("stale")]),
    }


def collect_pending(task_dir: Path) -> dict:
    rows = _sync_queue(task_dir)
    intent = _active_intent(task_dir)
    if not intent.get("valid"):
        result = {
            **status_envelope(
                COMPONENT,
                "blocked_runtime_intent_required",
                next_action="run_survey_driver",
                terminal=False,
                blocked=True,
                summary=_summary(rows),
            ),
            "pending_requests": [],
        }
        return _write_status(task_dir, result)
    pending = [row for row in rows if row.get("status") == "pending_spawn"]
    result = {
        **status_envelope(
            COMPONENT,
            "pending_spawn" if pending else "idle",
            next_action="spawn_workers" if pending else "rerun_survey_driver",
            terminal=False,
            blocked=bool(pending),
            summary=_summary(rows),
        ),
        "pending_requests": pending,
    }
    return _write_status(task_dir, result)


def collect_status(task_dir: Path) -> dict:
    rows = _sync_queue(task_dir)
    intent = _active_intent(task_dir)
    summary = _summary(rows)
    if not intent.get("valid"):
        status = "blocked_runtime_intent_required"
        next_action = "run_survey_driver"
        blocked = True
    elif summary["rebalance_required_count"]:
        status = "rebalance_required"
        next_action = "rerun_survey_driver"
        blocked = True
    elif summary["pending_spawn_count"]:
        status = "pending_spawn"
        next_action = "spawn_workers"
        blocked = True
    elif summary["spawned_count"]:
        status = "waiting_for_worker_results"
        next_action = "record_agent_output"
        blocked = True
    elif summary["invalid_result_count"]:
        status = "invalid_result"
        next_action = "inspect_worker_output"
        blocked = True
    else:
        status = "idle"
        next_action = "rerun_survey_driver"
        blocked = False
    result = {
        **status_envelope(COMPONENT, status, next_action=next_action, terminal=False, blocked=blocked, summary=summary),
        "queue": rows,
    }
    return _write_status(task_dir, result)


def mark_spawned(task_dir: Path, request_id: str, agent_id: str) -> dict:
    rows = _sync_queue(task_dir)
    intent = _active_intent(task_dir)
    row = next((item for item in rows if item.get("request_id") == request_id), None)
    if not row:
        return {"status": "invalid", "error": "unknown_request_id"}
    if (
        not intent.get("valid")
        or row.get("request_type") not in set(intent.get("allowed_request_types") or [])
        or str(row.get("phase_generation") or "") != str(intent.get("phase_generation") or "")
        or str(row.get("status") or "").startswith("stale")
    ):
        row["status"] = row.get("status") if str(row.get("status") or "").startswith("stale") else "stale_superseded"
        row["error"] = "runtime_intent_changed"
        write_jsonl(_state(task_dir) / QUEUE_FILE, rows)
        return {"status": "stale_request_rejected", "error": "runtime_intent_changed", "request_id": request_id}
    if row.get("status") in {"spawned", "result_recorded", "rebalance_required"}:
        return {"status": "invalid", "error": "duplicate_spawn", "request_id": request_id}
    if row.get("status") != "pending_spawn":
        return {"status": "invalid", "error": "request_not_pending", "request_id": request_id, "current_status": row.get("status")}
    now = _utc_now()
    row["status"] = "spawned"
    row["spawned_agent_id"] = agent_id
    row["spawned_at"] = now
    write_jsonl(_state(task_dir) / QUEUE_FILE, rows)
    session = {
        "ts": now,
        "request_id": request_id,
        "request_type": row.get("request_type"),
        "source_file": row.get("source_file"),
        "spawned_agent_id": agent_id,
        "subagent_session_id": agent_id,
        "status": "spawned",
    }
    write_jsonl(_state(task_dir) / SESSIONS_FILE, read_jsonl(_state(task_dir) / SESSIONS_FILE) + [session])
    collect_status(task_dir)
    return {"status": "spawned", "request_id": request_id, "spawned_agent_id": agent_id}


def _parse_agent_output(output_file: Path) -> tuple[dict | None, str | None]:
    text = output_file.read_text(encoding="utf-8")
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        return parsed, None if isinstance(parsed, dict) else "json_not_object"
    except json.JSONDecodeError:
        pass
    match = re.search(r"```json\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if match:
        try:
            parsed = json.loads(match.group(1))
            return parsed, None if isinstance(parsed, dict) else "json_not_object"
        except json.JSONDecodeError:
            return None, "invalid_fenced_json"
    return None, "non_json_worker_output"


def _unavailable_paper_ids(result: dict) -> list[str]:
    ids = []
    for item in result.get("unavailable_or_downgrade_candidates") or []:
        if isinstance(item, dict) and str(item.get("paper_id") or "").strip():
            ids.append(str(item["paper_id"]).strip())
        elif str(item or "").strip():
            ids.append(str(item).strip())
    return sorted(set(ids))


def _route_result(task_dir: Path, row: dict, result: dict, subagent_session_id: str) -> dict:
    request_type = row.get("request_type")
    if request_type == "topic_profile":
        return record_topic_profile_result(task_dir, result, subagent_session_id)
    if request_type == "discovery":
        return record_discovery_result(task_dir, result, subagent_session_id)
    if request_type == "topic_relevance":
        return record_topic_relevance_result(task_dir, result, subagent_session_id)
    if request_type == "topic_relevance_second_audit":
        return record_topic_relevance_second_audit_result(task_dir, result, subagent_session_id)
    if request_type == "paper_understanding":
        return record_paper_reader_result(task_dir, result, subagent_session_id)
    if request_type == "knowledge_tree":
        return record_knowledge_tree_result(task_dir, result, subagent_session_id)
    if request_type == "spine_planner":
        return record_spine_plan_result(task_dir, result, subagent_session_id)
    if request_type == "gate7_repair":
        return record_runtime_repair_result(task_dir, result, subagent_session_id)
    if request_type == "gate7_reviewer":
        return record_review_report(task_dir, result, subagent_session_id)
    if request_type == "gate7_targeted_rereview":
        return record_targeted_rereview(task_dir, result, subagent_session_id)
    return {"status": "invalid", "error": "unknown_request_type", "request_type": request_type}


def _append_result_row(task_dir: Path, row: dict) -> None:
    write_jsonl(_state(task_dir) / RESULTS_FILE, read_jsonl(_state(task_dir) / RESULTS_FILE) + [row])


def record_agent_output(task_dir: Path, request_id: str, output_file: Path) -> dict:
    rows = _sync_queue(task_dir)
    intent = _active_intent(task_dir)
    row = next((item for item in rows if item.get("request_id") == request_id), None)
    if not row:
        return {"status": "invalid", "error": "unknown_request_id"}
    if (
        not intent.get("valid")
        or row.get("request_type") not in set(intent.get("allowed_request_types") or [])
        or str(row.get("phase_generation") or "") != str(intent.get("phase_generation") or "")
        or str(row.get("status") or "").startswith("stale")
    ):
        row["status"] = "stale_result_rejected"
        row["error"] = "runtime_intent_changed"
        write_jsonl(_state(task_dir) / QUEUE_FILE, rows)
        _append_result_row(
            task_dir,
            {
                "ts": _utc_now(),
                "request_id": request_id,
                "request_type": row.get("request_type"),
                "status": "stale_request_rejected",
                "error": "runtime_intent_changed",
                "output_file": str(output_file),
            },
        )
        collect_status(task_dir)
        return {"status": "stale_request_rejected", "error": "runtime_intent_changed", "request_id": request_id}
    if row.get("status") in {"result_recorded", "rebalance_required"}:
        return {"status": "invalid", "error": "result_already_recorded", "request_id": request_id}
    parsed, parse_error = _parse_agent_output(output_file)
    now = _utc_now()
    if parse_error or parsed is None:
        row["status"] = "invalid_result"
        row["error"] = parse_error
        write_jsonl(_state(task_dir) / QUEUE_FILE, rows)
        result_row = {
            "ts": now,
            "request_id": request_id,
            "request_type": row.get("request_type"),
            "status": "invalid_result",
            "error": parse_error,
            "output_file": str(output_file),
        }
        _append_result_row(task_dir, result_row)
        collect_status(task_dir)
        return {"status": "invalid_result", "error": parse_error, "request_id": request_id}

    result_hash = _stable_hash(parsed)
    subagent_session_id = str(row.get("spawned_agent_id") or parsed.get("subagent_session_id") or "")
    record_result = _route_result(task_dir, row, parsed, subagent_session_id)
    unavailable_ids = _unavailable_paper_ids(parsed) if row.get("request_type") == "paper_understanding" else []
    if record_result.get("status") == "invalid":
        final_status = "invalid_result"
        row["error"] = record_result.get("error")
    elif unavailable_ids and str(parsed.get("status") or "") == "blocked":
        final_status = "rebalance_required"
    else:
        final_status = "result_recorded"
    row["status"] = final_status
    row["result_hash"] = result_hash
    row["recorded_at"] = now
    write_jsonl(_state(task_dir) / QUEUE_FILE, rows)
    result_row = {
        "ts": now,
        "request_id": request_id,
        "request_type": row.get("request_type"),
        "status": final_status,
        "result_hash": result_hash,
        "output_file": str(output_file),
        "record_result": record_result,
        "unavailable_paper_ids": unavailable_ids,
    }
    _append_result_row(task_dir, result_row)
    collect_status(task_dir)
    return {
        "status": final_status,
        "request_id": request_id,
        "result_hash": result_hash,
        "record_result": record_result,
        "unavailable_paper_ids": unavailable_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
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
        if not args.agent_id:
            result = {"status": "invalid", "error": "missing_agent_id"}
        else:
            result = mark_spawned(args.task_dir, args.mark_spawned, args.agent_id)
    elif args.record_agent_output:
        if not args.output_file:
            result = {"status": "invalid", "error": "missing_output_file"}
        else:
            result = record_agent_output(args.task_dir, args.record_agent_output, args.output_file)
    else:
        result = {"status": "invalid", "error": "choose a dispatcher action"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
