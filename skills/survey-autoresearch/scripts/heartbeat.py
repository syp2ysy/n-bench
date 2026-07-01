#!/usr/bin/env python3
"""Update heartbeat timestamps for survey-autoresearch runs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def update_heartbeat(task_dir: Path, source: str = "heartbeat") -> dict:
    now = utc_now()
    payload = {"last_seen": now, "source": source}
    heartbeat_path = task_dir / "state" / "heartbeat.json"
    heartbeat_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    progress_path = task_dir / "state" / "progress.json"
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        progress["last_seen"] = now
        progress["updated_at"] = now
        progress_path.write_text(json.dumps(progress, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log_path = task_dir / "logs" / "heartbeat.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": now, "source": source, "event": "heartbeat"}) + "\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--source", default="heartbeat")
    args = parser.parse_args()
    print(json.dumps(update_heartbeat(args.task_dir, args.source), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
