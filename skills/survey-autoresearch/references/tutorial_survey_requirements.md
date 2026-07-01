# Tutorial Survey Requirements

Use this reference for `target=full` and `target=csur`.

A long survey must teach the field, not only describe a framework. Before final synthesis, prepare:

- `outputs/glossary.md`: define core terms a newcomer needs before method sections.
- `outputs/running_example.md`: one concrete system example carried through capture, representation, storage, retrieval, update, controller interface, and evaluation.
- `outputs/review.md`: include a tutorial primer section that uses the glossary and running example.

The review should let a newcomer answer:

1. What is the surveyed object?
2. What data structures or records flow through it?
3. Which method families exist and how do they differ?
4. Which benchmarks test which capability?
5. Which baselines or ablations prove the mechanism is used?
6. Which method family should be chosen for a new problem?

If the answer to any question is only "read the state files", synthesis has failed.
