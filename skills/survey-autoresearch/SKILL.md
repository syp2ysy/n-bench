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
- CSUR-grade writing craft: for `target=csur`, imitate recent official ACM Computing Surveys exemplars through `references/csur_exemplar_patterns.md`, then write `state/csur_imitation_plan.md` before synthesis.
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

Before Phase 1 taxonomy seed, write a scope audit to `state/scope_audit.md`.

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

Before Phase 8 synthesis, write `state/review_style_audit.md`.

The audit must contain:
- **Reader contract**: target reader, what they already know, and what the review teaches them that a paper list would not.
- **Central thesis**: one sentence that can appear in the abstract, introduction, and conclusion without changing meaning.
- **Conceptual contribution**: the framework, model, taxonomy, ladder, or set of tensions introduced by the review.
- **CSUR/tutorial reader artifacts**: the concrete field map a new reader needs, including benchmark landscape, method taxonomy, method design pipeline, evaluation protocol, and practical design guidelines.
- **Related-survey differentiation**: why this review is not merely newer, broader, or longer.
- **Top-survey pattern check**: how the draft follows review-paper norms from `references/review_writing_patterns.md`.
- **Anti-dump check**: sections that are paper lists, chronology lists, or task lists must be rewritten before completion.
- **Process-leakage check**: user audits, prior draft mistakes, scope corrections, and defensive "not X" framing must stay in logs, review rounds, or `outputs/final_report.md`, not in the survey body.
- **Scaffold-leakage check**: internal framework notes, task-pressure shorthand, state filenames, draft-version labels, and "good survey/method" meta-commentary must be translated into publication-facing prose before entering `outputs/review.md`.
- **Criticality check**: the review must discuss benchmark limitations, method failure modes, disagreements, negative evidence, or counterexamples.

The synthesizer must not write a final review until the audit names a thesis and a conceptual contribution. A complete survey must teach a way to think, not only collect references.

For full and CSUR targets, read `references/review_writing_patterns.md`, `references/taxonomy_and_structure.md`, and `references/completion_gates.md` before synthesis. Use those references for section grammar, required reader artifacts, and completion gates instead of duplicating the checklists here.

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
- `full`: 150+ references, full survey-style draft, evidence table, BibTeX, synthesis tables.
- `csur`: `full` plus systematic review protocol, related-survey matrix, paper-level fact extraction for every A/B paper, evidence-backed synthesis tables, figure plan, and CSUR-readiness gate.

If the user asks for an ACM Computing Surveys, CSUR-grade, publication-grade, or tutorial survey, use `csur`. If the user does not specify the target, default to `full` for "survey paper" and `short` for "literature review" or "related work".

## CSUR-Grade Requirements

Use `target=csur` when the deliverable should be a mature survey paper rather than a landscape draft.

Before final synthesis, write:
- `state/research_questions.md`: 3-6 research questions covering taxonomy, benchmarks, methods, evidence, and gaps.
- `state/search_protocol.md`: databases, search strings or routes, inclusion criteria, exclusion criteria, screening counts, and source limitations.
- `state/search_protocol.md` must include at least three discovery routes, such as database search, venue sweep, citation snowball, related-survey bibliography expansion, and explicit query variants.
- `state/related_surveys.md`: matrix of related surveys with what they organize around, what they miss, and what this review adds.
- `state/paper_facts.jsonl`: for every A/B paper, extract `paper_id`, `method_family`, `task_family`, `benchmark_or_dataset`, `metrics`, `mechanism_or_contribution`, `ablations`, and `limitations`.
- `state/csur_imitation_plan.md`: selected recent official CSUR exemplars, section skeleton, abstract moves, section reader functions, and internal notes excluded from the review body. Read `references/csur_exemplar_patterns.md` first.
- `outputs/synthesis_tables.md`: benchmark and method tables that are traceable to `paper_facts.jsonl`.
- `outputs/figures_plan.md`: at least three figure/table designs such as taxonomy, method pipeline, and benchmark/evaluation matrix.

Do not claim CSUR readiness merely because the review has section headings or tables. The review must be supported by paper-level facts, a systematic search protocol, explicit positioning against related surveys, and a CSUR imitation plan grounded in official ACM DL records from 2025-2026 unless a fallback is clearly documented.

## Runtime State

Every run uses this structure:

