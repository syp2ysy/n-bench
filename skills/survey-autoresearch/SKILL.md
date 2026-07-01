---
name: survey-autoresearch
description: Run unattended long-horizon literature review and survey-writing workflows. Use when the user asks Codex to produce a literature review, survey paper, related work section, research landscape, annotated bibliography, or evidence-backed field overview that should keep working for many hours, persist state, verify citations, build taxonomy, and revise until quality gates pass.
---

# Survey AutoResearch

Use this skill to run a long-horizon survey-writing task as an AutoResearch loop, not as a one-shot answer. The task continues until completion gates pass or a precise external blocker is recorded.

The design follows two required patterns:
- AutoResearch runtime: zero interaction after start, persistent state, fresh work sessions, stall detection, forced pivots, heartbeat watchdog, and worker/guardian separation. See `references/autoresearch_runtime.md`.
- Scientific survey-writing pipeline: Literature Survey, Structure and Logic, Evidence Design, Figures and Tables, Peer Review and Revision. See the matching reference files below.
- Review-paper writing craft: thesis-driven synthesis, conceptual contribution, critical appraisal, and field agenda rather than source accumulation. See `references/review_writing_patterns.md`.
- Paper mechanism understanding: for `target=full` and `target=csur`, extract A/B papers as scientific contributions with motivation, task, method pipeline, implementation, experiment, result, limitation, and relation to prior work. See `references/paper_mechanism_cards.md`.
- Argument-first synthesis: build `state/topic_diagnosis.yml` and `state/argument_graph.yml` before `outputs/article_plan.md`; the final article must follow the selected survey architecture and argument graph. See `references/topic_diagnosis.md` and `references/argument_graph.md`.
- Deep synthesis artifacts: for `target=full` and `target=csur`, build mechanism cards, compatibility paper cards, system-node cards, section cards, tutorial artifacts, worked examples, benchmark/method tables, section dossiers, and a conceptual framework before drafting. See `references/deep_synthesis_artifacts.md`, `references/final_review_absorption.md`, and `references/section_dossier_patterns.md`.
- Publication prose translation: `outputs/review.md` must read like a mature survey article, not a pasted bundle of state artifacts. Translate dossiers, tables, and worked examples into article prose through `references/publication_prose_translation.md`.
- Article layer: separate research artifacts, synthesis artifacts, appendix methodology, internal planning, and article-facing prose. Write `outputs/article_plan.md` before `outputs/review.md`; the plan must declare article-body, article-display, appendix, and internal-only material. Do not paste survey-type labels, evidence tiers, search routes, run counts, raw tables, or worked-example fields into the article body. See `references/article_layer.md`.
- Survey type routing: first decide primary survey type plus secondary lenses. Use the corresponding section grammar instead of forcing every survey into the same node model. See `references/survey_type_router.md`.
- System-object survey adapter: if the topic names a system, architecture, memory, planner, world model, retrieval system, controller, interface, or comparable composed object, read `references/system_object_survey_adapter.md` before node-card construction.
- CSUR-grade writing craft: for `target=csur`, imitate recent official ACM Computing Surveys exemplars through `references/csur_exemplar_patterns.md`, mine section rhetoric through `references/csur_rhetoric_mining.md`, then write both `state/csur_imitation_plan.md` and `state/csur_style_patterns.yml` before synthesis.
- AutoResearch landscape discipline: use external systems as design evidence, not authority. See `references/autoresearch_landscape.md` before revising workflow architecture or claiming parity with another AutoResearch project.

## Non-Negotiable Behavior

1. Do not end an active run with a question.
2. Do not ask whether to continue between phases.
3. Resolve ambiguity locally and log the decision as `level=decision`.
4. Persist every meaningful state change under the task `state/` directory.
5. Start each major work pass from curated state files, not from conversation history.
6. If a pass stalls, pivot structure, not tactics.
7. If blocked by an external dependency, write a `Blocked` report with exact cause, attempted recovery, and next recovery action.
8. Verify citation-like records continuously: after each batch of about 20 retained or cited items, write verification evidence to `logs/verification.jsonl`.
9. Heartbeat or patrol workers only check liveness, restart, or nudge. They must not edit literature, taxonomy, claims, or outputs.
10. Do not trust external AutoResearch projects blindly. Separate code-inspected facts, paper claims, reusable workflow ideas, and non-transferable assumptions.

