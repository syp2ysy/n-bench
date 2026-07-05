#!/usr/bin/env python3
"""Prepare and record the topic-boundary worker output."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_jsonl, write_json, write_jsonl
    from .status_schema import STATUS_SCHEMA_VERSION, status_envelope
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_jsonl, write_json, write_jsonl
    from status_schema import STATUS_SCHEMA_VERSION, status_envelope


REQUIRED_FIELDS = [
    "topic",
    "central_question",
    "positive_anchors",
    "negative_anchors",
    "allowed_background",
    "core_claim_types",
    "search_seed_queries",
    "acceptance_rubric",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _stable_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _task_spec(task_dir: Path) -> str:
    path = task_dir / "state" / "task_spec.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write_runtime_intent(task_dir: Path, target: str) -> str:
    state = task_dir / "state"
    source_hashes = {
        "state/task_spec.md": _sha256_file(state / "task_spec.md"),
        "state/topic_profile_spawn_requests.json": _sha256_file(state / "topic_profile_spawn_requests.json"),
    }
    payload = {
        "active_phase": "topic_profile",
        "next_action": "spawn_topic_profile_agents",
        "allowed_request_types": ["topic_profile"],
        "source_hashes": source_hashes,
    }
    generation = _stable_hash(payload)
    write_json(
        state / "runtime_active_intent.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "active_phase": "topic_profile",
            "next_action": "spawn_topic_profile_agents",
            "allowed_request_types": ["topic_profile"],
            "phase_generation": generation,
            "source_hashes": source_hashes,
            "generated_at": _utc_now(),
        },
    )
    return generation


def prepare_topic_profile_request(task_dir: Path, target: str = "full") -> dict:
    state = task_dir / "state"
    request = {
        "request_id": "topic-profile-TP001",
        "next_action": "spawn_topic_profile_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": 1,
        "batch_id": "TP001",
        "target": target,
        "task_spec": _task_spec(task_dir),
        "required_result_keys": REQUIRED_FIELDS + ["validator_results", "remaining_blockers"],
        "record_command": f"python3 scripts/topic_profile.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>",
        "message": (
            "You are the Topic Boundary Agent for survey-autoresearch.\n"
            "Define the scope before any corpus search. Do not invent search results or papers.\n"
            f"Task directory: {task_dir.resolve()}\n"
            "Return one JSON object with topic, central_question, positive_anchors, negative_anchors, "
            "allowed_background, core_claim_types, search_seed_queries, acceptance_rubric, "
            "validator_results, and remaining_blockers.\n\n"
            f"Task spec:\n{_task_spec(task_dir)}"
        ),
    }
    write_json(
        state / "topic_profile_spawn_requests.json",
        {
            "next_action": "spawn_topic_profile_agents",
            "spawn_requests": [request],
        },
    )
    _write_runtime_intent(task_dir, target)
    return {
        **status_envelope(
            "topic_profile",
            "blocked_topic_profile_agent_spawn_required",
            next_action="spawn_topic_profile_agents",
            terminal=False,
            blocked=True,
            blocked_by_phase="topic_profile",
            active_batch_id="TP001",
            summary={"spawn_request_count": 1},
        ),
        "spawn_request_count": 1,
        "spawn_requests": [request],
    }


def _profile_errors(result: dict) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        value = result.get(field)
        if value in [None, "", [], {}]:
            errors.append(f"missing_{field}")
    rubric = result.get("acceptance_rubric") or {}
    if isinstance(rubric, dict):
        for key in ["paper_relevance", "survey_spine", "paper_understanding"]:
            if not rubric.get(key):
                errors.append(f"missing_acceptance_rubric_{key}")
    else:
        errors.append("invalid_acceptance_rubric")
    validators = result.get("validator_results") or []
    if not any((row.get("validator") or row.get("name")) == "validate_topic_profile" and row.get("status") == "passed" for row in validators if isinstance(row, dict)):
        errors.append("missing_validate_topic_profile_pass")
    return errors


def record_topic_profile_result(task_dir: Path, result: dict, subagent_session_id: str) -> dict:
    state = task_dir / "state"
    errors = _profile_errors(result)
    row = {
        "recorded_at": _utc_now(),
        "subagent_session_id": subagent_session_id,
        "status": "invalid" if errors else "recorded",
        "errors": errors,
        "result": result,
    }
    write_jsonl(state / "topic_profile_results.jsonl", read_jsonl(state / "topic_profile_results.jsonl") + [row])
    if errors:
        return {"component": "topic_profile", "status": "invalid", "errors": errors}
    profile = {field: result.get(field) for field in REQUIRED_FIELDS}
    profile["schema_version"] = STATUS_SCHEMA_VERSION
    profile["subagent_session_id"] = subagent_session_id
    profile["recorded_at"] = row["recorded_at"]
    profile["must_find_related_surveys"] = bool(result.get("must_find_related_surveys", True))
    write_json(state / "topic_profile.json", profile)
    return {"component": "topic_profile", "status": "recorded", "topic_profile": profile}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--record-result", type=Path)
    parser.add_argument("--subagent-session-id", default="")
    args = parser.parse_args()
    if args.record_result:
        result = record_topic_profile_result(args.task_dir, json.loads(args.record_result.read_text(encoding="utf-8")), args.subagent_session_id)
    else:
        result = prepare_topic_profile_request(args.task_dir, args.target)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
