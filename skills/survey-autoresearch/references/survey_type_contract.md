# Survey Type Contract

Every full or CSUR run starts with `state/survey_type_plan.yml`.

Required fields:

- `topic`
- `primary_type`: `system-object`, `method-family`, `benchmark/evaluation`, `risk/threat`, or `application-domain`
- `secondary_lenses`
- `exemplar_alignment`
- `community_native_taxonomy`
- `exemplar_section_patterns`
- `candidate_article_spines`
- `selected_article_spine`
- `why_not_exemplar_spine`
- `figure_first_plan`
- `science_paradigm_profile`
- `evidence_norms`
- `required_evidence_units`
- `common_confounders`
- `why_this_type`
- `why_not_other_types`
- `article_skeleton`
- `excluded_templates`

For full or CSUR runs, do not choose the article spine from topic type alone. First perform exemplar-aligned outline design:

- Identify 1-3 high-quality adjacent surveys, official tutorials, or field roadmaps.
- Extract their section patterns, taxonomy spine, figures, data/evaluation treatment, and open-problem style.
- Compare at least two candidate article spines, including one community-native taxonomy if the field has one.
- Select an article spine and explicitly state why it should differ from or follow the exemplar pattern.
- Treat `primary_type` as an analysis lens, not an automatic table of contents.

`community_native_taxonomy` should name the field-native organizing vocabulary, such as Cascaded/Joint WAM for World Action Models. If the final article does not use the community-native taxonomy as its spine, `why_not_exemplar_spine` must explain why.

`figure_first_plan` must specify at least the core roadmap or taxonomy figure, plus any timeline, data ecosystem, evaluation matrix, or diagnostic lens figures needed for a mature survey.

Topic-specific defaults:

- `system-object`: components, interfaces, lifecycle, evaluation.
- `method-family`: assumptions, method families, metrics, applications, limitations.
- `benchmark/evaluation`: capabilities, protocols, metrics, baselines, confounders, missing tests.
- `risk/threat`: assets, threat model, attack surfaces, defenses, evaluation, governance gaps.
- `application-domain`: tasks, data, workflows, methods, deployment, evaluation.

Do not force system-component artifacts onto non-system topics. Do not organize a system-object topic as a task list unless explicitly requested.

Science paradigm profile:

- `science_paradigm_profile` names the community evidence regime, such as `ML/AI systems`, `robotics/embodied-ai`, `biomedicine/clinical`, `materials/chemistry`, `theory/math`, `benchmark/evaluation`, or `social/scientific policy`.
- `evidence_norms` states what the community accepts as meaningful evidence.
- `required_evidence_units` lists required proof objects such as benchmark, dataset, theorem, simulation, physical experiment, clinical endpoint, baseline, ablation, uncertainty estimate, OOD split, or statistical test.
- `common_confounders` lists failure modes that article claims must control or acknowledge.

The profile prevents the skill from using one field's proof standard for another field. For example, a robotics survey normally needs benchmark, baseline, ablation, sim-real or OOD boundaries, and controller/perception confounders; a theory survey needs definitions, lemmas, theorem statements, proof dependencies, and boundary cases.

Every full or CSUR run also writes `state/scenario_definitions.yml`. The definitions follow the primary survey type and secondary lenses rather than forcing a system-component schema onto all topics.
