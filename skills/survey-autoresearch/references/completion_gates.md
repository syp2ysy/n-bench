# Completion Gates

Use this reference before final delivery and after every review sprint.

## Gate 1: Literature

Short target:
- references >= 80;
- verification rate >= 80%;
- every taxonomy cell has at least two A/B references or is documented as a gap.

Full target:
- references >= 150;
- verification rate >= 80%;
- accepted or peer-reviewed ratio >= 30% when field norms make this meaningful; if `task_spec.md` declares `accepted_ratio_required: false`, require stronger verification and explicit venue/preprint status labels instead;
- every taxonomy cell has at least two A/B references or is documented as a gap.
- long managed runs include verification evidence in `logs/verification.jsonl` for each about-20 citation batch.
- A/B coverage is not entirely `unassigned`; at least one taxonomy cell or system-node assignment must carry the A/B evidence.

CSUR target:
- satisfies the full target;
- includes systematic review protocol artifacts;
- extracts paper cards and paper-level facts for every A/B paper;
- positions the review against related surveys;
- backs synthesis tables from paper cards and paper-level facts.

All targets:
- hallucinated citation = 0;
- citation plan contains A/B/C/D depth;
- source limitations are documented.
- discovery routes are documented rather than implied.

## Gate 2: Taxonomy

Pass when:
- taxonomy is multi-axis;
- gap analysis exists;
- related surveys are compared;
- taxonomy is used to organize the review, not only displayed.
- the outline is aligned with the survey object: system/method topics are not organized mainly as task lists unless explicitly requested.

## Gate 3: Evidence

Pass when:
- every major claim has a claim record;
- claim records reference known paper IDs;
- evidence fields are nonempty;
- claim strength does not exceed evidence strength;
- uncertain numbers are omitted or marked.

## Gate 4: Output

Pass when these files are present and nonempty:
- `outputs/review.md`;
- `outputs/evidence_table.csv`;
- `outputs/references.bib`;
- `outputs/final_report.md`.

For `target=full`, `outputs/review.md` must also include CSUR/tutorial reader artifacts:
- benchmark landscape;
- method taxonomy;
- method design pipeline;
- evaluation protocol;
- practical design guidelines;
- multiple synthesis tables or boxes.
- critical analysis of limitations, failure modes, disagreements, negative evidence, or counterexamples.

A full survey with only a high-level conceptual framework fails Gate 4 even if all output files exist.

Gate 4 also rejects review-body process leakage: user-audit narratives, scope-correction explanations, defensive framing, or statements that the review is correcting an earlier workflow. Put those notes in review rounds or `outputs/final_report.md`; rewrite the survey body as positive field synthesis.

Gate 4 also rejects scaffold leakage: draft-version labels, internal state filenames, "good survey/method/benchmark" meta-commentary, compressed "X exposes Y; A exposes B" notes, and "map everything back to the framework" phrasing. Put those notes in `state/` files and translate them into publication-facing prose before writing `outputs/review.md`.

Gate 4 also rejects task-first outlines for method/system topics. It is fine to mention tasks, benchmarks, and applications; the failure is making the first substantive sections a task catalog when the claimed survey object is a method, representation, architecture, or system.

Gate 4 also rejects unsubstantiated multi-agent claims. A final report or review body may say `multi-agent`, `subagent`, `multi-agent discussion`, or equivalent only when `state/agent_rounds.jsonl` and `state/merge_decisions.jsonl` contain actual records from the run. Reviewer personas alone are not multi-agent proof.

For LaTeX/PDF targets, compilation and visual checks are additional gates.

## Gate 5: Deep Synthesis

For `target=full` and `target=csur`, pass only when these artifacts are present and substantive:

- `state/paper_cards.jsonl`;
- `state/system_node_cards.jsonl`;
- `state/section_cards.jsonl`;
- `state/research_questions_by_perspective.md`;
- `outputs/conceptual_framework.md`.

Additional checks:

- paper cards include survey role, mechanism, system component or node, interface or operation fields, failure modes, limitations, evidence spans, what each A/B paper teaches the survey, and complete A/B coverage;
- system-node cards include role, why the node matters, inputs, outputs, representative papers grounded in paper cards, failure modes, evaluation signals, open questions, and explicit gap reasons for weak/gap nodes;
- section cards include reader question, section thesis, section structure, opening move, structured subsection moves, closing implication, and required display item;
- the conceptual framework includes substantive English or Chinese sections for central thesis, system model, node/component interactions, taxonomy axes, running example, and how the framework differs from prior survey views;
- perspective questions include multiple reader or expert viewpoints before taxonomy lock;
- major claims trace to paper-card fields, not only to paper IDs.

