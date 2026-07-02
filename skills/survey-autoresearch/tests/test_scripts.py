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
from scripts.validate_synthesis_dossiers import validate_synthesis_dossiers
from scripts.verify_sources import validate_sources


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
                        "section_or_page": "Section 4, Table 2",
                        "evidence_summary": "The paper compares the method with a no-memory baseline.",
                        "supports": "direct",
                        "strength": "shows",
                    }
                ],
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
            "The table below is introduced as an article-facing comparison of mechanism and evidence.\n\n"
            "| Family | Mechanism | Evidence | Limitation |\n"
            "| --- | --- | --- | --- |\n"
            "| Retrieval | writes and reads structured evidence | no-memory comparison | perception confounder |\n\n"
            "The table shows that method labels are insufficient. A reader should compare what evidence is written, how it is retrieved, which baseline is used, and what limitation remains.\n\n"
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
        write_jsonl(state / "claim_evidence_spans.jsonl", self.claims())
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
        status = validate_paper_understanding(shallow, [{"paper_id": "p001", "depth": "A"}])
        self.assertFalse(status["valid"])
        self.assertIn("invalid_paper_understanding", status["errors"])
        status = validate_paper_understanding(self.mechanism_cards(1), [{"paper_id": "p001", "depth": "A"}])
        self.assertTrue(status["valid"], status)

    def test_paper_understanding_rejects_generic_relation_and_missing_experiment_details(self):
        card = self.mechanism_cards(1)[0]
        card["relation_to_prior_work"] = "This is related to prior work."
        card["experimental_setup"] = {"metrics": ["success"]}
        status = validate_paper_understanding([card], [{"paper_id": "p001", "depth": "A"}])
        self.assertFalse(status["valid"])
        self.assertIn("generic_relation_to_prior_work", status["invalid_cards"]["p001"])
        self.assertIn("missing_baselines", status["invalid_cards"]["p001"])
        self.assertIn("missing_ablations", status["invalid_cards"]["p001"])

    def test_claim_evidence_blocks_missing_span_and_overclaim(self):
        too_strong = self.claims()
        too_strong[0]["strength"] = "demonstrates"
        status = validate_claim_evidence(too_strong, self.mechanism_cards(1))
        self.assertFalse(status["valid"])
        self.assertIn("claim_strength_exceeds_evidence:p001", status["invalid_claims"]["c1"])
        status = validate_claim_evidence(self.claims(), self.mechanism_cards(1))
        self.assertTrue(status["valid"], status)

    def test_coverage_gate_enforces_full_survey_breadth(self):
        status = build_coverage(self.papers(20, 1), self.citation_plan(a=2, b=4, c=14), "full")
        self.assertFalse(status["valid"])
        self.assertIn("verified_refs", status["missing"])
        status = build_coverage(self.papers(), self.citation_plan(), "full")
        self.assertTrue(status["valid"], status)

    def test_argument_graph_requires_section_mapping(self):
        graph = self.argument_graph()
        status = validate_argument_graph(graph, self.article_plan())
        self.assertTrue(status["valid"], status)
        graph["argument_nodes"]["A2"].pop("implication")
        status = validate_argument_graph(graph, self.article_plan())
        self.assertFalse(status["valid"])

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

    def test_init_task_uses_new_state_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "test topic", target="full")
            self.assertTrue((task_dir / "state/survey_type_plan.yml").exists())
            self.assertTrue((task_dir / "state/scenario_definitions.yml").exists())
            self.assertTrue((task_dir / "state/section_evidence_plans.jsonl").exists())
            self.assertTrue((task_dir / "state/paper_mechanism_cards.jsonl").exists())
            self.assertFalse((task_dir / "state/paper_cards.jsonl").exists())
            gates = json.loads((task_dir / "state/completion_gates.json").read_text())
            self.assertIn("gate_6_article_quality", gates)
            self.assertNotIn("gate_7_review_depth", gates)

    def test_dashboard_renders_new_gate_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dashboard topic", target="short")
            path = render_dashboard(task_dir, "short")
            html = path.read_text(encoding="utf-8")
            self.assertIn("gate_1_source_identity", html)
            self.assertIn("gate_6_article_quality", html)

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
