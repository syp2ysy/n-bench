#!/usr/bin/env python3
"""Prepare and record worker-selected survey spine artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .paper_card_store import mirror_paper_cards
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .status_schema import status_envelope
    from .validate_argument_graph import parse_structured_text
    from .validate_related_survey_alignment import validate_related_survey_alignment
except ImportError:  # pragma: no cover
    from paper_card_store import mirror_paper_cards
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from status_schema import status_envelope
    from validate_argument_graph import parse_structured_text
    from validate_related_survey_alignment import validate_related_survey_alignment


COMPONENT = "spine_planner"
RESULT_SCHEMA_VERSION = 1
ACCEPTANCE_VALIDATOR = "validate_spine_plan"
REQUIRED_RESULT_KEYS = [
    "batch_id",
    "status",
    "selected_spine",
    "candidate_taxonomies",
    "spine_decision",
    "section_to_evidence_map",
    "taxonomy_alignment",
    "validator_results",
    "remaining_blockers",
]
VALID_RESULT_STATUSES = {"resolved", "partially_resolved", "blocked"}
REQUIRED_SPINE_PHRASES = [
    "Existing related surveys",
    "Candidate taxonomies",
    "Why this spine",
    "Section-to-evidence",
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
    card_dir = _state(task_dir) / "paper_cards"
    if (not card_dir.exists() or not any(card_dir.glob("*.json"))) and (_state(task_dir) / "paper_mechanism_cards.jsonl").exists():
        mirror_paper_cards(task_dir)
    cards: dict[str, dict] = {}
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
                "limitations": core.get("limitations") or card.get("limitations") or "",
            }
        )
    return summaries


def _taxonomy_names(candidate_taxonomies) -> list[str]:
    value = candidate_taxonomies
    if isinstance(value, dict):
        value = value.get("candidate_taxonomies") or value.get("taxonomies") or []
    if isinstance(value, str):
        value = [value]
    names: list[str] = []
    for item in value or []:
        if isinstance(item, dict):
            name = item.get("name") or item.get("spine") or item.get("title")
        else:
            name = item
        if str(name or "").strip():
            names.append(str(name).strip())
    return names


def _selected_candidate_name(candidate_taxonomies) -> str:
    value = candidate_taxonomies
    if isinstance(value, dict):
        selected = value.get("selected_spine")
        if isinstance(selected, str) and selected.strip():
            return selected.strip()
        if isinstance(selected, dict):
            name = selected.get("name") or selected.get("spine") or selected.get("title")
            if str(name or "").strip():
                return str(name).strip()
        value = value.get("candidate_taxonomies") or value.get("taxonomies") or []
    for item in value or []:
        if isinstance(item, dict) and str(item.get("decision") or "").strip().lower() == "selected":
            return str(item.get("name") or item.get("spine") or item.get("title") or "").strip()
    return ""


def _selected_spine_name(selected_spine) -> str:
    if isinstance(selected_spine, dict):
        return str(selected_spine.get("name") or selected_spine.get("spine") or selected_spine.get("title") or "").strip()
    if isinstance(selected_spine, list):
        return ""
    return str(selected_spine or "").strip()


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


def _paper_ids_in_section_map(section_map) -> set[str]:
    ids: set[str] = set()
    items = []
    if isinstance(section_map, dict):
        items = list(section_map.values())
    elif isinstance(section_map, list):
        items = section_map
    for item in items:
        if isinstance(item, dict):
            for key in ["paper_ids", "supporting_papers", "representative_papers", "evidence_papers"]:
                value = item.get(key) or []
                if isinstance(value, str):
                    value = [value]
                ids.update(str(pid) for pid in value if str(pid).strip())
        elif isinstance(item, str):
            ids.add(item)
    return ids


def validate_spine_plan(
    task_dir: Path,
    target: str = "full",
    *,
    spine_decision: str | None = None,
    selected_spine=None,
    candidate_taxonomies=None,
    section_to_evidence_map=None,
    taxonomy_alignment=None,
) -> dict:
    cards = _load_cards(task_dir)
    tree = _load_structured(_outputs(task_dir) / "knowledge_tree.yml")
    taxonomy = candidate_taxonomies if candidate_taxonomies is not None else _load_structured(_state(task_dir) / "taxonomy_candidates.yml")
    taxonomy_source = taxonomy or tree.get("candidate_taxonomies") or []
    raw_selected = selected_spine if selected_spine is not None else tree.get("selected_spine") or (taxonomy.get("selected_spine") if isinstance(taxonomy, dict) else "")
    selected = _selected_spine_name(raw_selected) or _selected_candidate_name(taxonomy_source)
    candidates = _taxonomy_names(taxonomy_source)
    spine_text = spine_decision if spine_decision is not None else _read_text(_state(task_dir) / "spine_decision.md")
    section_map = section_to_evidence_map if section_to_evidence_map is not None else {}
    alignment = taxonomy_alignment if taxonomy_alignment is not None else read_jsonl(_state(task_dir) / "taxonomy_alignment.jsonl")
    if not isinstance(alignment, list):
        alignment = []
    errors: list[str] = []
    if not tree:
        errors.append("missing_knowledge_tree")
    if not cards:
        errors.append("missing_paper_cards")
    branches = tree.get("branches") or []
    if not isinstance(branches, list) or not branches:
        errors.append("invalid_knowledge_tree_branches")
        branches = []
    if not selected:
        errors.append("missing_selected_spine")
    if not candidates:
        errors.append("missing_candidate_taxonomies")
    elif selected and not any(selected.lower() in candidate.lower() or candidate.lower() in selected.lower() for candidate in candidates):
        errors.append("selected_spine_not_in_candidate_taxonomies")
    for phrase in REQUIRED_SPINE_PHRASES:
        if phrase.lower() not in str(spine_text or "").lower():
            errors.append("spine_decision_missing_" + phrase.lower().replace(" ", "_").replace("-", "_"))
    if target in {"full", "csur"}:
        required = 10 if target == "csur" else 6
        if len(alignment) < required:
            errors.append(f"insufficient_related_survey_alignment:{len(alignment)}/{required}")
    card_ids = set(cards)
    branch_ids = {str(pid) for branch in branches for pid in (branch.get("included_papers") or []) if str(pid).strip()}
    map_ids = _paper_ids_in_section_map(section_map)
    spine_mentions = {paper_id for paper_id in card_ids if paper_id.lower() in str(spine_text or "").lower()}
    trace_ids = (map_ids | spine_mentions | branch_ids) & card_ids
    if card_ids and not trace_ids:
        errors.append("spine_missing_public_paper_card_trace")
    valid = not errors
    return {
        **status_envelope(
            COMPONENT,
            "complete" if valid else "blocked",
            terminal=valid,
            blocked=not valid,
            blocked_by_phase=None if valid else "synthesis",
            summary={
                "candidate_taxonomy_count": len(candidates),
                "selected_spine": selected,
                "paper_card_count": len(cards),
                "related_survey_alignment_count": len(alignment),
                "error_count": len(set(errors)),
            },
        ),
        "valid": valid,
        "errors": sorted(set(errors)),
        "selected_spine": selected,
        "candidate_taxonomies": candidates,
        "trace_paper_ids": sorted(trace_ids),
    }


def _prompt(task_dir: Path, batch_id: str, cards: dict[str, dict]) -> str:
    related_candidates = [
        {
            "paper_id": row.get("paper_id"),
            "candidate_id": row.get("candidate_id"),
            "relevance_grade": row.get("relevance_grade"),
            "allowed_role": row.get("allowed_role"),
            "corrected_family": row.get("corrected_family"),
            "rationale": row.get("rationale"),
        }
        for row in read_jsonl(_state(task_dir) / "topic_relevance_audit.jsonl")
        if row.get("relevance_grade") == "direct_related_survey" and row.get("allowed_role") == "related_survey"
    ]
    papers_by_id = {str(row.get("paper_id")): row for row in read_jsonl(_state(task_dir) / "papers.jsonl") if row.get("paper_id")}
    related_sources = [
        {
            **item,
            "title": papers_by_id.get(str(item.get("paper_id")), {}).get("title"),
            "abstract": papers_by_id.get(str(item.get("paper_id")), {}).get("abstract"),
            "verification_status": papers_by_id.get(str(item.get("paper_id")), {}).get("verification_status"),
            "survey_role": papers_by_id.get(str(item.get("paper_id")), {}).get("survey_role"),
            "verified_source": papers_by_id.get(str(item.get("paper_id")), {}).get("source_candidate_id") or item.get("paper_id"),
        }
        for item in related_candidates
    ]
    return (
        "You are the Survey Spine Planner worker for survey-autoresearch.\n"
        "Choose or repair the article spine from the worker-produced knowledge tree, paper cards, and related-survey taxonomy alignment. "
        "Do not invent papers, related surveys, or taxonomy branches. The spine must be field-native, traceable to paper-card evidence, "
        "and explicitly compare existing related-survey taxonomies with the current corpus.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Batch id: {batch_id}\n"
        f"Task spec:\n{_read_text(_state(task_dir) / 'task_spec.md')}\n"
        f"Topic profile:\n{json.dumps(read_json(_state(task_dir) / 'topic_profile.json'), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Knowledge tree:\n{_read_text(_outputs(task_dir) / 'knowledge_tree.yml')}\n"
        f"Taxonomy candidates:\n{_read_text(_state(task_dir) / 'taxonomy_candidates.yml')}\n"
        f"Existing spine decision:\n{_read_text(_state(task_dir) / 'spine_decision.md')}\n"
        f"Paper-card summaries:\n{json.dumps(_paper_card_summaries(cards), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Related-survey taxonomy alignment:\n{json.dumps(read_jsonl(_state(task_dir) / 'taxonomy_alignment.jsonl'), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Verified direct-related survey candidates from topic audit:\n{json.dumps(related_sources, indent=2, sort_keys=True, ensure_ascii=False)}\n"
        "Return one strict JSON object with keys: batch_id, status, selected_spine, candidate_taxonomies, "
        "spine_decision, section_to_evidence_map, taxonomy_alignment, validator_results, remaining_blockers. "
        "spine_decision must contain the headings or phrases: Existing related surveys, Candidate taxonomies, "
        "Why this spine, and Section-to-evidence. section_to_evidence_map must name public paper IDs from state/paper_cards. "
        "taxonomy_alignment must contain full/CSUR related-survey alignment records using only verified direct-related survey candidates above, "
        "with paper_id, title, survey_type, source_ref or verified_source, existing_taxonomy, section_extractions, taxonomy_evidence, "
        "article_taxonomy_mapping, coverage_overlap, coverage_gap, taxonomy_delta, article_taxonomy_necessity, article_delta, and why_delta_is_justified."
    )


def _spawn_request(task_dir: Path, cards: dict[str, dict]) -> dict:
    batch_id = "SP001"
    return {
        "request_id": f"spine-planner-{batch_id}",
        "request_type": "spine_planner",
        "next_action": "spawn_spine_planner_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "required_result_keys": list(REQUIRED_RESULT_KEYS),
        "expected_acceptance_validators": [ACCEPTANCE_VALIDATOR],
        "batch_id": batch_id,
        "paper_card_count": len(cards),
        "paper_card_ids": sorted(cards),
        "record_command": f"python3 scripts/spine_planner.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>",
        "message": _prompt(task_dir, batch_id, cards),
        "status": "pending_spawn",
    }


def prepare_spine_plan_request(task_dir: Path, target: str = "full") -> dict:
    cards = _load_cards(task_dir)
    tree = _load_structured(_outputs(task_dir) / "knowledge_tree.yml")
    if not tree:
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
    validation = validate_spine_plan(task_dir, target)
    if validation.get("valid"):
        return validation
    request = _spawn_request(task_dir, cards)
    write_json(_state(task_dir) / "spine_planner_spawn_requests.json", {"next_action": "spawn_spine_planner_agents", "spawn_requests": [request]})
    runtime = {
        **status_envelope(
            COMPONENT,
            "blocked_spine_planner_agent_spawn_required",
            next_action="spawn_spine_planner_agents",
            terminal=False,
            blocked=True,
            blocked_by_phase="synthesis",
            active_batch_id="SP001",
            summary={
                "paper_card_count": len(cards),
                "spawn_request_count": 1,
                "target": target,
                "validation_errors": validation.get("errors") or [],
            },
        ),
        "spawn_request_count": 1,
        "spawn_requests": [request],
    }
    write_json(_state(task_dir) / "spine_planner_runtime_action.json", runtime)
    return runtime


def _validate_result(task_dir: Path, result: dict, target: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result_not_object"]
    for key in REQUIRED_RESULT_KEYS:
        if key not in result:
            errors.append(f"missing_{key}")
    if str(result.get("batch_id") or "") != "SP001":
        errors.append("batch_id_mismatch")
    if str(result.get("status") or "") not in VALID_RESULT_STATUSES:
        errors.append("invalid_status")
    if result.get("status") != "resolved":
        return sorted(set(errors))
    if ACCEPTANCE_VALIDATOR not in _passed_validators(result):
        errors.append("missing_acceptance_validators")
    provided = validate_spine_plan(
        task_dir,
        target,
        spine_decision=str(result.get("spine_decision") or ""),
        selected_spine=result.get("selected_spine"),
        candidate_taxonomies=result.get("candidate_taxonomies"),
        section_to_evidence_map=result.get("section_to_evidence_map"),
        taxonomy_alignment=result.get("taxonomy_alignment"),
    )
    errors.extend(provided.get("errors") or [])
    related = validate_related_survey_alignment(
        result.get("taxonomy_alignment") if isinstance(result.get("taxonomy_alignment"), list) else [],
        read_jsonl(_state(task_dir) / "paper_mechanism_cards.jsonl"),
        target,
        papers=read_jsonl(_state(task_dir) / "papers.jsonl"),
        topic_relevance_audit=read_jsonl(_state(task_dir) / "topic_relevance_audit.jsonl"),
        citation_plan=read_jsonl(_state(task_dir) / "citation_plan.jsonl"),
    )
    if not related.get("valid"):
        errors.extend(f"related_survey_alignment:{item}" for item in related.get("errors") or [])
    return sorted(set(errors))


def record_spine_plan_result(task_dir: Path, result: dict, subagent_session_id: str, target: str = "full") -> dict:
    errors = _validate_result(task_dir, result, target)
    if errors:
        return {"status": "invalid", "error": "invalid_spine_plan_result", "errors": errors}
    recorded_at = _utc_now()
    row = {**result, "fresh_context": True, "subagent_session_id": subagent_session_id, "recorded_at": recorded_at}
    write_jsonl(_state(task_dir) / "spine_planner_results.jsonl", read_jsonl(_state(task_dir) / "spine_planner_results.jsonl") + [row])
    if result.get("status") != "resolved":
        return {"status": "recorded", "batch_id": result.get("batch_id"), "resolved": False}
    taxonomy = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "candidate_taxonomies": result.get("candidate_taxonomies") or [],
        "selected_spine": result.get("selected_spine"),
        "source_artifact": "state/spine_decision.md",
        "subagent_session_id": subagent_session_id,
        "recorded_at": recorded_at,
    }
    write_json(_state(task_dir) / "taxonomy_candidates.yml", taxonomy)
    (_state(task_dir) / "spine_decision.md").write_text(str(result.get("spine_decision") or "").rstrip() + "\n", encoding="utf-8")
    write_jsonl(_state(task_dir) / "taxonomy_alignment.jsonl", result.get("taxonomy_alignment") or [])
    tree = _load_structured(_outputs(task_dir) / "knowledge_tree.yml")
    if tree:
        tree["candidate_taxonomies"] = result.get("candidate_taxonomies") or tree.get("candidate_taxonomies") or []
        tree["selected_spine"] = result.get("selected_spine") or tree.get("selected_spine") or ""
        tree["spine_planner_subagent_session_id"] = subagent_session_id
        tree["spine_planner_recorded_at"] = recorded_at
        write_json(_outputs(task_dir) / "knowledge_tree.yml", tree)
    validation = validate_spine_plan(task_dir, target)
    if not validation.get("valid"):
        return {"status": "invalid", "error": "recorded_spine_plan_failed_validation", "validation": validation}
    write_json(
        _state(task_dir) / "spine_planner_runtime_action.json",
        status_envelope(
            COMPONENT,
            "spine_plan_recorded",
            next_action="rerun_phase_gate",
            terminal=False,
            blocked=False,
            summary={"selected_spine": validation.get("selected_spine"), "trace_paper_ids": validation.get("trace_paper_ids")},
        ),
    )
    return {"status": "recorded", "batch_id": result.get("batch_id"), "validation": validation}


def collect_status(task_dir: Path, target: str = "full") -> dict:
    validation = validate_spine_plan(task_dir, target)
    if validation.get("valid"):
        return validation
    runtime = read_json(_state(task_dir) / "spine_planner_runtime_action.json")
    if runtime:
        return {**runtime, "validation": validation}
    return validation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--collect-status", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--record-result", type=Path)
    parser.add_argument("--subagent-session-id")
    args = parser.parse_args()
    if args.prepare:
        result = prepare_spine_plan_request(args.task_dir, args.target)
    elif args.collect_status:
        result = collect_status(args.task_dir, args.target)
    elif args.validate:
        result = validate_spine_plan(args.task_dir, args.target)
    elif args.record_result:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_spine_plan_result(
                args.task_dir,
                json.loads(args.record_result.read_text(encoding="utf-8")),
                args.subagent_session_id,
                args.target,
            )
    else:
        result = {"component": COMPONENT, "status": "invalid", "error": "choose --prepare, --collect-status, --validate, or --record-result"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
