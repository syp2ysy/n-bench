# Article Layer

Use this reference after research and synthesis artifacts exist.

## Three Layers

Research layer:
- `papers.jsonl`, `citation_plan.jsonl`, `paper_mechanism_cards.jsonl`, `claim_evidence_spans.jsonl`, verification logs, and coverage records.
- Goal: comprehensive and traceable evidence.

Synthesis layer:
- `topic_diagnosis.yml`, `argument_graph.yml`, `conceptual_framework.md`, `method_taxonomy.md`, `benchmark_landscape.md`, `node_paper_matrix.md`, `worked_examples.md`, `section_dossiers/`, and `coverage_matrix.md`.
- Goal: convert papers into mechanisms, comparisons, benchmarks, limitations, and agenda.

Article layer:
- `article_plan.md`, `review_body_draft.md`, and final `review.md`.
- Goal: a publication-facing survey article with narrative control, selective case boxes, interpreted tables, and coherent section transitions.

## Article Plan

Write `state/topic_diagnosis.yml` and `state/argument_graph.yml` before `outputs/article_plan.md`. Then write `outputs/article_plan.md` before drafting `review.md`.

It must specify:
- central article thesis;
- `article_body_sections`: H2/H3 section order, reader function, argument node, and publication-facing section thesis.
- `article_displays`: the 3-6 tables, figures, or prose case boxes allowed in `review.md`, each with a publication-facing title.
- `appendix_sections`: survey protocol, exhaustive tables, coverage matrices, full worked examples, and other transparent but non-narrative material.
- `internal_only`: survey type diagnosis, primary/secondary lenses, evidence tiers, search routes, run counts, artifact decisions, repair notes, gate status, and state-file terminology.

The article plan is a private blueprint, not article source text. Only `article_body_sections` and `article_displays` can drive `review.md`; `appendix_sections` can drive `outputs/appendix.md`; `internal_only` must never be copied into `review.md`.

## Article-Facing Vs Appendix-Facing

Article-facing:
- a small number of synthesis tables that the prose interprets;
- selective case-study boxes written as paragraphs;
- benchmark selection guide or calibrated evidence wording;
- take-home findings.

Appendix-facing:
- full worked examples;
- full benchmark table;
- full method taxonomy table;
- full node-paper matrix;
- full coverage matrix.

Internal-facing:
- state files, logs, gate reports, review rounds, raw extraction cards, topic diagnosis, survey type labels, evidence tiers, search routes, run counts, and artifact-selection decisions.

## Integration Rule

`review.md` should integrate selected artifacts, not paste all artifacts.

Do not include a standalone methodology, evidence-tier, or survey-type-routing section in `review.md` unless the user explicitly requested a systematic-review protocol in the article body. For ordinary full/CSUR-style surveys, put search/screening details, A/B/C evidence tiers, candidate counts, and source-route notes in `outputs/appendix.md` or `outputs/final_report.md`. The article body may still position related surveys and calibrate claim strength through scholarly prose.

Every major section must correspond to an argument node. If the article plan cannot explain which node a section realizes, repair `state/argument_graph.yml` or remove the section.

Every table in the article must have a before-paragraph that states why it exists and an after-paragraph that explains the main comparison or implication.

Every case study in the article must be paper-specific prose. It may draw from `worked_examples.md`, but it must not preserve repeated labels such as `Problem`, `Write policy`, or `Design lesson`.

Every major section must advance the central thesis. If a section can be moved anywhere without breaking the argument, rewrite the section flow.
