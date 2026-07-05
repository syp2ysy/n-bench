#!/usr/bin/env python3
"""Stable release-freshness helpers for survey-autoresearch gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .gate_check import evaluate_gates
except ImportError:  # pragma: no cover
    from gate_check import evaluate_gates


VOLATILE_GATE_HASH_KEYS = {"generated_at", "release_manifest", "survey_complete", "completion_level"}


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def nonempty_file(path: Path) -> bool:
    return path.exists() and path.is_file() and bool(path.read_text(encoding="utf-8").strip())


def stable_gate_payload(gates: dict) -> dict:
    return {key: value for key, value in (gates or {}).items() if key not in VOLATILE_GATE_HASH_KEYS}


def stable_gate_hash(gates: dict) -> str:
    payload = json.dumps(stable_gate_payload(gates), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def current_gate_status_and_hash(task_dir: Path, target: str = "full") -> tuple[dict, str]:
    gates = evaluate_gates(task_dir, target)
    return gates, stable_gate_hash(gates)


def release_manifest_fresh(task_dir: Path, manifest: dict, target: str = "full") -> tuple[bool, dict]:
    outputs = task_dir / "outputs"
    candidate_md = outputs / "survey_candidate.md"
    final_md = outputs / "survey.md"
    final_html = outputs / "survey.html"
    gates, gate_hash = current_gate_status_and_hash(task_dir, target)
    checks = {
        "released": manifest.get("released") is True,
        "released_at": bool(str(manifest.get("released_at") or "").strip()),
        "release_allowed": gates.get("release_allowed") is True,
        "all_blocking_gates_passed": gates.get("all_blocking_gates_passed") is True,
        "final_md_nonempty": nonempty_file(final_md),
        "final_html_nonempty": nonempty_file(final_html),
        "candidate_hash": str(manifest.get("candidate_hash") or "") == sha256_file(candidate_md),
        "survey_hash": str(manifest.get("survey_hash") or "") == sha256_file(final_md),
        "survey_html_hash": str(manifest.get("survey_html_hash") or "") == sha256_file(final_html),
        "gate_check_hash": str(manifest.get("gate_check_hash") or "") == gate_hash,
    }
    return all(checks.values()), {"checks": checks, "gate_check_hash": gate_hash, "gates": gates}
