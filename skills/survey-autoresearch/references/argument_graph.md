# Argument Graph

Use this after mechanism extraction and before `outputs/article_plan.md`.

`state/argument_graph.yml` controls the survey's logic. It explains why sections appear in this order and how each section advances the central thesis.

Required structure:

```yaml
central_thesis: >
  The main claim about how the field should be understood.
field_shift: >
  What changed in the field.
gap_in_existing_surveys: >
  Why prior organization is insufficient.
argument_nodes:
  A1:
    claim: Existing views fragment the mechanism.
    evidence: [related_surveys]
    strength: suggests
    section: Introduction
    leads_to: [A2]
  A2:
    claim: The proposed taxonomy explains method behavior.
    evidence: [paper_mechanism_cards, method_taxonomy]
    strength: shows
    section: Method Taxonomy
    leads_to: [A3]
section_order:
  - Introduction
  - Method Taxonomy
takeaway_findings:
  - A concise finding derived from the graph.
```

Rules:

- Every major section must correspond to at least one argument node.
- Each node needs claim, evidence, strength, section, and `leads_to`.
- The last node may have an empty `leads_to`.
- `outputs/article_plan.md` must follow `section_order`.
- Do not draft `review.md` directly from paper cards or tables; draft from the argument graph, article plan, and section dossiers.