```text
runs/<slug>/
  state/
    task_spec.md
    research_questions.md
    search_protocol.md
    progress.json
    heartbeat.json
    papers.jsonl
    lqs_scores.jsonl
    citation_plan.jsonl
    claims.jsonl
    paper_facts.jsonl
    csur_imitation_plan.md
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
    synthesis_tables.md
    figures_plan.md
    evidence_table.csv
    references.bib
    final_report.md
  dashboard/
    index.html
    phases/*.html
```

Use append-only JSONL for papers, claims, reviews, and logs. Rewrite summary JSON files only when the corresponding state is recalculated.

## Phase Routing

Run phases in this order, looping where gates fail:

1. Phase 0: Task lock. Write scope, angle, audience, target, and assumptions to `task_spec.md`.
2. Phase 1: Taxonomy seed. Create initial axes and search cells after completing `scope_audit.md`; if the survey object is a system/method concept, make the primary taxonomy system-first. Use a multi-perspective question pass to expose blind spots before locking the taxonomy.
3. Phase 2: Recall. Retrieve broad candidates with multiple query variants per cell.
4. Phase 3: LQS scoring. Score papers and assign `must-cite`, `conditional`, or `drop`.
5. Phase 4: Citation depth. Classify each retained paper as A, B, C, or D.
6. Phase 5: Venue and citation verification. Check title, authors, year, venue, DOI/arXiv/OpenReview/DBLP.
7. Phase 6: Evidence extraction. Convert paper notes into `claims.jsonl`; for `target=csur`, also write `paper_facts.jsonl` before synthesis.
8. Phase 7: Taxonomy repair. Fill weak cells, record gap analysis, redesign axes if needed.
9. Phase 8: Synthesis. For `target=csur`, first write `state/csur_imitation_plan.md`; then write `review.md`, `evidence_table.csv`, and `references.bib`.
10. Phase 9: Peer review. Run independent reviewer personas and route weaknesses.
11. Phase 10: Sprint loop. Fix routed weaknesses, rerun gates, repeat until complete.

For the AutoResearch landscape and workflow borrowing rules, read `references/autoresearch_landscape.md`. For the literature pipeline, read `references/literature_pipeline.md`. For structure and taxonomy, read `references/taxonomy_and_structure.md`. For review-writing craft, read `references/review_writing_patterns.md`. For CSUR exemplars, read `references/csur_exemplar_patterns.md`. For claim rules, read `references/evidence_verification.md`. For reviewer routing, read `references/review_routing.md`. For completion criteria, read `references/completion_gates.md`.
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
- Scorer: run LQS and update `lqs_scores.jsonl`.
- Classifier: write `citation_plan.jsonl`.
- Verifier: check citation identity and venue status.
- Extractor: write evidence-backed `claims.jsonl`.
- Taxonomist: maintain `taxonomy.md` and coverage gaps.
- Synthesizer: write outputs from claims and citation plan.
- Reviewer: score independently and route weaknesses.
- Heartbeat: update liveness only; do not modify business state.

## Script Helpers

- `scripts/init_task.py`: create run state.
- `scripts/heartbeat.py`: update heartbeat and `progress.json:last_seen`.
- `scripts/patrol.py`: inspect runs for stale heartbeat state and recommend nudge, restart, pivot, or blocked report.
- `scripts/render_dashboard.py`: regenerate `dashboard/index.html` and per-phase progress pages from state files.
- `scripts/score_lqs.py`: score candidate papers.
- `scripts/coverage_report.py`: count A/B papers per taxonomy cell.
- `scripts/validate_claims.py`: verify claim records reference known paper IDs and evidence.
- `scripts/gate_check.py`: evaluate blocking gates, including `gate_6_csur_readiness` for `target=csur`.
- `scripts/normalize_bib.py`: sort BibTeX entries for stable output.

## Final Output Contract

A successful run returns:

```text
outputs/review.md
outputs/evidence_table.csv
outputs/references.bib
outputs/final_report.md
dashboard/index.html
```

`final_report.md` must state:
- status: `Complete` or `Blocked`;
- topic, target, run duration, and final phase;
- gates passed and remaining risks;
- source limitations;
- paths to final artifacts.
- a link to `dashboard/index.html`.

Do not include internal logs in the final review body. Keep workflow details in `final_report.md`.
