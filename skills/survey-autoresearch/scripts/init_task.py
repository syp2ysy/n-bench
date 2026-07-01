#!/usr/bin/env python3
"""Initialize persistent state for a survey-autoresearch run."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


STATE_FILES = [
    "papers.jsonl",
    "lqs_scores.jsonl",
    "citation_plan.jsonl",
    "claims.jsonl",
    "claim_evidence_spans.jsonl",
    "paper_mechanism_cards.jsonl",
    "paper_cards.jsonl",
    "system_node_cards.jsonl",
    "section_cards.jsonl",
    "review_rounds.jsonl",
    "phase_summaries.jsonl",
    "agent_rounds.jsonl",
    "merge_decisions.jsonl",
    "disagreements.jsonl",
]

LOG_FILES = [
    "orchestrator.jsonl",
    "heartbeat.jsonl",
    "search.jsonl",
    "extraction.jsonl",
    "synthesis.jsonl",
    "verification.jsonl",
]

OUTPUT_FILES = {
    "review.md": "",
    "review_body_draft.md": "",
    "article_plan.md": "",
    "appendix.md": "",
    "coverage_matrix.md": "",
    "evidence_ladder.md": "",
    "evidence_table.csv": "claim_id,paper_id,evidence\n",
    "references.bib": "",
    "final_report.md": "",
    "synthesis_tables.md": "",
    "figures_plan.md": "",
    "conceptual_framework.md": "",
    "glossary.md": "",
    "running_example.md": "",
    "worked_examples.md": "",
    "benchmark_landscape.md": "",
    "method_taxonomy.md": "",
    "node_paper_matrix.md": "",
    "evaluation_protocol.md": "",
    "design_guidelines.md": "",
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
    """Create a run directory with AutoResearch-compatible state files."""
    task_slug = slug or slugify(topic)
    task_dir = base_dir / task_slug
    state_dir = task_dir / "state"
    logs_dir = task_dir / "logs"
    outputs_dir = task_dir / "outputs"
    state_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    now = utc_now()
    task_spec = f"""# Task Spec

Topic: {topic}
Target: {target}
Output mode: {output_mode}

Mission:
Run an unattended survey-autoresearch workflow until the completion gates pass or a precise blocker is recorded.

Success criteria:
- Persistent state is updated every iteration.
- Literature recall, LQS scoring, citation-depth classification, venue/status verification, taxonomy design, evidence extraction, synthesis, and peer-review routing are completed.
- Full/CSUR runs build paper cards, system node cards, section cards, and a conceptual framework before drafting.
- Final outputs include review.md, evidence_table.csv, references.bib, and final_report.md.

Publication norm:
accepted_ratio_required: true
reason: default field norm; set false only for explicitly preprint-heavy fields.
"""
    (state_dir / "task_spec.md").write_text(task_spec, encoding="utf-8")

    progress = {
        "created_at": now,
        "updated_at": now,
        "last_seen": now,
        "status": "running",
        "iteration": 0,
        "phase": "phase_0_task_initialization",
        "stale_count": 0,
        "topic": topic,
        "target": target,
        "output_mode": output_mode,
        "papers_total": 0,
        "verified_refs": 0,
        "claims_total": 0,
        "gates_passed": [],
        "next_action": "write scope audit and mine multi-perspective research questions",
    }
    write_json(state_dir / "progress.json", progress)
    write_json(state_dir / "heartbeat.json", {"last_seen": now, "source": "init_task"})
    write_json(state_dir / "coverage.json", {"cells": {}, "summary": {"total_cells": 0}})
    write_json(state_dir / "directions_tried.json", {"directions": []})
    write_json(
        state_dir / "completion_gates.json",
        {
            "gate_1_literature": False,
            "gate_2_taxonomy": False,
            "gate_3_evidence": False,
            "gate_4_output": False,
            "gate_5_deep_synthesis": False,
            "gate_6_csur_readiness": False,
            "gate_7_review_depth": False,
            "final_review_status": False,
        },
    )
    (state_dir / "taxonomy.md").write_text(
        "# Taxonomy\n\nSeed axes will be updated by the taxonomy worker.\n",
        encoding="utf-8",
    )
    (state_dir / "research_questions.md").write_text("", encoding="utf-8")
    (state_dir / "research_questions_by_perspective.md").write_text("", encoding="utf-8")
    (state_dir / "topic_diagnosis.yml").write_text("", encoding="utf-8")
    (state_dir / "argument_graph.yml").write_text("", encoding="utf-8")
    (state_dir / "paper_summary_consistency.jsonl").touch()
    (state_dir / "search_protocol.md").write_text("", encoding="utf-8")
    (state_dir / "related_surveys.md").write_text("", encoding="utf-8")
    (state_dir / "csur_imitation_plan.md").write_text("", encoding="utf-8")
    (state_dir / "csur_style_patterns.yml").write_text("", encoding="utf-8")
    (state_dir / "csur_paragraph_patterns.yml").write_text("", encoding="utf-8")
    (state_dir / "paper_facts.jsonl").touch()

    for filename in STATE_FILES:
        (state_dir / filename).touch()
    for filename in LOG_FILES:
        (logs_dir / filename).touch()
    for filename, content in OUTPUT_FILES.items():
        (outputs_dir / filename).write_text(content, encoding="utf-8")
    (outputs_dir / "section_dossiers").mkdir(exist_ok=True)

    log_line = {
        "ts": now,
        "source": "init_task",
        "level": "decision",
        "event": "task_initialized",
        "detail": f"Initialized survey-autoresearch task for {topic}",
    }
    with (logs_dir / "orchestrator.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(log_line, sort_keys=True) + "\n")

    return task_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", required=True, type=Path)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--output-mode", default="markdown")
    parser.add_argument("--target", choices=["short", "full", "csur"], default="short")
    args = parser.parse_args()
    task_dir = initialize_task(
        base_dir=args.base_dir,
        topic=args.topic,
        slug=args.slug,
        output_mode=args.output_mode,
        target=args.target,
    )
    print(task_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
