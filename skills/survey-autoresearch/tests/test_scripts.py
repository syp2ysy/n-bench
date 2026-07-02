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
                    "implementation_details": {"model": "encoder", "memory": "structured store", "controller": "planner"},
                    "experimental_setup": {"metrics": ["success"], "baselines": ["no memory"], "ablations": ["no retrieval"]},
                    "main_results": [
                        {
                            "result": "The method improves the diagnostic benchmark over the no-memory baseline.",
                            "evidence_span": "Section 4, Table 2.",
                            "claim_strength": "shows",
                        }
                    ],
                    "limitations_and_confounders": ["perception and controller strength may confound aggregate success"],
                    "relation_to_prior_work": "Extends prior context-only systems with explicit evidence use.",
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

    def argument_graph(self) -> dict:
        return {
            "central_thesis": "Memory should be evaluated as an evidence-to-action interface.",
            "field_shift": "Agents move from short tasks to long-horizon deployment.",
            "gap_in_existing_surveys": "Task-first views split method, benchmark, and evidence reasoning.",
            "argument_nodes": {
                "A1": {
                    "claim": "Existing views fragment mechanisms.",
                    "evidence": ["related_survey_matrix"],
                    "implication": "Use an interface-centered lens.",
                    "section": "Introduction",
                    "leads_to": ["A2"],
                },
                "A2": {
                    "claim": "Method families differ by mechanism and evidence.",
                    "evidence": ["method_family_dossiers"],
                    "implication": "Compare methods by pipeline and result support.",
                    "section": "Method Families",
                    "leads_to": ["A3"],
                },
                "A3": {
                    "claim": "Benchmarks operationalize but do not automatically prove claims.",
                    "evidence": ["benchmark_dossiers"],
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
            (directory / "dossier.md").write_text("# Dossier\n\nMechanism and evidence comparison.\n", encoding="utf-8")

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

    def test_init_task_uses_new_state_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "test topic", target="full")
            self.assertTrue((task_dir / "state/survey_type_plan.yml").exists())
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
