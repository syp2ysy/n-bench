# Evidence Contract

The evidence layer establishes source truth and claim support.

Required files:

- `state/raw_candidates.jsonl`
- `state/search_routes.jsonl`
- `state/lqs_scores.jsonl`
- `state/corpus_expansion.json`
- `state/papers.jsonl`
- `state/citation_plan.jsonl`
- `state/topic_relevance_audit.jsonl`
- `state/topic_relevance_second_audits.jsonl`
- `state/full_text_sources.jsonl`
- `state/claim_evidence_spans.jsonl`
- `state/section_evidence_plans.jsonl`
- `outputs/coverage_matrix.md`

Source identity fields:

- `paper_id`, `title`, `authors`, `year`
- `venue_status`
- one or more source identifiers: `doi`, `arxiv_id`, `openreview_url`, `dblp_url`, `official_url`
- `verification_status`: `verified`, `partial`, or `unverified`
- `verified_sources`

Topic relevance audit fields:

- `paper_id` and `candidate_id` or `source_candidate_id`
- `evidence_used`: nonempty title/abstract/query/source metadata snippets used by the worker
- `positive_topic_signals`
- `negative_drift_signals`
- `relevance_grade`: `core`, `direct_related_survey`, `adjacent_background`, `generic_background`, or `out_of_scope`
- `allowed_depth`: `A`, `B`, `C`, or `exclude`
- `allowed_role`: `core`, `related_survey`, `background`, or `exclude`
- `family_label_supported`
- `corrected_family`
- `rationale`

Topic relevance second-audit fields:

- `paper_id`
- `primary_audit_session_id`
- `subagent_session_id`: must differ from the primary audit session
- `trigger_reasons`: must cover the validator-reported high-risk reasons
- `evidence_used`: must include evidence beyond title/query, such as abstract, source metadata, or full-text metadata
- `decision`: `confirm_core`, `downgrade_to_C`, `exclude`, or `direct_related_survey`
- `allowed_depth`, `allowed_role`, and `rationale`

Claim evidence fields:

- `claim_id`, `claim`, `claim_type`
- `paper_ids`
- `named_entities` and `cited_paper_ids` when the claim names specific papers, systems, methods, or benchmarks
- `support_relation`: `direct`, `indirect`, or `background`
- `strength`: `demonstrates`, `shows`, `suggests`, or `may indicate`
- `evidence_spans`: each span needs `paper_id`, `source_ref`, `section_or_page`, `excerpt`, `evidence_summary`, `supports`, and `strength`

Full-text source fields:

- `paper_id`
- `source_ref`: stable identifier used by claim/evidence spans
- `source_url`, `source_kind` or `source_type`
- `access_status`
- `extraction_status`
- `captured_excerpts`: each excerpt needs a section/page/figure/table locator and a short extracted passage or faithful excerpt note

`state/full_text_sources.jsonl` is the audit layer between verified source identity and paper understanding. It proves the run worked from accessible full text rather than from metadata. A/B paper mechanism cards must have a matching full-text source record.

Rules:

