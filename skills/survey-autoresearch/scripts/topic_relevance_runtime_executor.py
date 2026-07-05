#!/usr/bin/env python3
"""Prepare and record topic-relevance audit worker batches."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .status_schema import STATUS_SCHEMA_VERSION, status_envelope
    from .validate_topic_relevance import secondary_audit_record_errors, second_audit_trigger_reasons, validate_topic_relevance
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from status_schema import STATUS_SCHEMA_VERSION, status_envelope
    from validate_topic_relevance import secondary_audit_record_errors, second_audit_trigger_reasons, validate_topic_relevance


COMPONENT = "topic_relevance_runtime_executor"
RESULT_SCHEMA_VERSION = 1
DEFAULT_BATCH_SIZE = 25
DEFAULT_SECOND_AUDIT_BATCH_SIZE = 10
RETRY_SPLIT_FAILURE_THRESHOLD = 2
RETRY_SPLIT_BATCH_SIZE = 8
REQUIRED_RESULT_KEYS = ["batch_id", "status", "audit_records", "validator_results", "remaining_blockers"]
SECOND_AUDIT_RESULT_KEYS = ["batch_id", "status", "paper_ids", "secondary_audit_records", "validator_results", "remaining_blockers"]
VALID_RESULT_STATUSES = {"resolved", "partially_resolved", "blocked"}
PRIMARY_VALIDATOR_ALIASES = {"topic_relevance_worker_output_schema_v1": "validate_topic_relevance"}
SECONDARY_VALIDATOR_ALIASES = {"topic_relevance_second_audit_worker_output_schema_v1": "validate_topic_relevance_second_audit"}


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_hash(value) -> str:
    payload = json.dumps(value or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _paper_id(row: dict) -> str:
    for key in ["paper_id", "arxiv_id", "doi", "url", "candidate_id", "title"]:
        value = str((row or {}).get(key) or "").strip()
        if value:
            return value
    return ""


def _read_survey_type(task_dir: Path) -> str:
    path = _state(task_dir) / "survey_type_plan.yml"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _candidate_records(task_dir: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    papers = {_paper_id(row): row for row in read_jsonl(_state(task_dir) / "papers.jsonl") if _paper_id(row)}
    for row in read_jsonl(_state(task_dir) / "raw_candidates.jsonl"):
        pid = _paper_id(row)
        if not pid:
            continue
        records[pid] = {**row, **papers.get(pid, {})}
        records[pid].setdefault("paper_id", pid)
        records[pid].setdefault("candidate_id", row.get("candidate_id"))
    return records


def _citation_depths(task_dir: Path) -> dict[str, str]:
    depths = {}
    for row in read_jsonl(_state(task_dir) / "citation_plan.jsonl"):
        pid = _paper_id(row)
        if pid:
            depths[pid] = str(row.get("depth") or row.get("level") or "unassigned").upper()
    return depths


def _primary_audits(task_dir: Path) -> dict[str, dict]:
    return {_paper_id(row): row for row in read_jsonl(_state(task_dir) / "topic_relevance_audit.jsonl") if _paper_id(row)}


def _batch_prompt(task_dir: Path, batch: dict) -> str:
    return (
        "You are a topic-relevance audit worker for survey-autoresearch.\n"
        "Judge topic fit from the provided real title, abstract_snippet, query, and source metadata. "
        "Do not use broad field importance as evidence of core relevance.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Batch id: {batch.get('batch_id')}\n"
        f"Paper ids: {', '.join(batch.get('paper_ids') or [])}\n"
        "Return one strict JSON object with keys: batch_id, status, audit_records, validator_results, remaining_blockers. "
        "Use status=resolved only when every listed paper_id has exactly one valid audit record; otherwise use blocked or partially_resolved. "
        "Each audit record must include paper_id, candidate_id or source_candidate_id, evidence_used, positive_topic_signals, "
        "negative_drift_signals, relevance_grade, allowed_depth, allowed_role, family_label_supported, corrected_family, and rationale. "
        "Allowed relevance_grade values: core, direct_related_survey, adjacent_background, generic_background, out_of_scope. "
        "Allowed allowed_depth values only: A, B, C, exclude. Use A/B only for topic-core papers that can support full or medium-depth reading; "
        "use C for background/adjacent records; use exclude for out_of_scope. "
        "Allowed allowed_role values only: core, related_survey, background, exclude. "
        "For direct_related_survey, allowed_role must be related_survey. For out_of_scope, allowed_depth must be exclude and allowed_role must be exclude. "
        "evidence_used must be a list of objects like {\"field\":\"title|abstract_snippet|query|source_metadata\", \"text\":\"...\"}, not a dictionary. "
        "validator_results must include {\"validator\":\"validate_topic_relevance\", \"status\":\"passed\"} only if the batch is schema-valid."
    )


def _second_audit_prompt(task_dir: Path, batch: dict) -> str:
    return (
        "You are an independent second-audit worker for survey-autoresearch topic relevance.\n"
        "Review only the listed high-risk A/B papers. Use the real title, abstract_snippet, query, source metadata, and primary audit summary. "
        "Do not accept core A/B status by reputation or broad field relevance.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Batch id: {batch.get('batch_id')}\n"
        f"Paper ids: {', '.join(batch.get('paper_ids') or [])}\n"
        "Return one JSON object with keys: batch_id, status, paper_ids, secondary_audit_records, validator_results, remaining_blockers. "
        "Each secondary_audit_record must include paper_id, primary_audit_session_id, subagent_session_id, trigger_reasons, evidence_used, "
        "decision, allowed_depth, allowed_role, and rationale. Allowed decision values: confirm_core, downgrade_to_C, exclude, direct_related_survey."
    )


def _spawn_request(task_dir: Path, batch: dict, records: dict[str, dict]) -> dict:
    ids = [str(pid) for pid in batch.get("paper_ids") or []]
    return {
        "request_id": f"topic-relevance-{batch.get('batch_id')}",
        "next_action": "spawn_topic_relevance_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "required_result_keys": list(REQUIRED_RESULT_KEYS),
        "batch_id": batch.get("batch_id"),
        "paper_ids": ids,
        "expected_paper_ids": ids,
        "candidate_records": [records[pid] for pid in ids if pid in records],
        "record_command": f"python3 scripts/topic_relevance_runtime_executor.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>",
        "message": _batch_prompt(task_dir, batch),
        "status": "pending_spawn",
    }


def _second_audit_spawn_request(task_dir: Path, batch: dict, records: dict[str, dict], primary_audits: dict[str, dict], depths: dict[str, str]) -> dict:
    ids = [str(pid) for pid in batch.get("paper_ids") or []]
    trigger_reasons = {
        pid: second_audit_trigger_reasons(primary_audits.get(pid, {}), depths.get(pid, "C"))
        for pid in ids
    }
    primary_session_by_paper = {
        pid: str((primary_audits.get(pid) or {}).get("subagent_session_id") or (primary_audits.get(pid) or {}).get("auditor_id") or "")
        for pid in ids
    }
    return {
        "request_id": f"topic-second-audit-{batch.get('batch_id')}",
        "next_action": "spawn_topic_relevance_second_audit_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "required_result_keys": list(SECOND_AUDIT_RESULT_KEYS),
        "batch_id": batch.get("batch_id"),
        "paper_ids": ids,
        "expected_paper_ids": ids,
        "candidate_records": [records[pid] for pid in ids if pid in records],
        "primary_audit_records": [primary_audits[pid] for pid in ids if pid in primary_audits],
        "trigger_reasons_by_paper": trigger_reasons,
        "primary_audit_session_by_paper": primary_session_by_paper,
        "record_command": f"python3 scripts/topic_relevance_runtime_executor.py --task-dir {task_dir.resolve()} --record-second-audit <result.json> --subagent-session-id <subagent-session-id>",
        "message": _second_audit_prompt(task_dir, batch),
        "status": "pending_spawn",
    }


def _refresh_batch_statuses(doc: dict) -> dict:
    active_batch_id = None
    for batch in doc.get("batches") or []:
        if batch.get("status") == "resolved":
            continue
        if active_batch_id is None:
            if batch.get("status") in {"blocked_by_upstream", "", None}:
                batch["status"] = "pending_spawn"
            if batch.get("status") == "pending_spawn":
                active_batch_id = batch.get("batch_id")
        else:
            batch["status"] = "blocked_by_upstream"
    doc["active_batch_id"] = active_batch_id
    return doc


def _summary(doc: dict) -> dict:
    batches = doc.get("batches") or []
    pending = [batch for batch in batches if batch.get("status") != "resolved"]
    active = next((batch for batch in batches if batch.get("batch_id") == doc.get("active_batch_id")), None)
    return {
        "batch_count": len(batches),
        "active_batch_id": doc.get("active_batch_id"),
        "active_paper_ids": active.get("paper_ids") if active else [],
        "pending_batch_count": len(pending),
        "resolved_batch_count": len(batches) - len(pending),
        "paper_count": int(doc.get("paper_count") or 0),
        "batch_size": int(doc.get("batch_size") or DEFAULT_BATCH_SIZE),
    }


def _with_metadata(doc: dict) -> dict:
    doc = dict(doc or {})
    doc["schema_version"] = STATUS_SCHEMA_VERSION
    doc["summary"] = _summary(doc)
    return doc


def _make_batches(paper_ids: list[str], batch_size: int) -> list[dict]:
    batches = []
    for idx, start in enumerate(range(0, len(paper_ids), batch_size), start=1):
        ids = paper_ids[start:start + batch_size]
        batches.append(
            {
                "batch_id": f"TR{idx:03d}",
                "status": "pending_spawn" if idx == 1 else "blocked_by_upstream",
                "paper_ids": ids,
                "paper_count": len(ids),
            }
        )
    return batches


def _topic_batch_worker_failure_count(task_dir: Path, batch_id: str) -> int:
    failures = 0
    for row in read_jsonl(_state(task_dir) / "runtime_dispatch_queue.jsonl"):
        if row.get("request_type") != "topic_relevance":
            continue
        if str(row.get("batch_id") or "") != str(batch_id):
            continue
        status = str(row.get("status") or "")
        error = str(row.get("error") or "")
        if status == "stale_spawned" and error:
            failures += 1
    return failures


def _split_active_batch_after_worker_failures(task_dir: Path, doc: dict) -> dict:
    active_id = str(doc.get("active_batch_id") or "")
    if not active_id:
        return doc
    batches = list(doc.get("batches") or [])
    active_index = next((idx for idx, batch in enumerate(batches) if str(batch.get("batch_id") or "") == active_id), None)
    if active_index is None:
        return doc
    active = batches[active_index]
    paper_ids = [str(pid) for pid in active.get("paper_ids") or [] if str(pid)]
    if active.get("split_from") or len(paper_ids) <= RETRY_SPLIT_BATCH_SIZE:
        return doc
    failure_count = _topic_batch_worker_failure_count(task_dir, active_id)
    if failure_count < RETRY_SPLIT_FAILURE_THRESHOLD:
        return doc
    split_at = _utc_now()
    split_batches = []
    for idx, start in enumerate(range(0, len(paper_ids), RETRY_SPLIT_BATCH_SIZE), start=1):
        ids = paper_ids[start:start + RETRY_SPLIT_BATCH_SIZE]
        split_batches.append(
            {
                "batch_id": f"{active_id}S{idx:02d}",
                "status": "pending_spawn" if idx == 1 else "blocked_by_upstream",
                "paper_ids": ids,
                "paper_count": len(ids),
                "split_from": active_id,
                "split_at": split_at,
                "split_reason": "repeated_topic_relevance_worker_failures",
                "split_failure_count": failure_count,
            }
        )
    doc["batches"] = batches[:active_index] + split_batches + batches[active_index + 1:]
    doc["split_events"] = list(doc.get("split_events") or []) + [
        {
            "ts": split_at,
            "batch_id": active_id,
            "failure_count": failure_count,
            "split_batch_ids": [batch["batch_id"] for batch in split_batches],
            "split_batch_size": RETRY_SPLIT_BATCH_SIZE,
        }
    ]
    doc["active_batch_id"] = split_batches[0]["batch_id"] if split_batches else None
    return doc


def _make_second_audit_batches(paper_ids: list[str], batch_size: int) -> list[dict]:
    batches = []
    for idx, start in enumerate(range(0, len(paper_ids), batch_size), start=1):
        ids = paper_ids[start:start + batch_size]
        batches.append(
            {
                "batch_id": f"TS{idx:03d}",
                "status": "pending_spawn" if idx == 1 else "blocked_by_upstream",
                "paper_ids": ids,
                "paper_count": len(ids),
            }
        )
    return batches


def _write_runtime_action(task_dir: Path, doc: dict) -> dict:
    doc = _with_metadata(doc)
    records = _candidate_records(task_dir)
    active = next((batch for batch in doc.get("batches") or [] if batch.get("batch_id") == doc.get("active_batch_id")), None)
    requests = [_spawn_request(task_dir, active, records)] if active else []
    next_action = "spawn_topic_relevance_agents" if active else "rerun_phase_gate"
    result_status = "blocked_topic_relevance_agent_spawn_required" if active else "topic_relevance_batches_resolved"
    write_json(_state(task_dir) / "topic_relevance_spawn_requests.json", {"next_action": next_action, "spawn_requests": requests})
    write_json(
        _state(task_dir) / "topic_relevance_runtime_action.json",
        {
            **status_envelope(
                COMPONENT,
                "pending_topic_relevance_runtime" if active else "topic_relevance_batches_resolved",
                next_action=next_action,
                terminal=active is None,
                blocked=active is not None,
                blocked_by_phase="source_verification" if active else None,
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
            blocked_by_phase="source_verification" if active else None,
            active_batch_id=doc.get("active_batch_id"),
            summary={**(doc.get("summary") or {}), "spawn_request_count": len(requests)},
        ),
        "spawn_request_count": len(requests),
        "spawn_requests": requests,
    }


def _write_second_audit_runtime_action(task_dir: Path, doc: dict) -> dict:
    doc = _with_metadata(doc)
    records = _candidate_records(task_dir)
    primary = _primary_audits(task_dir)
    depths = _citation_depths(task_dir)
    active = next((batch for batch in doc.get("batches") or [] if batch.get("batch_id") == doc.get("active_batch_id")), None)
    requests = [_second_audit_spawn_request(task_dir, active, records, primary, depths)] if active else []
    next_action = "spawn_topic_relevance_second_audit_agents" if active else "rerun_phase_gate"
    result_status = "blocked_topic_relevance_second_audit_agent_spawn_required" if active else "topic_relevance_second_audit_batches_resolved"
    write_json(_state(task_dir) / "topic_relevance_spawn_requests.json", {"next_action": next_action, "spawn_requests": requests})
    write_json(
        _state(task_dir) / "topic_relevance_runtime_action.json",
        {
            **status_envelope(
                COMPONENT,
                "pending_topic_relevance_second_audit_runtime" if active else "topic_relevance_second_audit_batches_resolved",
                next_action=next_action,
                terminal=active is None,
                blocked=active is not None,
                blocked_by_phase="source_verification" if active else None,
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
            blocked_by_phase="source_verification" if active else None,
            active_batch_id=doc.get("active_batch_id"),
            summary={**(doc.get("summary") or {}), "spawn_request_count": len(requests)},
        ),
        "spawn_request_count": len(requests),
        "spawn_requests": requests,
    }


def prepare_topic_relevance_batches(task_dir: Path, batch_size: int = DEFAULT_BATCH_SIZE) -> dict:
    state = _state(task_dir)
    records = _candidate_records(task_dir)
    paper_ids = sorted(records)
    plan_hash = _stable_hash({"paper_ids": paper_ids, "batch_size": batch_size})
    existing = read_json(state / "topic_relevance_batches.json")
    if existing.get("plan_hash") == plan_hash and existing.get("batches"):
        doc = _refresh_batch_statuses(existing)
        doc = _split_active_batch_after_worker_failures(task_dir, doc)
        doc = _refresh_batch_statuses(doc)
    else:
        doc = {
            "plan_hash": plan_hash,
            "batch_size": batch_size,
            "paper_count": len(paper_ids),
            "batches": _make_batches(paper_ids, batch_size),
        }
        doc = _refresh_batch_statuses(doc)
    doc = _with_metadata(doc)
    write_json(state / "topic_relevance_batches.json", doc)
    return _write_runtime_action(task_dir, doc)


def prepare_topic_relevance_second_audit_batches(task_dir: Path, batch_size: int = DEFAULT_SECOND_AUDIT_BATCH_SIZE) -> dict:
    state = _state(task_dir)
    raw = read_jsonl(state / "raw_candidates.jsonl")
    papers = read_jsonl(state / "papers.jsonl")
    citation = read_jsonl(state / "citation_plan.jsonl")
    audit = read_jsonl(state / "topic_relevance_audit.jsonl")
    second = read_jsonl(state / "topic_relevance_second_audits.jsonl")
    target = str(read_json(state / "progress.json").get("target") or "full")
    if target not in {"short", "full", "csur"}:
        target = "full"
    validation = validate_topic_relevance(raw, papers, citation, audit, _read_survey_type(task_dir), target, secondary_audits=second)
    paper_ids = sorted(validation.get("second_audit_required_paper_ids") or [])
    plan_hash = _stable_hash({"paper_ids": paper_ids, "batch_size": batch_size, "audit": audit, "second": second})
    existing = read_json(state / "topic_relevance_second_audit_batches.json")
    if existing.get("plan_hash") == plan_hash and existing.get("batches"):
        doc = _refresh_batch_statuses(existing)
    else:
        doc = {
            "plan_hash": plan_hash,
            "batch_size": batch_size,
            "paper_count": len(paper_ids),
            "batches": _make_second_audit_batches(paper_ids, batch_size),
        }
        doc = _refresh_batch_statuses(doc)
    doc = _with_metadata(doc)
    write_json(state / "topic_relevance_second_audit_batches.json", doc)
    return _write_second_audit_runtime_action(task_dir, doc)


def collect_topic_relevance_status(task_dir: Path) -> dict:
    state = _state(task_dir)
    doc = _refresh_batch_statuses(read_json(state / "topic_relevance_batches.json"))
    if not doc.get("batches"):
        return {
            **status_envelope(
                COMPONENT,
                "not_prepared",
                next_action="prepare_topic_relevance_batches",
                terminal=False,
                blocked=True,
                blocked_by_phase="source_verification",
                summary={"batch_count": 0, "paper_count": 0},
            ),
            "batches": [],
        }
    doc = _with_metadata(doc)
    write_json(state / "topic_relevance_batches.json", doc)
    all_resolved = all(batch.get("status") == "resolved" for batch in doc.get("batches") or [])
    return {
        **status_envelope(
            COMPONENT,
            "resolved" if all_resolved else "pending_topic_relevance_runtime",
            next_action="rerun_phase_gate" if all_resolved else "spawn_topic_relevance_agents",
            terminal=all_resolved,
            blocked=not all_resolved,
            blocked_by_phase=None if all_resolved else "source_verification",
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
    passed: set[str] = set()
    for item in validators:
        if not isinstance(item, dict):
            continue
        name = str(item.get("validator") or item.get("name") or "").strip()
        if not name:
            continue
        ok = str(item.get("status") or "").lower() == "passed" or item.get("passed") is True
        if not ok:
            continue
        passed.add(name)
        if name in PRIMARY_VALIDATOR_ALIASES:
            passed.add(PRIMARY_VALIDATOR_ALIASES[name])
        if name in SECONDARY_VALIDATOR_ALIASES:
            passed.add(SECONDARY_VALIDATOR_ALIASES[name])
    return passed


def _normalize_result_status(result: dict) -> dict:
    if not isinstance(result, dict):
        return result
    if str(result.get("status") or "").lower() == "completed":
        normalized = dict(result)
        normalized["status"] = "resolved"
        normalized["status_normalized_from"] = "completed"
        return normalized
    return result


def _merge_audits(existing: list[dict], replacements: list[dict], paper_ids: set[str]) -> list[dict]:
    return [row for row in existing if _paper_id(row) not in paper_ids] + replacements


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
    expected_ids = {str(pid) for pid in batch.get("paper_ids") or []}
    records = result.get("audit_records")
    if not isinstance(records, list) or not records:
        errors.append("missing_audit_records")
        records = []
    record_ids = [_paper_id(row) for row in records if isinstance(row, dict)]
    if len(record_ids) != len(set(record_ids)):
        errors.append("duplicate_audit_record_paper_ids")
    if expected_ids - set(record_ids):
        errors.append("missing_batch_topic_relevance_audits")
    if set(record_ids) - expected_ids:
        errors.append("unknown_topic_relevance_audit_paper_ids")
    if "validate_topic_relevance" not in _passed_validators(result):
        errors.append("missing_acceptance_validators")
    subset_raw = [row for row in read_jsonl(_state(task_dir) / "raw_candidates.jsonl") if _paper_id(row) in expected_ids]
    subset_papers = [row for row in read_jsonl(_state(task_dir) / "papers.jsonl") if _paper_id(row) in expected_ids]
    subset_citation = [row for row in read_jsonl(_state(task_dir) / "citation_plan.jsonl") if _paper_id(row) in expected_ids]
    validation = validate_topic_relevance(subset_raw, subset_papers, subset_citation, records, _read_survey_type(task_dir), "short")
    schema_errors = validation.get("schema_errors") or []
    if schema_errors:
        errors.append("invalid_topic_relevance_audit")
    return sorted(set(errors))


def _validate_second_audit_result(task_dir: Path, result: dict, batch: dict, subagent_session_id: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result_not_object"]
    for key in SECOND_AUDIT_RESULT_KEYS:
        if key not in result:
            errors.append(f"missing_{key}")
    if str(result.get("batch_id") or "") != str(batch.get("batch_id") or ""):
        errors.append("batch_id_mismatch")
    if str(result.get("status") or "") not in VALID_RESULT_STATUSES:
        errors.append("invalid_status")
    if result.get("status") != "resolved":
        return sorted(set(errors))
    expected_ids = {str(pid) for pid in batch.get("paper_ids") or []}
    paper_ids = {str(pid) for pid in result.get("paper_ids") or [] if str(pid)}
    if paper_ids != expected_ids:
        errors.append("paper_ids_mismatch")
    records = result.get("secondary_audit_records")
    if not isinstance(records, list) or not records:
        errors.append("missing_secondary_audit_records")
        records = []
    record_ids = [_paper_id(row) for row in records if isinstance(row, dict)]
    if len(record_ids) != len(set(record_ids)):
        errors.append("duplicate_secondary_audit_record_paper_ids")
    if expected_ids - set(record_ids):
        errors.append("missing_batch_secondary_audits")
    if set(record_ids) - expected_ids:
        errors.append("unknown_secondary_audit_paper_ids")
    if "validate_topic_relevance_second_audit" not in _passed_validators(result):
        errors.append("missing_acceptance_validators")
    primary = _primary_audits(task_dir)
    depths = _citation_depths(task_dir)
    for record in records:
        if not isinstance(record, dict):
            errors.append("secondary_record_not_object")
            continue
        pid = _paper_id(record)
        if subagent_session_id and str(record.get("subagent_session_id") or "") != subagent_session_id:
            errors.append(f"secondary_audit_session_mismatch:{pid or 'unknown'}")
        errors.extend(secondary_audit_record_errors(record, primary.get(pid), depths.get(pid, "C")))
    return sorted(set(errors))


def record_topic_relevance_result(task_dir: Path, result: dict, subagent_session_id: str) -> dict:
    result = _normalize_result_status(result)
    state = _state(task_dir)
    doc = _refresh_batch_statuses(read_json(state / "topic_relevance_batches.json"))
    batch_id = str(result.get("batch_id") or "")
    batch = next((item for item in doc.get("batches") or [] if str(item.get("batch_id") or "") == batch_id), None)
    if not batch:
        return {"status": "invalid", "error": "unknown_batch_id"}
    if batch_id != str(doc.get("active_batch_id") or ""):
        return {"status": "invalid", "error": "batch_blocked_by_upstream"}
    errors = _validate_result(task_dir, result, batch)
    if errors:
        return {"status": "invalid", "error": "invalid_topic_relevance_result", "errors": errors}
    recorded_at = _utc_now()
    result_hash = _stable_hash(result)
    stamped_records = [
        {
            **record,
            "fresh_context": True,
            "batch_id": batch_id,
            "source_batch_id": batch_id,
            "result_hash": result_hash,
            "subagent_session_id": subagent_session_id,
            "recorded_at": recorded_at,
        }
        for record in result.get("audit_records") or []
        if isinstance(record, dict)
    ]
    row = {
        **result,
        "audit_records": stamped_records,
        "fresh_context": True,
        "result_hash": result_hash,
        "subagent_session_id": subagent_session_id,
        "recorded_at": recorded_at,
    }
    write_jsonl(state / "topic_relevance_results.jsonl", read_jsonl(state / "topic_relevance_results.jsonl") + [row])
    if result.get("status") == "resolved":
        paper_ids = {str(pid) for pid in batch.get("paper_ids") or []}
        merged = _merge_audits(read_jsonl(state / "topic_relevance_audit.jsonl"), stamped_records, paper_ids)
        write_jsonl(state / "topic_relevance_audit.jsonl", merged)
        batch["status"] = "resolved"
        batch["resolved_at"] = recorded_at
        batch["subagent_session_id"] = subagent_session_id
    else:
        batch["status"] = str(result.get("status"))
    doc = _with_metadata(_refresh_batch_statuses(doc))
    write_json(state / "topic_relevance_batches.json", doc)
    _write_runtime_action(task_dir, doc)
    return {"status": "recorded", "batch_id": batch_id, "next_active_batch_id": doc.get("active_batch_id")}


def record_topic_relevance_second_audit_result(task_dir: Path, result: dict, subagent_session_id: str) -> dict:
    result = _normalize_result_status(result)
    state = _state(task_dir)
    doc = _refresh_batch_statuses(read_json(state / "topic_relevance_second_audit_batches.json"))
    batch_id = str(result.get("batch_id") or "")
    batch = next((item for item in doc.get("batches") or [] if str(item.get("batch_id") or "") == batch_id), None)
    if not batch:
        return {"status": "invalid", "error": "unknown_batch_id"}
    if batch_id != str(doc.get("active_batch_id") or ""):
        return {"status": "invalid", "error": "batch_blocked_by_upstream"}
    errors = _validate_second_audit_result(task_dir, result, batch, subagent_session_id)
    if errors:
        return {"status": "invalid", "error": "invalid_topic_relevance_second_audit_result", "errors": errors}
    recorded_at = _utc_now()
    row = {**result, "fresh_context": True, "subagent_session_id": subagent_session_id, "recorded_at": recorded_at}
    write_jsonl(state / "topic_relevance_results.jsonl", read_jsonl(state / "topic_relevance_results.jsonl") + [row])
    if result.get("status") == "resolved":
        existing = [item for item in read_jsonl(state / "topic_relevance_second_audits.jsonl") if _paper_id(item) not in set(result.get("paper_ids") or [])]
        replacement = [
            {**record, "fresh_context": True, "recorded_at": recorded_at}
            for record in result.get("secondary_audit_records") or []
        ]
        write_jsonl(state / "topic_relevance_second_audits.jsonl", existing + replacement)
        batch["status"] = "resolved"
        batch["resolved_at"] = recorded_at
        batch["subagent_session_id"] = subagent_session_id
    else:
        batch["status"] = str(result.get("status"))
    doc = _with_metadata(_refresh_batch_statuses(doc))
    write_json(state / "topic_relevance_second_audit_batches.json", doc)
    _write_second_audit_runtime_action(task_dir, doc)
    return {"status": "recorded", "batch_id": batch_id, "next_active_batch_id": doc.get("active_batch_id")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--prepare-second-audit", action="store_true")
    parser.add_argument("--collect-status", action="store_true")
    parser.add_argument("--record-result", type=Path)
    parser.add_argument("--record-second-audit", type=Path)
    parser.add_argument("--subagent-session-id")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()
    if args.prepare:
        result = prepare_topic_relevance_batches(args.task_dir, args.batch_size)
    elif args.prepare_second_audit:
        result = prepare_topic_relevance_second_audit_batches(args.task_dir, args.batch_size)
    elif args.collect_status:
        result = collect_topic_relevance_status(args.task_dir)
    elif args.record_result:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_topic_relevance_result(args.task_dir, json.loads(args.record_result.read_text(encoding="utf-8")), args.subagent_session_id)
    elif args.record_second_audit:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_topic_relevance_second_audit_result(args.task_dir, json.loads(args.record_second_audit.read_text(encoding="utf-8")), args.subagent_session_id)
    else:
        result = {"status": "invalid", "error": "choose --prepare, --prepare-second-audit, --collect-status, --record-result, or --record-second-audit"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
