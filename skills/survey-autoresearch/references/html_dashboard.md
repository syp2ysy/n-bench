# HTML Dashboard

Use this reference whenever a run updates progress, gates, summaries, or final artifacts.

## Purpose

The dashboard gives the user a static, browser-readable view of the run without introducing a server dependency. It is a view over existing state files, not a separate source of truth.

## Render Command

Run after each orchestrator loop and after final report updates:

```bash
python3 scripts/render_dashboard.py --task-dir <run_dir>
```

This overwrites:

```text
<run_dir>/dashboard/index.html
<run_dir>/dashboard/phases/phase_00_task_lock.html
...
<run_dir>/dashboard/phases/phase_11_sprint_loop.html
```

## Dashboard Source Files

The renderer reads:
- `state/progress.json`
- `state/heartbeat.json`
- `state/completion_gates.json`
- `state/coverage.json`
- `state/taxonomy.md`
- `state/claims.jsonl`
- `state/citation_plan.jsonl`
- `state/review_rounds.jsonl`
- `state/phase_summaries.jsonl`
- recent `logs/*.jsonl`
- output artifact paths

Missing optional JSONL files render as `not available yet`. Malformed required JSON renders an error dashboard and exits nonzero.

## Required Pages

`dashboard/index.html` shows:
- topic, status, target, current phase, iteration, last heartbeat;
- 12-phase timeline;
- gate board;
- current conclusions grouped by taxonomy cell;
- latest review or synthesis summary;
- next action;
- risks, blockers, stale count, and unresolved major weaknesses;
- links to final artifacts and raw state files.

Each phase page shows:
- phase purpose;
- inputs and outputs;
- status and completion checks;
- phase summary if present;
- current conclusions;
- recent `level=decision` logs;
- links to raw artifacts.

## Phase Summary Records

Workers may append durable summaries to `state/phase_summaries.jsonl`:

```json
{
  "phase": "phase_2_recall",
  "ts": "2026-06-20T08:00:00+00:00",
  "summary": "Recall expanded from arXiv search into DBLP venue sweep.",
  "conclusions": ["The current candidate pool is strongest for tool-use agents."],
  "open_questions": ["OpenReview status remains unverified for several papers."],
  "evidence_paths": ["state/papers.jsonl", "logs/search.jsonl"]
}
```

Do not duplicate full logs here; write concise human summaries only.

## Display Rules

- Escape all user, source, claim, review, and log text before rendering HTML.
- Use static HTML and embedded CSS only.
- Do not add JavaScript or network assets in the first implementation.
- Use fixed status terms: `not_started`, `active`, `complete`, `stale`, `blocked`.
- Preserve raw JSONL and Markdown files as the source of truth.
