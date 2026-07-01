#!/usr/bin/env python3
"""Render static HTML progress dashboards for survey-autoresearch runs."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

try:
    from .gate_check import evaluate_gates
except ImportError:  # pragma: no cover - used when run as a standalone script
    from gate_check import evaluate_gates


class DashboardRenderError(RuntimeError):
    """Raised when required dashboard state is malformed."""


PHASES = [
    {
        "id": "phase_0_task_initialization",
        "file": "phase_00_task_lock.html",
        "title": "Phase 0: Task Lock",
        "purpose": "Lock topic, scope, angle, audience, target, output mode, and assumptions.",
        "inputs": ["User topic", "target", "output mode"],
        "outputs": ["state/task_spec.md", "state/progress.json"],
        "checks": ["Task spec exists", "target is recorded", "next action is set"],
    },
    {
        "id": "phase_1_question_mining",
        "file": "phase_01_question_mining.html",
        "title": "Phase 1: Question Mining",
        "purpose": "Mine research questions from multiple reader and expert perspectives before locking taxonomy.",
        "inputs": ["state/task_spec.md"],
        "outputs": ["state/research_questions_by_perspective.md", "state/research_questions.md"],
        "checks": ["Multiple perspectives are recorded", "taxonomy remains provisional"],
    },
    {
        "id": "phase_2_recall",
        "file": "phase_02_recall.html",
        "title": "Phase 2: Recall",
        "purpose": "Retrieve broad candidate papers with multiple query routes per taxonomy cell.",
        "inputs": ["state/taxonomy.md"],
        "outputs": ["state/papers.jsonl", "logs/search.jsonl"],
        "checks": ["Candidates appended", "search routes logged"],
    },
    {
        "id": "phase_3_survey_role_scoring",
        "file": "phase_03_lqs_scoring.html",
        "title": "Phase 3: Survey-Role Scoring",
        "purpose": "Score candidates by conceptual centrality, mechanism clarity, evidence strength, coverage value, benchmark/ablation value, and verification.",
        "inputs": ["state/papers.jsonl"],
        "outputs": ["state/lqs_scores.jsonl"],
        "checks": ["Papers scored", "survey roles assigned", "foundational work is not dropped by age"],
    },
    {
        "id": "phase_4_citation_depth",
        "file": "phase_04_citation_depth.html",
        "title": "Phase 4: Citation Depth",
        "purpose": "Assign A/B/C/D citation depth so important papers drive the analysis.",
        "inputs": ["state/lqs_scores.jsonl"],
        "outputs": ["state/citation_plan.jsonl"],
        "checks": ["A/B papers assigned", "D papers excluded"],
    },
    {
        "id": "phase_5_verification",
        "file": "phase_05_verification.html",
        "title": "Phase 5: Verification",
        "purpose": "Verify citation identity, venue, year, and source status.",
        "inputs": ["state/citation_plan.jsonl"],
        "outputs": ["logs/verification.jsonl", "state/papers.jsonl"],
        "checks": ["Verification rate improves", "hallucinated citations remain zero"],
    },
    {
        "id": "phase_6_deep_evidence_extraction",
        "file": "phase_06_evidence_extraction.html",
        "title": "Phase 6: Deep Evidence Extraction",
        "purpose": "Convert A/B papers into paper cards and evidence-backed claim records.",
        "inputs": ["state/papers.jsonl", "state/citation_plan.jsonl"],
        "outputs": ["state/paper_cards.jsonl", "state/paper_facts.jsonl", "state/claims.jsonl"],
        "checks": ["A/B papers have paper cards", "major claims trace to card fields", "evidence spans are nonempty"],
    },
    {
        "id": "phase_7_system_node_graph",
        "file": "phase_07_system_node_graph.html",
        "title": "Phase 7: System-Node Graph",
        "purpose": "Build component or system-node cards, then repair taxonomy from node coverage.",
        "inputs": ["state/paper_cards.jsonl", "state/coverage.json"],
        "outputs": ["state/system_node_cards.jsonl", "state/taxonomy.md", "state/coverage.json"],
        "checks": ["System nodes have representative papers", "failure modes and evaluation signals are visible", "weak cells are repaired"],
    },
    {
        "id": "phase_8_section_planning",
        "file": "phase_08_section_planning.html",
        "title": "Phase 8: Section Planning",
        "purpose": "Plan major sections from reader questions, section theses, rhetoric patterns, and required display items.",
        "inputs": ["state/system_node_cards.jsonl", "state/paper_cards.jsonl"],
        "outputs": ["state/section_cards.jsonl", "outputs/conceptual_framework.md", "state/csur_style_patterns.yml"],
        "checks": ["Section cards exist", "conceptual framework exists", "CSUR rhetoric patterns exist when target=csur"],
    },
    {
        "id": "phase_9_synthesis",
        "file": "phase_09_synthesis.html",
        "title": "Phase 9: Synthesis",
        "purpose": "Write review outputs from paper cards, node cards, section cards, claims, and verified citations.",
        "inputs": ["state/section_cards.jsonl", "state/paper_cards.jsonl", "state/claims.jsonl", "state/citation_plan.jsonl"],
        "outputs": ["outputs/review.md", "outputs/evidence_table.csv", "outputs/references.bib", "outputs/synthesis_tables.md", "outputs/figures_plan.md"],
        "checks": ["Output files are nonempty", "claims are linked to evidence", "sections follow their cards"],
    },
    {
        "id": "phase_10_peer_review",
        "file": "phase_10_peer_review.html",
        "title": "Phase 10: Peer Review",
        "purpose": "Run newcomer, system architect, experimentalist, and CSUR stylist review passes.",
        "inputs": ["outputs/review.md", "state/section_cards.jsonl"],
        "outputs": ["state/review_rounds.jsonl"],
        "checks": ["Reviewer summaries exist", "major weaknesses are routed"],
    },
    {
        "id": "phase_11_sprint_loop",
        "file": "phase_11_sprint_loop.html",
        "title": "Phase 11: Sprint Loop",
        "purpose": "Fix routed weaknesses, rerun gates, and stop only when complete or blocked.",
        "inputs": ["state/review_rounds.jsonl", "state/completion_gates.json"],
        "outputs": ["outputs/final_report.md", "dashboard/index.html"],
        "checks": ["Gates pass or blocker is documented", "no regression remains"],
    },
]


CSS = """
:root {
  --bg: #f6f7f9;
  --surface: #ffffff;
  --surface-soft: #f0f3f6;
  --border: #d8dee4;
  --text: #1f2328;
  --muted: #636c76;
  --green: #1a7f37;
  --blue: #0969da;
  --amber: #9a6700;
  --red: #cf222e;
  --gray: #6e7781;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.5;
}
a { color: var(--blue); text-decoration: none; }
a:hover { text-decoration: underline; }
.wrap { max-width: 1160px; margin: 0 auto; padding: 24px; }
header { border-bottom: 1px solid var(--border); padding-bottom: 18px; margin-bottom: 20px; }
h1 { font-size: 28px; margin: 0 0 8px; letter-spacing: 0; }
h2 { font-size: 18px; margin: 28px 0 12px; }
h3 { font-size: 15px; margin: 0 0 8px; }
.muted { color: var(--muted); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
}
.metric { font-size: 24px; font-weight: 700; margin: 2px 0; }
.pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  font-size: 12px;
  font-weight: 600;
}
.passed { color: var(--green); background: #dafbe1; border-color: #aceebb; }
.active { color: var(--blue); background: #ddf4ff; border-color: #b6e3ff; }
.stale { color: var(--amber); background: #fff8c5; border-color: #f0d98c; }
.blocked, .failed { color: var(--red); background: #ffebe9; border-color: #ffcecb; }
.not_started { color: var(--gray); background: #f6f8fa; border-color: var(--border); }
.phase-card { min-height: 128px; }
.phase-card a { font-weight: 700; }
table { width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); }
th, td { padding: 9px 10px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
th { background: var(--surface-soft); font-size: 12px; text-transform: uppercase; color: var(--muted); }
ul { margin: 8px 0 0 18px; padding: 0; }
li { margin: 4px 0; }
.section { margin-top: 22px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }
.warning { border-left: 4px solid var(--amber); }
.danger { border-left: 4px solid var(--red); }
.ok { border-left: 4px solid var(--green); }
footer { margin-top: 28px; padding-top: 14px; border-top: 1px solid var(--border); color: var(--muted); font-size: 13px; }
"""


def html_escape(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def read_required_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DashboardRenderError(f"Malformed JSON in required file {path}: {exc}") from exc
    except FileNotFoundError:
        return {}


def read_optional_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def read_jsonl(path: Path, required: bool = False) -> list[dict]:
    if not path.exists():
        if required:
            raise DashboardRenderError(f"Missing required JSONL file {path}")
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise DashboardRenderError(f"Malformed JSONL in {path}:{line_number}: {exc}") from exc
    return rows


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def rel_link(rel_path: str, label: str | None = None, prefix: str = "../") -> str:
    return f'<a href="{html_escape(prefix + rel_path)}">{html_escape(label or rel_path)}</a>'


def phase_index(phase_id: str) -> int:
    for idx, phase in enumerate(PHASES):
        if phase["id"] == phase_id:
            return idx
    return 0


def phase_statuses(progress: dict) -> dict[str, str]:
    current = progress.get("phase", "phase_0_task_initialization")
    current_idx = phase_index(current)
    status = progress.get("status", "running")
    stale_count = int(progress.get("stale_count", 0) or 0)
    statuses = {}
    for idx, phase in enumerate(PHASES):
        if status == "blocked" and idx == current_idx:
            statuses[phase["id"]] = "blocked"
        elif idx < current_idx:
            statuses[phase["id"]] = "complete"
        elif idx == current_idx and stale_count >= 2:
            statuses[phase["id"]] = "stale"
        elif idx == current_idx:
            statuses[phase["id"]] = "active"
        else:
            statuses[phase["id"]] = "not_started"
    return statuses


def status_label(status: str) -> str:
    css = {
        "complete": "passed",
        "active": "active",
        "stale": "stale",
        "blocked": "blocked",
        "not_started": "not_started",
    }.get(status, "not_started")
    return f'<span class="pill {css}">{html_escape(status)}</span>'


def gate_label(passed: bool) -> str:
    return '<span class="pill passed">passed</span>' if passed else '<span class="pill failed">failing</span>'


def load_state(task_dir: Path) -> dict:
    state_dir = task_dir / "state"
    logs_dir = task_dir / "logs"
    progress = read_required_json(state_dir / "progress.json")
    heartbeat = read_required_json(state_dir / "heartbeat.json")
    completion_gates = read_required_json(state_dir / "completion_gates.json")
    coverage = read_required_json(state_dir / "coverage.json")
    claims = read_jsonl(state_dir / "claims.jsonl")
    citation_plan = read_jsonl(state_dir / "citation_plan.jsonl")
    review_rounds = read_jsonl(state_dir / "review_rounds.jsonl")
    phase_summaries = read_jsonl(state_dir / "phase_summaries.jsonl")
    decisions = []
    for log_path in sorted(logs_dir.glob("*.jsonl")):
        for row in read_jsonl(log_path):
            if row.get("level") == "decision":
                item = dict(row)
                item["log_file"] = str(log_path.relative_to(task_dir))
                decisions.append(item)
    decisions = decisions[-12:]
    try:
        gates = evaluate_gates(task_dir, target=progress.get("target", "short"))
    except Exception as exc:  # gate helper should never prevent visibility
        gates = {"error": str(exc), "all_blocking_gates_passed": False}
    return {
        "progress": progress,
        "heartbeat": heartbeat,
        "completion_gates": completion_gates,
        "coverage": coverage,
        "claims": claims,
        "citation_plan": citation_plan,
        "review_rounds": review_rounds,
        "phase_summaries": phase_summaries,
        "decisions": decisions,
        "gates": gates,
        "taxonomy": read_optional_text(state_dir / "taxonomy.md"),
    }


def latest_review_summary(review_rounds: list[dict]) -> str:
    if not review_rounds:
        return "not available yet"
    latest = review_rounds[-1]
    return latest.get("summary") or latest.get("overall_summary") or "not available yet"


def open_major_weaknesses(review_rounds: list[dict]) -> list[str]:
    weaknesses = []
    for review in review_rounds:
        for weakness in review.get("weaknesses", []):
            if isinstance(weakness, dict):
                severity = str(weakness.get("severity", "")).lower()
                status = str(weakness.get("status", "open")).lower()
                if severity == "major" and status not in {"resolved", "closed", "fixed"}:
                    weaknesses.append(weakness.get("text") or weakness.get("body") or json.dumps(weakness))
            elif isinstance(weakness, str):
                weaknesses.append(weakness)
    return weaknesses[-8:]


def group_claims(claims: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for claim in claims:
        confidence = str(claim.get("confidence", "")).lower()
        if confidence and confidence not in {"high", "medium"}:
            continue
        grouped[claim.get("taxonomy_cell") or "unassigned"].append(claim)
    return dict(grouped)


def render_claims(claims: list[dict]) -> str:
    grouped = group_claims(claims)
    if not grouped:
        return '<p class="muted">not available yet</p>'
    parts = []
    for cell, cell_claims in sorted(grouped.items()):
        items = "".join(
            f"<li><strong>{html_escape(claim.get('claim_id', 'claim'))}</strong>: "
            f"{html_escape(claim.get('claim', ''))}<br><span class=\"muted\">Evidence: "
            f"{html_escape(claim.get('evidence', 'not available yet'))}</span></li>"
            for claim in cell_claims[-5:]
        )
        parts.append(f"<div class=\"card\"><h3>{html_escape(cell)}</h3><ul>{items}</ul></div>")
    return '<div class="grid">' + "".join(parts) + "</div>"


def render_decisions(decisions: list[dict], phase_id: str | None = None) -> str:
    selected = decisions
    if phase_id:
        selected = [item for item in decisions if item.get("phase") in {None, "", phase_id} or phase_id in str(item.get("detail", ""))]
        if not selected:
            selected = decisions[-5:]
    if not selected:
        return '<p class="muted">not available yet</p>'
    rows = ""
    for item in selected[-8:]:
        rows += (
            "<tr>"
            f"<td>{html_escape(item.get('ts', ''))}</td>"
            f"<td>{html_escape(item.get('source', ''))}</td>"
            f"<td>{html_escape(item.get('event', 'decision'))}</td>"
            f"<td>{html_escape(item.get('detail', ''))}</td>"
            f"<td class=\"mono\">{html_escape(item.get('log_file', ''))}</td>"
            "</tr>"
        )
    return f"<table><tr><th>Time</th><th>Source</th><th>Event</th><th>Decision</th><th>Log</th></tr>{rows}</table>"


def render_phase_summaries(phase_summaries: list[dict], phase_id: str) -> str:
    selected = [item for item in phase_summaries if item.get("phase") == phase_id]
    if not selected:
        return '<p class="muted">not available yet</p>'
    latest = selected[-1]
    conclusions = latest.get("conclusions") or []
    conclusion_html = "".join(f"<li>{html_escape(item)}</li>" for item in conclusions) or "<li>not available yet</li>"
    return (
        f"<p>{html_escape(latest.get('summary', 'not available yet'))}</p>"
        f"<ul>{conclusion_html}</ul>"
    )


def render_gate_board(gates: dict) -> str:
    if "error" in gates:
        return f'<div class="card danger">Gate check unavailable: {html_escape(gates["error"])}</div>'
    gate_names = [
        ("gate_1_literature", "Literature"),
        ("gate_2_taxonomy", "Taxonomy"),
        ("gate_3_evidence", "Evidence"),
        ("gate_4_output", "Output"),
    ]
    if "gate_5_deep_synthesis" in gates:
        gate_names.append(("gate_5_deep_synthesis", "Deep Synthesis"))
    if "gate_6_csur_readiness" in gates:
        gate_names.append(("gate_6_csur_readiness", "CSUR"))
    cards = []
    for gate_id, label in gate_names:
        gate = gates.get(gate_id, {})
        detail = ""
        if gate_id == "gate_1_literature":
            detail = (
                f"<div class=\"muted\">papers {html_escape(gate.get('papers', 0))}/"
                f"{html_escape(gate.get('min_refs', 'n/a'))}</div>"
                f"<div class=\"muted\">verified {html_escape(gate.get('verification_rate', 0))}</div>"
            )
        elif gate_id == "gate_3_evidence":
            validation = gate.get("claim_validation", {})
            detail = f"<div class=\"muted\">valid claims {html_escape(validation.get('valid_claims', 0))}</div>"
        elif gate_id == "gate_5_deep_synthesis":
            checks = gate.get("checks", [])
            if isinstance(checks, dict):
                total = len(checks)
                passed = sum(1 for item in checks.values() if bool(item))
            else:
                total = len(checks)
                passed = sum(1 for item in checks if isinstance(item, dict) and item.get("passed"))
            detail = f"<div class=\"muted\">checks {html_escape(passed)}/{html_escape(total)}</div>"
        cards.append(
            f'<div class="card"><h3>{html_escape(label)}</h3>{gate_label(bool(gate.get("passed")))}{detail}</div>'
        )
    final_passed = bool(gates.get("all_blocking_gates_passed"))
    cards.append(f'<div class="card"><h3>Blocking Gates</h3>{gate_label(final_passed)}</div>')
    return '<div class="grid">' + "".join(cards) + "</div>"


def artifact_links(prefix: str = "../") -> str:
    artifacts = [
        "outputs/review.md",
        "outputs/evidence_table.csv",
        "outputs/references.bib",
        "outputs/final_report.md",
        "state/progress.json",
        "state/claims.jsonl",
        "state/citation_plan.jsonl",
        "state/review_rounds.jsonl",
        "logs/orchestrator.jsonl",
    ]
    return "<ul>" + "".join(f"<li>{rel_link(path, prefix=prefix)}</li>" for path in artifacts) + "</ul>"


def page(title: str, body: str) -> str:
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(title)}</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="wrap">
    {body}
    <footer>Generated {html_escape(generated)} UTC by survey-autoresearch.</footer>
  </div>
</body>
</html>
"""


def render_overview(task_dir: Path, state: dict, statuses: dict[str, str]) -> str:
    progress = state["progress"]
    heartbeat = state["heartbeat"]
    gates = state["gates"]
    topic = progress.get("topic", task_dir.name)
    current_phase = progress.get("phase", "phase_0_task_initialization")
    phase_cards = ""
    for phase in PHASES:
        status = statuses[phase["id"]]
        phase_cards += (
            '<div class="card phase-card">'
            f'<div>{status_label(status)}</div>'
            f'<p><a href="phases/{html_escape(phase["file"])}">{html_escape(phase["title"])}</a></p>'
            f'<p class="muted">{html_escape(phase["purpose"])}</p>'
            "</div>"
        )
    weaknesses = open_major_weaknesses(state["review_rounds"])
    risk_items = [
        f"stale_count: {progress.get('stale_count', 0)}",
        f"status: {progress.get('status', 'unknown')}",
    ]
    risk_items.extend(weaknesses or ["not available yet"])
    risks = "".join(f"<li>{html_escape(item)}</li>" for item in risk_items)
    body = f"""
<header>
  <h1>{html_escape(topic)}</h1>
  <p class="muted">Survey AutoResearch progress dashboard</p>
</header>
<section class="grid">
  <div class="card"><h3>Status</h3><div class="metric">{html_escape(progress.get('status', 'unknown'))}</div></div>
  <div class="card"><h3>Target</h3><div class="metric">{html_escape(progress.get('target', 'unknown'))}</div></div>
  <div class="card"><h3>Current Phase</h3><div class="metric mono">{html_escape(current_phase)}</div></div>
  <div class="card"><h3>Iteration</h3><div class="metric">{html_escape(progress.get('iteration', 0))}</div></div>
  <div class="card"><h3>Last Heartbeat</h3><div class="metric mono">{html_escape(heartbeat.get('last_seen', 'not available yet'))}</div></div>
  <div class="card"><h3>Next Action</h3><p>{html_escape(progress.get('next_action', 'not available yet'))}</p></div>
</section>
<section class="section">
  <h2>Phase Timeline</h2>
  <div class="grid">{phase_cards}</div>
</section>
<section class="section">
  <h2>Gate Board</h2>
  {render_gate_board(gates)}
</section>
<section class="section">
  <h2>Current Conclusions</h2>
  {render_claims(state["claims"])}
</section>
<section class="section">
  <h2>Current Summary</h2>
  <div class="card"><p>{html_escape(latest_review_summary(state["review_rounds"]))}</p></div>
</section>
<section class="section">
  <h2>Risks And Blockers</h2>
  <div class="card warning"><ul>{risks}</ul></div>
</section>
<section class="section">
  <h2>Recent Decisions</h2>
  {render_decisions(state["decisions"])}
</section>
<section class="section">
  <h2>Evidence Links</h2>
  <div class="card">{artifact_links(prefix="../")}</div>
</section>
"""
    return page(f"{topic} - Survey AutoResearch Dashboard", body)


def render_phase_page(task_dir: Path, state: dict, phase: dict, status: str) -> str:
    progress = state["progress"]
    inputs = "".join(f"<li>{rel_link(path, path, prefix='../../')}</li>" for path in phase["inputs"])
    outputs = "".join(f"<li>{rel_link(path, path, prefix='../../')}</li>" for path in phase["outputs"])
    checks = "".join(f"<li>{html_escape(item)}</li>" for item in phase["checks"])
    body = f"""
<header>
  <p><a href="../index.html">Dashboard</a></p>
  <h1>{html_escape(phase["title"])}</h1>
  <p class="muted">{html_escape(phase["purpose"])}</p>
  <p>{status_label(status)} <span class="muted">Current run phase: {html_escape(progress.get('phase', 'unknown'))}</span></p>
</header>
<section class="grid">
  <div class="card"><h3>Inputs</h3><ul>{inputs}</ul></div>
  <div class="card"><h3>Outputs</h3><ul>{outputs}</ul></div>
  <div class="card"><h3>Completion Checks</h3><ul>{checks}</ul></div>
</section>
<section class="section">
  <h2>Phase Summary</h2>
  <div class="card">{render_phase_summaries(state["phase_summaries"], phase["id"])}</div>
</section>
<section class="section">
  <h2>Key Conclusions</h2>
  {render_claims(state["claims"])}
</section>
<section class="section">
  <h2>Recent Decisions</h2>
  {render_decisions(state["decisions"], phase_id=phase["id"])}
</section>
<section class="section">
  <h2>Raw Artifacts</h2>
  <div class="card">{artifact_links(prefix="../../")}</div>
</section>
"""
    return page(phase["title"], body)


def render_error_dashboard(task_dir: Path, error: Exception) -> None:
    body = f"""
<header>
  <h1>Survey AutoResearch Dashboard Error</h1>
  <p class="muted">The dashboard could not be rendered from current state.</p>
</header>
<div class="card danger">
  <h2>Warning</h2>
  <p>{html_escape(error)}</p>
</div>
"""
    write_text(task_dir / "dashboard/index.html", page("Survey AutoResearch Dashboard Error", body))


def render_dashboard(task_dir: Path) -> dict:
    try:
        state = load_state(task_dir)
        statuses = phase_statuses(state["progress"])
        dashboard_dir = task_dir / "dashboard"
        phases_dir = dashboard_dir / "phases"
        phase_pages = []
        write_text(dashboard_dir / "index.html", render_overview(task_dir, state, statuses))
        for phase in PHASES:
            phase_path = phases_dir / phase["file"]
            write_text(phase_path, render_phase_page(task_dir, state, phase, statuses[phase["id"]]))
            phase_pages.append(str(phase_path))
        return {"index": str(dashboard_dir / "index.html"), "phase_pages": phase_pages}
    except DashboardRenderError as exc:
        render_error_dashboard(task_dir, exc)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = render_dashboard(args.task_dir)
    except DashboardRenderError as exc:
        print(str(exc))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
