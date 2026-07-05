# Article Contract

`outputs/survey_candidate.md` is the publication-facing candidate article reviewed by Gate 7. `outputs/survey_candidate.html` is its rendered candidate page.

Final `outputs/survey.md` and `outputs/survey.html` are release-only artifacts. They must not exist before Gate 7 passes and `promote_survey_release.py` promotes the candidate. Dashboard/status pages may show gates and run metadata; candidate and final article pages must not.

An assistant may describe a run as complete only when `outputs/release_manifest.json` has `released: true`. If the manifest is absent or `released` is false, any article page is a candidate or draft.

Render `outputs/survey_candidate.html` with `scripts/render_survey_html.py` and `assets/survey_template.html`. The page must display the full Markdown article, a reader-facing table of contents, and a References section with cited paper titles and verified links from `state/papers.jsonl` or `outputs/references.bib`. If no verified link exists for a paper, mark it source-limited rather than inventing a URL.

`outputs/article_plan.md` must separate:

- article body sections
- article displays
- appendix sections
- internal-only planning

Only article-body sections and article displays can drive `survey_candidate.md`.

For full or CSUR surveys, design the reader-facing figures and tables before drafting prose. At minimum, the article plan must include:

- taxonomy roadmap figure;
- method evolution or timeline figure;
- data ecosystem figure or table;
- evaluation protocol matrix.

The article spine should be driven by a reader-facing field map and community-native taxonomy, not only by evidence-plan bookkeeping. Evidence plans constrain claims, but they do not replace a mature survey outline.

Before writing each article-body section, consult `state/section_evidence_plans.jsonl`. A section should not introduce a new strong claim until the claim is represented in `state/claim_evidence_spans.jsonl` and covered by that section's evidence plan.

Do not expand for length alone. If the article is too short for full/CSUR targets, run an expansion clarity audit and add only evidence-backed clarification that preserves the argument graph. Enough length must come from distinct evidence and synthesis, not repeated prose. A paragraph that can be removed without changing the argument should be removed.

Large growth from `outputs/survey_body_draft.md` to `outputs/survey_candidate.md` also needs expansion provenance. Record what section was unclear, which evidence was rechecked, what text may be added, and what argument spine must not change. Passing the final length threshold does not excuse padding.

Article body must:

- state a central thesis and keep returning to it;
- teach the field to newcomers while giving experts a defensible taxonomy or framework;
- define concepts before using them;
- align its main taxonomy with field-native terminology unless it explicitly argues for a better alternative;
- explain how its scope and taxonomy relate to verified existing surveys, including existing coverage, coverage gaps, taxonomy delta, and why the article taxonomy is needed;
- cite and compare at least four verified related surveys in the related-survey positioning discussion for full targets, and at least six for CSUR targets;
- explain representative papers as mechanisms and evidence;
- compare scenario-specific definitions where the topic object changes by setting;
- interpret every table or figure in prose;
- compare method families rather than list papers;
- make method sections explain trade-offs, alternatives, conflicts, and scope conditions;
- make benchmark/evaluation sections provide an evaluation recipe: protocol, metric, baseline, ablation/control, and confounder;
- calibrate evidence strength in scholarly language;
- close each major section with design, evaluation, or research implications.
- place the conclusion as the final article-body section; only references, appendix, acknowledgements, or back matter may follow it.
- derive open problems from evidence gaps rather than introducing unrelated advice.

Article body must not include:

- survey-type routing labels;
- A/B/C labels, source routes, candidate counts, or run metadata;
- state-file names, gate names, extraction fields, or repair notes;
- naked internal paper IDs such as `P001` or template phrases such as "相关证据见 P001";
- raw appendix tables;
- scaffold phrases such as "本节面向", "下面的表", "该工作在本文中被读作", "好的综述", or "本文采用 system-object survey 的结构".
- process-correction phrasing such as "本综述不再把...", "那种视角不是文章 spine", or runtime labels such as "新版 skill", `source_ref`, `science paradigm profile`, or A/B audit counts.
- repeated prescriptive padding such as multiple near-identical "future work should" paragraphs without new paper comparison, benchmark evidence, limitation, or implication.
- publication-facing artifacts whose filename stem is `review`; expert-review summaries belong in `outputs/final_report.md` and structured state files, not in a parallel article file.
- final `survey.md` or `survey.html` before release promotion; Gate 7 blocked runs may expose only `survey_candidate.md/html`.

Search protocol, broad coverage tables, and evidence logistics belong in `outputs/appendix.md` or `outputs/final_report.md`.