## Scope Bias Guardrails

Before Phase 1 multi-perspective question mining, write a scope audit to `state/scope_audit.md`.

The audit must answer:
- What is the core object of the survey: method/system, task, benchmark, theory, or application domain?
- Are user-provided seeds representative of the whole field, or only one task/interface?
- Which adjacent task families or method families would be missed if search followed only the seeds?
- Should the main outline be system-first, method-first, task-first, benchmark-first, or theory-first?

If the topic names a method, system, representation, architecture, theory, or process, the default outline must organize around that object rather than around downstream tasks. Tasks should be treated as interfaces, stress tests, or evaluation settings unless the user explicitly asks for a task survey.

Never let a seed set determine the narrative spine by itself. Seeds initialize recall, not structure. If a seed-biased outline would make one task family appear to be the field's main historical trajectory, redesign the taxonomy before synthesis and log the redesign decision.

For broad agent-system surveys, every retained taxonomy must include at least one cross-task/system axis. Examples:
- components and interfaces;
- representations and assumptions;
- lifecycle or workflow operations;
- controller/policy/planner interface;
- evaluation and ablation interface.

Task axes are allowed, but they cannot be the only organizing axis unless the user explicitly asks for a task-centered review. If the user gives task-biased seeds, use them to expand recall, then design an object-aligned taxonomy.

## Review Quality Guardrails

Before synthesis, write `state/review_style_audit.md`.

The audit must name the reader contract, central thesis, conceptual contribution, related-survey delta, anti-dump risks, process/scaffold leakage risks, and criticality risks. Use `references/review_writing_patterns.md` and `references/completion_gates.md` for the detailed checklist.

The synthesizer must not write a final review until the audit names a thesis and a conceptual contribution. A complete survey must teach a way to think, not only collect references.

For full and CSUR targets, read `references/deep_synthesis_artifacts.md`, `references/final_review_absorption.md`, `references/worked_example_patterns.md`, `references/benchmark_landscape_schema.md`, `references/method_taxonomy_schema.md`, `references/section_dossier_patterns.md`, `references/section_card_patterns.md`, `references/review_writing_patterns.md`, `references/taxonomy_and_structure.md`, and `references/completion_gates.md` before synthesis. Use those references for section grammar, required reader artifacts, and completion gates instead of duplicating the checklists here.

## Start Protocol

Create a run directory before doing substantive research:

```bash
python3 scripts/init_task.py \
  --base-dir runs \
  --topic "<topic>" \
  --target full \
  --output-mode markdown
```

Default targets:
- `short`: 80+ references, Markdown review, evidence table, BibTeX.
- `full`: 150+ references, full survey-style draft, evidence table, BibTeX, synthesis tables, paper mechanism cards, claim-evidence spans, argument graph, paper cards, system-node cards, section cards, and conceptual framework.
- `csur`: `full` plus systematic review protocol, related-survey matrix, CSUR rhetoric mining, evidence-backed synthesis tables, figure plan, and CSUR-readiness gate.

If the user asks for an ACM Computing Surveys, CSUR-grade, publication-grade, or tutorial survey, use `csur`. If the user does not specify the target, default to `full` for "survey paper" and `short` for "literature review" or "related work".

## CSUR-Grade Requirements

Use `target=csur` when the deliverable should be a mature survey paper rather than a landscape draft.

