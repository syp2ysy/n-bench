#!/usr/bin/env python3
"""Prepare and record worker-built knowledge tree and survey spine artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .knowledge_tree_store import validate_knowledge_tree_store
    from .paper_card_store import mirror_paper_cards
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .status_schema import status_envelope
except ImportError:  # pragma: no cover
    from knowledge_tree_store import validate_knowledge_tree_store
    from paper_card_store import mirror_paper_cards
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from status_schema import status_envelope


COMPONENT = "knowledge_tree_builder"
RESULT_SCHEMA_VERSION = 1
REQUIRED_RESULT_KEYS = [
    "batch_id",
    "status",
    "knowledge_tree",
    "paper_clusters",
    "taxonomy_candidates",
    "spine_decision",
    "validator_results",
    "remaining_blockers",
]
VALID_RESULT_STATUSES = {"resolved", "partially_resolved", "blocked"}
ACCEPTANCE_VALIDATOR = "validate_knowledge_tree"


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _outputs(task_dir: Path) -> Path:
    return task_dir / "outputs"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_cards(task_dir: Path) -> dict[str, dict]:
    card_dir = _state(task_dir) / "paper_cards"
    has_public_cards = card_dir.exists() and any(card_dir.glob("*.json"))
    if not has_public_cards and (_state(task_dir) / "paper_mechanism_cards.jsonl").exists():
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


def _prompt(task_dir: Path, batch_id: str, cards: dict[str, dict]) -> str:
    return (
        "You are the Knowledge Tree and Survey Spine worker for survey-autoresearch.\n"
        "Build the knowledge tree from public paper cards and related-survey taxonomy evidence. "
        "Do not invent papers, clusters, or taxonomy choices; every branch must trace to paper cards.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Batch id: {batch_id}\n"
        f"Task spec:\n{_read_text(_state(task_dir) / 'task_spec.md')}\n"
        f"Topic profile:\n{json.dumps(read_json(_state(task_dir) / 'topic_profile.json'), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Paper-card summaries:\n{json.dumps(_paper_card_summaries(cards), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Related-survey taxonomy alignment:\n{json.dumps(read_jsonl(_state(task_dir) / 'taxonomy_alignment.jsonl'), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        "Return one JSON object with keys: batch_id, status, knowledge_tree, paper_clusters, "
        "taxonomy_candidates, spine_decision, validator_results, remaining_blockers. "
        "knowledge_tree must contain root_claim, branches, candidate_taxonomies, and selected_spine. "
        "Each branch must include name, definition, included_papers, representative_papers, "
        "shared_assumptions_or_boundaries, evidence_standard, failure_modes, and related_survey_delta. "
        "spine_decision must explain existing related surveys, candidate taxonomies, why this spine, and a section-to-evidence map."
    )


def _spawn_request(task_dir: Path, cards: dict[str, dict]) -> dict:
    batch_id = "KT001"
    return {
        "request_id": f"knowledge-tree-{batch_id}",
        "request_type": "knowledge_tree",
        "next_action": "spawn_knowledge_tree_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "required_result_keys": list(REQUIRED_RESULT_KEYS),
        "batch_id": batch_id,
        "paper_card_count": len(cards),
        "paper_card_ids": sorted(cards),
        "record_command": f"python3 scripts/knowledge_tree_builder.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>",
        "message": _prompt(task_dir, batch_id, cards),
        "status": "pending_spawn",
    }


def prepare_knowledge_tree_request(task_dir: Path, target: str = "full") -> dict:
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
                summary={"paper_card_count": 0, "target": target},
            ),
            "spawn_requests": [],
        }
    request = _spawn_request(task_dir, cards)
    write_json(_state(task_dir) / "knowledge_tree_spawn_requests.json", {"next_action": "spawn_knowledge_tree_agents", "spawn_requests": [request]})
    runtime = {
        **status_envelope(
            COMPONENT,
            "blocked_knowledge_tree_agent_spawn_required",
            next_action="spawn_knowledge_tree_agents",
            terminal=False,
            blocked=True,
            blocked_by_phase="synthesis",
            active_batch_id="KT001",
            summary={"paper_card_count": len(cards), "spawn_request_count": 1, "target": target},
        ),
        "spawn_request_count": 1,
        "spawn_requests": [request],
    }
    write_json(_state(task_dir) / "knowledge_tree_runtime_action.json", runtime)
    return runtime


def _branch_errors(tree: dict, cards: dict[str, dict]) -> dict[str, list[str]]:
    invalid: dict[str, list[str]] = {}
    branches = tree.get("branches") or []
    if not isinstance(branches, list):
        return {"<branches>": ["invalid_branches"]}
    for branch in branches:
        name = str((branch or {}).get("name") or "<missing>")
        errors = []
        for field in [
            "name",
            "definition",
            "included_papers",
            "representative_papers",
            "shared_assumptions_or_boundaries",
            "evidence_standard",
            "failure_modes",
            "related_survey_delta",
        ]:
            if not (branch or {}).get(field):
                errors.append(f"missing_{field}")
        unknown = [str(pid) for pid in (branch or {}).get("included_papers") or [] if str(pid) not in cards]
        if unknown:
            errors.append("unknown_included_papers:" + ",".join(sorted(unknown)))
        if errors:
            invalid[name] = errors
    return invalid


def _validate_result(task_dir: Path, result: dict, cards: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result_not_object"]
    for key in REQUIRED_RESULT_KEYS:
        if key not in result:
            errors.append(f"missing_{key}")
    if str(result.get("batch_id") or "") != "KT001":
        errors.append("batch_id_mismatch")
    if str(result.get("status") or "") not in VALID_RESULT_STATUSES:
        errors.append("invalid_status")
    if result.get("status") != "resolved":
        return sorted(set(errors))
    tree = result.get("knowledge_tree")
    if not isinstance(tree, dict):
        errors.append("invalid_knowledge_tree")
        tree = {}
    if not tree.get("root_claim"):
        errors.append("missing_root_claim")
    if not tree.get("branches"):
        errors.append("missing_branches")
    if not tree.get("candidate_taxonomies"):
        errors.append("missing_candidate_taxonomies")
    if not tree.get("selected_spine"):
        errors.append("missing_selected_spine")
    if _branch_errors(tree, cards):
        errors.append("invalid_knowledge_tree_branch_traceability")
    if not isinstance(result.get("paper_clusters"), list) or not result.get("paper_clusters"):
        errors.append("missing_paper_clusters")
    if not result.get("taxonomy_candidates"):
        errors.append("missing_taxonomy_candidates")
    spine = str(result.get("spine_decision") or "")
    for phrase in ["Existing related surveys", "Candidate taxonomies", "Why this spine", "Section-to-evidence"]:
        if phrase.lower() not in spine.lower():
            errors.append("spine_decision_missing_" + phrase.lower().replace(" ", "_").replace("-", "_"))
    if ACCEPTANCE_VALIDATOR not in _passed_validators(result):
        errors.append("missing_acceptance_validators")
    return sorted(set(errors))


def _compat_contribution_tree(tree: dict) -> dict:
    branches = []
    for branch in tree.get("branches") or []:
        branches.append(
            {
                "name": branch.get("name"),
                "motivation": branch.get("definition") or branch.get("motivation") or "",
                "representative_papers": branch.get("representative_papers") or branch.get("included_papers") or [],
                "core_tradeoff": branch.get("shared_assumptions_or_boundaries") or "",
                "evidence_standard": branch.get("evidence_standard") or "",
                "failure_risks": branch.get("failure_modes") or [],
                "related_survey_delta": branch.get("related_survey_delta") or "",
            }
        )
    return {
        "root_claim": tree.get("root_claim") or "",
        "candidate_article_spines": tree.get("candidate_taxonomies") or [],
        "selected_article_spine": tree.get("selected_spine") or "",
        "branches": branches,
    }


def record_knowledge_tree_result(task_dir: Path, result: dict, subagent_session_id: str) -> dict:
    cards = _load_cards(task_dir)
    if not cards:
        return {"status": "invalid", "error": "missing_paper_cards"}
    errors = _validate_result(task_dir, result, cards)
    if errors:
        return {"status": "invalid", "error": "invalid_knowledge_tree_result", "errors": errors}
    recorded_at = _utc_now()
    row = {**result, "fresh_context": True, "subagent_session_id": subagent_session_id, "recorded_at": recorded_at}
    write_jsonl(_state(task_dir) / "knowledge_tree_results.jsonl", read_jsonl(_state(task_dir) / "knowledge_tree_results.jsonl") + [row])
    if result.get("status") != "resolved":
        return {"status": "recorded", "batch_id": result.get("batch_id"), "resolved": False}
    tree = dict(result.get("knowledge_tree") or {})
    tree.setdefault("schema_version", RESULT_SCHEMA_VERSION)
    tree["fresh_context"] = True
    tree["subagent_session_id"] = subagent_session_id
    tree["recorded_at"] = recorded_at
    write_json(_outputs(task_dir) / "knowledge_tree.yml", tree)
    write_json(_outputs(task_dir) / "contribution_tree.yml", _compat_contribution_tree(tree))
    write_jsonl(_state(task_dir) / "paper_clusters.jsonl", result.get("paper_clusters") or [])
    taxonomy = result.get("taxonomy_candidates")
    write_json(_state(task_dir) / "taxonomy_candidates.yml", taxonomy if isinstance(taxonomy, dict) else {"candidate_taxonomies": taxonomy})
    (_state(task_dir) / "spine_decision.md").write_text(str(result.get("spine_decision") or "").rstrip() + "\n", encoding="utf-8")
    validation = validate_knowledge_tree_store(task_dir)
    if not validation.get("valid"):
        return {"status": "invalid", "error": "recorded_knowledge_tree_failed_validation", "validation": validation}
    write_json(
        _state(task_dir) / "knowledge_tree_runtime_action.json",
        status_envelope(
            COMPONENT,
            "knowledge_tree_recorded",
            next_action="rerun_phase_gate",
            terminal=False,
            blocked=False,
            summary={"branch_count": validation.get("summary", {}).get("branch_count"), "paper_card_count": len(cards)},
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
        result = prepare_knowledge_tree_request(args.task_dir, args.target)
    elif args.record_result:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_knowledge_tree_result(args.task_dir, json.loads(args.record_result.read_text(encoding="utf-8")), args.subagent_session_id)
    else:
        result = {"component": COMPONENT, "status": "invalid", "error": "choose --prepare or --record-result"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
