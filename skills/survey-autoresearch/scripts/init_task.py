#!/usr/bin/env python3
"""Initialize persistent state for a survey-autoresearch run."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


STATE_FILES = [
    "raw_candidates.jsonl",
    "papers.jsonl",
    "lqs_scores.jsonl",
    "citation_plan.jsonl",
    "paper_mechanism_cards.jsonl",
    "claim_evidence_spans.jsonl",
    "section_evidence_plans.jsonl",
    "expert_review_reports.jsonl",
    "weakness_routes.jsonl",
    "review_rounds.jsonl",
    "phase_summaries.jsonl",
]

LOG_FILES = [
    "orchestrator.jsonl",
    "heartbeat.jsonl",
    "search.jsonl",
    "verification.jsonl",
    "synthesis.jsonl",
]

OUTPUT_FILES = {
    "review.md": "",
    "review_body_draft.md": "",
    "article_plan.md": "",
    "appendix.md": "",
    "coverage_matrix.md": "",
    "related_survey_matrix.md": "",
    "references.bib": "",
    "final_report.md": "",
    "figures_plan.md": "",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "survey-task"


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def initialize_task(
    base_dir: Path,
    topic: str,
    slug: str | None = None,
    output_mode: str = "markdown",
    target: str = "short",
) -> Path:
    task_slug = slug or slugify(topic)
    task_dir = base_dir / task_slug
    state = task_dir / "state"
    logs = task_dir / "logs"
    outputs = task_dir / "outputs"
    state.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    now = utc_now()
    (state / "task_spec.md").write_text(
        f"# Task Spec\n\nTopic: {topic}\nTarget: {target}\nOutput mode: {output_mode}\n",
        encoding="utf-8",
    )
    (state / "survey_type_plan.yml").write_text("", encoding="utf-8")
    (state / "scenario_definitions.yml").write_text("", encoding="utf-8")
    (state / "argument_graph.yml").write_text("", encoding="utf-8")
    (state / "search_protocol.md").write_text("", encoding="utf-8")
    (state / "csur_notes.md").write_text("", encoding="utf-8")
    write_json(
        state / "progress.json",
        {
            "created_at": now,
            "updated_at": now,
            "last_seen": now,
            "status": "running",
            "iteration": 0,
            "phase": "phase_0_task_lock",
            "topic": topic,
            "target": target,
            "next_action": "write survey_type_plan.yml and start high-recall discovery",
        },
    )
    write_json(state / "heartbeat.json", {"last_seen": now, "source": "init_task"})
    write_json(
        state / "completion_gates.json",
        {
            "gate_1_source_identity": False,
            "gate_2_paper_understanding": False,
            "gate_3_claim_evidence": False,
            "gate_4_coverage": False,
            "gate_5_argument_graph": False,
            "gate_6_article_quality": False,
            "gate_7_expert_review": False,
            "final_review_status": False,
        },
    )
    write_json(
        state / "review_iteration_status.json",
        {
            "round": 0,
            "last_median_score": None,
            "previous_median_score": None,
            "status": "not_reviewed",
        },
    )
    for filename in STATE_FILES:
        (state / filename).touch()
    for filename in LOG_FILES:
        (logs / filename).touch()
    for filename, content in OUTPUT_FILES.items():
        (outputs / filename).write_text(content, encoding="utf-8")
    (outputs / "method_family_dossiers").mkdir(exist_ok=True)
    (outputs / "benchmark_dossiers").mkdir(exist_ok=True)
    (outputs / "risk_dossiers").mkdir(exist_ok=True)
    (outputs / "application_dossiers").mkdir(exist_ok=True)

    with (logs / "orchestrator.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": now, "event": "task_initialized", "topic": topic}, sort_keys=True) + "\n")
    return task_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", required=True, type=Path)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--output-mode", default="markdown")
    parser.add_argument("--target", choices=["short", "full", "csur"], default="short")
    args = parser.parse_args()
    print(initialize_task(args.base_dir, args.topic, args.slug, args.output_mode, args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
