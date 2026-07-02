import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_coverage_matrix import build_coverage
from scripts.gate_check import evaluate_gates
from scripts.init_task import initialize_task
from scripts.render_dashboard import render_dashboard
from scripts.score_lqs import classify_depth, score_paper
from scripts.validate_article_quality import validate_article_quality
from scripts.validate_argument_graph import validate_argument_graph
from scripts.validate_claim_evidence import validate_claim_evidence
from scripts.validate_paper_understanding import validate_paper_understanding
from scripts.validate_scenario_definitions import validate_scenario_definitions
from scripts.validate_section_evidence_plans import validate_section_evidence_plans
from scripts.validate_exemplar_alignment import validate_exemplar_alignment
from scripts.validate_synthesis_dossiers import validate_synthesis_dossiers
from scripts.verify_sources import validate_sources
from scripts.expert_review_gate import validate_expert_reviews
from scripts.build_contribution_tree import validate_contribution_tree


ROOT = Path(__file__).resolve().parents[1]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


class SurveyAutoResearchRefactorTest(unittest.TestCase):
    def papers(self, total: int = 160, related_surveys: int = 6) -> list[dict]:
        rows = []
        for idx in range(1, total + 1):
            rows.append(
                {
                    "paper_id": f"p{idx:03d}",
                    "title": f"Verified Paper {idx}",
                    "authors": ["A. Author"],
                    "year": 2025,
                    "venue_status": "peer-reviewed" if idx % 3 else "arxiv",
                    "doi": f"10.0000/{idx}",
                    "verification_status": "verified",
                    "verified_sources": ["doi"],
                    "survey_role": "survey" if idx <= related_surveys else ("benchmark" if idx % 5 == 0 else "method"),
                    "family": "family-a" if idx % 2 else "family-b",
                }
            )
        return rows

    def citation_plan(self, a: int = 25, b: int = 70, c: int = 65) -> list[dict]:
        rows = []
        idx = 1
        for depth, count in [("A", a), ("B", b), ("C", c)]:
            for _ in range(count):
                rows.append({"paper_id": f"p{idx:03d}", "depth": depth})
                idx += 1
        return rows

    def mechanism_cards(self, count: int = 95) -> list[dict]:
        rows = []
        for idx in range(1, count + 1):
            rows.append(
                {
                    "paper_id": f"p{idx:03d}",
                    "title": f"Verified Paper {idx}",
                    "survey_role": "method",
                    "level": "A" if idx <= 25 else "B",
                    "reading_depth": "full_text_deep_read",
                    "full_text_accessed": True,
                    "source_type": "arxiv_pdf",
                    "sections_read": [
                        "Introduction and problem formulation",
                        "Method and system architecture",
                        "Experiments and evaluation setup",
                        "Results, discussion, and limitations",
                    ],
                    "evidence_span_locations": [
                        "Section 1, page 1",
                        "Section 3, pages 4-6",
                        "Section 4, Table 2",
                        "Section 5, page 9",
                    ],
                    "deep_read_notes": "Full text was read across introduction, method, experiment, result, and limitation sections.",
                    "motivation": "The paper addresses a concrete long-horizon research bottleneck.",
                    "problem_setting": "A partially observable embodied or agentic decision problem.",
                    "task_definition": {"input": "observation and goal", "output": "action or answer"},
                    "benchmark_or_dataset": ["Benchmark-X"],
                    "method_pipeline": ["encode observation", "write record", "retrieve evidence", "act or answer"],
                    "implementation_details": {
                        "model_backbone": "encoder",
                        "memory_module": "structured store",
                        "retriever_or_map": "retriever",
                        "planner_or_controller": "planner",
                        "training_or_inference_setup": "inference-time retrieval",
                    },
                    "experimental_setup": {
                        "metrics": ["success"],
                        "baselines": ["no memory"],
                        "ablations": ["no retrieval"],
                        "evaluation_protocol": "diagnostic benchmark with no-memory comparison",
                    },
                    "main_results": [
                        {
                            "result": "The method improves the diagnostic benchmark over the no-memory baseline.",
                            "evidence_span": "Section 4, Table 2.",
                            "claim_strength": "shows",
                        }
                    ],
                    "limitations_and_confounders": [
                        "perception and controller strength may confound aggregate success",
                        "the evidence does not isolate all deployment-time failures",
                    ],
                    "relation_to_prior_work": "extends prior context-only systems with explicit evidence use.",
                    "what_it_changes_in_the_survey_argument": "It supports the claim that memory must be evaluated through evidence and control interfaces.",
                    "must_not_overclaim": ["does not demonstrate general memory causality without negative controls"],
                    "evidence_spans": ["Section 4, Table 2 reports the comparison."],
                }
            )
        return rows

    def full_text_sources(self, count: int = 95) -> list[dict]:
        return [
            {
                "paper_id": f"p{idx:03d}",
                "source_ref": f"src-p{idx:03d}",
                "source_url": f"https://arxiv.org/pdf/0000.{idx:05d}",
                "source_kind": "arxiv_pdf",
                "access_status": "accessible",
                "extraction_status": "extracted",
                "captured_excerpts": [
                    {
                        "section_or_page": "Section 4, Table 2",
                        "excerpt": "The method is compared with a no-memory baseline and improves the diagnostic benchmark.",
                    }
                ],
            }
            for idx in range(1, count + 1)
        ]

    def claims(self) -> list[dict]:
        return [
            {
                "claim_id": "c1",
                "claim": "Structured memory can improve a diagnostic benchmark when retrieved evidence is connected to the controller.",
                "claim_type": "result",
                "paper_ids": ["p001"],
                "strength": "shows",
                "evidence_spans": [
                    {
                        "paper_id": "p001",
                        "source_ref": "src-p001",
                        "section_or_page": "Section 4, Table 2",
                        "excerpt": "The method is compared with a no-memory baseline and improves the diagnostic benchmark.",
                        "evidence_summary": "The paper compares the method with a no-memory baseline.",
                        "supports": "direct",
                        "strength": "shows",
                    }
                ],
            }
        ]

    def contribution_statements(self, count: int = 95) -> list[dict]:
        return [
            {
                "paper_id": f"p{idx:03d}",
                "statement": (
                    f"Verified Paper {idx} addresses evidence-conditioned decisions by using structured retrieval, "
                    "evaluates on Benchmark-X against a no-memory baseline, and shows diagnostic improvement while "
                    "remaining limited by perception and controller confounders."
                ),
                "problem": "evidence-conditioned decision making",
                "method": "structured retrieval memory",
                "benchmark": ["Benchmark-X"],
                "result": "shows improvement over a no-memory baseline",
                "limitation": "perception and controller confounders remain",
                "evidence_strength": "shows",
                "source_ref": f"src-p{idx:03d}",
            }
            for idx in range(1, count + 1)
        ]

    def contribution_tree(self) -> dict:
        return {
            "root_claim": "Memory research is organized by how evidence changes downstream decisions.",
            "candidate_article_spines": [
                "contribution-tree: retrieval memory vs structured map memory",
                "system-node diagnostic lens",
            ],
            "selected_article_spine": "contribution-tree: retrieval memory vs structured map memory",
            "branches": [
                {
                    "name": "retrieval memory",
                    "motivation": "make past evidence available to later decisions",
                    "representative_papers": ["p001", "p002"],
                    "core_tradeoff": "high semantic recall versus wrong-evidence and latency risk",
                    "evidence_standard": "requires no-memory, oracle-evidence, and wrong-evidence comparisons",
                    "failure_risks": ["wrong evidence", "stale evidence"],
                    "subbranches": ["local evidence retrieval", "external evidence store"],
                },
                {
                    "name": "structured map memory",
                    "motivation": "preserve spatial and object state for planning",
                    "representative_papers": ["p003", "p004"],
                    "core_tradeoff": "spatial persistence versus stale object state",
                    "evidence_standard": "requires map ablations and stale-state tests",
                    "failure_risks": ["spatial aliasing", "stale map"],
                    "subbranches": ["semantic map", "topological graph"],
                },
            ],
        }

    def expert_reviews(self, score: float = 8.8, weaknesses: list[dict] | None = None) -> list[dict]:
        personas = [
            ("domain_expert", "Domain Expert Reviewer"),
            ("survey_architect", "Survey Architect Reviewer"),
            ("evidence_factuality", "Evidence/Factuality Reviewer"),
            ("newcomer_tutorial", "Newcomer/Tutorial Reviewer"),
            ("style_publication", "Style/Publication Reviewer"),
        ]
        sections = [
            "Introduction",
            "Method Families",
            "Benchmark and Evaluation",
            "Evidence and Limitations",
            "Design Guidance",
            "Open Problems",
            "Conclusion",
        ]
        quotes = [
            "memory is useful only when prior evidence changes a later decision",
            "two methods can share a benchmark label while using different pipelines",
            "the prose explains motivation, mechanism, experimental support, and confounders",
            "the section closes by linking method design to evidence and evaluation choices",
            "The table shows that method labels are insufficient",
        ]
        base_dims = [
            "narrative_coherence",
            "paper_understanding_depth",
            "field_native_taxonomy_quality",
            "method_taxonomy_quality",
            "benchmark_and_evaluation_quality",
            "evidence_factuality_and_citation_accuracy",
            "synthesis_not_catalog",
            "publication_prose",
            "newcomer_value",
            "expert_value",
        ]
        reports = []
        for offset, (reviewer_id, persona) in enumerate(personas):
            dims = {name: max(0, min(10, score - offset * 0.01)) for name in base_dims}
            report = {
                "reviewer_id": reviewer_id,
                "persona": persona,
                "overall_score": score,
                "dimension_scores": dims,
                "blocking_weaknesses": weaknesses or [],
                "pass_recommendation": not weaknesses and score >= 8.5,
                "summary": f"{persona} read the complete article and found persona-specific strengths and repair risks.",
                "review_trace": {"reviewed_full_article": True, "article_chars_read": len(self.review_text())},
                "sections_reviewed": sections,
                "section_comments": {
                    section: f"{persona} comment on {section}: the section links claims, evidence, and limitations in a concrete way."
                    for section in sections
                },
                "quoted_evidence_from_review": quotes,
            }
            if persona == "Domain Expert Reviewer":
                report["paper_mechanism_audits"] = [
                    {"paper_id": f"p{idx:03d}", "verdict": "consistent", "finding": "The article's mechanism wording is consistent with the paper card and does not overclaim."}
                    for idx in range(1, 11)
                ]
            if persona == "Survey Architect Reviewer":
                report["flow_taxonomy_audit"] = {
                    "section_flow": "The article progresses from motivation to taxonomy, evidence, design guidance, and open problems.",
                    "taxonomy_coherence": "The method taxonomy compares mechanisms and interfaces rather than only grouping paper titles.",
                    "synthesis_vs_catalog": "The prose explains implications after tables and avoids becoming a paper-by-paper catalog.",
                }
            if persona == "Evidence/Factuality Reviewer":
                report["claim_citation_audits"] = [
                    {"claim_id": "c1", "paper_id": f"p{idx:03d}", "verdict": "supported", "finding": "The claim is tied to a full-text evidence span and does not exceed the recorded strength."}
                    for idx in range(1, 11)
                ]
            if persona == "Newcomer/Tutorial Reviewer":
                report["tutorial_audit"] = {
                    "glossary_clarity": "The glossary gives a concrete entry point into terms that would otherwise be ambiguous to new readers.",
                    "running_example_usefulness": "The running example connects memory, evidence, controller use, and benchmark interpretation.",
                    "confusing_terms": "The remaining confusing terms are identified and explained through section comments rather than ignored.",
                }
            if persona == "Style/Publication Reviewer":
                report["style_audit"] = {
                    "repetition": "Repeated claims are controlled by linking each repetition to a new implication or section role.",
                    "artifact_leakage": "The article avoids process artifacts and keeps workflow language outside the publication body.",
                    "table_interpretation": "Tables are introduced and interpreted with prose before and after the display.",
                    "transition_quality": "Transitions connect previous evidence to the next section's argument.",
                }
            reports.append(report)
        return reports

    def expert_invocations(self) -> list[dict]:
        return [
            {
                "reviewer_id": reviewer_id,
                "persona": persona,
                "fresh_context": True,
                "inputs": ["outputs/review.md", "outputs/appendix.md", "state/paper_mechanism_cards.jsonl"],
                "forbidden_inputs": ["previous reviewer reports", "state/expert_review_reports.jsonl"],
                "output": "state/expert_review_reports.jsonl",
                "timestamp": "2026-07-03T00:00:00Z",
            }
            for reviewer_id, persona in [
                ("domain_expert", "Domain Expert Reviewer"),
                ("survey_architect", "Survey Architect Reviewer"),
                ("evidence_factuality", "Evidence/Factuality Reviewer"),
                ("newcomer_tutorial", "Newcomer/Tutorial Reviewer"),
                ("style_publication", "Style/Publication Reviewer"),
            ]
        ]

    def repair_actions(self, weakness_id: str = "w1") -> list[dict]:
        return [
            {
                "weakness_id": weakness_id,
                "status": "resolved",
                "route_to": "synthesis_dossiers",
                "repair_action": "rebuild method-family comparison",
                "changed_artifacts": ["outputs/method_family_dossiers/retrieval_memory.json", "outputs/review.md"],
                "evidence": "The method family now compares alternatives, trade-offs, and evidence limits.",
            }
        ]

    def regression_checks(self, weakness_id: str = "w1") -> list[dict]:
        return [
            {
                "weakness_id": weakness_id,
                "status": "passed",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_scripts.py",
                "result": "OK",
            }
        ]

    def scenario_definitions(self) -> dict:
        scenarios = []
        for name in ["navigation", "EQA", "manipulation", "VLA", "lifelong"]:
            scenarios.append(
                {
                    "scenario": name,
                    "object_definition": f"{name} defines memory through task-specific state and evidence.",
                    "required_fields": ["state", "source", "time", "task"],
                    "typical_benchmarks": [f"{name}-Bench"],
                    "unsuitable_claims": [f"{name} success alone does not prove all memory mechanisms."],
                    "evaluation_pressure": "diagnostic pressure with confounders",
                    "failure_risks": ["stale evidence", "wrong retrieval"],
                }
            )
        return {"scenarios": scenarios}

    def method_dossier(self) -> dict:
        return {
            "family": "retrieval memory",
            "family_motivation": "Retrieve grounded evidence for downstream decisions.",
            "assumptions": ["history can be indexed", "retrieval affects a controller"],
            "representative_a_papers": ["p001", "p002"],
            "supporting_b_papers": ["p026", "p027"],
            "shared_mechanism_pattern": "write structured evidence, retrieve it by task-conditioned keys, then expose it to a controller",
            "differences_among_representative_papers": "p001 uses local evidence while p002 uses a broader external store.",
            "relation_graph": [
                {"source": "p001", "target": "p002", "relation": "alternative", "reason": "different retrieval granularity"}
            ],
            "common_benchmarks": ["EQA-Bench"],
            "evidence_strength_summary": "shows task-specific gains under no-memory comparison but still needs wrong-evidence controls",
            "failure_modes": ["wrong evidence", "latency"],
            "open_questions": ["how to separate retrieval quality from answer priors"],
            "advances_central_story": "connects scenario-specific evidence to an action-facing interface",
            "scenario_links": ["EQA"],
        }

    def benchmark_dossier(self) -> dict:
        return {
            "benchmark": "EQA-Bench",
            "capability_tested": "grounded evidence retrieval",
            "task_formulation": "answer questions from embodied observations",
            "input_output": "input observations and question; output answer and evidence",
            "environment_dataset": "simulated embodied scenes",
            "metrics": ["accuracy", "groundedness"],
            "common_baselines": ["closed-book", "oracle evidence"],
            "reported_memory_specific_ablations": ["no-memory"],
            "missing_diagnostic_controls": ["wrong evidence", "stale evidence"],
            "what_it_can_support": "whether retrieved evidence helps answer questions",
            "what_it_cannot_support": "it cannot alone prove object-state memory or policy-time use",
            "representative_papers_using_it": ["p001", "p002"],
            "confounders": ["language priors", "visual recognition"],
            "scenario_links": ["EQA"],
        }

    def section_evidence_plans(self) -> list[dict]:
        base = [
            {
                "section_id": "S1",
                "title": "Introduction",
                "argument_node": "A1",
                "section_claim": "Existing views fragment mechanisms.",
                "scenario_definitions_used": ["navigation", "EQA"],
                "method_families_used": [],
                "anchor_papers": ["p001"],
                "supporting_papers": ["p026"],
                "benchmarks": [],
                "required_comparisons": ["task-first view vs interface-centered view"],
                "must_include_evidence_spans": ["c1"],
                "must_not_overclaim": ["do not claim all settings are solved"],
            },
            {
                "section_id": "S2",
                "title": "Method Families",
                "argument_node": "A2",
                "section_claim": "Method families differ by mechanism and evidence.",
                "scenario_definitions_used": ["EQA", "lifelong"],
                "method_families_used": ["retrieval memory"],
                "anchor_papers": ["p001", "p002"],
                "supporting_papers": ["p026", "p027"],
                "benchmarks": ["EQA-Bench"],
                "required_comparisons": ["p001 vs p002", "local evidence vs external store"],
                "must_include_evidence_spans": ["c1"],
                "must_not_overclaim": ["do not state retrieval proves causality"],
            },
            {
                "section_id": "S3",
                "title": "Benchmark and Evaluation",
                "argument_node": "A3",
                "section_claim": "Benchmarks operationalize but do not automatically prove claims.",
                "scenario_definitions_used": ["EQA"],
                "method_families_used": ["retrieval memory"],
                "anchor_papers": ["p001"],
                "supporting_papers": ["p026"],
                "benchmarks": ["EQA-Bench"],
                "required_comparisons": ["closed-book vs oracle evidence"],
                "protocol": "compare no-memory, oracle evidence, and wrong evidence",
                "metric": "accuracy and groundedness",
                "baseline": "closed-book answerer",
                "confounder": "language priors",
                "must_include_evidence_spans": ["c1"],
                "must_not_overclaim": ["do not claim benchmark success proves causality"],
            },
        ]
        for idx, title in enumerate(["Evidence and Limitations", "Design Guidance", "Open Problems"], start=4):
            base.append(
                {
                    "section_id": f"S{idx}",
                    "title": title,
                    "argument_node": "A3",
                    "section_claim": f"{title} connects evidence limits to repair routes.",
                    "scenario_definitions_used": ["EQA"],
                    "method_families_used": ["retrieval memory"],
                    "anchor_papers": ["p001"],
                    "supporting_papers": ["p026"],
                    "benchmarks": ["EQA-Bench"],
                    "required_comparisons": ["evidence strength vs overclaim risk"],
                    "must_include_evidence_spans": ["c1"],
                    "must_not_overclaim": ["do not overstate causal memory claims"],
                }
            )
        return base

    def argument_graph(self) -> dict:
        return {
            "central_thesis": "Memory should be evaluated as an evidence-to-action interface.",
            "field_shift": "Agents move from short tasks to long-horizon deployment.",
            "gap_in_existing_surveys": "Task-first views split method, benchmark, and evidence reasoning.",
            "paradigm_evidence_norms": {
                "science_paradigm_profile": "robotics/embodied-ai",
                "required_evidence_units": ["benchmark", "baseline", "ablation", "sim_real_or_ood_boundary"],
                "common_confounders": ["perception", "controller capacity", "simulation bias"],
            },
            "community_taxonomy_nodes": ["retrieval memory", "structured map memory", "episodic policy memory"],
            "taxonomy_competition": {
                "community_native_taxonomy": "method-family taxonomy organizes retrieval, mapping, and episodic policy memory.",
                "alternative_taxonomy": "system-node taxonomy is retained as a diagnostic lens rather than the article spine.",
                "selected": "community-native method-family taxonomy",
            },
            "paper_relation_graph": [
                {"source": "p001", "target": "p002", "relation": "alternative retrieval granularity"},
                {"source": "p001", "target": "p026", "relation": "benchmark transfer pressure"},
            ],
            "contribution_tree": "outputs/contribution_tree.yml",
            "candidate_spines_from_contribution_tree": ["retrieval memory", "structured map memory"],
            "exemplar_delta": "The article follows related survey patterns of definition, taxonomy, data, evaluation, and open challenges while adding evidence-to-action diagnostics.",
            "figure_plan": {
                "taxonomy_roadmap": "Reader-facing map of method families and diagnostic interfaces.",
                "method_evolution_timeline": "Timeline of retrieval and controller interfaces.",
                "data_ecosystem": "Table linking observations, traces, annotations, and deployment logs.",
                "evaluation_protocol_matrix": "Matrix of protocol, metric, baseline, and confounder.",
            },
            "story_skeleton": [
                "field_shift",
                "fragmented_existing_view",
                "new_unifying_lens",
                "scenario-specific definitions",
                "method-family comparison",
                "benchmark/evidence limitations",
                "research agenda",
            ],
            "argument_nodes": {
                "A1": {
                    "claim": "Existing views fragment mechanisms.",
                    "evidence": ["related_survey_matrix"],
                    "scenario_links": ["navigation", "EQA"],
                    "method_family_links": [],
                    "benchmark_links": [],
                    "implication": "Use an interface-centered lens.",
                    "section": "Introduction",
                    "section_role": "definition",
                    "leads_to": ["A2"],
                },
                "A2": {
                    "claim": "Method families differ by mechanism and evidence.",
                    "evidence": ["method_family_dossiers"],
                    "scenario_links": ["EQA", "lifelong"],
                    "method_family_links": ["retrieval memory"],
                    "benchmark_links": ["EQA-Bench"],
                    "implication": "Compare methods by pipeline and result support.",
                    "section": "Method Families",
                    "section_role": "taxonomy",
                    "leads_to": ["A3"],
                },
                "A3": {
                    "claim": "Benchmarks operationalize but do not automatically prove claims.",
                    "evidence": ["benchmark_dossiers"],
                    "scenario_links": ["EQA"],
                    "method_family_links": ["retrieval memory"],
                    "benchmark_links": ["EQA-Bench"],
                    "benchmark_limit": "success does not prove causal memory contribution without diagnostic controls",
                    "implication": "Use diagnostic controls.",
                    "section": "Benchmark and Evaluation",
                    "section_role": "evaluation",
                    "leads_to": [],
                },
            },
            "section_order": ["Introduction", "Method Families", "Benchmark and Evaluation"],
            "takeaway_findings": ["Evidence strength controls article wording."],
        }

    def article_plan(self) -> str:
        return (
            "# Article Plan\n\n"
            "## Article Body Sections\n"
            "- Introduction\n- Method Families\n- Benchmark and Evaluation\n- Evidence and Limitations\n- Design Guidance\n- Open Problems\n\n"
            "## Article Displays\n"
            "- Taxonomy roadmap figure\n"
            "- Method evolution timeline figure\n"
            "- Data ecosystem figure or table\n"
            "- Evaluation protocol matrix\n"
            "- Method comparison table\n- Benchmark protocol table\n\n"
            "## Appendix Sections\n"
            "- Search protocol\n- Broad coverage matrix\n\n"
            "## Internal Only\n"
            "- Keep source routes, evidence labels, run counts, and repair notes out of review.md.\n"
        )

    def review_text(self, repeat: int = 180) -> str:
        section = (
            "This section starts from a clear thesis: memory is useful only when prior evidence changes a later decision. "
            "The comparison matters because two methods can share a benchmark label while using different pipelines, evaluation baselines, and limitations. "
            "Instead of listing papers, the prose explains motivation, mechanism, experimental support, and confounders. "
            "Therefore, the section closes by linking method design to evidence and evaluation choices.\n\n"
        )
        table = (
            "The comparison table is introduced as a publication-ready synthesis of mechanism and evidence.\n\n"
            "| Family | Mechanism | Evidence | Limitation |\n"
            "| --- | --- | --- | --- |\n"
            "| Retrieval | writes and reads structured evidence | no-memory comparison | perception confounder |\n\n"
            "The table shows that method labels are insufficient. A reader should compare what evidence is written, how it is retrieved, which baseline is used, and what limitation remains.\n\n"
            "A minimum evaluation recipe specifies protocol, metric, baseline, ablation, and confounder before the article interprets benchmark success.\n\n"
        )
        body = (section + table) * repeat
        return (
            "# Survey\n\n"
            "## Introduction\n" + body +
            "## Method Families\n" + body +
            "## Benchmark and Evaluation\n" + body +
            "## Evidence and Limitations\n" + body +
            "## Design Guidance\n" + body +
            "## Open Problems\n" + body +
            "## Conclusion\n" + section
        )

    def populate_full_task(self, task_dir: Path) -> None:
        state = task_dir / "state"
        outputs = task_dir / "outputs"
        write_jsonl(state / "papers.jsonl", self.papers())
        write_jsonl(state / "citation_plan.jsonl", self.citation_plan())
        write_jsonl(state / "paper_mechanism_cards.jsonl", self.mechanism_cards())
        write_jsonl(state / "full_text_sources.jsonl", self.full_text_sources())
        write_jsonl(state / "paper_contribution_statements.jsonl", self.contribution_statements())
        write_jsonl(state / "claim_evidence_spans.jsonl", self.claims())
        write_jsonl(state / "expert_review_reports.jsonl", self.expert_reviews())
        write_jsonl(state / "expert_review_invocations.jsonl", self.expert_invocations())
        write_jsonl(state / "weakness_routes.jsonl", [])
        write_jsonl(state / "repair_actions.jsonl", [])
        write_jsonl(state / "regression_checks.jsonl", [])
        (state / "review_iteration_status.json").write_text(
            json.dumps({"round": 1, "last_median_score": 8.8, "previous_median_score": None}),
            encoding="utf-8",
        )
        (state / "survey_type_plan.yml").write_text(
            "topic: embodied memory system\n"
            "primary_type: system-object\n"
            "secondary_lenses:\n"
            "  - method-family\n"
            "  - benchmark/evaluation\n"
            "why_this_type: The topic names a system object.\n"
            "why_not_other_types: A pure task survey would fragment evidence.\n"
            "article_skeleton:\n"
            "  - Introduction\n"
            "  - Method Families\n"
            "  - Benchmark and Evaluation\n"
            "exemplar_alignment: Field Survey Exemplar uses definition -> taxonomy -> data ecosystem -> evaluation -> open challenges.\n"
            "community_native_taxonomy:\n"
            "  - retrieval memory\n"
            "  - structured map memory\n"
            "  - episodic policy memory\n"
            "exemplar_section_patterns:\n"
            "  - definition\n"
            "  - taxonomy\n"
            "  - data ecosystem\n"
            "  - evaluation protocol\n"
            "  - open challenges\n"
            "candidate_article_spines:\n"
            "  - community-native method-family taxonomy\n"
            "  - system-node diagnostic lens\n"
            "selected_article_spine: community-native method-family taxonomy\n"
            "why_not_exemplar_spine: The article adapts the exemplar pattern to an evidence-to-action interface topic.\n"
            "figure_first_plan: taxonomy roadmap; method evolution timeline; data ecosystem; evaluation protocol matrix.\n"
            "science_paradigm_profile: robotics/embodied-ai\n"
            "evidence_norms:\n"
            "  - benchmark/baseline/ablation evidence is required for method claims\n"
            "  - sim-real or OOD boundaries must be stated for deployment claims\n"
            "required_evidence_units:\n"
            "  - benchmark\n"
            "  - baseline\n"
            "  - ablation\n"
            "  - sim_real_or_ood_boundary\n"
            "common_confounders:\n"
            "  - perception\n"
            "  - controller capacity\n"
            "  - simulation bias\n"
            "excluded_templates:\n"
            "  - pure chronological survey\n",
            encoding="utf-8",
        )
        (state / "argument_graph.yml").write_text(json.dumps(self.argument_graph()), encoding="utf-8")
        (state / "scenario_definitions.yml").write_text(json.dumps(self.scenario_definitions()), encoding="utf-8")
        write_jsonl(state / "section_evidence_plans.jsonl", self.section_evidence_plans())
        (outputs / "article_plan.md").write_text(self.article_plan(), encoding="utf-8")
        (outputs / "review.md").write_text(self.review_text(), encoding="utf-8")
        (outputs / "appendix.md").write_text("# Appendix\n\nSearch protocol and coverage logistics.\n", encoding="utf-8")
        (outputs / "coverage_matrix.md").write_text("# Coverage Matrix\n\nVerified coverage summary.\n", encoding="utf-8")
        (outputs / "contribution_tree.yml").write_text(json.dumps(self.contribution_tree()), encoding="utf-8")
        (outputs / "related_survey_matrix.md").write_text("# Related Survey Matrix\n\nSurvey positioning.\n", encoding="utf-8")
        (outputs / "references.bib").write_text("@article{x,title={x}}\n", encoding="utf-8")
        (outputs / "final_report.md").write_text("Complete\n", encoding="utf-8")
        for dirname in ["method_family_dossiers", "benchmark_dossiers"]:
            directory = outputs / dirname
            directory.mkdir(exist_ok=True)
        (outputs / "method_family_dossiers" / "retrieval_memory.json").write_text(
            json.dumps(self.method_dossier(), sort_keys=True),
            encoding="utf-8",
        )
        (outputs / "benchmark_dossiers" / "eqa_bench.json").write_text(
            json.dumps(self.benchmark_dossier(), sort_keys=True),
            encoding="utf-8",
        )

    def test_source_identity_gate_blocks_unverified_a_b(self):
        papers = self.papers(3, 0)
        papers[1]["verification_status"] = "unverified"
        status = validate_sources(papers, [{"paper_id": "p001", "depth": "A"}, {"paper_id": "p002", "depth": "B"}], "full")
        self.assertFalse(status["valid"])
        self.assertIn("p002", status["unverified_a_b"])

    def test_paper_understanding_requires_scientific_contribution_chain(self):
        shallow = [{"paper_id": "p001", "title": "Paper", "survey_role": "method", "level": "A"}]
        status = validate_paper_understanding(shallow, [{"paper_id": "p001", "depth": "A"}], self.full_text_sources(1))
        self.assertFalse(status["valid"])
        self.assertIn("invalid_paper_understanding", status["errors"])
        status = validate_paper_understanding(self.mechanism_cards(1), [{"paper_id": "p001", "depth": "A"}], self.full_text_sources(1))
        self.assertTrue(status["valid"], status)

    def test_paper_understanding_rejects_generic_relation_and_missing_experiment_details(self):
        card = self.mechanism_cards(1)[0]
        card["relation_to_prior_work"] = "This is related to prior work."
        card["experimental_setup"] = {"metrics": ["success"]}
        status = validate_paper_understanding([card], [{"paper_id": "p001", "depth": "A"}], self.full_text_sources(1))
        self.assertFalse(status["valid"])
        self.assertIn("generic_relation_to_prior_work", status["invalid_cards"]["p001"])
        self.assertIn("missing_baselines", status["invalid_cards"]["p001"])
        self.assertIn("missing_ablations", status["invalid_cards"]["p001"])

    def test_paper_understanding_rejects_metadata_only_a_b_cards(self):
        card = self.mechanism_cards(1)[0]
        card["reading_depth"] = "abstract_metadata_only"
        card["full_text_accessed"] = False
        card["source_type"] = "Semantic Scholar metadata"
        card["sections_read"] = ["title and abstract"]
        card["evidence_span_locations"] = ["curated-list row"]
        card["main_results"][0]["evidence_span"] = "Semantic Scholar metadata says the paper improves a benchmark."
        status = validate_paper_understanding([card], [{"paper_id": "p001", "depth": "A"}], self.full_text_sources(1))
        self.assertFalse(status["valid"])
        self.assertIn("a_b_not_full_text_deep_read", status["invalid_cards"]["p001"])
        self.assertIn("full_text_not_accessed", status["invalid_cards"]["p001"])
        self.assertIn("metadata_only_evidence_location", status["invalid_cards"]["p001"])
        self.assertEqual(status["metadata_only_a_b_count"], 1)

    def test_metadata_only_c_is_not_required_by_paper_understanding(self):
        card = {
            "paper_id": "p150",
            "title": "Metadata-only Background Paper",
            "level": "C",
            "reading_depth": "abstract_metadata_only",
            "evidence_limited": True,
        }
        status = validate_paper_understanding([card], [{"paper_id": "p001", "depth": "A"}], self.full_text_sources(1))
        self.assertFalse(status["valid"])
        self.assertIn("p001", status["invalid_cards"])
        status = validate_paper_understanding([card], [{"paper_id": "p150", "depth": "C"}], [])
        self.assertTrue(status["valid"], status)

    def test_paper_understanding_requires_full_text_source_audit_for_a_b(self):
        status = validate_paper_understanding(self.mechanism_cards(1), [{"paper_id": "p001", "depth": "A"}], [])
        self.assertFalse(status["valid"])
        self.assertIn("missing_full_text_source_audit", status["invalid_cards"]["p001"])
        source = self.full_text_sources(1)[0]
        source["captured_excerpts"] = []
        source["extraction_status"] = "metadata_only"
        status = validate_paper_understanding(self.mechanism_cards(1), [{"paper_id": "p001", "depth": "A"}], [source])
        self.assertFalse(status["valid"])
        self.assertIn("invalid_full_text_source_audit", status["invalid_cards"]["p001"])

    def test_claim_evidence_blocks_missing_span_and_overclaim(self):
        too_strong = self.claims()
        too_strong[0]["strength"] = "demonstrates"
        status = validate_claim_evidence(too_strong, self.mechanism_cards(1), full_text_sources=self.full_text_sources(1))
        self.assertFalse(status["valid"])
        self.assertIn("claim_strength_exceeds_evidence:p001", status["invalid_claims"]["c1"])
        status = validate_claim_evidence(self.claims(), self.mechanism_cards(1), full_text_sources=self.full_text_sources(1))
        self.assertTrue(status["valid"], status)

    def test_claim_evidence_rejects_metadata_only_support_for_strong_claims(self):
        metadata_card = self.mechanism_cards(1)[0]
        metadata_card["reading_depth"] = "abstract_metadata_only"
        metadata_card["full_text_accessed"] = False
        claim = self.claims()[0]
        claim["evidence_spans"][0]["section_or_page"] = "Semantic Scholar metadata"
        claim["evidence_spans"][0]["evidence_summary"] = "Abstract metadata says the method improves the benchmark."
        status = validate_claim_evidence([claim], [metadata_card], full_text_sources=self.full_text_sources(1))
        self.assertFalse(status["valid"])
        self.assertIn("claim_requires_full_text_deep_read:p001", status["invalid_claims"]["c1"])
        self.assertIn("metadata_only_span_for_strong_claim:p001", status["invalid_claims"]["c1"])

    def test_claim_evidence_requires_excerpt_for_strong_claims(self):
        claim = self.claims()[0]
        claim["evidence_spans"][0].pop("excerpt")
        status = validate_claim_evidence([claim], self.mechanism_cards(1), full_text_sources=self.full_text_sources(1))
        self.assertFalse(status["valid"])
        self.assertIn("strong_claim_missing_excerpt:p001", status["invalid_claims"]["c1"])

    def test_coverage_gate_enforces_full_survey_breadth(self):
        status = build_coverage(self.papers(20, 1), self.citation_plan(a=2, b=4, c=14), "full")
        self.assertFalse(status["valid"])
        self.assertIn("verified_refs", status["missing"])
        status = build_coverage(self.papers(), self.citation_plan(), "full")
        self.assertTrue(status["valid"], status)

    def test_contribution_tree_requires_ab_statements_and_branch_tradeoffs(self):
        status = validate_contribution_tree([], {}, self.citation_plan(a=2, b=0, c=0), self.argument_graph(), target="full")
        self.assertFalse(status["valid"])
        self.assertIn("missing_contribution_statements", status["errors"])
        weak_tree = {
            "root_claim": "Memory research has papers.",
            "branches": [{"name": "retrieval memory", "representative_papers": ["p001"]}],
        }
        status = validate_contribution_tree(self.contribution_statements(2), weak_tree, self.citation_plan(a=2, b=0, c=0), self.argument_graph(), target="full")
        self.assertFalse(status["valid"])
        self.assertIn("invalid_contribution_tree", status["errors"])
        status = validate_contribution_tree(self.contribution_statements(4), self.contribution_tree(), self.citation_plan(a=4, b=0, c=0), self.argument_graph(), target="full")
        self.assertTrue(status["valid"], status)

    def test_contribution_tree_must_drive_argument_graph_spines(self):
        graph = self.argument_graph()
        graph.pop("contribution_tree")
        graph.pop("candidate_spines_from_contribution_tree")
        status = validate_contribution_tree(self.contribution_statements(4), self.contribution_tree(), self.citation_plan(a=4, b=0, c=0), graph, target="full")
        self.assertFalse(status["valid"])
        self.assertIn("argument_graph_missing_contribution_tree", status["errors"])

    def test_argument_graph_requires_section_mapping(self):
        graph = self.argument_graph()
        status = validate_argument_graph(graph, self.article_plan())
        self.assertTrue(status["valid"], status)
        graph["argument_nodes"]["A2"].pop("implication")
        status = validate_argument_graph(graph, self.article_plan())
        self.assertFalse(status["valid"])

    def test_exemplar_alignment_requires_field_native_outline(self):
        status = validate_exemplar_alignment({}, self.argument_graph(), self.article_plan(), target="full")
        self.assertFalse(status["valid"])
        self.assertIn("missing_exemplar_alignment_fields", status["errors"])
        survey_type_plan = {
            "primary_type": "method-family",
            "exemplar_alignment": ["Field Survey Exemplar"],
            "community_native_taxonomy": ["retrieval memory", "structured map memory"],
            "exemplar_section_patterns": ["definition", "taxonomy", "data ecosystem", "evaluation", "open challenges"],
            "candidate_article_spines": ["community-native method-family taxonomy", "system-node diagnostic lens"],
            "selected_article_spine": "community-native method-family taxonomy",
            "why_not_exemplar_spine": "The article adapts the exemplar pattern to this evidence-to-action topic.",
            "figure_first_plan": "taxonomy roadmap; method evolution timeline; data ecosystem; evaluation protocol matrix",
            "science_paradigm_profile": "ML/AI systems",
            "evidence_norms": ["benchmark/baseline/ablation evidence controls method claims"],
            "required_evidence_units": ["benchmark", "baseline", "ablation"],
            "common_confounders": ["data leakage", "scale", "benchmark saturation"],
        }
        status = validate_exemplar_alignment(survey_type_plan, self.argument_graph(), self.article_plan(), target="full")
        self.assertTrue(status["valid"], status)

    def test_exemplar_alignment_requires_science_paradigm_profile(self):
        survey_type_plan = {
            "primary_type": "method-family",
            "exemplar_alignment": ["Field Survey Exemplar"],
            "community_native_taxonomy": ["retrieval memory", "structured map memory"],
            "exemplar_section_patterns": ["definition", "taxonomy", "data ecosystem", "evaluation", "open challenges"],
            "candidate_article_spines": ["community-native method-family taxonomy", "system-node diagnostic lens"],
            "selected_article_spine": "community-native method-family taxonomy",
            "why_not_exemplar_spine": "The article adapts the exemplar pattern to this topic.",
            "figure_first_plan": "taxonomy roadmap; method evolution timeline; data ecosystem; evaluation protocol matrix",
        }
        status = validate_exemplar_alignment(survey_type_plan, self.argument_graph(), self.article_plan(), target="full")
        self.assertFalse(status["valid"])
        self.assertIn("missing_science_paradigm_profile", status["errors"])

    def test_scenario_definitions_require_context_specific_definitions(self):
        status = validate_scenario_definitions({}, target="full")
        self.assertFalse(status["valid"])
        status = validate_scenario_definitions(self.scenario_definitions(), target="full")
        self.assertTrue(status["valid"], status)
        weak = {"scenarios": [{"scenario": "navigation", "object_definition": "spatial memory"}]}
        status = validate_scenario_definitions(weak, target="full")
        self.assertFalse(status["valid"])

    def test_synthesis_dossiers_require_cross_paper_comparison_and_benchmark_limits(self):
        weak_method = {"family": "retrieval", "representative_a_papers": ["p001"], "supporting_b_papers": []}
        weak_bench = {"benchmark": "EQA", "capability_tested": "answering"}
        status = validate_synthesis_dossiers(
            [weak_method],
            [weak_bench],
            self.scenario_definitions(),
            self.mechanism_cards(2),
            target="full",
        )
        self.assertFalse(status["valid"])
        status = validate_synthesis_dossiers(
            [self.method_dossier()],
            [self.benchmark_dossier()],
            self.scenario_definitions(),
            self.mechanism_cards(30),
            target="full",
        )
        self.assertTrue(status["valid"], status)

    def test_section_evidence_plans_cover_article_sections_and_benchmark_requirements(self):
        status = validate_section_evidence_plans(
            [],
            self.argument_graph(),
            self.article_plan(),
            self.claims(),
            self.mechanism_cards(2),
            target="full",
        )
        self.assertFalse(status["valid"])
        status = validate_section_evidence_plans(
            self.section_evidence_plans(),
            self.argument_graph(),
            self.article_plan(),
            self.claims(),
            self.mechanism_cards(30),
            target="full",
        )
        self.assertTrue(status["valid"], status)

    def test_article_quality_rejects_internal_methodology_and_unsupported_claim(self):
        bad = (
            "# Survey\n\n## 调研设计\n"
            "本文采用 system-object survey 的结构。文献被分为 A-level 和 B-level。"
        )
        status = validate_article_quality(bad, self.article_plan(), self.argument_graph(), self.claims(), "full")
        self.assertFalse(status["valid"])
        self.assertIn("internal_or_scaffold_language", status["errors"])
        unsupported = self.review_text(20) + "\nThis system demonstrates a new causal result that is not recorded."
        status = validate_article_quality(unsupported, self.article_plan(), self.argument_graph(), self.claims(), "full")
        self.assertFalse(status["valid"])
        self.assertIn("unsupported_strong_article_claims", status["errors"])

    def test_article_quality_rejects_new_artifact_language(self):
        for phrase in ["article-facing", "支撑文件", "正文选择", "supporting material", "worked example 集合", "材料保留在"]:
            status = validate_article_quality(self.review_text(20) + phrase, self.article_plan(), self.argument_graph(), self.claims(), "full")
            self.assertFalse(status["valid"], phrase)
            self.assertIn("internal_or_scaffold_language", status["errors"])

    def test_article_quality_rejects_rendered_html_artifact_leakage(self):
        html = "<html><body><header>新版 skill 更新版：95 full-text A/B audited with source_ref and science paradigm profile.</header></body></html>"
        status = validate_article_quality(
            self.review_text(20),
            self.article_plan(),
            self.argument_graph(),
            self.claims(),
            "full",
            rendered_artifacts=[("outputs/review.html", html)],
        )
        self.assertFalse(status["valid"])
        self.assertIn("rendered_artifact_boundary", status["errors"])
        dashboard = "<html><body>gate_7_expert_review A/B full-text deep-read debug panel</body></html>"
        status = validate_article_quality(
            self.review_text(20),
            self.article_plan(),
            self.argument_graph(),
            self.claims(),
            "full",
            rendered_artifacts=[("dashboard/index.html", dashboard)],
        )
        self.assertTrue(status["valid"], status)

    def test_article_quality_rejects_process_correction_prose(self):
        bad = self.review_text(20) + "\n本综述不再把 WAM 拆成主目录中的七个系统节点。那种 system-node 视角不是文章 spine。"
        status = validate_article_quality(bad, self.article_plan(), self.argument_graph(), self.claims(), "full")
        self.assertFalse(status["valid"])
        self.assertIn("internal_or_scaffold_language", status["errors"])

    def test_article_quality_requires_tradeoff_and_evaluation_recipe(self):
        no_tradeoff = self.review_text(30).replace(
            "because two methods can share a benchmark label while using different pipelines, evaluation baselines, and limitations",
            "and this paragraph lists several related papers",
        )
        status = validate_article_quality(no_tradeoff, self.article_plan(), self.argument_graph(), self.claims(), "full")
        self.assertFalse(status["valid"])
        self.assertIn("missing_section_tradeoff", status["errors"])
        no_recipe = self.review_text(30).replace(
            "which baseline is used, and what limitation remains",
            "which paper is cited, and what topic remains",
        )
        no_recipe = no_recipe.replace(
            "A minimum evaluation recipe specifies protocol, metric, baseline, ablation, and confounder before the article interprets benchmark success.",
            "A citation paragraph lists papers before the article interprets benchmark success.",
        )
        no_recipe = no_recipe.replace("evaluation protocol matrix", "citation matrix")
        status = validate_article_quality(no_recipe, self.article_plan(), self.argument_graph(), self.claims(), "full")
        self.assertFalse(status["valid"])
        self.assertIn("missing_evaluation_recipe", status["errors"])

    def test_expert_review_gate_requires_independent_high_scoring_reviews(self):
        status = validate_expert_reviews(self.expert_reviews()[:2], target="full", review_invocations=self.expert_invocations()[:2])
        self.assertFalse(status["valid"])
        self.assertIn("too_few_expert_reviews", status["errors"])
        status = validate_expert_reviews(self.expert_reviews(score=8.4), target="full", review_invocations=self.expert_invocations())
        self.assertFalse(status["valid"])
        self.assertIn("median_score_below_threshold", status["errors"])
        status = validate_expert_reviews(self.expert_reviews(score=9.0), target="csur", review_invocations=self.expert_invocations())
        self.assertTrue(status["valid"], status)

    def test_expert_review_gate_rejects_duplicate_personas_and_unresolved_weaknesses(self):
        duplicate = self.expert_reviews()
        duplicate[1]["persona"] = duplicate[0]["persona"]
        status = validate_expert_reviews(duplicate, target="full", review_invocations=self.expert_invocations())
        self.assertFalse(status["valid"])
        self.assertIn("duplicate_reviewer_personas", status["errors"])
        weakness = {
            "weakness_id": "w1",
            "severity": "major",
            "evidence_quote": "The section reads like a paper list.",
            "why_it_matters": "It fails synthesis.",
            "route_to": "synthesis_dossiers",
            "repair_action": "rebuild method-family comparison",
        }
        status = validate_expert_reviews(self.expert_reviews(weaknesses=[weakness]), target="full", review_invocations=self.expert_invocations())
        self.assertFalse(status["valid"])
        self.assertIn("unresolved_major_weaknesses", status["errors"])
        bad = self.expert_reviews(weaknesses=[{"severity": "major", "route_to": "synthesis_dossiers"}])
        status = validate_expert_reviews(bad, target="full", review_invocations=self.expert_invocations())
        self.assertFalse(status["valid"])
        self.assertIn("invalid_expert_review_reports", status["errors"])

    def test_expert_review_gate_requires_invocations_and_repair_closure(self):
        status = validate_expert_reviews(self.expert_reviews(score=8.8), target="full")
        self.assertFalse(status["valid"])
        self.assertIn("missing_expert_review_invocations", status["errors"])
        bad_invocations = self.expert_invocations()
        bad_invocations[0]["fresh_context"] = False
        status = validate_expert_reviews(self.expert_reviews(score=8.8), target="full", review_invocations=bad_invocations)
        self.assertFalse(status["valid"])
        self.assertIn("invalid_expert_review_invocations", status["errors"])
        weakness = {
            "weakness_id": "w1",
            "severity": "major",
            "evidence_quote": "The section reads like a paper list.",
            "why_it_matters": "It fails synthesis.",
            "route_to": "synthesis_dossiers",
            "repair_action": "rebuild method-family comparison",
        }
        status = validate_expert_reviews(
            self.expert_reviews(weaknesses=[weakness]),
            target="full",
            review_invocations=self.expert_invocations(),
            repair_actions=self.repair_actions("w1"),
            regression_checks=[],
        )
        self.assertFalse(status["valid"])
        self.assertIn("missing_regression_checks_for_repairs", status["errors"])
        status = validate_expert_reviews(
            self.expert_reviews(weaknesses=[weakness]),
            target="full",
            review_invocations=self.expert_invocations(),
            repair_actions=self.repair_actions("w1"),
            regression_checks=self.regression_checks("w1"),
        )
        self.assertTrue(status["valid"], status)

    def test_survey_type_lenses_drive_required_dossiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "LLM uncertainty quantification", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "state/survey_type_plan.yml").write_text(
                "topic: LLM uncertainty quantification\n"
                "primary_type: method-family\n"
                "secondary_lenses:\n"
                "  - benchmark/evaluation\n"
                "why_this_type: The topic names a method family.\n"
                "why_not_other_types: It is not a composed system object.\n"
                "article_skeleton:\n"
                "  - Introduction\n"
                "  - Method Families\n"
                "  - Benchmark and Evaluation\n"
                "exemplar_alignment: Field Survey Exemplar uses definition -> taxonomy -> data ecosystem -> evaluation -> open challenges.\n"
                "community_native_taxonomy:\n"
                "  - calibration methods\n"
                "  - uncertainty estimation methods\n"
                "  - evaluation protocols\n"
                "exemplar_section_patterns:\n"
                "  - definition\n"
                "  - taxonomy\n"
                "  - data ecosystem\n"
                "  - evaluation protocol\n"
                "  - open challenges\n"
                "candidate_article_spines:\n"
                "  - community-native method-family taxonomy\n"
                "  - system-node diagnostic lens\n"
                "selected_article_spine: community-native method-family taxonomy\n"
                "why_not_exemplar_spine: The article adapts the exemplar pattern to uncertainty-specific method families.\n"
                "figure_first_plan: taxonomy roadmap; method evolution timeline; data ecosystem; evaluation protocol matrix.\n"
                "science_paradigm_profile: ML/AI systems\n"
                "evidence_norms:\n"
                "  - calibration and benchmark evidence must be separated from application claims\n"
                "required_evidence_units:\n"
                "  - benchmark\n"
                "  - metric\n"
                "  - baseline\n"
                "common_confounders:\n"
                "  - dataset shift\n"
                "  - prompt sensitivity\n"
                "  - calibration target mismatch\n"
                "excluded_templates:\n"
                "  - system-component-only survey\n",
                encoding="utf-8",
            )
            gates = evaluate_gates(task_dir, "full")
            self.assertTrue(gates["gate_5_argument_graph"]["passed"], gates["gate_5_argument_graph"])

    def test_gate_check_full_fixture_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            gates = evaluate_gates(task_dir, "full")
            self.assertTrue(gates["all_blocking_gates_passed"], gates)
            self.assertIn("gate_7_expert_review", gates)

    def test_gate_check_blocks_when_expert_review_missing_or_low_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "state/expert_review_reports.jsonl").write_text("", encoding="utf-8")
            gates = evaluate_gates(task_dir, "full")
            self.assertFalse(gates["all_blocking_gates_passed"])
            self.assertFalse(gates["gate_7_expert_review"]["passed"])

    def test_gate_check_blocks_rendered_html_leakage_and_missing_contribution_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "world action models", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "outputs" / "review.html").write_text("<html>新版 skill 更新版 full-text A/B audited source_ref</html>", encoding="utf-8")
            gates = evaluate_gates(task_dir, "full")
            self.assertFalse(gates["gate_6_article_quality"]["passed"])
            self.assertFalse(gates["all_blocking_gates_passed"])
            (task_dir / "outputs" / "review.html").unlink()
            (task_dir / "outputs" / "contribution_tree.yml").write_text("", encoding="utf-8")
            gates = evaluate_gates(task_dir, "full")
            self.assertFalse(gates["gate_5_argument_graph"]["passed"])
            self.assertIn("contribution_tree", gates["gate_5_argument_graph"])

    def test_gate_check_blocks_missing_full_text_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "state/full_text_sources.jsonl").write_text("", encoding="utf-8")
            gates = evaluate_gates(task_dir, "full")
            self.assertFalse(gates["gate_2_paper_understanding"]["passed"])
            self.assertFalse(gates["all_blocking_gates_passed"])

    def test_gate_check_blocks_missing_scenario_definitions_and_section_plans(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "state/scenario_definitions.yml").write_text("", encoding="utf-8")
            (task_dir / "state/section_evidence_plans.jsonl").write_text("", encoding="utf-8")
            gates = evaluate_gates(task_dir, "full")
            self.assertFalse(gates["gate_5_argument_graph"]["passed"])
            self.assertIn("scenario_definitions", gates["gate_5_argument_graph"])
            self.assertIn("section_evidence_plans", gates["gate_5_argument_graph"])

    def test_gate_check_distinguishes_expanded_coverage_from_deep_read_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "world action models", target="full")
            self.populate_full_task(task_dir)
            cards = self.mechanism_cards()
            for card in cards:
                card["reading_depth"] = "abstract_metadata_only"
                card["full_text_accessed"] = False
                card["source_type"] = "curated list metadata"
                card["sections_read"] = ["title and abstract"]
                card["evidence_span_locations"] = ["curated-list row"]
            write_jsonl(task_dir / "state" / "paper_mechanism_cards.jsonl", cards)
            gates = evaluate_gates(task_dir, "full")
            self.assertTrue(gates["gate_4_coverage"]["coverage_expanded"])
            self.assertFalse(gates["gate_2_paper_understanding"]["paper_understanding_complete"])
            self.assertFalse(gates["all_blocking_gates_passed"])

    def test_init_task_uses_new_state_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "test topic", target="full")
            self.assertTrue((task_dir / "state/survey_type_plan.yml").exists())
            self.assertTrue((task_dir / "state/scenario_definitions.yml").exists())
            self.assertTrue((task_dir / "state/section_evidence_plans.jsonl").exists())
            self.assertTrue((task_dir / "state/paper_mechanism_cards.jsonl").exists())
            self.assertTrue((task_dir / "state/full_text_sources.jsonl").exists())
            self.assertTrue((task_dir / "state/paper_contribution_statements.jsonl").exists())
            self.assertTrue((task_dir / "state/expert_review_invocations.jsonl").exists())
            self.assertTrue((task_dir / "state/repair_actions.jsonl").exists())
            self.assertTrue((task_dir / "state/regression_checks.jsonl").exists())
            self.assertFalse((task_dir / "state/paper_cards.jsonl").exists())
            gates = json.loads((task_dir / "state/completion_gates.json").read_text())
            self.assertIn("gate_6_article_quality", gates)
            self.assertIn("gate_7_expert_review", gates)
            self.assertNotIn("gate_7_review_depth", gates)
            self.assertTrue((task_dir / "state/expert_review_reports.jsonl").exists())
            self.assertTrue((task_dir / "state/weakness_routes.jsonl").exists())
            self.assertTrue((task_dir / "state/review_iteration_status.json").exists())

    def test_dashboard_renders_new_gate_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dashboard topic", target="short")
            path = render_dashboard(task_dir, "short")
            html = path.read_text(encoding="utf-8")
            self.assertIn("gate_1_source_identity", html)
            self.assertIn("gate_6_article_quality", html)
            self.assertIn("gate_7_expert_review", html)
            self.assertIn("A/B full-text deep-read", html)

    def test_lqs_keeps_foundational_roles(self):
        scored = score_paper({"paper_id": "p1", "survey_role": "seminal", "conceptual_centrality": 10, "mechanism_clarity": 8})
        self.assertEqual(scored["lqs_model"], "survey-role")
        self.assertNotEqual(classify_depth(scored, role="section protagonist"), "D")

    def test_deleted_legacy_files_and_terms_do_not_remain_in_main_flow(self):
        deleted_scripts = [
            "review_scorecard.py",
            "validate_review_depth.py",
            "validate_paper_cards.py",
            "validate_node_cards.py",
            "validate_section_cards.py",
            "validate_worked_examples.py",
        ]
        for script in deleted_scripts:
            self.assertFalse((ROOT / "scripts" / script).exists(), script)
        deleted_refs = [
            "article_layer.md",
            "deep_synthesis_artifacts.md",
            "publication_prose_translation.md",
            "worked_example_patterns.md",
            "section_card_patterns.md",
        ]
        for ref in deleted_refs:
            self.assertFalse((ROOT / "references" / ref).exists(), ref)
        main_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [ROOT / "SKILL.md", ROOT / "scripts/gate_check.py"]
        )
        for old in ["paper_cards", "paper_facts", "section_cards", "worked_examples", "review_scorecard", "review_depth"]:
            self.assertNotIn(old, main_text)


if __name__ == "__main__":
    unittest.main()
