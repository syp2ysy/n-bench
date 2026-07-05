#!/usr/bin/env python3
"""Public facade for A/B full-text paper reading and card recording."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .full_text_source_planner import build_full_text_fetch_plan
    from .paper_card_store import mirror_paper_cards, validate_paper_card_store
    from .paper_understanding_runtime_executor import (
        collect_paper_understanding_status,
        prepare_paper_understanding_batches,
        record_paper_understanding_result,
    )
    from .phase_gate import PHASE_ORDER, evaluate_phase_barriers
    from .run_expert_reviews import read_json, read_jsonl, write_json
    from .status_schema import status_envelope
except ImportError:  # pragma: no cover
    from full_text_source_planner import build_full_text_fetch_plan
    from paper_card_store import mirror_paper_cards, validate_paper_card_store
    from paper_understanding_runtime_executor import (
        collect_paper_understanding_status,
        prepare_paper_understanding_batches,
        record_paper_understanding_result,
    )
    from phase_gate import PHASE_ORDER, evaluate_phase_barriers
    from run_expert_reviews import read_json, read_jsonl, write_json
    from status_schema import status_envelope


COMPONENT = "paper_reader"
PAPER_PHASE = "paper_understanding"


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _ab_ids(task_dir: Path) -> list[str]:
    rows = read_jsonl(_state(task_dir) / "citation_plan.jsonl")
    return [
        str(row.get("paper_id") or "").strip()
        for row in rows
        if str(row.get("paper_id") or "").strip()
        and str(row.get("depth") or row.get("level") or "").upper() in {"A", "B"}
    ]


def _phase_index(phase: str | None) -> int:
    if phase in PHASE_ORDER:
        return PHASE_ORDER.index(str(phase))
    return len(PHASE_ORDER)


def _source_blocker(task_dir: Path, target: str, allow_source_repair_gap: bool = False) -> dict | None:
    phase = evaluate_phase_barriers(task_dir, target)
    blocked_by = phase.get("blocked_by_phase")
    if allow_source_repair_gap and _ab_ids(task_dir):
        return None
    if blocked_by and _phase_index(str(blocked_by)) < _phase_index(PAPER_PHASE):
        return {
            **status_envelope(
                COMPONENT,
                "blocked_source_verification_required",
                next_action=phase.get("allowed_next_phase") or phase.get("next_action"),
                terminal=False,
                blocked=True,
                blocked_by_phase=blocked_by,
                summary={
                    "target": target,
                    "blocked_before_paper_reader": blocked_by,
                    "allowed_next_phase": phase.get("allowed_next_phase"),
                },
            ),
            "phase_status": phase,
        }
    if not _ab_ids(task_dir):
        return {
            **status_envelope(
                COMPONENT,
                "blocked_citation_plan_required",
                next_action="repair_source_verification",
                terminal=False,
                blocked=True,
                blocked_by_phase="source_verification",
                summary={"target": target, "ab_paper_count": 0},
            ),
            "phase_status": phase,
        }
    return None


def _rewrite_record_commands(task_dir: Path) -> None:
    path = _state(task_dir) / "paper_understanding_spawn_requests.json"
    doc = read_json(path)
    requests = doc.get("spawn_requests")
    if not isinstance(requests, list):
        return
    for request in requests:
        if not isinstance(request, dict):
            continue
        request["legacy_record_command"] = request.get("record_command")
        request["record_command"] = (
            f"python3 scripts/paper_reader.py --task-dir {task_dir.resolve()} "
            "--record-result <result.json> --subagent-session-id <subagent-session-id>"
        )
    write_json(path, doc)


def _card_summary(task_dir: Path) -> dict:
    card_status = validate_paper_card_store(task_dir)
    return {
        "public_card_valid": bool(card_status.get("valid")),
        "public_card_required_count": (card_status.get("summary") or {}).get("required_count", 0),
        "public_card_missing_count": (card_status.get("summary") or {}).get("missing_count", 0),
        "public_card_invalid_count": (card_status.get("summary") or {}).get("invalid_count", 0),
    }


def _with_public_status(task_dir: Path, result: dict, target: str, fetch_plan: dict | None = None) -> dict:
    summary = dict(result.get("summary") or {})
    summary.update(_card_summary(task_dir))
    if fetch_plan:
        summary["full_text_fetch_plan"] = fetch_plan.get("summary") or {}
    return {
        **result,
        "component": COMPONENT,
        "legacy_component": result.get("component"),
        "target": target,
        "summary": summary,
        "public_card_store": "state/paper_cards",
        "compatibility_sources": ["state/full_text_sources.jsonl", "state/paper_mechanism_cards.jsonl"],
    }


def prepare_paper_reading(
    task_dir: Path,
    target: str = "full",
    batch_size: int = 5,
    max_active_batches: int = 3,
    allow_source_repair_gap: bool = False,
) -> dict:
    """Prepare paper-reading worker tasks without fabricating full-text evidence."""
    blocker = _source_blocker(task_dir, target, allow_source_repair_gap)
    if blocker:
        return blocker
    fetch_plan = build_full_text_fetch_plan(task_dir)
    result = prepare_paper_understanding_batches(task_dir, batch_size, max_active_batches)
    _rewrite_record_commands(task_dir)
    return _with_public_status(task_dir, result, target, fetch_plan)


def collect_status(task_dir: Path, target: str = "full") -> dict:
    blocker = _source_blocker(task_dir, target)
    if blocker:
        return blocker
    result = collect_paper_understanding_status(task_dir)
    if (task_dir / "state" / "paper_mechanism_cards.jsonl").exists():
        mirror_paper_cards(task_dir)
    return _with_public_status(task_dir, result, target)


def record_result(task_dir: Path, result: dict, subagent_session_id: str, target: str = "full") -> dict:
    recorded = record_paper_understanding_result(task_dir, result, subagent_session_id)
    if recorded.get("status") == "recorded":
        mirror_paper_cards(task_dir)
    return _with_public_status(task_dir, recorded, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--collect-status", action="store_true")
    parser.add_argument("--record-result", type=Path)
    parser.add_argument("--subagent-session-id")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--max-active-batches", type=int, default=3)
    args = parser.parse_args()
    if args.prepare:
        output = prepare_paper_reading(args.task_dir, args.target, args.batch_size, args.max_active_batches)
    elif args.collect_status:
        output = collect_status(args.task_dir, args.target)
    elif args.record_result:
        if not args.subagent_session_id:
            output = {"component": COMPONENT, "status": "invalid", "error": "missing_subagent_session_id"}
        else:
            payload = json.loads(args.record_result.read_text(encoding="utf-8"))
            output = record_result(args.task_dir, payload, args.subagent_session_id, args.target)
    else:
        output = {"component": COMPONENT, "status": "invalid", "error": "choose --prepare, --collect-status, or --record-result"}
    print(json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if output.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
