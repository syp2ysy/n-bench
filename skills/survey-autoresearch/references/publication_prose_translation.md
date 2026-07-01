# Publication Prose Translation

Use this reference after section dossiers and synthesis artifacts exist, before writing `outputs/review.md`.

## Core Rule

`state/` and most `outputs/*.md` files are research materials. `outputs/review.md` is an article. Do not paste structured artifacts into the article body. Translate them into publication-facing prose.

## Required Pass

Create `outputs/review_body_draft.md` before final `outputs/review.md`.

The draft must be written from:
- `outputs/section_dossiers/`;
- selected prose case studies from `outputs/worked_examples.md`;
- interpreted summaries of `outputs/benchmark_landscape.md`, `outputs/method_taxonomy.md`, and `outputs/node_paper_matrix.md`;
- `outputs/glossary.md` and `outputs/running_example.md`;
- CSUR paragraph patterns when `target=csur`.

Move exhaustive tables, raw structured examples, and long paper-card material to `outputs/appendix.md` or supporting artifacts.

## Case Studies In Review

`outputs/worked_examples.md` may use field labels such as `Problem`, `Memory record`, `Write policy`, and `Design lesson`.

`outputs/review.md` must not use those labels as repeated bullet blocks. A review-body case study should be 2-4 coherent paragraphs:

1. paper-specific problem and mechanism;
2. how the memory or system object is written, read, updated, or connected to action;
3. benchmark, ablation, or evidence status;
4. limitation and design lesson tied to the section thesis.

Do not make every A paper a case-study box in the article. Use a small set of representative boxes; put the exhaustive set in `worked_examples.md` or `appendix.md`.

## Tables In Review

Every table in `review.md` must have:
- an introduction explaining why the table exists;
- an interpretation paragraph explaining the main comparison, trade-off, or design implication.

Do not write "the following table summarizes..." and then move on. The prose after the table must tell the reader what to learn from it.

## Section Rhythm

Each major section should follow:

1. opening thesis or tension;
2. definitions needed by a newcomer;
3. comparison across method or benchmark families;
4. 1-2 selective prose case studies;
5. benchmark or evidence tie-in;
6. closing implication for design, evaluation, or open problems.

Avoid long runs of consecutive worked examples. After one or two examples, synthesize what they show.

## Forbidden In `review.md`

Keep these in state files or appendices, not in the article body:

- `Problem:`, `Memory record:`, `Write policy:`, `Read policy:`, `Update policy:`, `Controller interface:`, `Benchmark / task:`, `Ablation evidence:`, `Failure mode:`, `Design lesson:` as repeated bullets;
- "该工作在本文中被读作";
- "本文要求把该工作放入";
- "若原文没有完整报告，则将其作为证据缺口";
- "The paper teaches that ... must be specified through record schema";
- state filenames, draft version labels, workflow repair notes, or gate language.

Publication prose can still say a study lacks a no-memory or wrong-memory control. Say it as an evidence limitation, not as an internal instruction.
