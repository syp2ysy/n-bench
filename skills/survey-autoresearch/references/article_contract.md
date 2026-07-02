# Article Contract

`outputs/review.md` is the publication-facing article.

`outputs/article_plan.md` must separate:

- article body sections
- article displays
- appendix sections
- internal-only planning

Only article-body sections and article displays can drive `review.md`.

For full or CSUR surveys, design the reader-facing figures and tables before drafting prose. At minimum, the article plan must include:

- taxonomy roadmap figure;
- method evolution or timeline figure;
- data ecosystem figure or table;
- evaluation protocol matrix.

The article spine should be driven by a reader-facing field map and community-native taxonomy, not only by evidence-plan bookkeeping. Evidence plans constrain claims, but they do not replace a mature survey outline.

Before writing each article-body section, consult `state/section_evidence_plans.jsonl`. A section should not introduce a new strong claim until the claim is represented in `state/claim_evidence_spans.jsonl` and covered by that section's evidence plan.

Article body must:

- state a central thesis and keep returning to it;
- define concepts before using them;
- align its main taxonomy with field-native terminology unless it explicitly argues for a better alternative;
- explain representative papers as mechanisms and evidence;
- compare scenario-specific definitions where the topic object changes by setting;
- interpret every table or figure in prose;
- compare method families rather than list papers;
- make method sections explain trade-offs, alternatives, conflicts, and scope conditions;
- make benchmark/evaluation sections provide an evaluation recipe: protocol, metric, baseline, ablation/control, and confounder;
- calibrate evidence strength in scholarly language;
- close each major section with design, evaluation, or research implications.

Article body must not include:

- survey-type routing labels;
- A/B/C labels, source routes, candidate counts, or run metadata;
- state-file names, gate names, extraction fields, or repair notes;
- raw appendix tables;
- scaffold phrases such as "本节面向", "下面的表", "该工作在本文中被读作", "好的综述", or "本文采用 system-object survey 的结构".

Search protocol, broad coverage tables, and evidence logistics belong in `outputs/appendix.md` or `outputs/final_report.md`.
