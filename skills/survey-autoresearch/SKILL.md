---
name: survey-autoresearch
description: Run unattended literature review and survey-writing workflows with persistent state, verified sources, paper-level understanding, evidence-grounded synthesis, argument-first article planning, and publication-quality review output.
---

# Survey AutoResearch

Use this skill when the user asks for a literature review, survey paper, research landscape, related work section, annotated bibliography, or evidence-backed field overview that should run as a persistent research workflow rather than a one-shot answer.

The workflow has one public path:

`init_task.py -> runner.py --run-until-complete -> task_queue.py for requested workers -> gate_engine.py -> promote_survey_release.py`

Final `outputs/survey.md` and `outputs/survey.html` are release-only artifacts. They must not exist, or must be quarantined, until all phase gates and Gate 7 pass and `promote_survey_release.py` promotes the current candidate.

The v2 core is intentionally smaller than the internal helper graph:

`topic boundary -> corpus anti-drift selection -> paper_cards -> knowledge tree/taxonomy -> survey spine -> evidence-backed draft -> review repair loop -> release`

Treat `state/run_state.json`, `state/tasks.jsonl`, `state/paper_cards/`, `outputs/knowledge_tree.yml`, `state/spine_decision.md`, and `state/failure_ledger.jsonl` as the public research spine. Legacy JSONL files remain compatibility inputs for validators, but downstream writing and repair should reason from the spine, not from ad hoc runtime packets.

## Main Loop

1. Initialize a run with `scripts/init_task.py`.
2. Resume work only through `scripts/runner.py --task-dir <run> --target <target> --run-until-complete`.
3. If the runner returns a worker-spawn status, run `scripts/task_queue.py --task-dir <run> --collect-pending` or inspect the normalized `state/tasks.jsonl`.
4. Spawn only the pending requests returned by the task queue with `multi_agent_v1.spawn_agent(fork_context=false)`.
5. Record each spawned session with `task_queue.py --mark-spawned <request-id> --agent-id <subagent-session-id>`.
6. Save each worker response exactly as returned and record it with `task_queue.py --record-agent-output <request-id> --output-file <file>`.
7. Rerun `runner.py --run-until-complete` until completion, quality-limited stop, or a real blocker.

If the current Codex runtime cannot spawn subagents, report `blocked_subagent_spawn_required`; do not claim completion. Python helpers may prepare batches, validate schemas, merge worker output, and record hashes; they must not fabricate discovery results, semantic topic audits, topic second audits, paper-understanding cards, reviewer reports, or repair results.

## Stop Conditions

Stop only when one of these is true:

- `survey_driver.py`, `gate7_driver.py`, or a collect-status command returns `complete`.
- The run is explicitly `quality_limited`.
- Fresh subagents or required source documents are unavailable.
- The same non-worker blocker recurs for three consecutive driver passes with no persisted progress. Worker-spawn states must first rebuild `runtime_active_intent.json` and expose dispatcher pending/spawned/result status.

Do not stop at prompt generation, worker packets, runtime action files, repair notes, stale summaries, targeted rereview requests, or reviewer routing. Reviewer routing back to an earlier phase is a rollback action, not a stop condition.

## Phase Barriers

The runner enforces this gated chain:

`topic/corpus boundary -> source identity + topic relevance audit -> A/B full-text understanding -> paper_cards -> knowledge tree/taxonomy -> survey spine -> section evidence plans -> survey candidate -> expert review -> release promotion`

Run `scripts/gate_engine.py --task-dir <run> --target <target> --phase <phase>` for manual checks, or `--explain` / `--route-repair` for compact next-step guidance. If a phase fails, repair that phase instead of creating downstream artifacts.

Important barriers:

- Discovery is worker-produced when starting from an empty run. The worker returns real `raw_candidates`, `search_routes`, `lqs_scores`, and `corpus_expansion`; Python validates sufficiency but does not invent papers.
- Topic profile is worker-produced before discovery. It defines positive anchors, negative anchors, allowed background, seed queries, and acceptance rubrics; discovery should follow that boundary rather than searching from the raw topic string alone.
- Source verification is not just DOI or metadata verification. Full and CSUR runs require worker-produced `state/topic_relevance_audit.jsonl` before A/B full-text reading.
- High-risk A/B core topic decisions require independent worker second audit in `state/topic_relevance_second_audits.jsonl`.
- A/B papers must be topic-audit qualified, verified, and full-text readable. Broad LLM, generic MLLM, education, medical, RAG, or XAI papers cannot enter A/B unless the audit directly supports the topic boundary.
- Paper understanding requires `state/full_text_sources.jsonl`, compatibility `state/paper_mechanism_cards.jsonl`, and mirrored `state/paper_cards/{paper_id}.json` for every A/B paper. Every paper card must say how the paper changes the knowledge tree or survey argument.
- Knowledge-tree and spine work must be grounded in paper cards plus related-survey taxonomy alignment. A section spine that cannot be traced to paper cards, related surveys, and evidence spans is a blocked draft, not a weak pass.
- Expert review requires five fresh independent reviewers when subagents are available. Gate 7 repair runs through phase-ordered repair batches and must record validated repair and regression results before rerun.
- Major review failures must be copied into `state/failure_ledger.jsonl` with root cause, rollback route, failed assumption, and prevention rule. Repeated repairs should consult this ledger before drafting again.

## Public Commands

| Purpose | Command |
| --- | --- |
| Initialize a run | `python3 scripts/init_task.py --base-dir <base> --topic "<topic>" --slug <slug> --target <short|full|csur>` |
| Resume or drive the workflow | `python3 scripts/runner.py --task-dir <run> --target <target> --run-until-complete` |
| Sync compact run state | `python3 scripts/run_state.py --task-dir <run> --target <target> --sync` |
| Sync compact task queue | `python3 scripts/task_queue.py --task-dir <run> --sync` |
| Prepare/record topic profile | `python3 scripts/topic_profile.py --task-dir <run> --prepare` / `--record-result <json>` |
| Collect pending worker requests | `python3 scripts/task_queue.py --task-dir <run> --collect-pending` |
| Record spawned worker session | `python3 scripts/task_queue.py --task-dir <run> --mark-spawned <request-id> --agent-id <session-id>` |
| Record worker output | `python3 scripts/task_queue.py --task-dir <run> --record-agent-output <request-id> --output-file <file>` |
| Validate, explain, or route gates | `python3 scripts/gate_engine.py --task-dir <run> --target <target> [--phase <phase>|--explain|--route-repair]` |
| Mirror paper cards | `python3 scripts/paper_card_store.py --task-dir <run> --mirror` |
| Record review failures | `python3 scripts/failure_ledger.py --task-dir <run> --append-from-adjudication` |
| Promote final survey | `python3 scripts/promote_survey_release.py --task-dir <run> --target <target>` |

All other scripts are internal helpers unless a contract below explicitly says otherwise. In particular, `survey_driver.py`, `phase_gate.py`, `gate_check.py`, `runtime_dispatcher.py`, topic-relevance, paper-understanding, and Gate 7 runtime executors prepare or record compatibility state; `runner.py`, `gate_engine.py`, and `task_queue.py` are the public orchestration facade.

## Required Contracts

Read the relevant contract before touching that layer:

- Runtime dispatch, active intent, phase generation, stale requests, and worker result recording: `references/runtime_contract.md`.
- Survey type and artifact choices: `references/survey_type_contract.md`.
- Source identity, topic relevance, evidence spans, and coverage: `references/evidence_contract.md`.
- Paper-level full-text understanding: `references/paper_understanding_contract.md`.
- Knowledge tree, related-survey taxonomy comparison, and spine decision: `references/knowledge_tree_contract.md`.
- Scenario definitions: `references/scenario_definition_contract.md`.
- Synthesis dossiers, related-survey matrix, and argument graph: `references/synthesis_contract.md`.
- Article plan, appendix boundary, and publication prose: `references/article_contract.md`.
- Expert review scoring, adjudication, repair routing, and release criteria: `references/expert_gate_contract.md`.
- CSUR style: `references/csur_patterns.md` and `references/csur_official_exemplars.yml`.

## Article Boundary

`survey_candidate.md` and final `survey.md` must not expose workflow internals: survey-type routing labels, A/B/C labels, run counts, state-file names, gate names, paper IDs such as `P001`, repair notes, reviewer comments, or scaffold phrases. Search protocol, coverage tables, and evidence logistics belong in `outputs/appendix.md` or `outputs/final_report.md`.

## Completion

Call the survey complete only when `outputs/release_manifest.json` has `released: true`, hashes matching the current candidate plus final `survey.md/html`, and a current gate hash proving the present state still passes. Otherwise call it a candidate, draft, blocked run, or automatic-check artifact.

The default target is `full`. Use `short` only when the user explicitly asks for a short or quick draft; even short runs must pass the minimum discovery, source, and evidence gates.
