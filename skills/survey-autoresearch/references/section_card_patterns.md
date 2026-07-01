# Section Card Patterns

Use this reference before writing or revising major sections in `outputs/review.md`.

## Required Section Card

Every major section in a full or CSUR survey needs a `state/section_cards.jsonl` record:

```json
{
  "section_id": "S4",
  "title": "Representation and Grounding",
  "reader_question": "What should the reader understand after this section?",
  "section_thesis": "The section's one-sentence argument.",
  "structure": "总-分-总",
  "opening_move": "Define the tension or capability before naming papers.",
  "subsection_moves": [
    {
      "subsection": "A method family or design choice",
      "claim": "What this subsection argues.",
      "papers": ["p001", "p014"],
      "required_comparison": "What must be compared.",
      "implication": "What follows for design, evaluation, or theory."
    }
  ],
  "closing_move": "Design or evaluation implication and transition.",
  "required_display_item": "Table, figure, box, or checklist used by the section."
}
```

Each `subsection_moves` entry must be an object. It needs `subsection`, `claim`, `required_comparison`, and `implication`. It also needs at least two paper IDs, unless the move is explicitly about a gap and includes `gap_reason`.

## Section Grammar

- Introduction: broad problem -> why existing views are incomplete -> survey object -> contributions -> roadmap.
- Foundations: definition -> boundary cases -> running example -> taxonomy preview.
- System model: total picture -> node-by-node explanation -> design/evaluation implication.
- Method taxonomy: classification dimension -> mechanism families -> representative papers -> trade-off.
- Benchmarks: capability -> protocol/dataset -> metric -> confounder -> missing test.
- Open problems: evidence gap -> why hard -> concrete research move.

## Paragraph Grammar

Prefer:

- claim -> contrast -> evidence -> implication;
- framework element -> representative systems -> failure mode -> design lesson;
- capability -> benchmark protocol -> metric -> confounder -> missing ablation.

Avoid:

- paper-by-paper paragraphs;
- task chapters without explaining what the task tests;
- sections that can be moved anywhere without changing the argument;
- introductions that start by listing many papers before stating the object.
