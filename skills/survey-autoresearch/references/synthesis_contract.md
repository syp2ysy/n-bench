# Synthesis Contract

Synthesis turns verified papers into comparison structures.

Required synthesis outputs:

- `state/scenario_definitions.yml`
- `outputs/method_family_dossiers/`
- `outputs/benchmark_dossiers/`
- `outputs/related_survey_matrix.md`
- `state/section_evidence_plans.jsonl`
- `state/argument_graph.yml`

Method-family dossiers should explain motivation, assumptions, representative A papers, supporting B papers, shared mechanism pattern, differences among representative papers, relation graph, common benchmarks, evidence strength, failure modes, open questions, and how the family advances the central story.

Benchmark dossiers should explain capability tested, task formulation, input/output, environment or dataset, metrics, baselines, reported memory-specific ablations, missing diagnostic controls, what the benchmark can and cannot support, representative papers, and confounders.

`state/argument_graph.yml` must include:

- central thesis
- field shift
- gap in existing surveys
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

For full or CSUR surveys, the argument graph must show why the final article spine is field-native. It must compare at least two possible taxonomies, such as system-node taxonomy versus Cascaded/Joint WAM taxonomy, and record why the selected spine gives readers a better map of the field.

Each argument node should include a `section_role`, such as definition, background, taxonomy, data ecosystem, evaluation protocol, diagnostic lens, application scenario, open challenge, or conclusion. The role prevents sections from becoming only evidence buckets.

The figure plan must be reader-facing before drafting. It should include the article's roadmap/taxonomy figure, method evolution or timeline, data ecosystem figure/table, and evaluation protocol matrix whenever relevant to the topic.

Before drafting each article-body section, write a section evidence plan that maps the section to its argument node, scenario definitions, method families, anchor papers, benchmarks, required comparisons, evidence spans, and overclaim boundaries.
