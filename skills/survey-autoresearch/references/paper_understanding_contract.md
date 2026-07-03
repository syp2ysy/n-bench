# Paper Understanding Contract

`state/paper_mechanism_cards.jsonl` is the single deep-reading interpretation source. `state/full_text_sources.jsonl` is the full-text audit source that each A/B card must bind to.

Reading depth is explicit:

- `full_text_deep_read`: the run opened and read the paper full text or PDF key sections. Only this state can support A/B papers.
- `abstract_metadata_only`: the run saw only title, abstract, Semantic Scholar/Crossref/DBLP metadata, a curated list row, GitHub list, or survey table. This can only be C/background or evidence-limited.
- `unavailable_or_unread`: the paper was not read deeply enough to support article claims.

Every A/B paper needs:

- `paper_id`, `title`, `survey_role`, `level`
- `reading_depth: full_text_deep_read`
- `full_text_accessed: true`
- `source_type` naming a full-text source such as PDF, publisher HTML, arXiv PDF, ACM DL PDF, or OpenReview PDF
- `full_text_sources`: stable source references matching `state/full_text_sources.jsonl`
- a matching `state/full_text_sources.jsonl` record with accessible full text, extraction status, source reference, and captured excerpt(s)
- `sections_read` covering at least intro/problem, method/system, experiment/evaluation, and results/limitations
- `evidence_span_locations` with concrete section, page, figure, or table locators
- `deep_read_notes` summarizing what was learned from the full text
- `motivation`
- `problem_setting`
- `task_definition`
- `benchmark_or_dataset`
- `method_pipeline`
- `implementation_details`
- `experimental_setup`
- `main_results`
- `limitations_and_confounders`
- `relation_to_prior_work`
- `what_it_changes_in_the_survey_argument`
- `must_not_overclaim`
- `evidence_spans`

The card explains a scientific contribution, not a survey bucket. It must answer why the paper exists, what task it studies, how the method works, how it was evaluated, what the results support, what they do not support, and how the paper changes the survey argument.

Every required A/B field must contain substantive content. Empty strings, empty lists, empty dicts, placeholder prose, and generic sentences such as "this paper is important", "related to prior work", or "read the paper" fail the Paper Understanding Completion Gate. If a field is genuinely not applicable, use a structured `not_applicable_reason` with an evidence-backed explanation; do not leave the field blank.

All A/B papers in `state/citation_plan.jsonl` must have complete mechanism cards before any contribution tree, scenario definition, synthesis dossier, argument graph, section evidence plan, article plan, or review draft is treated as valid. Partial A/B completion is a blocked state, not a warning.

A/B papers without full-text access, concrete results, baselines, ablations, limitations, or benchmark/environment details must be downgraded. They may be retained as C/background only when marked `evidence_limited=true`.

Evidence spans for A/B papers must come from the full text. Title-only, abstract-only, Semantic Scholar metadata, Crossref/DBLP metadata, curated-list rows, GitHub list entries, or visible survey-table rows are not deep-reading evidence.

The paper mechanism card is not enough by itself. For A/B papers, the run must also record where the full text was accessed and what section/page/figure/table evidence was extracted. If `full_text_sources.jsonl` is missing, metadata-only, or lacks captured excerpts, the card must fail even if all mechanism fields are filled.

`relation_to_prior_work` must name the relationship type, such as extends, replaces, contradicts, benchmarks, reframes, surveys, predecessor, successor, alternative, or conflict. Generic prose such as "related to prior work" is not enough.

Benchmark papers should not be treated as method systems. Survey papers should not be used as experimental-result evidence. Main results must cite evidence spans beyond a paper title.

C papers can appear in coverage matrices, related-work context, appendices, and bibliographies. They cannot support mechanism, experimental-result, benchmark-property, comparison, or limitation claims in `review.md` unless promoted to A/B through full-text deep reading.
