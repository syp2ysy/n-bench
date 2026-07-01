# CSUR Exemplar Patterns

Use this reference before drafting `outputs/review.md` for `target=csur`.

The exemplar set is restricted to recent official ACM Computing Surveys records. Do not use arXiv-only, submitted, under-review, or unverified accepted claims as default style exemplars. Use 2025-2026 ACM DL records by default; use 2024 only as an explicitly labeled fallback.

The maintained DOI pool lives in `references/csur_official_exemplars.yml`. Add a new record there only when an official ACM DL DOI page verifies the paper as an ACM Computing Surveys publication. Custom verified exemplars must include DOI, ACM DL URL, verification date, and reason for use.

## Official Exemplar Pool

| Pattern | Official CSUR exemplars | Use for |
| --- | --- | --- |
| Lifecycle-style survey | Data-centric Artificial Intelligence: A Survey, ACM CSUR 2025, DOI `10.1145/3711118` | Topics organized by lifecycle stages, maintenance, benchmarks, and future direction. |
| Fast-moving AI topic survey | A Survey of AI-Generated Content, ACM CSUR 2025, DOI `10.1145/3704262` | New areas with rapidly expanding methods, applications, risks, and governance concerns. |
| Critique-heavy survey | A.I. Robustness: a Human-Centered Perspective on Technological Challenges and Opportunities, ACM CSUR 2025, DOI `10.1145/3665926` | Topics where limitations, human impact, and evaluation gaps are central. |
| Broad-method taxonomy survey | A Survey of Multimodal Learning: Methods, Applications, and Future Directions, ACM CSUR 2025, DOI `10.1145/3713070` | Broad method families with applications and forward-looking research directions. |
| Threat/risk survey | AI Agents Under Threat: A Survey of Key Security Challenges and Future Pathways, ACM CSUR 2025, DOI `10.1145/3716628` | Agent, security, safety, misuse, or risk-centered topics. |
| LLM-era taxonomy survey | A Survey on Uncertainty Quantification of Large Language Models, ACM CSUR 2026, DOI `10.1145/3744238` | LLM-era taxonomies with open challenges and future directions. |
| System-lens survey | Machine Learning Systems: A Survey from a Data-Oriented Perspective, ACM CSUR 2026, DOI `10.1145/3769292` | Topics needing a clear lens that reorganizes a system field. |
| Systematic corpus survey | A Systematic Survey on Large Language Models for Algorithm Design, ACM CSUR 2026, DOI `10.1145/3787585` | Reviews that need search protocol, corpus scope, taxonomy, and benchmark/open-issue structure. |
| Agent-optimization survey | A Survey on the Optimization of Large Language Model-based Agents, ACM CSUR 2026, DOI `10.1145/3789261` | Agent method surveys organized by objectives, optimization levers, and evaluation gaps. |
| Framework-pattern survey | Prompting Frameworks for Large Language Models: A Survey, ACM CSUR 2026, DOI `10.1145/3789253` | Topics where reusable design patterns must be converted into taxonomy dimensions. |

## Required `state/csur_imitation_plan.md`

Before synthesis, write a short plan with these headings:

1. `Selected CSUR Exemplars`: choose two or three official exemplars from the pool with ACM DL DOI, year, and why each fits.
2. `Section Skeleton`: list the article section sequence.
3. `Abstract Move Sequence`: state the moves the abstract will perform.
4. `Reader Function By Major Section`: explain what each section teaches the reader.
5. `Internal Notes Excluded From Review Body`: name scaffold notes, logs, and state-file details that cannot enter `outputs/review.md`.

Then write `state/csur_style_patterns.yml` using `references/csur_rhetoric_mining.md`. A CSUR plan that only lists DOI records, section titles, or a skeleton is not enough; it must also mine abstract moves, introduction moves, section opening/body/closing habits, table functions, paragraph patterns, and forbidden surface forms.

## Pattern Prompts

### Lifecycle-Style Survey

