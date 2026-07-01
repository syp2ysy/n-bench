# AutoResearch Landscape

Use this reference when choosing or revising the survey workflow. External AutoResearch projects are design evidence, not authority. Separate paper claims, code-inspected facts, and reusable ideas.

## Adoption Rule

Only absorb a pattern if it improves one of these properties:
- broader discovery;
- stronger citation grounding;
- better taxonomy or outline formation;
- clearer critical synthesis;
- more reliable long-running execution;
- more honest reporting of automation limits.

Do not copy a project's self-reported quality score, task framing, or "autonomous" label into this skill's completion standard.

## Evidence Matrix

| Work or codebase | What it is | Reuse | Do not copy |
| --- | --- | --- | --- |
| Deli AutoResearch framework | Protocol page for long-horizon autonomous tasks; no executable code. | State files, fresh sessions, heartbeat, stall detection, worker/guardian separation. | Treating protocol language as proof that a run is actually autonomous or multi-agent. |
| Deli paper-writing skill | Hierarchical paper-writing workflow with literature, structure, evidence/experiment, figures/tables, and review phases. | Phase routing and quality-gate idea. | Experiment phases for survey-only tasks unless the user asks for a research paper. |
| AutoSurvey | Runnable survey-generation code with `main.py`, outline/writer/judge agents, and a large arXiv database dependency. | Retrieval -> outline -> section drafting -> judge loop. | Assuming generated citations and survey quality are publication-ready without independent verification. |
| AutoSurvey2 / auto_research | Research-paper generation and artifact-sync repository. | Separation of writing and artifact management. | Treating general paper generation as survey-specific evidence synthesis. |
| SurveyX | Academic survey generation code with tasks, eval data, embeddings, LLM configuration, and LaTeX dependencies. | Task fixtures, evaluation mindset, manuscript assembly hints. | Hard-coding its topic format, provider assumptions, or LaTeX dependency into this skill. |
| InteractiveSurvey | Personalized interactive survey generation with retriever, outline, generator, Docker/demo assets. | User-in-the-loop outline repair and personalization ideas. | Using interactive assumptions for unattended runs. |
| STORM / Co-STORM | Knowledge curation system with persona generation, grounded questions, retrieval, outline, and article generation. | Multi-perspective question asking before taxonomy lock; outline blind-spot discovery. | Treating Wikipedia-style article generation as CSUR-grade survey synthesis. |
| PaperQA2 | Scientific RAG with document ingestion, search, metadata clients, and citation-backed answers. | Citation grounding, source retrieval, re-ranking, metadata checks. | Using QA answers as final survey prose without synthesis and taxonomy repair. |
| OpenScholar | Literature-synthesis system built around scientific corpora and retrieval-augmented answers. | Retrieval and scholarly grounding principles. | Depending on paper-only claims when code or corpus access is unavailable. |
| SurveyGen | Automated survey-generation work that reports citation-quality and critical-analysis limitations. | Use as a warning case: add citation and criticality gates. | Assuming fully automatic survey writing is mature enough to skip human-quality gates. |
| Agentic AutoSurvey | Survey-generation work framed around agentic decomposition. | Consider role decomposition when real subagents are available. | Calling a run multi-agent without saved agent outputs and merge decisions. |
| Agent Laboratory | End-to-end research workflow with literature review, experimentation, and report writing. | Staged workflow and human feedback checkpoints. | Importing experiment/code phases into ordinary survey tasks. |
| The AI Scientist | Autonomous scientific discovery system with idea, code, experiment, visualization, paper, and review components. | Reviewer-loop and artifact discipline ideas. | Treating experiment automation as evidence that survey synthesis is solved. |

## Workflow Implications

- Discovery should combine keyword search, venue sweep, citation snowball, and related-survey bibliography expansion.
- Outline formation should include a multi-perspective question pass before the taxonomy is locked.
- Drafting should follow evidence-backed claims, not generated section prose.
- Review should include criticality checks: disagreement, negative evidence, benchmark limitations, and method failure modes.
- Multi-agent language is allowed only when the run records actual agent outputs in `state/agent_rounds.jsonl` and merge decisions in `state/merge_decisions.jsonl`.

## Source Handles

- Deli AutoResearch framework: https://victorchen96.github.io/auto_research/framework.html
- Deli paper-writing skill: https://victorchen96.github.io/auto_research/skill/paper-writing.html
- AutoSurvey: https://github.com/AutoSurveys/AutoSurvey
- AutoSurvey paper: https://arxiv.org/abs/2406.10252
- AutoSurvey2 / auto_research: https://github.com/annihi1ation/auto_research
- SurveyX: https://github.com/IAAR-Shanghai/SurveyX
- InteractiveSurvey: https://github.com/TechnicolorGUO/InteractiveSurvey
- STORM: https://github.com/stanford-oval/storm
- PaperQA2: https://github.com/Future-House/paper-qa
- OpenScholar: https://arxiv.org/abs/2411.14199
- SurveyGen: https://arxiv.org/abs/2508.17647
- Agentic AutoSurvey: https://arxiv.org/abs/2509.18661
- Agent Laboratory: https://github.com/SamuelSchmidgall/AgentLaboratory
- The AI Scientist: https://github.com/SakanaAI/AI-Scientist
