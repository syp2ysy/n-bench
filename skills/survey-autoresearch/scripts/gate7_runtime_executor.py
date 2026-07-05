#!/usr/bin/env python3
"""Prepare and record phase-ordered Gate 7 runtime repair work."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .gate7_loop import record_repair_action, record_regression_check
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .status_schema import STATUS_SCHEMA_VERSION, status_envelope
except ImportError:  # pragma: no cover
    from gate7_loop import record_repair_action, record_regression_check
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from status_schema import STATUS_SCHEMA_VERSION, status_envelope


PHASE_ORDER = ["source_verification", "paper_understanding", "synthesis", "argument", "article"]
VALID_RESULT_STATUSES = {"resolved", "partially_resolved", "blocked"}
RUNTIME_RESULT_SCHEMA_VERSION = 1
REQUIRED_RESULT_KEYS = [
    "batch_id",
    "status",
    "changed_artifacts",
    "artifact_hashes_before",
    "artifact_hashes_after",
    "repair_records",
    "regression_checks",
    "validator_results",
    "remaining_blockers",
]


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _sha256_artifact(task_dir: Path, artifact: str) -> str:
    path = task_dir / artifact
    if not path.exists():
        return ""
    if path.is_file():
        return _sha256_file(path)
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _stable_hash(value) -> str:
    payload = json.dumps(value or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _batch_summary(batches_doc: dict, plan: dict | None = None) -> dict:
    batches = batches_doc.get("batches") or []
    active_batch_id = batches_doc.get("active_batch_id")
    active = next((batch for batch in batches if batch.get("batch_id") == active_batch_id), None)
    pending = [batch for batch in batches if batch.get("status") != "resolved"]
    return {
        "batch_count": len(batches),
        "active_batch_id": active_batch_id,
        "active_rollback_phase": active.get("rollback_phase") if active else None,
        "pending_batch_count": len(pending),
        "resolved_batch_count": len(batches) - len(pending),
        "rerun_policy": batches_doc.get("rerun_policy") or (plan or {}).get("rerun_policy"),
        "major_rebuild_required": bool(batches_doc.get("major_rebuild_required") or (plan or {}).get("major_rebuild_required")),
    }


def _with_batch_metadata(batches_doc: dict, plan: dict | None = None) -> dict:
    batches_doc = dict(batches_doc or {})
    batches_doc["schema_version"] = STATUS_SCHEMA_VERSION
    batches_doc["summary"] = _batch_summary(batches_doc, plan)
    return batches_doc


def _phase_key(phase: str) -> tuple[int, str]:
    try:
        return (PHASE_ORDER.index(phase), phase)
    except ValueError:
        return (len(PHASE_ORDER), phase)


def _union(items: list[dict], key: str) -> list[str]:
    values: list[str] = []
    for item in items:
        for value in item.get(key) or []:
            if value not in values:
                values.append(value)
    return sorted(values)


def _batch_prompt(task_dir: Path, batch: dict, plan: dict) -> str:
    weakness_lines = []
    for item in batch.get("repair_items") or []:
        weakness_lines.append(
            "- "
            + json.dumps(
                {
                    "repair_id": item.get("repair_id"),
                    "weakness_id": item.get("weakness_id"),
                    "route_to": item.get("route_to"),
                    "affected_sections": item.get("affected_sections") or [],
                    "affected_papers": item.get("affected_papers") or [],
                    "affected_claims": item.get("affected_claims") or [],
                    "required_evidence_check": item.get("required_evidence_check") or [],
                    "acceptance_validators": item.get("acceptance_validators") or [],
                    "repair_acceptance_criteria": item.get("repair_acceptance_criteria") or "",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return (
        "You are a Gate 7 repair agent for survey-autoresearch.\n"
        "Use source/evidence state first; do not fabricate reviewer or targeted rereview output.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Review round id: {plan.get('review_round_id')}\n"
        f"Batch id: {batch.get('batch_id')}\n"
        f"Rollback phase: {batch.get('rollback_phase')}\n"
        "Repair items:\n"
        + "\n".join(weakness_lines)
        + "\n\nReturn one JSON object with keys: batch_id, status, changed_artifacts, "
        "artifact_hashes_before, artifact_hashes_after, repair_records, regression_checks, "
        "validator_results, remaining_blockers. status must be resolved, partially_resolved, or blocked. "
        "For resolved batches, repair_records and regression_checks must cover every weakness_id in this batch exactly once, "
        "and validator_results must include one passed object for every acceptance_validators entry using "
        '{"validator": "<acceptance_validator>", "status": "passed", "command": "...", "result": "..."}'
        ". changed_artifacts, artifact_hashes_before, and artifact_hashes_after must cover every changed_artifacts entry "
        "listed in the batch; artifact_hashes_after must match the repaired files/directories on disk."
    )


def _spawn_request_for_batch(task_dir: Path, batch: dict, plan: dict) -> dict:
    return {
        "request_id": f"repair-{batch.get('batch_id')}",
        "next_action": "spawn_repair_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": RUNTIME_RESULT_SCHEMA_VERSION,
        "required_result_keys": list(REQUIRED_RESULT_KEYS),
        "review_round_id": plan.get("review_round_id"),
        "batch_id": batch.get("batch_id"),
        "rollback_phase": batch.get("rollback_phase"),
        "repair_item_count": len(batch.get("repair_items") or []),
        "weakness_ids": [item.get("weakness_id") for item in batch.get("repair_items") or []],
        "expected_weakness_ids": [item.get("weakness_id") for item in batch.get("repair_items") or []],
        "changed_artifacts": batch.get("changed_artifacts") or [],
        "expected_changed_artifacts": batch.get("changed_artifacts") or [],
        "acceptance_validators": batch.get("acceptance_validators") or [],
        "expected_acceptance_validators": batch.get("acceptance_validators") or [],
        "record_command": f"python3 scripts/gate7_runtime_executor.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>",
        "message": _batch_prompt(task_dir, batch, plan),
        "status": "pending_spawn",
    }


def _write_active_spawn_request(task_dir: Path, batches_doc: dict, plan: dict) -> dict:
    batches_doc = _with_batch_metadata(batches_doc, plan)
    active = next((batch for batch in batches_doc.get("batches") or [] if batch.get("batch_id") == batches_doc.get("active_batch_id")), None)
    requests = [_spawn_request_for_batch(task_dir, active, plan)] if active else []
    write_json(_state(task_dir) / "gate7_spawn_requests.json", {"next_action": "spawn_repair_agents", "spawn_requests": requests})
    next_action = "spawn_repair_agents" if active else ("reset_full_review_round" if plan.get("rerun_policy") == "full_gate7_round" else "spawn_targeted_rereviewers")
    runtime_status = "pending_runtime_repair" if active else "repair_batches_resolved"
    runtime_summary = dict(batches_doc.get("summary") or {})
    runtime_summary["spawn_request_count"] = len(requests)
    write_json(
        _state(task_dir) / "gate7_runtime_action.json",
        {
            **status_envelope(
                "gate7_runtime_executor",
                runtime_status,
                next_action=next_action,
                terminal=active is None,
                blocked=active is not None,
                active_batch_id=batches_doc.get("active_batch_id"),
                summary=runtime_summary,
            ),
            "review_round_id": plan.get("review_round_id"),
            "candidate_hash": plan.get("candidate_hash"),
            "rerun_policy": plan.get("rerun_policy"),
            "major_rebuild_required": bool(plan.get("major_rebuild_required")),
            "active_batch_id": batches_doc.get("active_batch_id"),
            "batch_count": len(batches_doc.get("batches") or []),
            "pending_batch_count": len([batch for batch in batches_doc.get("batches") or [] if batch.get("status") != "resolved"]),
        },
    )
    result_status = "blocked_repair_agent_spawn_required" if active else "repair_batches_resolved"
    result_summary = dict(runtime_summary)
    result_summary["spawn_request_count"] = len(requests)
    return {
        **status_envelope(
            "gate7_runtime_executor",
            result_status,
            next_action=next_action,
            terminal=active is None,
            blocked=active is not None,
            active_batch_id=batches_doc.get("active_batch_id"),
            summary=result_summary,
        ),
        "rerun_policy": plan.get("rerun_policy"),
        "active_batch_id": batches_doc.get("active_batch_id"),
        "spawn_request_count": len(requests),
        "spawn_requests": requests,
    }


def _refresh_batch_statuses(batches_doc: dict) -> dict:
    active_found = False
    active_batch_id = None
    for batch in batches_doc.get("batches") or []:
        if batch.get("status") == "resolved":
            continue
        if not active_found:
            if batch.get("status") == "blocked_by_upstream":
                batch["status"] = "pending_spawn"
            active_found = True
            active_batch_id = batch.get("batch_id")
        else:
            batch["status"] = "blocked_by_upstream"
    batches_doc["active_batch_id"] = active_batch_id
    return batches_doc


def _make_batches(plan: dict) -> list[dict]:
    by_phase: dict[str, list[dict]] = {}
    for item in plan.get("repair_items") or []:
        phase = str(item.get("rollback_phase") or "article")
        by_phase.setdefault(phase, []).append(item)
    batches = []
    for idx, phase in enumerate(sorted(by_phase, key=_phase_key), start=1):
        items = by_phase[phase]
        batches.append(
            {
                "batch_id": f"RB{idx:03d}",
                "rollback_phase": phase,
                "status": "pending_spawn" if idx == 1 else "blocked_by_upstream",
                "repair_items": items,
                "repair_item_count": len(items),
                "weakness_ids": [item.get("weakness_id") for item in items],
                "changed_artifacts": _union(items, "changed_artifacts"),
                "required_evidence_check": _union(items, "required_evidence_check"),
                "acceptance_validators": _union(items, "acceptance_validators"),
            }
        )
    return batches


def prepare_runtime_repair(task_dir: Path, plan: dict | None = None) -> dict:
    state = _state(task_dir)
    plan = plan or read_json(state / "gate7_repair_plan.json")
    if not plan or not plan.get("repair_items"):
        return {
            **status_envelope(
                "gate7_runtime_executor",
                "invalid",
                next_action="build_repair_plan",
                terminal=True,
                blocked=True,
                summary={"error": "missing_gate7_repair_plan"},
            ),
            "error": "missing_gate7_repair_plan",
        }
    plan_hash = _stable_hash(plan)
    existing = read_json(state / "gate7_repair_batches.json")
    if existing.get("plan_hash") == plan_hash and existing.get("batches"):
        batches_doc = _refresh_batch_statuses(existing)
    else:
        batches_doc = {
            "plan_hash": plan_hash,
            "review_round_id": plan.get("review_round_id"),
            "candidate_hash": plan.get("candidate_hash"),
            "rerun_policy": plan.get("rerun_policy"),
            "major_rebuild_required": bool(plan.get("major_rebuild_required")),
            "batches": _make_batches(plan),
        }
        batches_doc = _refresh_batch_statuses(batches_doc)
    batches_doc = _with_batch_metadata(batches_doc, plan)
    write_json(state / "gate7_repair_batches.json", batches_doc)
    return _write_active_spawn_request(task_dir, batches_doc, plan)


def collect_runtime_repair_status(task_dir: Path) -> dict:
    state = _state(task_dir)
    plan = read_json(state / "gate7_repair_plan.json")
    batches_doc = _refresh_batch_statuses(read_json(state / "gate7_repair_batches.json"))
    if not batches_doc.get("batches"):
        return {
            **status_envelope(
                "gate7_runtime_executor",
                "not_prepared",
                next_action="prepare_runtime_repair",
                terminal=False,
                blocked=True,
                active_batch_id=None,
                summary={"batch_count": 0, "active_batch_id": None, "pending_batch_count": 0, "resolved_batch_count": 0},
            ),
            "batches": [],
        }
    batches_doc = _with_batch_metadata(batches_doc, plan)
    write_json(state / "gate7_repair_batches.json", batches_doc)
    all_resolved = all(batch.get("status") == "resolved" for batch in batches_doc.get("batches") or [])
    next_action = "spawn_repair_agents"
    if all_resolved:
        next_action = "reset_full_review_round" if plan.get("rerun_policy") == "full_gate7_round" else "spawn_targeted_rereviewers"
    summary = dict(batches_doc.get("summary") or {})
    summary["all_batches_resolved"] = all_resolved
    return {
        **status_envelope(
            "gate7_runtime_executor",
            "resolved" if all_resolved else "pending_runtime_repair",
            next_action=next_action,
            terminal=all_resolved,
            blocked=not all_resolved,
            active_batch_id=batches_doc.get("active_batch_id"),
            summary=summary,
        ),
        "status": "resolved" if all_resolved else "pending_runtime_repair",
        "active_batch_id": batches_doc.get("active_batch_id"),
        "batches": batches_doc.get("batches") or [],
        "all_batches_resolved": all_resolved,
        "ready_for_full_reround": all_resolved and plan.get("rerun_policy") == "full_gate7_round",
        "ready_for_targeted_rereview": all_resolved and plan.get("rerun_policy") == "targeted_rereview",
        "rerun_policy": plan.get("rerun_policy"),
    }


def _record_weakness_ids(rows) -> list[str]:
    if not isinstance(rows, list):
        return []
    return [
        str(item.get("weakness_id") or "").strip()
        for item in rows
        if isinstance(item, dict) and str(item.get("weakness_id") or "").strip()
    ]


def _has_duplicates(values: list[str]) -> bool:
    return len(values) != len(set(values))


def _validate_result(task_dir: Path, result: dict, batch: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result_not_object"]
    if str(result.get("batch_id") or "") != str(batch.get("batch_id") or ""):
        errors.append("batch_id_mismatch")
    if str(result.get("status") or "") not in VALID_RESULT_STATUSES:
        errors.append("invalid_status")
    for field in ["changed_artifacts", "artifact_hashes_before", "artifact_hashes_after", "repair_records", "regression_checks", "validator_results", "remaining_blockers"]:
        if field not in result:
            errors.append(f"missing_{field}")
    if result.get("status") == "resolved":
        expected_weakness_ids = {
            str(weakness_id).strip()
            for weakness_id in batch.get("weakness_ids") or []
            if str(weakness_id).strip()
        }
        repair_records = result.get("repair_records")
        regression_checks = result.get("regression_checks")
        if not isinstance(repair_records, list) or not repair_records:
            errors.append("missing_repair_records")
        else:
            repair_weakness_id_list = _record_weakness_ids(repair_records)
            repair_weakness_ids = set(repair_weakness_id_list)
            if _has_duplicates(repair_weakness_id_list):
                errors.append("duplicate_repair_weakness_ids")
            if expected_weakness_ids - repair_weakness_ids:
                errors.append("missing_batch_repair_records")
            if repair_weakness_ids - expected_weakness_ids:
                errors.append("unknown_repair_weakness_ids")
        if not isinstance(regression_checks, list) or not regression_checks:
            errors.append("missing_regression_checks")
        else:
            regression_weakness_id_list = _record_weakness_ids(regression_checks)
            regression_weakness_ids = set(regression_weakness_id_list)
            if _has_duplicates(regression_weakness_id_list):
                errors.append("duplicate_regression_weakness_ids")
            if expected_weakness_ids - regression_weakness_ids:
                errors.append("missing_batch_regression_checks")
            if regression_weakness_ids - expected_weakness_ids:
                errors.append("unknown_regression_weakness_ids")
        expected_artifacts = {
            str(artifact).strip()
            for artifact in batch.get("changed_artifacts") or []
            if str(artifact).strip()
        }
        changed_artifacts = result.get("changed_artifacts")
        if not isinstance(changed_artifacts, list):
            errors.append("invalid_changed_artifacts")
            changed_artifact_set: set[str] = set()
        else:
            changed_artifact_set = {str(artifact).strip() for artifact in changed_artifacts if str(artifact).strip()}
        if expected_artifacts - changed_artifact_set:
            errors.append("missing_changed_artifacts")
        before_hashes = result.get("artifact_hashes_before")
        after_hashes = result.get("artifact_hashes_after")
        if not isinstance(before_hashes, dict):
            errors.append("invalid_artifact_hashes_before")
            before_hashes = {}
        if not isinstance(after_hashes, dict):
            errors.append("invalid_artifact_hashes_after")
            after_hashes = {}
        before_keys = {str(key) for key in before_hashes}
        after_keys = {str(key) for key in after_hashes}
        if expected_artifacts - before_keys:
            errors.append("missing_artifact_hashes_before")
        if expected_artifacts - after_keys:
            errors.append("missing_artifact_hashes_after")
        for artifact in sorted(expected_artifacts & after_keys):
            if str(after_hashes.get(artifact) or "") != _sha256_artifact(task_dir, artifact):
                errors.append("artifact_hash_mismatch")
        validators = result.get("validator_results") or []
        if (
            not isinstance(validators, list)
            or not validators
            or any(not isinstance(item, dict) or str(item.get("status") or "").lower() != "passed" for item in validators)
        ):
            errors.append("invalid_validator_results")
        else:
            passed_validators = {
                str(item.get("validator") or item.get("name") or "").strip()
                for item in validators
                if isinstance(item, dict)
                and str(item.get("status") or "").lower() == "passed"
                and str(item.get("validator") or item.get("name") or "").strip()
            }
            expected_validators = {
                str(validator).strip()
                for validator in batch.get("acceptance_validators") or []
                if str(validator).strip()
            }
            if expected_validators - passed_validators:
                errors.append("missing_acceptance_validators")
    return sorted(set(errors))


def record_runtime_repair_result(task_dir: Path, result: dict, subagent_session_id: str) -> dict:
    state = _state(task_dir)
    batches_doc = _refresh_batch_statuses(read_json(state / "gate7_repair_batches.json"))
    plan = read_json(state / "gate7_repair_plan.json")
    batch_id = str(result.get("batch_id") or "")
    batch = next((item for item in batches_doc.get("batches") or [] if str(item.get("batch_id") or "") == batch_id), None)
    if not batch:
        return {"status": "invalid", "error": "unknown_batch_id"}
    if batch_id != str(batches_doc.get("active_batch_id") or ""):
        return {"status": "invalid", "error": "batch_blocked_by_upstream"}
    errors = _validate_result(task_dir, result, batch)
    if errors:
        return {"status": "invalid", "error": "invalid_repair_result", "errors": errors}
    if result.get("status") != "resolved":
        row = {**result, "fresh_context": True, "subagent_session_id": subagent_session_id, "recorded_at": _utc_now()}
        write_jsonl(state / "gate7_repair_results.jsonl", read_jsonl(state / "gate7_repair_results.jsonl") + [row])
        batch["status"] = str(result.get("status"))
        write_json(state / "gate7_repair_batches.json", _with_batch_metadata(_refresh_batch_statuses(batches_doc), plan))
        return {"status": str(result.get("status")), "batch_id": batch_id}
    for repair in result.get("repair_records") or []:
        recorded = record_repair_action(task_dir, repair)
        if recorded.get("status") != "recorded":
            return {"status": "invalid", "error": "invalid_repair_record", "repair_status": recorded}
    for check in result.get("regression_checks") or []:
        recorded = record_regression_check(task_dir, check)
        if recorded.get("status") != "recorded":
            return {"status": "invalid", "error": "invalid_regression_check", "check_status": recorded}
    row = {
        **result,
        "fresh_context": True,
        "subagent_session_id": subagent_session_id,
        "recorded_at": _utc_now(),
        "candidate_hash_after_record": _sha256_file(task_dir / "outputs" / "survey_candidate.md"),
    }
    write_jsonl(state / "gate7_repair_results.jsonl", read_jsonl(state / "gate7_repair_results.jsonl") + [row])
    batch["status"] = "resolved"
    batch["resolved_at"] = row["recorded_at"]
    batch["subagent_session_id"] = subagent_session_id
    batches_doc = _refresh_batch_statuses(batches_doc)
    batches_doc = _with_batch_metadata(batches_doc, plan)
    write_json(state / "gate7_repair_batches.json", batches_doc)
    _write_active_spawn_request(task_dir, batches_doc, plan)
    return {"status": "recorded", "batch_id": batch_id, "next_active_batch_id": batches_doc.get("active_batch_id")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--collect-status", action="store_true")
    parser.add_argument("--record-result", type=Path)
    parser.add_argument("--subagent-session-id")
    args = parser.parse_args()
    if args.prepare:
        result = prepare_runtime_repair(args.task_dir)
    elif args.collect_status:
        result = collect_runtime_repair_status(args.task_dir)
    elif args.record_result:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_runtime_repair_result(args.task_dir, json.loads(args.record_result.read_text(encoding="utf-8")), args.subagent_session_id)
    else:
        result = {"status": "invalid", "error": "choose --prepare, --collect-status, or --record-result"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