Before final synthesis, write:
- `state/research_questions.md`: 3-6 converged research questions covering taxonomy, benchmarks, methods, evidence, and gaps. Each RQ must state which perspective questions it derives from.
- `state/search_protocol.md`: databases, search strings or routes, inclusion criteria, exclusion criteria, screening counts, and source limitations.
- `state/search_protocol.md` must include at least three discovery routes, such as database search, venue sweep, citation snowball, related-survey bibliography expansion, and explicit query variants.
- `state/related_surveys.md`: matrix of related surveys with what they organize around, what they miss, and what this review adds.
- `state/topic_diagnosis.yml`: primary survey type, secondary lenses, domain pressures, evidence norm, recommended structure, excluded templates, and section grammar.
- `state/paper_mechanism_cards.jsonl`: canonical deep extraction for every A/B paper. Include motivation, problem/task setting, benchmark/environment, method pipeline, implementation details, experiment design, results, limitations/confounders, prior-work relationship, and how the paper changes the survey argument.
- `state/claim_evidence_spans.jsonl`: important claims with paper IDs, evidence spans, support type, and calibrated strength.
- `state/argument_graph.yml`: central thesis, field shift, related-survey gap, argument nodes, evidence dependencies, section order, and take-away findings.
- `state/paper_cards.jsonl`: compatibility extraction for every A/B paper. Generate it from `state/paper_mechanism_cards.jsonl` with `scripts/derive_paper_cards_from_mechanism_cards.py` when possible.
- `state/paper_facts.jsonl`: derived compatibility summary for benchmark/method tables; generate it from `state/paper_cards.jsonl` with `scripts/derive_paper_facts.py` when possible.
- `state/system_node_cards.jsonl`: system nodes with role, why they matter, inputs, outputs, design families, representative papers, failure modes, evaluation signals, and open questions.
- `state/section_cards.jsonl`: section reader question, thesis, structure, opening move, subsection moves, closing implication, and required display item.
- `state/csur_imitation_plan.md`: selected recent official CSUR exemplars, section skeleton, abstract moves, section reader functions, and internal notes excluded from the review body. Read `references/csur_exemplar_patterns.md` first.
- `state/csur_style_patterns.yml`: mined CSUR rhetoric patterns with exemplar evidence: abstract moves, introduction moves, section opening/body/closing moves, table functions, paragraph patterns, and forbidden surface forms.
- `outputs/conceptual_framework.md`: central thesis, system diagram in words, node interactions, taxonomy axes, running example, and prior-survey delta.
- `outputs/glossary.md` and `outputs/running_example.md`: tutorial layer for newcomer comprehension.
- `outputs/worked_examples.md`: structured paper-level worked examples for A papers.
- `outputs/article_plan.md`: selected article-facing tables, case-study boxes, appendix-facing artifacts, and section flow aligned to `state/argument_graph.yml` before final drafting.
- `outputs/review_body_draft.md`: article-prose draft produced from section dossiers and selected case studies before final `review.md`.
- `outputs/appendix.md`: optional exhaustive tables and raw structured examples that should not be pasted into the review body.
- `outputs/coverage_matrix.md`: appendix-facing literature map covering A/B/C evidence levels, method families, benchmark roles, and article-use status.
- `outputs/benchmark_landscape.md`: benchmark capability/protocol/metric/baseline/confounder table.
- `outputs/method_taxonomy.md`: method-family representation/write/read/update/interface table.
- `outputs/node_paper_matrix.md`: system-node to paper mechanism/evidence matrix.
- `outputs/evaluation_protocol.md` and `outputs/design_guidelines.md`: reusable evaluation and design artifacts.
- `outputs/section_dossiers/`: section-level dossiers used before drafting article prose.
- `outputs/synthesis_tables.md`: benchmark and method tables that are traceable to `paper_cards.jsonl` and `paper_facts.jsonl`.
- `outputs/figures_plan.md`: at least three figure/table designs such as taxonomy, method pipeline, and benchmark/evaluation matrix.

Do not claim CSUR readiness merely because the review has section headings or tables. The review must be supported by paper mechanism cards, claim-evidence spans, an argument graph, paper cards, system-node cards, section cards, a systematic search protocol, explicit positioning against related surveys, and a CSUR imitation/rhetoric plan grounded in official ACM DL records from 2025-2026 unless a fallback is clearly documented.

## Runtime State

Every run uses this structure:

