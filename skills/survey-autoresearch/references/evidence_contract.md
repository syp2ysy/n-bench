# Evidence Contract

The evidence layer establishes source truth and claim support.

Required files:

- `state/papers.jsonl`
- `state/citation_plan.jsonl`
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
- `evidence_spans`: each span needs `paper_id`, `section_or_page`, `evidence_summary`, `supports`, and `strength`

Rules:

- A/B papers must be verified.
- C papers must meet the target verification rate.
- Unverified papers cannot support article-body claims.
- Claim strength cannot exceed evidence-span strength.
- A paper title alone is not evidence.
- Strong article claims should appear in a section whose evidence plan includes the relevant claim/evidence span.