- Discovery sufficiency is a hard predecessor to source verification and paper understanding.
- Source verification is not just DOI/metadata verification. Full and CSUR runs must have a worker-produced `state/topic_relevance_audit.jsonl` before A/B full-text reading begins.
- Full and CSUR runs must record enough raw candidates, search routes, related surveys, and corpus-expansion status before selecting A/B/C papers.
- Full and CSUR discovery should be route-level: keyword/snowball, curated-list/benchmark/venue, related-survey mining, author-group snowballing, and final enrichment can be separate worker batches. Only the merged and deduplicated route results are canonical discovery state.
- Every retained paper in `state/papers.jsonl` must have `source_candidate_id` linking back to `state/raw_candidates.jsonl`.
- Every raw candidate, retained paper, and A/B paper must have a topic audit record. Missing audit coverage blocks source verification with `topic_relevance_audit`.
- A/B papers must be `core`, or a small explicitly allowed number of `direct_related_survey` records; `generic_background` and `out_of_scope` records cannot be A/B.
- `validate_coverage.py` must count full/CSUR support from audit-supported topic records when `state/topic_relevance_audit.jsonl` exists. A paper's self-assigned `family` or `topic_axis` label cannot by itself prove coverage.
- Topic coverage is layered. Raw support comes only from audited raw candidates; retained support comes only from audited retained papers; verified support comes only from retained papers whose source identity is verified; A/B support comes only from citation-plan A/B papers with `relevance_grade=core` and `family_label_supported=true`.
- Related-survey support for full/CSUR source verification counts only retained, verified papers audited as `direct_related_survey` with `allowed_role=related_survey`. A survey-like title in raw candidates is not enough. A later dedicated related-survey discovery worker/gate should prove that those surveys were intentionally found, verified, and used in taxonomy alignment; until then, validators must at least require source-topic IDs to connect discovery, topic audit, and taxonomy alignment.
- High-risk A/B core audit rows require an independent worker second audit before source verification can pass when they rely only on title/query evidence, contain negative drift signals, label a survey/review as A/B core, or allow A/B depth without explaining the topic boundary. A string such as `secondary` in the primary audit is not sufficient; the primary audit row must carry its real `subagent_session_id`, and the second audit must be recorded in `state/topic_relevance_second_audits.jsonl` with a different `subagent_session_id` that references the primary session.
- Broad LLM, generic MLLM, education, medical, RAG, or XAI surveys are background or related-survey material unless the audit rationale shows direct relevance to the topic boundary, such as visual intermediate-state reasoning, image-as-workspace, visual scratchpad methods, image-grounded reasoning actions, or equivalent topic-specific anchors.
- Retained coverage is a hard predecessor to A/B reading. Verified-paper counts alone are not enough: the retained corpus must satisfy target A/B/C depth, candidate linkage, core-family support, and corpus-expansion requirements before paper understanding begins.
- `state/search_routes.jsonl` must record typed discovery routes. Use `route_type`: `keyword`, `snowball`, `related_survey_refs`, `venue`, `benchmark`, `author_group`, or `curated_list`. Full/CSUR runs must show each selected core family has an independent route, raw-candidate support, verified-paper support, and A/B support.
- `state/corpus_expansion.json` must record curated lists checked, recent surveys checked, the largest visible external paper count, and why the retained corpus is sufficient. If that visible count substantially exceeds the retained corpus, corpus expansion must be completed before source verification proceeds.
- If a public curated list or recent survey visibly contains far more relevant papers than the retained corpus, `state/corpus_expansion.json` must mark expansion required and complete it before the run proceeds.
- A/B papers must be verified.
- A/B papers must have auditable full-text source records.
- A/B full-text understanding must be recorded through paper-understanding worker results. Python validators may merge and check `state/full_text_sources.jsonl` and compatibility `state/paper_mechanism_cards.jsonl`, then mirror them into `state/paper_cards/{paper_id}.json`; they must not fabricate deep-read conclusions.
- A/B paper cards must have survey utility. Each mirrored `state/paper_cards/{paper_id}.json` needs `survey_use.changes_knowledge_tree` or an equivalent evidence-backed statement explaining how the paper changes the knowledge tree, spine, claim structure, or evidence gap. A paper that is merely adjacent background cannot enter A/B even if it has metadata relevance.
- C papers must meet the target verification rate.
- Unverified papers cannot support article-body claims.
- Claim strength cannot exceed evidence-span strength.
- A paper title alone is not evidence.
- Abstracts, metadata, curated lists, and survey-table rows can support discovery or C/background coverage only; they cannot support strong mechanism, benchmark, experimental-result, comparison, or limitation claims.
- Strong claims in `survey_candidate.md` or final `survey.md` need an evidence span with `source_ref` and `excerpt`.
- Strong article claims should appear in a section whose evidence plan includes the relevant claim/evidence span.
- If an article sentence names a paper, method, system, or benchmark and also cites sources, the citation window must include the corresponding paper ID or citation key. A sentence that names one work while citing another is invalid even when both papers exist.
- Named systems, method short names, and benchmark names used near citations must be registered in the relevant A/B paper's `entity_aliases`; unregistered named entities near citations are invalid until the alias is evidence-backed or the prose is rewritten.
- Coverage must support the selected article spine. Raw counts are not enough: core families from the community taxonomy or contribution tree need route, raw, verified, and A/B support, and a benchmark-heavy corpus with thin method/task families cannot pass full or CSUR coverage. If retained coverage is invalid, the next phase is coverage repair, not source or paper-understanding work.
