# Taxonomy And Structure

Use this reference when building the review outline, taxonomy, and narrative.

## Topic Lock

Phase 0 records:
- scope;
- angle;
- audience;
- exclusions;
- target length;
- output format;
- assumptions made without user interaction.

If a topic is broad, narrow it through the written task spec rather than asking repeated questions.

## Taxonomy Rules

Use a multi-axis taxonomy, not a flat list.

Early taxonomy axes are hypotheses for search, not the final structure. For `target=full` and `target=csur`, lock the final taxonomy only after:
- multi-perspective questions are written;
- A/B papers have `state/paper_cards.jsonl` records;
- major components or nodes have `state/system_node_cards.jsonl` records;
- weak or over-dominant cells have been repaired.

First decide the survey spine:
- system-first: for architectures, planners, world models, retrieval systems, tool-use systems, or other composed systems;
- method-first: for algorithms or model families;
- task-first: only when the user explicitly asks for a task or benchmark survey;
- benchmark-first: for evaluation papers;
- theory-first: for conceptual or formal surveys.

If the topic is a system object, tasks and benchmarks are evaluation settings that make system assumptions observable. Do not organize the whole survey as a sequence of downstream tasks unless the user explicitly asked for that. A task-first outline for a system-object topic is a scope failure unless it is justified in `state/scope_audit.md`.

This is a general rule. Task-biased seeds initialize recall but cannot define the spine for a method, system, architecture, representation, or theory survey.

Good axes include:
- method family x application domain;
- architecture x autonomy level;
- objective x training signal;
- benchmark x capability;
- failure mode x mitigation.
- system component x operation;
- representation x interface;
- mechanism x lifecycle operation;
- assumption x evaluation ablation.

Requirements:
- Each taxonomy cell should eventually have at least two A/B references or be marked as a gap.
- System-node or component coverage should also be tracked for system-object topics.
- Empty cells are useful gap-analysis material.
- Spanning methods are not errors; they reveal taxonomy tension.
- A taxonomy should be redesigned if review feedback says it is only a list.
- A taxonomy should be redesigned if one seed-heavy task family dominates the outline while other task families use the same underlying system object.

## Survey Structure

Default full-survey structure:

1. Introduction: hook, gap, contributions, roadmap.
2. Background: definitions and taxonomy overview.
3. Field map: task families, benchmarks/datasets, metrics, and capability pressures.
4. Core method sections: one family or axis per section.
5. Method design pipeline: how to choose representations, mechanisms, operations, and interfaces.
6. Comparative synthesis: tables and cross-paper analysis.
7. Evidence and benchmarks: empirical or literature-derived comparison, ablations, and confounders.
8. Practical design guidelines: what to build first under common constraints.
9. Open problems: barrier plus attack vector.
10. Conclusion: numbered findings, not an abstract repeat.

Default CSUR-grade structure. For `target=csur`, refine this after reading `csur_exemplar_patterns.md` and writing `state/csur_imitation_plan.md`:

1. Introduction: scope, research questions, contributions, and why the survey object matters.
2. Survey methodology: databases/routes, search strings, inclusion/exclusion criteria, screening counts, and source limitations.
3. Related surveys: matrix comparing what prior surveys organize around, what they miss, and what this review adds.
4. Foundations and definitions: central terms and conceptual object.
5. Field and benchmark landscape: tasks, datasets, protocols, metrics, confounders, and targeted ablations.
6. Evidence-backed method taxonomy: families derived from A/B paper facts rather than only prose intuition.
7. Design patterns and system pipeline: representations, mechanisms, operations, and interfaces.
8. Evaluation and meta-analysis: metric patterns, ablations, benchmark gaps, and threats to validity.
9. Practical guidance and open problems: recipes and agenda tied to evidence gaps.
10. Threats to validity and conclusion.

For system-object surveys, prefer:

1. Introduction: define the system object and why existing survey views leave a gap.
2. System model: components, representations, operations, interfaces, and evaluation.
3. Field map: representative tasks and benchmarks as evaluation settings where the system object is tested.
4. Store/representation families.
5. Lifecycle or workflow operations.
6. Policy/planner/controller interfaces.
7. Method design pipeline and practical decision table.
8. Tasks and benchmarks as evaluation settings, not the main spine.
9. Evaluation, ablations, metrics, confounders, and source limitations.
10. Open problems and research agenda.

## Thesis-Driven Structure

A full survey needs a spine stronger than "papers about X".

Before drafting, write:
- one-sentence central thesis;
- 3-5 take-home findings;
- one conceptual framework or model introduced by the review;
- one benchmark landscape table that names tasks, datasets, metrics, and limits;
- one method taxonomy table that compares families along dimensions that matter;
- one method design pipeline or decision table that helps readers build a system;
- one research agenda tied to gaps in evidence.

For CSUR-grade drafts, also write:
- research questions before taxonomy;
- related-survey positioning before claiming novelty;
- paper cards before taxonomy lock and synthesis;
- system-node cards before method sections;
- section cards before drafting `outputs/review.md`;
- `outputs/conceptual_framework.md` before final synthesis;
- paper-level facts for all A/B papers before synthesis tables;
- threats to validity before final completion.

The outline should make the thesis feel inevitable. If the outline could be permuted without changing the argument, it is probably a catalog rather than a survey.

Use tasks and benchmarks as evaluation evidence. Do not let them become the outline unless the user asks for a task or benchmark survey.

Default short review structure:

1. Scope and search method.
2. Taxonomy.
3. Main families.
4. Evidence and disagreements.
5. Open problems.
6. Annotated bibliography.

## Paragraph Logic

Use these patterns:
- Claim -> Evidence -> Implication for core analysis.
- Compare -> Contrast -> Trade-off for method comparisons.
- Concession -> Limitation for critical assessment.
- Broad -> Narrow -> This review for introduction.
- Tension -> Competing designs -> What would resolve it.
- Framework element -> Examples -> Failure mode -> Design lesson.
- Evidence gap -> Why current benchmarks miss it -> Proposed evaluation.

## Related Survey Differentiation

Every full survey needs a comparison against existing surveys. "More recent" is not enough.

Acceptable differentiation:
- new taxonomy;
- new angle;
- new evidence table or meta-analysis;
- broader benchmark comparison;
- deeper treatment of a neglected failure mode.
- explicit evaluation protocol or design guideline not present in prior surveys.

For each related survey, record:
- what it organizes around;
- what it misses or treats as secondary;
- what conceptual object this review elevates;
- which table/framework/agenda is new.
