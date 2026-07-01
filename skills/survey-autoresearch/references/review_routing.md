# Review Routing

Use this reference after each draft or major revision.

## Reviewer Personas

Run 3-5 independent reviewer passes:

| Persona | Focus |
| --- | --- |
| Experimentalist | evidence quality, benchmarks, statistical caution |
| Theorist | definitions, taxonomy, conceptual depth |
| Perfectionist | prose clarity, structure, formatting |
| Synthesizer | cross-cutting analysis and gap quality |
| Newcomer | accessibility, missing definitions, examples |

Reviewers should score independently. Do not show one reviewer another review before it is written.

## Scoring Dimensions

Score 1-10:
- novelty of synthesis;
- comprehensiveness;
- clarity;
- technical depth;
- evidence quality;
- citation reliability.

Calibration:
- 6.0: complete but basic;
- 7.0: good structured review;
- 8.0: strong survey with critical synthesis;
- 8.5: high-quality survey with robust taxonomy, evidence, and revision;
- 9.0: exceptional, usually requiring original analysis or unusually strong synthesis.

## Anti-Inflation

- First review round score is capped at 7.0.
- Maximum gain per round is 1.5 unless a major missing component was added.
- At least one unresolved weakness remains until final gates pass.
- Previous fixed weaknesses must be regression-checked.

## Weakness Routing

| Weakness | Route |
| --- | --- |
| Citation coverage insufficient | Literature recall |
| Too many unverified/preprint refs | Venue upgrade and verification |
| Missing recent work | Recent-focused search |
| Taxonomy not novel | Taxonomy redesign |
| Topic object collapsed into task list | Taxonomy redesign and section reorganization |
| Structure unclear | Section reorganization and transitions |
| Analysis lacks depth | Claim-evidence-implication repair |
| Critical analysis missing | Evidence extraction and synthesis repair |
| No failure modes, disagreements, or negative evidence | Contradiction-first search and synthesis repair |
| Claims too strong | Evidence verification and hedge downgrade |
| Tables incomparable | Synthesis table rebuild |
| Paper cards generic or missing mechanism | Paper-card extraction repair |
| A/B papers missing paper cards | Paper-card coverage repair |
| Node cards not grounded in paper cards | Node graph repair |
| Important system node missing | System-object adapter pass |
| Section cards are headings, not arguments | Section-card rewrite |
| Conceptual framework lacks running example | Framework repair |
| CSUR style patterns copied, not mined | CSUR rhetoric mining repair |
| Claims cite paper IDs but not card fields | Claim trace repair |
| Synthesis tables not derived from cards | Table rebuild from paper cards |
| Review reads like expanded outline or proposal | Review-depth repair and section dossier rebuild |
| Newcomer cannot explain the field after reading | Tutorial primer, glossary, and running-example repair |
| Major method families lack mechanism explanation | Method taxonomy rebuild and worked-example expansion |
| Core papers are only name-dropped | Worked-paper-example pass |
| Benchmark section lists names without metrics/baselines/confounders | Benchmark landscape rebuild |
| Paper cards exist but do not appear in final review | Final-review absorption repair |
| Section cards compress into short overview prose | Section dossier expansion |
| Paper cards use template fields instead of paper-specific mechanisms | Paper-card specificity repair |
| Review body pastes worked-example field labels | Publication prose translation |
| Tables appear without interpretation paragraphs | Table interpretation repair |
| Case studies read like paper-card dumps | Case-study prose rewrite |
| Review reads like state artifacts instead of an article | Publication prose translation and appendix split |
| Review pastes full coverage or absorption matrix into the body | Article plan repair and appendix split |
| Review repeats headings or template paragraphs to satisfy length | Semantic repetition repair and global rewrite |
| Article lacks selected-table/case-box plan | Article plan pass |
| Paper appears only in tables without prose mechanism context | Final-review absorption repair |
| Review score is keyword-rich but prose is incoherent | Global coherence and publication prose pass |
| Survey type template does not fit the topic | Survey type router and outline rewrite |
| Missing visualizations | Figures and tables pass |
| Process-correction language appears in review body | Section reorganization and final-report relocation |
| Related-survey differentiation is only recency or breadth | Taxonomy redesign and related-survey matrix repair |
| Final report claims multi-agent without agent records | Final-report correction or true agent-round logging |
| Review drift or regression | Reopen prior weakness |

Write each review to `state/review_rounds.jsonl` with weakness IDs, severity, routed owner, and resolved status.

Reviewer personas are not true multi-agent work unless separate agent calls produced records in `state/agent_rounds.jsonl` and the orchestrator recorded merge decisions in `state/merge_decisions.jsonl`.
