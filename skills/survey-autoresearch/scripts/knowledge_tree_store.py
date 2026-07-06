#!/usr/bin/env python3
"""Mirror worker-produced synthesis into public knowledge-tree artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_jsonl, write_json, write_jsonl
    from .status_schema import status_envelope
    from .validate_argument_graph import parse_structured_text
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_jsonl, write_json, write_jsonl
    from status_schema import status_envelope
    from validate_argument_graph import parse_structured_text


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _safe_id(value: object) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or "").strip()) or "unknown"


def _load_public_cards(task_dir: Path) -> dict[str, dict]:
    cards: dict[str, dict] = {}
    card_dir = task_dir / "state" / "paper_cards"
    if not card_dir.exists():
        return cards
    for path in sorted(card_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        paper_id = str(data.get("paper_id") or path.stem)
        cards[paper_id] = data
    return cards


def _paper_ids(branch: dict) -> list[str]:
    ids = []
    for key in ["representative_papers", "supporting_papers", "included_papers"]:
        value = branch.get(key) or []
        if isinstance(value, str):
            value = [value]
        ids.extend(str(item) for item in value if str(item).strip())
    return sorted(set(ids))


def _branch_from_legacy(branch: dict, cards: dict[str, dict]) -> dict:
    paper_ids = _paper_ids(branch)
    evidence = []
    for paper_id in paper_ids:
        card = cards.get(paper_id) or {}
        survey_use = card.get("survey_use") or {}
        evidence.append(
            {
                "paper_id": paper_id,
                "has_public_card": paper_id in cards,
                "changes_knowledge_tree": survey_use.get("changes_knowledge_tree") or "",
                "one_sentence_contribution": survey_use.get("one_sentence_contribution") or "",
            }
        )
    return {
        "name": branch.get("name"),
        "definition": branch.get("motivation") or branch.get("definition") or "",
        "included_papers": paper_ids,
        "representative_papers": branch.get("representative_papers") or [],
        "excluded_nearby_topics": branch.get("excluded_nearby_topics") or [],
        "shared_assumptions_or_boundaries": branch.get("core_tradeoff") or "",
        "evidence_standard": branch.get("evidence_standard") or "",
        "failure_modes": branch.get("failure_risks") or [],
        "related_survey_delta": branch.get("related_survey_delta") or "",
        "paper_card_evidence": evidence,
    }


def _legacy_tree(task_dir: Path) -> dict:
    outputs = task_dir / "outputs"
    public_tree = outputs / "knowledge_tree.yml"
    if public_tree.exists() and public_tree.read_text(encoding="utf-8").strip():
        parsed = parse_structured_text(_text(public_tree))
        if isinstance(parsed, dict) and parsed:
            return parsed
    return parse_structured_text(_text(outputs / "contribution_tree.yml")) or {}


def _is_worker_native_tree(tree: dict) -> bool:
    if not isinstance(tree, dict) or not tree.get("branches"):
        return False
    if tree.get("builder_kind") == "mirror_from_worker_synthesis":
        return False
    return bool(tree.get("candidate_taxonomies") or tree.get("selected_spine") or tree.get("subagent_session_id"))


def _sync_from_public_tree(task_dir: Path, tree: dict, cards: dict[str, dict]) -> dict:
    state = task_dir / "state"
    branches = tree.get("branches") or []
    if not isinstance(branches, list):
        branches = []
    clusters = [
        {
            "cluster_id": f"KT{idx:03d}",
            "name": branch.get("name"),
            "paper_ids": branch.get("included_papers") or [],
            "source_artifact": "outputs/knowledge_tree.yml",
        }
        for idx, branch in enumerate(branches, start=1)
        if isinstance(branch, dict)
    ]
    write_jsonl(state / "paper_clusters.jsonl", clusters)
    write_json(
        state / "taxonomy_candidates.yml",
        {
            "schema_version": 1,
            "candidate_taxonomies": tree.get("candidate_taxonomies") or [],
            "selected_spine": tree.get("selected_spine") or "",
            "source_artifact": "outputs/knowledge_tree.yml",
        },
    )
    spine_path = state / "spine_decision.md"
    existing_spine = _text(spine_path)
    if not existing_spine.strip() or "Selected spine: not selected" in existing_spine:
        spine = [
            "# Spine Decision",
            "",
            f"Selected spine: {tree.get('selected_spine') or 'not selected'}",
            "",
            "Existing related surveys organize the topic through the related-survey taxonomy alignment recorded in state/taxonomy_alignment.jsonl.",
            "",
            "Candidate taxonomies considered:",
        ]
        for candidate in tree.get("candidate_taxonomies") or []:
            spine.append(f"- {candidate}")
        spine.extend(
            [
                "",
                "Why this spine is better for the current corpus:",
                tree.get("root_claim") or "The selected spine must be justified by the worker-produced knowledge tree.",
                "",
                "Section-to-evidence map:",
            ]
        )
        for branch in branches:
            if isinstance(branch, dict):
                spine.append(f"- {branch.get('name')}: {', '.join(branch.get('included_papers') or [])}")
        spine_path.write_text("\n".join(spine) + "\n", encoding="utf-8")
    return {
        **status_envelope(
            "knowledge_tree_store",
            "mirrored",
            terminal=False,
            blocked=False,
            summary={"branch_count": len(clusters), "paper_card_count": len(cards), "mode": "preserved_public_tree"},
        ),
        "branch_count": len(clusters),
        "paper_card_count": len(cards),
        "mode": "preserved_public_tree",
    }


def mirror_knowledge_tree(task_dir: Path) -> dict:
    state = task_dir / "state"
    outputs = task_dir / "outputs"
    cards = _load_public_cards(task_dir)
    public_tree = parse_structured_text(_text(outputs / "knowledge_tree.yml")) or {}
    if _is_worker_native_tree(public_tree):
        return _sync_from_public_tree(task_dir, public_tree, cards)
    legacy = _legacy_tree(task_dir)
    branches = legacy.get("branches") or []
    if not isinstance(branches, list):
        branches = []
    public_branches = [_branch_from_legacy(branch, cards) for branch in branches if isinstance(branch, dict)]
    tree = {
        "schema_version": 1,
        "builder_kind": "mirror_from_worker_synthesis",
        "source_artifact": "outputs/contribution_tree.yml",
        "root_claim": legacy.get("root_claim") or "",
        "branches": public_branches,
        "candidate_taxonomies": legacy.get("candidate_article_spines") or [],
        "selected_spine": legacy.get("selected_article_spine") or "",
        "mirrored_at": _utc_now(),
    }
    write_json(outputs / "knowledge_tree.yml", tree)
    clusters = [
        {
            "cluster_id": f"KT{idx:03d}",
            "name": branch.get("name"),
            "paper_ids": branch.get("included_papers") or [],
            "source_artifact": "outputs/knowledge_tree.yml",
        }
        for idx, branch in enumerate(public_branches, start=1)
    ]
    write_jsonl(state / "paper_clusters.jsonl", clusters)
    write_json(
        state / "taxonomy_candidates.yml",
        {
            "schema_version": 1,
            "candidate_taxonomies": legacy.get("candidate_article_spines") or [],
            "selected_spine": legacy.get("selected_article_spine") or "",
            "source_artifact": "outputs/knowledge_tree.yml",
        },
    )
    spine = [
        "# Spine Decision",
        "",
        f"Selected spine: {legacy.get('selected_article_spine') or 'not selected'}",
        "",
        "Existing related surveys organize the topic through the related-survey taxonomy alignment recorded in state/taxonomy_alignment.jsonl.",
        "",
        "Candidate taxonomies considered:",
    ]
    for candidate in legacy.get("candidate_article_spines") or []:
        spine.append(f"- {candidate}")
    spine.extend(
        [
            "",
            "Why this spine is better for the current corpus:",
            legacy.get("root_claim") or "The selected spine must be justified by the worker-produced knowledge tree.",
            "",
            "Section-to-evidence map:",
        ]
    )
    for branch in public_branches:
        spine.append(f"- {branch.get('name')}: {', '.join(branch.get('included_papers') or [])}")
    (state / "spine_decision.md").write_text("\n".join(spine) + "\n", encoding="utf-8")
    return {
        **status_envelope(
            "knowledge_tree_store",
            "mirrored",
            terminal=False,
            blocked=False,
            summary={"branch_count": len(public_branches), "paper_card_count": len(cards)},
        ),
        "branch_count": len(public_branches),
        "paper_card_count": len(cards),
    }


def validate_knowledge_tree_store(task_dir: Path) -> dict:
    outputs = task_dir / "outputs"
    state = task_dir / "state"
    cards = _load_public_cards(task_dir)
    tree = parse_structured_text(_text(outputs / "knowledge_tree.yml")) or {}
    clusters = read_jsonl(state / "paper_clusters.jsonl")
    spine = _text(state / "spine_decision.md")
    errors: list[str] = []
    invalid_branches: dict[str, list[str]] = {}
    if not tree:
        errors.append("missing_knowledge_tree")
    if not clusters:
        errors.append("missing_paper_clusters")
    if not spine.strip():
        errors.append("missing_spine_decision")
    branches = tree.get("branches") or []
    if not isinstance(branches, list) or not branches:
        errors.append("invalid_knowledge_tree_branches")
        branches = []
    paper_ids_with_cards = sorted(cards)
    for branch in branches:
        name = str((branch or {}).get("name") or "<missing>")
        branch_errors = []
        for field in ["name", "definition", "included_papers", "shared_assumptions_or_boundaries", "evidence_standard", "failure_modes"]:
            if not (branch or {}).get(field):
                branch_errors.append(f"missing_{field}")
        unknown = [paper_id for paper_id in (branch or {}).get("included_papers") or [] if paper_id not in cards]
        if unknown:
            branch_errors.append("missing_public_paper_cards:" + ",".join(unknown))
        if branch_errors:
            invalid_branches[name] = branch_errors
    for phrase in ["Existing related surveys", "Candidate taxonomies", "Why this spine", "Section-to-evidence"]:
        if phrase.lower() not in spine.lower():
            errors.append("spine_decision_missing_" + _safe_id(phrase).lower())
    if invalid_branches:
        errors.append("invalid_knowledge_tree_branch_traceability")
    valid = not errors
    return {
        **status_envelope(
            "knowledge_tree_store",
            "complete" if valid else "blocked",
            terminal=valid,
            blocked=not valid,
            blocked_by_phase=None if valid else "synthesis",
            summary={"branch_count": len(branches), "paper_card_count": len(cards), "error_count": len(set(errors))},
        ),
        "valid": valid,
        "errors": sorted(set(errors)),
        "invalid_branches": invalid_branches,
        "paper_ids_with_cards": paper_ids_with_cards,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--mirror", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.validate:
        result = validate_knowledge_tree_store(args.task_dir)
    else:
        result = mirror_knowledge_tree(args.task_dir)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("valid", True) or result.get("status") == "mirrored" else 1


if __name__ == "__main__":
    raise SystemExit(main())
