---
name: survey-autoresearch
description: Run unattended literature review and survey-writing workflows with persistent state, verified sources, paper-level understanding, evidence-grounded synthesis, argument-first article planning, and publication-quality review output.
---

# Survey AutoResearch

Use this skill when the user asks for a literature review, survey paper, research landscape, related work section, annotated bibliography, or evidence-backed field overview that should run as a long-horizon research workflow rather than a one-shot answer.

The workflow has one gated core chain:

`high-recall discovery -> source truth -> full-text evidence -> A/B paper understanding completion -> contribution tree -> scenario definitions -> field synthesis -> argument graph -> section evidence re-check -> publication article`

The final `outputs/review.md` is an article. It must not read like a workflow report, evidence report, appendix, checklist, or state-file dump.

## Non-Negotiable Runtime

- Persist meaningful state under the task `state/`, `logs/`, and `outputs/` directories.
- Start every major pass from state files, not conversation memory.
- Do not ask whether to continue between phases.
- Do not enter a phase until `scripts/phase_gate.py` passes the previous phase.
- If a run stalls, change structure rather than repeating the same search or synthesis tactic.
- Keep heartbeat/patrol workers separate from research workers; they may inspect liveness but must not edit research content.
- Verify citation identity continuously and record verification evidence.
- Treat external AutoResearch projects as design references, not authority.

Read `references/runtime_contract.md` before long-running work.

## Phase Barriers

1. **Task lock and survey type**: write `state/task_spec.md` and `state/survey_type_plan.yml`.
2. **High-recall discovery**: collect broad candidates in `state/raw_candidates.jsonl`, `state/search_routes.jsonl`, `state/lqs_scores.jsonl`, and `state/corpus_expansion.json`; this phase must pass before source verification or citation planning.
3. **Source verification and citation depth**: write `state/papers.jsonl` and `state/citation_plan.jsonl`; every retained paper must point back to a raw candidate.
4. **A/B paper understanding completion**: write `state/full_text_sources.jsonl` and `state/paper_mechanism_cards.jsonl` for every A/B paper; this phase must pass before contribution abstraction, synthesis, argument graph, article plan, or drafting.
5. **Contribution abstraction**: write `state/paper_contribution_statements.jsonl` and `outputs/contribution_tree.yml`.
6. **Scenario/domain definitions**: write `state/scenario_definitions.yml`.
7. **Field synthesis**: write method-family dossiers, benchmark dossiers, related-survey matrix, and `state/claim_evidence_spans.jsonl`.
8. **Story skeleton**: write `state/argument_graph.yml`.
9. **Section source re-check and drafting**: write `state/section_evidence_plans.jsonl`, `outputs/article_plan.md`, `outputs/review_body_draft.md`, final `outputs/review.md`, and `outputs/appendix.md`.
10. **Expert review and repair**: generate independent expert review reports, log reviewer invocations, close routed weaknesses with repair/regression evidence, and rerun gates until complete or precisely blocked.

Run `scripts/phase_gate.py --task-dir <run> --target <target> --phase <phase>` at each barrier. If a phase fails, repair that phase instead of creating downstream artifacts. If A/B paper understanding fails and downstream synthesis/article files already exist, the run is invalid until the A/B cards are completed and the phase gate passes.

## Required Contracts

- Survey type and topic-specific artifact selection: `references/survey_type_contract.md`.
- Scenario/domain definitions for topic-specific meanings: `references/scenario_definition_contract.md`.
- Source identity, evidence spans, and coverage: `references/evidence_contract.md`.
- Paper-level scientific contribution extraction: `references/paper_understanding_contract.md`.
- Synthesis dossiers and argument graph: `references/synthesis_contract.md`.
- Article plan, appendix boundary, and publication prose: `references/article_contract.md`.
- Final review standards and repair routing: `references/review_contract.md`.
- Independent expert review scoring and weakness routing: `references/expert_review_contract.md`.
- CSUR style and official exemplar use for `target=csur`: `references/csur_patterns.md` and `references/csur_official_exemplars.yml`.

## Final Summary Gates

`scripts/gate_check.py` is a final summary check, not the phase controller. Completion requires all phase barriers plus:

