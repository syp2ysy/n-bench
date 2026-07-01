# Final Review Absorption

Use this reference before writing `outputs/review.md`.

The final review must absorb intermediate artifacts through article prose, not by pasting all artifacts into `review.md`:

- Paper cards -> structured worked examples, then selected prose case studies in `review.md`.
- System-node cards -> node-paper matrix and system-model prose.
- Section cards -> section dossiers.
- Benchmark cards/facts -> benchmark landscape table.
- Method facts -> method taxonomy table.
- Conceptual framework -> tutorial primer and running example.

Do not write `review.md` directly from a paper list, paper cards, or section titles. Draft each major section from its section dossier, then run the publication-prose translation pass in `publication_prose_translation.md`.

Minimum absorption checks:

- every A paper appears in `outputs/worked_examples.md`, `outputs/appendix.md`, or as a named case study;
- `review.md` uses a selective set of prose case studies rather than an exhaustive field dump;
- every major method family has representation, write trigger, read key, update policy, controller interface, failure mode, representative works, and benchmark fit;
- every benchmark entry states memory pressure, metrics, baselines, memory-specific ablations, and confounders;
- open problems cite an evidence gap and a concrete benchmark or method move;
- each table embedded in `review.md` is introduced and interpreted in prose.
