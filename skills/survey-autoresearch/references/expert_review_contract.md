# Expert Review Contract

`state/expert_review_reports.jsonl` records independent reviewer judgments after Gate 1-6 pass.

Required personas for mature full/CSUR review:

- Domain Expert Reviewer: paper mechanisms, method claims, benchmark interpretation.
- Survey Architect Reviewer: central thesis, taxonomy, section order, synthesis quality.
- Evidence/Factuality Reviewer: citation support, claim strength, source status.
- Paradigm/Evidence Norm Reviewer may be combined with Domain Expert or Evidence/Factuality: whether the article uses the correct proof standard for the scientific field.
- Newcomer/Tutorial Reviewer: whether a new reader can understand the field and design choices.
- Style/Publication Reviewer: publication prose, artifact leakage, repetition, transitions.

Each report needs `reviewer_id`, `persona`, `overall_score`, `dimension_scores`, `blocking_weaknesses`, and `pass_recommendation`.

Gate 7 is a full-article audit, not a score-form validator. For `target=full` or `target=csur`, every reviewer report must prove that the reviewer read the article body:

- `sections_reviewed`: list every top-level `##` article section reviewed, excluding references or appendices.
- `section_comments`: map each reviewed section title to a concrete comment about that section's argument, evidence, readability, or style.
- `quoted_evidence_from_review`: at least five short quotes copied from different parts of `outputs/review.md`; each quote must appear in the article text.
- `review_trace`: include `article_chars_read` and `reviewed_full_article: true`.

Persona-specific audits are required:

- Domain Expert Reviewer: `paper_mechanism_audits` with at least ten A/B paper checks against the article's mechanism claims.
- Survey Architect Reviewer: `flow_taxonomy_audit` covering section flow, taxonomy coherence, and synthesis-vs-catalog risk.
- Evidence/Factuality Reviewer: `claim_citation_audits` with at least ten claim/citation checks against article text and evidence spans.
- Domain Expert or Evidence/Factuality Reviewer must also comment on `science_paradigm_profile`: whether method, benchmark, theorem, experiment, simulation, clinical, or deployment claims use evidence units accepted by the relevant community.
- Newcomer/Tutorial Reviewer: `tutorial_audit` covering glossary clarity, running example usefulness, and remaining confusing terms.
- Style/Publication Reviewer: `style_audit` covering repetition, artifact leakage, table interpretation, and transition quality.

Passing reviews must still name non-blocking weaknesses or explicitly explain why no blocking weakness remains. Reusing the same summary, identical dimension scores, or generic comments across reviewers is not independent expert review and must fail Gate 7.

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
