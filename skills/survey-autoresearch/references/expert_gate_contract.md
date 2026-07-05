# Expert Review Contract

Gate 7 is the final maturity gate for `target=full` and `target=csur`. It is not self-evaluation and not a score-form check.

## Required Order

1. Gate 1-6 pass.
2. Freeze `outputs/survey_candidate.md`, `outputs/appendix.md`, `state/argument_graph.yml`, and `state/section_evidence_plans.jsonl` in `state/expert_review_round_status.json`.
3. Dispatch five independent reviewers and record `state/expert_review_invocations.jsonl`.
4. Wait until all five reports are returned. Do not repair while reports are still missing.
5. Adjudicate all major/blocking weaknesses in `state/expert_review_adjudication.json`.
6. Repair each canonical weakness only after rechecking evidence.
7. If the repair is local prose/artifact cleanup, run targeted rereview for each repaired major/blocking weakness. If the repair touches evidence/state, the article spine, paper understanding, claim evidence, section evidence plans, synthesis, coverage, source verification, argument graph, or benchmark dossiers, archive the old round and start a new full five-reviewer Gate 7 round.

In Codex, dispatch reviewers with `multi_agent_v1.spawn_agent` using `fork_context=false`. Record each returned subagent id as `subagent_session_id`. If fresh subagents or fresh contexts are unavailable, mark the run blocked; do not fabricate reviewer reports.

`gate7_driver.py --run-until-complete` is the Gate 7 orchestrator. `gate7_loop.py` manages freeze, reviewer prompts, report recording, adjudication status, round reset, and rereview status. `build_repair_plan.py` converts adjudicated weaknesses into route-specific rollback work and writes `state/gate7_repair_plan.json` with `schema_version` plus a `summary` of repair counts, rollback phases, and rerun policy. `gate7_runtime_executor.py` consumes `state/gate7_runtime_action.json`, groups repair items into phase-ordered batches in `state/gate7_repair_batches.json`, writes repair-agent spawn requests, validates repair-agent results, and records repairs plus regression checks through the Gate 7 recording APIs. `runtime_dispatcher.py` is the main-agent queue consumer: it normalizes Gate 7 reviewer, repair-agent, and targeted-rereviewer requests from `state/gate7_spawn_requests.json`, tracks spawned subagents, parses returned JSON, and routes each result to `gate7_loop.py` or `gate7_runtime_executor.py`. `phase_gate.py`, `gate7_driver.py`, and `gate7_runtime_executor.py --collect-status` use a stable status envelope with `schema_version`, `component`, `status`, `next_action`, `terminal`, `blocked`, `blocked_by_phase`, `active_batch_id`, and `summary`. Runtime action files and spawn requests are requests, not evidence of repair. `run_expert_reviews.py --dispatch-packets-only` may prepare external packets when subagents are unavailable. Packet preparation is not independent review. A packet-only round remains blocked until real fresh-context reviewer invocations are recorded.

If `gate7_loop.py --collect-status` returns `spawn_reviewers`, `wait_all_reports`, `adjudicate`, `repair_with_evidence`, `spawn_repair_agents`, `run_regression_checks`, `reset_full_review_round`, `spawn_targeted_rereviewers`, `rerun_gate_check`, or `promote_release`, the main agent or driver must perform that action before claiming the survey is complete. Reviewer routing back to an earlier phase is a rollback action, not a stop condition. The loop is not complete at prompt generation, adjudication, repair-plan creation, runtime repair requests, regression notes, targeted rereview, or round reset; it is complete only when collect-status returns `complete`. If `review_iteration_status.json` marks the run `quality_limited`, the driver returns `quality_limited_stop`, not completion.

Runtime repair batches are ordered as `source_verification/coverage -> paper_understanding -> synthesis/claim_evidence/benchmark_dossiers -> argument_graph/section_evidence_plan -> article_quality`. Only the earliest unresolved batch may be active. Downstream prose repair must wait until upstream source, paper-understanding, claim-evidence, section-plan, argument, or synthesis repair has been recorded and validated.

