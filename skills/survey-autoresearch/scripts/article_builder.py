#!/usr/bin/env python3
"""Prepare and record worker-built survey candidate article artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .render_survey_html import render_survey_html
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .status_schema import status_envelope
    from .validate_article_quality import validate_article_quality
except ImportError:  # pragma: no cover
    from render_survey_html import render_survey_html
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from status_schema import status_envelope
    from validate_article_quality import validate_article_quality


COMPONENT = "article_builder"
RESULT_SCHEMA_VERSION = 1
ACCEPTANCE_VALIDATOR = "validate_article_quality"
VALID_RESULT_STATUSES = {"resolved", "partially_resolved", "blocked"}
REQUIRED_RESULT_KEYS = [
    "batch_id",
    "status",
    "survey_candidate_md",
    "appendix_md",
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


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


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
    return (
        "You are the Article Draft worker for survey-autoresearch.\n"
        "Write the publication-facing survey candidate and appendix from the verified article plan, "
        "argument graph, section evidence plans, claim evidence spans, paper cards, synthesis dossiers, "
        "and related-survey alignment. Do not expose workflow internals, paper IDs, A/B/C labels, gate names, "
        "state-file names, or repair notes in the article body. Use scholarly citations with stable paper/citation keys.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Batch id: {batch_id}\n"
        f"Target: {target}\n"
        f"Task spec:\n{_read_text(_state(task_dir) / 'task_spec.md')}\n"
        f"Article plan:\n{_read_text(_outputs(task_dir) / 'article_plan.md')}\n"
        f"Argument graph:\n{_read_text(_state(task_dir) / 'argument_graph.yml')}\n"
        f"Section evidence plans:\n{json.dumps(read_jsonl(_state(task_dir) / 'section_evidence_plans.jsonl'), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Claim evidence spans:\n{json.dumps(read_jsonl(_state(task_dir) / 'claim_evidence_spans.jsonl'), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Taxonomy alignment:\n{json.dumps(read_jsonl(_state(task_dir) / 'taxonomy_alignment.jsonl'), indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Scenario definitions:\n{_read_text(_state(task_dir) / 'scenario_definitions.yml')}\n"
        f"Method dossiers:\n{json.dumps([json.loads(p.read_text(encoding='utf-8')) for p in sorted((_outputs(task_dir) / 'method_family_dossiers').glob('*.json'))] if (_outputs(task_dir) / 'method_family_dossiers').exists() else [], indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Benchmark dossiers:\n{json.dumps([json.loads(p.read_text(encoding='utf-8')) for p in sorted((_outputs(task_dir) / 'benchmark_dossiers').glob('*.json'))] if (_outputs(task_dir) / 'benchmark_dossiers').exists() else [], indent=2, sort_keys=True, ensure_ascii=False)}\n"
        "Return one strict JSON object with keys: batch_id, status, survey_candidate_md, appendix_md, "
        "validator_results, remaining_blockers. For full target, survey_candidate_md must be a complete "
        "reader-facing article, not notes. It must include related-survey positioning, taxonomy roadmap, "
        "method evolution/timeline, data ecosystem, evaluation protocol matrix, limitations, and conclusion. "
        "appendix_md must contain search/evidence logistics and display/table details. validator_results must "
        "include validate_article_quality: passed only after checking the article-quality contract."
    )


def _spawn_request(task_dir: Path, target: str) -> dict:
    batch_id = "ART001"
    return {
        "request_id": f"article-{batch_id}",
        "request_type": "article",
        "next_action": "spawn_article_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "required_result_keys": list(REQUIRED_RESULT_KEYS),
        "expected_acceptance_validators": [ACCEPTANCE_VALIDATOR],
        "batch_id": batch_id,
        "target": target,
        "record_command": f"python3 scripts/article_builder.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>",
        "message": _prompt(task_dir, batch_id, target),
        "status": "pending_spawn",
    }


def prepare_article_request(task_dir: Path, target: str = "full") -> dict:
    if not (_outputs(task_dir) / "article_plan.md").exists():
        return {
            **status_envelope(
                COMPONENT,
                "blocked_article_plan_required",
                next_action="spawn_argument_agents",
                terminal=False,
                blocked=True,
                blocked_by_phase="argument",
                summary={"target": target},
            ),
            "spawn_requests": [],
        }
    request = _spawn_request(task_dir, target)
    write_json(_state(task_dir) / "article_spawn_requests.json", {"next_action": "spawn_article_agents", "spawn_requests": [request]})
    runtime = {
        **status_envelope(
            COMPONENT,
            "blocked_article_agent_spawn_required",
            next_action="spawn_article_agents",
            terminal=False,
            blocked=True,
            blocked_by_phase="article",
            active_batch_id="ART001",
            summary={"spawn_request_count": 1, "target": target},
        ),
        "spawn_request_count": 1,
        "spawn_requests": [request],
    }
    write_json(_state(task_dir) / "article_runtime_action.json", runtime)
    return runtime


def _validate_result(task_dir: Path, result: dict, target: str) -> tuple[list[str], dict]:
    errors: list[str] = []
    details: dict[str, dict] = {}
    if not isinstance(result, dict):
        return ["result_not_object"], details
    for key in REQUIRED_RESULT_KEYS:
        if key not in result:
            errors.append(f"missing_{key}")
    if str(result.get("batch_id") or "") != "ART001":
        errors.append("batch_id_mismatch")
    if str(result.get("status") or "") not in VALID_RESULT_STATUSES:
        errors.append("invalid_status")
    if result.get("status") != "resolved":
        return sorted(set(errors)), details
    if ACCEPTANCE_VALIDATOR not in _passed_validators(result):
        errors.append("missing_acceptance_validators")

    survey = str(result.get("survey_candidate_md") or "")
    appendix = str(result.get("appendix_md") or "")
    article_status = validate_article_quality(
        survey,
        article_plan=_read_text(_outputs(task_dir) / "article_plan.md"),
        argument_graph=read_json(_state(task_dir) / "argument_graph.yml"),
        claims=read_jsonl(_state(task_dir) / "claim_evidence_spans.jsonl"),
        target=target,
        rendered_artifacts=None,
        expansion_audit=read_jsonl(_state(task_dir) / "expansion_audit.jsonl"),
        draft_text=_read_text(_outputs(task_dir) / "survey_draft.md"),
        legacy_artifacts=[],
        premature_final_artifacts=[p for p in ["outputs/survey.md", "outputs/survey.html"] if (task_dir / p).exists()],
        appendix_text=appendix,
    )
    details["article_quality"] = article_status
    if not article_status.get("valid"):
        errors.extend(f"article_quality:{item}" for item in article_status.get("errors") or [])
    return sorted(set(errors)), details


def record_article_result(task_dir: Path, result: dict, subagent_session_id: str, target: str = "full") -> dict:
    errors, validation = _validate_result(task_dir, result, target)
    if errors:
        return {"status": "invalid", "error": "invalid_article_result", "errors": errors, "validation": validation}
    recorded_at = _utc_now()
    row = {**result, "fresh_context": True, "subagent_session_id": subagent_session_id, "recorded_at": recorded_at}
    write_jsonl(_state(task_dir) / "article_results.jsonl", read_jsonl(_state(task_dir) / "article_results.jsonl") + [row])
    if result.get("status") != "resolved":
        return {"status": "recorded", "batch_id": result.get("batch_id"), "resolved": False}

    outputs = _outputs(task_dir)
    outputs.mkdir(exist_ok=True)
    (outputs / "survey_candidate.md").write_text(str(result.get("survey_candidate_md") or "").rstrip() + "\n", encoding="utf-8")
    (outputs / "appendix.md").write_text(str(result.get("appendix_md") or "").rstrip() + "\n", encoding="utf-8")
    html_path = render_survey_html(task_dir)
    rendered_text = html_path.read_text(encoding="utf-8")
    post_status = validate_article_quality(
        (outputs / "survey_candidate.md").read_text(encoding="utf-8"),
        article_plan=_read_text(outputs / "article_plan.md"),
        argument_graph=read_json(_state(task_dir) / "argument_graph.yml"),
        claims=read_jsonl(_state(task_dir) / "claim_evidence_spans.jsonl"),
        target=target,
        rendered_artifacts=[(str(html_path.relative_to(task_dir)), rendered_text)],
        expansion_audit=read_jsonl(_state(task_dir) / "expansion_audit.jsonl"),
        draft_text=_read_text(outputs / "survey_draft.md"),
        legacy_artifacts=[],
        premature_final_artifacts=[p for p in ["outputs/survey.md", "outputs/survey.html"] if (task_dir / p).exists()],
        appendix_text=(outputs / "appendix.md").read_text(encoding="utf-8"),
    )
    validation["rendered_article_quality"] = post_status
    if not post_status.get("valid"):
        return {"status": "invalid", "error": "invalid_rendered_article", "errors": post_status.get("errors") or [], "validation": validation}
    write_json(
        _state(task_dir) / "article_runtime_action.json",
        status_envelope(
            COMPONENT,
            "article_recorded",
            next_action="rerun_phase_gate",
            terminal=False,
            blocked=False,
            summary={"chars": len(str(result.get("survey_candidate_md") or "")), "html": str(html_path.relative_to(task_dir))},
        ),
    )
    return {"status": "recorded", "batch_id": result.get("batch_id"), "validation": validation}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--record-result", type=Path)
    parser.add_argument("--subagent-session-id", default="")
    args = parser.parse_args()
    if args.prepare:
        result = prepare_article_request(args.task_dir, args.target)
    elif args.record_result:
        result = record_article_result(args.task_dir, json.loads(args.record_result.read_text(encoding="utf-8")), args.subagent_session_id, args.target)
    else:
        result = {"status": "invalid", "error": "choose --prepare or --record-result"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") not in {"invalid"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
