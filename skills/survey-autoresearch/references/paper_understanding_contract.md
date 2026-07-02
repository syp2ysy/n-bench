# Paper Understanding Contract

`state/paper_mechanism_cards.jsonl` is the single deep-reading source of truth.

Every A/B paper needs:

- `paper_id`, `title`, `survey_role`, `level`
- `motivation`
- `problem_setting`
- `task_definition`
- `benchmark_or_dataset`
- `method_pipeline`
- `implementation_details`
- `experimental_setup`
- `main_results`
- `limitations_and_confounders`
- `relation_to_prior_work`
- `what_it_changes_in_the_survey_argument`
- `must_not_overclaim`
- `evidence_spans`

The card explains a scientific contribution, not a survey bucket. It must answer why the paper exists, what task it studies, how the method works, how it was evaluated, what the results support, what they do not support, and how the paper changes the survey argument.

A/B papers without results, baselines, ablations, or limitations must be downgraded or marked as evidence-limited.
