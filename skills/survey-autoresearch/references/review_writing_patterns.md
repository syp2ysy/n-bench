# Review Writing Patterns

Use this reference before drafting or revising `outputs/review.md`.

These patterns make the review synthesize, teach, and argue. For `target=csur`, first read `csur_exemplar_patterns.md` and write `state/csur_imitation_plan.md`; use this file for general writing moves after the CSUR pattern is selected.

## Source Cues

Use these as writing-craft cues, not as default CSUR exemplars:

- ACM Computing Surveys describes survey articles as organizing research in a novel way that integrates and adds understanding to the field: https://dl.acm.org/journal/csur/editorial-charter
- IEEE Communications Surveys & Tutorials emphasizes tutorials and surveys that put results in context and remain comprehensible outside the specialty: https://www.comsoc.org/publications/journals/ieee-comst/policies-guidelines
- Annual Reviews examples show review articles synthesizing diverse approaches into integrated frameworks and critical assessments: https://www.annualreviews.org/content/journals/10.1146/annurev-environ-012420-043621 and https://www.annualreviews.org/content/journals/10.1146/annurev-environ-012320-084937
- Nature Reviews article listings illustrate concise review summaries that state the topic, scope, and forward-looking opportunities: https://www.nature.com/natrevmats/articles?type=review-article

When drafting, translate these cues into concrete artifacts: thesis, conceptual model, field map, benchmark landscape, method taxonomy, design pipeline, synthesis tables, evidence ladder, related-survey differentiation, and research agenda.

Artifacts are not the article. Use `references/article_layer.md` and `references/publication_prose_translation.md` before final drafting: research artifacts support the article, synthesis artifacts organize the article, and `review.md` must read like publication-facing prose.

## What Strong Reviews Do

1. **Teach a lens**: the reader should leave with a framework, not only a bibliography.
2. **State a thesis**: a strong review has a claim about how the field should be understood.
3. **Organize by ideas**: use mechanisms, tensions, levels, design choices, or evidence gaps; avoid chronology or task lists unless the review is explicitly historical or task-centered.
4. **Compare, do not catalog**: papers are evidence for claims, not the units of the outline.
5. **Name trade-offs**: every method family should have strengths, failure modes, and the conditions where it is appropriate.
6. **Use display items**: tables, boxes, figures, frameworks, and evaluation ladders carry synthesis.
7. **Separate evidence from speculation**: distinguish what is demonstrated, suggested, assumed, and still untested.
8. **End with an agenda**: future directions should follow from evidence gaps, not generic "more robustness" language.

## Required Artifacts For Full Surveys

Write these before or during synthesis:

- `state/review_style_audit.md`: reader contract, central thesis, conceptual contribution, related-survey differentiation, anti-dump check.
- `state/paper_cards.jsonl`: A/B paper extraction with survey role, mechanism, system component or node, interface, evidence spans, failure modes, limitations, and what the paper teaches the survey.
- `state/system_node_cards.jsonl`: system or method components with role, why they matter, inputs, outputs, representative papers, failure modes, and evaluation signals.
- `state/section_cards.jsonl`: reader question, section thesis, section structure, opening move, subsection moves, closing implication, and required display item for every major section.
- `outputs/conceptual_framework.md`: central thesis, system model, node/component interactions, taxonomy axes, running example, and related-survey delta.
- `outputs/review.md`: thesis-driven review, not workflow report.
- A field map that tells a new reader what tasks, benchmarks, method families, and evaluation settings define the area.
- A benchmark landscape table with representative benchmarks/datasets, task type, capability pressure, metrics, and limitations.
- A method taxonomy table with families, design choices, strengths, failure modes, and representative work.
- A method design pipeline or decision flow: problem framing -> representation -> integration interface -> evaluation.
- An evaluation protocol section with metrics, baselines, ablations, confounders, stress tests, and reporting checklist.
- Practical design guidelines or a decision table that helps readers choose a method family for a concrete problem.
- At least three synthesis tables or boxes for a full-length review.
- `outputs/article_plan.md` selecting article-facing tables, case-study boxes, appendix-facing exhaustive artifacts, and section transitions.
- `outputs/coverage_matrix.md` mapping the broad literature; summarize it in the article rather than pasting the full matrix.
- A "take-home findings" or equivalent synthesis section.
- An open-problem section where each problem has: evidence gap, why it matters, and a concrete research move.

If a full review has a strong conceptual thesis but lacks benchmark and method-design scaffolding, treat it as an essay rather than a survey draft and revise before completion.

