# Expert Review Contract

Gate 7 is the final maturity gate for `target=full` and `target=csur`. It is not self-evaluation and not a score-form check.

## Required Order

1. Gate 1-6 pass.
2. Freeze `outputs/review.md`, `outputs/appendix.md`, `state/argument_graph.yml`, and `state/section_evidence_plans.jsonl` in `state/expert_review_round_status.json`.
3. Dispatch five independent reviewers and record `state/expert_review_invocations.jsonl`.
4. Wait until all five reports are returned. Do not repair while reports are still missing.
5. Adjudicate all major/blocking weaknesses in `state/expert_review_adjudication.json`.
6. Repair each canonical weakness only after rechecking evidence.
7. Run targeted rereview for each repaired major/blocking weakness.

If fresh subagents or fresh contexts are unavailable, mark the run blocked; do not fabricate reviewer reports.

## Required Reviewers

Full/CSUR runs require exactly these persona roles:

- Domain Expert Reviewer
- Survey Architect Reviewer
- Evidence/Factuality Reviewer
- Newcomer/Tutorial Reviewer
- Style/Publication Reviewer

Each invocation needs `review_round_id`, `reviewer_id`, `persona`, `fresh_context: true`, `subagent_session_id`, article/evidence inputs, forbidden previous reports and repair actions, output target, and `status: returned`.

## Report Contract

Each row in `state/expert_review_reports.jsonl` needs:

- `reviewer_id`, `persona`, `overall_score`, `pass_recommendation`
- `dimension_scores` and `dimension_audits`
- `review_trace`, `sections_reviewed`, `section_comments`, `quoted_evidence_from_review`
- persona-specific audits: paper mechanism, flow/taxonomy, claim/citation, tutorial, or style audit
- `blocking_weaknesses`

`dimension_audits` must independently cover:

- narrative coherence
- paper understanding depth
- field-native taxonomy quality
- method taxonomy quality
- benchmark/evaluation quality
- evidence/citation accuracy
- synthesis not catalog
- publication prose
- newcomer value
- expert value

Each dimension audit needs score, verdict, evidence quotes, failure cases, why it matters, repair recommendation, and route. A dimension below the target floor creates a major weakness.

Thresholds:

- `full`: median overall >= 8.5 and every dimension median >= 8.0.
- `csur`: median overall >= 9.0 and every dimension median >= 8.5.

## Adjudication And Repair

`state/expert_review_adjudication.json` must map reviewer weaknesses into canonical weaknesses with severity, source reviewers, affected sections, affected papers, affected claims, route, required evidence check, and repair acceptance criteria. Unadjudicated major weaknesses fail Gate 7.

`state/repair_actions.jsonl` must record evidence-first repair:

- `evidence_rechecked` from the relevant source: paper mechanism cards, claim evidence spans, contribution tree, argument graph, section evidence plans, benchmark dossiers, or full-text sources.
- changed artifacts and repair action.
- claim strength changes and newly modified claims.
- status: resolved, accepted limitation, or unresolved.

If the repair adds or strengthens a claim, update `state/claim_evidence_spans.jsonl` before revising the article. If evidence is insufficient, downgrade the wording or route back to source verification or paper understanding.

`state/targeted_rereview_reports.jsonl` must verify each repaired major/blocking weakness against changed artifacts and checked evidence refs. Verdict must be `resolved`, with matching article hash and no introduced regression.

## Weakness Routes

- citation/source error -> source verification or claim evidence
- paper mechanism unclear -> paper understanding
- benchmark misread -> benchmark dossiers
- taxonomy/story weak -> contribution tree, synthesis dossiers, and argument graph
- section reads like a paper list -> section evidence plan
- artifact/process language -> article quality
- shallow coverage -> discovery and coverage

If two consecutive rounds improve by less than 0.2 while still below threshold, mark the run quality-limited instead of pretending completion.
