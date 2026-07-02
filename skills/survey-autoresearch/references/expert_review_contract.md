# Expert Review Contract

`state/expert_review_reports.jsonl` records independent reviewer judgments after Gate 1-6 pass.

Required personas for mature full/CSUR review:

- Domain Expert Reviewer: paper mechanisms, method claims, benchmark interpretation.
- Survey Architect Reviewer: central thesis, taxonomy, section order, synthesis quality.
- Evidence/Factuality Reviewer: citation support, claim strength, source status.
- Newcomer/Tutorial Reviewer: whether a new reader can understand the field and design choices.
- Style/Publication Reviewer: publication prose, artifact leakage, repetition, transitions.

Each report needs `reviewer_id`, `persona`, `overall_score`, `dimension_scores`, `blocking_weaknesses`, and `pass_recommendation`.

Score dimensions:

- narrative coherence
- paper understanding depth
- method taxonomy quality
- benchmark and evaluation quality
- evidence factuality and citation accuracy
- synthesis not catalog
- publication prose
- newcomer value
- expert value

Thresholds:

- `target=full`: median score must be at least 8.5.
- `target=csur`: median score must be at least 9.0.
- `target=short`: expert review is optional.

Weakness routes:

- citation or source error -> source verification or claim evidence;
- paper mechanism unclear -> paper understanding;
- benchmark misread -> benchmark dossiers;
- taxonomy feels like buckets -> synthesis dossiers and argument graph;
- section reads like a paper list -> section evidence plan;
- artifact/process language -> article quality;
- shallow coverage -> coverage and high-recall discovery.

If median score is below 8.0, do not only polish prose. Repair paper understanding, synthesis dossiers, argument graph, or section evidence plans first.

If two consecutive expert-review rounds improve by less than 0.2 while still below threshold, mark the run quality-limited in `state/review_iteration_status.json` and report the blocker honestly.
