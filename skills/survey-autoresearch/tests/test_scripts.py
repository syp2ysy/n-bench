import json
import subprocess
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
from scripts.validate_csur_style_patterns import validate_csur_style_patterns
from scripts.validate_csur_paragraph_patterns import validate_csur_paragraph_patterns
from scripts.validate_node_cards import validate_node_cards
from scripts.validate_paper_cards import validate_paper_cards
from scripts.validate_section_cards import validate_section_cards
from scripts.validate_review_depth import validate_review_depth
from scripts.validate_worked_examples import validate_worked_examples
from scripts.validate_benchmark_landscape import validate_benchmark_landscape
from scripts.validate_method_taxonomy import validate_method_taxonomy
from scripts.validate_node_paper_matrix import validate_node_paper_matrix
from scripts.validate_newcomer_tutorial import validate_newcomer_tutorial
from scripts.validate_card_specificity import validate_card_specificity
from scripts.validate_review_absorption import validate_review_absorption
from scripts.review_scorecard import score_review
from scripts.derive_paper_facts import derive_paper_facts
from scripts.validate_case_study_prose import validate_case_study_prose
from scripts.validate_table_interpretation import validate_table_interpretation
from scripts.validate_publication_prose import validate_publication_prose
from scripts.validate_semantic_repetition import validate_semantic_repetition
from scripts.validate_global_coherence import validate_global_coherence
from scripts.validate_topic_diagnosis import validate_topic_diagnosis
from scripts.validate_argument_graph import validate_argument_graph
from scripts.validate_paper_mechanism_cards import validate_paper_mechanism_cards
from scripts.validate_claim_evidence_spans import validate_claim_evidence_spans
from scripts.validate_citation_identity import validate_citation_identity
from scripts.validate_paper_summary_consistency import validate_paper_summary_consistency
from scripts.validate_article_plan_alignment import validate_article_plan_alignment
from scripts.derive_paper_cards_from_mechanism_cards import derive_paper_cards
from scripts.derive_evidence_ladder import derive_evidence_ladder


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

    def _valid_csur_style_patterns(self) -> str:
        return (
            "exemplar_evidence:\n"
            "  - doi: 10.1145/3711118\n"
            "    exemplar: Data-centric Artificial Intelligence: A Survey\n"
            "    abstract_moves_observed:\n"
            "      - move: field importance\n"
            "        evidence_note: Abstract frames data as central to the AI lifecycle.\n"
            "    introduction_moves_observed:\n"
            "      - move: lifecycle scope\n"
            "        evidence_note: Introduction motivates lifecycle organization and survey scope.\n"
            "    section_rhetoric_observed:\n"
            "      - section_type: lifecycle stage\n"
            "        opening_move: opens with the problem solved by the stage\n"
            "        body_move: compares method and resource families\n"
            "        closing_move: closes with limitations and directions\n"
            "    table_functions_observed:\n"
            "      - compares resources by lifecycle role\n"
            "    conclusion_moves_observed:\n"
            "      - synthesizes findings into future directions\n"
            "  - doi: 10.1145/3769292\n"
            "    exemplar: Machine Learning Systems: A Survey from a Data-Oriented Perspective\n"
            "    abstract_moves_observed:\n"
            "      - move: system lens\n"
            "        evidence_note: Abstract uses a data-oriented lens to reorganize ML systems.\n"
            "    introduction_moves_observed:\n"
            "      - move: why existing views are incomplete\n"
            "        evidence_note: Introduction motivates why a systems lens changes organization.\n"
            "    section_rhetoric_observed:\n"
            "      - section_type: system lens\n"
            "        opening_move: defines the lens before listing systems\n"
            "        body_move: compares components through the lens\n"
            "        closing_move: derives design and evaluation implications\n"
            "    table_functions_observed:\n"
            "      - compares system components and design concerns\n"
            "    conclusion_moves_observed:\n"
            "      - returns to research agenda\n"
            "abstract_moves:\n"
            "  - field_importance\n"
            "  - fragmentation_or_gap\n"
            "  - organizing_framework\n"
            "  - evidence_artifacts\n"
            "  - agenda\n"
            "introduction_moves:\n"
            "  - broad_problem\n"
            "  - why_existing_views_fail\n"
            "  - survey_object_definition\n"
            "  - contributions\n"
            "  - roadmap\n"
            "section_patterns:\n"
            "  system_model:\n"
            "    structure: 总-分-总\n"
            "    opening: define the system object and tension\n"
            "    body: node-by-node explanation with representative systems\n"
            "    closing: design implication and evaluation consequence\n"
            "table_functions:\n"
            "  - compare mechanism, interface, evidence, and limitation\n"
            "paragraph_patterns:\n"
            "  - claim -> contrast -> evidence -> implication\n"
            "  - framework element -> representative systems -> failure mode -> design lesson\n"
            "forbidden_surface_forms:\n"
            "  - Paper A proposes\n"
            "  - This section surveys\n"
        )

    def _valid_csur_paragraph_patterns(self) -> str:
        names = [
            "introduction_paragraph",
            "tutorial_definition_paragraph",
            "taxonomy_opening_paragraph",
            "method_comparison_paragraph",
            "benchmark_paragraph",
            "limitation_paragraph",
            "open_challenge_paragraph",
            "conclusion_agenda_paragraph",
        ]
        return "\n".join(
            f"{name}:\n"
            "  when_to_use: Use when drafting the corresponding survey paragraph.\n"
            "  paragraph_moves:\n"
            "    - define the reader question\n"
            "    - compare mechanisms or evidence\n"
            "    - close with design implication\n"
            "  evidence_from_exemplar: Observed in official ACM Computing Surveys rhetoric notes.\n"
            "  forbidden_shortcut: Do not list papers without mechanism explanation.\n"
            for name in names
        )

    def _valid_paper_cards(self) -> list[dict]:
        return [
            {
                "paper_id": "p1",
                "title": "Foundational System Paper",
                "survey_role": "foundational",
                "problem": "Defines why a system needs explicit state across interactions.",
                "method_summary": "Introduces a structured memory layer used by planning.",
                "system_node": "state capture",
                "mechanism_or_contribution": "Records interaction state and makes it available to a downstream controller.",
                "representation": "structured records",
                "inputs": ["observation", "action history"],
                "outputs": ["retrieved state", "planner constraint"],
                "write_policy": "append important events",
                "read_policy": "task-conditioned retrieval",
                "update_or_consolidation": "summarize repeated episodes",
                "controller_interface": "planner reads retrieved state before action selection",
                "evaluation_tasks": ["planning"],
                "metrics": ["task success"],
                "baselines": ["no memory"],
                "ablations": ["no retrieval"],
                "failure_modes": ["stale state"],
                "limitations": ["limited dynamic updates"],
                "what_it_teaches_the_survey": "A memory claim becomes meaningful only when stored records change a later decision.",
                "evidence_spans": ["Section 4 reports no-memory and no-retrieval ablations."],
            },
            {
                "paper_id": "p2",
                "title": "Benchmark System Paper",
                "survey_role": "benchmark",
                "problem": "Separates memory quality from downstream task success.",
                "method_summary": "Introduces diagnostic tasks for record validity and retrieval failures.",
                "system_node": "evaluation",
                "mechanism_or_contribution": "Benchmarks wrong, stale, and oracle memory conditions.",
                "representation": "diagnostic records",
                "inputs": ["stored records", "queries"],
                "outputs": ["diagnostic score"],
                "write_policy": "controlled benchmark injection",
                "read_policy": "oracle, wrong, and stale retrieval conditions",
                "update_or_consolidation": "not applicable; benchmark manipulation",
                "controller_interface": "evaluation harness controls memory availability",
                "evaluation_tasks": ["diagnostic evaluation"],
                "metrics": ["accuracy", "failure recovery"],
                "baselines": ["oracle memory", "wrong memory"],
                "ablations": ["stale memory injection"],
                "failure_modes": ["false recall"],
                "limitations": ["synthetic benchmark scope"],
                "what_it_teaches_the_survey": "Strong evaluation requires perturbing memory contents, not only comparing final success.",
                "evidence_spans": ["Table 2 defines oracle, wrong, and stale-memory settings."],
            },
        ]

    def _valid_node_cards(self) -> list[dict]:
        return [
            {
                "node": "state capture",
                "role_in_system": "Converts interaction history into records that later modules can inspect.",
                "why_it_matters": "Without typed records, later retrieval and planning cannot distinguish evidence from generic context.",
                "inputs": ["observation", "action", "time"],
                "outputs": ["typed record", "provenance"],
                "main_design_families": ["event log", "structured record"],
                "representative_papers": ["p1", "p2"],
                "failure_modes": ["missing provenance"],
                "evaluation_signals": ["no-memory ablation"],
                "open_questions": ["how much raw context should be retained"],
            },
            {
                "node": "evaluation",
                "role_in_system": "Tests whether memory changes behavior for the right reason.",
                "why_it_matters": "Task success alone can hide perception, policy, or language-prior confounds.",
                "inputs": ["memory condition", "task protocol"],
                "outputs": ["causal evidence", "failure diagnosis"],
                "main_design_families": ["oracle test", "wrong-memory injection"],
                "representative_papers": ["p1", "p2"],
                "failure_modes": ["unattributed success gain"],
                "evaluation_signals": ["oracle/wrong/stale memory tests"],
                "open_questions": ["how to standardize lifecycle tests"],
            },
        ]

    def _valid_section_cards(self) -> list[dict]:
        return [
            {
                "section_id": "S1",
                "title": "System Model",
                "reader_question": "What are the key nodes of the surveyed system?",
                "section_thesis": "A survey must explain how records, interfaces, lifecycle operations, and evaluation interact.",
                "structure": "总-分-总",
                "opening_move": "Define the system object and the central tension before naming papers.",
                "subsection_moves": [
                    {
                        "subsection": "State capture",
                        "claim": "Typed records make later retrieval and evaluation meaningful.",
                        "papers": ["p1", "p2"],
                        "required_comparison": "Compare event logs with structured records.",
                        "implication": "Record design changes both retrieval validity and evaluation interpretation.",
                    }
                ],
                "closing_move": "Return to design and evaluation implications for later method sections.",
                "required_display_item": "System node table",
            }
        ]

    def _valid_topic_diagnosis(self) -> str:
        return (
            "primary_survey_type: system-object\n"
            "secondary_lenses:\n"
            "  - benchmark/evaluation\n"
            "  - method-family\n"
            "domain_pressures:\n"
            "  - partial observability\n"
            "  - closed-loop control\n"
            "evidence_norm:\n"
            "  preprint_heavy: true\n"
            "  benchmark_fragmentation: high\n"
            "recommended_structure:\n"
            "  - foundations\n"
            "  - system model\n"
            "  - method families\n"
            "  - benchmark landscape\n"
            "  - evaluation protocol\n"
            "excluded_templates:\n"
            "  - pure chronological history\n"
            "section_grammar:\n"
            "  Introduction:\n"
            "    - field shift\n"
            "    - gap\n"
            "    - framework\n"
            "    - contributions\n"
            "  Method Families:\n"
            "    - bottleneck\n"
            "    - mechanism\n"
            "    - comparison\n"
            "    - benchmark tie\n"
            "    - implication\n"
            "  Benchmarks:\n"
            "    - capability\n"
            "    - protocol\n"
            "    - metric\n"
            "    - baseline\n"
            "    - confounder\n"
        )

    def _valid_argument_graph(self) -> str:
        return json.dumps(
            {
                "central_thesis": "Memory is an interface between records, operations, controllers, and evaluation.",
                "field_shift": "Agent systems are moving from short tasks to long-horizon deployment.",
                "gap_in_existing_surveys": "Task-first views fragment mechanisms, benchmarks, and evidence.",
                "argument_nodes": {
                    "A1": {
                        "claim": "Existing task-centered views fragment memory mechanisms.",
                        "evidence": ["related_surveys"],
                        "leads_to": ["A2"],
                        "section": "Tutorial Primer: Embodied Memory in One Running Example",
                        "strength": "suggests",
                    },
                    "A2": {
                        "claim": "A system model connects records, retrieval, update, and evaluation.",
                        "evidence": ["system_node_cards"],
                        "leads_to": ["A3"],
                        "section": "System Model",
                        "strength": "shows",
                    },
                    "A3": {
                        "claim": "Benchmarks operationalize different memory claims.",
                        "evidence": ["benchmark_landscape"],
                        "leads_to": [],
                        "section": "Benchmark Landscape",
                        "strength": "shows",
                    },
                },
                "section_order": [
                    "Tutorial Primer: Embodied Memory in One Running Example",
                    "System Model",
                    "Benchmark Landscape",
                ],
                "takeaway_findings": ["Memory claims require causal ablations."],
            }
        )

    def _valid_paper_mechanism_cards(self) -> list[dict]:
        return [
            {
                "paper_id": "p1",
                "title": "Foundational System Paper",
                "venue_status": "peer-reviewed",
                "level": "A",
                "survey_role": "foundational",
                "system_node": "state capture",
                "motivation": "The paper addresses partial observability in long-horizon planning.",
                "problem_setting": "Planning under hidden state across interactions.",
                "task_definition": "Input observation and goal; output planner action.",
                "benchmark_or_environment": ["planning benchmark"],
                "method_overview": "Introduces typed memory records that are retrieved before planning.",
                "architecture_or_pipeline": ["observe", "write typed record", "retrieve by task", "plan action"],
                "memory_design": {
                    "record_schema": ["observation", "action", "time", "provenance"],
                    "write_trigger": "event boundary",
                    "storage": "structured record store",
                    "read_key": "task-conditioned query",
                    "update_policy": "summarize repeated episodes",
                    "controller_interface": "planner reads retrieved state before action selection",
                },
                "implementation_details": {
                    "model_backbone": "visual encoder",
                    "retriever_or_map": "structured memory retrieval",
                    "planner_or_policy": "symbolic planner",
                    "training_or_inference_setup": "inference-time retrieval",
                },
                "experimental_setup": {
                    "datasets_envs": ["planning benchmark"],
                    "metrics": ["task success"],
                    "baselines": ["no memory"],
                    "ablations": ["no retrieval"],
                },
                "main_results": [
                    {
                        "claim": "Typed retrieval improves task success over no memory.",
                        "evidence": "Section 4 and Table 2 report no memory and no retrieval comparisons.",
                        "strength": "shows",
                    }
                ],
                "limitations_and_confounders": ["limited dynamic updates"],
                "comparison_to_prior_work": "Extends unstructured recurrent state with typed records.",
                "how_it_changes_the_survey_argument": "Shows that memory claims need a visible record and controller interface.",
                "evidence_spans": ["Section 4 and Table 2 report no memory and no retrieval comparisons."],
            },
            {
                "paper_id": "p2",
                "title": "Benchmark System Paper",
                "venue_status": "peer-reviewed",
                "level": "B",
                "survey_role": "benchmark",
                "system_node": "evaluation",
                "motivation": "The paper separates memory quality from aggregate task success.",
                "problem_setting": "Diagnostic evaluation of memory correctness and freshness.",
                "task_definition": "Input stored records and query; output answer or diagnostic score.",
                "benchmark_or_environment": ["diagnostic benchmark"],
                "method_overview": "Introduces benchmark conditions that perturb oracle memory, wrong memory, and stale memory.",
                "architecture_or_pipeline": ["construct memory condition", "run task", "measure diagnostic failure"],
                "memory_design": {
                    "record_schema": ["record", "condition", "provenance"],
                    "write_trigger": "controlled benchmark injection",
                    "storage": "diagnostic memory table",
                    "read_key": "oracle, wrong, or stale condition",
                    "update_policy": "benchmark-controlled manipulation",
                    "controller_interface": "evaluation harness controls memory availability",
                },
                "implementation_details": {
                    "model_backbone": "benchmark harness",
                    "retriever_or_map": "controlled retriever",
                    "planner_or_policy": "tested system",
                    "training_or_inference_setup": "evaluation-time perturbation",
                },
                "experimental_setup": {
                    "datasets_envs": ["diagnostic benchmark"],
                    "metrics": ["accuracy", "failure recovery"],
                    "baselines": ["oracle memory", "wrong memory"],
                    "ablations": ["stale memory injection"],
                },
                "main_results": [
                    {
                        "claim": "Diagnostic conditions reveal false recall and stale-memory failures.",
                        "evidence": "Table 2 defines oracle memory, wrong memory, and stale memory injection settings.",
                        "strength": "shows",
                    }
                ],
                "limitations_and_confounders": ["synthetic benchmark scope"],
                "comparison_to_prior_work": "Complements task success benchmarks with controlled memory perturbations.",
                "how_it_changes_the_survey_argument": "Shows why evaluation needs memory-specific negative controls.",
                "evidence_spans": ["Table 2 defines oracle memory, wrong memory, and stale memory injection settings."],
            },
        ]

    def _rich_review_text(self, *, target: str = "full") -> str:
        cases = []
        evaluation_variants = [
            "The evaluation lesson is that no-memory and no-retrieval ablations identify whether typed capture is doing useful work. The main limitation is stale state: a system can still preserve old evidence after the environment changes, so the case supports the section thesis that write policy and update policy must be evaluated together.",
            "The evaluation lesson is that oracle-memory and wrong-memory conditions distinguish helpful retrieval from plausible but misleading recall. The main limitation is false recall under semantically similar queries, so the case supports the section thesis that read keys and evidence provenance must be discussed together.",
            "The evaluation lesson is that latency and capacity controls matter when the retrieved state enters a planner or policy. The main limitation is that a strong controller can hide whether memory was actually consumed, so the case supports the section thesis that interface attribution must accompany final success scores.",
            "The evaluation lesson is that stale-memory injection exposes whether maintenance policies revise contradictions rather than simply appending more context. The main limitation is weak lifecycle evidence, so the case supports the section thesis that consolidation and forgetting need their own diagnostics.",
            "The evaluation lesson is that benchmark protocols should separate perception error, retrieval error, and action error. The main limitation is confounding among these layers, so the case supports the section thesis that mechanism, interface, and evidence must be discussed together.",
            "The evaluation lesson is that shared-memory or long-horizon settings require provenance and permission checks in addition to task success. The main limitation is governance evidence, so the case supports the section thesis that memory quality includes lifecycle and access-control behavior.",
        ]
        for i in range(4 if target == "full" else 6):
            paper_id = "p1" if i % 2 == 0 else "p2"
            cases.append(
                f"### Case study {i + 1}: Paper {paper_id} as a mechanism example\n"
                f"Paper {paper_id} is useful here because it makes one design decision observable rather than treating memory as a generic accuracy booster. "
                "Its mechanism starts from a typed record, connects that record to a task-conditioned read operation, and passes the retrieved state to a planner or diagnostic harness. "
                "In the taxonomy, this paper anchors a system node where representation, retrieval, and evidence meet. "
                "Compared with a flat context buffer, this design exposes where information is written, what key retrieves it, and which downstream decision is allowed to consume it.\n\n"
                f"{evaluation_variants[i]}\n"
            )

        def table_block(title: str, header: str, row: str) -> str:
            return (
                f"\n{title}\n\n"
                f"{header}\n"
                "| --- | --- | --- |\n"
                f"{row}\n\n"
                "This table is not a catalogue; it separates the design choice from the evidence needed to interpret it. "
                "The important comparison is that two systems can share a task label while relying on different records, read keys, and failure modes. "
                "Consequently, the table should be read as a guide for method selection and evaluation design rather than as an exhaustive bibliography.\n"
            )

        method_section_count = 10 if target == "full" else 12
        h3_sections = "\n".join(
            f"### Method family {i}: structured tutorial subsection\n"
            "This subsection opens by defining the reader question: which record is being maintained, when is it written, and how does it enter action? "
            "Compared with adjacent families, it emphasizes a different trade-off among representation fidelity, retrieval latency, update cost, and controller compatibility. "
            f"Family {i} is distinguished by a specific interface emphasis: record schema, read key, update behavior, controller timing, or evidence status becomes the dominant design choice. "
            f"The section then uses representative systems as evidence and closes by explaining which benchmark or ablation would falsify the claimed memory benefit for family {i}.\n"
            for i in range(1, method_section_count + 1)
        )
        filler = " ".join(
            [
                "A tutorial survey must define the concept, explain the mechanism, compare method families, dissect representative papers, "
                "describe benchmark protocols, state metrics and baselines, and connect open problems to concrete evidence gaps."
            ]
            * (220 if target == "full" else 380)
        )
        return (
            "# Rich Tutorial Survey\n\n"
            "## Tutorial Primer: Embodied Memory in One Running Example\n"
            "This section first builds the reader's mental model before introducing any taxonomy. "
            "The central tension is that embodied memory is not merely stored text: it is a record that must survive perception noise, partial observability, action latency, and environmental change. "
            "Glossary terms: embodied memory, episodic memory, semantic memory, spatial memory, procedural memory, semantic map, topological graph, "
            "3D scene memory, retrieval memory, VLA working memory, stale memory, oracle memory, wrong-memory injection, and memory-causal ablation. "
            "Running example: a robot records an observation, writes an object-state tuple, stores short-term and long-term memories, retrieves by object plus time plus place, "
            "updates stale records, sends a route constraint to the planner, and is evaluated with no-memory, wrong-memory, and oracle-memory controls. "
            "The implication is that each later method family can be understood by asking what changes in this flow.\n\n"
            "## System Model\n"
            "The system model turns the running example into a reusable analysis tool. "
            "Rather than asking whether a paper has a memory module, this section asks which node it implements, what record crosses the interface, and what failure becomes visible if the node is weak. "
            "This framing also explains why navigation, EQA, manipulation, and lifelong deployment are evaluation settings rather than the organizing spine.\n\n"
            "| node | input | output | representative papers | failure mode | evaluation |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| capture | frame, pose, action | typed record | p1, p2 | missing provenance | no-record ablation |\n"
            "| retrieval | query, goal | evidence, constraint | p1, p2 | false recall | oracle/wrong-memory tests |\n\n"
            "The table shows that each node has both a data function and an evidential function. "
            "Capture is not complete unless provenance can later be inspected; retrieval is not useful unless wrong-memory controls show that the controller can reject misleading evidence.\n\n"
            "## Related Surveys\n"
            "Related surveys are positioned by organizing lens, missing evidence matrix, benchmark coverage, and method taxonomy gaps. "
            "This section uses them to motivate the present system-level lens, then transitions from survey positioning to the concrete mechanism taxonomy.\n\n"
            + h3_sections
            + "\n## Method Taxonomy\n"
            "The method taxonomy is an analysis tool, not a naming exercise. "
            "It compares method families by the shape of their memory record, the trigger that writes the record, the key that retrieves it, the lifecycle operation that maintains it, and the interface that exposes it to a planner or policy. "
            "This comparison lets a reader decide which family fits a new problem before seeing any benchmark score.\n\n"
            "| method family | representation | memory record | write trigger | read key | update policy | controller interface | strength | failure mode | representative works | best benchmarks |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            + "".join(
                f"| family {i} | structured state | record fields | event boundary | task key | revise stale records | planner or policy | interpretable | stale state | p1, p2 | benchmark {i} |\n"
                for i in range(1, 9 if target == "full" else 11)
            )
            + "\nThe table's main message is that representation and interface cannot be selected independently. "
            "A spatial map gives strong locality but weak object-state revision; an episodic store preserves evidence provenance but can add retrieval latency; a skill memory changes action directly but can hide whether success came from memory or from policy prior. "
            "These trade-offs set up the case studies below.\n"
            + "\n## Benchmark Landscape\n"
            "Benchmarks are useful only when the capability they operationalize is explicit. "
            "This section therefore groups tasks by memory pressure, required record fields, metric, baseline, and confounder. "
            "The goal is to help readers choose a benchmark for a memory claim and to design the negative controls needed to interpret the result.\n\n"
            "| benchmark | task family | environment | memory pressure | required memory fields | input/output | metrics | baselines | memory-specific ablations | confounders | best-suited method families | representative papers |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            + "".join(
                f"| benchmark {i} | task | simulator | long-horizon record validity | object, place, time | observation/action | success, latency | no-memory, oracle-memory | wrong-memory, stale-memory | perception and planner strength | family {i} | p1, p2 |\n"
                for i in range(1, 11 if target == "full" else 19)
            )
            + "\nThe table should be read as a selection guide. "
            "If a claim is about spatial grounding, the benchmark must perturb location or map state; if it is about evidence-grounded question answering, the benchmark must distinguish correct recall from language priors; if it is about action-facing memory, latency and wrong-state tests become part of the protocol.\n"
            + "\n## Case Studies: From Structured Evidence to Article Prose\n"
            "The following boxes are deliberately selective. "
            "The full evidence tables remain separate from the main article, while the review body uses a smaller set of prose case studies to teach mechanism, evidence, and limitation without turning the article into a catalogue.\n\n"
            + "\n".join(cases)
            + "\n## Method Design Pipeline\n"
            "The method design pipeline starts from memory pressure, selects a memory record schema, chooses a store family, defines write behavior, read behavior, update behavior, and controller interface, then designs memory-causal ablations. "
            "The practical implication is that an implementation report should not stop at a memory-module diagram: it must state which record is written, which query reads it, and which action component consumes the result.\n\n"
            + "\n## Evaluation Protocol\n"
            "Evaluation is where the survey's system lens becomes causal. "
            "A memory claim is weak if it compares only final task success; it becomes stronger when the benchmark manipulates memory availability, correctness, freshness, capacity, and latency while holding perception and policy as stable as possible.\n\n"
            "| condition | purpose | expected evidence |\n| --- | --- | --- |\n| no-memory | checks reliance | success drop |\n| oracle-memory | estimates upper bound | recoverable failures |\n| wrong-memory | detects false recall | rejection or repair |\n\n"
            "The table separates upper-bound evidence from negative controls. "
            "No-memory tests show whether a system uses memory at all, while wrong-memory and stale-memory tests show whether it can avoid acting on misleading records.\n\n"
            "## Failure Modes\n"
            "Failure modes turn the taxonomy into a research agenda. "
            "They show where an apparently successful method family can break when records are stale, retrieval is plausible but wrong, or the controller ignores the retrieved state.\n\n"
            "| failure mode | cause | diagnostic test | design response |\n| --- | --- | --- | --- |\n| stale memory | outdated state | stale injection | update or decay |\n| ignored memory | weak interface | action attribution | tighter controller interface |\n\n"
            "The implication is that robustness cannot be judged by a single success score. "
            "A mature benchmark should reveal whether the failure occurred at record capture, retrieval, update, or controller integration.\n\n"
            "## Tutorial Glossary Table\n"
            "The glossary is included to keep the article readable for newcomers while preserving precise distinctions among record, query, interface, and evaluation.\n\n"
            "| term | plain explanation |\n| --- | --- |\n| memory record | typed evidence used by future actions |\n| read key | query used to retrieve memory |\n\n"
            "These terms recur throughout the review and prevent method families from being compared only by task label.\n\n"
            "## Node-Paper Matrix\n"
            "The node-paper matrix compresses detailed system-node evidence into an article-facing synthesis. "
            "It is used here to explain which papers instantiate a mechanism, which evidence they provide, and which failure mode remains open.\n\n"
            "| system node | representative papers | mechanism pattern | evaluation signal |\n| --- | --- | --- | --- |\n| capture | p1, p2 | event record | no-memory test |\n\n"
            "This matrix is most useful when it is read together with the case studies: the matrix gives coverage, while the cases explain mechanisms.\n\n"
            "## Evidence Trace Table\n"
            "The evidence trace keeps the review's claims grounded without exposing internal notes. "
            "It summarizes the chain from claim to paper to evidence span and design lesson in article language.\n\n"
            "| claim | paper | evidence span | design lesson |\n| --- | --- | --- | --- |\n| memory changes action | p1 | no-memory ablation | expose controller interface |\n\n"
            "The trace makes clear where the evidence is strong and where the survey is proposing a design implication rather than reporting a settled result.\n\n"
            "## Design Guidelines\n"
            "Choose schema, store, read key, update behavior, controller interface, and evaluation protocol before claiming memory contribution. "
            "Compared with a generic module checklist, this guideline emphasizes dependencies: record schema constrains retrieval, retrieval constrains controller integration, and controller integration determines which ablation is meaningful.\n\n"
            "## Open Problems\n"
            "Each open problem links an evidence gap to a benchmark or method move: dynamic update tests, privacy deletion, latency-aware control, and provenance-aware shared records. "
            "The agenda is therefore concrete: define perturbations that isolate stale records, build benchmarks that report memory-causal ablations, and design interfaces that expose when a policy used or ignored retrieved state.\n\n"
            "## Critical Analysis\n"
            "Benchmark limitations, failure modes, trade-offs, and negative evidence show where method families disagree. "
            + filler
        )

    def _artifact_dump_review_text(self, *, target: str = "full") -> str:
        text = self._rich_review_text(target=target)
        raw_examples = "\n".join(
            f"### Worked example {i + 1}: Paper p1\n"
            "- Problem: generic task description.\n"
            "- Memory record: observation, action, timestamp.\n"
            "- Write policy: records are written when available.\n"
            "- Read policy: memory is read when needed.\n"
            "- Update policy: update when new observations arrive.\n"
            "- Controller interface: planner uses memory.\n"
            "- Benchmark / task: arXiv and related task family.\n"
            "- Ablation evidence: 本文要求把该工作放入 no-memory, oracle-memory, wrong-memory.\n"
            "- Failure mode: 若原文没有完整报告，则将其作为证据缺口.\n"
            "- Design lesson: The paper teaches that memory must be specified through record schema.\n"
            for i in range(12 if target == "full" else 25)
        )
        return text + "\n\n## Raw Worked Example Dump\n" + raw_examples

    def _write_depth_outputs(self, task_dir: Path, *, target: str = "full") -> None:
        worked = []
        for i in range(12 if target == "full" else 25):
            paper_id = "p1" if i % 2 == 0 else "p2"
            worked.append(
                f"### Worked example: Paper {paper_id} example {i + 1}\n\n"
                f"- Paper ID: {paper_id}\n"
                "- Problem: Explain whether memory records change a later decision.\n"
                "- Memory record: observation, action, timestamp, provenance, confidence, and task state.\n"
                "- Write policy: append typed records at event boundaries and revise stale records.\n"
                "- Read policy: task-conditioned retrieval with semantic, spatial, and temporal keys.\n"
                "- Update / consolidation: summarize repeated episodes and mark contradictions.\n"
                "- Controller interface: planner receives a retrieved constraint before action selection.\n"
                "- Benchmark / task: diagnostic benchmark with task success and latency.\n"
                "- Ablation evidence: no-memory, oracle-memory, wrong-memory, stale-memory, and capacity tests.\n"
                "- Failure mode: stale state and false recall.\n"
                "- Design lesson: record schema and controller interface must be evaluated together.\n"
            )
        (task_dir / "outputs/worked_examples.md").write_text("# Worked Examples\n\n" + "\n".join(worked))
        (task_dir / "outputs/benchmark_landscape.md").write_text(
            "# Benchmark Landscape\n\n"
            "| Benchmark | Task family | Environment | Memory pressure | Required memory fields | Input / Output | Metrics | Baselines | Memory-specific ablations | Confounders | Best-suited method families | Representative papers |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            + "".join(
                f"| benchmark {i} | task | simulator | long-horizon record validity | object, place, time | observation/action | success, latency | no-memory, oracle-memory | wrong-memory, stale-memory | perception and planner strength | family {i} | p1, p2 |\n"
                for i in range(1, 11 if target == "full" else 19)
            )
        )
        (task_dir / "outputs/method_taxonomy.md").write_text(
            "# Method Taxonomy\n\n"
            "| Method family | Representation | Memory record | Write trigger | Read key | Update policy | Controller interface | Strength | Failure mode | Representative works | Best benchmarks |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            + "".join(
                f"| family {i} | structured state | observation, action, time | event boundary | task-conditioned key | revise stale records | planner or policy | interpretable | stale state | p1, p2 | benchmark {i} |\n"
                for i in range(1, 9 if target == "full" else 11)
            )
        )
        (task_dir / "outputs/node_paper_matrix.md").write_text(
            "# Node Paper Matrix\n\n"
            "| System node | What it does | Representative papers | Mechanism pattern | Evidence | Failure mode | Evaluation signal |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
            "| state capture | converts interaction history into typed records | p1, p2 | event record with provenance | no-record ablation | missing provenance | no-memory test |\n"
            "| evaluation | diagnoses whether memory changes behavior | p1, p2 | oracle/wrong/stale tests | diagnostic benchmark | confounded gains | causal ablation |\n"
        )
        (task_dir / "outputs/glossary.md").write_text(
            "# Glossary\n\n"
            "- embodied memory: records that connect embodied experience to later action.\n"
            "- episodic memory: event-level records of observations and actions.\n"
            "- semantic memory: stable facts or object relations.\n"
            "- spatial memory: map or graph-grounded state.\n"
            "- procedural memory: reusable skills or action programs.\n"
            "- semantic map: spatial map with semantic labels.\n"
            "- topological graph: graph of places or states.\n"
            "- 3D scene memory: three-dimensional scene state used for reasoning.\n"
            "- retrieval memory: external store read by semantic, spatial, or temporal keys.\n"
            "- VLA working memory: short-horizon memory used by vision-language-action policies.\n"
            "- stale memory: old records that conflict with current state.\n"
            "- oracle memory: ideal memory condition used as an upper-bound control.\n"
            "- wrong-memory injection: negative control using incorrect memory.\n"
            "- memory-causal ablation: experiment that isolates whether memory changes behavior.\n"
        )
        (task_dir / "outputs/running_example.md").write_text(
            "# Running Example\n\n"
            "Capture: RGB-D frame, pose, timestamp, and action are recorded. Representation: the object becomes an object-state tuple in a semantic map. "
            "Storage: the current episode and long-term object memory are separated. Retrieval: the system reads by object, time, and place. "
            "Update: stale records are marked or overwritten. Controller: the planner receives a navigation subgoal or manipulation precondition. "
            "Evaluation: no-memory, wrong-memory, and oracle-memory controls test whether memory is causally used.\n"
        )
        (task_dir / "outputs/evaluation_protocol.md").write_text(
            "# Evaluation Protocol\n\n| Condition | Purpose | Metric |\n| --- | --- | --- |\n| no-memory | reliance | success drop |\n| oracle-memory | upper bound | recoverable failures |\n| wrong-memory | false recall | rejection rate |\n"
        )
        (task_dir / "outputs/design_guidelines.md").write_text(
            "# Design Guidelines\n\nChoose memory schema, store family, read key, update policy, controller interface, and causal ablation before implementation claims.\n"
        )
        (task_dir / "outputs/article_plan.md").write_text(
            "# Article Plan\n\n"
            "## Section Order\n"
            "- Tutorial Primer: Embodied Memory in One Running Example\n"
            "- System Model\n"
            "- Benchmark Landscape\n\n"
            "## Article-facing selections\n"
            "- Use the tutorial primer, system model, method taxonomy, benchmark landscape, evaluation protocol, and selected case-study boxes in review.md.\n"
            "- Keep exhaustive worked examples, benchmark rows, method rows, and node-paper coverage in appendix-facing files.\n\n"
            "## Evidence Sources\n"
            "- Use paper mechanism cards, claim evidence spans, and benchmark evidence when selecting article-facing cases.\n\n"
            "## Section flow\n"
            "Each H2 opens with a thesis, compares mechanisms or benchmark signals in the body, and closes with a design or evaluation implication. "
            "The review should not paste structured extraction fields directly into article prose.\n\n"
            "## Selected tables and boxes\n"
            "Use one system-model table, one method-taxonomy table, one benchmark-selection table, one evaluation-protocol table, and a small number of prose case-study boxes.\n"
        )
        (task_dir / "outputs/coverage_matrix.md").write_text(
            "# Coverage Matrix\n\n"
            "| paper | level | family | article use |\n"
            "| --- | --- | --- | --- |\n"
            "| Foundational System Paper | A | state capture | prose case study |\n"
            "| Benchmark System Paper | B | evaluation | benchmark context |\n"
        )
        dossier_dir = task_dir / "outputs/section_dossiers"
        dossier_dir.mkdir(exist_ok=True)
        for i in range(1, 4):
            (dossier_dir / f"section_{i:02d}.md").write_text(
                f"# Section Dossier {i}\n\n"
                "1. Section thesis: explain mechanisms, not only topics.\n"
                "2. Reader question: what should the reader learn?\n"
                "3. Required definitions: memory record, read key, controller interface.\n"
                "4. Running example continuation: connect the robot example to this section.\n"
                "5. Method families or benchmark families: compare design choices.\n"
                "6. Worked paper examples: p1 and p2.\n"
                "7. Comparison table: mechanism versus evidence.\n"
                "8. Benchmark tie-in: no-memory, oracle-memory, wrong-memory.\n"
                "9. Failure modes: stale state and false recall.\n"
                "10. Open questions: update and latency.\n"
                "11. Required citations and evidence spans: p1, p2.\n"
            )

    def _write_deep_artifacts(self, task_dir: Path, *, include_csur_style: bool = False) -> None:
        (task_dir / "state/topic_diagnosis.yml").write_text(self._valid_topic_diagnosis())
        (task_dir / "state/argument_graph.yml").write_text(self._valid_argument_graph())
        (task_dir / "state/paper_mechanism_cards.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in self._valid_paper_mechanism_cards())
        )
        (task_dir / "state/paper_cards.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in self._valid_paper_cards())
        )
        (task_dir / "state/system_node_cards.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in self._valid_node_cards())
        )
        (task_dir / "state/section_cards.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in self._valid_section_cards())
        )
        (task_dir / "state/research_questions_by_perspective.md").write_text(
            "# Questions By Perspective\n\n- System architect: what are the nodes?\n- Experimentalist: what evidence isolates the claim?\n"
        )
        (task_dir / "outputs/conceptual_framework.md").write_text(
            "# Conceptual Framework\n\n"
            "## Central Thesis\nMemory-like systems should be analyzed as interfaces between records, operations, and evaluation.\n\n"
            "## System Diagram In Words\nRecords flow into retrieval, maintenance, control, and evaluation.\n\n"
            "## Node Interactions\nState capture constrains retrieval; evaluation diagnoses whether retrieval changed action.\n\n"
            "## Taxonomy Axes\nRepresentation, interface, lifecycle operation, and evidence strength.\n\n"
            "## Running Example\nA system stores an event, retrieves it for planning, updates it after failure, and is tested with wrong-memory injection.\n\n"
            "## Prior-Survey Delta\nThe framework explains how design choices change evaluation claims.\n"
        )
        if include_csur_style:
            (task_dir / "state/csur_style_patterns.yml").write_text(
                self._valid_csur_style_patterns()
            )
            (task_dir / "state/csur_paragraph_patterns.yml").write_text(
                self._valid_csur_paragraph_patterns()
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
            {
                "paper_id": f"p{i}",
                "title": f"Verified Paper {i}",
                "authors": [f"Author {i}"],
                "year": 2025,
                "venue_status": "peer-reviewed" if i < 60 else "arxiv",
                "doi": f"10.1000/{i}",
                "verified_sources": ["doi"],
                "verification_status": "verified",
                "verified": True,
                "accepted": i < 60,
            }
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
                "paper_card_fields": {"p1": ["what_it_teaches_the_survey", "mechanism_or_contribution"]},
            }
        ]
        default_review = self._rich_review_text(target=target)
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
        (task_dir / "state/claim_evidence_spans.jsonl").write_text(
            json.dumps(
                {
                    "claim_id": "c1",
                    "claim": "A supported claim.",
                    "claim_type": "method",
                    "paper_ids": ["p1"],
                    "strength": "suggests",
                    "evidence_spans": [
                        {
                            "paper_id": "p1",
                            "section_or_page": "Section 4",
                            "evidence_summary": "Section 4 reports the mechanism and no-memory comparison.",
                            "supports": "direct",
                            "strength": "shows",
                        }
                    ],
                }
            )
            + "\n"
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
        self._write_deep_artifacts(task_dir, include_csur_style=target == "csur")
        self._write_depth_outputs(task_dir, target=target)
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
            fact_rows = derive_paper_facts(self._valid_paper_cards())
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
            (task_dir / "state/csur_paragraph_patterns.yml").write_text(
                self._valid_csur_paragraph_patterns()
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
                "state/claim_evidence_spans.jsonl",
                "state/paper_mechanism_cards.jsonl",
                "state/taxonomy.md",
                "state/topic_diagnosis.yml",
                "state/argument_graph.yml",
                "state/paper_summary_consistency.jsonl",
                "state/csur_imitation_plan.md",
                "state/csur_style_patterns.yml",
                "state/csur_paragraph_patterns.yml",
                "state/paper_cards.jsonl",
                "state/coverage.json",
                "state/directions_tried.json",
                "state/research_questions_by_perspective.md",
                "state/section_cards.jsonl",
                "state/system_node_cards.jsonl",
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
            "outputs/review_body_draft.md",
            "outputs/article_plan.md",
            "outputs/appendix.md",
            "outputs/evidence_table.csv",
            "outputs/references.bib",
            "outputs/final_report.md",
            "outputs/coverage_matrix.md",
            "outputs/evidence_ladder.md",
                "outputs/conceptual_framework.md",
                "outputs/glossary.md",
                "outputs/running_example.md",
                "outputs/worked_examples.md",
                "outputs/benchmark_landscape.md",
                "outputs/method_taxonomy.md",
                "outputs/node_paper_matrix.md",
                "outputs/evaluation_protocol.md",
                "outputs/design_guidelines.md",
                "outputs/section_dossiers",
            ]:
                self.assertTrue((task_dir / rel).exists(), rel)

            progress = json.loads((task_dir / "state/progress.json").read_text())
            self.assertEqual(progress["status"], "running")
            self.assertEqual(progress["phase"], "phase_0_task_initialization")
            self.assertEqual(progress["target"], "full")
            completion_gates = json.loads((task_dir / "state/completion_gates.json").read_text())
            self.assertIn("gate_5_deep_synthesis", completion_gates)
            self.assertIn("gate_6_csur_readiness", completion_gates)
            self.assertIn("gate_7_review_depth", completion_gates)
            self.assertIn("final_review_status", completion_gates)
            self.assertNotIn("gate_5_review", completion_gates)

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

    def test_survey_role_scoring_keeps_old_foundational_work(self):
        paper = {
            "title": "An old but foundational system paper",
            "recency_months": 96,
            "citations_per_month": 0,
            "venue_tier": "preprint",
            "acceptance_status": "preprint",
            "survey_role": "foundational",
            "conceptual_centrality": 10,
            "mechanism_clarity": 9,
            "evidence_strength": 7,
            "taxonomy_coverage_value": 9,
            "benchmark_or_ablation_value": 6,
            "venue_or_verification": 6,
        }

        scored = score_paper(paper)

        self.assertGreaterEqual(scored["lqs"], 7.0)
        self.assertEqual(scored["lqs_bucket"], "must-cite")
        self.assertEqual(scored["lqs_model"], "survey-role")

    def test_derive_paper_facts_from_paper_cards(self):
        facts = derive_paper_facts(self._valid_paper_cards())

        self.assertEqual(len(facts), 2)
        self.assertEqual(facts[0]["paper_id"], "p1")
        self.assertEqual(facts[0]["method_family"], "state capture")
        self.assertEqual(
            facts[0]["mechanism_or_contribution"],
            self._valid_paper_cards()[0]["mechanism_or_contribution"],
        )
        self.assertIn("task success", facts[0]["metrics"])

    def test_coverage_counts_ab_refs_per_taxonomy_cell(self):
        citation_plan = [
            {"paper_id": "p1", "taxonomy_cell": "agents/tool-use", "system_node": "retrieval", "depth": "A"},
            {"paper_id": "p2", "taxonomy_cell": "agents/tool-use", "system_node": "retrieval", "depth": "B"},
            {"paper_id": "p3", "taxonomy_cell": "agents/planning", "system_node": "planning", "depth": "C"},
        ]

        coverage = build_coverage(citation_plan)

        self.assertEqual(coverage["cells"]["agents/tool-use"]["ab_refs"], 2)
        self.assertTrue(coverage["cells"]["agents/tool-use"]["passes_min_ab_refs"])
        self.assertEqual(coverage["cells"]["agents/planning"]["ab_refs"], 0)
        self.assertFalse(coverage["cells"]["agents/planning"]["passes_min_ab_refs"])
        self.assertEqual(coverage["system_nodes"]["retrieval"]["ab_refs"], 2)

    def test_coverage_rejects_all_unassigned_ab_refs(self):
        citation_plan = [
            {"paper_id": "p1", "taxonomy_cell": "unassigned", "system_node": "unassigned", "depth": "A"},
            {"paper_id": "p2", "taxonomy_cell": "unassigned", "system_node": "unassigned", "depth": "B"},
        ]

        coverage = build_coverage(citation_plan)

        self.assertFalse(coverage["summary"]["assigned_ab_coverage_passed"])
        self.assertIn("unassigned", coverage["summary"]["coverage_warnings"])

    def test_validate_paper_cards_rejects_shallow_template_cards(self):
        shallow_cards = [
            {
                "paper_id": "p1",
                "method_family": "retrieval",
                "task_family": "agents",
                "limitations": "limited",
            }
        ]

        result = validate_paper_cards(shallow_cards)

        self.assertFalse(result["valid"])
        self.assertIn("missing survey_role", result["errors"][0])
        self.assertIn("missing what_it_teaches_the_survey", result["errors"][0])

    def test_validate_paper_cards_allows_seminal_role_and_checks_ab_coverage(self):
        cards = self._valid_paper_cards()
        cards[0]["survey_role"] = "seminal"
        citation_plan = [
            {"paper_id": "p1", "taxonomy_cell": "cell/a", "depth": "A"},
            {"paper_id": "p2", "taxonomy_cell": "cell/a", "depth": "B"},
            {"paper_id": "p3", "taxonomy_cell": "cell/a", "depth": "B"},
            {"paper_id": "p4", "taxonomy_cell": "cell/a", "depth": "C"},
        ]

        result = validate_paper_cards(cards, citation_plan=citation_plan)

        self.assertFalse(result["valid"])
        self.assertIn("p3", result["missing_paper_cards"])
        self.assertNotIn("unknown survey_role seminal", "\n".join(result["errors"]))

    def test_validate_node_cards_requires_role_meaning_papers_failure_and_eval(self):
        node_cards = [
            {
                "node": "retrieval",
                "role_in_system": "Finds records.",
                "inputs": ["query"],
                "outputs": ["record"],
                "representative_papers": ["p1"],
            }
        ]

        result = validate_node_cards(node_cards)

        self.assertFalse(result["valid"])
        self.assertIn("missing why_it_matters", result["errors"][0])
        self.assertIn("representative_papers needs at least 2 entries", result["errors"][0])

    def test_validate_node_cards_grounding_and_gap_nodes(self):
        node_cards = [
            {
                "node": "state capture",
                "status": "covered",
                "role_in_system": "Converts events into records.",
                "why_it_matters": "It creates the substrate for retrieval.",
                "inputs": ["event"],
                "outputs": ["record"],
                "main_design_families": ["event log"],
                "representative_papers": ["p1", "missing"],
                "failure_modes": ["lost provenance"],
                "evaluation_signals": ["no-record ablation"],
                "open_questions": ["what to retain"],
            },
            {
                "node": "evaluation",
                "status": "gap",
                "role_in_system": "Tests whether state changes behavior.",
                "why_it_matters": "It separates memory effects from policy effects.",
                "inputs": ["protocol"],
                "outputs": ["diagnosis"],
                "main_design_families": ["oracle test"],
                "representative_papers": ["p2"],
                "failure_modes": ["confounded gains"],
                "evaluation_signals": ["stale-state injection"],
                "open_questions": ["how to standardize tests"],
                "gap_reason": "Only one A/B paper isolates this node.",
            },
        ]
        result = validate_node_cards(node_cards, paper_cards=self._valid_paper_cards())

        self.assertFalse(result["valid"])
        self.assertIn("unknown representative_paper missing", "\n".join(result["errors"]))

        node_cards[0]["representative_papers"] = ["p1", "p2"]
        result = validate_node_cards(node_cards, paper_cards=self._valid_paper_cards())

        self.assertTrue(result["valid"])

    def test_validate_node_cards_requires_paper_card_nodes_to_be_covered(self):
        node_cards = [self._valid_node_cards()[0]]

        result = validate_node_cards(node_cards, paper_cards=self._valid_paper_cards())

        self.assertFalse(result["valid"])
        self.assertIn("uncovered paper_card node evaluation", "\n".join(result["errors"]))

    def test_validate_section_cards_requires_argument_structure(self):
        section_cards = [
            {
                "section_id": "S1",
                "title": "Methods",
                "reader_question": "What are the methods?",
                "section_thesis": "Methods differ.",
                "structure": "list",
                "opening_move": "",
                "closing_move": "",
            }
        ]

        result = validate_section_cards(section_cards)

        self.assertFalse(result["valid"])
        self.assertIn("structure must be 总-分-总 or an accepted argument pattern", result["errors"][0])
        self.assertIn("missing opening_move", result["errors"][0])

    def test_validate_section_cards_rejects_unstructured_subsection_moves(self):
        section_cards = self._valid_section_cards()
        section_cards[0]["subsection_moves"] = ["介绍相关工作"]

        result = validate_section_cards(section_cards)

        self.assertFalse(result["valid"])
        self.assertIn("subsection_moves[1] must be an object", "\n".join(result["errors"]))

    def test_validate_section_cards_requires_subsection_claim_papers_comparison_and_implication(self):
        section_cards = self._valid_section_cards()
        section_cards[0]["subsection_moves"] = [
            {
                "subsection": "State capture",
                "claim": "Typed records matter.",
                "papers": ["p1"],
                "required_comparison": "Compare event logs with structured records.",
            }
        ]

        result = validate_section_cards(section_cards)

        self.assertFalse(result["valid"])
        joined = "\n".join(result["errors"])
        self.assertIn("subsection_moves[1] needs at least 2 papers or gap_reason", joined)
        self.assertIn("subsection_moves[1] missing implication", joined)

    def test_validate_csur_style_patterns_rejects_doi_only_skeleton(self):
        skeleton_only = (
            "# CSUR Plan\n\n"
            "Selected CSUR Exemplars: https://dl.acm.org/doi/10.1145/3769292\n\n"
            "Section Skeleton: intro, methods, benchmarks, conclusion.\n"
        )

        result = validate_csur_style_patterns(skeleton_only)

        self.assertFalse(result["valid"])
        self.assertIn("abstract_moves", result["missing"])
        self.assertIn("section_patterns", result["missing"])

        valid = validate_csur_style_patterns(self._valid_csur_style_patterns())

        self.assertTrue(valid["valid"])

    def test_validate_csur_style_patterns_requires_exemplar_evidence(self):
        template_only = (
            "abstract_moves:\n"
            "  - field_importance\n"
            "  - fragmentation_or_gap\n"
            "  - organizing_framework\n"
            "introduction_moves:\n"
            "  - broad_problem\n"
            "  - roadmap\n"
            "section_patterns:\n"
            "  system_model:\n"
            "    structure: 总-分-总\n"
            "    opening: define object\n"
            "    body: compare methods\n"
            "    closing: agenda\n"
            "table_functions:\n"
            "  - compare methods\n"
            "paragraph_patterns:\n"
            "  - claim -> evidence -> implication\n"
            "forbidden_surface_forms:\n"
            "  - Paper A proposes\n"
        )

        result = validate_csur_style_patterns(template_only)

        self.assertFalse(result["valid"])
        self.assertIn("exemplar_evidence", result["missing"])

    def test_validate_csur_paragraph_patterns_requires_all_core_paragraph_moves(self):
        result = validate_csur_paragraph_patterns("introduction_paragraph:\n  paragraph_moves: []\n")

        self.assertFalse(result["valid"])
        self.assertIn("tutorial_definition_paragraph", result["missing_patterns"])
        self.assertIn("evidence_from_exemplar", result["missing_fields"])

        valid = validate_csur_paragraph_patterns(self._valid_csur_paragraph_patterns())

        self.assertTrue(valid["valid"])

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

    def test_validate_claims_cli_accepts_paper_cards_and_detects_missing_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            papers_path = tmp_path / "papers.jsonl"
            claims_path = tmp_path / "claims.jsonl"
            cards_path = tmp_path / "paper_cards.jsonl"
            papers_path.write_text(json.dumps({"paper_id": "p1"}) + "\n")
            claims_path.write_text(
                json.dumps(
                    {
                        "claim_id": "c1",
                        "claim": "A claim needs a card trace.",
                        "paper_ids": ["p1"],
                        "evidence": "Evidence.",
                        "paper_card_fields": {"p1": ["what_it_teaches_the_survey"]},
                    }
                )
                + "\n"
            )
            bad_card = self._valid_paper_cards()[0]
            bad_card["what_it_teaches_the_survey"] = ""
            cards_path.write_text(json.dumps(bad_card) + "\n")

            result = subprocess.run(
                [
                    "python3",
                    "scripts/validate_claims.py",
                    "--claims",
                    str(claims_path),
                    "--papers",
                    str(papers_path),
                    "--paper-cards",
                    str(cards_path),
                ],
                cwd="/Users/sunyanpeng/.codex/skills/survey-autoresearch",
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("paper_card trace fields unavailable", result.stdout)

    def test_validate_review_depth_rejects_outline_expansion(self):
        shallow_review = (
            "# Survey\n\n"
            "## System Model\nA seven-node framework is proposed.\n\n"
            "## Benchmark Landscape\nGOAT-Bench, OpenEQA, and ALFRED are useful benchmarks.\n\n"
            "## Method Taxonomy\nMethods include maps, retrieval, and VLA memory.\n\n"
            "## Evaluation Protocol\nUse ablations.\n"
        )

        result = validate_review_depth(shallow_review, target="full")

        self.assertFalse(result["valid"])
        self.assertIn("length", result["failed_checks"])
        self.assertIn("case_studies", result["failed_checks"])
        self.assertIn("benchmark_entries", result["failed_checks"])
        self.assertIn("method_families", result["failed_checks"])

    def test_validate_review_depth_accepts_rich_tutorial_review(self):
        result = validate_review_depth(self._rich_review_text(target="full"), target="full")

        self.assertTrue(result["valid"])
        self.assertGreaterEqual(result["h3_count"], 10)
        self.assertGreaterEqual(result["case_studies"], 4)

    def test_validate_case_study_prose_rejects_raw_field_dump_in_review(self):
        bad = (
            "### Worked example: Paper p1\n\n"
            "- Problem: generic task description.\n"
            "- Memory record: observation, action, timestamp.\n"
            "- Write policy: records are written when available.\n"
            "- Read policy: memory is read when needed.\n"
            "- Update policy: update when new observations arrive.\n"
            "- Controller interface: planner uses memory.\n"
            "- Benchmark / task: arXiv and related task family.\n"
            "- Ablation evidence: 本文要求把该工作放入 no-memory controls.\n"
            "- Failure mode: stale state.\n"
            "- Design lesson: The paper teaches that memory must be specified through record schema.\n"
        )

        result = validate_case_study_prose(bad, target="full")

        self.assertFalse(result["valid"])
        self.assertIn("raw_field_labels", result["failed_checks"])
        self.assertIn("banned_template_phrases", result["failed_checks"])

        good = (
            "### Case study: Paper p1 as spatial external memory\n\n"
            "Paper p1 matters because it replaces an opaque recurrent state with a typed memory interface. "
            "The mechanism writes observation and action evidence into a structured record, retrieves the record through a task-conditioned query, and passes the retrieved constraint to a planner. "
            "Compared with a flat context buffer, this design makes the read and write boundaries inspectable.\n\n"
            "The evaluation evidence is strongest when no-memory, oracle-memory, wrong-memory, and stale-memory controls are all reported. "
            "Its limitation is that false recall can still be hidden by a strong controller, so the design lesson is to evaluate the memory object and the action interface together.\n"
        )

        result = validate_case_study_prose(good, target="full")

        self.assertTrue(result["valid"])

    def test_validate_table_interpretation_requires_explanatory_prose(self):
        bad = (
            "## Benchmark Landscape\n"
            "Benchmarks are listed below.\n\n"
            "| benchmark | metric | baseline |\n"
            "| --- | --- | --- |\n"
            "| B1 | success | no-memory |\n"
            "## Next Section\n"
            "More content.\n"
        )

        result = validate_table_interpretation(bad, target="full")

        self.assertFalse(result["valid"])
        self.assertIn("table_1 missing after-table interpretation", "\n".join(result["errors"]))

        good = (
            "## Benchmark Landscape\n"
            "Benchmarks are compared by the memory claim they can isolate, not only by task family.\n\n"
            "| benchmark | metric | baseline |\n"
            "| --- | --- | --- |\n"
            "| B1 | success | no-memory |\n\n"
            "This table shows why the benchmark is useful: it separates final success from memory-causal evidence. "
            "The comparison implies that wrong-memory and stale-memory controls are needed before the method claim is credible.\n"
        )

        result = validate_table_interpretation(good, target="full")

        self.assertTrue(result["valid"])

    def test_validate_publication_prose_rejects_artifact_dump_review(self):
        result = validate_publication_prose(self._artifact_dump_review_text(target="full"), target="full")

        self.assertFalse(result["valid"])
        self.assertIn("case_study_prose", result["failed_checks"])
        self.assertIn("raw_artifact_language", result["failed_checks"])

        result = validate_publication_prose(self._rich_review_text(target="full"), target="full")

        self.assertTrue(result["valid"])

    def test_validate_publication_prose_rejects_internal_article_scaffolding(self):
        bad = (
            "## Tutorial Primer\n"
            "本节面向不熟悉 embodied memory 的读者。下面的表是本文的中心方法谱系，"
            "这个表的作用不是列术语，而是解释 artifact 如何进入 dossier。\n\n"
            "## 核心文献吸收矩阵\n"
            "| Core work | 本文如何使用它 |\n"
            "| --- | --- |\n"
            "| Paper p1 | 该工作在本文中被读作 paper card 中的一个 node card 例子 |\n\n"
            "This table is followed by enough prose to avoid a table-only failure, but it still exposes internal scaffolding."
        )

        result = validate_publication_prose(bad, target="full")

        self.assertFalse(result["valid"])
        self.assertIn("raw_artifact_language", result["failed_checks"])
        self.assertIn("本节面向", result["raw_artifact_phrases"])
        self.assertIn("核心文献吸收矩阵", result["raw_artifact_phrases"])

    def test_validate_semantic_repetition_rejects_repeated_headings_and_template_blocks(self):
        repeated = (
            "# Survey\n\n"
            "## Cross-task Design Principles\n"
            "### 深入讨论：record schema 的跨任务意义\n"
            "Record schema determines what can be retrieved and acted upon. 因此，未来综述和方法论文都应把 record schema 写成一等对象。"
            "This paragraph repeats the same design implication, evidence-status language, and benchmark move across the article to inflate depth.\n\n"
            "### 深入讨论：record schema 的跨任务意义\n"
            "Record schema determines what can be retrieved and acted upon. 因此，未来综述和方法论文都应把 record schema 写成一等对象。"
            "This paragraph repeats the same design implication, evidence-status language, and benchmark move across the article to inflate depth.\n\n"
            "### 深入讨论：read policy 的跨任务意义\n"
            "Read policy determines what can be retrieved and acted upon. 因此，未来综述和方法论文都应把 read policy 写成一等对象。"
            "This paragraph repeats the same design implication, evidence-status language, and benchmark move across the article to inflate depth.\n"
        )

        result = validate_semantic_repetition(repeated, target="full")

        self.assertFalse(result["valid"])
        self.assertIn("duplicate_headings", result["failed_checks"])
        self.assertIn("repeated_templates", result["failed_checks"])

    def test_validate_global_coherence_rejects_raw_matrix_and_missing_section_implications(self):
        bad = (
            "# Survey\n\n"
            "## System Model\n"
            "Short opening.\n\n"
            "| node | paper |\n"
            "| --- | --- |\n"
            "| retrieval | p1 |\n\n"
            "## 核心文献吸收矩阵\n"
            "| Core work | Survey role | 本文如何使用它 |\n"
            "| --- | --- | --- |\n"
            "| Paper p1 | system | truncated abstract text |\n\n"
            "## Conclusion\n"
            "The article ends."
        )

        result = validate_global_coherence(bad, target="full")

        self.assertFalse(result["valid"])
        self.assertIn("raw_coverage_matrix_in_review", result["failed_checks"])
        self.assertIn("section_flow", result["failed_checks"])

    def test_validate_global_coherence_accepts_article_plan_driven_sections(self):
        article = (
            "# Survey\n\n"
            "## System Model\n"
            "A mature system-model section first states why the object must be decomposed before papers are named. "
            "The core tension is that two systems can report the same task success while writing different records, reading them with different keys, and exposing different control interfaces. "
            "Compared with a paper-list section, this opening tells the reader what question the section will answer and why the answer matters.\n\n"
            "### Capture and retrieval\n"
            "The body compares event capture and retrieval as coupled design choices. Compared with flat context, typed records expose provenance; however, retrieval still needs stale-memory and wrong-memory tests before the evidence is credible.\n\n"
            "The closing implication is that a system-model table is useful only when it changes evaluation design: readers should know which ablation diagnoses each node and which benchmark can reveal the failure.\n\n"
            "## Conclusion\n"
            "The conclusion returns to the central thesis without introducing a new taxonomy."
        )

        result = validate_global_coherence(article, target="full")

        self.assertTrue(result["valid"])

    def test_validate_worked_examples_requires_mechanism_interface_and_evidence(self):
        bad = "### Worked example: Paper p1\n\n- Problem: too short\n"

        result = validate_worked_examples(bad, self._valid_paper_cards(), target="full")

        self.assertFalse(result["valid"])
        self.assertIn("insufficient_examples", result["failed_checks"])
        self.assertIn("incomplete_example", "\n".join(result["errors"]))

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "outputs").mkdir()
            self._write_depth_outputs(task_dir, target="full")
            result = validate_worked_examples(
                (task_dir / "outputs/worked_examples.md").read_text(),
                self._valid_paper_cards(),
                target="full",
            )

        self.assertTrue(result["valid"])

    def test_validate_benchmark_landscape_requires_metrics_baselines_and_confounders(self):
        bad = (
            "| Benchmark | Task |\n"
            "| --- | --- |\n"
            "| GOAT-Bench | navigation |\n"
        )

        result = validate_benchmark_landscape(bad, target="full")

        self.assertFalse(result["valid"])
        self.assertIn("missing_columns", result["failed_checks"])

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "outputs").mkdir()
            self._write_depth_outputs(task_dir, target="full")
            result = validate_benchmark_landscape(
                (task_dir / "outputs/benchmark_landscape.md").read_text(),
                target="full",
            )

        self.assertTrue(result["valid"])

    def test_validate_method_taxonomy_rejects_concept_buckets(self):
        bad = (
            "| Method family | Representative works |\n"
            "| --- | --- |\n"
            "| maps | p1 |\n"
            "| retrieval | p2 |\n"
        )

        result = validate_method_taxonomy(bad, target="full")

        self.assertFalse(result["valid"])
        self.assertIn("missing_columns", result["failed_checks"])

    def test_validate_node_paper_matrix_requires_mechanism_and_evaluation(self):
        bad = (
            "| System node | What it does | Representative papers |\n"
            "| --- | --- | --- |\n"
            "| retrieval | reads memory | p1 |\n"
        )

        result = validate_node_paper_matrix(bad)

        self.assertFalse(result["valid"])
        self.assertIn("missing_columns", result["failed_checks"])

    def test_validate_newcomer_tutorial_requires_glossary_and_running_example(self):
        review = "# Survey\n\n## Introduction\nMemory matters."

        result = validate_newcomer_tutorial(review, "", "")

        self.assertFalse(result["valid"])
        self.assertIn("missing_tutorial_section", result["failed_checks"])
        self.assertIn("missing_glossary_terms", result["failed_checks"])
        self.assertIn("missing_running_example_steps", result["failed_checks"])

    def test_validate_card_specificity_rejects_template_cards(self):
        cards = self._valid_paper_cards()
        cards[0]["mechanism_or_contribution"] = "task success or answer accuracy memory ablation effect"
        cards[0]["write_policy"] = "Records are written when available."
        cards[0]["read_policy"] = "Memory is read when needed."

        result = validate_card_specificity(cards)

        self.assertFalse(result["valid"])
        self.assertIn("generic_card", "\n".join(result["errors"]))

    def test_validate_review_absorption_requires_a_papers_and_artifacts_in_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir)
            (task_dir / "outputs/review.md").write_text(
                "# Survey\n\n## Benchmark Landscape\nBenchmarks are discussed.\n\n## Method Taxonomy\nMethods are discussed."
            )

            result = validate_review_absorption(task_dir, target="full")

            self.assertFalse(result["valid"])
            self.assertIn("insufficient_contextual_absorption", result["failed_checks"])
            self.assertIn("missing_newcomer_artifact_absorption", result["failed_checks"])

            (task_dir / "outputs/review.md").write_text(self._rich_review_text(target="full"))
            result = validate_review_absorption(task_dir, target="full")

            self.assertTrue(result["valid"])

    def test_validate_review_absorption_rejects_table_only_paper_mentions(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir)
            (task_dir / "outputs/review.md").write_text(
                "# Survey\n\n"
                "## Tutorial Primer\nGlossary and running example define the newcomer path.\n\n"
                "## Method Taxonomy\nMethod taxonomy, write trigger, read key, update policy, and controller interface are listed.\n\n"
                "## Benchmark Landscape\nBenchmark landscape, memory pressure, confounders, baselines, and metrics are discussed.\n\n"
                "## Node Matrix\nSystem node and representative papers are shown.\n\n"
                "| paper | role |\n"
                "| --- | --- |\n"
                "| Foundational System Paper | system |\n"
                "| Benchmark System Paper | benchmark |\n"
            )
            (task_dir / "outputs/coverage_matrix.md").write_text(
                "| paper | family |\n| --- | --- |\n| Foundational System Paper | mechanism |\n| Benchmark System Paper | benchmark |\n"
            )

            result = validate_review_absorption(task_dir, target="full")

            self.assertFalse(result["valid"])
            self.assertIn("insufficient_contextual_absorption", result["failed_checks"])
            self.assertIn("p1", result["papers_without_context"])

    def test_validate_review_absorption_accepts_papers_absorbed_in_prose_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir)
            (task_dir / "outputs/review.md").write_text(
                "# Survey\n\n"
                "## Tutorial Primer\nGlossary and running example define the newcomer path.\n\n"
                "## Method Taxonomy\n"
                "The method taxonomy uses write trigger, read key, update policy, and controller interface to compare mechanisms. "
                "Foundational System Paper contributes a typed event-record mechanism: it writes observation, action, time, provenance, and confidence into a structured record, reads it through a task-conditioned key, and passes the retrieved constraint to a planner. "
                "Its evidence includes no-memory and no-retrieval ablations on a diagnostic benchmark, but its limitation is that dynamic updates and stale state remain weakly tested. "
                "Benchmark System Paper then connects this node-level claim to evaluation by introducing oracle, wrong, and stale-memory conditions; the benchmark evidence clarifies whether memory, rather than perception or controller strength, caused the behavior.\n\n"
                "## Benchmark Landscape\nBenchmark landscape, memory pressure, confounders, baselines, metrics, wrong-memory controls, and stale-memory controls are discussed.\n\n"
                "## Node Matrix\nSystem node coverage is summarized after the prose case studies.\n\n"
                "## Design Guidelines\nThe design implication is to report record schema, read key, update policy, controller interface, and memory-causal ablations together."
            )

            result = validate_review_absorption(task_dir, target="full")

            self.assertTrue(result["valid"])

    def test_review_scorecard_rejects_proposal_like_review(self):
        result = score_review("# Survey\n\nThis proposal defines a framework.", target="full")

        self.assertFalse(result["passed"])
        self.assertLess(result["scores"]["newcomer_score"], 8)

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
                {
                    "paper_id": f"p{i}",
                    "title": f"Verified Paper {i}",
                    "authors": [f"Author {i}"],
                    "year": 2025,
                    "venue_status": "peer-reviewed" if i < 60 else "arxiv",
                    "doi": f"10.1000/full-{i}",
                    "verified_sources": ["doi"],
                    "verification_status": "verified",
                    "verified": True,
                    "accepted": i < 60,
                }
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
            (task_dir / "state/claim_evidence_spans.jsonl").write_text(
                json.dumps(
                    {
                        "claim_id": "c1",
                        "claim": "A supported claim.",
                        "claim_type": "method",
                        "paper_ids": ["p1"],
                        "strength": "suggests",
                        "evidence_spans": [
                            {
                                "paper_id": "p1",
                                "section_or_page": "Section 4",
                                "evidence_summary": "Section 4 provides evidence text.",
                                "supports": "direct",
                                "strength": "shows",
                            }
                        ],
                    }
                )
                + "\n"
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
            self.assertIn("benchmark landscape", gates["gate_4_output"]["reader_artifact_warnings"])
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
            self._write_deep_artifacts(task_dir)
            self._write_depth_outputs(task_dir, target="full")

            gates = evaluate_gates(task_dir, target="full")

            self.assertTrue(gates["gate_4_output"]["passed"])
            self.assertFalse(gates["gate_7_review_depth"]["passed"])
            self.assertIn("review depth", gates["gate_7_review_depth"]["failed_checks"])
            self.assertFalse(gates["all_blocking_gates_passed"])

            (task_dir / "outputs/review.md").write_text(self._rich_review_text(target="full"))
            gates = evaluate_gates(task_dir, target="full")

            self.assertTrue(gates["all_blocking_gates_passed"])

            (task_dir / "outputs/review.md").write_text(self._artifact_dump_review_text(target="full"))
            gates = evaluate_gates(task_dir, target="full")

            self.assertFalse(gates["gate_7_review_depth"]["passed"])
            self.assertIn("publication prose", gates["gate_7_review_depth"]["failed_checks"])

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

    def test_full_survey_gate_requires_deep_synthesis_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir)
            (task_dir / "state/paper_cards.jsonl").unlink()
            (task_dir / "state/system_node_cards.jsonl").unlink()
            (task_dir / "state/section_cards.jsonl").unlink()

            gates = evaluate_gates(task_dir, target="full")

            self.assertFalse(gates["gate_5_deep_synthesis"]["passed"])
            self.assertIn("state/paper_cards.jsonl", gates["gate_5_deep_synthesis"]["missing_artifacts"])
            self.assertIn("state/system_node_cards.jsonl", gates["gate_5_deep_synthesis"]["missing_artifacts"])
            self.assertIn("state/section_cards.jsonl", gates["gate_5_deep_synthesis"]["missing_artifacts"])
            self.assertFalse(gates["all_blocking_gates_passed"])

    def test_full_survey_gate_requires_ab_paper_card_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir)
            paper_cards = self._valid_paper_cards()[:1]
            (task_dir / "state/paper_cards.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in paper_cards)
            )

            gates = evaluate_gates(task_dir, target="full")

            self.assertFalse(gates["gate_5_deep_synthesis"]["passed"])
            self.assertIn("paper-card depth", gates["gate_5_deep_synthesis"]["failed_checks"])
            self.assertIn("p2", gates["gate_5_deep_synthesis"]["paper_cards"]["missing_paper_cards"])

    def test_full_survey_gate_accepts_chinese_conceptual_framework_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir)
            (task_dir / "outputs/conceptual_framework.md").write_text(
                "# 概念框架\n\n"
                "## 中心论点\n具备研究价值的综述需要把系统对象解释为一组相互作用的机制，而不是把论文按任务堆叠。这里说明核心论点如何贯穿全文。\n\n"
                "## 系统模型\n系统模型描述输入如何被记录、表示、检索、更新并进入控制接口，同时说明每个组件承担的功能边界和证据要求。\n\n"
                "## 节点交互\n节点交互解释记录生成、表示选择、读取策略、更新策略和控制接口之间如何相互约束，并说明错误如何传播到评测。\n\n"
                "## 分类轴\n分类轴从表示、接口、生命周期操作和证据强度组织方法，使读者能比较设计选择而不是只记住论文名称。\n\n"
                "## 贯穿例子\n贯穿例子展示一个系统如何写入事件、检索记录、根据反馈修正状态，并用扰动实验验证记忆是否真正改变决策。\n\n"
                "## 与已有综述的区别\n相关综述差异在于本文把系统节点和证据链作为组织对象，因此能解释已有分类无法揭示的设计与评测缺口。\n"
            )

            gates = evaluate_gates(task_dir, target="full")

            self.assertTrue(gates["gate_5_deep_synthesis"]["conceptual_framework"]["passed"])

    def test_full_survey_gate_rejects_empty_conceptual_framework_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir)
            (task_dir / "outputs/conceptual_framework.md").write_text(
                "## Central Thesis\n\n## System Model\n\n## Node Interactions\n\n## Taxonomy Axes\n\n## Running Example\n\n## Prior-Survey Delta\n"
            )

            gates = evaluate_gates(task_dir, target="full")

            self.assertFalse(gates["gate_5_deep_synthesis"]["conceptual_framework"]["passed"])

    def test_full_survey_gate_rejects_keyword_rich_review_without_node_and_section_logic(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir)
            (task_dir / "state/system_node_cards.jsonl").write_text(
                json.dumps({"node": "retrieval", "role_in_system": "Find records."}) + "\n"
            )
            (task_dir / "state/section_cards.jsonl").write_text(
                json.dumps({"section_id": "S1", "title": "Methods", "structure": "list"}) + "\n"
            )

            gates = evaluate_gates(task_dir, target="full")

            self.assertTrue(gates["gate_4_output"]["passed"])
            self.assertFalse(gates["gate_5_deep_synthesis"]["passed"])
            self.assertIn("node depth", gates["gate_5_deep_synthesis"]["failed_checks"])
            self.assertIn("section argument", gates["gate_5_deep_synthesis"]["failed_checks"])

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

    def test_full_survey_gate_allows_preprint_heavy_publication_norm_with_stronger_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir)
            papers = [
                {
                    "paper_id": f"p{i}",
                    "title": f"Preprint Paper {i}",
                    "authors": [f"Author {i}"],
                    "year": 2026,
                    "venue_status": "preprint",
                    "arxiv_id": f"2601.{i:05d}",
                    "verified_sources": ["arxiv"],
                    "verification_status": "verified",
                    "verified": True,
                    "accepted": i < 10,
                }
                for i in range(160)
            ]
            (task_dir / "state/papers.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in papers)
            )
            (task_dir / "state/task_spec.md").write_text(
                "# Task Spec\n\nTarget: full\n\nPublication norm:\naccepted_ratio_required: false\nreason: preprint-heavy field\n"
            )

            gates = evaluate_gates(task_dir, target="full")

            self.assertTrue(gates["gate_1_literature"]["publication_norm"]["preprint_heavy"])
            self.assertTrue(gates["gate_1_literature"]["passed"])

    def test_csur_gate_requires_protocol_related_surveys_and_paper_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "state").mkdir()
            (task_dir / "outputs").mkdir()
            papers = [
                {
                    "paper_id": f"p{i}",
                    "title": f"Verified CSUR Paper {i}",
                    "authors": [f"Author {i}"],
                    "year": 2025,
                    "venue_status": "peer-reviewed" if i < 80 else "arxiv",
                    "doi": f"10.1000/csur-{i}",
                    "verified_sources": ["doi"],
                    "verification_status": "verified",
                    "verified": True,
                    "accepted": i < 80,
                }
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
            (task_dir / "state/claim_evidence_spans.jsonl").write_text(
                json.dumps(
                    {
                        "claim_id": "c1",
                        "claim": "A supported synthesis claim.",
                        "claim_type": "taxonomy",
                        "paper_ids": ["p1", "p2"],
                        "strength": "suggests",
                        "evidence_spans": [
                            {
                                "paper_id": "p1",
                                "section_or_page": "Section 4",
                                "evidence_summary": "Section 4 supports the synthesis claim.",
                                "supports": "direct",
                                "strength": "shows",
                            },
                            {
                                "paper_id": "p2",
                                "section_or_page": "Table 2",
                                "evidence_summary": "Table 2 supports the benchmark side of the claim.",
                                "supports": "direct",
                                "strength": "shows",
                            },
                        ],
                    }
                )
                + "\n"
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
            full_cards = []
            full_mechanism_cards = []
            for i in range(12):
                card = dict(self._valid_paper_cards()[0])
                card["paper_id"] = f"p{i}"
                full_cards.append(card)
                mechanism_card = json.loads(json.dumps(self._valid_paper_mechanism_cards()[0]))
                mechanism_card["paper_id"] = f"p{i}"
                mechanism_card["title"] = f"Mechanism Paper {i}"
                mechanism_card["level"] = "A" if i < 8 else "B"
                full_mechanism_cards.append(mechanism_card)
            (task_dir / "state/paper_cards.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in full_cards)
            )
            (task_dir / "state/paper_mechanism_cards.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in full_mechanism_cards)
            )
            (task_dir / "state/paper_facts.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in derive_paper_facts(full_cards))
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
            self._write_deep_artifacts(task_dir, include_csur_style=True)
            (task_dir / "state/paper_cards.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in full_cards)
            )
            (task_dir / "state/paper_mechanism_cards.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in full_mechanism_cards)
            )
            (task_dir / "state/paper_facts.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in derive_paper_facts(full_cards))
            )
            self._write_depth_outputs(task_dir, target="csur")
            anchor_context = "\n".join(
                (
                    f"Paper p{i} is treated as an article-facing anchor because its mechanism writes a typed record, "
                    "reads that record through a task-conditioned key, and exposes the retrieved state to a planner interface. "
                    "Within the taxonomy, it supports a system node that connects representation, retrieval, update policy, and evidence status. "
                    "The benchmark evidence should be read through no-memory, wrong-memory, stale-memory, and oracle-memory ablations, while the limitation is that stale state and false recall remain possible confounders."
                )
                for i in range(6)
            )
            (task_dir / "outputs/review.md").write_text(
                self._rich_review_text(target="csur") + "\n\n## Additional Article-Facing Anchor Cases\n" + anchor_context
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

    def test_csur_gate_requires_rhetoric_patterns_not_only_exemplar_dois(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            self._write_full_survey_fixture(task_dir, target="csur")
            (task_dir / "state/csur_style_patterns.yml").write_text(
                "selected_exemplars:\n"
                "  - https://dl.acm.org/doi/10.1145/3769292\n"
                "section_skeleton: intro, taxonomy, methods, benchmarks, conclusion\n"
            )

            gates = evaluate_gates(task_dir, target="csur")

            self.assertFalse(gates["gate_5_deep_synthesis"]["passed"])
            self.assertIn("CSUR rhetoric", gates["gate_5_deep_synthesis"]["failed_checks"])

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
            self.assertEqual(len(result["phase_pages"]), 12)
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

    def test_topic_diagnosis_requires_primary_secondary_and_section_grammar(self):
        shallow = {
            "primary_survey_type": "system-object",
        }
        rich = {
            "primary_survey_type": "system-object",
            "secondary_lenses": ["benchmark/evaluation", "method-family"],
            "domain_pressures": ["partial observability", "closed-loop control"],
            "evidence_norm": {"preprint_heavy": True, "benchmark_fragmentation": "high"},
            "recommended_structure": ["foundations", "system model", "method families", "benchmark landscape", "evaluation protocol"],
            "excluded_templates": ["pure chronological history"],
            "section_grammar": {
                "Introduction": ["field shift", "gap", "framework", "contributions"],
                "Method Families": ["bottleneck", "mechanism", "comparison", "benchmark tie", "implication"],
                "Benchmarks": ["capability", "protocol", "metric", "baseline", "confounder"],
            },
        }

        self.assertFalse(validate_topic_diagnosis(shallow)["valid"])
        self.assertTrue(validate_topic_diagnosis(rich)["valid"])

    def test_paper_mechanism_cards_require_scientific_contribution_chain(self):
        shallow = [
            {
                "paper_id": "p1",
                "title": "Memory System",
                "survey_role": "method",
                "method_overview": "Uses memory.",
            }
        ]
        rich = [
            {
                "paper_id": "p1",
                "title": "Memory System",
                "venue_status": "peer-reviewed",
                "level": "A",
                "survey_role": "method",
                "motivation": "The paper addresses partial observability in long-horizon control.",
                "problem_setting": "Object-goal navigation with hidden state across episodes.",
                "task_definition": "Input observations and goal query; output navigation action.",
                "benchmark_or_environment": ["EnvBench"],
                "method_overview": "The system writes typed object-location records and retrieves them before planning.",
                "architecture_or_pipeline": ["detect object", "write record", "retrieve by goal", "plan action"],
                "memory_design": {
                    "record_schema": ["object", "place", "time", "confidence"],
                    "write_trigger": "object observation",
                    "storage": "spatial-temporal store",
                    "read_key": "object goal plus room",
                    "update_policy": "revise stale records",
                    "controller_interface": "planner receives retrieved goal constraint",
                },
                "implementation_details": {
                    "model_backbone": "visual encoder",
                    "retriever_or_map": "semantic map",
                    "planner_or_policy": "planner",
                    "training_or_inference_setup": "inference-time retrieval",
                },
                "experimental_setup": {
                    "datasets_envs": ["EnvBench"],
                    "metrics": ["success"],
                    "baselines": ["no memory"],
                    "ablations": ["no retrieval"],
                },
                "main_results": [
                    {
                        "claim": "Typed retrieval improves success over no-memory baseline.",
                        "evidence": "Table 2 compares no-memory and retrieval conditions.",
                        "strength": "shows",
                    }
                ],
                "limitations_and_confounders": ["perception quality may confound gains"],
                "comparison_to_prior_work": "Extends map-based memory with task-conditioned retrieval.",
                "how_it_changes_the_survey_argument": "Shows why record schema and controller interface must be compared together.",
                "evidence_spans": ["Table 2 reports no-memory and retrieval comparison."],
            }
        ]

        self.assertFalse(validate_paper_mechanism_cards(shallow)["valid"])
        status = validate_paper_mechanism_cards(rich, citation_plan=[{"paper_id": "p1", "depth": "A"}])
        self.assertTrue(status["valid"])
        self.assertEqual(derive_paper_cards(rich)[0]["paper_id"], "p1")

    def test_claim_evidence_spans_and_strength_ladder(self):
        mechanism_cards = [
            {
                "paper_id": "p1",
                "title": "Memory System",
                "main_results": [{"claim": "Retrieval improves success.", "evidence": "Table 2.", "strength": "shows"}],
                "evidence_spans": ["Table 2 reports no-memory and retrieval comparison."],
            }
        ]
        too_strong = [
            {
                "claim_id": "c1",
                "claim": "The method demonstrates causal memory contribution.",
                "claim_type": "result",
                "paper_ids": ["p1"],
                "strength": "demonstrates",
                "evidence_spans": [
                    {
                        "paper_id": "p1",
                        "section_or_page": "Table 2",
                        "evidence_summary": "No-memory comparison.",
                        "supports": "direct",
                        "strength": "shows",
                    }
                ],
            }
        ]
        calibrated = [
            {
                **too_strong[0],
                "strength": "shows",
            }
        ]

        self.assertFalse(validate_claim_evidence_spans(too_strong, mechanism_cards)["valid"])
        self.assertTrue(validate_claim_evidence_spans(calibrated, mechanism_cards)["valid"])

    def test_citation_identity_blocks_unverified_a_level_support(self):
        papers = [
            {"paper_id": "p1", "title": "Verified", "authors": ["A"], "year": 2025, "venue_status": "peer-reviewed", "doi": "10.1/x", "verified_sources": ["doi"], "verification_status": "verified"},
            {"paper_id": "p2", "title": "Unverified", "authors": ["B"], "year": 2026, "venue_status": "unknown", "verification_status": "unverified"},
        ]
        citation_plan = [{"paper_id": "p1", "depth": "A"}, {"paper_id": "p2", "depth": "A"}]

        status = validate_citation_identity(papers, citation_plan, target="full")

        self.assertFalse(status["valid"])
        self.assertIn("p2", status["unverified_a_b_papers"])

    def test_argument_graph_and_article_plan_alignment_are_required(self):
        graph = {
            "central_thesis": "Memory is an interface.",
            "field_shift": "Agents move from short tasks to long deployment.",
            "gap_in_existing_surveys": "Task-first views split record, retrieval, and evaluation.",
            "argument_nodes": {
                "A1": {"claim": "Task views fragment memory mechanisms.", "evidence": ["related_surveys"], "leads_to": ["A2"], "section": "Introduction", "strength": "suggests"},
                "A2": {"claim": "System nodes unify methods and benchmarks.", "evidence": ["system_node_cards"], "leads_to": ["A3"], "section": "System Model", "strength": "shows"},
                "A3": {"claim": "Benchmarks operationalize memory claims.", "evidence": ["benchmark_landscape"], "leads_to": [], "section": "Benchmarks", "strength": "shows"},
            },
            "section_order": ["Introduction", "System Model", "Benchmarks"],
            "takeaway_findings": ["Memory claims require causal ablations."],
        }
        article_plan = (
            "# Article Plan\n\n"
            "## Section Order\n- Introduction\n- System Model\n- Benchmarks\n\n"
            "## Article-facing Evidence\nUse mechanism cards, benchmark landscape, and selected prose case boxes.\n\n"
            "## Appendix-facing Artifacts\nMove exhaustive coverage matrices to appendix.\n"
        )

        self.assertTrue(validate_argument_graph(graph)["valid"])
        self.assertTrue(validate_article_plan_alignment(article_plan, graph)["valid"])
        self.assertFalse(validate_article_plan_alignment("# Article Plan\n\n- Benchmarks\n", graph)["valid"])

    def test_paper_summary_consistency_downgrades_unsupported_ablations(self):
        cards = [
            {
                "paper_id": "p1",
                "title": "Memory System",
                "experimental_setup": {"benchmarks": ["EnvBench"], "baselines": ["no memory"], "ablations": ["wrong-memory"]},
                "main_results": [{"claim": "Wrong-memory ablation proves robustness.", "evidence": "Table 2.", "strength": "demonstrates"}],
                "evidence_spans": ["Table 2 reports no-memory baseline only."],
            }
        ]

        status = validate_paper_summary_consistency(cards)

        self.assertFalse(status["valid"])
        self.assertIn("p1", status["invalid_papers"])

    def test_gate_full_requires_topic_argument_and_mechanism_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "run"
            task_dir.mkdir()
            self._write_full_survey_fixture(task_dir, target="full")
            for rel in [
                "state/topic_diagnosis.yml",
                "state/argument_graph.yml",
                "state/paper_mechanism_cards.jsonl",
            ]:
                (task_dir / rel).write_text("")

            result = evaluate_gates(task_dir, "full")

            self.assertFalse(result["all_blocking_gates_passed"])
            self.assertFalse(result["gate_5_deep_synthesis"]["checks"]["topic diagnosis"])
            self.assertFalse(result["gate_5_deep_synthesis"]["checks"]["paper mechanism depth"])
            self.assertFalse(result["gate_5_deep_synthesis"]["checks"]["argument graph"])

    def test_evidence_ladder_summarizes_claim_strengths(self):
        claims = [
            {"claim_id": "c1", "strength": "demonstrates"},
            {"claim_id": "c2", "strength": "suggests"},
            {"claim_id": "c3", "strength": "suggests"},
        ]

        ladder = derive_evidence_ladder(claims)

        self.assertEqual(ladder["counts"]["suggests"], 2)
        self.assertEqual(ladder["strongest"], "demonstrates")


if __name__ == "__main__":
    unittest.main()
