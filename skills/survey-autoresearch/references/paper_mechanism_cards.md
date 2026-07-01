# Paper Mechanism Cards

Use this before synthesis for `target=full` and `target=csur`.

`state/paper_mechanism_cards.jsonl` is the canonical deep extraction layer. It explains a paper as a scientific contribution, not only as a survey category.

Each A-level paper needs:

```json
{
  "paper_id": "",
  "title": "",
  "venue_status": "",
  "level": "A",
  "survey_role": "foundational | method | benchmark | system | application | negative | survey | frontier",
  "motivation": "Why this paper was needed.",
  "problem_setting": "The concrete task or problem setting.",
  "task_definition": "Inputs, outputs, action space, or protocol.",
  "benchmark_or_environment": [],
  "method_overview": "Mechanism-level summary, not a slogan.",
  "architecture_or_pipeline": [],
  "memory_design": {
    "record_schema": [],
    "write_trigger": "",
    "storage": "",
    "read_key": "",
    "update_policy": "",
    "controller_interface": ""
  },
  "implementation_details": {
    "model_backbone": "",
    "retriever_or_map": "",
    "planner_or_policy": "",
    "training_or_inference_setup": ""
  },
  "experimental_setup": {
    "datasets_envs": [],
    "metrics": [],
    "baselines": [],
    "ablations": []
  },
  "main_results": [
    {
      "claim": "",
      "evidence": "",
      "strength": "demonstrates | shows | suggests | may indicate | hypothesizes"
    }
  ],
  "limitations_and_confounders": [],
  "comparison_to_prior_work": "",
  "how_it_changes_the_survey_argument": "",
  "evidence_spans": []
}
```

B-level papers may use the same schema with lighter implementation detail, but they still need task, method, benchmark/evidence role, limitations, and survey-use fields. C-level papers belong in `outputs/coverage_matrix.md` and bibliography; they must not support mechanism or result claims in the review body.

Use `scripts/derive_paper_cards_from_mechanism_cards.py` to generate compatibility `state/paper_cards.jsonl` when needed.
