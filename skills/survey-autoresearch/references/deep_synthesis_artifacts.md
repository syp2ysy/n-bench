# Deep Synthesis Artifacts

Use this reference for `target=full` and `target=csur` before drafting `outputs/review.md`.

## Required Flow

1. Triage retained papers by survey role: `foundational`, `seminal`, `system`, `benchmark`, `application`, `negative` or `failure`, `survey`, `bridge`, `frontier`.
2. Write `state/paper_cards.jsonl` for A/B papers.
3. Derive `state/paper_facts.jsonl` from paper cards with `scripts/derive_paper_facts.py` when CSUR tables need the compact schema.
4. Build `state/system_node_cards.jsonl` from the paper cards.
5. Derive taxonomy and section plan from node coverage, not from seed keywords alone.
6. Write `outputs/conceptual_framework.md` before `outputs/review.md`.
7. Convert deep artifacts into final-review artifacts before drafting: `worked_examples.md`, `benchmark_landscape.md`, `method_taxonomy.md`, `node_paper_matrix.md`, `glossary.md`, `running_example.md`, `evaluation_protocol.md`, `design_guidelines.md`, and `section_dossiers/`.

`state/research_questions_by_perspective.md` is the exploration layer. `state/research_questions.md` is the converged layer. Each final research question should state which perspective questions it derives from.

## Paper Cards

Each A/B paper card must explain what the paper teaches the survey. Required content:

```json
{
  "paper_id": "p001",
  "survey_role": "foundational | seminal | system | benchmark | application | negative | failure | survey | bridge | frontier",
  "problem": "What problem this paper makes visible.",
  "method_summary": "How the paper's mechanism works.",
  "system_node": "The system node this paper clarifies.",
  "mechanism_or_contribution": "Concrete mechanism or benchmark contribution.",
  "representation": "Main representation, if applicable.",
  "inputs": ["inputs to the mechanism"],
  "outputs": ["outputs used by later components"],
  "write_policy": "How records/state are created, if applicable.",
  "read_policy": "How records/state are retrieved, if applicable.",
  "update_or_consolidation": "How state is revised, compressed, or forgotten.",
  "controller_interface": "How the mechanism affects a downstream decision.",
  "evaluation_tasks": ["tasks or settings"],
  "metrics": ["metrics"],
  "baselines": ["baselines"],
  "ablations": ["ablations"],
  "failure_modes": ["what fails"],
  "limitations": ["what remains untested"],
  "what_it_teaches_the_survey": "Why this paper matters for the review's argument.",
  "evidence_spans": ["section/table/page-level evidence summaries"]
}
```

Avoid generic records that only say method family, task family, and limitations. Those records cannot support a deep survey.

Every A/B paper in `state/citation_plan.jsonl` must have a paper card. Missing A/B cards fail the deep-synthesis gate.

## System Node Cards

Each node card must contain:

- `node`;
- `role_in_system`;
- `why_it_matters` or `why_it_matters_in_embodiment`;
- `inputs` and `outputs`;
- `main_design_families`;
- at least two `representative_papers`;
- `failure_modes`;
- `evaluation_signals`;
- `open_questions`;
- `status`: `covered`, `weak`, or `gap`.

The node card should teach why the component exists, not merely where it appears in an architecture diagram.

Representative papers must exist in `state/paper_cards.jsonl`. Every nonempty `system_node` or `memory_node` named in paper cards must be covered by a node card. A `gap` node may have fewer than two representative papers, but it must include `gap_reason` rather than inventing coverage.

## Conceptual Framework

`outputs/conceptual_framework.md` must contain:

1. central thesis;
2. system diagram in words;
3. node list and node interactions;
4. taxonomy axes;
5. running example;
6. what the framework explains that prior surveys do not.

This file is the bridge between literature extraction and article prose.

## Final-Review Absorption

The cards are not the deliverable. For full and CSUR targets:

- A papers must become worked examples in `outputs/worked_examples.md` and `outputs/review.md`.
- B papers must appear in comparison tables such as method taxonomy, benchmark landscape, or node-paper matrix.
- System-node cards must become a node-paper matrix with mechanism pattern, evidence, failure mode, and evaluation signal.
- Section cards must become section dossiers before article prose is drafted.
- A final review that only summarizes the cards into high-level prose fails the review-depth gate.
