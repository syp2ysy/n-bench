# Literature Pipeline

Use this reference for recall, scoring, citation-depth planning, and venue upgrade.

## Stage 1: High-Recall Retrieval

Target 200-500 raw candidates for a full survey and 80-200 for a short review.

For each taxonomy cell, run at least three query variants:
- core terms;
- synonyms and adjacent terms;
- method names, benchmark names, dataset names, or system names.

Search routes:
- arXiv and Semantic Scholar for broad recall;
- DBLP and venue proceedings for accepted status;
- OpenReview for ICLR/NeurIPS/ICML-style review venues;
- backward citation snowball from seed papers;
- forward citation search from seminal papers;
- existing survey bibliography expansion.

Log each search route in `logs/search.jsonl` and each retained candidate in `state/papers.jsonl`.

After every batch of about 20 retained candidates or citation-like records, write verification records to `logs/verification.jsonl`. Each record should include `paper_id`, source checked, and whether title/year/venue matched. This batch cadence is part of the completion gate for long full/CSUR runs.

## Stage 2: LQS Scoring

Score each candidate with:

| Dimension | Weight | Default scoring |
| --- | ---: | --- |
| Recency | 30% | 6mo=10, 1yr=8, 2yr=5, 3yr=3 |
| Citation impact | 25% | cites/mo >=50=10, >=10=8, >=3=6 |
| Venue | 20% | top-tier=10, strong=7, workshop=4, preprint=3 |
| Institution or author signal | 10% | top lab=10, top university=9, known=6 |
| Acceptance status | 15% | accepted=10, under review=5, preprint=3 |

Use `scripts/score_lqs.py` for deterministic scoring where metadata is available.

Thresholds:
- LQS >= 7.0: must-cite;
- 5.0 <= LQS < 7.0: conditional;
- LQS < 5.0: drop unless it fills a critical historical or taxonomy gap.

## Stage 3: Citation Depth

Assign depth in `state/citation_plan.jsonl`:

| Depth | Use |
| --- | --- |
| A | 1-3 paragraphs, section protagonist, 3-5 per major section |
| B | 2-5 sentences, important comparison or key evidence |
| C | one contextual citation |
| D | excluded from the review |

Do not let C-level papers dominate the intellectual structure. A and B papers carry the analysis.

## Stage 4: Venue Upgrade

For every arXiv/preprint candidate:
- check DBLP;
- check OpenReview where relevant;
- check the paper page for "accepted at";
- convert BibTeX entry type only when acceptance is verified.

Targets:
- verification rate >= 80%;
- hallucinated citations = 0;
- accepted or peer-reviewed ratio >= 30% when the field has normal publication venues;
- arXiv-only ratio <= 60% when feasible.
- verification evidence is present throughout the run, not only in a final bulk pass.

Do not invent accepted status to satisfy a ratio.
