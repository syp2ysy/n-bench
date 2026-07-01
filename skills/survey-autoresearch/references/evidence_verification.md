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

## Paper-Mechanism Card Schema

For `target=full` and `target=csur`, `state/paper_mechanism_cards.jsonl` is the canonical deep extraction layer. It must explain each A-level paper as a scientific contribution: motivation, task, benchmark/environment, method pipeline, implementation details, experiments, results, limitations, relationship to prior work, and how it changes the survey argument.

Read `references/paper_mechanism_cards.md` before extraction.

## Compatibility Paper-Card Schema

For `target=full` and `target=csur`, every A/B paper in `state/citation_plan.jsonl` needs a deep record in `state/paper_cards.jsonl`. This is the canonical extraction layer for synthesis:

```json
{
  "paper_id": "paper_001",
  "survey_role": "foundational | seminal | system | benchmark | application | negative | survey | bridge | frontier",
  "problem": "What problem the paper makes visible for the review.",
  "method_summary": "One concise mechanism-level summary.",
  "system_node": "capture | representation | storage | retrieval | update | interface | evaluation",
  "mechanism_or_contribution": "The concrete contribution used by the review.",
  "inputs": ["observations", "queries", "feedback"],
  "outputs": ["records", "retrieved evidence", "planner constraints"],
  "representation": "text | vector | graph | map | program | hybrid",
  "write_policy": "when and how records are added",
  "read_policy": "when and how records are retrieved",
  "update_or_consolidation": "append, summarize, revise, merge, forget, or relink",
  "controller_interface": "how the method affects decisions, actions, or evaluation",
  "evaluation_tasks": ["representative task or protocol"],
  "datasets_or_envs": ["benchmark or environment"],
  "metrics": ["metric"],
  "baselines": ["baseline"],
  "ablations": ["ablation"],
  "failure_modes": ["failure mode"],
  "limitations": ["limitation"],
  "what_it_teaches_the_survey": "The conceptual lesson this paper contributes.",
  "evidence_spans": ["section, table, page, or quoted-free evidence note"]
}
```

The extractor may adapt field names to the topic, but the card must still capture role, mechanism, system node or component, interface, evaluation signal, failure/limitation, and the lesson used by the survey.

When `state/paper_mechanism_cards.jsonl` exists, prefer deriving compatibility paper cards:

```bash
python3 scripts/derive_paper_cards_from_mechanism_cards.py --paper-mechanism-cards state/paper_mechanism_cards.jsonl --output state/paper_cards.jsonl
```

## CSUR Paper-Fact Schema

For compatibility and compact tables, keep `state/paper_facts.jsonl`. It is a derived artifact, not a second source of truth. Prefer:

```bash
python3 scripts/derive_paper_facts.py --paper-cards state/paper_cards.jsonl --output state/paper_facts.jsonl
```

For `target=csur`, every A/B paper must have both a paper card and a paper-fact summary:

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

Use paper facts as compact sources for benchmark and method synthesis tables. Do not generate full or CSUR-grade synthesis directly from prose impressions or paper facts alone; use paper cards for the mechanism and argument layer.

## Evidence Rules

- Every important claim in `review.md` must map to at least one claim record.
- For `target=full` and `target=csur`, claim records must trace to paper-card fields such as mechanism, interface, evidence spans, or `what_it_teaches_the_survey`; a bare paper ID is not enough.
- For `target=full` and `target=csur`, important method/result/benchmark/comparison claims must also appear in `state/claim_evidence_spans.jsonl` with paper ID, section/page/table note, evidence summary, support type, and strength.
- Claim strength must not exceed evidence strength.
- Numbers, dates, venues, benchmark scores, and model names must be source-backed.
- If a number cannot be verified, omit it or mark it source-limited.
- Do not cite a paper for a claim it does not support.
- For `target=csur`, do not use an A/B paper in a synthesis table unless its `paper_cards.jsonl` and `paper_facts.jsonl` records have the required fields.

For standalone claim validation in full/CSUR runs, pass paper cards and mechanism cards:

```bash
python3 scripts/validate_claims.py --claims state/claims.jsonl --papers state/papers.jsonl --paper-cards state/paper_cards.jsonl
python3 scripts/validate_claim_evidence_spans.py --claims state/claim_evidence_spans.jsonl --paper-mechanism-cards state/paper_mechanism_cards.jsonl
python3 scripts/validate_paper_summary_consistency.py --paper-mechanism-cards state/paper_mechanism_cards.jsonl
```

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

For full/CSUR targets:
- A/B papers must be identity verified before supporting review-body claims.
- C-level papers should be at least 90% verified for broad coverage.
- Unverified papers may remain in recall state, but cannot support final synthesis.

Run:

```bash
python3 scripts/validate_citation_identity.py --papers state/papers.jsonl --citation-plan state/citation_plan.jsonl --target full
```

## Source-Limited Areas

When public search cannot verify a source, say so in `outputs/final_report.md`. Do not fabricate a source, metric, or social-media signal.
