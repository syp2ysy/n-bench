---
name: survey-autoresearch
description: Run unattended literature review and survey-writing workflows with persistent state, verified sources, paper-level understanding, evidence-grounded synthesis, argument-first article planning, and publication-quality review output.
---

# Survey AutoResearch

Use this skill when the user asks for a literature review, survey paper, research landscape, related work section, annotated bibliography, or evidence-backed field overview that should run as a persistent research workflow rather than a one-shot answer.

The workflow has one public path:

`init_task.py -> survey_driver.py --run-until-complete -> runtime_dispatcher.py for requested workers -> phase_gate.py/gate_check.py -> promote_survey_release.py`

Final `outputs/survey.md` and `outputs/survey.html` are release-only artifacts. They must not exist, or must be quarantined, until all phase gates and Gate 7 pass and `promote_survey_release.py` promotes the current candidate.

## Main Loop

1. Initialize a run with `scripts/init_task.py`.
2. Resume work only through `scripts/survey_driver.py --task-dir <run> --target <target> --run-until-complete`.
3. If the driver returns a worker-spawn status, run `scripts/runtime_dispatcher.py --task-dir <run> --collect-pending`.
4. Spawn only the pending requests returned by the dispatcher with `multi_agent_v1.spawn_agent(fork_context=false)`.
5. Record each spawned session with `runtime_dispatcher.py --mark-spawned <request-id> --agent-id <subagent-session-id>`.
6. Save each worker response exactly as returned and record it with `runtime_dispatcher.py --record-agent-output <request-id> --output-file <file>`.
7. Rerun `survey_driver.py --run-until-complete` until completion, quality-limited stop, or a real blocker.

If the current Codex runtime cannot spawn subagents, report `blocked_subagent_spawn_required`; do not claim completion. Python helpers may prepare batches, validate schemas, merge worker output, and record hashes; they must not fabricate discovery results, semantic topic audits, topic second audits, paper-understanding cards, reviewer reports, or repair results.

## Stop Conditions

Stop only when one of these is true:

- `survey_driver.py`, `gate7_driver.py`, or a collect-status command returns `complete`.
- The run is explicitly `quality_limited`.
- Fresh subagents or required source documents are unavailable.
- The same blocker recurs for three consecutive driver passes with no persisted progress.

Do not stop at prompt generation, worker packets, runtime action files, repair notes, stale summaries, targeted rereview requests, or reviewer routing. Reviewer routing back to an earlier phase is a rollback action, not a stop condition.

## Phase Barriers

The driver enforces this gated chain:

`high-recall discovery -> source identity + topic relevance audit -> A/B full-text understanding -> contribution tree -> scenario definitions -> synthesis dossiers -> argument graph -> section evidence plans -> survey candidate -> expert review -> release promotion`

Run `scripts/phase_gate.py --task-dir <run> --target <target> --phase <phase>` for manual checks. If a phase fails, repair that phase instead of creating downstream artifacts.

Important barriers:

- Discovery is worker-produced when starting from an empty run. The worker returns real `raw_candidates`, `search_routes`, `lqs_scores`, and `corpus_expansion`; Python validates sufficiency but does not invent papers.
- Source verification is not just DOI or metadata verification. Full and CSUR runs require worker-produced `state/topic_relevance_audit.jsonl` before A/B full-text reading.
- High-risk A/B core topic decisions require independent worker second audit in `state/topic_relevance_second_audits.jsonl`.
- A/B papers must be topic-audit qualified, verified, and full-text readable. Broad LLM, generic MLLM, education, medical, RAG, or XAI papers cannot enter A/B unless the audit directly supports the topic boundary.
- Paper understanding requires `state/full_text_sources.jsonl` and `state/paper_mechanism_cards.jsonl` for every A/B paper.
- Expert review requires five fresh independent reviewers when subagents are available. Gate 7 repair runs through phase-ordered repair batches and must record validated repair and regression results before rerun.

## Public Commands

| Purpose | Command |
| --- | --- |
| Initialize a run | `python3 scripts/init_task.py --base-dir <base> --topic "<topic>" --slug <slug> --target <short|full|csur>` |
| Resume or drive the workflow | `python3 scripts/survey_driver.py --task-dir <run> --target <target> --run-until-complete` |
| Collect pending worker requests | `python3 scripts/runtime_dispatcher.py --task-dir <run> --collect-pending` |
| Record spawned worker session | `python3 scripts/runtime_dispatcher.py --task-dir <run> --mark-spawned <request-id> --agent-id <session-id>` |
| Record worker output | `python3 scripts/runtime_dispatcher.py --task-dir <run> --record-agent-output <request-id> --output-file <file>` |
| Validate one phase | `python3 scripts/phase_gate.py --task-dir <run> --target <target> --phase <phase>` |
| Run final summary gates | `python3 scripts/gate_check.py --task-dir <run> --target <target>` |
| Promote final survey | `python3 scripts/promote_survey_release.py --task-dir <run> --target <target>` |

All other scripts are internal helpers unless a contract below explicitly says otherwise. In particular, topic-relevance, paper-understanding, and Gate 7 runtime executors prepare or record batches; `runtime_dispatcher.py` is the only public main-agent queue consumer.

## Required Contracts

Read the relevant contract before touching that layer:

- Runtime dispatch, active intent, phase generation, stale requests, and worker result recording: `references/runtime_contract.md`.
- Survey type and artifact choices: `references/survey_type_contract.md`.
- Source identity, topic relevance, evidence spans, and coverage: `references/evidence_contract.md`.
- Paper-level full-text understanding: `references/paper_understanding_contract.md`.
- Scenario definitions: `references/scenario_definition_contract.md`.
- Synthesis dossiers, related-survey matrix, and argument graph: `references/synthesis_contract.md`.
- Article plan, appendix boundary, and publication prose: `references/article_contract.md`.
- Expert review scoring, adjudication, repair routing, and release criteria: `references/expert_gate_contract.md`.
- CSUR style: `references/csur_patterns.md` and `references/csur_official_exemplars.yml`.

## Article Boundary

`survey_candidate.md` and final `survey.md` must not expose workflow internals: survey-type routing labels, A/B/C labels, run counts, state-file names, gate names, paper IDs such as `P001`, repair notes, reviewer comments, or scaffold phrases. Search protocol, coverage tables, and evidence logistics belong in `outputs/appendix.md` or `outputs/final_report.md`.

## Completion

Call the survey complete only when `outputs/release_manifest.json` has `released: true` and hashes matching the current candidate plus final `survey.md/html`. Otherwise call it a candidate, draft, blocked run, or automatic-check artifact.

The default target is `full`. Use `short` only when the user explicitly asks for a short or quick draft; even short runs must pass the minimum discovery, source, and evidence gates.