1. **Source Identity Gate**: A/B papers are fully verified; C papers meet the target verification rate; unverified papers do not support article claims.
2. **A/B Paper Understanding Completion Gate**: every A/B paper has a full-text mechanism card with nonempty substantive fields, source/excerpt audit, motivation, task/problem, benchmark/environment, implementation, experiment, result, limitation, relation-to-prior-work, and overclaim boundaries.
3. **Claim-Evidence Gate**: every important claim traces to source-backed evidence spans and section evidence plans; strong claims need quoted/extracted evidence and claim strength does not exceed evidence strength.
4. **Coverage Gate**: discovery sufficiency, corpus expansion, retained literature breadth, family, benchmark, related-survey, and scenario gaps are all recorded and valid.
5. **Argument Graph Gate**: contribution tree, scenario definitions, synthesis dossiers, story skeleton, and section evidence plans jointly support the article.
6. **Article Quality Gate**: `review.md` and rendered publication artifacts are publication prose with no raw artifacts, internal methodology, run metadata, unsupported factual claims, repeated template sections, or un-interpreted tables.
7. **Expert Review Gate**: independent reviewer reports meet the target score threshold, have invocation evidence, and close all major weaknesses with repair/regression evidence.

The default target is `full`. Use `short` only when the user explicitly asks for a short or quick draft; even short runs must pass minimum discovery and evidence checks.

## Survey-Type Defaults

- `system-object`: components/interfaces/lifecycle/evaluation; use component dossiers only for this type or when selected as a secondary lens.
- `method-family`: assumptions, method families, evaluation metrics, applications, and limitations.
- `benchmark/evaluation`: capabilities, protocols, metrics, baselines, confounders, and missing tests.
- `risk/threat`: assets, threat model, attack surface, defenses, evaluation, and governance gaps.
- `application-domain`: domain tasks, data, workflows, methods, deployment constraints, and evaluation.

Hybrid topics must choose one primary type and explicit secondary lenses in `state/survey_type_plan.yml`.

## Article Boundary

`review.md` must not include:

- survey-type routing labels or internal template decisions;
- A/B/C evidence labels, run counts, search routes, or candidate counts;
- state-file names, gate names, extraction-card fields, repair notes, or workflow commentary;
- phrasing such as "本文采用 system-object survey 的结构", "本节面向", "下面的表", "该工作在本文中被读作", "好的综述", or equivalent scaffold language.

Transparent search protocol, broad coverage tables, and evidence logistics belong in `outputs/appendix.md` or `outputs/final_report.md`, not in the article body.

## Script Helpers

- `scripts/init_task.py`: create the new state/output skeleton.
- `scripts/heartbeat.py`, `scripts/patrol.py`: runtime liveness helpers.
- `scripts/score_lqs.py`: survey-role scoring for candidate triage.
- `scripts/phase_gate.py`: phase barrier controller.
- `scripts/verify_sources.py`: source identity validation.
- `scripts/validate_paper_understanding.py`: paper mechanism-card validation.
- `scripts/validate_claim_evidence.py`: claim-to-evidence validation.
- `scripts/validate_coverage.py`: discovery, corpus-expansion, candidate-linkage, and retained-coverage validator.
- `scripts/build_contribution_tree.py`: contribution-statement and contribution-tree validator.
- `scripts/validate_scenario_definitions.py`: scenario/domain definition validation.
- `scripts/validate_synthesis_dossiers.py`: method-family and benchmark dossier validation.
- `scripts/validate_argument_graph.py`: argument graph validation.
- `scripts/validate_section_evidence_plans.py`: section source re-check validation.
- `scripts/validate_article_quality.py`: article boundary, prose, repetition, section, table, and factual-support checks.
- `scripts/expert_review_gate.py`: independent expert-review score, persona, weakness, and stop-rule validation.
- `scripts/gate_check.py`: gate orchestrator.
- `scripts/render_dashboard.py`: HTML progress dashboard.
- `scripts/normalize_bib.py`: BibTeX normalization.

## Final Outputs

Minimum full/CSUR outputs:

- `outputs/review.md`
- `outputs/appendix.md`
- `outputs/references.bib`
- `outputs/coverage_matrix.md`
- `outputs/article_plan.md`
- `outputs/final_report.md`

CSUR runs additionally require CSUR exemplar notes and paragraph-style guidance recorded in state or appendix, but those notes must not leak into `review.md`.
