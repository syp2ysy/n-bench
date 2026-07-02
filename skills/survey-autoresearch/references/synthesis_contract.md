# Synthesis Contract

Synthesis turns verified papers into comparison structures.

Required synthesis outputs:

- `outputs/method_family_dossiers/`
- `outputs/benchmark_dossiers/`
- `outputs/related_survey_matrix.md`
- `state/argument_graph.yml`

Method-family dossiers should explain motivation, assumptions, representative papers, common benchmarks, strengths, failure modes, adjacent-family comparisons, evidence status, and open questions.

Benchmark dossiers should explain capability tested, environment, input/output, metrics, standard baselines, what the benchmark can and cannot prove, memory or method-specific controls needed, confounders, and representative papers.

`state/argument_graph.yml` must include:

- central thesis
- field shift
- gap in existing surveys
- argument nodes with claim, evidence, implication, section, and `leads_to`
- section order
- take-home findings

Sections are not a table of contents; they are an argument dependency chain.