## Section-Level Checklist

Each major section should pass:

- The first paragraph makes an argument or names a tension.
- The section compares at least two families, designs, or assumptions.
- Citations support claims instead of replacing analysis.
- The final paragraph tells the reader what follows for system design, benchmark design, or theory.

Draft major sections from `state/section_cards.jsonl`. The opening paragraph should answer the reader question and establish the section thesis before papers appear. The middle paragraphs compare families using paper-card evidence. The closing paragraph should state the design, evaluation, or research implication.

Rewrite the section if:

- It begins with "Paper A does..., Paper B does..., Paper C does...";
- It can be moved anywhere in the review without breaking the argument;
- It has many citations but no trade-off;
- It describes a task without explaining what the task reveals about the survey object.
- It names a benchmark without stating what capability, metric, or confounder the benchmark tests.
- It names a method family without explaining its design pipeline, inputs, outputs, controller interface, and failure modes.

## Useful Review Moves

- **Reframing move**: "The field is usually described as X; a more useful object is Y."
- **Tension move**: "The literature optimizes A and B, but these goals conflict under C."
- **Ladder move**: arrange evidence from weak to strong and use it to judge claims.
- **Matrix move**: compare families across orthogonal dimensions.
- **Failure-mode move**: organize gaps by why systems fail, not by where papers appeared.
- **Bridge move**: connect adjacent fields that solve the same problem under different names.
- **Agenda move**: turn each weakness into an evaluable research direction.
- **Tutorial move**: after introducing a taxonomy, show how a reader would design, evaluate, and debug a representative system.

## Anti-Dump Heuristics

- If a paragraph has more than five citations, it needs an explicit synthesis claim.
- If a section has no table, contrast, or named tension, check whether it is only a catalog.
- If the abstract says "we survey" but not "we argue" or "we propose a framework", rewrite.
- If the conclusion repeats the abstract, replace it with take-home findings.
- If open problems are not linked to current evidence gaps, rewrite them.
- If a full survey lacks benchmark tables, method-family tables, metric/ablation discussion, or practical design guidance, it is too high-level.
- If the body explains a prior mistake, user audit, scope correction, or says the review is "not X", "not task-centered", or "not a paper list", rewrite it as a positive synthesis of the field object.
- If a sentence reads like internal notes joined by semicolons, such as "family A exposes issue X; family B exposes issue Y", rewrite it into publication-facing prose that explains the evaluation condition, evidence, and implication.
- If the body names internal state files, draft versions, sprint history, or what a "good survey" should do, move that material to `outputs/final_report.md` or `state/`.
- If a method/system review opens with task-family chapters, rewrite the opening sections around mechanisms, representations, interfaces, evidence, or design choices.
- If related-survey positioning only says "newer", "broader", "larger", or "more comprehensive", add a structural contribution such as a taxonomy, framework, evidence matrix, evaluation protocol, or design agenda.

## Tone And Style

Prefer a confident scholarly voice:

- Define concepts before naming many papers.
- Use precise scholarly verbs such as "distinguishes", "operationalizes", "constrains", "trades off", "fails when", "requires", and "tests". Avoid compressed scaffold verbs when they turn sections into checklist notes.
- Avoid inflated claims when evidence is preprint-heavy.
- Avoid workflow narration in the review body; keep search details concise and put process logs in `final_report.md`.
- Avoid defensive correction prose in the review body. A survey should tell readers how the field is organized, not how the draft was rescued from a biased outline.

## Scaffold To Prose

Use internal notes to think, then translate them before publication:

- Internal: "benchmark family A exposes pressure X; benchmark family B exposes pressure Y."
- Article prose: "Benchmark families operationalize different validity conditions. Family A tests whether X remains reliable under realistic constraints, whereas family B tests whether Y can be supported by grounded evidence."
- Internal: "good methods can be mapped back to the framework."
- Article prose: "The framework is useful only if it predicts design and evaluation differences; therefore each method family is compared by records, interfaces, maintenance operations, and evidence requirements."

## Completion Standard

A review is complete only when a reader can answer:

- What is the central conceptual object?
- What taxonomy or framework did this review contribute?
- Which benchmarks, datasets, metrics, and confounders define the field?
- How do representative methods differ in design, not just in results?
- How would a new researcher choose and evaluate a system or method family?
- What are the main design trade-offs?
- Which claims are well supported, and which remain speculative?
- What should the next benchmark or method measure?
