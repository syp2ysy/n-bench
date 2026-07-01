#!/usr/bin/env python3
"""Patrol survey-autoresearch runs for stale heartbeat state."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def inspect_task(
    task_dir: Path,
    now_iso: str | None = None,
    stale_after_minutes: int = 120,
) -> dict:
    state_dir = task_dir / "state"
    progress_path = state_dir / "progress.json"
    heartbeat_path = state_dir / "heartbeat.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
    heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8")) if heartbeat_path.exists() else {}
    last_seen = progress.get("last_seen") or heartbeat.get("last_seen")
    now = parse_ts(now_iso) if now_iso else utc_now()

    if not last_seen:
        minutes_since_seen = None
        stale = True
    else:
        delta = now - parse_ts(last_seen)
        minutes_since_seen = int(delta.total_seconds() // 60)
        stale = minutes_since_seen >= stale_after_minutes

    stale_count = int(progress.get("stale_count", 0))
    if stale_count >= 4:
        action = "structural_pivot_or_blocked_report"
    elif stale:
        action = "nudge_or_restart"
    else:
        action = "continue"

    return {
        "task_dir": str(task_dir),
        "stale": stale,
        "minutes_since_seen": minutes_since_seen,
        "stale_after_minutes": stale_after_minutes,
        "stale_count": stale_count,
        "recommended_action": action,
    }


def patrol(base_dir: Path, stale_after_minutes: int = 120) -> list[dict]:
    results = []
    for progress_path in sorted(base_dir.glob("*/state/progress.json")):
        results.append(
            inspect_task(progress_path.parents[1], stale_after_minutes=stale_after_minutes)
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", type=Path)
    parser.add_argument("--task-dir", type=Path)
    parser.add_argument("--stale-after-minutes", type=int, default=120)
    args = parser.parse_args()
    if bool(args.base_dir) == bool(args.task_dir):
        parser.error("provide exactly one of --base-dir or --task-dir")
    if args.task_dir:
        results = [inspect_task(args.task_dir, stale_after_minutes=args.stale_after_minutes)]
    else:
        results = patrol(args.base_dir, stale_after_minutes=args.stale_after_minutes)
    print(json.dumps(results, indent=2, sort_keys=True))
    return 1 if any(item["stale"] for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
