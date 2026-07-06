#!/usr/bin/env python3
"""Prepare and record worker-built argument and section-planning artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .status_schema import status_envelope
    from .validate_argument_graph import parse_structured_text, validate_argument_graph
    from .validate_claim_evidence import validate_claim_evidence
    from .validate_exemplar_alignment import validate_exemplar_alignment
    from .validate_section_evidence_plans import validate_section_evidence_plans
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from status_schema import status_envelope
    from validate_argument_graph import parse_structured_text, validate_argument_graph
    from validate_claim_evidence import validate_claim_evidence
    from validate_exemplar_alignment import validate_exemplar_alignment
    from validate_section_evidence_plans import validate_section_evidence_plans


COMPONENT = "argument_builder"
RESULT_SCHEMA_VERSION = 1
ACCEPTANCE_VALIDATOR = "validate_argument_plan"
VALID_RESULT_STATUSES = {"resolved", "partially_resolved", "blocked"}
REQUIRED_RESULT_KEYS = [
    "batch_id",
    "status",
    "survey_type_plan",
    "argument_graph",
    "article_plan",
    "claim_evidence_spans",
    "section_evidence_plans",
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


def _as_text(value) -> str:
    if isinstance(value, str):
        return value.rstrip() + "\n"
    return json.dumps(value or {}, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _load_structured(path: Path) -> dict:
    if not path.exists():
        return {}
    parsed = parse_structured_text(path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _argument_graph_with_preserved_synthesis_linkage(task_dir: Path, result_graph) -> dict:
    existing = _load_structured(_state(task_dir) / "argument_graph.yml")
    graph = dict(existing)
    if isinstance(result_graph, dict):
        graph.update(result_graph)
    if not graph.get("contribution_tree") and (_outputs(task_dir) / "contribution_tree.yml").exists():
        graph["contribution_tree"] = "outputs/contribution_tree.yml"
    if not graph.get("candidate_spines_from_contribution_tree") and existing.get("candidate_spines_from_contribution_tree"):
        graph["candidate_spines_from_contribution_tree"] = existing.get("candidate_spines_from_contribution_tree")
    return graph


def _load_cards(task_dir: Path) -> list[dict]:
    return read_jsonl(_state(task_dir) / "paper_mechanism_cards.jsonl")


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


def _prompt(task_dir: Path, batch_id: str, target: str) -> str:
    cards = _load_cards(task_dir)
    card_summaries = []
    for card in cards:
        card_summaries.append(
            {
                "paper_id": card.get("paper_id"),
                "title": card.get("title") or (card.get("identity") or {}).get("title"),
                "one_sentence_contribution": card.get("one_sentence_contribution") or (card.get("survey_use") or {}).get("one_sentence_contribution"),
                "possible_sections": card.get("possible_sections") or (card.get("survey_use") or {}).get("possible_sections"),
                "supports_claims": card.get("supports_claims") or (card.get("survey_use") or {}).get("supports_claims"),
                "method_pipeline": card.get("method_pipeline"),
                "benchmark_or_dataset": card.get("benchmark_or_dataset"),
                "main_results": card.get("main_results"),
                "field_evidence_map": card.get("field_evidence_map"),
            }
        )
    return (
        "You are the Argument Plan worker for survey-autoresearch.\n"
        "Build the claim evidence, article plan, section evidence plan, and exemplar-aligned survey type plan from verified synthesis artifacts. "
        "Do not invent papers, evidence spans, benchmarks, or claims. Every claim must cite captured full-text evidence from paper cards/full-text sources.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Batch id: {batch_id}\n"
        f"Target: {target}\n"
        f"Task spec:\n{_read_text(_state(task_dir) / 'task_spec.md')}\n"
        f"Topic profile:\n{json.dumps(read_json(_state(task_dir) / 'topic_profile.json'), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Knowledge tree:\n{_read_text(_outputs(task_dir) / 'knowledge_tree.yml')}\n"
        f"Spine decision:\n{_read_text(_state(task_dir) / 'spine_decision.md')}\n"
        f"Taxonomy alignment:\n{json.dumps(read_jsonl(_state(task_dir) / 'taxonomy_alignment.jsonl'), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Scenario definitions:\n{_read_text(_state(task_dir) / 'scenario_definitions.yml')}\n"
        f"Method dossiers:\n{json.dumps([json.loads(p.read_text(encoding='utf-8')) for p in sorted((_outputs(task_dir) / 'method_family_dossiers').glob('*.json'))] if (_outputs(task_dir) / 'method_family_dossiers').exists() else [], indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Benchmark dossiers:\n{json.dumps([json.loads(p.read_text(encoding='utf-8')) for p in sorted((_outputs(task_dir) / 'benchmark_dossiers').glob('*.json'))] if (_outputs(task_dir) / 'benchmark_dossiers').exists() else [], indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Paper-card summaries:\n{json.dumps(card_summaries, indent=2, sort_keys=True, ensure_ascii=False)}\n"
        "Return one strict JSON object with keys: batch_id, status, survey_type_plan, argument_graph, article_plan, "
        "claim_evidence_spans, section_evidence_plans, validator_results, remaining_blockers. "
        "survey_type_plan must include exemplar_alignment, community_native_taxonomy, exemplar_section_patterns, candidate_article_spines, "
        "selected_article_spine, why_not_exemplar_spine, figure_first_plan, science_paradigm_profile, evidence_norms, required_evidence_units, common_confounders. "
        "article_plan must include Article Body, Article Displays, Appendix, and Internal sections, with taxonomy roadmap, method evolution/timeline, data ecosystem, and evaluation protocol matrix. "
        "section_evidence_plans must cover every article body section and cite claim ids from claim_evidence_spans. "
        "validator_results must include validate_argument_plan: passed only after checking the validator contracts."
    )


def _spawn_request(task_dir: Path, target: str) -> dict:
    batch_id = "ARG001"
    cards = _load_cards(task_dir)
    return {
        "request_id": f"argument-{batch_id}",
        "request_type": "argument",
        "next_action": "spawn_argument_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "required_result_keys": list(REQUIRED_RESULT_KEYS),
        "expected_acceptance_validators": [ACCEPTANCE_VALIDATOR],
        "batch_id": batch_id,
        "paper_card_count": len(cards),
        "record_command": f"python3 scripts/argument_builder.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>",
        "message": _prompt(task_dir, batch_id, target),
        "status": "pending_spawn",
    }


def prepare_argument_request(task_dir: Path, target: str = "full") -> dict:
    if not _load_cards(task_dir):
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
    request = _spawn_request(task_dir, target)
    write_json(_state(task_dir) / "argument_spawn_requests.json", {"next_action": "spawn_argument_agents", "spawn_requests": [request]})
    runtime = {
        **status_envelope(
            COMPONENT,
            "blocked_argument_agent_spawn_required",
            next_action="spawn_argument_agents",
            terminal=False,
            blocked=True,
            blocked_by_phase="argument",
            active_batch_id="ARG001",
            summary={"paper_card_count": len(_load_cards(task_dir)), "spawn_request_count": 1, "target": target},
        ),
        "spawn_request_count": 1,
        "spawn_requests": [request],
    }
    write_json(_state(task_dir) / "argument_runtime_action.json", runtime)
    return runtime


def _validate_result(task_dir: Path, result: dict, target: str) -> tuple[list[str], dict]:
    errors: list[str] = []
    details: dict[str, dict] = {}
    if not isinstance(result, dict):
        return ["result_not_object"], details
    for key in REQUIRED_RESULT_KEYS:
        if key not in result:
            errors.append(f"missing_{key}")
    if str(result.get("batch_id") or "") != "ARG001":
        errors.append("batch_id_mismatch")
    if str(result.get("status") or "") not in VALID_RESULT_STATUSES:
        errors.append("invalid_status")
    if result.get("status") != "resolved":
        return sorted(set(errors)), details
    if ACCEPTANCE_VALIDATOR not in _passed_validators(result):
        errors.append("missing_acceptance_validators")

    cards = _load_cards(task_dir)
    claims = _as_list(result.get("claim_evidence_spans"))
    section_plans = _as_list(result.get("section_evidence_plans"))
    survey_type_plan = _as_text(result.get("survey_type_plan"))
    article_plan = str(result.get("article_plan") or "")
    graph = _argument_graph_with_preserved_synthesis_linkage(task_dir, result.get("argument_graph"))

    claim_status = validate_claim_evidence(claims, cards, section_plans if target != "short" else None, full_text_sources=read_jsonl(_state(task_dir) / "full_text_sources.jsonl"))
    details["claim_evidence"] = claim_status
    if not claim_status.get("valid"):
        errors.extend(f"claim_evidence:{item}" for item in claim_status.get("errors") or [])
    argument_status = validate_argument_graph(graph, article_plan)
    details["argument_graph"] = argument_status
    if not argument_status.get("valid"):
        errors.extend(f"argument_graph:{item}" for item in argument_status.get("errors") or [])
    exemplar_status = validate_exemplar_alignment(
        survey_type_plan,
        graph,
        article_plan,
        target,
        read_jsonl(_state(task_dir) / "taxonomy_alignment.jsonl"),
        cards,
    )
    details["exemplar_alignment"] = exemplar_status
    if not exemplar_status.get("valid"):
        errors.extend(f"exemplar_alignment:{item}" for item in exemplar_status.get("errors") or [])
    section_status = validate_section_evidence_plans(section_plans, graph, article_plan, claims, cards, target)
    details["section_evidence_plans"] = section_status
    if not section_status.get("valid"):
        errors.extend(f"section_evidence_plans:{item}" for item in section_status.get("errors") or [])
    return sorted(set(errors)), details


def record_argument_result(task_dir: Path, result: dict, subagent_session_id: str, target: str = "full") -> dict:
    errors, validation = _validate_result(task_dir, result, target)
    if errors:
        return {"status": "invalid", "error": "invalid_argument_result", "errors": errors, "validation": validation}
    recorded_at = _utc_now()
    row = {**result, "fresh_context": True, "subagent_session_id": subagent_session_id, "recorded_at": recorded_at}
    write_jsonl(_state(task_dir) / "argument_results.jsonl", read_jsonl(_state(task_dir) / "argument_results.jsonl") + [row])
    if result.get("status") != "resolved":
        return {"status": "recorded", "batch_id": result.get("batch_id"), "resolved": False}

    (_state(task_dir) / "survey_type_plan.yml").write_text(_as_text(result.get("survey_type_plan")), encoding="utf-8")
    write_json(_state(task_dir) / "argument_graph.yml", _argument_graph_with_preserved_synthesis_linkage(task_dir, result.get("argument_graph")))
    (_outputs(task_dir) / "article_plan.md").write_text(str(result.get("article_plan") or "").rstrip() + "\n", encoding="utf-8")
    write_jsonl(_state(task_dir) / "claim_evidence_spans.jsonl", _as_list(result.get("claim_evidence_spans")))
    write_jsonl(_state(task_dir) / "section_evidence_plans.jsonl", _as_list(result.get("section_evidence_plans")))
    write_json(
        _state(task_dir) / "argument_runtime_action.json",
        status_envelope(
            COMPONENT,
            "argument_recorded",
            next_action="rerun_phase_gate",
            terminal=False,
            blocked=False,
            summary={
                "claim_count": len(_as_list(result.get("claim_evidence_spans"))),
                "section_plan_count": len(_as_list(result.get("section_evidence_plans"))),
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
        result = prepare_argument_request(args.task_dir, args.target)
    elif args.record_result:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_argument_result(args.task_dir, json.loads(args.record_result.read_text(encoding="utf-8")), args.subagent_session_id, args.target)
    else:
        result = {"component": COMPONENT, "status": "invalid", "error": "choose --prepare or --record-result"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
