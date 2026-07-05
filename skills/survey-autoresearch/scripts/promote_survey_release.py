#!/usr/bin/env python3
"""Promote a Gate-7-approved survey candidate to final survey artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    from .gate_freshness import stable_gate_hash
    from .gate_check import evaluate_gates
except ImportError:  # pragma: no cover
    from gate_freshness import stable_gate_hash
    from gate_check import evaluate_gates


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def completion_level(gates: dict) -> str:
    if gates.get("release_allowed") and gates.get("survey_complete"):
        return "publication_ready"
    if all((gates.get(name) or {}).get("passed") for name in [
        "gate_1_source_identity",
        "gate_2_paper_understanding",
        "gate_3_claim_evidence",
        "gate_4_coverage",
        "gate_5_argument_graph",
        "gate_6_article_quality",
    ]):
        return "automatic_checked"
    return "draft"


def quarantine_stale_finals(outputs: Path, paths: list[Path], gates: dict, gate_hash: str) -> dict:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return {"stale_final_quarantined": False, "stale_release_dir": "", "stale_artifacts": []}
    stamp = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y%m%dT%H%M%SZ")
    stale_dir = outputs / "stale_releases" / stamp
    suffix = 1
    while stale_dir.exists():
        suffix += 1
        stale_dir = outputs / "stale_releases" / f"{stamp}-{suffix}"
    stale_dir.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for path in existing:
        before_hash = sha256_file(path)
        destination = stale_dir / path.name
        shutil.move(str(path), str(destination))
        artifacts.append(
            {
                "original_path": str(path),
                "quarantined_path": str(destination),
                "sha256": before_hash,
            }
        )
    stale_manifest = {
        "stale_final_quarantined": True,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "blocked_by_phase": gates.get("blocked_by_phase"),
        "allowed_next_phase": gates.get("allowed_next_phase"),
        "completion_level": completion_level(gates),
        "gate_check_hash": gate_hash,
        "artifacts": artifacts,
    }
    write_json(stale_dir / "stale_manifest.json", stale_manifest)
    return {
        "stale_final_quarantined": True,
        "stale_release_dir": str(stale_dir),
        "stale_artifacts": artifacts,
    }


def promote_release(task_dir: Path, target: str = "full", gate_check_path: Path | None = None) -> dict:
    outputs = task_dir / "outputs"
    candidate_md = outputs / "survey_candidate.md"
    candidate_html = outputs / "survey_candidate.html"
    final_md = outputs / "survey.md"
    final_html = outputs / "survey.html"
    manifest_path = outputs / "release_manifest.json"
    final_report = outputs / "final_report.md"

    gates = evaluate_gates(task_dir, target)
    gate_hash = stable_gate_hash(gates)
    level = completion_level(gates)
    allowed = bool(gates.get("release_allowed") and gates.get("all_blocking_gates_passed"))

    manifest = {
        "released": False,
        "released_at": None,
        "completion_level": level,
        "survey_complete": False,
        "release_allowed": allowed,
        "candidate_hash": sha256_file(candidate_md),
        "candidate_html_hash": sha256_file(candidate_html),
        "survey_hash": sha256_file(final_md),
        "survey_html_hash": sha256_file(final_html),
        "gate_check_hash": gate_hash,
        "gate_check_path": str(gate_check_path) if gate_check_path else "",
        "blocked_by_phase": gates.get("blocked_by_phase"),
        "allowed_next_phase": gates.get("allowed_next_phase"),
    }

    if allowed:
        if not candidate_md.exists() or not candidate_md.read_text(encoding="utf-8").strip():
            manifest["release_error"] = "missing_survey_candidate_md"
        elif not candidate_html.exists() or not candidate_html.read_text(encoding="utf-8").strip():
            manifest["release_error"] = "missing_survey_candidate_html"
        else:
            shutil.copyfile(candidate_md, final_md)
            shutil.copyfile(candidate_html, final_html)
            manifest.update(
                {
                    "released": True,
                    "released_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "completion_level": "publication_ready",
                    "survey_complete": True,
                    "survey_hash": sha256_file(final_md),
                    "survey_html_hash": sha256_file(final_html),
                }
            )
    else:
        manifest.update(quarantine_stale_finals(outputs, [final_md, final_html], gates, gate_hash))
        manifest["survey_hash"] = sha256_file(final_md)
        manifest["survey_html_hash"] = sha256_file(final_html)

    write_json(manifest_path, manifest)
    status_line = (
        "Survey release: publication_ready\n"
        if manifest["released"]
        else f"Survey release blocked: {level}; survey_complete=false; final release is not valid\n"
    )
    final_report.write_text(status_line + json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    parser.add_argument("--gate-check-path", type=Path)
    args = parser.parse_args()
    result = promote_release(args.task_dir, args.target, args.gate_check_path)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("released") else 1


if __name__ == "__main__":
    raise SystemExit(main())