Each repair-agent spawn request must expose the handoff contract explicitly: `result_schema_version`, `required_result_keys`, `expected_weakness_ids`, `expected_changed_artifacts`, and `expected_acceptance_validators`. A repair agent must satisfy those fields in its returned JSON; a prompt or spawn request alone never advances a batch.

## Required Reviewers

Full/CSUR runs require exactly these persona roles:

- Domain Expert Reviewer
- Survey Architect Reviewer
- Evidence/Factuality Reviewer
- Newcomer/Tutorial Reviewer
- Style/Publication Reviewer

Each invocation needs `review_round_id`, `reviewer_id`, `persona`, `fresh_context: true`, `subagent_session_id`, article/evidence inputs, forbidden previous reports and repair actions, output target, and `status: returned`.

## Report Contract

Each row in `state/expert_review_reports.jsonl` needs:

- `reviewer_id`, `persona`, `overall_score`, `pass_recommendation`
- `dimension_scores` and `dimension_audits`
- `review_trace`, `sections_reviewed`, `section_comments`, `quoted_evidence_from_review`
- persona-specific audits: paper mechanism, flow/taxonomy, claim/citation, tutorial, or style audit
- `blocking_weaknesses`

`dimension_audits` must independently cover:

- narrative coherence
- paper understanding depth
- field-native taxonomy quality
- method taxonomy quality
- benchmark/evaluation quality
- evidence/citation accuracy
- synthesis not catalog
- information density
- publication prose
- newcomer value
- expert value

Each dimension audit needs score, verdict, evidence quotes, failure cases, why it matters, repair recommendation, and route. A dimension below the target floor creates a major weakness.

Reviewers must flag expansion that adds words without new evidence, clearer mechanism, sharper comparison, benchmark context, limitation, or implication.

Persona focus is mandatory:

- Domain Expert Reviewer audits named-paper citation alignment and paper-card field-evidence consistency against full-text evidence.
- Survey Architect Reviewer audits whether the taxonomy is aligned with existing surveys, whether deltas are justified, and whether core-family coverage supports the article spine.
- Evidence/Factuality Reviewer audits strong claims against source spans and citation windows, including unknown method, system, and benchmark short names near citations.
- Newcomer/Tutorial Reviewer audits whether the article teaches the field through paper comparison rather than author commentary.
- Style/Publication Reviewer audits padding, conclusion order, scaffold leakage, table interpretation, rendered article boundary, candidate/final release boundary, and absence of legacy review-stem publication artifacts.

Thresholds:

- `full`: median overall >= 8.5 and every dimension median >= 8.0.
- `csur`: median overall >= 9.0 and every dimension median >= 8.5.

## Adjudication And Repair

`state/expert_review_adjudication.json` must map reviewer weaknesses into canonical weaknesses with `schema_version`, `review_reports_hash`, severity, source reviewers, source weakness ids, affected sections, affected papers, affected claims, route, required evidence check, and repair acceptance criteria. Reviewer-local ids such as `BW1` are not global ids; source ids must be recorded as `reviewer_id:weakness_id`, while canonical ids use `CW001`, `CW002`, and so on. Empty `affected_papers` or `affected_claims` lists are valid for article/style weaknesses, but the keys must exist and be lists. Old adjudications without the current schema, without a matching report hash, with bare local source ids, or with missing route-specific evidence requirements must be rebuilt before repair planning. Unadjudicated major weaknesses fail Gate 7.

`state/repair_actions.jsonl` must record evidence-first repair. Use `gate7_loop.py --record-repair` so the repair is tied to the current `survey_candidate.md` hash. A repair for a major/blocking weakness must change the candidate hash relative to the frozen article hash; if the reviewer route requires returning to paper understanding, coverage, or claim evidence, `changed_artifacts` must name the repaired state/evidence files instead of pretending prose-only repair is enough.

