# Survey Type Contract

Every full or CSUR run starts with `state/survey_type_plan.yml`.

Required fields:

- `topic`
- `primary_type`: `system-object`, `method-family`, `benchmark/evaluation`, `risk/threat`, or `application-domain`
- `secondary_lenses`
- `why_this_type`
- `why_not_other_types`
- `article_skeleton`
- `excluded_templates`

Topic-specific defaults:

- `system-object`: components, interfaces, lifecycle, evaluation.
- `method-family`: assumptions, method families, metrics, applications, limitations.
- `benchmark/evaluation`: capabilities, protocols, metrics, baselines, confounders, missing tests.
- `risk/threat`: assets, threat model, attack surfaces, defenses, evaluation, governance gaps.
- `application-domain`: tasks, data, workflows, methods, deployment, evaluation.

Do not force system-component artifacts onto non-system topics. Do not organize a system-object topic as a task list unless explicitly requested.
