#!/usr/bin/env python3
"""Prepare and record phase-ordered paper-understanding worker batches."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .phase_gate import evaluate_phase_barriers
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .status_schema import STATUS_SCHEMA_VERSION, status_envelope
    from .validate_paper_understanding import depth_ids, validate_paper_understanding
except ImportError:  # pragma: no cover
    from phase_gate import evaluate_phase_barriers
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from status_schema import STATUS_SCHEMA_VERSION, status_envelope
    from validate_paper_understanding import depth_ids, validate_paper_understanding


COMPONENT = "paper_understanding_runtime_executor"
DEFAULT_BATCH_SIZE = 5
DEFAULT_MAX_ACTIVE_BATCHES = 3
RESULT_SCHEMA_VERSION = 2
VALID_RESULT_STATUSES = {"resolved", "partially_resolved", "blocked"}
CHANGED_ARTIFACTS = ["state/full_text_sources.jsonl", "state/paper_mechanism_cards.jsonl"]
ACCEPTANCE_VALIDATORS = ["validate_paper_understanding", "phase_gate:paper_understanding"]
REQUIRED_RESULT_KEYS = [
    "batch_id",
    "status",
    "paper_ids",
    "full_text_sources",
    "paper_mechanism_cards",
    "artifact_hashes_before",
    "validator_results",
    "unavailable_or_downgrade_candidates",
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


def _stable_hash(value) -> str:
    payload = json.dumps(value or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _jsonl_hash(rows: list[dict]) -> str:
    payload = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _artifact_hash(task_dir: Path, artifact: str) -> str:
    return _sha256_file(task_dir / artifact)


def _ab_citation_rows(citation_plan: list[dict]) -> list[dict]:
    return [
        row for row in citation_plan
        if str(row.get("paper_id") or "").strip()
        and str(row.get("depth") or row.get("level") or "").upper() in {"A", "B"}
    ]


def _valid_completed_ids(cards: list[dict], citation_plan: list[dict], sources: list[dict]) -> set[str]:
    completed: set[str] = set()
    cards_by_id = {str(card.get("paper_id")): card for card in cards if card.get("paper_id")}
    for row in _ab_citation_rows(citation_plan):
        pid = str(row["paper_id"])
        card = cards_by_id.get(pid)
        if not card:
            continue
        status = validate_paper_understanding([card], [row], sources)
        if status.get("valid"):
            completed.add(pid)
    return completed


def _batch_summary(doc: dict) -> dict:
    batches = doc.get("batches") or []
    active_batch_ids = _active_batch_ids(doc)
    active = [batch for batch in batches if batch.get("batch_id") in set(active_batch_ids)]
    pending = [batch for batch in batches if batch.get("status") != "resolved"]
    return {
        "batch_count": len(batches),
        "active_batch_id": active_batch_ids[0] if active_batch_ids else None,
        "active_batch_ids": active_batch_ids,
        "active_paper_ids": [pid for batch in active for pid in batch.get("paper_ids") or []],
        "pending_batch_count": len(pending),
        "resolved_batch_count": len(batches) - len(pending),
        "paper_required_count": int(doc.get("paper_required_count") or 0),
        "paper_completed_count": int(doc.get("paper_completed_count") or 0),
        "batch_size": int(doc.get("batch_size") or DEFAULT_BATCH_SIZE),
        "max_active_batches": int(doc.get("max_active_batches") or DEFAULT_MAX_ACTIVE_BATCHES),
    }


def _with_metadata(doc: dict) -> dict:
    doc = dict(doc or {})
    doc["schema_version"] = STATUS_SCHEMA_VERSION
    doc["summary"] = _batch_summary(doc)
    return doc


def _active_batch_ids(doc: dict) -> list[str]:
    ids = doc.get("active_batch_ids")
    if isinstance(ids, list):
        return [str(item) for item in ids if str(item).strip()]
    active = str(doc.get("active_batch_id") or "").strip()
    return [active] if active else []


def _refresh_batch_statuses(doc: dict, max_active_batches: int | None = None) -> dict:
    max_active = max(1, int(max_active_batches or doc.get("max_active_batches") or DEFAULT_MAX_ACTIVE_BATCHES))
    active_batch_ids: list[str] = []
    for batch in doc.get("batches") or []:
        if batch.get("status") == "resolved":
            continue
        if len(active_batch_ids) < max_active:
            if batch.get("status") in {"blocked_by_upstream", "", None}:
                batch["status"] = "pending_spawn"
            if batch.get("status") == "pending_spawn":
                active_batch_ids.append(str(batch.get("batch_id") or ""))
        else:
            batch["status"] = "blocked_by_upstream"
    active_batch_ids = [item for item in active_batch_ids if item]
    doc["active_batch_ids"] = active_batch_ids
    doc["active_batch_id"] = active_batch_ids[0] if active_batch_ids else None
    doc["max_active_batches"] = max_active
    return doc


def _make_batches(paper_ids: list[str], batch_size: int) -> list[dict]:
    batches = []
    for idx, start in enumerate(range(0, len(paper_ids), batch_size), start=1):
        ids = paper_ids[start:start + batch_size]
        batches.append(
            {
                "batch_id": f"PU{idx:03d}",
                "status": "pending_spawn" if idx == 1 else "blocked_by_upstream",
                "paper_ids": ids,
                "paper_count": len(ids),
                "changed_artifacts": list(CHANGED_ARTIFACTS),
                "acceptance_validators": list(ACCEPTANCE_VALIDATORS),
            }
        )
    return batches


def _batch_prompt(task_dir: Path, batch: dict) -> str:
    return (
        "You are a paper-understanding worker for survey-autoresearch.\n"
        "Do not fabricate full-text access or mechanism-card evidence.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Batch id: {batch.get('batch_id')}\n"
        f"Paper ids: {', '.join(batch.get('paper_ids') or [])}\n"
        "Return one JSON object with keys: batch_id, status, paper_ids, full_text_sources, "
        "paper_mechanism_cards, artifact_hashes_before, validator_results, "
        "unavailable_or_downgrade_candidates, remaining_blockers. For resolved batches, every expected "
        "paper id must have a full-text source record and a mechanism card that passes validate_paper_understanding. "
        "The runtime executor computes artifact_hashes_after after merging the returned JSONL rows."
    )


def _candidate_urls_from_paper(paper: dict) -> list[dict]:
    candidates: list[dict] = []
    arxiv_id = str(paper.get("arxiv_id") or "").strip()
    if arxiv_id:
        candidates.extend(
            [
                {"source_kind": "arxiv_pdf", "url": f"https://arxiv.org/pdf/{arxiv_id}"},
                {"source_kind": "paper_html", "url": f"https://arxiv.org/abs/{arxiv_id}"},
            ]
        )
    for field, kind in [("openreview_url", "openreview_pdf"), ("official_url", "official_pdf_or_html"), ("url", "official_pdf_or_html")]:
        url = str(paper.get(field) or "").strip()
        if url:
            candidates.append({"source_kind": kind, "url": url})
    doi = str(paper.get("doi") or "").strip()
    if doi:
        candidates.append({"source_kind": "publisher_html", "url": f"https://doi.org/{doi}"})
    for source in paper.get("verified_sources") or []:
        if isinstance(source, dict):
            url = str(source.get("url") or source.get("source_url") or "").strip()
            if url:
                candidates.append({"source_kind": str(source.get("source_kind") or source.get("source_type") or "verified_source"), "url": url})
    seen = set()
    deduped = []
    for candidate in candidates:
        url = candidate.get("url")
        if url and url not in seen:
            seen.add(url)
            deduped.append(candidate)
    return deduped


def _paper_records_by_id(task_dir: Path) -> dict[str, dict]:
    return {str(row.get("paper_id")): row for row in read_jsonl(_state(task_dir) / "papers.jsonl") if row.get("paper_id")}


def _fetch_candidates_by_paper(task_dir: Path, paper_records: dict[str, dict]) -> dict[str, list[dict]]:
    planned = {
        str(row.get("paper_id")): row.get("source_candidates") or [
            {"source_kind": "planned_url", "url": url}
            for url in row.get("candidate_urls") or []
        ]
        for row in read_jsonl(_state(task_dir) / "full_text_fetch_plan.jsonl")
        if row.get("paper_id")
    }
    result: dict[str, list[dict]] = {}
    for paper_id, paper in paper_records.items():
        result[paper_id] = planned.get(paper_id) or _candidate_urls_from_paper(paper)
    return result


def _spawn_request(task_dir: Path, batch: dict, paper_records: dict[str, dict], fetch_candidates: dict[str, list[dict]]) -> dict:
    paper_ids = [str(pid) for pid in batch.get("paper_ids") or []]
    return {
        "request_id": f"paper-understanding-{batch.get('batch_id')}",
        "next_action": "spawn_paper_understanding_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "required_result_keys": list(REQUIRED_RESULT_KEYS),
        "batch_id": batch.get("batch_id"),
        "paper_ids": paper_ids,
        "expected_paper_ids": paper_ids,
        "paper_records": [paper_records.get(pid, {"paper_id": pid}) for pid in paper_ids],
        "fetch_candidates_by_paper": {pid: fetch_candidates.get(pid, []) for pid in paper_ids},
        "expected_changed_artifacts": list(CHANGED_ARTIFACTS),
        "acceptance_validators": list(ACCEPTANCE_VALIDATORS),
        "expected_acceptance_validators": list(ACCEPTANCE_VALIDATORS),
        "record_command": f"python3 scripts/paper_understanding_runtime_executor.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>",
        "message": _batch_prompt(task_dir, batch),
        "status": "pending_spawn",
    }


def _write_runtime_action(task_dir: Path, doc: dict) -> dict:
    doc = _with_metadata(doc)
    active_ids = set(_active_batch_ids(doc))
    active = [batch for batch in doc.get("batches") or [] if batch.get("batch_id") in active_ids]
    paper_records = _paper_records_by_id(task_dir)
    fetch_candidates = _fetch_candidates_by_paper(task_dir, paper_records)
    requests = [_spawn_request(task_dir, batch, paper_records, fetch_candidates) for batch in active]
    next_action = "spawn_paper_understanding_agents" if active else "rerun_phase_gate"
    status = "blocked_paper_understanding_agent_spawn_required" if active else "paper_understanding_batches_resolved"
    summary = dict(doc.get("summary") or {})
    summary["spawn_request_count"] = len(requests)
    write_json(_state(task_dir) / "paper_understanding_spawn_requests.json", {"next_action": next_action, "spawn_requests": requests})
    write_json(
        _state(task_dir) / "paper_understanding_runtime_action.json",
        {
            **status_envelope(
                COMPONENT,
                "pending_paper_understanding_runtime" if active else "paper_understanding_batches_resolved",
                next_action=next_action,
                terminal=active is None,
                blocked=active is not None,
                blocked_by_phase="paper_understanding" if active else None,
                active_batch_id=doc.get("active_batch_id"),
                summary=summary,
            ),
            "active_batch_id": doc.get("active_batch_id"),
            "active_batch_ids": _active_batch_ids(doc),
        },
    )
    return {
        **status_envelope(
            COMPONENT,
            status,
            next_action=next_action,
            terminal=active is None,
            blocked=active is not None,
            blocked_by_phase="paper_understanding" if active else None,
            active_batch_id=doc.get("active_batch_id"),
            summary=summary,
        ),
        "spawn_request_count": len(requests),
        "spawn_requests": requests,
        "active_batch_ids": _active_batch_ids(doc),
    }


def prepare_paper_understanding_batches(task_dir: Path, batch_size: int = DEFAULT_BATCH_SIZE, max_active_batches: int = DEFAULT_MAX_ACTIVE_BATCHES) -> dict:
    state = _state(task_dir)
    citation_plan = read_jsonl(state / "citation_plan.jsonl")
    cards = read_jsonl(state / "paper_mechanism_cards.jsonl")
    sources = read_jsonl(state / "full_text_sources.jsonl")
    required_ids = [str(row["paper_id"]) for row in _ab_citation_rows(citation_plan)]
    completed_ids = _valid_completed_ids(cards, citation_plan, sources)
    pending_ids = [pid for pid in required_ids if pid not in completed_ids]
    plan_hash = _stable_hash({"required_ids": required_ids, "batch_size": batch_size, "max_active_batches": max_active_batches})
    existing = read_json(state / "paper_understanding_batches.json")
    if existing.get("plan_hash") == plan_hash and existing.get("batches"):
        doc = _refresh_batch_statuses(existing, max_active_batches)
    else:
        doc = {
            "plan_hash": plan_hash,
            "batch_size": batch_size,
            "max_active_batches": max_active_batches,
            "paper_required_count": len(required_ids),
            "paper_completed_count": len(completed_ids),
            "batches": _make_batches(pending_ids, batch_size),
        }
        doc = _refresh_batch_statuses(doc, max_active_batches)
    doc["paper_required_count"] = len(required_ids)
    doc["paper_completed_count"] = len(completed_ids)
    doc = _with_metadata(doc)
    write_json(state / "paper_understanding_batches.json", doc)
    return _write_runtime_action(task_dir, doc)


def collect_paper_understanding_status(task_dir: Path) -> dict:
    state = _state(task_dir)
    doc = _refresh_batch_statuses(read_json(state / "paper_understanding_batches.json"))
    if not doc.get("batches"):
        return {
            **status_envelope(
                COMPONENT,
                "not_prepared",
                next_action="prepare_paper_understanding_batches",
                terminal=False,
                blocked=True,
                blocked_by_phase="paper_understanding",
                summary={"batch_count": 0, "paper_required_count": 0, "paper_completed_count": 0},
            ),
            "batches": [],
        }
    citation_plan = read_jsonl(state / "citation_plan.jsonl")
    cards = read_jsonl(state / "paper_mechanism_cards.jsonl")
    sources = read_jsonl(state / "full_text_sources.jsonl")
    doc["paper_required_count"] = len(_ab_citation_rows(citation_plan))
    doc["paper_completed_count"] = len(_valid_completed_ids(cards, citation_plan, sources))
    doc = _with_metadata(doc)
    write_json(state / "paper_understanding_batches.json", doc)
    all_resolved = all(batch.get("status") == "resolved" for batch in doc.get("batches") or [])
    return {
        **status_envelope(
            COMPONENT,
            "resolved" if all_resolved else "pending_paper_understanding_runtime",
            next_action="rerun_phase_gate" if all_resolved else "spawn_paper_understanding_agents",
            terminal=all_resolved,
            blocked=not all_resolved,
            blocked_by_phase=None if all_resolved else "paper_understanding",
        active_batch_id=doc.get("active_batch_id"),
            summary=doc.get("summary") or {},
        ),
        "batches": doc.get("batches") or [],
        "all_batches_resolved": all_resolved,
        "active_batch_ids": _active_batch_ids(doc),
    }


def _ids_from_rows(rows: list[dict], key: str = "paper_id") -> list[str]:
    return [
        str(row.get(key) or "").strip()
        for row in rows
        if isinstance(row, dict) and str(row.get(key) or "").strip()
    ]


def _duplicates(values: list[str]) -> bool:
    return len(values) != len(set(values))


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


def _merge_by_paper(existing: list[dict], replacements: list[dict], paper_ids: set[str]) -> list[dict]:
    return [row for row in existing if str(row.get("paper_id") or "") not in paper_ids] + replacements


def _validate_result(task_dir: Path, result: dict, batch: dict, merged_sources: list[dict], merged_cards: list[dict]) -> list[str]:
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
    result_ids = [str(pid) for pid in result.get("paper_ids") or [] if str(pid).strip()]
    result_id_set = set(result_ids)
    if _duplicates(result_ids):
        errors.append("duplicate_batch_paper_ids")
    if expected_ids - result_id_set:
        errors.append("missing_batch_paper_ids")
    if result_id_set - expected_ids:
        errors.append("unknown_batch_paper_ids")
    source_ids = _ids_from_rows(result.get("full_text_sources") or [])
    card_ids = _ids_from_rows(result.get("paper_mechanism_cards") or [])
    if set(source_ids) != expected_ids:
        errors.append("full_text_sources_do_not_cover_batch")
    if set(card_ids) != expected_ids:
        errors.append("mechanism_cards_do_not_cover_batch")
    if _duplicates(source_ids):
        errors.append("duplicate_full_text_source_paper_ids")
    if _duplicates(card_ids):
        errors.append("duplicate_mechanism_card_paper_ids")

    before = result.get("artifact_hashes_before")
    if not isinstance(before, dict):
        errors.append("invalid_artifact_hashes_before")
        before = {}
    for artifact in CHANGED_ARTIFACTS:
        if artifact not in before:
            errors.append("missing_artifact_hashes_before")
        elif str(before.get(artifact) or "") != _artifact_hash(task_dir, artifact):
            errors.append("artifact_hash_before_mismatch")
    expected_after = {
        "state/full_text_sources.jsonl": _jsonl_hash(merged_sources),
        "state/paper_mechanism_cards.jsonl": _jsonl_hash(merged_cards),
    }
    after = result.get("artifact_hashes_after")
    if after is not None:
        if not isinstance(after, dict):
            errors.append("invalid_artifact_hashes_after")
        else:
            for artifact, expected_hash in expected_after.items():
                if artifact in after and str(after.get(artifact) or "") != expected_hash:
                    errors.append("artifact_hash_after_mismatch")

    missing_validators = set(ACCEPTANCE_VALIDATORS) - _passed_validators(result)
    if missing_validators:
        errors.append("missing_acceptance_validators")

    batch_citation = [{"paper_id": pid, "depth": "A"} for pid in sorted(expected_ids)]
    batch_status = validate_paper_understanding(result.get("paper_mechanism_cards") or [], batch_citation, result.get("full_text_sources") or [])
    if not batch_status.get("valid"):
        errors.append("invalid_paper_understanding_batch")
    try:
        phase_status = evaluate_phase_barriers(task_dir, "full")
        if phase_status.get("blocked_by_phase") not in {None, "paper_understanding"}:
            errors.append("upstream_phase_not_ready")
    except Exception:
        pass
    return sorted(set(errors))


def record_paper_understanding_result(task_dir: Path, result: dict, subagent_session_id: str) -> dict:
    state = _state(task_dir)
    doc = _refresh_batch_statuses(read_json(state / "paper_understanding_batches.json"))
    batch_id = str(result.get("batch_id") or "")
    batch = next((item for item in doc.get("batches") or [] if str(item.get("batch_id") or "") == batch_id), None)
    if not batch:
        return {"status": "invalid", "error": "unknown_batch_id"}
    if batch_id not in set(_active_batch_ids(doc)):
        return {"status": "invalid", "error": "batch_blocked_by_upstream"}

    paper_ids = {str(pid) for pid in batch.get("paper_ids") or []}
    existing_sources = read_jsonl(state / "full_text_sources.jsonl")
    existing_cards = read_jsonl(state / "paper_mechanism_cards.jsonl")
    new_sources = result.get("full_text_sources") or []
    new_cards = result.get("paper_mechanism_cards") or []
    merged_sources = _merge_by_paper(existing_sources, new_sources, paper_ids)
    merged_cards = _merge_by_paper(existing_cards, new_cards, paper_ids)
    errors = _validate_result(task_dir, result, batch, merged_sources, merged_cards)
    if errors:
        return {"status": "invalid", "error": "invalid_paper_understanding_result", "errors": errors}

    computed_after = {
        "state/full_text_sources.jsonl": _jsonl_hash(merged_sources),
        "state/paper_mechanism_cards.jsonl": _jsonl_hash(merged_cards),
    }
    row = {**result, "artifact_hashes_after": computed_after, "fresh_context": True, "subagent_session_id": subagent_session_id, "recorded_at": _utc_now()}
    write_jsonl(state / "paper_understanding_results.jsonl", read_jsonl(state / "paper_understanding_results.jsonl") + [row])
    if result.get("status") == "resolved":
        write_jsonl(state / "full_text_sources.jsonl", merged_sources)
        write_jsonl(state / "paper_mechanism_cards.jsonl", merged_cards)
        batch["status"] = "resolved"
        batch["resolved_at"] = row["recorded_at"]
        batch["subagent_session_id"] = subagent_session_id
    else:
        batch["status"] = str(result.get("status"))
    citation_plan = read_jsonl(state / "citation_plan.jsonl")
    doc["paper_required_count"] = len(_ab_citation_rows(citation_plan))
    doc["paper_completed_count"] = len(_valid_completed_ids(read_jsonl(state / "paper_mechanism_cards.jsonl"), citation_plan, read_jsonl(state / "full_text_sources.jsonl")))
    doc = _with_metadata(_refresh_batch_statuses(doc))
    write_json(state / "paper_understanding_batches.json", doc)
    _write_runtime_action(task_dir, doc)
    return {"status": "recorded", "batch_id": batch_id, "next_active_batch_id": doc.get("active_batch_id")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--collect-status", action="store_true")
    parser.add_argument("--record-result", type=Path)
    parser.add_argument("--subagent-session-id")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-active-batches", type=int, default=DEFAULT_MAX_ACTIVE_BATCHES)
    args = parser.parse_args()
    if args.prepare:
        result = prepare_paper_understanding_batches(args.task_dir, args.batch_size, args.max_active_batches)
    elif args.collect_status:
        result = collect_paper_understanding_status(args.task_dir)
    elif args.record_result:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_paper_understanding_result(args.task_dir, json.loads(args.record_result.read_text(encoding="utf-8")), args.subagent_session_id)
    else:
        result = {"status": "invalid", "error": "choose --prepare, --collect-status, or --record-result"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