When repair is performed by a repair agent, record the returned JSON with `gate7_runtime_executor.py --record-result <json> --subagent-session-id <id>`. The result must include `batch_id`, `status`, `changed_artifacts`, before/after artifact hashes, repair records, regression checks, validator results, and remaining blockers. For `status=resolved`, `repair_records[*].weakness_id` and `regression_checks[*].weakness_id` must exactly cover the active batch's canonical weakness ids, with no missing, extra, or duplicate ids. `changed_artifacts`, `artifact_hashes_before`, and `artifact_hashes_after` must cover every active batch changed artifact, and `artifact_hashes_after` must match the repaired files or directories on disk. `validator_results` must include one passed result for every active batch `acceptance_validators` entry, named as `{"validator": "<acceptance_validator>", "status": "passed", "command": "...", "result": "..."}` or with `name` instead of `validator`. The executor rejects blocked downstream batches, invalid validator results, duplicate or partial batch coverage, stale artifact hashes, and results that do not produce normal repair/regression records.

- `evidence_rechecked` from the relevant source: paper mechanism cards, claim evidence spans, contribution tree, argument graph, section evidence plans, benchmark dossiers, or full-text sources.
- changed artifacts and repair action.
- claim strength changes and newly modified claims.
- status: resolved, accepted limitation, or unresolved.

If the repair adds or strengthens a claim, update `state/claim_evidence_spans.jsonl` before revising the article. If evidence is insufficient, downgrade the wording or route back to source verification or paper understanding.

`state/regression_checks.jsonl` must contain one passing check for each repaired major/blocking weakness. Record these with `gate7_loop.py --record-regression-check`; each record must name the actual command or check performed, status, and result. Failing or missing regression checks keep the loop in `run_regression_checks`.

`state/targeted_rereview_reports.jsonl` must verify each repaired major/blocking weakness against changed artifacts and checked evidence refs. Verdict must be `resolved`, with `fresh_context: true`, a nonempty `subagent_session_id`, a matching article hash, and no introduced regression.

Targeted rereview is also a fresh-context reviewer pass. Use `gate7_loop.py --make-targeted-rereview-prompts`, spawn those prompts with `fork_context=false`, and record returned JSON with `gate7_loop.py --record-targeted-rereview`. The main agent must not write targeted rereview reports itself.

After targeted rereview is resolved, rerun `gate_check.py --output state/gate_check_full.json`. `collect-status` must see a fresh gate summary whose candidate hash matches the current `outputs/survey_candidate.md`; stale summaries must lead back to `rerun_gate_check`, not promotion.

For `rerun_policy=full_gate7_round`, completed repairs and passing regression checks must not lead to targeted rereview. The driver archives active Gate 7 files under `state/gate7_rounds/<round>/`, clears active reports, invocations, adjudication, repairs, regression checks, and targeted rereviews, freezes the changed candidate, and spawns five fresh full reviewers.

After promotion, `collect-status` may return `complete` only when `outputs/release_manifest.json` has `released: true`, `released_at`, `gate_check_hash`, and hashes matching the current `survey_candidate.md`, `survey.md`, and `survey.html`. A stale or incomplete release manifest is not completion.

## Weakness Routes

- citation/source error -> source verification or claim evidence
- paper mechanism unclear -> paper understanding
- benchmark misread -> benchmark dossiers
- taxonomy/story weak -> contribution tree, synthesis dossiers, and argument graph
- section reads like a paper list -> section evidence plan
- artifact/process language -> article quality
- shallow coverage -> discovery and coverage

Every full/CSUR Gate 7 round must append `state/expert_review_round_history.jsonl` with candidate hash, median score, dimension medians, canonical weaknesses, route counts, rerun policy, and major-rebuild flag. `state/review_iteration_status.json` is derived from that history. If two consecutive near-threshold rounds improve by less than 0.2 while still below threshold, mark the run quality-limited instead of pretending completion. Low-score failures, broad evidence-layer failures, and routes through paper understanding, claim evidence, source verification, coverage, synthesis, argument graph, section evidence plans, or benchmark dossiers require rollback repair and a new full Gate 7 round, not targeted rereview. Only a Gate-7-passing run may be promoted to final `outputs/survey.md/html`.
