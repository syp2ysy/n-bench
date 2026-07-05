#!/usr/bin/env python3
"""Single facade for phase and release gate evaluation.

The legacy CLIs remain available, but new orchestration code should call this
module so phase and final-release decisions share one public truth source.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .gate_check import evaluate_gates
    from .phase_gate import PHASE_ORDER, evaluate_phase_barriers
    from .status_schema import STATUS_SCHEMA_VERSION, status_envelope
except ImportError:  # pragma: no cover
    from gate_check import evaluate_gates
    from phase_gate import PHASE_ORDER, evaluate_phase_barriers
    from status_schema import STATUS_SCHEMA_VERSION, status_envelope


def evaluate_all(task_dir: Path, target: str = "full") -> dict:
    """Evaluate all phase barriers and final release gates."""
    phase_status = evaluate_phase_barriers(task_dir, target)
    gates = evaluate_gates(task_dir, target)
    status = "complete" if gates.get("all_blocking_gates_passed") else "blocked"
    return {
        **status_envelope(
            "gate_engine",
            status,
            next_action=gates.get("allowed_next_phase") or phase_status.get("allowed_next_phase"),
            terminal=bool(gates.get("survey_complete")),
            blocked=not bool(gates.get("all_blocking_gates_passed")),
            blocked_by_phase=gates.get("blocked_by_phase") or phase_status.get("blocked_by_phase"),
            summary={
                "target": target,
                "all_required_phases_passed": phase_status.get("all_required_phases_passed"),
                "all_blocking_gates_passed": gates.get("all_blocking_gates_passed"),
                "release_allowed": gates.get("release_allowed"),
                "completion_level": gates.get("completion_level"),
            },
        ),
        "target": target,
        "phase_barriers": phase_status,
        "gates": gates,
        "all_blocking_gates_passed": bool(gates.get("all_blocking_gates_passed")),
        "release_allowed": bool(gates.get("release_allowed")),
        "survey_complete": bool(gates.get("survey_complete")),
    }


def evaluate_phase(task_dir: Path, target: str, phase: str) -> dict:
    """Evaluate one named phase through the shared phase engine."""
    phase_status = evaluate_phase_barriers(task_dir, target)
    details = dict((phase_status.get("phases") or {}).get(phase) or {})
    return {
        **status_envelope(
            "gate_engine",
            "complete" if details.get("passed") else "blocked",
            next_action=phase_status.get("allowed_next_phase"),
            terminal=bool(details.get("passed")),
            blocked=not bool(details.get("passed")),
            blocked_by_phase=None if details.get("passed") else phase,
            summary={
                "target": target,
                "phase": phase,
                "phase_order": PHASE_ORDER,
            },
        ),
        "target": target,
        "phase": phase,
        **details,
    }


def _errors_from_details(details: dict) -> list[str]:
    errors: list[str] = []
    nested = [details]
    nested.extend(value for value in details.values() if isinstance(value, dict))
    for item in nested:
        for key in ["errors", "missing", "discovery_missing", "retained_missing", "source_missing"]:
            value = item.get(key)
            if isinstance(value, list):
                errors.extend(str(entry) for entry in value if str(entry).strip())
    return sorted(set(errors))


def _recommended_commands(task_dir: Path, target: str, allowed_next_phase: str | None) -> list[str]:
    task = str(task_dir)
    commands = [
        f"python3 scripts/runner.py --task-dir {task} --target {target} --run-until-complete",
    ]
    if allowed_next_phase in {
        "topic_profile",
        "discovery",
        "topic_relevance_audit",
        "topic_relevance_second_audit",
        "paper_understanding",
        "spawn_expert_reviewers",
        "repair_with_evidence_check",
        "targeted_rereview",
    }:
        commands.append(f"python3 scripts/task_queue.py --task-dir {task} --collect-pending")
    commands.append(f"python3 scripts/gate_engine.py --task-dir {task} --target {target} --explain")
    return commands


def explain_blocker(task_dir: Path, target: str = "full") -> dict:
    """Return a compact explanation of the current blocking gate and next public action."""
    phase_status = evaluate_phase_barriers(task_dir, target)
    gates = evaluate_gates(task_dir, target)
    blocked_by = gates.get("blocked_by_phase") or phase_status.get("blocked_by_phase")
    allowed_next = gates.get("allowed_next_phase") or phase_status.get("allowed_next_phase")
    details = dict((phase_status.get("phases") or {}).get(blocked_by) or {})
    errors = _errors_from_details(details)
    status = "complete" if not blocked_by and gates.get("all_blocking_gates_passed") else "blocked"
    return {
        **status_envelope(
            "gate_engine",
            status,
            next_action=allowed_next,
            terminal=status == "complete",
            blocked=status != "complete",
            blocked_by_phase=blocked_by,
            summary={
                "target": target,
                "allowed_next_phase": allowed_next,
                "validator": details.get("validator"),
                "error_count": len(errors),
            },
        ),
        "target": target,
        "allowed_next_phase": allowed_next,
        "validator": details.get("validator"),
        "errors": errors,
        "details": details.get("details") or details,
        "recommended_commands": _recommended_commands(task_dir, target, allowed_next),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--phase", choices=PHASE_ORDER)
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.explain:
        result = explain_blocker(args.task_dir, args.target)
    else:
        result = evaluate_phase(args.task_dir, args.target, args.phase) if args.phase else evaluate_all(args.task_dir, args.target)
    result["schema_version"] = STATUS_SCHEMA_VERSION
    text = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result.get("status") == "complete" or result.get("all_blocking_gates_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