```text
runs/<slug>/
  state/
    task_spec.md
    research_questions.md
    research_questions_by_perspective.md
    search_protocol.md
    progress.json
    heartbeat.json
    papers.jsonl
    lqs_scores.jsonl
    citation_plan.jsonl
    claims.jsonl
    claim_evidence_spans.jsonl
    topic_diagnosis.yml
    argument_graph.yml
    paper_mechanism_cards.jsonl
    paper_cards.jsonl
    system_node_cards.jsonl
    section_cards.jsonl
    paper_facts.jsonl
    csur_imitation_plan.md
    csur_style_patterns.yml
    csur_paragraph_patterns.yml
    related_surveys.md
    taxonomy.md
    coverage.json
    directions_tried.json
    review_rounds.jsonl
    phase_summaries.jsonl
    agent_rounds.jsonl
    merge_decisions.jsonl
    disagreements.jsonl
    completion_gates.json
  logs/
    orchestrator.jsonl
    heartbeat.jsonl
    search.jsonl
    extraction.jsonl
    synthesis.jsonl
    verification.jsonl
  outputs/
    review.md
    review_body_draft.md
    article_plan.md
    appendix.md
    coverage_matrix.md
    evidence_ladder.md
    synthesis_tables.md
    figures_plan.md
    evidence_table.csv
    references.bib
    final_report.md
    conceptual_framework.md
    glossary.md
    running_example.md
    worked_examples.md
    benchmark_landscape.md
    method_taxonomy.md
    node_paper_matrix.md
    evaluation_protocol.md
    design_guidelines.md
    section_dossiers/
  dashboard/
    index.html
    phases/*.html
```

Use append-only JSONL for papers, claims, reviews, and logs. Rewrite summary JSON files only when the corresponding state is recalculated.

## Phase Routing

Run phases in this order, looping where gates fail:

1. Phase 0: Task lock. Write scope, angle, audience, target, and assumptions to `task_spec.md`.
2. Phase 1: Topic diagnosis. Write `state/topic_diagnosis.yml` with primary survey type, secondary lenses, evidence norm, and section grammar.
3. Phase 2: Multi-perspective question mining. Write `state/research_questions_by_perspective.md` before locking taxonomy.
4. Phase 3: Broad recall by discovery route: related surveys, seminal papers, benchmarks, systems, applications, and failure/negative cases.
5. Phase 4: Citation identity verification. Check title, authors, year, venue/status, DOI/arXiv/OpenReview/DBLP/official page.
6. Phase 5: Survey-role and evidence-level triage. Use `scripts/score_lqs.py`; classify papers as A/B/C/D and by foundational, system, benchmark, method, application, negative/failure, survey, bridge, or frontier role.
7. Phase 6: Paper mechanism extraction. Convert A/B papers into `state/paper_mechanism_cards.jsonl`; derive `state/paper_cards.jsonl` and `state/paper_facts.jsonl` when possible.
8. Phase 7: Claim-evidence extraction. Write `state/claim_evidence_spans.jsonl` and calibrate strength with `references/claim_evidence_alignment.md`.
9. Phase 8: System-node graph and taxonomy repair. Build `state/system_node_cards.jsonl`; repair taxonomy from mechanism and node coverage.
10. Phase 9: Argument graph and section planning. Build `state/argument_graph.yml`, `state/section_cards.jsonl`, `outputs/conceptual_framework.md`, and for CSUR `state/csur_style_patterns.yml`.
11. Phase 10A: Artifact synthesis. Build tutorial artifacts, worked examples, benchmark landscape, method taxonomy, node-paper matrix, coverage matrix, evidence ladder, evaluation protocol, design guidelines, and section dossiers.
12. Phase 10B: Article planning. Write `outputs/article_plan.md` aligned to `state/argument_graph.yml`.
13. Phase 10C: Article boundary check. Mark each planned section/display as article-body, appendix-only, or internal-only; move survey protocols, evidence tiers, search routes, run metadata, and artifact-selection decisions out of the article body.
14. Phase 10D: Publication prose drafting. Draft `outputs/review_body_draft.md` only from the argument graph, article-body plan, section dossiers, selected prose case studies, interpreted tables, and CSUR paragraph patterns.
15. Phase 10E: Evidence calibration and style pass. Repair unsupported paper summaries, over-strong claims, article-boundary leaks, raw artifact language, repeated templates, and uninterpreted tables before final `outputs/review.md`.
16. Phase 11: Peer review and sprint loop. Run newcomer, system architect, experimentalist, and CSUR stylist review passes; fix routed weaknesses and rerun gates.

