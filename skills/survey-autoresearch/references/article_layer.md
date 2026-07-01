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
- primary survey type, secondary lenses, and selected skeleton;
- how the article section order follows the argument graph;
- H2/H3 section order and the reader function of each major section;
- selected article-facing tables, usually 3-6;
- selected prose case-study boxes, usually 4-8;
- appendix-facing exhaustive artifacts;
- what must not enter `review.md`, including raw paper-card fields, full coverage matrices, and internal workflow notes.

## Article-Facing Vs Appendix-Facing

Article-facing:
- a small number of synthesis tables that the prose interprets;
- selective case-study boxes written as paragraphs;
- benchmark selection guide or evidence ladder;
- take-home findings.

Appendix-facing:
- full worked examples;
- full benchmark table;
- full method taxonomy table;
- full node-paper matrix;
- full coverage matrix.

Internal-facing:
- state files, logs, gate reports, review rounds, and raw extraction cards.

## Integration Rule

`review.md` should integrate selected artifacts, not paste all artifacts.

Every major section must correspond to an argument node. If the article plan cannot explain which node a section realizes, repair `state/argument_graph.yml` or remove the section.

Every table in the article must have a before-paragraph that states why it exists and an after-paragraph that explains the main comparison or implication.

Every case study in the article must be paper-specific prose. It may draw from `worked_examples.md`, but it must not preserve repeated labels such as `Problem`, `Write policy`, or `Design lesson`.

Every major section must advance the central thesis. If a section can be moved anywhere without breaking the argument, rewrite the section flow.
