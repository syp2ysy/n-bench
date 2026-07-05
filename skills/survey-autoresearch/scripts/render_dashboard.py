#!/usr/bin/env python3
"""Render a compact HTML dashboard for survey-autoresearch runs."""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

try:
    from .gate_check import evaluate_gates
except ImportError:  # pragma: no cover
    from gate_check import evaluate_gates


class DashboardRenderError(RuntimeError):
    """Raised when required dashboard state is malformed."""


CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f6f7f9; color: #1f2328; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 24px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.card { background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 14px; }
.muted { color: #636c76; }
.pass { color: #1a7f37; font-weight: 700; }
.fail { color: #cf222e; font-weight: 700; }
pre { white-space: pre-wrap; background: #f0f3f6; padding: 12px; border-radius: 8px; }
"""


def esc(value) -> str:
    return escape("" if value is None else str(value), quote=True)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DashboardRenderError(f"Malformed JSON: {path}") from exc


def render_dashboard(task_dir: Path, target: str | None = None) -> Path:
    state = task_dir / "state"
    dashboard = task_dir / "dashboard"
    dashboard.mkdir(exist_ok=True)
    progress = read_json(state / "progress.json")
    selected_target = target or progress.get("target") or "full"
    gates = evaluate_gates(task_dir, selected_target)
    phase_barriers = gates.get("phase_barriers", {})
    outputs = task_dir / "outputs"
    coverage = gates.get("gate_4_coverage", {})
    phase_coverage = (((phase_barriers.get("phases") or {}).get("source_verification") or {}).get("details") or {}).get("coverage") or coverage
    gate_cards = []
    for key in [
        "gate_1_source_identity",
        "gate_2_paper_understanding",
        "gate_3_claim_evidence",
        "gate_4_coverage",
        "gate_5_argument_graph",
        "gate_6_article_quality",
        "gate_7_expert_review",
    ]:
        gate = gates.get(key, {})
        score = ""
        if key == "gate_7_expert_review" and gate.get("median_score") is not None:
            score = f"<p class='muted'>median expert score: {esc(gate.get('median_score'))}</p>"
            round_status = gate.get("round_status") or {}
            dim = gate.get("dimension_medians") or {}
            dim_preview = ", ".join(f"{name}:{value}" for name, value in sorted(dim.items())[:4])
            score += (
                "<p class='muted'>reviewers returned: "
                + f"{esc(round_status.get('reviewers_returned', 0))}/{esc(round_status.get('reviewers_expected', 5))}</p>"
                + f"<p class='muted'>dimension medians: {esc(dim_preview)}</p>"
                + f"<p class='muted'>canonical major weaknesses: {esc(len(gate.get('canonical_major_weaknesses') or []))}</p>"
                + f"<p class='muted'>unresolved repairs: {esc(len(gate.get('unresolved_major_weaknesses') or []))}</p>"
                + f"<p class='muted'>targeted rereview issues: {esc(len(gate.get('invalid_targeted_rereviews') or {}))}</p>"
            )
        if key == "gate_2_paper_understanding":
            score = (
                score
                + "<p class='muted'>A/B full-text deep-read: "
                + f"{esc(gate.get('a_b_full_text_deep_read_count', 0))}/{esc(gate.get('a_b_required_count', gate.get('required_a_b_cards', 0)))}"
                + f" · metadata-only A/B: {esc(gate.get('metadata_only_a_b_count', 0))}</p>"
            )
        gate_cards.append(
            f"<div class='card'><h3>{esc(key)}</h3><div class='{ 'pass' if gate.get('passed') else 'fail' }'>"
            f"{'PASS' if gate.get('passed') else 'FAIL'}</div>{score}<pre>{esc(json.dumps(gate, indent=2, ensure_ascii=False)[:1200])}</pre></div>"
        )
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Survey AutoResearch</title>"
        f"<style>{CSS}</style></head><body><div class='wrap'>"
        f"<h1>{esc(progress.get('topic', task_dir.name))}</h1>"
        f"<p class='muted'>target: {esc(selected_target)}</p>"
        "<div class='grid'>"
        f"<div class='card'><h3>Current Phase</h3><p>{esc(progress.get('current_phase') or progress.get('phase'))}</p>"
        f"<p class='muted'>last passed: {esc(phase_barriers.get('last_passed_phase'))}</p>"
        f"<p class='muted'>blocked by: {esc(phase_barriers.get('blocked_by_phase'))}</p>"
        f"<p class='muted'>allowed next: {esc(phase_barriers.get('allowed_next_phase'))}</p></div>"
        f"<div class='card'><h3>Release</h3><p>completion: {esc(gates.get('completion_level'))}</p>"
        f"<p class='muted'>survey complete: {esc(gates.get('survey_complete'))}</p>"
        f"<p class='muted'>release allowed: {esc(gates.get('release_allowed'))}</p>"
        f"<p class='muted'>candidate md: {esc((outputs / 'survey_candidate.md').exists())}</p>"
        f"<p class='muted'>final md: {esc((outputs / 'survey.md').exists())}</p></div>"
        f"<div class='card'><h3>Discovery</h3><p class='muted'>raw candidates: {esc(coverage.get('raw_candidates', 0))}</p>"
        f"<p class='muted'>search routes: {esc(coverage.get('search_routes', 0))}</p>"
        f"<p class='muted'>related surveys: {esc(coverage.get('related_surveys', 0))}</p>"
        f"<p class='muted'>corpus expansion: {esc(coverage.get('corpus_expansion_status'))}</p>"
        f"<p class='muted'>retained coverage ready: {esc(not bool(phase_coverage.get('retained_missing')))}</p>"
        f"<p class='muted'>coverage blockers: {esc(', '.join(phase_coverage.get('retained_missing') or []))}</p></div>"
        "</div>"
        f"<div class='grid'>{''.join(gate_cards)}</div>"
        f"<h2>Blocking Gates</h2><div class='{ 'pass' if gates.get('all_blocking_gates_passed') else 'fail' }'>"
        f"{'PASS' if gates.get('all_blocking_gates_passed') else 'FAIL'}</div>"
        "</div></body></html>"
    )
    path = dashboard / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"])
    args = parser.parse_args()
    print(render_dashboard(args.task_dir, args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