For the AutoResearch landscape and workflow borrowing rules, read `references/autoresearch_landscape.md`. For the literature pipeline, read `references/literature_pipeline.md`. For topic diagnosis and survey type routing, read `references/topic_diagnosis.md` and `references/survey_type_router.md`. For mechanism extraction and claim alignment, read `references/paper_mechanism_cards.md`, `references/claim_evidence_alignment.md`, and `references/evidence_verification.md`. For argument structure, read `references/argument_graph.md`. For system-object topics, read `references/system_object_survey_adapter.md`. For deep synthesis artifacts, read `references/deep_synthesis_artifacts.md`. For article-layer writing, read `references/article_layer.md`, `references/final_review_absorption.md`, `references/tutorial_survey_requirements.md`, `references/worked_example_patterns.md`, `references/benchmark_landscape_schema.md`, `references/method_taxonomy_schema.md`, `references/section_dossier_patterns.md`, `references/publication_prose_translation.md`, and `references/publication_prose_rules.md`. For section grammar, read `references/section_card_patterns.md`. For review-writing craft, read `references/review_writing_patterns.md`. For CSUR exemplars, read `references/csur_exemplar_patterns.md`, `references/csur_official_exemplars.yml`, and `references/csur_rhetoric_mining.md`. For reviewer routing, read `references/review_routing.md`. For completion criteria, read `references/completion_gates.md`.
For visual progress reporting, read `references/html_dashboard.md`.

## Multi-Agent Truthfulness

This skill can run in three modes:
- `single-agent`: one agent executes all phases with state files and gates;
- `single-agent multi-pass`: one agent runs independent reviewer personas or repeated analysis passes;
- `true multi-agent`: separate agents or subagents produce independently recorded outputs that the orchestrator merges.

Do not call a run `multi-agent`, `multi-agent discussion`, or `multi-agent consensus` unless:
- real subagent or external agent calls were used;
- each agent pass is recorded in `state/agent_rounds.jsonl`;
- merge or conflict-resolution decisions are recorded in `state/merge_decisions.jsonl`;
- unresolved conflicts or dissent are recorded in `state/disagreements.jsonl`.

Reviewer personas in `state/review_rounds.jsonl` are review simulation. They are useful, but they are not proof of true multi-agent work.

## Orchestrator Loop

At each loop:

1. Update `state/heartbeat.json` and `state/progress.json:last_seen`.
2. Read `state/progress.json`, `state/completion_gates.json`, `state/directions_tried.json`, and the latest review weaknesses.
3. Choose the next worker based on the first failing gate or highest-priority major weakness.
4. Give the worker only the relevant state files, the output contract, file caps, and completion criteria.
5. Require the worker to write state files and logs before returning.
6. Recalculate coverage and gates.
7. Regenerate the static dashboard with `python3 scripts/render_dashboard.py --task-dir <run_dir>`.
8. If the loop produced no new papers, claims, verified citations, coverage progress, or gate progress, increment `stale_count`.
9. If `stale_count >= 2`, force a structural pivot and log it.
10. If `stale_count >= 4`, write a `Blocked` report and continue only with a new structural route.

Structural pivots include:
- keyword search to citation snowball;
- arXiv search to venue sweep;
- method taxonomy to benchmark taxonomy;
- chronological structure to problem-driven structure;
- same-field search to adjacent-field analogy;
- broad recall to contradiction-first search;
- prose revision to evidence-table repair.

When several pivots are plausible, prefer direction diversity over digging one route deeper. Log why the new route differs from prior routes.

## 24-Hour Operating Rule

Treat 24 hours as the default unattended run budget, not the completion deadline.

