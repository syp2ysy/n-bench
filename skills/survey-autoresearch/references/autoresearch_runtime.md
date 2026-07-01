# AutoResearch Runtime Protocol

Use this reference whenever a survey run needs to work unattended for many hours.

## Failure Modes To Prevent

1. Cognitive loop: repeated similar attempts with diminishing returns.
2. Stalling: the worker summarizes and waits for the user.
3. Runtime fragility: context compaction, closed sessions, or lost timers kill the loop silently.

## Required Constraints

- Zero interaction after start.
- Ready means execute.
- Callback means report alive.
- State lives in files, not conversation memory.
- Guardian and worker responsibilities stay separate.
- Fresh work sessions receive curated state files; do not resume from long chat context.
- Citation-like content is verified in small batches, not saved for the end.

## Liveness

Every callback starts by updating:

```bash
python3 scripts/heartbeat.py --task-dir <run_dir> --source <worker_name>
```

The heartbeat worker may only:
- check `last_seen`;
- restart or nudge a stale loop;
- log liveness decisions.

It must not edit `papers.jsonl`, `claims.jsonl`, `taxonomy.md`, outputs, or review decisions.

Use patrol checks for unattended runs:

```bash
python3 scripts/patrol.py --base-dir runs --stale-after-minutes 120
```

Exit code `1` means at least one task is stale and needs nudge, restart, pivot, or a blocked report.

## Stall Detection

An iteration is stale when it produces none of these:
- new candidate papers;
- new LQS-scored papers;
- new A/B citation-plan entries;
- new verified citations;
- new evidence-backed claims;
- improved taxonomy coverage;
- a newly passed gate;
- a resolved major review weakness.

Rules:
- stale iteration: `stale_count += 1`;
- `stale_count >= 2`: force a structural pivot;
- `stale_count >= 4`: mark structurally stuck, write a Blocked report, and continue only if a new structural route exists.

## Structural Pivots

Do not tune the same tactic harder. Change the frame:

| Stale frame | Pivot |
| --- | --- |
| keyword search | backward and forward citation snowball |
| arXiv search | DBLP, OpenReview, venue proceedings |
| method list | benchmark or failure-mode taxonomy |
| recent-only sweep | seminal-paper seed expansion |
| prose polishing | evidence table repair |
| broad survey | contradiction-first search |
| same field | adjacent-field analogy |

## Work Session Caps

One worker pass should have:
- one explicit deliverable;
- file write limits;
- completion criteria;
- a maximum of 15 reasoning/action rounds or about 30 minutes before returning state.

Fresh workers should receive only curated state files, never the whole prior conversation.

## Batch Verification

For literature or citation-heavy work, verify every batch of about 20 retained or cited records before expanding further. Append verification evidence to `logs/verification.jsonl`, either as per-paper records with `paper_id`, `verified`, and `checks`, or as explicit `citation_batch_verified` records.

Do not defer all citation verification to the final pass. Batch verification prevents large hallucinated bibliographies from becoming expensive to unwind.
