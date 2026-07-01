import json
import tempfile
import unittest
from pathlib import Path

from scripts.coverage_report import build_coverage
from scripts.gate_check import evaluate_gates
from scripts.init_task import initialize_task
from scripts.patrol import inspect_task
from scripts.render_dashboard import DashboardRenderError, render_dashboard
from scripts.score_lqs import classify_depth, score_paper
from scripts.validate_claims import validate_claim_records


class SurveyAutoResearchScriptsTest(unittest.TestCase):
    def _valid_csur_imitation_plan(self) -> str:
        return (
            "# CSUR Imitation Plan\n\n"
            "## Selected CSUR Exemplars\n"
            "- Data-centric Artificial Intelligence: A Survey, ACM Computing Surveys, 2025, https://dl.acm.org/doi/10.1145/3711118\n"
            "- Machine Learning Systems: A Survey from a Data-Oriented Perspective, ACM Computing Surveys, 2026, https://dl.acm.org/doi/10.1145/3769292\n"
            "- A Survey on Uncertainty Quantification of Large Language Models, ACM Computing Surveys, 2026, https://dl.acm.org/doi/10.1145/3744238\n\n"
            "## Section Skeleton\n"
            "Introduction; survey methodology; related surveys; foundations; benchmark landscape; method taxonomy; design patterns; evaluation; open challenges; conclusion.\n\n"
            "## Abstract Move Sequence\n"
            "Motivation gap -> scope -> taxonomy/framework -> evidence artifacts -> research agenda.\n\n"
            "## Reader Function By Major Section\n"
            "Each major section defines the field object, compares method families, and explains evaluation implications.\n\n"
            "## Internal Notes Excluded From Review Body\n"
            "Do not include workflow logs, draft version labels, state file names, audit language, or scaffold sentences.\n"
        )

    def _write_full_survey_fixture(
        self,
        task_dir: Path,
        *,
        topic: str = "Retrieval augmented generation for autonomous agents",
        review: str | None = None,
        target: str = "full",
        with_verification_log: bool = True,
        related_surveys: str | None = None,
    ) -> None:
        (task_dir / "state").mkdir()
        (task_dir / "outputs").mkdir()
        (task_dir / "logs").mkdir()
        papers = [
            {"paper_id": f"p{i}", "verified": True, "accepted": i < 60}
            for i in range(160)
        ]
        citation_plan = [
            {"paper_id": "p1", "taxonomy_cell": "cell/a", "depth": "A"},
            {"paper_id": "p2", "taxonomy_cell": "cell/a", "depth": "B"},
        ]
        claims = [
            {
                "claim_id": "c1",
                "claim": "A supported claim.",
                "paper_ids": ["p1"],
                "evidence": "Evidence text.",
                "strength": "suggests",
            }
        ]
        default_review = (
            "# Survey\n\n"
            "## Benchmark Landscape\n| benchmark | task | metric |\n| --- | --- | --- |\n| A | B | C |\n\n"
            "## Method Taxonomy\n| method family | design choice |\n| --- | --- |\n| A | B |\n\n"
            "## Method Design Pipeline\nThe design pipeline moves from problem framing to representation, integration, and evaluation.\n\n"
            "## Evaluation Protocol\nMetrics include task success, utility, latency, resource budget, and ablations.\n\n"
            "## Practical Design Guidelines\nGuidelines help readers choose a method family and ablation suite.\n\n"
            "## Critical Analysis\nBenchmark limitations and failure modes show where method families disagree."
        )
        (task_dir / "state/task_spec.md").write_text(
            f"# Task Spec\n\nTopic: {topic}\nTarget: {target}\nOutput mode: markdown\n"
        )
        (task_dir / "state/progress.json").write_text(
            json.dumps({"topic": topic, "target": target})
        )
        (task_dir / "state/papers.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in papers)
        )
        (task_dir / "state/citation_plan.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in citation_plan)
        )
        (task_dir / "state/claims.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in claims)
        )
        (task_dir / "state/taxonomy.md").write_text(
            "# Taxonomy\n\nAxis 1 x Axis 2\n\n## Gap Analysis\nMissing cells reveal opportunities.\n"
        )
        (task_dir / "outputs/review.md").write_text(review or default_review)
        (task_dir / "outputs/evidence_table.csv").write_text(
            "claim_id,paper_id,evidence\nc1,p1,Evidence text.\n"
        )
        (task_dir / "outputs/references.bib").write_text("@article{p1,title={X}}\n")
        (task_dir / "outputs/final_report.md").write_text("status: Complete\n")
        if with_verification_log:
            (task_dir / "logs/verification.jsonl").write_text(
                "".join(
                    json.dumps({"paper_id": f"p{i}", "verified": True, "checks": [{"ok": True}]}) + "\n"
                    for i in range(160)
                )
            )
        else:
            (task_dir / "logs/verification.jsonl").write_text("")
        if target == "csur":
            (task_dir / "state/research_questions.md").write_text(
                "# Research Questions\n\nRQ1. Taxonomy?\nRQ2. Benchmarks?\nRQ3. Methods?\n"
            )
            (task_dir / "state/search_protocol.md").write_text(
                "# Search Protocol\n\n## Databases\nDBLP, arXiv, OpenReview.\n\n## Search Routes\nKeyword queries, venue sweep, citation snowball, and related-survey backward links.\n\n## Inclusion Criteria\nRelevant surveys and methods.\n\n## Exclusion Criteria\nIrrelevant papers.\n\n## Screening Counts\nRaw=200, retained=160.\n"
            )
            (task_dir / "state/related_surveys.md").write_text(
                related_surveys
                or (
                    "# Related Surveys\n\n| survey | organizes around | misses | this review adds |\n"
                    "| --- | --- | --- | --- |\n"
                    + "".join(
                        f"| S{i} | topic | gap | new taxonomy and evidence table |\n"
                        for i in range(8)
                    )
                )
            )
            fact_rows = [
                {
                    "paper_id": f"p{i}",
                    "method_family": "retrieval",
                    "task_family": "agents",
                    "benchmark_or_dataset": "Benchmark",
                    "metrics": ["success"],
                    "mechanism_or_contribution": "retrieval system",
                    "ablations": ["no retrieval"],
                    "limitations": "Limited scope.",
                }
                for i in range(12)
            ]
            (task_dir / "state/paper_facts.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in fact_rows)
            )
            (task_dir / "outputs/synthesis_tables.md").write_text(
                "# Synthesis Tables\n\n| benchmark | protocol | metrics | ablations |\n"
                "| --- | --- | --- | --- |\n| B | P | M | A |\n\n"
                "| method | mechanism | interface | evaluation |\n"
                "| --- | --- | --- | --- |\n| M | R | S | Ops |\n"
            )
            (task_dir / "outputs/figures_plan.md").write_text(
                "# Figures Plan\n\n1. Taxonomy figure.\n2. Pipeline figure.\n3. Benchmark matrix.\n"
            )
            (task_dir / "state/csur_imitation_plan.md").write_text(
                self._valid_csur_imitation_plan()
            )

    def test_initialize_task_creates_state_logs_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(
                base_dir=Path(tmp),
                topic="Autonomous research agents",
                slug="auto-agents",
                output_mode="markdown",
                target="full",
            )

            self.assertEqual(task_dir.name, "auto-agents")
            for rel in [
                "state/task_spec.md",
                "state/progress.json",
                "state/heartbeat.json",
                "state/papers.jsonl",
                "state/lqs_scores.jsonl",
                "state/citation_plan.jsonl",
                "state/claims.jsonl",
                "state/taxonomy.md",
                "state/csur_imitation_plan.md",
                "state/coverage.json",
                "state/directions_tried.json",
                "state/review_rounds.jsonl",
                "state/phase_summaries.jsonl",
                "state/agent_rounds.jsonl",
                "state/merge_decisions.jsonl",
                "state/disagreements.jsonl",
                "state/completion_gates.json",
                "logs/orchestrator.jsonl",
                "logs/heartbeat.jsonl",
                "logs/search.jsonl",
                "logs/extraction.jsonl",
                "logs/synthesis.jsonl",
                "logs/verification.jsonl",
                "outputs/review.md",
                "outputs/evidence_table.csv",
                "outputs/references.bib",
                "outputs/final_report.md",
            ]:
                self.assertTrue((task_dir / rel).exists(), rel)

            progress = json.loads((task_dir / "state/progress.json").read_text())
            self.assertEqual(progress["status"], "running")
            self.assertEqual(progress["phase"], "phase_0_task_initialization")
            self.assertEqual(progress["target"], "full")

    def test_lqs_scoring_and_depth_classification(self):
        paper = {
            "title": "A strong accepted paper",
            "recency_months": 4,
            "citations_per_month": 12,
            "venue_tier": "top",
            "institution_tier": "top_lab",
            "acceptance_status": "accepted",
        }

        scored = score_paper(paper)

        self.assertGreaterEqual(scored["lqs"], 7.0)
        self.assertEqual(scored["lqs_bucket"], "must-cite")
        self.assertEqual(classify_depth(scored, role="section_protagonist"), "A")
        self.assertEqual(classify_depth(scored, role="supporting_context"), "C")

    def test_coverage_counts_ab_refs_per_taxonomy_cell(self):
        citation_plan = [
            {"paper_id": "p1", "taxonomy_cell": "agents/tool-use", "depth": "A"},
            {"paper_id": "p2", "taxonomy_cell": "agents/tool-use", "depth": "B"},
            {"paper_id": "p3", "taxonomy_cell": "agents/planning", "depth": "C"},
        ]

        coverage = build_coverage(citation_plan)

        self.assertEqual(coverage["cells"]["agents/tool-use"]["ab_refs"], 2)
        self.assertTrue(coverage["cells"]["agents/tool-use"]["passes_min_ab_refs"])
        self.assertEqual(coverage["cells"]["agents/planning"]["ab_refs"], 0)
        self.assertFalse(coverage["cells"]["agents/planning"]["passes_min_ab_refs"])

    def test_validate_claim_records_requires_evidence_and_known_papers(self):
        claims = [
            {
                "claim_id": "c1",
                "claim": "Tool-using agents need explicit recovery loops.",
                "paper_ids": ["p1"],
                "evidence": "Section 4 reports recovery-loop failures.",
                "strength": "suggests",
            },
            {
                "claim_id": "c2",
                "claim": "Unsupported claim.",
                "paper_ids": ["missing"],
                "evidence": "",
                "strength": "demonstrates",
            },
        ]
        known = {"p1"}

        result = validate_claim_records(claims, known)

        self.assertFalse(result["valid"])
        self.assertEqual(result["valid_claims"], 1)
        self.assertEqual(result["invalid_claims"], 1)
        self.assertIn("unknown paper_id missing", result["errors"][0])

    def test_evaluate_gates_uses_reference_and_evidence_thresholds(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "state").mkdir()
            (task_dir / "outputs").mkdir()
            papers = [
                {"paper_id": f"p{i}", "verified": True, "accepted": i < 40}
                for i in range(100)
            ]
            citation_plan = [
                {"paper_id": "p1", "taxonomy_cell": "cell/a", "depth": "A"},
                {"paper_id": "p2", "taxonomy_cell": "cell/a", "depth": "B"},
            ]
            claims = [
                {
                    "claim_id": "c1",
                    "claim": "A supported claim.",
                    "paper_ids": ["p1"],
                    "evidence": "Evidence text.",
                    "strength": "suggests",
                }
            ]
            (task_dir / "state/papers.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in papers)
            )
            (task_dir / "state/citation_plan.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in citation_plan)
            )
            (task_dir / "state/claims.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in claims)
            )
            (task_dir / "state/taxonomy.md").write_text(
                "# Taxonomy\n\nAxis 1 x Axis 2\n\n## Gap Analysis\nMissing cells reveal opportunities.\n"
            )
            (task_dir / "outputs/review.md").write_text("Complete review draft.")
            (task_dir / "outputs/evidence_table.csv").write_text(
                "claim_id,paper_id,evidence\nc1,p1,Evidence text.\n"
            )
            (task_dir / "outputs/references.bib").write_text("@article{p1,title={X}}\n")

            gates = evaluate_gates(task_dir, target="short")

            self.assertTrue(gates["gate_1_literature"]["passed"])
            self.assertTrue(gates["gate_2_taxonomy"]["passed"])
            self.assertTrue(gates["gate_3_evidence"]["passed"])
            self.assertTrue(gates["gate_4_output"]["passed"])
            self.assertTrue(gates["all_blocking_gates_passed"])

    def test_full_survey_gate_requires_csur_style_reader_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "state").mkdir()
            (task_dir / "outputs").mkdir()
            papers = [
                {"paper_id": f"p{i}", "verified": True, "accepted": i < 60}
                for i in range(160)
            ]
            citation_plan = [
                {"paper_id": "p1", "taxonomy_cell": "cell/a", "depth": "A"},
                {"paper_id": "p2", "taxonomy_cell": "cell/a", "depth": "B"},
            ]
            claims = [
                {
                    "claim_id": "c1",
                    "claim": "A supported claim.",
                    "paper_ids": ["p1"],
                    "evidence": "Evidence text.",
                    "strength": "suggests",
                }
            ]
            (task_dir / "state/papers.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in papers)
            )
            (task_dir / "state/citation_plan.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in citation_plan)
            )
            (task_dir / "state/claims.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in claims)
            )
            (task_dir / "state/taxonomy.md").write_text(
                "# Taxonomy\n\nAxis 1 x Axis 2\n\n## Gap Analysis\nMissing cells reveal opportunities.\n"
            )
            (task_dir / "outputs/review.md").write_text(
                "# Survey\n\nThis review proposes a high-level framework and discusses broad trends."
            )
            (task_dir / "outputs/evidence_table.csv").write_text(
                "claim_id,paper_id,evidence\nc1,p1,Evidence text.\n"
            )
            (task_dir / "outputs/references.bib").write_text("@article{p1,title={X}}\n")
            (task_dir / "outputs/final_report.md").write_text("status: Complete\n")

            gates = evaluate_gates(task_dir, target="full")

            self.assertFalse(gates["gate_4_output"]["passed"])
            self.assertIn("benchmark landscape", gates["gate_4_output"]["missing_review_artifacts"])
            self.assertFalse(gates["all_blocking_gates_passed"])

            (task_dir / "outputs/review.md").write_text(
                "# Survey\n\n"
                "## Benchmark Landscape\n| benchmark | task | metric |\n| --- | --- | --- |\n| A | B | C |\n\n"
                "## Method Taxonomy\n| method family | design choice |\n| --- | --- |\n| A | B |\n\n"
                "## Method Design Pipeline\nThe design pipeline moves from problem framing to representation, integration, and evaluation.\n\n"
                "## Evaluation Protocol\nMetrics include task success, utility, latency, resource budget, and ablations.\n\n"
                "## Practical Design Guidelines\nGuidelines help readers choose a method family and ablation suite.\n\n"
                "## Critical Analysis\nBenchmark limitations and failure modes show where method families disagree."
            )

            gates = evaluate_gates(task_dir, target="full")

            self.assertTrue(gates["gate_4_output"]["passed"])
            self.assertTrue(gates["all_blocking_gates_passed"])

    def test_full_survey_gate_requires_critical_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            review = (
                "# Survey\n\n"
                "## Benchmark Landscape\n| benchmark | task | metric |\n| --- | --- | --- |\n| A | B | C |\n\n"
                "## Method Taxonomy\n| method family | design choice |\n| --- | --- |\n| A | B |\n\n"
                "## Method Design Pipeline\nThe design pipeline moves from problem framing to representation, integration, and evaluation.\n\n"
                "## Evaluation Protocol\nMetrics include task success, utility, latency, resource budget, and ablations.\n\n"
                "## Practical Design Guidelines\nGuidelines help readers choose a method family and ablation suite."
            )
            self._write_full_survey_fixture(task_dir, review=review)

            gates = evaluate_gates(task_dir, target="full")

            self.assertFalse(gates["gate_4_output"]["passed"])
            self.assertIn("critical analysis", gates["gate_4_output"]["missing_review_artifacts"])

    def test_gate_rejects_unsubstantiated_multi_agent_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir)
            (task_dir / "outputs/final_report.md").write_text(
                "status: Complete\nThis survey was produced by a multi-agent discussion.\n"
            )

            gates = evaluate_gates(task_dir, target="full")

            self.assertFalse(gates["gate_4_output"]["passed"])
            self.assertIn("unsubstantiated multi-agent claim", gates["gate_4_output"]["missing_review_artifacts"])

            (task_dir / "state/agent_rounds.jsonl").write_text(
                json.dumps({"agent": "searcher", "round": 1, "output": "candidate recall"}) + "\n"
            )
            (task_dir / "state/merge_decisions.jsonl").write_text(
                json.dumps({"round": 1, "decision": "merged searcher candidates into taxonomy"}) + "\n"
            )

            gates = evaluate_gates(task_dir, target="full")

            self.assertTrue(gates["gate_4_output"]["passed"])

    def test_full_survey_gate_rejects_generic_process_leakage_framing(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            review = (
                "# Survey\n\n"
                "This survey is not a question-answering survey; it is a retrieval systems review after scope correction.\n\n"
                "## Benchmark Landscape\n| benchmark | task | metric |\n| --- | --- | --- |\n| A | B | C |\n\n"
                "## Method Taxonomy\n| method family | design choice |\n| --- | --- |\n| A | B |\n\n"
                "## Method Design Pipeline\nThe design pipeline moves from problem framing to representation, integration, and evaluation.\n\n"
                "## Evaluation Protocol\nMetrics include task success, utility, latency, resource budget, and ablations.\n\n"
                "## Practical Design Guidelines\nGuidelines help readers choose a method family and ablation suite."
            )
            self._write_full_survey_fixture(task_dir, review=review)

            gates = evaluate_gates(task_dir, target="full")

            self.assertFalse(gates["gate_4_output"]["passed"])
            self.assertIn("process-leakage framing", gates["gate_4_output"]["missing_review_artifacts"])

    def test_full_survey_gate_rejects_scaffold_leakage_framing(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            review = (
                "# Survey\n\n"
                "## Abstract\n"
                "Navigation 暴露 spatial scope 与 stale map；EQA 暴露 evidence provenance 与 grounded-vs-guesser confound；"
                "manipulation/VLA 暴露 object state、task phase、occlusion 与 latency。"
                "好的方法和基准都可以放回 Memory Contract：它们承诺哪些字段、如何读写、如何维护、如何控制行动、如何被实验验证。\n\n"
                "## Benchmark Landscape\n| benchmark | task | metric |\n| --- | --- | --- |\n| A | B | C |\n\n"
                "## Method Taxonomy\n| method family | design choice |\n| --- | --- |\n| A | B |\n\n"
                "## Method Design Pipeline\nThe design pipeline moves from problem framing to representation, integration, and evaluation.\n\n"
                "## Evaluation Protocol\nMetrics include task success, utility, latency, resource budget, and ablations.\n\n"
                "## Practical Design Guidelines\nGuidelines help readers choose a method family and ablation suite.\n\n"
                "## Critical Analysis\nBenchmark limitations and failure modes show where method families disagree."
            )
            self._write_full_survey_fixture(task_dir, review=review)

            gates = evaluate_gates(task_dir, target="full")

            self.assertFalse(gates["gate_4_output"]["passed"])
            self.assertIn("scaffold-leakage framing", gates["gate_4_output"]["missing_review_artifacts"])

    def test_full_survey_gate_rejects_draft_metadata_and_internal_state_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            review = (
                "# Survey\n\n"
                "Long survey draft v11 / CSUR-style redo.\n\n"
                "The evidence layer is stored in papers.jsonl, citation_plan.jsonl, claims.jsonl, and paper_facts.jsonl. "
                "If used for formal submission, more extraction would be needed.\n\n"
                "## Benchmark Landscape\n| benchmark | task | metric |\n| --- | --- | --- |\n| A | B | C |\n\n"
                "## Method Taxonomy\n| method family | design choice |\n| --- | --- |\n| A | B |\n\n"
                "## Method Design Pipeline\nThe design pipeline moves from problem framing to representation, integration, and evaluation.\n\n"
                "## Evaluation Protocol\nMetrics include task success, utility, latency, resource budget, and ablations.\n\n"
                "## Practical Design Guidelines\nGuidelines help readers choose a method family and ablation suite.\n\n"
                "## Critical Analysis\nBenchmark limitations and failure modes show where method families disagree."
            )
            self._write_full_survey_fixture(task_dir, review=review)

            gates = evaluate_gates(task_dir, target="full")

            self.assertFalse(gates["gate_4_output"]["passed"])
            self.assertIn("scaffold-leakage framing", gates["gate_4_output"]["missing_review_artifacts"])

    def test_full_survey_gate_output_stays_lean_without_object_alignment_classifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(
                task_dir,
                topic="World models for autonomous systems",
            )

            gates = evaluate_gates(task_dir, target="full")

            self.assertNotIn("object_alignment", gates["gate_4_output"])
            self.assertNotIn("object-alignment", gates["gate_4_output"]["missing_review_artifacts"])

    def test_full_survey_gate_allows_task_mentions_inside_method_first_survey(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            review = (
                "# World Models Survey\n\n"
                "## Benchmark Landscape\n| benchmark | task | metric |\n| --- | --- | --- |\n"
                "| NavBench | navigation | success |\n"
                "| ManipBench | manipulation | success |\n\n"
                "## Method Taxonomy\n| method family | design choice |\n| --- | --- |\n| Latent dynamics | state prediction |\n\n"
                "## Method Design Pipeline\nThe design pipeline moves from state abstraction to prediction, integration, and evaluation.\n\n"
                "## Evaluation Protocol\nMetrics include task success, model error, intervention tests, and ablations.\n\n"
                "## Practical Design Guidelines\nGuidelines help readers choose a model family and benchmark suite.\n\n"
                "## Critical Analysis\nBenchmark limitations and failure modes show where model families disagree."
            )
            self._write_full_survey_fixture(
                task_dir,
                topic="World models for embodied agents",
                review=review,
            )

            gates = evaluate_gates(task_dir, target="full")

            self.assertTrue(gates["gate_4_output"]["passed"])

    def test_full_survey_gate_allows_formal_cross_task_synthesis(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            review = (
                "# Embodied Systems Survey\n\n"
                "Across navigation, embodied question answering, and manipulation, benchmark suites evaluate different validity conditions for system state. "
                "Spatial tasks test whether stored observations remain usable for localization and planning; question answering tasks test whether responses can be traced to grounded evidence; manipulation tasks test whether object state and task progress can be recovered under occlusion and latency constraints.\n\n"
                "## Benchmark Landscape\n| benchmark | task | metric |\n| --- | --- | --- |\n| A | B | C |\n\n"
                "## Method Taxonomy\n| method family | design choice |\n| --- | --- |\n| A | B |\n\n"
                "## Method Design Pipeline\nThe design pipeline moves from problem framing to representation, integration, and evaluation.\n\n"
                "## Evaluation Protocol\nMetrics include task success, utility, latency, resource budget, and ablations.\n\n"
                "## Practical Design Guidelines\nGuidelines help readers choose a method family and ablation suite.\n\n"
                "## Critical Analysis\nBenchmark limitations and failure modes show where method families disagree."
            )
            self._write_full_survey_fixture(task_dir, review=review)

            gates = evaluate_gates(task_dir, target="full")

            self.assertTrue(gates["gate_4_output"]["passed"])

    def test_full_survey_gate_requires_periodic_citation_verification_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir, with_verification_log=False)

            gates = evaluate_gates(task_dir, target="full")

            self.assertFalse(gates["gate_1_literature"]["passed"])
            self.assertFalse(gates["gate_1_literature"]["citation_verification_cadence"]["passed"])
            self.assertFalse(gates["all_blocking_gates_passed"])

    def test_csur_gate_requires_protocol_related_surveys_and_paper_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "state").mkdir()
            (task_dir / "outputs").mkdir()
            papers = [
                {"paper_id": f"p{i}", "verified": True, "accepted": i < 80}
                for i in range(160)
            ]
            citation_plan = [
                {"paper_id": f"p{i}", "taxonomy_cell": "cell/a", "depth": "A" if i < 8 else "B"}
                for i in range(12)
            ]
            claims = [
                {
                    "claim_id": "c1",
                    "claim": "A supported synthesis claim.",
                    "paper_ids": ["p1", "p2"],
                    "evidence": "Evidence text.",
                    "strength": "suggests",
                }
            ]
            review = (
                "# Survey\n\n"
                "## Benchmark Landscape\n| benchmark | task | metric |\n| --- | --- | --- |\n| A | B | C |\n\n"
                "## Method Taxonomy\n| method family | design choice |\n| --- | --- |\n| A | B |\n\n"
                "## Method Design Pipeline\nThe design pipeline moves from problem framing to representation, integration, and evaluation.\n\n"
                "## Evaluation Protocol\nMetrics include task success, utility, latency, resource budget, and ablations.\n\n"
                "## Practical Design Guidelines\nGuidelines help readers choose a method family and ablation suite.\n\n"
                "## Critical Analysis\nBenchmark limitations and failure modes show where method families disagree."
            )
            (task_dir / "state/papers.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in papers)
            )
            (task_dir / "state/citation_plan.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in citation_plan)
            )
            (task_dir / "state/claims.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in claims)
            )
            (task_dir / "state/taxonomy.md").write_text(
                "# Taxonomy\n\nAxis 1 x Axis 2\n\n## Gap Analysis\nMissing cells reveal opportunities.\n"
            )
            (task_dir / "outputs/review.md").write_text(review)
            (task_dir / "outputs/evidence_table.csv").write_text(
                "claim_id,paper_id,evidence\nc1,p1,Evidence text.\n"
            )
            (task_dir / "outputs/references.bib").write_text("@article{p1,title={X}}\n")
            (task_dir / "outputs/final_report.md").write_text("status: Complete\n")

            gates = evaluate_gates(task_dir, target="csur")

            self.assertFalse(gates["gate_6_csur_readiness"]["passed"])
            self.assertIn("state/research_questions.md", gates["gate_6_csur_readiness"]["missing_artifacts"])
            self.assertIn("state/search_protocol.md", gates["gate_6_csur_readiness"]["missing_artifacts"])
            self.assertIn("state/related_surveys.md", gates["gate_6_csur_readiness"]["missing_artifacts"])
            self.assertIn("state/paper_facts.jsonl", gates["gate_6_csur_readiness"]["missing_artifacts"])
            self.assertFalse(gates["all_blocking_gates_passed"])

            (task_dir / "state/research_questions.md").write_text(
                "# Research Questions\n\nRQ1. Taxonomy?\nRQ2. Benchmarks?\nRQ3. Methods?\n"
            )
            (task_dir / "state/search_protocol.md").write_text(
                "# Search Protocol\n\n## Databases\nDBLP, arXiv, OpenReview.\n\n## Search Routes\nKeyword queries, venue sweep, citation snowball, and related-survey backward links.\n\n## Inclusion Criteria\nRelevant surveys and methods.\n\n## Exclusion Criteria\nIrrelevant papers.\n\n## Screening Counts\nRaw=200, retained=160.\n"
            )
            (task_dir / "state/related_surveys.md").write_text(
                "# Related Surveys\n\n| survey | organizes around | misses | this review adds |\n"
                "| --- | --- | --- | --- |\n"
                + "".join(f"| S{i} | topic | gap | new taxonomy and evidence table |\n" for i in range(8))
            )
            fact_rows = []
            for i in range(12):
                fact_rows.append(
                    {
                        "paper_id": f"p{i}",
                        "method_family": "retrieval",
                        "task_family": "agents",
                        "benchmark_or_dataset": "Benchmark",
                        "metrics": ["success"],
                        "mechanism_or_contribution": "retrieval system",
                        "ablations": ["no retrieval"],
                        "limitations": "Limited scope.",
                    }
                )
            (task_dir / "state/paper_facts.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in fact_rows)
            )
            (task_dir / "outputs/synthesis_tables.md").write_text(
                "# Synthesis Tables\n\n| benchmark | protocol | metrics | ablations |\n"
                "| --- | --- | --- | --- |\n| B | P | M | A |\n\n"
                "| method | mechanism | interface | evaluation |\n"
                "| --- | --- | --- | --- |\n| M | R | S | Ops |\n"
            )
            (task_dir / "outputs/figures_plan.md").write_text(
                "# Figures Plan\n\n1. Taxonomy figure.\n2. Pipeline figure.\n3. Benchmark matrix.\n"
            )
            (task_dir / "state/csur_imitation_plan.md").write_text(
                self._valid_csur_imitation_plan()
            )

            gates = evaluate_gates(task_dir, target="csur")

            self.assertTrue(gates["gate_6_csur_readiness"]["passed"])
            self.assertTrue(gates["all_blocking_gates_passed"])

    def test_csur_gate_requires_imitation_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir, target="csur")
            (task_dir / "state/csur_imitation_plan.md").unlink()

            gates = evaluate_gates(task_dir, target="csur")

            self.assertFalse(gates["gate_6_csur_readiness"]["passed"])
            self.assertIn("state/csur_imitation_plan.md", gates["gate_6_csur_readiness"]["missing_artifacts"])

    def test_csur_gate_rejects_non_acm_or_stale_imitation_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir, target="csur")
            (task_dir / "state/csur_imitation_plan.md").write_text(
                "# CSUR Imitation Plan\n\n"
                "## Selected CSUR Exemplars\n"
                "- Explainable Reinforcement Learning: A Survey, arXiv only, 2020, https://arxiv.org/abs/2005.06247\n"
                "- A submitted survey under review, 2026, https://example.com/submitted\n\n"
                "## Section Skeleton\nIntroduction; taxonomy; methods.\n\n"
                "## Abstract Move Sequence\nGap -> scope -> taxonomy.\n\n"
                "## Reader Function By Major Section\nSections compare methods.\n\n"
                "## Internal Notes Excluded From Review Body\nNo logs.\n"
            )

            gates = evaluate_gates(task_dir, target="csur")

            self.assertFalse(gates["gate_6_csur_readiness"]["passed"])
            self.assertIn("csur_imitation_plan", gates["gate_6_csur_readiness"]["failed_checks"])

    def test_csur_gate_rejects_related_surveys_with_only_recency_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            related_surveys = (
                "# Related Surveys\n\n| survey | organizes around | misses | this review adds |\n"
                "| --- | --- | --- | --- |\n"
                + "".join(
                    f"| S{i} | prior work | older papers | more recent and broader |\n"
                    for i in range(8)
                )
            )
            self._write_full_survey_fixture(
                task_dir,
                target="csur",
                related_surveys=related_surveys,
            )

            gates = evaluate_gates(task_dir, target="csur")

            self.assertFalse(gates["gate_6_csur_readiness"]["passed"])
            self.assertIn("related_survey_differentiation", gates["gate_6_csur_readiness"]["failed_checks"])

    def test_csur_gate_rejects_related_surveys_with_unaccepted_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            related_surveys = (
                "# Related Surveys\n\n| survey | organizes around | misses | this review adds |\n"
                "| --- | --- | --- | --- |\n"
                "| S0 | topic | gap | new taxonomy and evidence table |\n"
                "| S1 | topic | gap | new taxonomy and evidence table |\n"
                "| S2 | topic | gap | new taxonomy and evidence table |\n"
                "| S3 | topic | gap | new taxonomy and evidence table |\n"
                "| S4 | topic | gap | new taxonomy and evidence table |\n"
                "| S5 | topic | gap | new taxonomy and evidence table |\n"
                "| S6 | topic | gap | new taxonomy and evidence table |\n"
                "| S7 | arXiv only under review survey | gap | submitted but broader |\n"
            )
            self._write_full_survey_fixture(
                task_dir,
                target="csur",
                related_surveys=related_surveys,
            )

            gates = evaluate_gates(task_dir, target="csur")

            self.assertFalse(gates["gate_6_csur_readiness"]["passed"])
            self.assertIn("related_survey_status", gates["gate_6_csur_readiness"]["failed_checks"])

    def test_skill_sources_do_not_retain_embodied_memory_specific_gate_terms(self):
        skill_dir = Path("/Users/sunyanpeng/.codex/skills/survey-autoresearch")
        checked_files = [
            skill_dir / "SKILL.md",
            skill_dir / "scripts/gate_check.py",
            skill_dir / "references/autoresearch_landscape.md",
            skill_dir / "references/completion_gates.md",
            skill_dir / "references/csur_exemplar_patterns.md",
            skill_dir / "references/evidence_verification.md",
            skill_dir / "references/review_writing_patterns.md",
            skill_dir / "references/taxonomy_and_structure.md",
        ]
        forbidden = [
            "memory_mechanism",
            "navigation",
            "manipulation",
            "EQA",
            "VLA",
            "embodied memory",
            "memory-specific",
            "object_alignment",
            "object-alignment",
            "gpt-image",
            "GPT Image",
        ]
        hits = []
        for path in checked_files:
            text = path.read_text(encoding="utf-8")
            for term in forbidden:
                if term in text:
                    hits.append(f"{path.name}:{term}")

        self.assertEqual([], hits)

    def test_autoresearch_landscape_distinguishes_reuse_from_blind_copying(self):
        path = Path("/Users/sunyanpeng/.codex/skills/survey-autoresearch/references/autoresearch_landscape.md")
        text = path.read_text(encoding="utf-8")

        for required in [
            "External AutoResearch projects are design evidence, not authority.",
            "Reuse",
            "Do not copy",
            "AutoSurvey",
            "STORM",
            "PaperQA2",
            "SurveyGen",
            "Agent Laboratory",
            "The AI Scientist",
            "state/agent_rounds.jsonl",
            "state/merge_decisions.jsonl",
        ]:
            self.assertIn(required, text)

    def test_patrol_detects_stale_task_from_old_last_seen(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(
                base_dir=Path(tmp),
                topic="Autonomous research agents",
                slug="stale",
                output_mode="markdown",
                target="short",
            )
            progress_path = task_dir / "state/progress.json"
            progress = json.loads(progress_path.read_text())
            progress["last_seen"] = "2026-01-01T00:00:00+00:00"
            progress_path.write_text(json.dumps(progress))

            result = inspect_task(
                task_dir,
                now_iso="2026-01-01T04:30:00+00:00",
                stale_after_minutes=120,
            )

            self.assertTrue(result["stale"])
            self.assertEqual(result["recommended_action"], "nudge_or_restart")
            self.assertGreaterEqual(result["minutes_since_seen"], 270)

    def test_render_dashboard_creates_overview_and_phase_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(
                base_dir=Path(tmp),
                topic="Autonomous <Research> & Agents",
                slug="dashboard",
                output_mode="markdown",
                target="short",
            )
            progress_path = task_dir / "state/progress.json"
            progress = json.loads(progress_path.read_text())
            progress["phase"] = "phase_2_recall"
            progress["iteration"] = 3
            progress["stale_count"] = 1
            progress["next_action"] = "Run DBLP <venue> sweep"
            progress_path.write_text(json.dumps(progress))
            (task_dir / "state/claims.jsonl").write_text(
                json.dumps(
                    {
                        "claim_id": "c1",
                        "claim": "Recovery loops improve reliability <when tools fail>.",
                        "paper_ids": ["p1"],
                        "evidence": "Evidence with <unsafe> text.",
                        "taxonomy_cell": "agents/recovery",
                        "confidence": "high",
                    }
                )
                + "\n"
            )
            (task_dir / "state/review_rounds.jsonl").write_text(
                json.dumps(
                    {
                        "round": 1,
                        "summary": "Reviewer says taxonomy is promising.",
                        "weaknesses": [{"severity": "major", "status": "open", "text": "Need more recent work."}],
                    }
                )
                + "\n"
            )
            (task_dir / "logs/orchestrator.jsonl").write_text(
                json.dumps(
                    {
                        "ts": "2026-01-01T00:00:00+00:00",
                        "source": "orchestrator",
                        "level": "decision",
                        "event": "pivot",
                        "detail": "Switch to citation snowball <now>.",
                    }
                )
                + "\n"
            )

            result = render_dashboard(task_dir)

            self.assertTrue((task_dir / "dashboard/index.html").exists())
            self.assertEqual(len(result["phase_pages"]), 11)
            for page in result["phase_pages"]:
                self.assertTrue(Path(page).exists(), page)
            overview = (task_dir / "dashboard/index.html").read_text()
            self.assertIn("Autonomous &lt;Research&gt; &amp; Agents", overview)
            self.assertIn("phase_2_recall", overview)
            self.assertIn("Run DBLP &lt;venue&gt; sweep", overview)
            self.assertIn("Recovery loops improve reliability &lt;when tools fail&gt;.", overview)
            self.assertIn("Need more recent work.", overview)
            self.assertIn("../state/claims.jsonl", overview)
            self.assertNotIn("<unsafe>", overview)
            phase_page = (task_dir / "dashboard/phases/phase_02_recall.html").read_text()
            self.assertIn("../../state/claims.jsonl", phase_page)

    def test_render_dashboard_handles_missing_optional_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(
                base_dir=Path(tmp),
                topic="Sparse task",
                slug="sparse",
                output_mode="markdown",
                target="short",
            )
            (task_dir / "state/review_rounds.jsonl").unlink()
            (task_dir / "state/claims.jsonl").unlink()

            render_dashboard(task_dir)

            overview = (task_dir / "dashboard/index.html").read_text()
            self.assertIn("not available yet", overview)

    def test_render_dashboard_fails_on_malformed_required_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(
                base_dir=Path(tmp),
                topic="Broken task",
                slug="broken",
                output_mode="markdown",
                target="short",
            )
            (task_dir / "state/progress.json").write_text("{not-json")

            with self.assertRaises(DashboardRenderError) as raised:
                render_dashboard(task_dir)

            self.assertIn("Malformed JSON", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
