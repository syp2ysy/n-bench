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

Prefer survey-role scoring whenever the candidate has enough metadata. This keeps older foundational work and negative evidence from being dropped only because it is not recent.

| Dimension | Weight | Default scoring |
| --- | ---: | --- |
| Conceptual centrality | 25% | Does this paper define, reframe, or anchor the survey object? |
| Mechanism clarity | 20% | Are inputs, outputs, assumptions, and interface clear enough for synthesis? |
| Evidence strength | 20% | Are claims backed by experiments, ablations, benchmarks, or formal analysis? |
| Taxonomy coverage value | 15% | Does the paper fill a node, family, gap, or bridge needed by the framework? |
| Benchmark or ablation value | 10% | Does it provide reusable evaluation evidence or controlled comparisons? |
| Venue or verification | 10% | Is identity, venue/preprint status, and source provenance verified? |

Use `scripts/score_lqs.py` for deterministic scoring. If survey-role fields are absent, the script falls back to legacy metadata scoring based on recency, citation impact, venue, institution/author signal, and acceptance status.

Thresholds:
- LQS >= 7.0: must-cite;
- 5.0 <= LQS < 7.0: conditional;
- LQS < 5.0: drop unless it fills a critical historical, system-node, negative-evidence, benchmark, or taxonomy gap.

Do not penalize a `foundational` or `seminal` paper for age when it is central to the survey's conceptual object. Mark the reason in `lqs_scores.jsonl`.

## Stage 3: Citation Depth

Assign depth in `state/citation_plan.jsonl`:

| Depth | Use |
| --- | --- |
| A | 1-3 paragraphs, section protagonist, 3-5 per major section |
| B | 2-5 sentences, important comparison or key evidence |
| C | one contextual citation |
| D | excluded from the review |

Do not let C-level papers dominate the intellectual structure. A and B papers carry the analysis.

For `target=full` and `target=csur`, every A/B paper must later receive a `state/paper_cards.jsonl` record. Assign A/B depth only when the paper can support a mechanism, benchmark, failure-mode, or conceptual claim.

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