- If gates pass before 24 hours, finalize.
- If gates do not pass after 24 hours, continue sprint loops while progress exists.
- If progress stalls, pivot and continue.
- If an unrecoverable external blocker appears, write `outputs/final_report.md` with `Blocked` status.

Where the environment supports automations, reminders, cron, thread wakeups, or shell guards, register a durable heartbeat. The skill protocol alone is not a scheduler; the run must be backed by the available scheduling mechanism.

## Worker Roles

Worker roles describe responsibilities. They are true separate agents only when the environment provides subagent tooling and the run records agent outputs and merge decisions.

- Orchestrator: choose phase, update progress, detect stalls, route work.
- Searcher: retrieve candidates and append `papers.jsonl`.
- Role Triage Worker: assign survey role and provisional node hints.
- Scorer: run LQS and update `lqs_scores.jsonl`.
- Classifier: write `citation_plan.jsonl`.
- Verifier: check citation identity and venue status.
- Paper-Mechanism Extractor: write `paper_mechanism_cards.jsonl` for A/B papers and derive compatibility `paper_cards.jsonl`.
- Claim-Evidence Verifier: write `claim_evidence_spans.jsonl` and downgrade claims whose strength exceeds evidence.
- Argument Architect: write `topic_diagnosis.yml`, `argument_graph.yml`, and align article sections to the graph.
- Node-Graph Builder: derive `system_node_cards.jsonl` from paper cards.
- Taxonomy Architect: derive taxonomy from node coverage, related-survey gaps, and evidence tensions.
- Section Planner: write `section_cards.jsonl`.
- Framework Writer: write `outputs/conceptual_framework.md`.
- CSUR Rhetoric Miner: write `state/csur_style_patterns.yml` from selected official exemplars.
- Article Planner: write `outputs/article_plan.md`; separate `article_body_sections`, `article_displays`, `appendix_sections`, and `internal_only` material before drafting.
- Publication Prose Writer: draft `review_body_draft.md` only from article plan, section dossiers, article-facing matrices, selected prose case studies, tutorial artifacts, and CSUR paragraph patterns.
- Synthesizer: produce final `review.md` after the article-boundary, publication-prose, and global-coherence passes. Do not paste raw paper-card fields, worked-example bullet labels, coverage matrices, survey-type labels, evidence tiers, search routes, run counts, or state-artifact language into the review body.
- Reviewer: score independently and route weaknesses.
- Heartbeat: update liveness only; do not modify business state.

## Script Helpers

