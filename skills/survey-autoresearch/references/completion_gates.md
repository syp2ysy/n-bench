# Completion Gates

Use this reference before final delivery and after every review sprint.

## Gate 1: Literature

Short target:
- references >= 80;
- verification rate >= 80%;
- every taxonomy cell has at least two A/B references or is documented as a gap.

Full target:
- references >= 150;
- verification rate >= 80%;
- accepted or peer-reviewed ratio >= 30% when field norms make this meaningful;
- every taxonomy cell has at least two A/B references or is documented as a gap.
- long managed runs include verification evidence in `logs/verification.jsonl` for each about-20 citation batch.

CSUR target:
- satisfies the full target;
- includes systematic review protocol artifacts;
- extracts paper-level facts for every A/B paper;
- positions the review against related surveys;
- backs synthesis tables from paper-level facts.

All targets:
- hallucinated citation = 0;
- citation plan contains A/B/C/D depth;
- source limitations are documented.
- discovery routes are documented rather than implied.

## Gate 2: Taxonomy

Pass when:
- taxonomy is multi-axis;
- gap analysis exists;
- related surveys are compared;
- taxonomy is used to organize the review, not only displayed.
- the outline is aligned with the survey object: system/method topics are not organized mainly as task lists unless explicitly requested.

## Gate 3: Evidence

Pass when:
- every major claim has a claim record;
- claim records reference known paper IDs;
- evidence fields are nonempty;
- claim strength does not exceed evidence strength;
- uncertain numbers are omitted or marked.

## Gate 4: Output

Pass when these files are present and nonempty:
- `outputs/review.md`;
- `outputs/evidence_table.csv`;
- `outputs/references.bib`;
- `outputs/final_report.md`.

For `target=full`, `outputs/review.md` must also include CSUR/tutorial reader artifacts:
- benchmark landscape;
- method taxonomy;
- method design pipeline;
- evaluation protocol;
- practical design guidelines;
- multiple synthesis tables or boxes.
- critical analysis of limitations, failure modes, disagreements, negative evidence, or counterexamples.

A full survey with only a high-level conceptual framework fails Gate 4 even if all output files exist.

Gate 4 also rejects review-body process leakage: user-audit narratives, scope-correction explanations, defensive "not task X" framing, or statements that the review is not a paper/task list. Put those notes in review rounds or `outputs/final_report.md`; rewrite the survey body as positive field synthesis.

Gate 4 also rejects scaffold leakage: draft-version labels, internal state filenames, "good survey/method/benchmark" meta-commentary, compressed "X exposes Y; A exposes B" notes, and "map everything back to the framework" phrasing. Put those notes in `state/` files and translate them into publication-facing prose before writing `outputs/review.md`.

Gate 4 also rejects task-first outlines for method/system topics. It is fine to mention tasks, benchmarks, and applications; the failure is making the first substantive sections a task catalog when the claimed survey object is a method, representation, architecture, or system.

Gate 4 also rejects unsubstantiated multi-agent claims. A final report or review body may say `multi-agent`, `subagent`, `multi-agent discussion`, or equivalent only when `state/agent_rounds.jsonl` and `state/merge_decisions.jsonl` contain actual records from the run. Reviewer personas alone are not multi-agent proof.

For LaTeX/PDF targets, compilation and visual checks are additional gates.

## Gate 5: Final Review

Pass when:
- Gates 1-4 pass;
- multi-persona review reaches the target score or two sprint rounds improve by <= 0.3;
- all major weaknesses are resolved or explicitly accepted as limitations;
- no previously fixed weakness regressed;
- final report states `Complete`.

## Gate 6: CSUR Readiness

For `target=csur`, pass only when these files are present and substantive:

- `state/research_questions.md`;
- `state/search_protocol.md`;
- `state/related_surveys.md`;
- `state/paper_facts.jsonl`;
- `state/csur_imitation_plan.md`;
- `outputs/synthesis_tables.md`;
- `outputs/figures_plan.md`.

Additional checks:

- at least three research questions;
- search protocol includes databases, inclusion criteria, exclusion criteria, and screening counts;
- search protocol includes at least three discovery routes, such as database search, venue sweep, citation snowball, related-survey bibliography expansion, and explicit query variants;
- related-survey table includes at least eight surveys;
- related-survey differentiation includes structural novelty such as a taxonomy, framework, evidence matrix, benchmark comparison, evaluation protocol, failure-mode analysis, or design agenda; recency or breadth alone fails;
- related-survey positioning does not rely on under-review, submitted, or arXiv-only records as accepted survey evidence;
- `state/csur_imitation_plan.md` cites at least two recent official ACM Computing Surveys exemplars from ACM DL, using 2025-2026 DOI records by default;
- `state/csur_imitation_plan.md` includes selected exemplars, section skeleton, abstract moves, reader function by major section, and internal notes excluded from the review body;
- the imitation plan does not use arXiv-only, submitted, under-review, or unverified accepted claims as CSUR exemplars;
- every A/B paper in `citation_plan.jsonl` has a paper-fact record;
- paper facts include method family, task family, benchmark/dataset, metrics, mechanism or contribution, ablations, and limitations;
- synthesis tables include metrics, ablations, and method/record-schema comparison;
- figure plan includes at least three planned figures or table designs.

## CSUR Style Gate

For `target=csur`, qualitative review must check more than section names:
- the abstract states motivation gap, scope, organizing framework or taxonomy, evidence artifacts, and research agenda;
- the introduction builds from field importance to related-survey gap, contributions, and roadmap;
- related-survey positioning states structural novelty, not only recency or breadth;
- taxonomy and benchmark sections define dimensions before listing papers or tasks;
- evaluation and open-problem sections tie limitations to evidence gaps and concrete research moves;
- all internal scaffold notes are absent from `outputs/review.md`.

## Criticality Gate

For full and CSUR targets, the review must do more than explain a taxonomy. It must include at least two forms of critical analysis:
- benchmark or dataset limitations;
- method failure modes;
- disagreements, contradictions, or trade-offs across families;
- negative evidence, counterexamples, or failed assumptions.

Put this critique in the review body as field synthesis. Do not describe it as an internal audit or a correction to a previous draft.

## Gate Check Helper

Run:

```bash
python3 scripts/gate_check.py --task-dir <run_dir> --target short
python3 scripts/gate_check.py --task-dir <run_dir> --target csur
```

The helper checks deterministic parts of Gates 1-4. The orchestrator still performs qualitative review for Gate 5.
