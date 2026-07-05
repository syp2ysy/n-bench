#!/usr/bin/env python3
"""Prepare and record discovery worker batches."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .status_schema import STATUS_SCHEMA_VERSION, status_envelope
    from .validate_coverage import validate_coverage
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from status_schema import STATUS_SCHEMA_VERSION, status_envelope
    from validate_coverage import validate_coverage


COMPONENT = "discovery_runtime_executor"
RESULT_SCHEMA_VERSION = 1
REQUIRED_RESULT_KEYS = ["batch_id", "status", "raw_candidates", "search_routes", "lqs_scores", "corpus_expansion", "validator_results", "remaining_blockers"]
VALID_RESULT_STATUSES = {"resolved", "partially_resolved", "blocked"}


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_hash(value) -> str:
    payload = json.dumps(value or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _target(task_dir: Path) -> str:
    progress = read_json(_state(task_dir) / "progress.json")
    target = str(progress.get("target") or "full")
    return target if target in {"short", "full", "csur"} else "full"


def _task_spec(task_dir: Path) -> str:
    path = _state(task_dir) / "task_spec.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _survey_type(task_dir: Path) -> str:
    path = _state(task_dir) / "survey_type_plan.yml"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _topic_profile(task_dir: Path) -> dict:
    return read_json(_state(task_dir) / "topic_profile.json")


def _summary(doc: dict) -> dict:
    batches = doc.get("batches") or []
    pending = [batch for batch in batches if batch.get("status") != "resolved"]
    return {
        "batch_count": len(batches),
        "active_batch_id": doc.get("active_batch_id"),
        "pending_batch_count": len(pending),
        "resolved_batch_count": len(batches) - len(pending),
    }


def _with_metadata(doc: dict) -> dict:
    doc = dict(doc or {})
    doc["schema_version"] = STATUS_SCHEMA_VERSION
    doc["summary"] = _summary(doc)
    return doc


def _refresh_batch_statuses(doc: dict) -> dict:
    active_batch_id = None
    for batch in doc.get("batches") or []:
        if batch.get("status") == "resolved":
            continue
        if active_batch_id is None:
            if batch.get("status") in {"blocked_by_upstream", "blocked", "partially_resolved", "", None}:
                batch["status"] = "pending_spawn"
            if batch.get("status") == "pending_spawn":
                active_batch_id = batch.get("batch_id")
        else:
            batch["status"] = "blocked_by_upstream"
    doc["active_batch_id"] = active_batch_id
    return doc


def _prompt(task_dir: Path, batch: dict) -> str:
    topic_profile = _topic_profile(task_dir)
    return (
        "You are a high-recall discovery worker for survey-autoresearch.\n"
        "Use real search sources and return structured discovery state. Do not invent papers or counts.\n"
        "Follow the topic_profile exactly: positive anchors define core relevance; negative anchors define drift risks; allowed background cannot become A/B core.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Batch id: {batch.get('batch_id')}\n"
        f"Task spec:\n{_task_spec(task_dir)}\n"
        f"Topic profile:\n{json.dumps(topic_profile, indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Survey type plan:\n{_survey_type(task_dir)}\n"
        "Return one JSON object with keys: batch_id, status, raw_candidates, search_routes, lqs_scores, corpus_expansion, validator_results, remaining_blockers."
    )


def _spawn_request(task_dir: Path, batch: dict) -> dict:
    return {
        "request_id": f"discovery-{batch.get('batch_id')}",
        "next_action": "spawn_discovery_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "required_result_keys": list(REQUIRED_RESULT_KEYS),
        "batch_id": batch.get("batch_id"),
        "attempt": int(batch.get("attempt") or 1),
        "previous_blockers": batch.get("last_blockers") or [],
        "target": _target(task_dir),
        "task_spec": _task_spec(task_dir),
        "topic_profile": _topic_profile(task_dir),
        "survey_type_plan": _survey_type(task_dir),
        "record_command": f"python3 scripts/discovery_runtime_executor.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>",
        "message": _prompt(task_dir, batch),
        "status": "pending_spawn",
    }


def _write_runtime_action(task_dir: Path, doc: dict) -> dict:
    doc = _with_metadata(doc)
    active = next((batch for batch in doc.get("batches") or [] if batch.get("batch_id") == doc.get("active_batch_id")), None)
    requests = [_spawn_request(task_dir, active)] if active else []
    next_action = "spawn_discovery_agents" if active else "rerun_phase_gate"
    result_status = "blocked_discovery_agent_spawn_required" if active else "discovery_batches_resolved"
    write_json(_state(task_dir) / "discovery_spawn_requests.json", {"next_action": next_action, "spawn_requests": requests})
    write_json(
        _state(task_dir) / "discovery_runtime_action.json",
        {
            **status_envelope(
                COMPONENT,
                "pending_discovery_runtime" if active else "discovery_batches_resolved",
                next_action=next_action,
                terminal=active is None,
                blocked=active is not None,
                blocked_by_phase="discovery" if active else None,
                active_batch_id=doc.get("active_batch_id"),
                summary={**(doc.get("summary") or {}), "spawn_request_count": len(requests)},
            ),
            "active_batch_id": doc.get("active_batch_id"),
        },
    )
    return {
        **status_envelope(
            COMPONENT,
            result_status,
            next_action=next_action,
            terminal=active is None,
            blocked=active is not None,
            blocked_by_phase="discovery" if active else None,
            active_batch_id=doc.get("active_batch_id"),
            summary={**(doc.get("summary") or {}), "spawn_request_count": len(requests)},
        ),
        "spawn_request_count": len(requests),
        "spawn_requests": requests,
    }


def prepare_discovery_batches(task_dir: Path) -> dict:
    state = _state(task_dir)
    plan_hash = _stable_hash({"task_spec": _task_spec(task_dir), "topic_profile": _topic_profile(task_dir), "survey_type_plan": _survey_type(task_dir), "target": _target(task_dir)})
    existing = read_json(state / "discovery_batches.json")
    if existing.get("plan_hash") == plan_hash and existing.get("batches"):
        doc = _refresh_batch_statuses(existing)
    else:
        doc = {
            "plan_hash": plan_hash,
            "batches": [{"batch_id": "D001", "status": "pending_spawn"}],
        }
        doc = _refresh_batch_statuses(doc)
    doc = _with_metadata(doc)
    write_json(state / "discovery_batches.json", doc)
    return _write_runtime_action(task_dir, doc)


def collect_discovery_status(task_dir: Path) -> dict:
    state = _state(task_dir)
    doc = _refresh_batch_statuses(read_json(state / "discovery_batches.json"))
    if not doc.get("batches"):
        return {
            **status_envelope(COMPONENT, "not_prepared", next_action="prepare_discovery_batches", terminal=False, blocked=True, blocked_by_phase="discovery", summary={"batch_count": 0}),
            "batches": [],
        }
    doc = _with_metadata(doc)
    write_json(state / "discovery_batches.json", doc)
    all_resolved = all(batch.get("status") == "resolved" for batch in doc.get("batches") or [])
    return {
        **status_envelope(
            COMPONENT,
            "resolved" if all_resolved else "pending_discovery_runtime",
            next_action="rerun_phase_gate" if all_resolved else "spawn_discovery_agents",
            terminal=all_resolved,
            blocked=not all_resolved,
            blocked_by_phase=None if all_resolved else "discovery",
            active_batch_id=doc.get("active_batch_id"),
            summary=doc.get("summary") or {},
        ),
        "batches": doc.get("batches") or [],
        "all_batches_resolved": all_resolved,
    }


def _passed_validators(result: dict) -> set[str]:
    validators = result.get("validator_results")
    if not isinstance(validators, list):
        return set()
    return {
        str(item.get("validator") or item.get("name") or "").strip()
        for item in validators
        if isinstance(item, dict)
        and str(item.get("status") or "").lower() == "passed"
        and str(item.get("validator") or item.get("name") or "").strip()
    }


def _validate_result(task_dir: Path, result: dict, batch: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result_not_object"]
    for key in REQUIRED_RESULT_KEYS:
        if key not in result:
            errors.append(f"missing_{key}")
    if str(result.get("batch_id") or "") != str(batch.get("batch_id") or ""):
        errors.append("batch_id_mismatch")
    if str(result.get("status") or "") not in VALID_RESULT_STATUSES:
        errors.append("invalid_status")
    if result.get("status") != "resolved":
        return sorted(set(errors))
    if "validate_discovery" not in _passed_validators(result):
        errors.append("missing_acceptance_validators")
    raw = result.get("raw_candidates")
    routes = result.get("search_routes")
    lqs = result.get("lqs_scores")
    corpus = result.get("corpus_expansion")
    if not isinstance(raw, list):
        errors.append("invalid_raw_candidates")
        raw = []
    if not isinstance(routes, list):
        errors.append("invalid_search_routes")
        routes = []
    if not isinstance(lqs, list):
        errors.append("invalid_lqs_scores")
        lqs = []
    if not isinstance(corpus, dict):
        errors.append("invalid_corpus_expansion")
        corpus = {}
    coverage = validate_coverage(raw, routes, lqs, corpus, [], [], _target(task_dir))
    if not coverage.get("discovery_sufficient"):
        errors.append("discovery_not_sufficient")
    return sorted(set(errors))


def record_discovery_result(task_dir: Path, result: dict, subagent_session_id: str) -> dict:
    state = _state(task_dir)
    doc = _refresh_batch_statuses(read_json(state / "discovery_batches.json"))
    batch_id = str(result.get("batch_id") or "")
    batch = next((item for item in doc.get("batches") or [] if str(item.get("batch_id") or "") == batch_id), None)
    if not batch:
        return {"status": "invalid", "error": "unknown_batch_id"}
    if batch_id != str(doc.get("active_batch_id") or ""):
        return {"status": "invalid", "error": "batch_blocked_by_upstream"}
    errors = _validate_result(task_dir, result, batch)
    if errors:
        return {"status": "invalid", "error": "invalid_discovery_result", "errors": errors}
    recorded_at = _utc_now()
    row = {**result, "fresh_context": True, "subagent_session_id": subagent_session_id, "recorded_at": recorded_at}
    write_jsonl(state / "discovery_results.jsonl", read_jsonl(state / "discovery_results.jsonl") + [row])
    if result.get("status") == "resolved":
        write_jsonl(state / "raw_candidates.jsonl", result.get("raw_candidates") or [])
        write_jsonl(state / "search_routes.jsonl", result.get("search_routes") or [])
        write_jsonl(state / "lqs_scores.jsonl", result.get("lqs_scores") or [])
        write_json(state / "corpus_expansion.json", result.get("corpus_expansion") or {})
        batch["status"] = "resolved"
        batch["resolved_at"] = recorded_at
        batch["subagent_session_id"] = subagent_session_id
    else:
        batch["status"] = "pending_spawn"
        batch["attempt"] = int(batch.get("attempt") or 1) + 1
        batch["last_blocked_at"] = recorded_at
        batch["last_blockers"] = result.get("remaining_blockers") or []
        batch["last_status"] = str(result.get("status") or "")
    doc = _with_metadata(_refresh_batch_statuses(doc))
    write_json(state / "discovery_batches.json", doc)
    _write_runtime_action(task_dir, doc)
    return {"status": "recorded", "batch_id": batch_id, "next_active_batch_id": doc.get("active_batch_id")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--collect-status", action="store_true")
    parser.add_argument("--record-result", type=Path)
    parser.add_argument("--subagent-session-id")
    args = parser.parse_args()
    if args.prepare:
        result = prepare_discovery_batches(args.task_dir)
    elif args.collect_status:
        result = collect_discovery_status(args.task_dir)
    elif args.record_result:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_discovery_result(args.task_dir, json.loads(args.record_result.read_text(encoding="utf-8")), args.subagent_session_id)
    else:
        result = {"status": "invalid", "error": "choose --prepare, --collect-status, or --record-result"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
