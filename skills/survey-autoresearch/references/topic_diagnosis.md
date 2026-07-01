# Topic Diagnosis

Use this before taxonomy lock.

`state/topic_diagnosis.yml` chooses the survey architecture. It prevents every topic from being forced into the same system-node template.

Required fields:

```yaml
primary_survey_type: system-object
secondary_lenses:
  - benchmark/evaluation
  - method-family
domain_pressures:
  - partial observability
  - closed-loop control
evidence_norm:
  preprint_heavy: true
  benchmark_fragmentation: high
recommended_structure:
  - foundations
  - system model
  - method families
  - benchmark landscape
  - evaluation protocol
excluded_templates:
  - pure chronological history
section_grammar:
  Introduction:
    - field shift
    - gap
    - framework
    - contributions
  Method Families:
    - bottleneck
    - mechanism
    - comparison
    - benchmark tie
    - implication
```

Survey types:

- `system-object`: systems, architectures, memory, planners, world models, retrieval systems, interfaces.
- `method-family`: uncertainty quantification, prompting, multimodal learning, optimization, alignment.
- `benchmark/evaluation`: datasets, metrics, protocols, robustness tests, leaderboards.
- `application-domain`: healthcare, education, laboratory robotics, materials discovery, finance.
- `risk/threat`: security, privacy, robustness, misuse, governance.

Choose one primary type plus secondary lenses. The article skeleton follows the primary type; secondary lenses define extra benchmark, risk, or application sections.