Keyword-rich prose, table counts, or generic method-family headings cannot substitute for these artifacts.

## Gate 6: CSUR Readiness

For `target=csur`, pass only when these files are present and substantive:

- `state/research_questions.md`;
- `state/search_protocol.md`;
- `state/related_surveys.md`;
- `state/paper_cards.jsonl`;
- `state/system_node_cards.jsonl`;
- `state/section_cards.jsonl`;
- `state/paper_facts.jsonl`;
- `state/csur_imitation_plan.md`;
- `state/csur_style_patterns.yml`;
- `outputs/conceptual_framework.md`;
- `outputs/synthesis_tables.md`;
- `outputs/figures_plan.md`.

Additional checks:

- at least three research questions;
- search protocol includes databases, inclusion criteria, exclusion criteria, and screening counts;
- search protocol includes at least three discovery routes, such as database search, venue sweep, citation snowball, related-survey bibliography expansion, and explicit query variants;
- related-survey table includes at least eight surveys;
- related-survey differentiation includes structural novelty such as a taxonomy, framework, evidence matrix, benchmark comparison, evaluation protocol, failure-mode analysis, or design agenda; recency or breadth alone fails;
- related-survey positioning does not rely on under-review, submitted, or arXiv-only records as accepted survey evidence;
- `state/csur_imitation_plan.md` cites at least two recent official ACM Computing Surveys exemplars from ACM DL, using 2025-2026 DOI records by default;
- `state/csur_imitation_plan.md` includes selected exemplars, section skeleton, abstract moves, reader function by major section, and internal notes excluded from the review body;
- the imitation plan does not use arXiv-only, submitted, under-review, or unverified accepted claims as CSUR exemplars;
- `state/csur_style_patterns.yml` includes abstract moves, introduction moves, section opening/body/closing patterns, table functions, paragraph patterns, forbidden surface forms, and observed evidence notes from at least two official CSUR exemplars;
- every A/B paper in `citation_plan.jsonl` has a paper-card record;
- every A/B paper in `citation_plan.jsonl` has a derived paper-fact record;
- paper facts include method family, task family, benchmark/dataset, metrics, mechanism or contribution, ablations, and limitations;
- paper facts are consistent with paper cards for paper ID and mechanism/contribution;
- paper cards include survey role, mechanism, system node or component, interface, evidence spans, failure modes, limitations, and what the paper teaches the survey;
- synthesis tables include metrics, ablations, and method/record-schema comparison, and are traceable to paper cards;
- figure plan includes at least three planned figures or table designs.

## Qualitative Final Review

Record this as `final_review_status`, not as a deterministic gate. Pass when:
- deterministic gates pass for the target;
- multi-persona review reaches the target score or two sprint rounds improve by <= 0.3;
- all major weaknesses are resolved or explicitly accepted as limitations;
- no previously fixed weakness regressed;
- final report states `Complete`.

## CSUR Style Gate

For `target=csur`, qualitative review must check more than section names:
- the abstract states motivation gap, scope, organizing framework or taxonomy, evidence artifacts, and research agenda;
- the introduction builds from field importance to related-survey gap, contributions, and roadmap;
- related-survey positioning states structural novelty, not only recency or breadth;
- taxonomy and benchmark sections define dimensions before listing papers or tasks;
- evaluation and open-problem sections tie limitations to evidence gaps and concrete research moves;
- all internal scaffold notes are absent from `outputs/review.md`.

## Criticality Gate

For full and CSUR targets, the review must do more than explain a taxonomy. It must include at least two forms of critical analysis:
- benchmark or dataset limitations;
- method failure modes;
- disagreements, contradictions, or trade-offs across families;
- negative evidence, counterexamples, or failed assumptions.

Put this critique in the review body as field synthesis. Do not describe it as an internal audit or a correction to a previous draft.

## Gate Check Helper

Run:

```bash
python3 scripts/gate_check.py --task-dir <run_dir> --target short
python3 scripts/gate_check.py --task-dir <run_dir> --target csur
```

The helper checks deterministic Gates 1-6. The orchestrator records qualitative final review separately as `final_review_status`.