- **When to use**: the topic has stages such as data creation, training, deployment, maintenance, or governance.
- **Section skeleton**: Introduction -> Background/definitions -> Lifecycle stages -> Benchmarks/resources -> Discussion/future directions -> Conclusion.
- **Abstract moves**: field shift -> lifecycle gap -> stage taxonomy -> benchmark/resource synthesis -> agenda.
- **Section habits**: open each stage with the problem it solves; compare designs within the stage; close with failure modes and evidence gaps.
- **Avoid**: chronology, paper lists, or saying that stage names merely "expose" problems.

### Broad-Method Taxonomy Survey

- **When to use**: the field is defined by method families across multiple tasks or applications.
- **Section skeleton**: Introduction -> Background -> Method taxonomy -> Applications/benchmarks -> Evaluation -> Future directions.
- **Abstract moves**: broad adoption -> fragmented methods -> organizing taxonomy -> application/evaluation synthesis -> open challenges.
- **Section habits**: define the classification dimension before naming papers; tables should compare mechanisms, inputs, outputs, assumptions, strengths, and limitations.
- **Avoid**: task chapters that do not explain the underlying method distinction.

### System-Lens Survey

- **When to use**: the review contributes a lens that reorganizes existing work around a system object, interface, or lifecycle.
- **Section skeleton**: Introduction -> Related work -> Lens/framework -> Survey methodology -> Evidence organized by lens -> Threats/open challenges -> Conclusion.
- **Abstract moves**: field importance -> why existing views are incomplete -> proposed lens -> evidence base -> what the lens clarifies.
- **Section habits**: make the lens useful before making it comprehensive; each section should show what the lens reveals for design or evaluation.
- **Avoid**: "all methods can be put back into our framework" wording; show utility through comparisons instead.

### Systematic Corpus Survey

- **When to use**: the user asks for CSUR-grade, publication-grade, systematic, or auditable coverage.
- **Section skeleton**: Introduction -> Survey methodology -> Related surveys -> Foundations -> Taxonomy -> Benchmarks/resources -> Evaluation -> Open issues.
- **Abstract moves**: scope problem -> search corpus -> taxonomy/evidence artifacts -> key gaps -> research directions.
- **Section habits**: report search routes and limits concisely; connect paper facts to synthesis tables; distinguish demonstrated evidence from speculation.
- **Avoid**: process logs, internal filenames, or screening details that belong in `outputs/final_report.md`.

### Threat/Risk Survey

- **When to use**: safety, security, privacy, misuse, trust, or governance is central.
- **Section skeleton**: Introduction -> Threat model/definitions -> Taxonomy -> Evidence by threat family -> Defenses/evaluation -> Future pathways.
- **Abstract moves**: risk growth -> scattered evidence -> threat taxonomy -> defense/evaluation review -> unresolved pathways.
- **Section habits**: use threat categories as analytical objects; pair each category with assets, attacker or failure assumptions, evidence, and mitigations.
- **Avoid**: generic alarm language without operational definitions or evaluation criteria.

### LLM/Agent Fast-Moving Topic Survey

- **When to use**: the topic changes quickly and includes preprints, tools, benchmarks, and agentic workflows.
- **Section skeleton**: Introduction -> Foundations -> Taxonomy by capability/objective -> Benchmarks/evaluation -> Optimization or design patterns -> Open challenges.
- **Abstract moves**: rapid growth -> fragmented terminology -> taxonomy -> benchmark/evaluation gaps -> future directions.
- **Section habits**: separate accepted evidence from preprint signals; state where benchmarks confound the claimed capability; make open challenges testable.
- **Avoid**: treating recency, breadth, or model popularity as the contribution.

## Surface-Prose Rule

Internal scaffold sentences are allowed in `state/` files, but not in `outputs/review.md`. Rewrite compressed notes into publication-facing prose:

- Bad surface form: "Task A exposes pressure X; task B exposes pressure Y; good methods can be mapped back to the framework."
- Good surface form: "Across task families, benchmarks evaluate different validity conditions. Spatial tasks test whether stored state remains useful for planning, while question-answering tasks test whether responses can be traced to grounded evidence. These differences motivate a framework that connects representation choices to evaluation claims."
