# Evidence Verification

Use this reference when extracting claims, checking sources, and writing synthesis.

## Claim Record Schema

Each major claim belongs in `state/claims.jsonl`:

```json
{
  "claim_id": "c001",
  "claim": "Tool-using research agents need explicit recovery loops.",
  "paper_ids": ["paper_001", "paper_014"],
  "evidence": "Paper sections or tables supporting the claim.",
  "strength": "suggests",
  "taxonomy_cell": "agents/tool-use",
  "confidence": "medium"
}
```

## CSUR Paper-Fact Schema

For `target=csur`, every A/B paper in `state/citation_plan.jsonl` must also have a record in `state/paper_facts.jsonl`:

```json
{
  "paper_id": "paper_001",
  "method_family": "retrieval-augmented system",
  "task_family": "question answering",
  "benchmark_or_dataset": "Representative benchmark",
  "metrics": ["accuracy", "groundedness"],
  "mechanism_or_contribution": "retrieval over provenance-rich evidence records",
  "ablations": ["no retrieval", "oracle evidence"],
  "limitations": "Does not isolate every possible confounder."
}
```

Use paper facts as the source for benchmark and method synthesis tables. Do not generate CSUR-grade synthesis tables directly from prose impressions.

## Evidence Rules

- Every important claim in `review.md` must map to at least one claim record.
- Claim strength must not exceed evidence strength.
- Numbers, dates, venues, benchmark scores, and model names must be source-backed.
- If a number cannot be verified, omit it or mark it source-limited.
- Do not cite a paper for a claim it does not support.
- For `target=csur`, do not use an A/B paper in a synthesis table unless its `paper_facts.jsonl` record has the required fields.

## Strength Ladder

Use this ladder:

```text
demonstrates > shows > suggests > may indicate > hypothesizes
```

Use `demonstrates` only for direct experimental or formal evidence. Use `suggests` for cross-paper synthesis.

## Citation Checks

Every batch of 20 citations must be checked for:
- title match;
- author list sanity;
- year;
- venue or preprint status;
- DOI, arXiv, OpenReview, DBLP, or official page URL where available.

Write verification decisions to `logs/verification.jsonl`.

## Source-Limited Areas

When public search cannot verify a source, say so in `outputs/final_report.md`. Do not fabricate a source, metric, or social-media signal.
