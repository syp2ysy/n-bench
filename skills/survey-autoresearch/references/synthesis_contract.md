# Synthesis Contract

Synthesis turns verified papers into comparison structures.

Required synthesis outputs:

- `state/paper_contribution_statements.jsonl`
- `outputs/contribution_tree.yml`
- `state/scenario_definitions.yml`
- `state/taxonomy_alignment.jsonl`
- `state/comparative_evidence_matrix.jsonl`
- `outputs/method_family_dossiers/`
- `outputs/benchmark_dossiers/`
- `outputs/related_survey_matrix.md`
- `state/section_evidence_plans.jsonl`
- `state/argument_graph.yml`

Method-family dossiers should explain motivation, assumptions, representative A papers, supporting B papers, shared mechanism pattern, differences among representative papers, relation graph, common benchmarks, evidence strength, failure modes, open questions, and how the family advances the central story.

Benchmark dossiers should explain capability tested, task formulation, input/output, environment or dataset, metrics, baselines, reported memory-specific ablations, missing diagnostic controls, what the benchmark can and cannot support, representative papers, and confounders.

`state/taxonomy_alignment.jsonl` must compare the article taxonomy with verified related surveys or field roadmaps. Full targets need at least six top related-survey records, and CSUR targets need at least ten. Each record must identify the source, include `paper_id` or `source_paper_id`, explain why it is a top related survey, extract the existing taxonomy and relevant sections, state coverage overlap, coverage gap, taxonomy delta, and article-taxonomy necessity, map article categories to existing categories, justify agreement and delta, and back each article-category delta with A/B paper evidence. The linked related-survey ID must be retained, source-verified, and audited as `direct_related_survey`; raw survey-like candidates that were not retained and verified do not satisfy alignment.

`validate_related_survey_alignment.py` audits recorded related-survey alignment; it does not replace discovery. Missing important surveys remains a discovery/coverage and expert-review failure.

`state/comparative_evidence_matrix.jsonl` grounds recommendations in papers. Each method, evaluation, or design recommendation should list supporting papers and show whether those papers report protocol, metric, baseline, ablation/control, and confounder. Minimum evaluation packages must be derived from this matrix, not from author preference alone.

`state/argument_graph.yml` must include:

- central thesis
- field shift
- gap in existing surveys
- paradigm evidence norms
- contribution tree reference and candidate spines derived from the contribution tree
- story skeleton
- community taxonomy nodes
- taxonomy competition
- paper relation graph
- exemplar delta
- figure plan
- argument nodes with claim, evidence, scenario links, method-family links, benchmark links, implication, section, and `leads_to`
- section order
- take-home findings

Sections are not a table of contents; they are an argument dependency chain.

Contribution abstraction:

- `state/paper_contribution_statements.jsonl` records one standard contribution sentence per A/B paper.
- Each statement must include problem, method, benchmark or task, result, limitation, evidence strength, and source reference.
- `outputs/contribution_tree.yml` clusters those statements into reader-facing branches with motivation, representative papers, core tradeoff, evidence standard, and failure risks.
- The contribution tree is a spine generator. It should propose candidate article spines and feed `state/argument_graph.yml`; it is not a raw appendix table.

For full or CSUR surveys, the argument graph must show why the final article spine is field-native. It must compare at least two possible taxonomies, such as system-node taxonomy versus Cascaded/Joint WAM taxonomy, and record why the selected spine gives readers a better map of the field.

`paradigm_evidence_norms` should mirror `state/survey_type_plan.yml` and state the proof standard for the field: required evidence units, common confounders, and what strong claims cannot infer. Argument nodes should use these norms when deciding whether a paper supports a mechanism, result, benchmark-property, comparison, or open-problem claim.

Each argument node should include a `section_role`, such as definition, background, taxonomy, data ecosystem, evaluation protocol, diagnostic lens, application scenario, open challenge, or conclusion. The role prevents sections from becoming only evidence buckets.

The figure plan must be reader-facing before drafting. It should include the article's roadmap/taxonomy figure, method evolution or timeline, data ecosystem figure/table, and evaluation protocol matrix whenever relevant to the topic.

Before drafting each article-body section, write a section evidence plan that maps the section to its argument node, scenario definitions, method families, anchor papers, benchmarks, required comparisons, evidence spans, and overclaim boundaries.