- `scripts/init_task.py`: create run state.
- `scripts/heartbeat.py`: update heartbeat and `progress.json:last_seen`.
- `scripts/patrol.py`: inspect runs for stale heartbeat state and recommend nudge, restart, pivot, or blocked report.
- `scripts/render_dashboard.py`: regenerate `dashboard/index.html` and per-phase progress pages from state files.
- `scripts/score_lqs.py`: score candidate papers.
- `scripts/coverage_report.py`: count A/B papers per taxonomy cell and system node; warn on unassigned A/B coverage.
- `scripts/derive_paper_cards_from_mechanism_cards.py`: derive compatibility paper cards from mechanism cards.
- `scripts/derive_paper_facts.py`: derive compact paper-fact records from paper cards.
- `scripts/derive_evidence_ladder.py`: summarize claim-strength distribution.
- `scripts/missing_deep_artifacts.py`: report missing cross-links among deep synthesis artifacts.
- `scripts/render_node_map.py`: render system-node cards as a Markdown synthesis table.
- `scripts/validate_topic_diagnosis.py`: verify primary survey type, secondary lenses, evidence norm, and section grammar.
- `scripts/validate_argument_graph.py`: verify central thesis, field shift, argument nodes, section order, and take-away findings.
- `scripts/validate_paper_mechanism_cards.py`: verify paper-level motivation/task/method/experiment/result/limitation extraction.
- `scripts/validate_claim_evidence_spans.py`: verify claim-to-evidence-span alignment and strength calibration.
- `scripts/validate_citation_identity.py`: verify A/B paper identity and verification status.
- `scripts/validate_paper_summary_consistency.py`: reject unsupported baseline, ablation, result, and role claims.
- `scripts/validate_article_plan_alignment.py`: verify article plan follows the argument graph.
- `scripts/validate_article_boundary.py`: verify internal planning, survey-type routing, evidence tiers, search routes, and run metadata stay out of `review.md`.
- `scripts/validate_paper_cards.py`: verify deep paper-card schema.
- `scripts/validate_node_cards.py`: verify system-node cards.
- `scripts/validate_section_cards.py`: verify argument-driven section cards.
- `scripts/validate_csur_style_patterns.py`: verify CSUR rhetoric mining.
- `scripts/validate_csur_paragraph_patterns.py`: verify CSUR paragraph-level rhetoric mining.
- `scripts/validate_review_depth.py`: verify final review length, section depth, worked examples, and table density.
- `scripts/validate_review_absorption.py`: verify final review absorbs paper cards, tutorial artifacts, and comparison tables.
- `scripts/validate_case_study_prose.py`: reject raw paper-card field dumps in review-body case studies.
- `scripts/validate_table_interpretation.py`: verify review-body tables are introduced and interpreted in prose.
- `scripts/validate_publication_prose.py`: verify `review.md` reads like article prose rather than an artifact bundle.
- `scripts/validate_semantic_repetition.py`: reject duplicate headings, repeated template paragraphs, and padding-like repeated synthesis.
- `scripts/validate_global_coherence.py`: verify article plan use, section thesis/implication flow, interpreted tables, and absence of raw coverage matrices.
- `scripts/validate_worked_examples.py`: verify paper-level worked examples.
- `scripts/validate_benchmark_landscape.py`: verify benchmark table schema and entries.
- `scripts/validate_method_taxonomy.py`: verify method-family table schema and entries.
- `scripts/validate_node_paper_matrix.py`: verify node-to-paper matrix.
- `scripts/validate_newcomer_tutorial.py`: verify glossary and running example.
- `scripts/validate_card_specificity.py`: reject template-like paper cards.
- `scripts/review_scorecard.py`: debug-only scorecard for newcomer, method, benchmark, and CSUR-style readiness; it is not a blocking gate.
- `scripts/validate_claims.py`: verify claim records reference known paper IDs and traceable paper-card evidence.
- `scripts/gate_check.py`: evaluate blocking gates, including `gate_6_csur_readiness` for `target=csur`.
- `scripts/normalize_bib.py`: sort BibTeX entries for stable output.

## Final Output Contract

A successful run returns:

Short target: `outputs/review.md`, `outputs/evidence_table.csv`, `outputs/references.bib`, `outputs/final_report.md`, and `dashboard/index.html`.

Full target: short outputs plus `outputs/article_plan.md`, `outputs/review_body_draft.md`, `outputs/appendix.md`, `outputs/coverage_matrix.md`, `outputs/evidence_ladder.md`, `outputs/conceptual_framework.md`, `outputs/glossary.md`, `outputs/running_example.md`, `outputs/worked_examples.md`, `outputs/benchmark_landscape.md`, `outputs/method_taxonomy.md`, `outputs/node_paper_matrix.md`, `outputs/evaluation_protocol.md`, `outputs/design_guidelines.md`, `outputs/section_dossiers/`, `outputs/synthesis_tables.md`, `outputs/figures_plan.md`, and deep cards under `state/`.

CSUR target: full outputs plus `state/search_protocol.md`, `state/related_surveys.md`, `state/topic_diagnosis.yml`, `state/argument_graph.yml`, `state/paper_mechanism_cards.jsonl`, `state/claim_evidence_spans.jsonl`, `state/csur_imitation_plan.md`, `state/csur_style_patterns.yml`, and `state/csur_paragraph_patterns.yml`.

`final_report.md` must state:
- status: `Complete` or `Blocked`;
- topic, target, run duration, and final phase;
- gates passed and remaining risks;
- source limitations;
- paths to final artifacts.
- a link to `dashboard/index.html`.

Do not include internal logs in the final review body. Keep workflow details in `final_report.md`.
