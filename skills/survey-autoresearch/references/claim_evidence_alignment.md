# Claim Evidence Alignment

Use this when extracting claims and calibrating article prose.

Every important review-body claim must trace to evidence spans, not only paper IDs.

Claim record:

```json
{
  "claim_id": "",
  "claim": "",
  "claim_type": "method | benchmark | result | limitation | taxonomy | comparison",
  "paper_ids": [],
  "strength": "demonstrates | shows | suggests | may indicate | hypothesizes",
  "evidence_spans": [
    {
      "paper_id": "",
      "section_or_page": "",
      "evidence_summary": "",
      "supports": "direct | indirect | background",
      "strength": "demonstrates | shows | suggests | may indicate | hypothesizes"
    }
  ],
  "unsupported_risk": ""
}
```

Strength ladder:

```text
demonstrates > shows > suggests > may indicate > hypothesizes
```

Rules:

- A claim cannot be stronger than its evidence.
- Use `demonstrates` only for direct experimental, formal, or controlled evidence.
- If a paper lacks memory-specific ablation, do not say it demonstrates memory causality.
- Benchmark papers can establish capability pressure or protocol, but cannot be described as method systems unless the paper itself provides that mechanism.
- Unverified papers cannot support review-body claims.

Run:

```bash
python3 scripts/validate_claim_evidence_spans.py --claims state/claim_evidence_spans.jsonl --paper-mechanism-cards state/paper_mechanism_cards.jsonl
python3 scripts/validate_paper_summary_consistency.py --paper-mechanism-cards state/paper_mechanism_cards.jsonl
```
