#!/usr/bin/env python3
"""Prepare an independent expansion-audit packet without fabricating audit content."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


AUDITOR_ID = "expansion_clarity_auditor"
AUDITOR_PERSONA = "Expansion Clarity Auditor"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def dispatch_packet(task_dir: Path, audit_round_id: str | None = None) -> dict:
    state = task_dir / "state"
    packets_dir = state / "expansion_audit_packets"
    packets_dir.mkdir(exist_ok=True)
    round_id = audit_round_id or f"expansion-{utc_now()}"
    packet_path = packets_dir / "expansion_clarity_auditor.json"
    packet = {
        "audit_round_id": round_id,
        "auditor_id": AUDITOR_ID,
        "persona": AUDITOR_PERSONA,
        "instructions": (
            "Use a fresh context. Identify only places where the survey is unclear or underexplained. "
            "Do not rewrite the article. Return JSONL rows in state/expansion_audit.jsonl with evidence-backed expansion items."
        ),
        "inputs": [
            "outputs/survey_candidate.md",
            "outputs/article_plan.md",
            "state/argument_graph.yml",
            "state/section_evidence_plans.jsonl",
            "state/claim_evidence_spans.jsonl",
            "state/paper_mechanism_cards.jsonl",
            "outputs/contribution_tree.yml",
            "outputs/method_family_dossiers",
            "outputs/benchmark_dossiers",
        ],
        "forbidden_inputs": ["writer expansion plan", "previous expansion prose", "repair actions from this audit round"],
        "output": "state/expansion_audit.jsonl",
        "status": "dispatched",
        "timestamp": utc_now(),
    }
    write_json(packet_path, packet)
    return {"status": "dispatched", "audit_round_id": round_id, "packet": str(packet_path.relative_to(task_dir))}


def collect_status(task_dir: Path) -> dict:
    rows = read_jsonl(task_dir / "state" / "expansion_audit.jsonl")
    return {
        "auditor_id": AUDITOR_ID,
        "persona": AUDITOR_PERSONA,
        "returned": bool(rows),
        "items": len(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--audit-round-id")
    parser.add_argument("--dispatch", action="store_true")
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    if args.dispatch:
        result = dispatch_packet(args.task_dir, args.audit_round_id)
    elif args.collect:
        result = collect_status(args.task_dir)
    else:
        result = {"error": "choose --dispatch or --collect"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
