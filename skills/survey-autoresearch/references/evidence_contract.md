# Evidence Contract

The evidence layer establishes source truth and claim support.

Required files:

- `state/raw_candidates.jsonl`
- `state/search_routes.jsonl`
- `state/lqs_scores.jsonl`
- `state/corpus_expansion.json`
- `state/papers.jsonl`
- `state/citation_plan.jsonl`
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

Claim evidence fields:

- `claim_id`, `claim`, `claim_type`
- `paper_ids`
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
- Full and CSUR runs must record enough raw candidates, search routes, related surveys, and corpus-expansion status before selecting A/B/C papers.
- Every retained paper in `state/papers.jsonl` must have `source_candidate_id` linking back to `state/raw_candidates.jsonl`.
- If a public curated list or recent survey visibly contains far more relevant papers than the retained corpus, `state/corpus_expansion.json` must mark expansion required and complete it before the run proceeds.
- A/B papers must be verified.
- A/B papers must have auditable full-text source records.
- C papers must meet the target verification rate.
- Unverified papers cannot support article-body claims.
- Claim strength cannot exceed evidence-span strength.
- A paper title alone is not evidence.
- Abstracts, metadata, curated lists, and survey-table rows can support discovery or C/background coverage only; they cannot support strong mechanism, benchmark, experimental-result, comparison, or limitation claims.
- Strong claims in `review.md` need an evidence span with `source_ref` and `excerpt`.
- Strong article claims should appear in a section whose evidence plan includes the relevant claim/evidence span.
