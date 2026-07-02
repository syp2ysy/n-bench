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
- argument nodes with claim, evidence, scenario links, method-family links, benchmark links, implication, section, and `leads_to`
- section order
- take-home findings

Sections are not a table of contents; they are an argument dependency chain.

Before drafting each article-body section, write a section evidence plan that maps the section to its argument node, scenario definitions, method families, anchor papers, benchmarks, required comparisons, evidence spans, and overclaim boundaries.
