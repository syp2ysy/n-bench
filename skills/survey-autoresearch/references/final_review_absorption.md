# Final Review Absorption

Use this reference before writing `outputs/review.md`.

The final review must absorb intermediate artifacts through article prose, not by pasting all artifacts into `review.md`:

- Paper cards -> structured worked examples, then selected prose case studies in `review.md`.
- System-node cards -> node-paper matrix and system-model prose.
- Section cards -> section dossiers.
- Benchmark cards/facts -> benchmark landscape table.
- Method facts -> method taxonomy table.
- Conceptual framework -> tutorial primer and running example.
- Coverage records -> `outputs/coverage_matrix.md`, then a short article-facing evidence map or selected anchor table.
- Section dossiers and selected artifacts -> `outputs/article_plan.md`, then `outputs/review_body_draft.md`.

Do not write `review.md` directly from a paper list, paper cards, section titles, or full coverage matrices. Draft each major section from its section dossier, select article-facing material in `article_plan.md`, then run the publication-prose translation pass in `publication_prose_translation.md`.

Minimum absorption checks:

- every A paper appears in `outputs/worked_examples.md`, `outputs/coverage_matrix.md`, `outputs/appendix.md`, or as a named case study;
- enough article-facing anchor papers appear in prose with mechanism, evidence, limitation, and taxonomy/node context;
- `review.md` uses a selective set of prose case studies rather than an exhaustive field dump;
- every major method family has representation, write trigger, read key, update policy, controller interface, failure mode, representative works, and benchmark fit;
- every benchmark entry states memory pressure, metrics, baselines, memory-specific ablations, and confounders;
- open problems cite an evidence gap and a concrete benchmark or method move;
- each table embedded in `review.md` is introduced and interpreted in prose.

Reject `review.md` if a paper appears only in a table and is never explained in prose, or if the body contains a raw "core literature absorption matrix" with truncated abstracts.
