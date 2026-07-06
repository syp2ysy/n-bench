#!/usr/bin/env python3
"""Initialize persistent state for a survey-autoresearch run."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .status_schema import STATUS_SCHEMA_VERSION
except ImportError:  # pragma: no cover
    from status_schema import STATUS_SCHEMA_VERSION


BOOTSTRAP_STATE_FILES = [
    "tasks.jsonl",
    "failure_ledger.jsonl",
]

LOG_FILES = [
    "orchestrator.jsonl",
    "heartbeat.jsonl",
]

OUTPUT_FILES = {
    "release_manifest.json": json.dumps({"released": False, "survey_complete": False, "release_allowed": False}, indent=2, sort_keys=True) + "\n",
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
    target: str = "full",
) -> Path:
    task_slug = slug or slugify(topic)
    runs_root = base_dir if base_dir.name == "runs" else base_dir / "runs"
    task_dir = runs_root / task_slug
    state = task_dir / "state"
    logs = task_dir / "logs"
    outputs = task_dir / "outputs"
    state.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    (state / "paper_cards").mkdir(exist_ok=True)

    now = utc_now()
    (state / "task_spec.md").write_text(
        f"# Task Spec\n\nTopic: {topic}\nTarget: {target}\nOutput mode: {output_mode}\n",
        encoding="utf-8",
    )
    write_json(
        state / "progress.json",
        {
            "created_at": now,
            "updated_at": now,
            "last_seen": now,
            "status": "running",
            "iteration": 0,
            "phase": "task_lock",
            "current_phase": "task_lock",
            "last_passed_phase": None,
            "blocked_by_phase": None,
            "allowed_next_phase": "topic_profile",
            "topic": topic,
            "target": target,
            "next_action": "run runner.py to prepare topic_profile worker task",
        },
    )
    write_json(state / "heartbeat.json", {"last_seen": now, "source": "init_task"})
    write_json(
        state / "run_state.json",
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "component": "run_state",
            "target": target,
            "topic": topic,
            "status": "initialized",
            "workflow": {
                "public_entrypoint": "runner.py",
                "legacy_driver": "survey_driver.py",
                "queue": "tasks.jsonl",
            },
            "research_assets": {
                "topic_profile": {"canonical": "state/topic_profile.json", "status": "missing"},
                "paper_cards": {"canonical": "state/paper_cards", "status": "empty"},
                "knowledge_tree": {"canonical": "outputs/knowledge_tree.yml", "status": "missing"},
                "spine_decision": {"canonical": "state/spine_decision.md", "status": "missing"},
                "failure_ledger": {"canonical": "state/failure_ledger.jsonl", "status": "empty"},
            },
            "created_at": now,
            "updated_at": now,
        },
    )
    for filename in BOOTSTRAP_STATE_FILES:
        (state / filename).touch()
    for filename in LOG_FILES:
        (logs / filename).touch()
    for filename, content in OUTPUT_FILES.items():
        (outputs / filename).write_text(content, encoding="utf-8")
    with (logs / "orchestrator.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": now, "event": "task_initialized", "topic": topic}, sort_keys=True) + "\n")
    return task_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", required=True, type=Path)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--output-mode", default="markdown")
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    print(initialize_task(args.base_dir, args.topic, args.slug, args.output_mode, args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
