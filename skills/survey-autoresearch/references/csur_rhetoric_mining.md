# CSUR Rhetoric Mining

Use this reference for `target=csur` after reading `references/csur_exemplar_patterns.md`.

## Required Output

Write `state/csur_style_patterns.yml` before synthesis. It must include:

```yaml
exemplar_evidence:
  - doi: "10.1145/3711118"
    exemplar: "Data-centric Artificial Intelligence: A Survey"
    abstract_moves_observed:
      - move: "field importance"
        evidence_note: "Short paraphrase of the observed abstract move."
    introduction_moves_observed:
      - move: "scope and lifecycle framing"
        evidence_note: "Short paraphrase of the observed introduction move."
    section_rhetoric_observed:
      - section_type: "lifecycle stage"
        opening_move: "How the section opens."
        body_move: "How comparisons are developed."
        closing_move: "How the section closes."
    table_functions_observed:
      - "What a table helps the reader compare."
    conclusion_moves_observed:
      - "How the conclusion turns findings into agenda."
abstract_moves:
  - field_importance
  - fragmentation_or_gap
  - organizing_framework
  - evidence_artifacts
  - agenda
introduction_moves:
  - broad_problem
  - why_existing_views_fail
  - survey_object_definition
  - contributions
  - roadmap
section_patterns:
  system_model:
    structure: "总-分-总"
    opening: "define object and tension"
    body: "node-by-node explanation with representative systems"
    closing: "design or evaluation implication"
table_functions:
  - "compare mechanisms, interfaces, evidence, and limitations"
paragraph_patterns:
  - "claim -> contrast -> evidence -> implication"
  - "framework element -> representative systems -> failure mode -> design lesson"
forbidden_surface_forms:
  - "Paper A proposes..."
  - "This section surveys..."
```

## What To Mine From Exemplars

For each selected official ACM Computing Surveys exemplar, record:

- how the abstract moves from motivation to contribution;
- how the introduction introduces the field object before listing work;
- how each method or benchmark section opens;
- what each table is doing for the reader;
- how limitations and open challenges are linked to evidence gaps;
- how the conclusion states take-home findings rather than repeating the abstract.

Do not stop at DOI, year, section skeleton, or article title. CSUR imitation means learning argument moves and section rhetoric.

The gate requires observed evidence from at least two official CSUR DOI records. Do not copy only the generic template above.
