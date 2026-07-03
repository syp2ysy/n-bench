import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_contribution_tree import validate_contribution_tree
from scripts.expert_review_gate import validate_expert_reviews
from scripts.gate_check import evaluate_gates
from scripts.init_task import initialize_task
from scripts.phase_gate import evaluate_phase_barriers
from scripts.render_dashboard import render_dashboard
from scripts.run_expert_reviews import collect_status, dispatch_packets, freeze_review_round
from scripts.score_lqs import classify_depth, score_paper
from scripts.validate_argument_graph import validate_argument_graph
from scripts.validate_article_quality import validate_article_quality
from scripts.validate_claim_evidence import validate_claim_evidence
from scripts.validate_coverage import validate_coverage
from scripts.validate_exemplar_alignment import validate_exemplar_alignment
from scripts.validate_paper_understanding import validate_paper_understanding
from scripts.validate_scenario_definitions import validate_scenario_definitions
from scripts.validate_section_evidence_plans import validate_section_evidence_plans
from scripts.validate_synthesis_dossiers import validate_synthesis_dossiers
from scripts.verify_sources import validate_sources


ROOT = Path(__file__).resolve().parents[1]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


class SurveyAutoResearchContractTest(unittest.TestCase):
    dimensions = [
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
    personas = [
        ("domain_expert", "Domain Expert Reviewer"),
        ("survey_architect", "Survey Architect Reviewer"),
        ("evidence_factuality", "Evidence/Factuality Reviewer"),
        ("newcomer_tutorial", "Newcomer/Tutorial Reviewer"),
        ("style_publication", "Style/Publication Reviewer"),
    ]

    def papers(self, total: int = 160, related_surveys: int = 8) -> list[dict]:
        return [
            {
                "paper_id": f"p{idx:03d}",
                "title": f"Verified Paper {idx}",
                "authors": ["A. Author"],
                "year": 2025,
                "venue_status": "peer-reviewed" if idx % 3 else "arxiv",
                "doi": f"10.0000/{idx}",
                "verification_status": "verified",
                "verified_sources": ["doi"],
                "source_candidate_id": f"cand-{idx:03d}",
                "survey_role": "survey" if idx <= related_surveys else ("benchmark" if idx % 5 == 0 else "method"),
                "family": "family-a" if idx % 2 else "family-b",
            }
            for idx in range(1, total + 1)
        ]

    def raw_candidates(self, total: int = 220, related_surveys: int = 8) -> list[dict]:
        return [
            {
                "candidate_id": f"cand-{idx:03d}",
                "paper_id": f"p{idx:03d}",
                "title": f"{'Survey' if idx <= related_surveys else 'Candidate'} Paper {idx}",
                "source": "Semantic Scholar",
                "query": "embodied memory survey",
                "survey_role": "survey" if idx <= related_surveys else ("benchmark" if idx % 5 == 0 else "method"),
            }
            for idx in range(1, total + 1)
        ]

    def search_routes(self, total: int = 8) -> list[dict]:
        families = ["seed", "synonym", "related_survey", "curated_list", "benchmark_page", "venue_domain", "backward_citation", "forward_citation"]
        return [
            {
                "route_id": f"route-{idx:02d}",
                "source": "Semantic Scholar" if idx % 2 else "OpenAlex",
                "query": f"{families[(idx - 1) % len(families)]} query",
                "query_family": families[(idx - 1) % len(families)],
                "results_seen": 50,
                "candidates_retained": 20,
            }
            for idx in range(1, total + 1)
        ]

    def lqs_scores(self, total: int = 220) -> list[dict]:
        return [{"candidate_id": f"cand-{idx:03d}", "paper_id": f"p{idx:03d}", "lqs": 8.0, "depth_recommendation": "B"} for idx in range(1, total + 1)]

    def citation_plan(self, a: int = 25, b: int = 70, c: int = 65) -> list[dict]:
        rows = []
        idx = 1
        for depth, count in [("A", a), ("B", b), ("C", c)]:
            for _ in range(count):
                rows.append({"paper_id": f"p{idx:03d}", "depth": depth})
                idx += 1
        return rows

    def corpus_expansion(self, required: bool = False, status: str = "not_required") -> dict:
        return {
            "required": required,
            "triggered_by": ["curated list larger than retained corpus"] if required else [],
            "visible_external_count": 500 if required else 0,
            "retained_candidate_count": 220,
            "expansion_rounds": [],
            "status": status,
            "waiver_reason": "",
        }

    def mechanism_cards(self, count: int = 95) -> list[dict]:
        return [
            {
                "paper_id": f"p{idx:03d}",
                "title": f"Verified Paper {idx}",
                "survey_role": "method",
                "level": "A" if idx <= 25 else "B",
                "reading_depth": "full_text_deep_read",
                "full_text_accessed": True,
                "source_type": "arxiv_pdf",
                "full_text_sources": [f"src-p{idx:03d}"],
                "sections_read": [
                    "Introduction and problem formulation",
                    "Method and system architecture",
                    "Experiments and evaluation setup",
                    "Results, discussion, and limitations",
                ],
                "evidence_span_locations": ["Section 1, page 1", "Section 3, pages 4-6", "Section 4, Table 2", "Section 5, page 9"],
                "deep_read_notes": "Full text was read across problem, method, experiment, result, and limitation sections.",
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
                "main_results": [{"result": "The method improves the diagnostic benchmark over the no-memory baseline.", "evidence_span": "Section 4, Table 2.", "claim_strength": "shows"}],
                "limitations_and_confounders": ["perception and controller strength may confound aggregate success", "the evidence does not isolate all deployment-time failures"],
                "relation_to_prior_work": "extends prior context-only systems with explicit evidence use.",
                "what_it_changes_in_the_survey_argument": "It supports the claim that memory must be evaluated through evidence and control interfaces.",
                "must_not_overclaim": ["does not demonstrate general memory causality without negative controls"],
                "evidence_spans": ["Section 4, Table 2 reports the comparison."],
            }
            for idx in range(1, count + 1)
        ]

    def full_text_sources(self, count: int = 95) -> list[dict]:
        return [
            {
                "paper_id": f"p{idx:03d}",
                "source_ref": f"src-p{idx:03d}",
                "source_url": f"https://arxiv.org/pdf/0000.{idx:05d}",
                "source_kind": "arxiv_pdf",
                "access_status": "accessible",
                "extraction_status": "extracted",
                "captured_excerpts": [{"section_or_page": "Section 4, Table 2", "excerpt": "The method is compared with a no-memory baseline and improves the diagnostic benchmark."}],
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
                "statement": "This paper addresses evidence-conditioned decisions by using structured retrieval, evaluates on Benchmark-X against a no-memory baseline, and shows diagnostic improvement while retaining confounders.",
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
            "candidate_article_spines": ["contribution-tree: retrieval memory vs structured map memory", "system-node diagnostic lens"],
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

    def scenario_definitions(self) -> dict:
        return {
            "scenarios": [
                {
                    "scenario": name,
                    "object_definition": f"{name} defines memory through task-specific state and evidence.",
                    "required_fields": ["state", "source", "time", "task"],
                    "typical_benchmarks": [f"{name}-Bench"],
                    "unsuitable_claims": [f"{name} success alone does not prove all memory mechanisms."],
                    "evaluation_pressure": "diagnostic pressure with confounders",
                    "failure_risks": ["stale evidence", "wrong retrieval"],
                }
                for name in ["navigation", "EQA", "manipulation", "VLA", "lifelong"]
            ]
        }

    def method_dossier(self) -> dict:
        return {
            "family": "retrieval memory",
            "family_motivation": "Retrieve grounded evidence for downstream decisions.",
            "assumptions": ["history can be indexed", "retrieval affects a controller"],
            "representative_a_papers": ["p001", "p002"],
            "supporting_b_papers": ["p026", "p027"],
            "shared_mechanism_pattern": "write structured evidence, retrieve it by task-conditioned keys, then expose it to a controller",
            "differences_among_representative_papers": "p001 uses local evidence while p002 uses a broader external store.",
            "relation_graph": [{"source": "p001", "target": "p002", "relation": "alternative", "reason": "different retrieval granularity"}],
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
        titles = ["Introduction", "Method Families", "Benchmark and Evaluation", "Evidence and Limitations", "Design Guidance", "Open Problems"]
        return [
            {
                "section_id": f"S{idx}",
                "title": title,
                "argument_node": "A1" if idx == 1 else ("A2" if idx == 2 else "A3"),
                "section_claim": f"{title} connects mechanisms, evidence, and limitations.",
                "scenario_definitions_used": ["EQA"],
                "method_families_used": ["retrieval memory"] if idx > 1 else [],
                "anchor_papers": ["p001"],
                "supporting_papers": ["p026"],
                "benchmarks": ["EQA-Bench"] if idx > 1 else [],
                "required_comparisons": ["evidence strength vs overclaim risk"],
                "must_include_evidence_spans": ["c1"],
                "must_not_overclaim": ["do not overstate causal memory claims"],
                "protocol": "compare no-memory, oracle evidence, and wrong evidence" if idx == 3 else "",
                "metric": "accuracy and groundedness" if idx == 3 else "",
                "baseline": "closed-book answerer" if idx == 3 else "",
                "confounder": "language priors" if idx == 3 else "",
            }
            for idx, title in enumerate(titles, start=1)
        ]

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
            "paper_relation_graph": [{"source": "p001", "target": "p002", "relation": "alternative retrieval granularity"}],
            "contribution_tree": "outputs/contribution_tree.yml",
            "candidate_spines_from_contribution_tree": ["retrieval memory", "structured map memory"],
            "exemplar_delta": "The article follows definition, taxonomy, data ecosystem, evaluation, and open challenges.",
            "figure_plan": {"taxonomy_roadmap": "map", "method_evolution_timeline": "timeline", "data_ecosystem": "table", "evaluation_protocol_matrix": "matrix"},
            "story_skeleton": ["field_shift", "fragmented_existing_view", "new_unifying_lens", "scenario-specific definitions", "method-family comparison", "benchmark/evidence limitations", "research agenda"],
            "argument_nodes": {
                "A1": {"claim": "Existing views fragment mechanisms.", "evidence": ["related_survey_matrix"], "scenario_links": ["navigation"], "method_family_links": [], "benchmark_links": [], "implication": "Use an interface-centered lens.", "section": "Introduction", "section_role": "definition", "leads_to": ["A2"]},
                "A2": {"claim": "Method families differ by mechanism and evidence.", "evidence": ["method_family_dossiers"], "scenario_links": ["EQA"], "method_family_links": ["retrieval memory"], "benchmark_links": ["EQA-Bench"], "implication": "Compare methods by pipeline and result support.", "section": "Method Families", "section_role": "taxonomy", "leads_to": ["A3"]},
                "A3": {"claim": "Benchmarks operationalize but do not automatically prove claims.", "evidence": ["benchmark_dossiers"], "scenario_links": ["EQA"], "method_family_links": ["retrieval memory"], "benchmark_links": ["EQA-Bench"], "benchmark_limit": "success does not prove causal memory contribution without diagnostic controls", "implication": "Use diagnostic controls.", "section": "Benchmark and Evaluation", "section_role": "evaluation", "leads_to": []},
            },
            "section_order": ["Introduction", "Method Families", "Benchmark and Evaluation"],
            "takeaway_findings": ["Evidence strength controls article wording."],
        }

    def article_plan(self) -> str:
        return (
            "# Article Plan\n\n"
            "## Article Body Sections\n- Introduction\n- Method Families\n- Benchmark and Evaluation\n- Evidence and Limitations\n- Design Guidance\n- Open Problems\n\n"
            "## Article Displays\n- Taxonomy roadmap figure\n- Method evolution timeline figure\n- Data ecosystem figure or table\n- Evaluation protocol matrix\n- Method comparison table\n- Benchmark protocol table\n\n"
            "## Appendix Sections\n- Search protocol\n- Broad coverage matrix\n\n"
            "## Internal Only\n- Keep source routes, evidence labels, run counts, and repair notes out of review.md.\n"
        )

    def review_text(self, repeat: int = 8) -> str:
        section = (
            "This section starts from a clear thesis: memory is useful only when prior evidence changes a later decision. "
            "The comparison matters because two methods can share a benchmark label while using different pipelines, evaluation baselines, and limitations. "
            "Instead of listing papers, the prose explains motivation, mechanism, experimental support, and confounders. "
            "Therefore, the section closes by linking method design to evidence and evaluation choices.\n\n"
        )
        table = (
            "The comparison table is introduced as a publication-ready synthesis of mechanism and evidence.\n\n"
            "| Family | Mechanism | Evidence | Limitation |\n| --- | --- | --- | --- |\n| Retrieval | writes and reads structured evidence | no-memory comparison | perception confounder |\n\n"
            "The table shows that method labels are insufficient. A reader should compare what evidence is written, how it is retrieved, which baseline is used, and what limitation remains.\n\n"
            "A minimum evaluation recipe specifies protocol, metric, baseline, ablation, and confounder before the article interprets benchmark success.\n\n"
        )
        body = (section + table) * repeat
        return "# Survey\n\n" + "".join(f"## {title}\n{body}" for title in ["Introduction", "Method Families", "Benchmark and Evaluation", "Evidence and Limitations", "Design Guidance", "Open Problems"]) + "## Conclusion\n" + section

    def expert_reviews(self, score: float = 8.8, weaknesses: list[dict] | None = None) -> list[dict]:
        sections = ["Introduction", "Method Families", "Benchmark and Evaluation", "Evidence and Limitations", "Design Guidance", "Open Problems", "Conclusion"]
        quotes = [
            "memory is useful only when prior evidence changes a later decision",
            "two methods can share a benchmark label while using different pipelines",
            "the prose explains motivation, mechanism, experimental support, and confounders",
            "the section closes by linking method design to evidence and evaluation choices",
            "The table shows that method labels are insufficient",
        ]
        reports = []
        for offset, (reviewer_id, persona) in enumerate(self.personas):
            dims = {name: max(0, min(10, score - offset * 0.01)) for name in self.dimensions}
            report = {
                "reviewer_id": reviewer_id,
                "persona": persona,
                "overall_score": score,
                "dimension_scores": dims,
                "dimension_audits": [
                    {
                        "dimension": name,
                        "score": dims[name],
                        "verdict": "pass" if dims[name] >= 8 else "fail",
                        "evidence_quotes": [quotes[offset % len(quotes)]],
                        "failure_cases": [] if dims[name] >= 8 else [f"{name} below threshold"],
                        "why_it_matters": f"{persona} checks whether {name} is mature enough.",
                        "repair_recommendation": f"Repair {name} through evidence-backed routing.",
                        "route_to": "claim_evidence" if "evidence" in name else ("benchmark_dossiers" if "benchmark" in name else ("paper_understanding" if "paper" in name else "article_quality")),
                    }
                    for name in self.dimensions
                ],
                "blocking_weaknesses": weaknesses or [],
                "pass_recommendation": not weaknesses and score >= 8.5,
                "summary": f"{persona} read the complete article and found persona-specific strengths and risks.",
                "review_trace": {"reviewed_full_article": True, "article_chars_read": len(self.review_text())},
                "sections_reviewed": sections,
                "section_comments": {section: f"{persona} says {section} links claims, evidence, and limitations." for section in sections},
                "quoted_evidence_from_review": quotes,
            }
            report.update(self.persona_audit(persona))
            reports.append(report)
        return reports

    def persona_audit(self, persona: str) -> dict:
        if persona == "Domain Expert Reviewer":
            return {"paper_mechanism_audits": [{"paper_id": f"p{idx:03d}", "verdict": "consistent", "finding": "Mechanism wording matches the full-text card."} for idx in range(1, 11)]}
        if persona == "Survey Architect Reviewer":
            return {"flow_taxonomy_audit": {"section_flow": "The article progresses from motivation to taxonomy, evidence, and open problems.", "taxonomy_coherence": "The taxonomy compares mechanisms and interfaces.", "synthesis_vs_catalog": "Tables are interpreted and not used as paper dumps."}}
        if persona == "Evidence/Factuality Reviewer":
            return {"claim_citation_audits": [{"claim_id": "c1", "paper_id": f"p{idx:03d}", "verdict": "supported", "finding": "The claim is tied to a full-text span."} for idx in range(1, 11)]}
        if persona == "Newcomer/Tutorial Reviewer":
            return {"tutorial_audit": {"glossary_clarity": "Terms are clear enough for a new reader.", "running_example_usefulness": "The running example connects memory and evaluation.", "confusing_terms": "Remaining confusing terms are named and explained."}}
        return {"style_audit": {"repetition": "Repeated claims are controlled through section-specific implications.", "artifact_leakage": "No workflow language remains in the publication-facing article body.", "table_interpretation": "Tables are introduced and interpreted with prose before and after each display.", "transition_quality": "Transitions connect the prior evidence to the next argument step."}}

    def expert_invocations(self, returned: bool = True) -> list[dict]:
        return [
            {
                "review_round_id": "round-1",
                "reviewer_id": reviewer_id,
                "persona": persona,
                "fresh_context": True,
                "subagent_session_id": f"subagent-{reviewer_id}",
                "inputs": ["outputs/review.md", "outputs/appendix.md", "state/paper_mechanism_cards.jsonl"],
                "forbidden_inputs": ["previous reviewer reports", "state/expert_review_reports.jsonl", "repair actions from this round"],
                "output": "state/expert_review_reports.jsonl",
                "status": "returned" if returned else "dispatched",
                "timestamp": "2026-07-03T00:00:00Z",
            }
            for reviewer_id, persona in self.personas
        ]

    def review_round_status(self, returned: int = 5, repaired_hash: str = "hash-after-repair") -> dict:
        return {
            "review_round_id": "round-1",
            "status": "all_reports_received" if returned == 5 else "collecting_reviews",
            "review_freeze": {
                "review_round_id": "round-1",
                "started_at": "2026-07-03T00:00:00Z",
                "frozen_artifacts": {"outputs/review.md": "hash-review", "outputs/appendix.md": "hash-appendix", "state/argument_graph.yml": "hash-argument", "state/section_evidence_plans.jsonl": "hash-section-plans"},
                "article_hash": "hash-review",
            },
            "all_reports_received": returned == 5,
            "reviewers_expected": 5,
            "reviewers_returned": returned,
            "repaired_article_hash": repaired_hash,
        }

    def weakness(self, weakness_id: str = "w1") -> dict:
        return {"weakness_id": weakness_id, "severity": "major", "evidence_quote": "The section reads like a paper list.", "why_it_matters": "It fails synthesis.", "route_to": "synthesis_dossiers", "repair_action": "rebuild method-family comparison"}

    def adjudication(self, weakness_id: str | None = None) -> dict:
        canonical = []
        if weakness_id:
            canonical.append(
                {
                    "weakness_id": weakness_id,
                    "severity": "major",
                    "source_reviewers": ["domain_expert"],
                    "source_weakness_ids": [weakness_id],
                    "affected_sections": ["Method Families"],
                    "affected_papers": ["p001"],
                    "affected_claims": ["c1"],
                    "route_to": "synthesis_dossiers",
                    "required_evidence_check": ["contribution_tree", "argument_graph"],
                    "repair_acceptance_criteria": "The repaired section compares method families and is supported by the contribution tree.",
                }
            )
        return {"review_round_id": "round-1", "all_major_weaknesses_adjudicated": True, "canonical_weaknesses": canonical}

    def repair_actions(self, weakness_id: str = "w1", evidence: bool = True) -> list[dict]:
        return [
            {
                "weakness_id": weakness_id,
                "status": "resolved",
                "route_to": "synthesis_dossiers",
                "evidence_rechecked": [
                    {"source": "contribution_tree", "id": "outputs/contribution_tree.yml", "finding": "The tree supports rebuilding comparison.", "supports_repair": True},
                    {"source": "argument_graph", "id": "state/argument_graph.yml", "finding": "The graph requires mechanism comparison.", "supports_repair": True},
                ]
                if evidence
                else [],
                "repair_action": "rebuild method-family comparison",
                "changed_artifacts": ["outputs/method_family_dossiers/retrieval_memory.json", "outputs/review.md"],
                "evidence": "The method family now compares alternatives, trade-offs, and evidence limits.",
                "claim_strength_changes": [],
                "new_or_modified_claims": [],
            }
        ]

    def regression_checks(self, weakness_id: str = "w1") -> list[dict]:
        return [{"weakness_id": weakness_id, "status": "passed", "command": "python3 -m unittest tests/test_scripts.py", "result": "OK"}]

    def targeted_rereviews(self, weakness_id: str = "w1", verdict: str = "resolved", article_hash: str = "hash-after-repair") -> list[dict]:
        return [
            {
                "weakness_id": weakness_id,
                "reviewer_id": "survey_architect",
                "persona": "Survey Architect Reviewer",
                "checked_changed_artifacts": ["outputs/review.md", "outputs/method_family_dossiers/retrieval_memory.json"],
                "checked_evidence_refs": ["outputs/contribution_tree.yml", "state/argument_graph.yml"],
                "verdict": verdict,
                "evidence_quote_after_repair": "The repaired method section compares retrieval memory with structured map memory.",
                "remaining_risk": "No blocking risk remains after targeted rereview.",
                "article_hash": article_hash,
            }
        ]

    def expert_gate_kwargs(self, weakness_id: str | None = None) -> dict:
        return {
            "round_status": self.review_round_status(),
            "adjudication": self.adjudication(weakness_id),
            "targeted_rereviews": self.targeted_rereviews(weakness_id) if weakness_id else [],
        }

    def populate_full_task(self, task_dir: Path) -> None:
        state, outputs = task_dir / "state", task_dir / "outputs"
        write_jsonl(state / "raw_candidates.jsonl", self.raw_candidates())
        write_jsonl(state / "search_routes.jsonl", self.search_routes())
        write_jsonl(state / "lqs_scores.jsonl", self.lqs_scores())
        (state / "corpus_expansion.json").write_text(json.dumps(self.corpus_expansion()), encoding="utf-8")
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
        write_jsonl(state / "targeted_rereview_reports.jsonl", [])
        (state / "expert_review_round_status.json").write_text(json.dumps(self.review_round_status()), encoding="utf-8")
        (state / "expert_review_adjudication.json").write_text(json.dumps(self.adjudication()), encoding="utf-8")
        (state / "review_iteration_status.json").write_text(json.dumps({"round": 1, "last_median_score": 8.8, "previous_median_score": None}), encoding="utf-8")
        (state / "survey_type_plan.yml").write_text(
            "topic: embodied memory system\nprimary_type: system-object\nsecondary_lenses:\n  - method-family\n  - benchmark/evaluation\nwhy_this_type: The topic names a system object.\nwhy_not_other_types: A pure task survey would fragment evidence.\narticle_skeleton:\n  - Introduction\n  - Method Families\n  - Benchmark and Evaluation\nexemplar_alignment: Field Survey Exemplar uses definition -> taxonomy -> data ecosystem -> evaluation -> open challenges.\ncommunity_native_taxonomy:\n  - retrieval memory\n  - structured map memory\n  - episodic policy memory\nexemplar_section_patterns:\n  - definition\n  - taxonomy\n  - data ecosystem\n  - evaluation protocol\n  - open challenges\ncandidate_article_spines:\n  - community-native method-family taxonomy\n  - system-node diagnostic lens\nselected_article_spine: community-native method-family taxonomy\nwhy_not_exemplar_spine: The article adapts the exemplar pattern to an evidence-to-action interface topic.\nfigure_first_plan: taxonomy roadmap; method evolution timeline; data ecosystem; evaluation protocol matrix.\nscience_paradigm_profile: robotics/embodied-ai\nevidence_norms:\n  - benchmark/baseline/ablation evidence is required for method claims\nrequired_evidence_units:\n  - benchmark\n  - baseline\n  - ablation\ncommon_confounders:\n  - perception\n  - controller capacity\nexcluded_templates:\n  - pure chronological survey\n",
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
            (outputs / dirname).mkdir(exist_ok=True)
        (outputs / "method_family_dossiers" / "retrieval_memory.json").write_text(json.dumps(self.method_dossier()), encoding="utf-8")
        (outputs / "benchmark_dossiers" / "eqa_bench.json").write_text(json.dumps(self.benchmark_dossier()), encoding="utf-8")

    def test_discovery_and_source_contracts(self):
        weak = validate_coverage(self.raw_candidates(30), self.search_routes(2), self.lqs_scores(30), self.corpus_expansion(), self.papers(20), self.citation_plan(2, 4, 14), "full")
        self.assertFalse(weak["valid"])
        self.assertFalse(weak["discovery_sufficient"])
        expansion = validate_coverage(self.raw_candidates(), self.search_routes(), self.lqs_scores(), self.corpus_expansion(True, "pending"), self.papers(), self.citation_plan(), "full")
        self.assertFalse(expansion["valid"])
        papers = self.papers(3, 0)
        papers[1]["verification_status"] = "unverified"
        self.assertFalse(validate_sources(papers, [{"paper_id": "p001", "depth": "A"}, {"paper_id": "p002", "depth": "B"}], "full")["valid"])

    def test_retained_papers_must_link_to_raw_candidates(self):
        papers = self.papers()
        papers[0].pop("source_candidate_id")
        status = validate_coverage(self.raw_candidates(), self.search_routes(), self.lqs_scores(), self.corpus_expansion(), papers, self.citation_plan(), "full")
        self.assertFalse(status["valid"])
        self.assertIn("paper_candidate_linkage", status["retained_missing"])

    def test_paper_understanding_completion_contract(self):
        valid = validate_paper_understanding(self.mechanism_cards(1), [{"paper_id": "p001", "depth": "A"}], self.full_text_sources(1))
        self.assertTrue(valid["valid"], valid)
        cases = {}
        cases["missing_card"] = []
        metadata = self.mechanism_cards(1)
        metadata[0].update({"reading_depth": "abstract_metadata_only", "full_text_accessed": False, "source_type": "Semantic Scholar metadata", "sections_read": ["abstract"], "evidence_span_locations": ["metadata row"]})
        cases["metadata_only"] = metadata
        generic = self.mechanism_cards(1)
        generic[0]["motivation"] = "This paper is important and relevant to the survey."
        generic[0]["deep_read_notes"] = ""
        cases["generic_or_empty"] = generic
        for name, cards in cases.items():
            with self.subTest(name=name):
                status = validate_paper_understanding(cards, [{"paper_id": "p001", "depth": "A"}], self.full_text_sources(1))
                self.assertFalse(status["valid"], status)

    def test_claim_evidence_contract(self):
        base_claim = self.claims()[0]
        bad_cases = {
            "missing_span": [{**base_claim, "evidence_spans": []}],
            "overclaim": [{**base_claim, "strength": "demonstrates", "evidence_spans": [{**base_claim["evidence_spans"][0], "strength": "suggests"}]}],
            "metadata_only_support": [{**base_claim, "evidence_spans": [{**base_claim["evidence_spans"][0], "section_or_page": "Semantic Scholar metadata", "excerpt": "metadata"}]}],
        }
        for name, claims in bad_cases.items():
            with self.subTest(name=name):
                self.assertFalse(validate_claim_evidence(claims, self.mechanism_cards(1), self.section_evidence_plans(), full_text_sources=self.full_text_sources(1))["valid"])
        self.assertTrue(validate_claim_evidence(self.claims(), self.mechanism_cards(1), self.section_evidence_plans(), full_text_sources=self.full_text_sources(1))["valid"])

    def test_synthesis_and_argument_contracts(self):
        self.assertTrue(validate_contribution_tree(self.contribution_statements(), json.dumps(self.contribution_tree()), self.citation_plan(), self.argument_graph(), "full")["valid"])
        self.assertFalse(validate_contribution_tree(self.contribution_statements(10), json.dumps({"branches": []}), self.citation_plan(), self.argument_graph(), "full")["valid"])
        self.assertTrue(validate_scenario_definitions(json.dumps(self.scenario_definitions()), "full")["valid"])
        self.assertFalse(validate_scenario_definitions(json.dumps({"scenarios": [{"scenario": "navigation"}]}), "full")["valid"])
        self.assertTrue(validate_synthesis_dossiers([self.method_dossier()], [self.benchmark_dossier()], json.dumps(self.scenario_definitions()), self.mechanism_cards(), "full")["valid"])
        bad_method = self.method_dossier()
        bad_method["differences_among_representative_papers"] = ""
        self.assertFalse(validate_synthesis_dossiers([bad_method], [self.benchmark_dossier()], json.dumps(self.scenario_definitions()), self.mechanism_cards(), "full")["valid"])
        self.assertTrue(validate_argument_graph(self.argument_graph(), self.article_plan())["valid"])
        bad_graph = self.argument_graph()
        bad_graph["argument_nodes"]["A2"].pop("section")
        self.assertFalse(validate_argument_graph(bad_graph, self.article_plan())["valid"])

    def test_section_exemplar_and_survey_type_contracts(self):
        self.assertTrue(validate_section_evidence_plans(self.section_evidence_plans(), self.argument_graph(), self.article_plan(), self.claims(), self.mechanism_cards(), "full")["valid"])
        plans = self.section_evidence_plans()
        plans[1]["required_comparisons"] = []
        self.assertFalse(validate_section_evidence_plans(plans, self.argument_graph(), self.article_plan(), self.claims(), self.mechanism_cards(), "full")["valid"])
        survey_type = "topic: LLM uncertainty quantification\nprimary_type: method-family\nsecondary_lenses:\n  - benchmark/evaluation\nwhy_this_type: method family\nwhy_not_other_types: not a component-only survey\narticle_skeleton:\n  - Introduction\n  - Method Families\n  - Benchmark and Evaluation\nexemplar_alignment: Field Survey Exemplar uses definition -> taxonomy -> data ecosystem -> evaluation -> open challenges.\ncommunity_native_taxonomy:\n  - calibration methods\n  - uncertainty estimation methods\n  - evaluation protocols\nexemplar_section_patterns:\n  - definition\n  - taxonomy\n  - data ecosystem\ncandidate_article_spines:\n  - method-family taxonomy\n  - risk/trust taxonomy\nselected_article_spine: method-family taxonomy\nwhy_not_exemplar_spine: adapted to uncertainty\nfigure_first_plan: taxonomy roadmap; method evolution timeline; data ecosystem; evaluation protocol matrix.\nscience_paradigm_profile: ML systems\nevidence_norms:\n  - calibration evidence must be benchmarked\nrequired_evidence_units:\n  - benchmark\n  - metric\n  - baseline\ncommon_confounders:\n  - dataset shift\n  - prompt sensitivity\nexcluded_templates:\n  - system-component-only survey\n"
        self.assertTrue(validate_exemplar_alignment(survey_type, self.argument_graph(), self.article_plan(), "full")["valid"])

    def test_article_quality_contract(self):
        good = validate_article_quality(self.review_text(), self.article_plan(), self.argument_graph(), self.claims(), "full")
        self.assertTrue(good["valid"], good)
        bad_text = self.review_text() + "\n本文采用 system-object survey 的结构。完整 material 保留在支撑文件中。"
        self.assertFalse(validate_article_quality(bad_text, self.article_plan(), self.argument_graph(), self.claims(), "full")["valid"])
        rendered = validate_article_quality(self.review_text(), self.article_plan(), self.argument_graph(), self.claims(), "full", rendered_artifacts=[("review.html", "<html>新版 skill 更新版 source_ref full-text A/B audited</html>")])
        self.assertFalse(rendered["valid"])
        no_recipe = self.review_text().replace("protocol, metric, baseline, ablation, and confounder", "paper title and citation")
        self.assertFalse(validate_article_quality(no_recipe, self.article_plan(), self.argument_graph(), self.claims(), "full")["valid"])

    def test_expert_review_loop_contract(self):
        valid_weakness = self.weakness()
        valid = validate_expert_reviews(
            self.expert_reviews(weaknesses=[valid_weakness]),
            target="full",
            review_invocations=self.expert_invocations(),
            repair_actions=self.repair_actions("w1"),
            regression_checks=self.regression_checks("w1"),
            round_status=self.review_round_status(),
            adjudication=self.adjudication("w1"),
            targeted_rereviews=self.targeted_rereviews("w1"),
        )
        self.assertTrue(valid["valid"], valid)
        cases = {
            "missing_persona": dict(reports=self.expert_reviews()[:4], invocations=self.expert_invocations()[:4], errors=["too_few_expert_reviews", "missing_required_personas"]),
            "missing_dimension_audits": dict(mutator=lambda reports: reports[0].pop("dimension_audits"), errors=["invalid_expert_review_reports"]),
            "low_dimension_without_major": dict(mutator=lambda reports: (reports[0]["dimension_audits"][0].update({"score": 7.5, "verdict": "fail"}), reports[0]["dimension_scores"].update({"narrative_coherence": 7.5})), errors=["invalid_expert_review_reports"]),
            "repair_before_all_returned": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), invocations=self.expert_invocations()[:4], repairs=self.repair_actions("w1"), round_status=self.review_round_status(returned=4), adjudication=self.adjudication("w1"), targeted=self.targeted_rereviews("w1"), errors=["repair_before_all_reviews_returned"]),
            "missing_adjudication": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), repairs=self.repair_actions("w1"), adjudication=self.adjudication(), targeted=self.targeted_rereviews("w1"), errors=["unadjudicated_major_weaknesses"]),
            "repair_without_evidence": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), repairs=self.repair_actions("w1", evidence=False), adjudication=self.adjudication("w1"), targeted=self.targeted_rereviews("w1"), errors=["invalid_repair_actions"]),
            "missing_targeted_rereview": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), repairs=self.repair_actions("w1"), adjudication=self.adjudication("w1"), targeted=[], errors=["missing_targeted_rereviews"]),
        }
        for name, spec in cases.items():
            reports = spec.get("reports", self.expert_reviews())
            if "mutator" in spec:
                spec["mutator"](reports)
            status = validate_expert_reviews(
                reports,
                target="full",
                review_invocations=spec.get("invocations", self.expert_invocations()),
                repair_actions=spec.get("repairs", []),
                regression_checks=self.regression_checks("w1"),
                round_status=spec.get("round_status", self.review_round_status()),
                adjudication=spec.get("adjudication", self.adjudication()),
                targeted_rereviews=spec.get("targeted", []),
            )
            with self.subTest(name=name):
                self.assertFalse(status["valid"], status)
                for error in spec["errors"]:
                    self.assertIn(error, status["errors"])

    def test_expert_review_rejects_targeted_rereview_hash_mismatch(self):
        weakness = self.weakness()
        status = validate_expert_reviews(
            self.expert_reviews(weaknesses=[weakness]),
            target="full",
            review_invocations=self.expert_invocations(),
            repair_actions=self.repair_actions("w1"),
            regression_checks=self.regression_checks("w1"),
            round_status=self.review_round_status(),
            adjudication=self.adjudication("w1"),
            targeted_rereviews=self.targeted_rereviews("w1", article_hash="wrong-hash"),
        )
        self.assertFalse(status["valid"])
        self.assertIn("invalid_targeted_rereviews", status["errors"])

    def test_phase_gate_blocks_downstream_when_paper_understanding_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            write_jsonl(task_dir / "state/paper_mechanism_cards.jsonl", self.mechanism_cards(94))
            status = evaluate_phase_barriers(task_dir, "full")
            self.assertFalse(status["phases"]["paper_understanding"]["passed"])
            self.assertIn("illegal_downstream_artifacts", status["phases"]["paper_understanding"])

    def test_phase_gate_reports_expert_review_next_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "state/expert_review_reports.jsonl").write_text("", encoding="utf-8")
            status = evaluate_phase_barriers(task_dir, "full")
            self.assertEqual(status["blocked_by_phase"], "expert_review")
            self.assertEqual(status["allowed_next_phase"], "expert_review_waiting")

    def test_gate_check_full_fixture_passes_and_blocks_understanding_shortfall(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            self.assertTrue(evaluate_gates(task_dir, "full")["all_blocking_gates_passed"])
            cards = self.mechanism_cards()
            for card in cards:
                card.update({"reading_depth": "abstract_metadata_only", "full_text_accessed": False, "source_type": "curated list metadata", "sections_read": ["title and abstract"], "evidence_span_locations": ["curated-list row"]})
            write_jsonl(task_dir / "state/paper_mechanism_cards.jsonl", cards)
            gates = evaluate_gates(task_dir, "full")
            self.assertTrue(gates["gate_4_coverage"]["coverage_expanded"])
            self.assertFalse(gates["gate_2_paper_understanding"]["paper_understanding_complete"])
            self.assertFalse(gates["all_blocking_gates_passed"])

    def test_init_runner_and_dashboard_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "runner topic")
            for relative in ["state/expert_review_round_status.json", "state/expert_review_adjudication.json", "state/targeted_rereview_reports.jsonl", "state/search_routes.jsonl"]:
                self.assertTrue((task_dir / relative).exists())
            (task_dir / "outputs/review.md").write_text("# Review\n\n## Intro\ntext\n", encoding="utf-8")
            (task_dir / "outputs/appendix.md").write_text("# Appendix\n", encoding="utf-8")
            (task_dir / "state/argument_graph.yml").write_text("central_thesis: x\n", encoding="utf-8")
            write_jsonl(task_dir / "state/section_evidence_plans.jsonl", [{"section_id": "S1"}])
            self.assertTrue(freeze_review_round(task_dir, "round-test")["review_freeze"]["frozen_artifacts"]["outputs/review.md"])
            self.assertEqual(dispatch_packets(task_dir, "round-test")["packets"], 5)
            self.assertEqual((task_dir / "state/expert_review_reports.jsonl").read_text(encoding="utf-8"), "")
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", [{"reviewer_id": "domain_expert"}])
            self.assertFalse(collect_status(task_dir)["all_reports_received"])
            html = render_dashboard(task_dir, "short").read_text(encoding="utf-8")
            self.assertIn("gate_7_expert_review", html)
            self.assertIn("A/B full-text deep-read", html)

    def test_lqs_keeps_foundational_roles(self):
        scored = score_paper({"paper_id": "p1", "survey_role": "seminal", "conceptual_centrality": 10, "mechanism_clarity": 8})
        self.assertEqual(scored["lqs_model"], "survey-role")
        self.assertNotEqual(classify_depth(scored, role="section protagonist"), "D")

    def test_clean_main_flow_has_no_legacy_schema_terms(self):
        main_text = "\n".join(path.read_text(encoding="utf-8") for path in [ROOT / "SKILL.md", ROOT / "scripts/gate_check.py"])
        for old in ["paper_" + "cards", "section_" + "cards", "worked_" + "examples", "review_" + "scorecard", "review_" + "depth"]:
            self.assertNotIn(old, main_text)


if __name__ == "__main__":
    unittest.main()
