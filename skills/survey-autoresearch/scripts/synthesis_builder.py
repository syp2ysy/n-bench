#!/usr/bin/env python3
"""Prepare and record worker-built synthesis artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .build_contribution_tree import validate_contribution_tree
    from .paper_card_store import mirror_paper_cards
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .status_schema import status_envelope
    from .validate_argument_graph import parse_structured_text
    from .validate_scenario_definitions import validate_scenario_definitions
    from .validate_synthesis_dossiers import validate_synthesis_dossiers
except ImportError:  # pragma: no cover
    from build_contribution_tree import validate_contribution_tree
    from paper_card_store import mirror_paper_cards
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from status_schema import status_envelope
    from validate_argument_graph import parse_structured_text
    from validate_scenario_definitions import validate_scenario_definitions
    from validate_synthesis_dossiers import validate_synthesis_dossiers


COMPONENT = "synthesis_builder"
RESULT_SCHEMA_VERSION = 1
ACCEPTANCE_VALIDATOR = "validate_synthesis_artifacts"
VALID_RESULT_STATUSES = {"resolved", "partially_resolved", "blocked"}
REQUIRED_RESULT_KEYS = [
    "batch_id",
    "status",
    "paper_contribution_statements",
    "scenario_definitions",
    "method_family_dossiers",
    "benchmark_dossiers",
    "comparative_evidence_matrix",
    "argument_graph",
    "validator_results",
    "remaining_blockers",
]


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _outputs(task_dir: Path) -> Path:
    return task_dir / "outputs"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_structured(path: Path) -> dict:
    parsed = parse_structured_text(_read_text(path))
    return parsed if isinstance(parsed, dict) else {}


def _load_cards(task_dir: Path) -> dict[str, dict]:
    cards: dict[str, dict] = {}
    for row in read_jsonl(_state(task_dir) / "paper_mechanism_cards.jsonl"):
        paper_id = str(row.get("paper_id") or "")
        if paper_id:
            cards[paper_id] = row
    if cards:
        return cards
    card_dir = _state(task_dir) / "paper_cards"
    if (not card_dir.exists() or not any(card_dir.glob("*.json"))) and (_state(task_dir) / "paper_mechanism_cards.jsonl").exists():
        mirror_paper_cards(task_dir)
    for path in sorted(card_dir.glob("*.json")) if card_dir.exists() else []:
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        paper_id = str(card.get("paper_id") or path.stem)
        if paper_id:
            cards[paper_id] = card
    return cards


def _paper_card_summaries(cards: dict[str, dict]) -> list[dict]:
    summaries = []
    for paper_id, card in sorted(cards.items()):
        survey_use = card.get("survey_use") or {}
        core = card.get("core_understanding") or {}
        summaries.append(
            {
                "paper_id": paper_id,
                "title": (card.get("identity") or {}).get("title") or card.get("title") or "",
                "one_sentence_contribution": survey_use.get("one_sentence_contribution") or "",
                "changes_knowledge_tree": survey_use.get("changes_knowledge_tree") or "",
                "possible_sections": survey_use.get("possible_sections") or [],
                "supports_claims": survey_use.get("supports_claims") or [],
                "problem": core.get("problem") or card.get("problem") or "",
                "method_pipeline": core.get("method_pipeline") or card.get("method_pipeline") or "",
                "benchmark_or_dataset": card.get("benchmark_or_dataset") or core.get("benchmark_or_dataset") or [],
                "main_results": card.get("main_results") or core.get("main_results") or [],
                "limitations": core.get("limitations") or card.get("limitations") or card.get("limitations_and_confounders") or "",
            }
        )
    return summaries


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


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    return []


def _scenario_text(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value if isinstance(value, dict) else {"scenarios": value or []}, ensure_ascii=False, sort_keys=True)


def _argument_graph_with_linkage(task_dir: Path, result_graph) -> dict:
    existing = _load_structured(_state(task_dir) / "argument_graph.yml")
    graph = dict(existing)
    if isinstance(result_graph, dict):
        graph.update(result_graph)
    return graph


def _write_json_files(directory: Path, rows: list[dict], key: str) -> None:
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for idx, row in enumerate(rows, start=1):
        name = str(row.get(key) or row.get("name") or f"item_{idx:03d}").strip().lower()
        safe = "".join(ch if ch.isalnum() else "_" for ch in name).strip("_") or f"item_{idx:03d}"
        write_json(directory / f"{safe}.json", row)


def _prompt(task_dir: Path, batch_id: str, cards: dict[str, dict]) -> str:
    return (
        "You are the Synthesis Artifacts worker for survey-autoresearch.\n"
        "Use the already verified paper cards and worker-built knowledge tree to build synthesis artifacts. "
        "Do not invent papers, benchmarks, or results. Every paper contribution statement, scenario, dossier, "
        "and comparative matrix row must be grounded in paper-card/full-text evidence.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Batch id: {batch_id}\n"
        f"Task spec:\n{_read_text(_state(task_dir) / 'task_spec.md')}\n"
        f"Topic profile:\n{json.dumps(read_json(_state(task_dir) / 'topic_profile.json'), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Knowledge tree:\n{_read_text(_outputs(task_dir) / 'knowledge_tree.yml')}\n"
        f"Contribution tree compatibility artifact:\n{_read_text(_outputs(task_dir) / 'contribution_tree.yml')}\n"
        f"Spine decision:\n{_read_text(_state(task_dir) / 'spine_decision.md')}\n"
        f"Paper-card summaries:\n{json.dumps(_paper_card_summaries(cards), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        "Return one strict JSON object with keys: batch_id, status, paper_contribution_statements, "
        "scenario_definitions, method_family_dossiers, benchmark_dossiers, comparative_evidence_matrix, "
        "argument_graph, validator_results, remaining_blockers. "
        "paper_contribution_statements must cover every A/B paper in state/citation_plan.jsonl. "
        "argument_graph must include non-empty contribution_tree and candidate_spines_from_contribution_tree fields. "
        "validator_results must include validate_synthesis_artifacts: passed only after you checked the validator contract."
    )


def _spawn_request(task_dir: Path, cards: dict[str, dict]) -> dict:
    batch_id = "SY001"
    return {
        "request_id": f"synthesis-{batch_id}",
        "request_type": "synthesis",
        "next_action": "spawn_synthesis_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "required_result_keys": list(REQUIRED_RESULT_KEYS),
        "expected_acceptance_validators": [ACCEPTANCE_VALIDATOR],
        "batch_id": batch_id,
        "paper_card_count": len(cards),
        "paper_card_ids": sorted(cards),
        "record_command": f"python3 scripts/synthesis_builder.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>",
        "message": _prompt(task_dir, batch_id, cards),
        "status": "pending_spawn",
    }


def prepare_synthesis_request(task_dir: Path, target: str = "full") -> dict:
    cards = _load_cards(task_dir)
    if not cards:
        return {
            **status_envelope(
                COMPONENT,
                "blocked_paper_cards_required",
                next_action="spawn_paper_understanding_agents",
                terminal=False,
                blocked=True,
                blocked_by_phase="paper_understanding",
                summary={"target": target},
            ),
            "spawn_requests": [],
        }
    if not _load_structured(_outputs(task_dir) / "knowledge_tree.yml"):
        return {
            **status_envelope(
                COMPONENT,
                "blocked_knowledge_tree_required",
                next_action="spawn_knowledge_tree_agents",
                terminal=False,
                blocked=True,
                blocked_by_phase="synthesis",
                summary={"target": target},
            ),
            "spawn_requests": [],
        }
    request = _spawn_request(task_dir, cards)
    write_json(_state(task_dir) / "synthesis_spawn_requests.json", {"next_action": "spawn_synthesis_agents", "spawn_requests": [request]})
    runtime = {
        **status_envelope(
            COMPONENT,
            "blocked_synthesis_agent_spawn_required",
            next_action="spawn_synthesis_agents",
            terminal=False,
            blocked=True,
            blocked_by_phase="synthesis",
            active_batch_id="SY001",
            summary={"paper_card_count": len(cards), "spawn_request_count": 1, "target": target},
        ),
        "spawn_request_count": 1,
        "spawn_requests": [request],
    }
    write_json(_state(task_dir) / "synthesis_runtime_action.json", runtime)
    return runtime


def _validate_result(task_dir: Path, result: dict, target: str, cards: dict[str, dict]) -> tuple[list[str], dict]:
    errors: list[str] = []
    details: dict[str, dict] = {}
    if not isinstance(result, dict):
        return ["result_not_object"], details
    for key in REQUIRED_RESULT_KEYS:
        if key not in result:
            errors.append(f"missing_{key}")
    if str(result.get("batch_id") or "") != "SY001":
        errors.append("batch_id_mismatch")
    if str(result.get("status") or "") not in VALID_RESULT_STATUSES:
        errors.append("invalid_status")
    if result.get("status") != "resolved":
        return sorted(set(errors)), details
    if ACCEPTANCE_VALIDATOR not in _passed_validators(result):
        errors.append("missing_acceptance_validators")

    statements = _as_list(result.get("paper_contribution_statements"))
    scenarios = result.get("scenario_definitions")
    methods = _as_list(result.get("method_family_dossiers"))
    benchmarks = _as_list(result.get("benchmark_dossiers"))
    matrix = _as_list(result.get("comparative_evidence_matrix"))
    graph = _argument_graph_with_linkage(task_dir, result.get("argument_graph"))

    contribution = validate_contribution_tree(
        statements,
        _read_text(_outputs(task_dir) / "contribution_tree.yml"),
        read_jsonl(_state(task_dir) / "citation_plan.jsonl"),
        graph,
        target,
    )
    details["contribution_tree"] = contribution
    if not contribution.get("valid"):
        errors.extend(f"contribution_tree:{item}" for item in contribution.get("errors") or [])
    scenario = validate_scenario_definitions(_scenario_text(scenarios), target, list(cards.values()))
    details["scenario_definitions"] = scenario
    if not scenario.get("valid"):
        errors.extend(f"scenario_definitions:{item}" for item in scenario.get("errors") or [])
    synthesis = validate_synthesis_dossiers(methods, benchmarks, _scenario_text(scenarios), list(cards.values()), target, matrix)
    details["synthesis_dossiers"] = synthesis
    if not synthesis.get("valid"):
        errors.extend(f"synthesis_dossiers:{item}" for item in synthesis.get("errors") or [])
    return sorted(set(errors)), details


def record_synthesis_result(task_dir: Path, result: dict, subagent_session_id: str, target: str = "full") -> dict:
    cards = _load_cards(task_dir)
    if not cards:
        return {"status": "invalid", "error": "missing_paper_cards"}
    errors, validation = _validate_result(task_dir, result, target, cards)
    if errors:
        return {"status": "invalid", "error": "invalid_synthesis_result", "errors": errors, "validation": validation}
    recorded_at = _utc_now()
    row = {**result, "fresh_context": True, "subagent_session_id": subagent_session_id, "recorded_at": recorded_at}
    write_jsonl(_state(task_dir) / "synthesis_results.jsonl", read_jsonl(_state(task_dir) / "synthesis_results.jsonl") + [row])
    if result.get("status") != "resolved":
        return {"status": "recorded", "batch_id": result.get("batch_id"), "resolved": False}

    write_jsonl(_state(task_dir) / "paper_contribution_statements.jsonl", _as_list(result.get("paper_contribution_statements")))
    (_state(task_dir) / "scenario_definitions.yml").write_text(_scenario_text(result.get("scenario_definitions")).rstrip() + "\n", encoding="utf-8")
    write_jsonl(_state(task_dir) / "comparative_evidence_matrix.jsonl", _as_list(result.get("comparative_evidence_matrix")))
    _write_json_files(_outputs(task_dir) / "method_family_dossiers", _as_list(result.get("method_family_dossiers")), "family")
    _write_json_files(_outputs(task_dir) / "benchmark_dossiers", _as_list(result.get("benchmark_dossiers")), "benchmark")
    write_json(_state(task_dir) / "argument_graph.yml", _argument_graph_with_linkage(task_dir, result.get("argument_graph")))
    write_json(
        _state(task_dir) / "synthesis_runtime_action.json",
        status_envelope(
            COMPONENT,
            "synthesis_recorded",
            next_action="rerun_phase_gate",
            terminal=False,
            blocked=False,
            summary={
                "paper_contribution_statement_count": len(_as_list(result.get("paper_contribution_statements"))),
                "scenario_count": len((result.get("scenario_definitions") or {}).get("scenarios") or [] if isinstance(result.get("scenario_definitions"), dict) else []),
                "method_dossier_count": len(_as_list(result.get("method_family_dossiers"))),
                "benchmark_dossier_count": len(_as_list(result.get("benchmark_dossiers"))),
            },
        ),
    )
    return {"status": "recorded", "batch_id": result.get("batch_id"), "validation": validation}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--record-result", type=Path)
    parser.add_argument("--subagent-session-id")
    args = parser.parse_args()
    if args.prepare:
        result = prepare_synthesis_request(args.task_dir, args.target)
    elif args.record_result:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_synthesis_result(args.task_dir, json.loads(args.record_result.read_text(encoding="utf-8")), args.subagent_session_id, args.target)
    else:
        result = {"component": COMPONENT, "status": "invalid", "error": "choose --prepare or --record-result"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
