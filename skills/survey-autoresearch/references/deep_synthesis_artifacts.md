# Deep Synthesis Artifacts

Use this reference for `target=full` and `target=csur` before drafting `outputs/review.md`.

## Required Flow

1. Triage retained papers by survey role: `foundational`, `system`, `benchmark`, `application`, `negative` or `failure`, `survey`, `bridge`, `frontier`.
2. Write `state/paper_cards.jsonl` for A/B papers.
3. Build `state/system_node_cards.jsonl` from the paper cards.
4. Derive taxonomy and section plan from node coverage, not from seed keywords alone.
5. Write `outputs/conceptual_framework.md` before `outputs/review.md`.

## Paper Cards

Each A/B paper card must explain what the paper teaches the survey. Required content:

```json
{
  "paper_id": "p001",
  "survey_role": "foundational | system | benchmark | application | negative | failure | survey | bridge | frontier",
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
- `open_questions`.

The node card should teach why the component exists, not merely where it appears in an architecture diagram.

## Conceptual Framework

`outputs/conceptual_framework.md` must contain:

1. central thesis;
2. system diagram in words;
3. node list and node interactions;
4. taxonomy axes;
5. running example;
6. what the framework explains that prior surveys do not.

This file is the bridge between literature extraction and article prose.
