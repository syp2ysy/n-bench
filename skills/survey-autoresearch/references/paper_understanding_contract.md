# Paper Understanding Contract

`state/paper_cards/{paper_id}.json` is the public deep-reading card store. `state/paper_mechanism_cards.jsonl` remains the compatibility append-only source produced by existing workers, and `state/full_text_sources.jsonl` is the full-text audit source that each A/B card must bind to.

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
- `field_evidence_map`
- `entity_aliases`

The card explains a scientific contribution, not a survey bucket. It must answer why the paper exists, what task it studies, how the method works, how it was evaluated, what the results support, what they do not support, and how the paper changes the survey argument.

The mirrored v2 paper card must include `survey_use`: possible sections, supported claims, one-sentence contribution, and especially `changes_knowledge_tree`. This field is required because downstream knowledge-tree and spine planning must know what the paper changes about the field structure, not just what the paper did.

Every required A/B field must contain substantive content. Empty strings, empty lists, empty dicts, placeholder prose, and generic sentences such as "this paper is important", "related to prior work", or "read the paper" fail the Paper Understanding Completion Gate. If a field is genuinely not applicable, use a structured `not_applicable_reason` with an evidence-backed explanation; do not leave the field blank.

`field_evidence_map` must bind each core interpretation field to full-text evidence. At minimum, map motivation, problem setting, method pipeline, benchmark or dataset, implementation details, experimental setup, main results, limitations/confounders, and relation to prior work to `source_ref` plus section/page/table/figure-level evidence. Metadata, abstract, title, survey-table, and curated-list sources do not count.

Field evidence must fit the field. Method pipeline evidence must come from method/system/model passages; benchmark evidence must name the benchmark, dataset, protocol, metric, baseline, or ablation; main-result evidence must include result-bearing language such as metric, table/figure, baseline comparison, improvement, or reported success. Boilerplate, funding, acknowledgements, license text, arXivLabs text, or metadata cannot fill motivation, result, or limitation fields.

The entities asserted by a card must be consistent with its evidence. Method names, benchmark names, and result entities in core fields must appear in the corresponding evidence span or in full-text-backed `entity_aliases`. If a card claims one benchmark or method but its evidence span names another or none, the A/B paper is incomplete.

`entity_aliases` must register the names the article may use near citations: paper-title variants, system names, method short names, benchmark names, and common abbreviations. Each alias needs a type, a `source_ref`, and evidence. A title-only alias set is insufficient for A/B papers; at least one non-title alias must be full-text backed when the paper names a method, system, or benchmark.

Do not reuse the same mechanism template across A/B papers. If multiple cards share the same method pipeline, limitations, and result language, the run must repair the cards from full-text evidence or downgrade the papers.

All A/B papers in `state/citation_plan.jsonl` must have complete mechanism cards before any contribution tree, scenario definition, synthesis dossier, argument graph, section evidence plan, article plan, or survey draft is treated as valid. Partial A/B completion is a blocked state, not a warning.

For unattended runs, use `paper_understanding_runtime_executor.py` and `runtime_dispatcher.py` instead of manually tracking ad hoc paper notes. The executor batches incomplete A/B papers, exposes up to three active batches by default, and writes worker requests to `state/paper_understanding_spawn_requests.json`; the dispatcher normalizes those requests into `state/runtime_dispatch_queue.jsonl`, tracks spawned agents, parses returned JSON, and calls `paper_understanding_runtime_executor.py --record-result`. A worker request is not evidence of deep reading; only a recorded result that passes `validate_paper_understanding` counts.

Paper-understanding worker requests use `result_schema_version: 2` and include `paper_records`, `fetch_candidates_by_paper`, `expected_paper_ids`, `expected_changed_artifacts`, `expected_acceptance_validators`, and `record_command`. Workers must return strict JSON or a fenced `json` block with `batch_id`, `status`, `paper_ids`, `full_text_sources`, `paper_mechanism_cards`, `artifact_hashes_before`, `validator_results`, `unavailable_or_downgrade_candidates`, and `remaining_blockers`. Workers do not write canonical JSONL files directly; the executor merges returned rows and computes `artifact_hashes_after`.

If a paper cannot be read deeply enough, do not fill a weak A/B card. Return it as an unavailable or downgrade candidate, then use `rebalance_ab_selection.py` to downgrade it to C and promote a verified replacement while preserving target A/B counts and coverage. Full-text URL discovery can be planned with `full_text_source_planner.py`, but URL discovery alone is not paper understanding.

A/B papers without full-text access, concrete results, baselines, ablations, limitations, or benchmark/environment details must be downgraded. They may be retained as C/background only when marked `evidence_limited=true`.

Evidence spans for A/B papers must come from the full text. Title-only, abstract-only, Semantic Scholar metadata, Crossref/DBLP metadata, curated-list rows, GitHub list entries, or visible survey-table rows are not deep-reading evidence.

The paper mechanism card is not enough by itself. For A/B papers, the run must also record where the full text was accessed and what section/page/figure/table evidence was extracted. If `full_text_sources.jsonl` is missing, metadata-only, or lacks captured excerpts, the card must fail even if all mechanism fields are filled.

`relation_to_prior_work` must name the relationship type, such as extends, replaces, contradicts, benchmarks, reframes, surveys, predecessor, successor, alternative, or conflict. Generic prose such as "related to prior work" is not enough.

Benchmark papers should not be treated as method systems. Survey papers should not be used as experimental-result evidence. Main results must cite evidence spans beyond a paper title.

C papers can appear in coverage matrices, related-work context, appendices, and bibliographies. They cannot support mechanism, experimental-result, benchmark-property, comparison, or limitation claims in `survey_candidate.md` or final `survey.md` unless promoted to A/B through full-text deep reading.
