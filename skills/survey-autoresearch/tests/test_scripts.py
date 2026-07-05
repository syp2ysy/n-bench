import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.build_contribution_tree import validate_contribution_tree
from scripts.build_repair_plan import build_repair_plan
from scripts.expert_review_gate import validate_expert_reviews
from scripts.gate7_driver import run_until_complete
from scripts.gate7_loop import (
    adjudicate_reports,
    collect_gate7_status,
    make_reviewer_prompts,
    make_targeted_rereview_prompts,
    precheck_review_report,
    record_repair_action,
    record_regression_check,
    record_review_report,
    record_targeted_rereview,
)
from scripts.gate_check import evaluate_gates
from scripts.init_task import initialize_task
from scripts.phase_gate import evaluate_phase_barriers
from scripts.render_dashboard import render_dashboard
from scripts.render_survey_html import render_survey_html
from scripts.promote_survey_release import promote_release
from scripts.run_expansion_audit import collect_status as collect_expansion_audit_status
from scripts.run_expansion_audit import dispatch_packet as dispatch_expansion_audit_packet
from scripts.run_expert_reviews import collect_status, dispatch_packets, freeze_review_round
from scripts.score_lqs import classify_depth, score_paper
from scripts.validate_argument_graph import validate_argument_graph
from scripts.validate_article_quality import validate_article_quality
from scripts.validate_claim_evidence import validate_claim_evidence
from scripts.validate_coverage import validate_coverage
from scripts.validate_exemplar_alignment import validate_exemplar_alignment
from scripts.validate_paper_understanding import validate_paper_understanding
from scripts.validate_related_survey_alignment import validate_related_survey_alignment
from scripts.validate_scenario_definitions import validate_scenario_definitions
from scripts.validate_section_evidence_plans import validate_section_evidence_plans
from scripts.validate_synthesis_dossiers import validate_synthesis_dossiers
from scripts.verify_sources import validate_sources


ROOT = Path(__file__).resolve().parents[1]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_text_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def sha256_artifact(task_dir: Path, artifact: str) -> str:
    path = task_dir / artifact
    if not path.exists():
        return ""
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def sha256_jsonl_rows(rows: list[dict]) -> str:
    payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stable_gate_hash(gates: dict) -> str:
    payload = {key: value for key, value in gates.items() if key not in {"generated_at", "release_manifest", "survey_complete", "completion_level"}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class SurveyAutoResearchContractTest(unittest.TestCase):
    dimensions = [
        "narrative_coherence",
        "paper_understanding_depth",
        "field_native_taxonomy_quality",
        "method_taxonomy_quality",
        "benchmark_and_evaluation_quality",
        "evidence_factuality_and_citation_accuracy",
        "synthesis_not_catalog",
        "information_density",
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
                "family": ["retrieval memory", "structured map memory", "episodic policy memory"][idx % 3],
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
                "family": ["retrieval memory", "structured map memory", "episodic policy memory"][idx % 3],
            }
            for idx in range(1, total + 1)
        ]

    def search_routes(self, total: int = 8) -> list[dict]:
        route_types = ["keyword", "snowball", "related_survey_refs", "curated_list", "benchmark", "venue", "author_group", "keyword"]
        core_families = ["retrieval memory", "structured map memory", "episodic policy memory"]
        return [
            {
                "route_id": f"route-{idx:02d}",
                "source": "Semantic Scholar" if idx % 2 else "OpenAlex",
                "query": f"{route_types[(idx - 1) % len(route_types)]} query",
                "query_family": route_types[(idx - 1) % len(route_types)],
                "route_type": route_types[(idx - 1) % len(route_types)],
                "core_family": core_families[(idx - 1) % len(core_families)],
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

    def topic_relevance_audit(
        self,
        raw_candidates: list[dict] | None = None,
        papers: list[dict] | None = None,
        citation_plan: list[dict] | None = None,
    ) -> list[dict]:
        raw_candidates = raw_candidates or self.raw_candidates()
        papers = papers or self.papers()
        citation_plan = citation_plan or self.citation_plan()
        paper_by_id = {str(row.get("paper_id")): row for row in papers if row.get("paper_id")}
        depth_by_id = {str(row.get("paper_id")): str(row.get("depth") or row.get("level") or "C").upper() for row in citation_plan if row.get("paper_id")}
        retained_ids = set(paper_by_id)
        related_ids = set(sorted(retained_ids)[-8:]) if len(retained_ids) >= 8 else set(retained_ids)
        rows = []
        seen = set()
        for candidate in raw_candidates:
            pid = str(candidate.get("paper_id") or "")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            paper = paper_by_id.get(pid, {})
            merged = {**candidate, **paper}
            family = str(merged.get("family") or merged.get("topic_axis") or "retrieval memory")
            depth = depth_by_id.get(pid, "C")
            retained = pid in retained_ids
            if retained and pid in related_ids and depth == "C":
                grade = "direct_related_survey"
                allowed_role = "related_survey"
                corrected_family = "related survey taxonomy"
            elif retained:
                grade = "core"
                allowed_role = "core" if depth in {"A", "B"} else "background"
                corrected_family = family
            else:
                grade = "adjacent_background"
                allowed_role = "background"
                corrected_family = family
            rows.append(
                {
                    "paper_id": pid,
                    "candidate_id": str(candidate.get("candidate_id") or paper.get("source_candidate_id") or pid),
                    "title": merged.get("title") or f"Paper {pid}",
                    "evidence_used": [
                        {"field": "title", "text": str(merged.get("title") or f"Paper {pid}")},
                        {"field": "query", "text": str(candidate.get("query") or "embodied memory survey")},
                        {"field": "source_metadata", "text": "Synthetic source metadata says this record matches the task topic boundary."},
                    ],
                    "positive_topic_signals": ["matches the synthetic survey topic boundary"],
                    "negative_drift_signals": [],
                    "relevance_grade": grade,
                    "allowed_depth": depth if grade == "core" else ("C" if grade != "out_of_scope" else "exclude"),
                    "allowed_role": allowed_role,
                    "family_label_supported": grade == "core",
                    "corrected_family": corrected_family,
                    "rationale": "Synthetic contract fixture: source metadata supports the task topic boundary, so legacy tests can focus on non-topic gates.",
                }
            )
        return rows

    def topic_profile(self, topic: str = "embodied memory system") -> dict:
        if "mllm" in topic.lower() or "image" in topic.lower() or "visual" in topic.lower():
            positive = [
                "visual scratchpad",
                "image-as-workspace",
                "visual intermediate-state reasoning",
            ]
            negative = [
                "generic LLM survey without visual workspace reasoning",
                "RAG survey without image-grounded reasoning actions",
                "education or medical ChatGPT survey without multimodal reasoning mechanisms",
            ]
            queries = [
                "visual scratchpad multimodal reasoning",
                "image as workspace MLLM reasoning",
                "visual intermediate state reasoning",
            ]
            central = "Which papers directly study image-grounded intermediate reasoning states rather than generic MLLM capability?"
        else:
            positive = [
                "retrieval memory",
                "structured map memory",
                "episodic policy memory",
            ]
            negative = [
                "generic LLM memory without embodied decision evidence",
                "survey-only background without direct system mechanism",
            ]
            queries = [
                "embodied memory retrieval system survey",
                "structured map memory embodied agents",
                "episodic policy memory embodied AI",
            ]
            central = "How do embodied systems use memory mechanisms to support evidence-conditioned decisions?"
        return {
            "schema_version": 1,
            "topic": topic,
            "central_question": central,
            "positive_anchors": positive,
            "negative_anchors": negative,
            "allowed_background": ["broad surveys may be used only for positioning, not as A/B core papers"],
            "core_claim_types": ["taxonomy claims", "method comparison claims", "benchmark and evaluation claims"],
            "search_seed_queries": queries,
            "acceptance_rubric": {
                "paper_relevance": "A/B papers must directly match the positive anchors and avoid the negative drift anchors.",
                "survey_spine": "The survey spine must be derived from topic-qualified paper cards and related-survey deltas.",
                "paper_understanding": "A/B papers require full-text mechanism cards with evidence spans.",
            },
            "must_find_related_surveys": True,
            "subagent_session_id": "test-topic-profile-agent",
            "recorded_at": "2026-07-05T00:00:00+00:00",
        }

    def write_topic_profile(self, task_dir: Path, topic: str = "embodied memory system") -> None:
        (task_dir / "state" / "topic_profile.json").write_text(
            json.dumps(self.topic_profile(topic), sort_keys=True),
            encoding="utf-8",
        )

    def corpus_expansion(self, required: bool = False, status: str = "not_required") -> dict:
        return {
            "required": required,
            "triggered_by": ["curated list larger than retained corpus"] if required else [],
            "visible_external_count": 500 if required else 0,
            "largest_visible_external_count": 500 if required else 180,
            "retained_candidate_count": 220,
            "curated_lists_checked": ["awesome embodied memory list"],
            "recent_surveys_checked": ["recent embodied memory survey"],
            "why_retained_corpus_is_sufficient": "The retained corpus covers all selected core families with independent routes and A/B papers.",
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
                "method_pipeline": [f"encode observation for p{idx:03d}", f"write task evidence for p{idx:03d}", f"retrieve decision evidence for p{idx:03d}", f"act or answer with p{idx:03d} evidence"],
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
                "main_results": [{"result": f"Paper p{idx:03d} improves the diagnostic benchmark over the no-memory baseline.", "evidence_span": "Section 4, Table 2.", "claim_strength": "shows"}],
                "limitations_and_confounders": [f"perception and controller strength may confound aggregate success for p{idx:03d}", f"the p{idx:03d} evidence does not isolate all deployment-time failures"],
                "relation_to_prior_work": "extends prior context-only systems with explicit evidence use.",
                "what_it_changes_in_the_survey_argument": "It supports the claim that memory must be evaluated through evidence and control interfaces.",
                "possible_sections": ["Method Families", "Evaluation Protocol"],
                "supports_claims": [{"claim_type": "evidence-control evaluation", "claim_hint": "memory utility depends on evidence/control interfaces"}],
                "one_sentence_contribution": f"Paper p{idx:03d} connects structured evidence use to measurable control performance under Benchmark-X.",
                "must_not_overclaim": ["does not demonstrate general memory causality without negative controls"],
                "evidence_spans": ["Section 4, Table 2 reports the comparison."],
                "scenario_links": ["navigation", "EQA", "manipulation", "VLA", "lifelong"],
                "entity_aliases": [
                    {"name": f"Verified Paper {idx}", "type": "paper_title", "source_ref": f"src-p{idx:03d}", "evidence": "paper title"},
                    {"name": f"Method-P{idx:03d}", "type": "method", "source_ref": f"src-p{idx:03d}", "evidence": "Section 3 names the method."},
                    {"name": "Benchmark-X", "type": "benchmark", "source_ref": f"src-p{idx:03d}", "evidence": "Section 4 names the benchmark."},
                ],
                "field_evidence_map": {
                    "motivation": [{"source_ref": f"src-p{idx:03d}", "location": "Introduction, page 1", "evidence_span": f"Introduction motivates Method-P{idx:03d} for the Benchmark-X challenge and names the problem gap."}],
                    "problem_setting": [{"source_ref": f"src-p{idx:03d}", "location": "Problem formulation, page 2", "evidence_span": "The task setting defines observation input, goal conditioning, and action or answer output."}],
                    "method_pipeline": [{"source_ref": f"src-p{idx:03d}", "location": "Method section, pages 4-5", "evidence_span": f"The method section presents Method-P{idx:03d} with an encoder, memory module, retriever, and controller pipeline."}],
                    "benchmark_or_dataset": [{"source_ref": f"src-p{idx:03d}", "location": "Evaluation section, page 7", "evidence_span": "The evaluation section uses Benchmark-X and reports the dataset, environment, protocol, metric, baseline, and ablation setup."}],
                    "implementation_details": [{"source_ref": f"src-p{idx:03d}", "location": "Implementation details, page 6", "evidence_span": f"Implementation details describe Method-P{idx:03d}, the encoder backbone, structured store, retriever, planner, and inference setup."}],
                    "experimental_setup": [{"source_ref": f"src-p{idx:03d}", "location": "Experiments, page 7", "evidence_span": "Experiments specify Benchmark-X, success metric, no-memory baseline, no-retrieval ablation, and diagnostic protocol."}],
                    "main_results": [{"source_ref": f"src-p{idx:03d}", "location": "Results, Table 2", "evidence_span": f"Table 2 result shows Method-P{idx:03d} improves Benchmark-X success metric compared with the no-memory baseline."}],
                    "limitations_and_confounders": [{"source_ref": f"src-p{idx:03d}", "location": "Limitations, page 9", "evidence_span": "The limitations section discusses perception confounders, controller capacity, and deployment-time failure risks."}],
                    "relation_to_prior_work": [{"source_ref": f"src-p{idx:03d}", "location": "Related Work, page 3", "evidence_span": "Related work states that the method extends prior context-only systems and compares against previous memory baselines."}],
                },
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
                "named_entities": [{"name": "Verified Paper 1", "paper_id": "p001"}],
                "cited_paper_ids": ["p001"],
                "support_relation": "direct",
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
                    "centrality": "core",
                    "supporting_a_b_papers": ["p001", "p002"],
                    "why_in_scope": f"{name} is a core evaluation context supported by A/B full-text papers.",
                }
                for name in ["navigation", "EQA", "manipulation", "VLA", "lifelong"]
            ]
        }

    def taxonomy_alignment(self, count: int = 6) -> list[dict]:
        records = [
            {
                "exemplar_id": "survey-001",
                "paper_id": "p153",
                "title": "Verified Related Survey",
                "survey_type": "field survey",
                "verified": True,
                "source_ref": "src-p001",
                "why_selected_as_top_related_survey": "It is a top related survey because it defines the main taxonomy and evaluation scope for this field.",
                "coverage_overlap": "It overlaps on retrieval memory, structured map memory, and benchmark evaluation coverage.",
                "coverage_gap": "It does not cover controller-facing evidence flow or wrong-evidence diagnostic controls.",
                "taxonomy_delta": "The article taxonomy keeps the retrieval/map split but reorganizes it around evidence-to-action interfaces.",
                "article_taxonomy_necessity": "This taxonomy is necessary because A/B papers require connecting mechanism evidence to action-facing evaluation.",
                "section_extractions": [
                    {"section": "Taxonomy", "source_ref": "src-p001", "summary": "The survey separates retrieval memory from map memory."},
                    {"section": "Evaluation", "source_ref": "src-p001", "summary": "The survey evaluates methods by benchmark and task scope."},
                ],
                "taxonomy_evidence": {"source_ref": "src-p001", "location": "Section 2", "summary": "The taxonomy is extracted from the related survey."},
                "existing_taxonomy": ["retrieval memory", "structured map memory", "episodic policy memory"],
                "article_taxonomy_mapping": [
                    {"article_category": "retrieval memory", "exemplar_category": "retrieval memory", "agreement": "shared category", "why_delta_is_needed": "the article adds controller-facing evidence checks", "supporting_a_b_papers": ["p001", "p002"]},
                    {"article_category": "structured map memory", "exemplar_category": "structured map memory", "delta": "article emphasizes stale-state evidence", "why_delta_is_needed": "A/B papers require map ablations and result evidence", "supporting_a_b_papers": ["p003", "p004"]},
                ],
                "agreement": "The survey shares the retrieval/map split.",
                "delta": "The article adds evidence-to-controller implications.",
                "article_delta": "The article turns the existing taxonomy into evidence-to-controller comparison.",
                "why_delta_is_justified": "A/B papers show controller-facing evidence claims that the exemplar does not organize explicitly.",
            },
            {
                "exemplar_id": "survey-002",
                "paper_id": "p154",
                "title": "Verified Evaluation Roadmap",
                "survey_type": "evaluation roadmap",
                "verified": True,
                "source_ref": "src-p002",
                "why_selected_as_top_related_survey": "It is a top related survey because it defines evaluation protocols and benchmark coverage.",
                "coverage_overlap": "It overlaps on retrieval evaluation, map evaluation, policy memory evaluation, and benchmark recipes.",
                "coverage_gap": "It leaves the causal link between retrieved evidence and downstream control under-specified.",
                "taxonomy_delta": "The article taxonomy separates benchmark pressure from causal evidence strength.",
                "article_taxonomy_necessity": "This taxonomy is necessary because benchmark success alone does not prove memory causality.",
                "section_extractions": [
                    {"section": "Methods", "source_ref": "src-p002", "summary": "The roadmap distinguishes retrieval and policy-memory evaluations."},
                    {"section": "Benchmarks", "source_ref": "src-p002", "summary": "The roadmap describes benchmark and ablation expectations."},
                ],
                "taxonomy_evidence": {"source_ref": "src-p002", "location": "Figure 1", "summary": "The roadmap taxonomy is extracted from a figure."},
                "existing_taxonomy": ["retrieval evaluation", "map evaluation", "policy memory evaluation"],
                "article_taxonomy_mapping": [
                    {"article_category": "retrieval memory", "existing_category": "retrieval evaluation", "agreement": "shared retrieval evidence concern", "why_delta_is_needed": "the article links retrieval evidence to action-facing interfaces", "supporting_a_b_papers": ["p001", "p002"]},
                    {"article_category": "episodic policy memory", "existing_category": "policy memory evaluation", "delta": "article separates benchmark pressure from causal evidence", "why_delta_is_needed": "A/B papers show benchmark results and remaining confounders", "supporting_a_b_papers": ["p005", "p006"]},
                ],
                "agreement": "Both use evaluation categories to separate method evidence.",
                "delta": "The article makes causal evidence limits explicit.",
                "article_delta": "The article adds claim-strength and confounder boundaries to the roadmap.",
                "why_delta_is_justified": "A/B papers show that benchmark success does not by itself prove memory causality.",
            }
        ]
        while len(records) < count:
            base = dict(records[len(records) % 2])
            idx = len(records) + 1
            base["exemplar_id"] = f"survey-{idx:03d}"
            base["paper_id"] = f"p{152 + idx:03d}"
            base["title"] = f"Verified Related Survey {idx}"
            base["source_ref"] = f"src-p{idx:03d}"
            base["why_selected_as_top_related_survey"] = f"Survey {idx} is selected as a top related survey because it covers a distinct taxonomy and benchmark slice."
            base["coverage_overlap"] = "It overlaps on method taxonomy, benchmark scope, and evaluation assumptions."
            base["coverage_gap"] = "It leaves scenario-specific evidence flow and diagnostic controls outside its main coverage."
            base["taxonomy_delta"] = "The article taxonomy adds evidence-to-action interfaces and claim-strength boundaries."
            base["article_taxonomy_necessity"] = "This taxonomy is necessary to connect paper mechanisms, benchmark evidence, and survey-level claims."
            base["section_extractions"] = [
                {"section": "Taxonomy", "source_ref": f"src-p{idx:03d}", "summary": f"Survey {idx} records taxonomy categories."},
                {"section": "Evaluation", "source_ref": f"src-p{idx:03d}", "summary": f"Survey {idx} records benchmark and evaluation scope."},
            ]
            base["taxonomy_evidence"] = {"source_ref": f"src-p{idx:03d}", "location": "Section 2", "summary": "Taxonomy evidence is extracted from the related survey."}
            records.append(base)
        return records[:count]

    def comparative_evidence_matrix(self) -> list[dict]:
        return [
            {
                "recommendation_id": "eval-recipe-1",
                "recommendation": "Minimum evaluation recipe should report protocol, metric, baseline, ablation, and confounder.",
                "supporting_papers": ["p001", "p002"],
                "paper_evidence": [
                    {"paper_id": "p001", "protocol": "reported", "metric": "reported", "baseline": "reported", "ablation": "reported", "confounder": "discussed"},
                    {"paper_id": "p002", "protocol": "reported", "metric": "reported", "baseline": "missing", "ablation": "missing", "confounder": "discussed"},
                ],
                "derived_gap": "Existing papers report protocols and metrics unevenly; missing baselines and ablations motivate the recipe.",
                "evidence_refs": ["claim_evidence_spans:c1"],
            }
        ]

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
        titles = ["Introduction", "Related Surveys", "Method Families", "Benchmark and Evaluation", "Evidence and Limitations", "Design Guidance", "Open Problems"]
        return [
            {
                "section_id": f"S{idx}",
                "title": title,
                "argument_node": "A1" if idx <= 2 else ("A2" if idx == 3 else "A3"),
                "section_claim": f"{title} connects mechanisms, evidence, and limitations.",
                "scenario_definitions_used": ["EQA"],
                "method_families_used": ["retrieval memory"] if idx > 1 else [],
                "anchor_papers": ["p001"],
                "supporting_papers": ["p026"],
                "benchmarks": ["EQA-Bench"] if idx > 1 else [],
                "required_comparisons": ["evidence strength vs overclaim risk"],
                "must_include_evidence_spans": ["c1"],
                "must_not_overclaim": ["do not overstate causal memory claims"],
                "protocol": "compare no-memory, oracle evidence, and wrong evidence" if title == "Benchmark and Evaluation" else "",
                "metric": "accuracy and groundedness" if title == "Benchmark and Evaluation" else "",
                "baseline": "closed-book answerer" if title == "Benchmark and Evaluation" else "",
                "confounder": "language priors" if title == "Benchmark and Evaluation" else "",
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
            "## Article Body Sections\n- Introduction\n- Related Surveys\n- Method Families\n- Benchmark and Evaluation\n- Evidence and Limitations\n- Design Guidance\n- Open Problems\n\n"
            "## Article Displays\n- Taxonomy roadmap figure\n- Method evolution timeline figure\n- Data ecosystem figure or table\n- Evaluation protocol matrix\n- Method comparison table\n- Benchmark protocol table\n\n"
            "## Appendix Sections\n- Search protocol\n- Broad coverage matrix\n\n"
            "## Internal Only\n- Keep source routes, evidence labels, run counts, and repair notes out of survey.md.\n"
        )

    def review_text(self, repeat: int = 8) -> str:
        sections = []
        for title in ["Introduction", "Related Surveys", "Method Families", "Benchmark and Evaluation", "Evidence and Limitations", "Design Guidance", "Open Problems"]:
            body = []
            for idx in range(repeat):
                related = (
                    f"Existing related surveys [@p001] [@p002] [@p003] [@p004] define their taxonomy and scope differently in pass {idx}; this survey compares existing coverage overlap, coverage gap, taxonomy delta, and why this article taxonomy is needed before explaining the article spine. "
                    if title == "Related Surveys"
                    else ""
                )
                body.append(
                    f"In {title}, pass {idx} starts from a clear thesis: memory is useful only when prior evidence changes a later decision. "
                    f"{related}"
                    f"The comparison matters in {title} pass {idx} because two methods can share a benchmark label while using different pipelines, evaluation baselines, and limitations. "
                    f"Instead of listing papers, the {title} prose in pass {idx} explains motivation, mechanism, experimental support, and confounders for this specific section. "
                    f"Therefore, {title} pass {idx} closes by linking method design to evidence and evaluation choices through a distinct implication.\n\n"
                    f"The comparison table for {title} pass {idx} is introduced as a publication-ready synthesis of mechanism and evidence.\n\n"
                    "| Family | Mechanism | Evidence | Limitation |\n| --- | --- | --- | --- |\n"
                    f"| Retrieval {idx} | writes and reads structured evidence | no-memory comparison | perception confounder |\n\n"
                    f"The table shows that method labels are insufficient in {title} pass {idx}. A reader in {title} pass {idx} should compare what evidence is written, how it is retrieved, which baseline is used, and what limitation remains.\n\n"
                    f"A minimum evaluation recipe specifies protocol, metric, baseline, ablation, and confounder before the article interprets benchmark success for {title} pass {idx}.\n\n"
                )
            sections.append(f"## {title}\n{''.join(body)}")
        conclusion = (
            "## Conclusion\n"
            "This section starts from a clear thesis: memory is useful only when prior evidence changes a later decision. "
            "The comparison matters because two methods can share a benchmark label while using different pipelines, evaluation baselines, and limitations. "
            "Instead of listing papers, the prose explains motivation, mechanism, experimental support, and confounders. "
            "Therefore, the section closes by linking method design to evidence and evaluation choices.\n\n"
        )
        return "# Survey\n\n" + "".join(sections) + conclusion

    def expansion_audit(self, status: str = "pending", evidence: bool = True) -> list[dict]:
        item = {
            "section": "Method Families",
            "problem_type": "underexplained_mechanism",
            "current_quote": "The current text names retrieval memory but does not explain the mechanism.",
            "why_expansion_is_needed": "The reader cannot tell how the method writes, retrieves, and evaluates evidence.",
            "allowed_expansion": "Add a concise mechanism explanation and benchmark-boundary sentence without changing the taxonomy spine.",
            "required_evidence_refs": ["paper_mechanism_cards:p001", "claim_evidence_spans:c1"],
            "must_not_change": "Do not change the central thesis, section order, or method-family taxonomy.",
            "estimated_added_words": 180,
            "status": status,
        }
        if evidence:
            item["evidence_rechecked"] = [
                {
                    "source": "paper_mechanism_cards",
                    "id": "p001",
                    "finding": "The full-text card supports a mechanism-level clarification.",
                    "supports_expansion": True,
                }
            ]
        else:
            item["required_evidence_refs"] = []
        return [item]

    def expert_reviews(self, score: float = 8.8, weaknesses: list[dict] | None = None) -> list[dict]:
        sections = ["Introduction", "Related Surveys", "Method Families", "Benchmark and Evaluation", "Evidence and Limitations", "Design Guidance", "Open Problems", "Conclusion"]
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
            return {"paper_mechanism_audits": [{"paper_id": f"p{idx:03d}", "verdict": "consistent", "field_evidence_consistency": "method, benchmark, and result fields match full-text evidence spans.", "finding": "Mechanism wording matches the full-text card."} for idx in range(1, 11)]}
        if persona == "Survey Architect Reviewer":
            return {"flow_taxonomy_audit": {"section_flow": "The article progresses from motivation to taxonomy, evidence, and open problems.", "taxonomy_coherence": "The taxonomy compares mechanisms and interfaces.", "synthesis_vs_catalog": "Tables are interpreted and not used as paper dumps.", "core_family_coverage": "Selected core families have discovery routes, A/B support, and related-survey delta justification.", "related_survey_delta": "The article explains how its taxonomy differs from existing surveys."}}
        if persona == "Evidence/Factuality Reviewer":
            return {"claim_citation_audits": [{"claim_id": "c1", "paper_id": f"p{idx:03d}", "verdict": "supported", "named_entity_alignment": "Named method and benchmark aliases match the citation window.", "finding": "The claim is tied to a full-text span."} for idx in range(1, 11)]}
        if persona == "Newcomer/Tutorial Reviewer":
            return {"tutorial_audit": {"glossary_clarity": "Terms are clear enough for a new reader.", "running_example_usefulness": "The running example connects memory and evaluation.", "confusing_terms": "Remaining confusing terms are named and explained."}}
        return {"style_audit": {"repetition": "Repeated claims are controlled through section-specific implications.", "artifact_leakage": "No workflow language remains in the publication-facing article body.", "table_interpretation": "Tables are introduced and interpreted with prose before and after each display.", "transition_quality": "Transitions connect the prior evidence to the next argument step.", "padding": "No section pads word count without evidence-backed clarification.", "candidate_final_boundary": "The reviewer checked that candidate artifacts are not represented as final release artifacts."}}

    def expert_invocations(self, returned: bool = True) -> list[dict]:
        return [
            {
                "review_round_id": "round-1",
                "reviewer_id": reviewer_id,
                "persona": persona,
                "fresh_context": True,
                "subagent_session_id": f"subagent-{reviewer_id}",
                "inputs": ["outputs/survey_candidate.md", "outputs/appendix.md", "state/paper_mechanism_cards.jsonl"],
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
                "frozen_artifacts": {"outputs/survey_candidate.md": "hash-survey", "outputs/appendix.md": "hash-appendix", "state/argument_graph.yml": "hash-argument", "state/section_evidence_plans.jsonl": "hash-section-plans"},
                "article_hash": "hash-survey",
            },
            "all_reports_received": returned == 5,
            "reviewers_expected": 5,
            "reviewers_returned": returned,
            "repaired_article_hash": repaired_hash,
        }

    def weakness(self, weakness_id: str = "w1") -> dict:
        return {
            "weakness_id": weakness_id,
            "severity": "major",
            "evidence_quote": "The section reads like a paper list.",
            "why_it_matters": "It fails synthesis.",
            "route_to": "synthesis_dossiers",
            "repair_action": "rebuild method-family comparison",
            "affected_sections": ["Method Families"],
            "affected_papers": ["p001"],
            "affected_claims": ["c1"],
        }

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
                "changed_artifacts": ["outputs/method_family_dossiers/retrieval_memory.json", "outputs/survey_candidate.md"],
                "evidence": "The method family now compares alternatives, trade-offs, and evidence limits.",
                "claim_strength_changes": [],
                "new_or_modified_claims": [],
            }
        ]

    def regression_checks(self, weakness_id: str = "w1") -> list[dict]:
        return [{"weakness_id": weakness_id, "status": "passed", "command": "python3 -m unittest tests/test_scripts.py", "result": "OK"}]

    def runtime_repair_result(self, batch: dict, task_dir: Path) -> dict:
        repair_records = []
        regression_checks = []
        changed_artifacts = sorted({artifact for item in batch.get("repair_items") or [] for artifact in item.get("changed_artifacts") or []})
        for item in batch.get("repair_items") or []:
            repair = self.repair_actions(str(item.get("weakness_id") or "CW001"))[0]
            repair["route_to"] = item.get("route_to")
            repair["changed_artifacts"] = item.get("changed_artifacts") or repair["changed_artifacts"]
            repair_records.append(repair)
            regression_checks.append(self.regression_checks(str(item.get("weakness_id") or "CW001"))[0])
        return {
            "batch_id": batch.get("batch_id"),
            "status": "resolved",
            "changed_artifacts": changed_artifacts,
            "artifact_hashes_before": {artifact: f"before:{artifact}" for artifact in changed_artifacts},
            "artifact_hashes_after": {artifact: sha256_artifact(task_dir, artifact) for artifact in changed_artifacts},
            "repair_records": repair_records,
            "regression_checks": regression_checks,
            "validator_results": [
                {"validator": validator, "command": validator, "status": "passed", "result": "OK"}
                for validator in batch.get("acceptance_validators") or []
            ],
            "remaining_blockers": [],
        }

    def populate_source_verified_task(self, task_dir: Path) -> None:
        state = task_dir / "state"
        self.write_topic_profile(task_dir)
        raw_candidates = self.raw_candidates()
        papers = self.papers()
        citation_plan = self.citation_plan()
        write_jsonl(state / "raw_candidates.jsonl", raw_candidates)
        write_jsonl(state / "search_routes.jsonl", self.search_routes())
        write_jsonl(state / "lqs_scores.jsonl", self.lqs_scores())
        (state / "corpus_expansion.json").write_text(json.dumps(self.corpus_expansion()), encoding="utf-8")
        write_jsonl(state / "papers.jsonl", papers)
        write_jsonl(state / "citation_plan.jsonl", citation_plan)
        write_jsonl(state / "topic_relevance_audit.jsonl", self.topic_relevance_audit(raw_candidates, papers, citation_plan))

    def populate_topic_fixture_task(self, task_dir: Path, fixture_name: str, include_audit: bool = True) -> None:
        fixture = ROOT / "tests" / "fixtures" / "topic_relevance" / fixture_name
        state = task_dir / "state"
        for filename in [
            "task_spec.md",
            "survey_type_plan.yml",
            "raw_candidates.jsonl",
            "papers.jsonl",
            "citation_plan.jsonl",
            "search_routes.jsonl",
            "lqs_scores.jsonl",
            "corpus_expansion.json",
        ]:
            shutil.copyfile(fixture / filename, state / filename)
        audit = state / "topic_relevance_audit.jsonl"
        if include_audit:
            shutil.copyfile(fixture / "topic_relevance_audit.jsonl", audit)
        else:
            audit.write_text("", encoding="utf-8")
        second_audits = fixture / "topic_relevance_second_audits.jsonl"
        if second_audits.exists():
            shutil.copyfile(second_audits, state / "topic_relevance_second_audits.jsonl")
        self.write_topic_profile(task_dir, topic="mllm think with image")

    def paper_understanding_result(self, batch: dict, task_dir: Path, status: str = "resolved") -> dict:
        paper_ids = [str(pid) for pid in batch.get("paper_ids") or []]
        max_idx = max(int(pid[1:]) for pid in paper_ids)
        cards_by_id = {card["paper_id"]: card for card in self.mechanism_cards(max_idx)}
        sources_by_id = {source["paper_id"]: source for source in self.full_text_sources(max_idx)}
        new_cards = [cards_by_id[pid] for pid in paper_ids]
        new_sources = [sources_by_id[pid] for pid in paper_ids]
        card_path = task_dir / "state/paper_mechanism_cards.jsonl"
        source_path = task_dir / "state/full_text_sources.jsonl"
        existing_cards = [json.loads(line) for line in card_path.read_text(encoding="utf-8").splitlines() if line.strip()] if card_path.exists() else []
        existing_sources = [json.loads(line) for line in source_path.read_text(encoding="utf-8").splitlines() if line.strip()] if source_path.exists() else []
        merged_cards = [row for row in existing_cards if str(row.get("paper_id")) not in paper_ids] + new_cards
        merged_sources = [row for row in existing_sources if str(row.get("paper_id")) not in paper_ids] + new_sources
        return {
            "batch_id": batch.get("batch_id"),
            "status": status,
            "paper_ids": paper_ids,
            "full_text_sources": new_sources,
            "paper_mechanism_cards": new_cards,
            "artifact_hashes_before": {
                "state/full_text_sources.jsonl": sha256_artifact(task_dir, "state/full_text_sources.jsonl"),
                "state/paper_mechanism_cards.jsonl": sha256_artifact(task_dir, "state/paper_mechanism_cards.jsonl"),
            },
            "artifact_hashes_after": {
                "state/full_text_sources.jsonl": sha256_jsonl_rows(merged_sources),
                "state/paper_mechanism_cards.jsonl": sha256_jsonl_rows(merged_cards),
            },
            "validator_results": [
                {"validator": validator, "command": validator, "status": "passed", "result": "OK"}
                for validator in batch.get("acceptance_validators") or []
            ],
            "unavailable_or_downgrade_candidates": [],
            "remaining_blockers": [],
        }

    def targeted_rereviews(self, weakness_id: str = "w1", verdict: str = "resolved", article_hash: str = "hash-after-repair") -> list[dict]:
        return [
            {
                "weakness_id": weakness_id,
                "reviewer_id": "survey_architect",
                "persona": "Survey Architect Reviewer",
                "checked_changed_artifacts": ["outputs/survey_candidate.md", "outputs/method_family_dossiers/retrieval_memory.json"],
                "checked_evidence_refs": ["outputs/contribution_tree.yml", "state/argument_graph.yml"],
                "verdict": verdict,
                "evidence_quote_after_repair": "The repaired method section compares retrieval memory with structured map memory.",
                "remaining_risk": "No blocking risk remains after targeted rereview.",
                "article_hash": article_hash,
                "fresh_context": True,
                "subagent_session_id": "subagent-targeted-rereview",
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
        self.write_topic_profile(task_dir)
        raw_candidates = self.raw_candidates()
        papers = self.papers()
        citation_plan = self.citation_plan()
        write_jsonl(state / "raw_candidates.jsonl", raw_candidates)
        write_jsonl(state / "search_routes.jsonl", self.search_routes())
        write_jsonl(state / "lqs_scores.jsonl", self.lqs_scores())
        (state / "corpus_expansion.json").write_text(json.dumps(self.corpus_expansion()), encoding="utf-8")
        write_jsonl(state / "papers.jsonl", papers)
        write_jsonl(state / "citation_plan.jsonl", citation_plan)
        write_jsonl(state / "topic_relevance_audit.jsonl", self.topic_relevance_audit(raw_candidates, papers, citation_plan))
        write_jsonl(state / "paper_mechanism_cards.jsonl", self.mechanism_cards())
        write_jsonl(state / "full_text_sources.jsonl", self.full_text_sources())
        write_jsonl(state / "paper_contribution_statements.jsonl", self.contribution_statements())
        write_jsonl(state / "claim_evidence_spans.jsonl", self.claims())
        write_jsonl(state / "taxonomy_alignment.jsonl", self.taxonomy_alignment())
        write_jsonl(state / "comparative_evidence_matrix.jsonl", self.comparative_evidence_matrix())
        write_jsonl(state / "expansion_audit.jsonl", self.expansion_audit("addressed"))
        write_jsonl(state / "expert_review_reports.jsonl", self.expert_reviews())
        write_jsonl(state / "expert_review_invocations.jsonl", self.expert_invocations())
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
        (outputs / "survey_body_draft.md").write_text(self.review_text(repeat=7), encoding="utf-8")
        (outputs / "survey_candidate.md").write_text(self.review_text(), encoding="utf-8")
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
        render_survey_html(task_dir)

    def test_discovery_and_source_contracts(self):
        weak = validate_coverage(self.raw_candidates(30), self.search_routes(2), self.lqs_scores(30), self.corpus_expansion(), self.papers(20), self.citation_plan(2, 4, 14), "full")
        self.assertFalse(weak["valid"])
        self.assertFalse(weak["discovery_sufficient"])
        expansion = validate_coverage(self.raw_candidates(), self.search_routes(), self.lqs_scores(), self.corpus_expansion(True, "pending"), self.papers(), self.citation_plan(), "full")
        self.assertFalse(expansion["valid"])
        unlinked = self.papers()
        unlinked[0].pop("source_candidate_id")
        linkage = validate_coverage(self.raw_candidates(), self.search_routes(), self.lqs_scores(), self.corpus_expansion(), unlinked, self.citation_plan(), "full")
        self.assertFalse(linkage["valid"])
        self.assertIn("paper_candidate_linkage", linkage["retained_missing"])
        papers = self.papers(3, 0)
        papers[1]["verification_status"] = "unverified"
        self.assertFalse(validate_sources(papers, [{"paper_id": "p001", "depth": "A"}, {"paper_id": "p002", "depth": "B"}], "full")["valid"])
        scored = score_paper({"paper_id": "p1", "survey_role": "seminal", "conceptual_centrality": 10, "mechanism_clarity": 8})
        self.assertEqual(scored["lqs_model"], "survey-role")
        self.assertNotEqual(classify_depth(scored, role="section protagonist"), "D")
        self.assertEqual(classify_depth({**scored, "topic_allowed_depth": "C"}, role="section protagonist"), "C")

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
        missing_field_evidence = self.mechanism_cards(1)
        missing_field_evidence[0]["field_evidence_map"].pop("main_results")
        cases["missing_field_evidence_map"] = missing_field_evidence
        title_only_alias = self.mechanism_cards(1)
        title_only_alias[0]["entity_aliases"] = [{"name": "Verified Paper 1", "type": "paper_title", "source_ref": "src-p001", "evidence": "paper title"}]
        cases["title_only_entity_aliases"] = title_only_alias
        boilerplate = [dict(card) for card in self.mechanism_cards(1)]
        boilerplate[0]["motivation"] = "We thank the supercomputing allocation and funding agencies for supporting this work."
        cases["boilerplate_motivation"] = boilerplate
        weak_result_evidence = self.mechanism_cards(1)
        weak_result_evidence[0]["field_evidence_map"]["main_results"] = [{"source_ref": "src-p001", "location": "Section 4, page 7", "evidence_span": "The evaluation discusses the system in broad terms without a metric, baseline, table, figure, comparison, or reported result."}]
        cases["main_result_without_result_evidence"] = weak_result_evidence
        missing_benchmark_entity = self.mechanism_cards(1)
        missing_benchmark_entity[0]["benchmark_or_dataset"] = ["Benchmark-Y"]
        missing_benchmark_entity[0]["field_evidence_map"]["benchmark_or_dataset"] = [{"source_ref": "src-p001", "location": "Evaluation section, page 7", "evidence_span": "The evaluation section reports protocol, metric, baseline, and ablation setup without naming the claimed benchmark."}]
        cases["benchmark_field_not_supported_by_evidence"] = missing_benchmark_entity
        duplicate_templates = self.mechanism_cards(2)
        for card in duplicate_templates:
            card["method_pipeline"] = ["encode observation", "write record", "retrieve evidence", "act or answer"]
            card["limitations_and_confounders"] = ["generic limitation one", "generic limitation two"]
            card["main_results"] = [{"result": "The method improves the benchmark.", "evidence_span": "Section 4, Table 2.", "claim_strength": "shows"}]
        cases["duplicate_template_cards"] = duplicate_templates
        template_card = self.mechanism_cards(1)
        template_card[0]["method_pipeline"] = [
            "The card records how the paper fits the survey taxonomy.",
            "The card records how the evidence should be used.",
            "The card records how the article discusses the method.",
        ]
        template_card[0]["field_evidence_map"]["method_pipeline"] = [{"source_ref": "src-p001", "location": "Section 3, page 4", "evidence_span": "The card records how the paper fits the survey taxonomy rather than extracting the actual method."}]
        cases["template_card_records_how"] = template_card
        missing_survey_use = self.mechanism_cards(1)
        missing_survey_use[0]["what_it_changes_in_the_survey_argument"] = ""
        missing_survey_use[0]["possible_sections"] = []
        missing_survey_use[0]["one_sentence_contribution"] = ""
        cases["missing_survey_use_tree_utility"] = missing_survey_use
        for name, cards in cases.items():
            with self.subTest(name=name):
                citation_plan = [{"paper_id": "p001", "depth": "A"}]
                if name == "duplicate_template_cards":
                    citation_plan.append({"paper_id": "p002", "depth": "A"})
                status = validate_paper_understanding(cards, citation_plan, self.full_text_sources(2))
                self.assertFalse(status["valid"], status)
                if name == "missing_survey_use_tree_utility":
                    self.assertIn("missing_survey_use_changes_knowledge_tree", status["invalid_cards"]["p001"])
                    self.assertIn("missing_possible_sections", status["invalid_cards"]["p001"])
                    self.assertIn("missing_one_sentence_contribution", status["invalid_cards"]["p001"])

    def test_claim_evidence_contract(self):
        base_claim = self.claims()[0]
        bad_cases = {
            "missing_span": [{**base_claim, "evidence_spans": []}],
            "overclaim": [{**base_claim, "strength": "demonstrates", "evidence_spans": [{**base_claim["evidence_spans"][0], "strength": "suggests"}]}],
            "metadata_only_support": [{**base_claim, "evidence_spans": [{**base_claim["evidence_spans"][0], "section_or_page": "Semantic Scholar metadata", "excerpt": "metadata"}]}],
            "named_paper_mismatch": [{**base_claim, "named_entities": [{"name": "Verified Paper 2", "paper_id": "p002"}], "cited_paper_ids": ["p001"]}],
            "pseudo_section_level_span": [{**base_claim, "evidence_spans": [{**base_claim["evidence_spans"][0], "excerpt": "Section-level full-text evidence says this section is supported.", "evidence_summary": "Section-level full-text evidence supports the section."}]}],
            "source_ref_not_backed_by_captured_excerpt": [{**base_claim, "evidence_spans": [{**base_claim["evidence_spans"][0], "excerpt": "This invented excerpt is not present in the captured full-text audit.", "evidence_summary": "Invented excerpt summary."}]}],
        }
        for name, claims in bad_cases.items():
            with self.subTest(name=name):
                self.assertFalse(validate_claim_evidence(claims, self.mechanism_cards(2), self.section_evidence_plans(), full_text_sources=self.full_text_sources(2), article_text="Verified Paper 2 shows a result [@p001].")["valid"])
        article_mismatch = validate_claim_evidence(self.claims(), self.mechanism_cards(2), self.section_evidence_plans(), full_text_sources=self.full_text_sources(2), article_text="Verified Paper 2 shows a result [@p001].")
        self.assertFalse(article_mismatch["valid"])
        named_cards = self.mechanism_cards(4)
        for card, alias in zip(named_cards, ["Visual Sketchpad", "OpenThinkIMG", "DeepEyes", "VTool-R1"]):
            card["entity_aliases"].append({"name": alias, "type": "method", "source_ref": f"src-{card['paper_id']}", "evidence": "The full text names this system."})
        bad_names = validate_claim_evidence(
            self.claims(),
            named_cards,
            self.section_evidence_plans(),
            full_text_sources=self.full_text_sources(4),
            article_text="Visual Sketchpad, OpenThinkIMG, DeepEyes, and VTool-R1 show a shared pattern [@p001] [@p002].",
        )
        self.assertFalse(bad_names["valid"])
        self.assertIn("named_paper_citation_alignment", bad_names["errors"])
        self.assertTrue(any("named_paper_citation_mismatch" in item for item in bad_names["article_alignment_errors"]))
        unknown_name = validate_claim_evidence(
            self.claims(),
            self.mechanism_cards(1),
            self.section_evidence_plans(),
            full_text_sources=self.full_text_sources(1),
            article_text="UnregisteredVisionTool improves this line of work [@p001].",
        )
        self.assertFalse(unknown_name["valid"])
        self.assertTrue(any("unregistered_named_entity_near_citation" in item for item in unknown_name["article_alignment_errors"]))
        self.assertTrue(validate_claim_evidence(self.claims(), self.mechanism_cards(1), self.section_evidence_plans(), full_text_sources=self.full_text_sources(1), article_text="Verified Paper 1 shows a result [@p001].")["valid"])

    def test_synthesis_and_argument_contracts(self):
        self.assertTrue(validate_contribution_tree(self.contribution_statements(), json.dumps(self.contribution_tree()), self.citation_plan(), self.argument_graph(), "full")["valid"])
        self.assertFalse(validate_contribution_tree(self.contribution_statements(10), json.dumps({"branches": []}), self.citation_plan(), self.argument_graph(), "full")["valid"])
        self.assertTrue(validate_scenario_definitions(json.dumps(self.scenario_definitions()), "full", self.mechanism_cards())["valid"])
        self.assertFalse(validate_scenario_definitions(json.dumps({"scenarios": [{"scenario": "navigation"}]}), "full")["valid"])
        peripheral = self.scenario_definitions()
        peripheral["scenarios"][0].update({"centrality": "core", "supporting_a_b_papers": [], "why_in_scope": ""})
        self.assertFalse(validate_scenario_definitions(json.dumps(peripheral), "full", self.mechanism_cards())["valid"])
        unsupported = self.scenario_definitions()
        unsupported["scenarios"][0]["supporting_a_b_papers"] = ["p001"]
        cards_without_scenario = self.mechanism_cards(2)
        cards_without_scenario[0]["scenario_links"] = []
        cards_without_scenario[0]["task_definition"] = {"input": "generic observation", "output": "generic action"}
        cards_without_scenario[0]["benchmark_or_dataset"] = ["Generic-Bench"]
        for entries in cards_without_scenario[0]["field_evidence_map"].values():
            for entry in entries:
                entry["evidence_span"] = "Generic full-text evidence without the requested scenario."
        scenario_status = validate_scenario_definitions(json.dumps(unsupported), "full", cards_without_scenario)
        self.assertFalse(scenario_status["valid"])
        self.assertIn("scenario_support_not_evidence_backed:p001", scenario_status["invalid_scenarios"]["navigation"])
        self.assertTrue(validate_synthesis_dossiers([self.method_dossier()], [self.benchmark_dossier()], json.dumps(self.scenario_definitions()), self.mechanism_cards(), "full", self.comparative_evidence_matrix())["valid"])
        bad_method = self.method_dossier()
        bad_method["differences_among_representative_papers"] = ""
        self.assertFalse(validate_synthesis_dossiers([bad_method], [self.benchmark_dossier()], json.dumps(self.scenario_definitions()), self.mechanism_cards(), "full", self.comparative_evidence_matrix())["valid"])
        self.assertFalse(validate_synthesis_dossiers([self.method_dossier()], [self.benchmark_dossier()], json.dumps(self.scenario_definitions()), self.mechanism_cards(), "full", [])["valid"])
        self.assertTrue(validate_argument_graph(self.argument_graph(), self.article_plan())["valid"])
        bad_graph = self.argument_graph()
        bad_graph["argument_nodes"]["A2"].pop("section")
        self.assertFalse(validate_argument_graph(bad_graph, self.article_plan())["valid"])

    def test_section_exemplar_and_survey_type_contracts(self):
        self.assertTrue(validate_section_evidence_plans(self.section_evidence_plans(), self.argument_graph(), self.article_plan(), self.claims(), self.mechanism_cards(), "full")["valid"])
        plans = self.section_evidence_plans()
        next(plan for plan in plans if plan["title"] == "Method Families")["required_comparisons"] = []
        self.assertFalse(validate_section_evidence_plans(plans, self.argument_graph(), self.article_plan(), self.claims(), self.mechanism_cards(), "full")["valid"])
        family_mismatch = self.section_evidence_plans()
        next(plan for plan in family_mismatch if plan["title"] == "Method Families")["method_families_used"] = ["unrelated policy gradient"]
        family_status = validate_section_evidence_plans(family_mismatch, self.argument_graph(), self.article_plan(), self.claims(), self.mechanism_cards(), "full")
        self.assertFalse(family_status["valid"])
        self.assertIn("method_family_not_in_argument_node:unrelated policy gradient", family_status["invalid_plans"]["Method Families"])
        claim_paper_mismatch = self.section_evidence_plans()
        next(plan for plan in claim_paper_mismatch if plan["title"] == "Method Families")["anchor_papers"] = ["p050"]
        claim_paper_status = validate_section_evidence_plans(claim_paper_mismatch, self.argument_graph(), self.article_plan(), self.claims(), self.mechanism_cards(), "full")
        self.assertFalse(claim_paper_status["valid"])
        self.assertIn("claim_evidence_papers_not_anchored:c1", claim_paper_status["invalid_plans"]["Method Families"])
        survey_type = "topic: LLM uncertainty quantification\nprimary_type: method-family\nsecondary_lenses:\n  - benchmark/evaluation\nwhy_this_type: method family\nwhy_not_other_types: not a component-only survey\narticle_skeleton:\n  - Introduction\n  - Method Families\n  - Benchmark and Evaluation\nexemplar_alignment: Field Survey Exemplar uses definition -> taxonomy -> data ecosystem -> evaluation -> open challenges.\ncommunity_native_taxonomy:\n  - calibration methods\n  - uncertainty estimation methods\n  - evaluation protocols\nexemplar_section_patterns:\n  - definition\n  - taxonomy\n  - data ecosystem\ncandidate_article_spines:\n  - method-family taxonomy\n  - risk/trust taxonomy\nselected_article_spine: method-family taxonomy\nwhy_not_exemplar_spine: adapted to uncertainty\nfigure_first_plan: taxonomy roadmap; method evolution timeline; data ecosystem; evaluation protocol matrix.\nscience_paradigm_profile: ML systems\nevidence_norms:\n  - calibration evidence must be benchmarked\nrequired_evidence_units:\n  - benchmark\n  - metric\n  - baseline\ncommon_confounders:\n  - dataset shift\n  - prompt sensitivity\nexcluded_templates:\n  - system-component-only survey\n"
        self.assertTrue(validate_exemplar_alignment(survey_type, self.argument_graph(), self.article_plan(), "full", self.taxonomy_alignment(), self.mechanism_cards())["valid"])
        self.assertFalse(validate_exemplar_alignment(survey_type, self.argument_graph(), self.article_plan(), "full", [], self.mechanism_cards())["valid"])
        self.assertTrue(validate_related_survey_alignment(self.taxonomy_alignment(), self.mechanism_cards(), "full")["valid"])
        linked_alignment = self.taxonomy_alignment()
        linked_audit = self.topic_relevance_audit()
        for idx, record in enumerate(linked_alignment, start=1):
            pid = f"p{idx:03d}"
            record["paper_id"] = pid
            audit_row = next(row for row in linked_audit if row["paper_id"] == pid)
            audit_row.update(
                {
                    "relevance_grade": "direct_related_survey",
                    "allowed_depth": "C",
                    "allowed_role": "related_survey",
                    "family_label_supported": False,
                    "corrected_family": "related surveys and field context",
                }
            )
        linked_status = validate_related_survey_alignment(
            linked_alignment,
            self.mechanism_cards(),
            "full",
            papers=self.papers(),
            topic_relevance_audit=linked_audit,
            citation_plan=self.citation_plan(),
        )
        self.assertTrue(linked_status["valid"], linked_status)
        missing_link = self.taxonomy_alignment()
        for record in missing_link:
            record.pop("paper_id", None)
        missing_link_status = validate_related_survey_alignment(
            missing_link,
            self.mechanism_cards(),
            "full",
            papers=self.papers(),
            topic_relevance_audit=linked_audit,
            citation_plan=self.citation_plan(),
        )
        self.assertFalse(missing_link_status["valid"])
        self.assertIn("missing_related_survey_paper_id", missing_link_status["invalid_records"]["survey-001"])
        too_few_full = validate_related_survey_alignment(self.taxonomy_alignment(2), self.mechanism_cards(), "full")
        self.assertFalse(too_few_full["valid"])
        self.assertEqual(too_few_full["target_min_records"], 6)
        too_few_csur = validate_related_survey_alignment(self.taxonomy_alignment(9), self.mechanism_cards(), "csur")
        self.assertFalse(too_few_csur["valid"])
        self.assertEqual(too_few_csur["target_min_records"], 10)
        missing_top_fields = self.taxonomy_alignment()
        missing_top_fields[0].pop("why_selected_as_top_related_survey")
        missing_top_fields[0].pop("coverage_gap")
        missing_top_status = validate_related_survey_alignment(missing_top_fields, self.mechanism_cards(), "full")
        self.assertFalse(missing_top_status["valid"])
        self.assertIn("missing_why_selected_as_top_related_survey", missing_top_status["invalid_records"]["survey-001"])
        self.assertIn("missing_coverage_gap", missing_top_status["invalid_records"]["survey-001"])
        bad_alignment_cases = {
            "too_thin": [dict(self.taxonomy_alignment()[0], section_extractions=[])],
            "no_delta_justification": [dict(self.taxonomy_alignment()[0], why_delta_is_justified=""), self.taxonomy_alignment()[1]],
            "unsupported_mapping": [
                {
                    **self.taxonomy_alignment()[0],
                    "article_taxonomy_mapping": [
                        {**self.taxonomy_alignment()[0]["article_taxonomy_mapping"][0], "supporting_a_b_papers": ["p094"]}
                    ],
                },
                self.taxonomy_alignment()[1],
            ],
        }
        weak_cards = self.mechanism_cards()
        weak_cards[93]["field_evidence_map"]["main_results"] = []
        for name, records in bad_alignment_cases.items():
            with self.subTest(name=name):
                cards = weak_cards if name == "unsupported_mapping" else self.mechanism_cards()
                self.assertFalse(validate_related_survey_alignment(records, cards, "full")["valid"])

    def test_article_quality_contract(self):
        appendix = "# Appendix\n\nSearch protocol and coverage logistics.\n"
        good = validate_article_quality(self.review_text(), self.article_plan(), self.argument_graph(), self.claims(), "full", appendix_text=appendix)
        self.assertTrue(good["valid"], good)
        bad_text = self.review_text() + "\n本文采用 system-object survey 的结构。完整 material 保留在支撑文件中。"
        self.assertFalse(validate_article_quality(bad_text, self.article_plan(), self.argument_graph(), self.claims(), "full")["valid"])
        rendered = validate_article_quality(self.review_text(), self.article_plan(), self.argument_graph(), self.claims(), "full", rendered_artifacts=[("survey.html", "<html>新版 skill 更新版 source_ref full-text A/B audited</html>")])
        self.assertFalse(rendered["valid"])
        no_recipe = self.review_text().replace("protocol, metric, baseline, ablation, and confounder", "paper title and citation")
        self.assertFalse(validate_article_quality(no_recipe, self.article_plan(), self.argument_graph(), self.claims(), "full")["valid"])
        no_related_positioning = self.review_text().replace("Related Surveys", "Background").replace("Existing related surveys", "Prior papers")
        related_status = validate_article_quality(no_related_positioning, self.article_plan(), self.argument_graph(), self.claims(), "full", appendix_text=appendix)
        self.assertFalse(related_status["valid"])
        self.assertIn("missing_related_survey_alignment_section", related_status["errors"])
        no_related_citations = self.review_text().replace("[@p001] [@p002] ", "")
        no_related_citation_status = validate_article_quality(no_related_citations, self.article_plan(), self.argument_graph(), self.claims(), "full", appendix_text=appendix)
        self.assertFalse(no_related_citation_status["valid"])
        self.assertIn("missing_related_survey_citations", no_related_citation_status["errors"])
        too_few_related_citations = self.review_text().replace("[@p003] [@p004] ", "")
        too_few_related_citation_status = validate_article_quality(too_few_related_citations, self.article_plan(), self.argument_graph(), self.claims(), "full", appendix_text="# Appendix\n\nSearch protocol and coverage logistics.\n")
        self.assertFalse(too_few_related_citation_status["valid"])
        self.assertIn("missing_related_survey_citations", too_few_related_citation_status["errors"])
        thin_related_positioning = self.review_text().replace("coverage overlap, coverage gap, taxonomy delta, and why this article taxonomy is needed", "broad related survey context")
        thin_related_status = validate_article_quality(thin_related_positioning, self.article_plan(), self.argument_graph(), self.claims(), "full", appendix_text="# Appendix\n\nSearch protocol and coverage logistics.\n")
        self.assertFalse(thin_related_status["valid"])
        self.assertIn("thin_related_survey_positioning", thin_related_status["errors"])
        short = "# Survey\n\n## Introduction\nA concise but underdeveloped draft.\n"
        short_status = validate_article_quality(short, self.article_plan(), self.argument_graph(), self.claims(), "full", expansion_audit=[])
        self.assertFalse(short_status["valid"])
        self.assertIn("needs_expansion_audit", short_status["errors"])
        invalid_audit = validate_article_quality(short, self.article_plan(), self.argument_graph(), self.claims(), "full", expansion_audit=self.expansion_audit(evidence=False))
        self.assertFalse(invalid_audit["valid"])
        self.assertIn("invalid_expansion_audit", invalid_audit["errors"])
        ready = validate_article_quality(short, self.article_plan(), self.argument_graph(), self.claims(), "full", expansion_audit=self.expansion_audit())
        self.assertFalse(ready["valid"])
        self.assertTrue(ready["expansion_audit_ready"])
        repeated = self.review_text() + "\n\nThis generic paragraph repeats without adding paper evidence or benchmark context.\n" * 4
        repeated_status = validate_article_quality(repeated, self.article_plan(), self.argument_graph(), self.claims(), "full")
        self.assertFalse(repeated_status["valid"])
        self.assertIn("repetitive_filler", repeated_status["errors"])
        after_conclusion = self.review_text() + "\n## Method Appendix That Is Actually Body\nThis body section appears after the conclusion and should fail.\n"
        self.assertFalse(validate_article_quality(after_conclusion, self.article_plan(), self.argument_graph(), self.claims(), "full")["valid"])
        expanded_without_audit = validate_article_quality(self.review_text(), self.article_plan(), self.argument_graph(), self.claims(), "full", draft_text="# Draft\n\n## Introduction\nshort draft\n")
        self.assertFalse(expanded_without_audit["valid"])
        self.assertIn("expansion_provenance_missing", expanded_without_audit["errors"])
        prescriptive = self.review_text() + ("\n未来应当建立新的协议。研究者应该采用更好的方法。本文认为未来应当这样做。\n" * 6)
        self.assertFalse(validate_article_quality(prescriptive, self.article_plan(), self.argument_graph(), self.claims(), "full")["valid"])
        prescriptive_section = self.review_text() + "\n## Research Agenda\n未来应当建立统一协议。研究者应该改进评测。本文认为需要新的任务。Future work should improve robustness. Researchers should report more details.\n\n## Conclusion\nThe survey closes.\n"
        section_padding = validate_article_quality(prescriptive_section, self.article_plan(), self.argument_graph(), self.claims(), "full")
        self.assertFalse(section_padding["valid"])
        self.assertIn("section_prescriptive_padding", section_padding["errors"])
        naked_ids = validate_article_quality(self.review_text() + "\n相关证据见 P001、P008。\n", self.article_plan(), self.argument_graph(), self.claims(), "full")
        self.assertFalse(naked_ids["valid"])
        self.assertIn("bare_internal_paper_ids", naked_ids["errors"])
        self.assertIn("template_evidence_phrasing", naked_ids["errors"])
        premature = validate_article_quality(self.review_text(), self.article_plan(), self.argument_graph(), self.claims(), "full", premature_final_artifacts=["outputs/survey.md"])
        self.assertFalse(premature["valid"])
        self.assertIn("premature_final_survey_artifact", premature["errors"])
        legacy_name = "review" + ".md"
        legacy = validate_article_quality(self.review_text(), self.article_plan(), self.argument_graph(), self.claims(), "full", legacy_artifacts=["outputs/" + legacy_name])
        self.assertFalse(legacy["valid"])
        self.assertIn("legacy_review_artifact_present", legacy["errors"])
        scaffold = validate_article_quality(self.review_text() + "\n在“证据是否可靠”这一问题上，本文给出模板化回答。\n", self.article_plan(), self.argument_graph(), self.claims(), "full")
        self.assertFalse(scaffold["valid"])
        self.assertIn("internal_or_scaffold_language", scaffold["errors"])
        html_note = validate_article_quality(self.review_text(), self.article_plan(), self.argument_graph(), self.claims(), "full", rendered_artifacts=[("survey_candidate.html", "<html><body>HTML reference note: generated references placeholder</body></html>")])
        self.assertFalse(html_note["valid"])
        self.assertIn("rendered_artifact_boundary", html_note["errors"])
        empty_appendix = validate_article_quality(self.review_text(), self.article_plan(), self.argument_graph(), self.claims(), "full", appendix_text="# Appendix\n")
        self.assertFalse(empty_appendix["valid"])
        self.assertIn("empty_appendix", empty_appendix["errors"])
        missing_appendix = validate_article_quality(self.review_text(), self.article_plan(), self.argument_graph(), self.claims(), "full", appendix_text=None)
        self.assertFalse(missing_appendix["valid"])
        self.assertIn("missing_appendix", missing_appendix["errors"])
        empty_string_appendix = validate_article_quality(self.review_text(), self.article_plan(), self.argument_graph(), self.claims(), "full", appendix_text="")
        self.assertFalse(empty_string_appendix["valid"])
        self.assertIn("empty_appendix", empty_string_appendix["errors"])

    def test_coverage_balance_contract(self):
        papers = self.papers(160)
        status = validate_coverage(self.raw_candidates(), self.search_routes(), self.lqs_scores(), self.corpus_expansion(), papers, self.citation_plan(), "full", core_families=["retrieval memory", "structured map memory", "episodic policy memory"])
        self.assertTrue(status["valid"], status)
        route_gap = validate_coverage(self.raw_candidates(), self.search_routes(2), self.lqs_scores(), self.corpus_expansion(), papers, self.citation_plan(), "full", core_families=["retrieval memory", "structured map memory", "episodic policy memory"])
        self.assertFalse(route_gap["valid"])
        self.assertIn("core_family_route_undercovered", route_gap["retained_missing"])
        bad_route_type = self.search_routes()
        bad_route_type[0].pop("route_type")
        route_type_status = validate_coverage(self.raw_candidates(), bad_route_type, self.lqs_scores(), self.corpus_expansion(), papers, self.citation_plan(), "full", core_families=["retrieval memory", "structured map memory", "episodic policy memory"])
        self.assertFalse(route_type_status["valid"])
        self.assertIn("search_route_type_missing", route_type_status["discovery_missing"])
        weak_corpus_audit = self.corpus_expansion()
        weak_corpus_audit["largest_visible_external_count"] = 500
        weak_corpus_audit["why_retained_corpus_is_sufficient"] = ""
        corpus_status = validate_coverage(self.raw_candidates(), self.search_routes(), self.lqs_scores(), weak_corpus_audit, papers, self.citation_plan(), "full", core_families=["retrieval memory", "structured map memory", "episodic policy memory"])
        self.assertFalse(corpus_status["valid"])
        self.assertIn("corpus_expansion_required", corpus_status["discovery_missing"])
        skewed = self.papers(160)
        for idx, paper in enumerate(skewed):
            if idx < 140:
                paper["family"] = "benchmark_evaluation"
                paper["survey_role"] = "benchmark"
            elif idx < 145:
                paper["family"] = "visual_workspace"
            elif idx < 150:
                paper["family"] = "domain_reasoning"
            else:
                paper["family"] = "training_data"
        skew_status = validate_coverage(self.raw_candidates(), self.search_routes(), self.lqs_scores(), self.corpus_expansion(), skewed, self.citation_plan(), "full", core_families=["visual_workspace", "domain_reasoning", "training_data"])
        self.assertFalse(skew_status["valid"])
        self.assertIn("coverage_family_imbalance", skew_status["retained_missing"])
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            write_jsonl(task_dir / "state/papers.jsonl", skewed)
            write_jsonl(task_dir / "state/topic_relevance_audit.jsonl", self.topic_relevance_audit(self.raw_candidates(), skewed, self.citation_plan()))
            phase_status = evaluate_phase_barriers(task_dir, "full")
            self.assertTrue(phase_status["phases"]["discovery"]["passed"])
            self.assertFalse(phase_status["phases"]["source_verification"]["passed"])
            self.assertEqual(phase_status["blocked_by_phase"], "source_verification")
            self.assertEqual(phase_status["allowed_next_phase"], "coverage_repair")
            self.assertIn("coverage_family_imbalance", phase_status["phases"]["source_verification"]["details"]["coverage"]["retained_missing"])

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
        missing_execution = validate_expert_reviews(
            [],
            target="full",
            review_invocations=[],
            repair_actions=[],
            regression_checks=[],
            round_status=self.review_round_status(returned=0),
            adjudication=self.adjudication(),
            targeted_rereviews=[],
        )
        self.assertFalse(missing_execution["valid"], missing_execution)
        self.assertIn("expert_review_not_executed", missing_execution["errors"])
        self.assertIn("no_expert_review_reports_returned", missing_execution["errors"])
        self.assertNotIn("median_score_below_threshold", missing_execution["errors"])
        cases = {
            "missing_persona": dict(reports=self.expert_reviews()[:4], invocations=self.expert_invocations()[:4], errors=["too_few_expert_reviews", "missing_required_personas"]),
            "missing_dimension_audits": dict(mutator=lambda reports: reports[0].pop("dimension_audits"), errors=["invalid_expert_review_reports"]),
            "low_dimension_without_major": dict(mutator=lambda reports: (reports[0]["dimension_audits"][0].update({"score": 7.5, "verdict": "fail"}), reports[0]["dimension_scores"].update({"narrative_coherence": 7.5})), errors=["invalid_expert_review_reports"]),
            "repair_before_all_returned": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), invocations=self.expert_invocations()[:4], repairs=self.repair_actions("w1"), round_status=self.review_round_status(returned=4), adjudication=self.adjudication("w1"), targeted=self.targeted_rereviews("w1"), errors=["repair_before_all_reviews_returned"]),
            "missing_adjudication": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), repairs=self.repair_actions("w1"), adjudication=self.adjudication(), targeted=self.targeted_rereviews("w1"), errors=["unadjudicated_major_weaknesses"]),
            "repair_without_evidence": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), repairs=self.repair_actions("w1", evidence=False), adjudication=self.adjudication("w1"), targeted=self.targeted_rereviews("w1"), errors=["invalid_repair_actions"]),
            "repair_hash_unchanged": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), repairs=self.repair_actions("w1"), round_status=self.review_round_status(repaired_hash="hash-survey"), adjudication=self.adjudication("w1"), targeted=self.targeted_rereviews("w1", article_hash="hash-survey"), errors=["repair_did_not_change_candidate"]),
            "missing_targeted_rereview": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), repairs=self.repair_actions("w1"), adjudication=self.adjudication("w1"), targeted=[], errors=["missing_targeted_rereviews"]),
            "targeted_rereview_hash_mismatch": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), repairs=self.repair_actions("w1"), adjudication=self.adjudication("w1"), targeted=self.targeted_rereviews("w1", article_hash="wrong-hash"), errors=["invalid_targeted_rereviews"]),
            "targeted_rereview_not_fresh": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), repairs=self.repair_actions("w1"), adjudication=self.adjudication("w1"), targeted=[{**self.targeted_rereviews("w1")[0], "fresh_context": False}], errors=["invalid_targeted_rereviews"]),
            "targeted_rereview_missing_subagent": dict(reports=self.expert_reviews(weaknesses=[valid_weakness]), repairs=self.repair_actions("w1"), adjudication=self.adjudication("w1"), targeted=[{key: value for key, value in self.targeted_rereviews("w1")[0].items() if key != "subagent_session_id"}], errors=["invalid_targeted_rereviews"]),
            "missing_domain_field_evidence_focus": dict(mutator=lambda reports: reports[0]["paper_mechanism_audits"][0].pop("field_evidence_consistency"), errors=["invalid_expert_review_reports"]),
            "missing_evidence_named_entity_focus": dict(mutator=lambda reports: reports[2]["claim_citation_audits"][0].pop("named_entity_alignment"), errors=["invalid_expert_review_reports"]),
            "missing_architect_core_coverage_focus": dict(mutator=lambda reports: reports[1]["flow_taxonomy_audit"].pop("core_family_coverage"), errors=["invalid_expert_review_reports"]),
            "missing_style_release_boundary_focus": dict(mutator=lambda reports: reports[4]["style_audit"].pop("candidate_final_boundary"), errors=["invalid_expert_review_reports"]),
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

    def test_gate7_prompt_precheck_adjudication_and_repair_plan_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "gate7 repair loop", target="full")
            self.populate_full_task(task_dir)
            prompts = make_reviewer_prompts(task_dir)
            prompt_text = prompts["reviewer_prompts"][0]["message"]
            self.assertIn(str(task_dir), prompt_text)
            self.assertIn("dimension_audits", prompt_text)
            self.assertIn("blocking_weaknesses", prompt_text)
            self.assertIn("paper_understanding", prompt_text)
            self.assertIn("narrative_coherence", prompt_text)
            self.assertEqual(precheck_review_report(self.expert_reviews()[0])["status"], "valid")
            bad_report = self.expert_reviews()[0]
            bad_report["dimension_audits"] = {"narrative_coherence": "not a list"}
            self.assertEqual(precheck_review_report(bad_report)["status"], "invalid")
            bad_route = self.expert_reviews()[0]
            bad_route["blocking_weaknesses"] = [self.weakness("BW1") | {"route_to": "not_a_route"}]
            self.assertEqual(precheck_review_report(bad_route)["status"], "invalid")

            weakness_a = {
                **self.weakness("BW1"),
                "route_to": "paper_understanding",
                "affected_sections": ["Method Families"],
                "affected_papers": [],
                "affected_claims": [],
            }
            weakness_b = {
                **self.weakness("BW1"),
                "route_to": "claim_evidence",
                "affected_sections": ["Evidence and Limitations"],
                "affected_papers": [],
                "affected_claims": [],
            }
            reports = self.expert_reviews()
            reports[0]["blocking_weaknesses"] = [weakness_a]
            reports[2]["blocking_weaknesses"] = [weakness_b]
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", reports)
            (task_dir / "state/expert_review_round_status.json").write_text(json.dumps(self.review_round_status()), encoding="utf-8")
            adjudicated = adjudicate_reports(task_dir)
            self.assertEqual(adjudicated["canonical_weakness_count"], 2)
            canonical = adjudicated["canonical_weaknesses"]
            self.assertEqual([item["weakness_id"] for item in canonical], ["CW001", "CW002"])
            self.assertIn("domain_expert:BW1", canonical[0]["source_weakness_ids"])
            self.assertIn("evidence_factuality:BW1", canonical[1]["source_weakness_ids"])
            by_route = {item["route_to"]: item for item in canonical}
            self.assertEqual(by_route["paper_understanding"]["affected_papers"], [])
            self.assertIn("paper_mechanism_cards", by_route["paper_understanding"]["required_evidence_check"])
            self.assertIn("claim_evidence_spans", by_route["claim_evidence"]["required_evidence_check"])

            validation = validate_expert_reviews(
                reports,
                target="full",
                review_invocations=self.expert_invocations(),
                repair_actions=[],
                regression_checks=[],
                round_status=self.review_round_status(),
                adjudication=adjudicated,
                targeted_rereviews=[],
            )
            self.assertNotIn("invalid_canonical_weaknesses", validation["errors"])

            plan = build_repair_plan(task_dir, "full")
            self.assertEqual(plan["schema_version"], 1)
            self.assertTrue(plan["major_rebuild_required"])
            self.assertEqual(plan["rerun_policy"], "full_gate7_round")
            self.assertEqual(plan["repair_items"][0]["rollback_phase"], "paper_understanding")
            self.assertEqual(plan["summary"]["repair_item_count"], len(plan["repair_items"]))
            self.assertEqual(plan["summary"]["first_rollback_phase"], "paper_understanding")
            self.assertEqual(plan["summary"]["rerun_policy"], "full_gate7_round")
            self.assertEqual(plan["summary"]["rollback_phase_counts"], {"paper_understanding": 1, "synthesis": 1})
            self.assertTrue((task_dir / "state/expert_review_round_history.jsonl").exists())
            iteration = json.loads((task_dir / "state/review_iteration_status.json").read_text(encoding="utf-8"))
            self.assertEqual(iteration["last_median_score"], 8.8)

    def test_paper_understanding_runtime_executor_batches_and_records_results(self):
        from scripts.paper_understanding_runtime_executor import (
            collect_paper_understanding_status,
            prepare_paper_understanding_batches,
            record_paper_understanding_result,
        )

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "paper understanding executor", target="full")
            self.populate_source_verified_task(task_dir)
            status = prepare_paper_understanding_batches(task_dir, batch_size=5)
            self.assertEqual(status["schema_version"], 1)
            self.assertEqual(status["component"], "paper_understanding_runtime_executor")
            self.assertEqual(status["status"], "blocked_paper_understanding_agent_spawn_required")
            self.assertEqual(status["next_action"], "spawn_paper_understanding_agents")
            self.assertEqual(status["active_batch_id"], "PU001")
            self.assertEqual(status["active_batch_ids"], ["PU001", "PU002", "PU003"])
            self.assertEqual(status["summary"]["batch_count"], 19)
            self.assertEqual(status["summary"]["paper_required_count"], 95)
            self.assertEqual(status["summary"]["paper_completed_count"], 0)

            batches = json.loads((task_dir / "state/paper_understanding_batches.json").read_text(encoding="utf-8"))
            self.assertEqual(batches["schema_version"], 1)
            self.assertEqual(batches["active_batch_id"], "PU001")
            self.assertEqual(batches["active_batch_ids"], ["PU001", "PU002", "PU003"])
            self.assertEqual(batches["batches"][0]["paper_ids"], ["p001", "p002", "p003", "p004", "p005"])
            self.assertEqual(batches["batches"][1]["status"], "pending_spawn")
            self.assertEqual(batches["batches"][2]["status"], "pending_spawn")
            self.assertEqual(batches["batches"][3]["status"], "blocked_by_upstream")
            spawn_requests = json.loads((task_dir / "state/paper_understanding_spawn_requests.json").read_text(encoding="utf-8"))
            self.assertEqual(len(spawn_requests["spawn_requests"]), 3)
            request = spawn_requests["spawn_requests"][0]
            self.assertEqual(request["batch_id"], "PU001")
            self.assertEqual(request["result_schema_version"], 2)
            self.assertEqual(request["expected_paper_ids"], ["p001", "p002", "p003", "p004", "p005"])
            self.assertIn("paper_mechanism_cards", request["required_result_keys"])
            self.assertNotIn("artifact_hashes_after", request["required_result_keys"])
            self.assertIn("state/full_text_sources.jsonl", request["expected_changed_artifacts"])
            self.assertEqual([row["paper_id"] for row in request["paper_records"]], ["p001", "p002", "p003", "p004", "p005"])
            self.assertIn("p001", request["fetch_candidates_by_paper"])
            self.assertIn("paper_understanding_runtime_executor.py", request["record_command"])

            runtime = collect_paper_understanding_status(task_dir)
            self.assertEqual(runtime["active_batch_id"], "PU001")
            self.assertEqual(runtime["active_batch_ids"], ["PU001", "PU002", "PU003"])
            self.assertTrue(runtime["blocked"])
            active = runtime["batches"][0]

            partial = self.paper_understanding_result(active, task_dir)
            partial["paper_ids"] = partial["paper_ids"][:4]
            partial["paper_mechanism_cards"] = partial["paper_mechanism_cards"][:4]
            partial["full_text_sources"] = partial["full_text_sources"][:4]
            recorded_partial = record_paper_understanding_result(task_dir, partial, "paper-agent-partial")
            self.assertEqual(recorded_partial["status"], "invalid", recorded_partial)
            self.assertIn("missing_batch_paper_ids", recorded_partial["errors"])
            self.assertEqual(read_text_if_exists(task_dir / "state/paper_mechanism_cards.jsonl"), "")
            self.assertEqual(read_text_if_exists(task_dir / "state/full_text_sources.jsonl"), "")

            metadata_only = self.paper_understanding_result(active, task_dir)
            metadata_only["full_text_sources"][0]["source_kind"] = "semantic scholar metadata"
            metadata_only["paper_mechanism_cards"][0]["source_type"] = "semantic scholar metadata"
            metadata_only["artifact_hashes_after"] = {
                "state/full_text_sources.jsonl": sha256_jsonl_rows(metadata_only["full_text_sources"]),
                "state/paper_mechanism_cards.jsonl": sha256_jsonl_rows(metadata_only["paper_mechanism_cards"]),
            }
            recorded_metadata = record_paper_understanding_result(task_dir, metadata_only, "paper-agent-metadata")
            self.assertEqual(recorded_metadata["status"], "invalid", recorded_metadata)
            self.assertIn("invalid_paper_understanding_batch", recorded_metadata["errors"])
            self.assertEqual(read_text_if_exists(task_dir / "state/paper_mechanism_cards.jsonl"), "")

            valid = self.paper_understanding_result(active, task_dir)
            recorded = record_paper_understanding_result(task_dir, valid, "paper-agent-001")
            self.assertEqual(recorded["status"], "recorded", recorded)
            after = collect_paper_understanding_status(task_dir)
            self.assertEqual(after["active_batch_id"], "PU002")
            self.assertEqual(after["active_batch_ids"], ["PU002", "PU003", "PU004"])
            self.assertEqual(after["summary"]["paper_completed_count"], 5)
            self.assertEqual(len((task_dir / "state/paper_mechanism_cards.jsonl").read_text(encoding="utf-8").splitlines()), 5)
            self.assertEqual(len((task_dir / "state/full_text_sources.jsonl").read_text(encoding="utf-8").splitlines()), 5)

    def test_paper_reader_public_facade_prepares_and_records_cards(self):
        from scripts.paper_card_store import validate_paper_card_store
        from scripts.paper_reader import collect_status, prepare_paper_reading, record_result

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "paper reader empty", target="full")
            blocked = prepare_paper_reading(task_dir, target="full")
            self.assertEqual(blocked["component"], "paper_reader")
            self.assertEqual(blocked["status"], "blocked_source_verification_required")
            self.assertFalse((task_dir / "state/paper_understanding_spawn_requests.json").exists())

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "paper reader source ready", target="full")
            self.populate_source_verified_task(task_dir)
            prepared = prepare_paper_reading(task_dir, target="full", batch_size=5)
            self.assertEqual(prepared["component"], "paper_reader")
            self.assertEqual(prepared["legacy_component"], "paper_understanding_runtime_executor")
            self.assertEqual(prepared["status"], "blocked_paper_understanding_agent_spawn_required")
            self.assertEqual(prepared["next_action"], "spawn_paper_understanding_agents")
            self.assertEqual(prepared["active_batch_ids"], ["PU001", "PU002", "PU003"])
            self.assertEqual(prepared["summary"]["paper_required_count"], 95)
            self.assertEqual(prepared["summary"]["public_card_missing_count"], 95)
            self.assertTrue((task_dir / "state/full_text_fetch_plan.jsonl").exists())
            spawn = json.loads((task_dir / "state/paper_understanding_spawn_requests.json").read_text(encoding="utf-8"))
            self.assertIn("paper_reader.py", spawn["spawn_requests"][0]["record_command"])
            self.assertIn("paper_understanding_runtime_executor.py", spawn["spawn_requests"][0]["legacy_record_command"])

            active = json.loads((task_dir / "state/paper_understanding_batches.json").read_text(encoding="utf-8"))["batches"][0]
            recorded = record_result(task_dir, self.paper_understanding_result(active, task_dir), "paper-agent-public", target="full")
            self.assertEqual(recorded["component"], "paper_reader")
            self.assertEqual(recorded["status"], "recorded", recorded)
            self.assertEqual(recorded["summary"]["public_card_missing_count"], 90)
            self.assertTrue((task_dir / "state/paper_cards/p001.json").exists())
            card_status = validate_paper_card_store(task_dir)
            self.assertFalse(card_status["valid"])
            self.assertEqual(card_status["summary"]["missing_count"], 90)
            after = collect_status(task_dir, target="full")
            self.assertEqual(after["component"], "paper_reader")
            self.assertEqual(after["summary"]["paper_completed_count"], 5)

    def test_runtime_dispatcher_queues_and_records_paper_worker_output(self):
        from scripts.paper_understanding_runtime_executor import collect_paper_understanding_status
        from scripts.runtime_dispatcher import collect_pending, mark_failed, mark_spawned, record_agent_output
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dispatcher paper worker", target="full")
            self.populate_source_verified_task(task_dir)
            driver_status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(driver_status["next_action"], "spawn_paper_understanding_agents")

            pending = collect_pending(task_dir)
            self.assertEqual(pending["schema_version"], 1)
            self.assertEqual(pending["component"], "runtime_dispatcher")
            self.assertEqual(pending["status"], "pending_spawn")
            self.assertEqual(len(pending["pending_requests"]), 3)
            first = pending["pending_requests"][0]
            self.assertEqual(first["request_type"], "paper_understanding")
            self.assertEqual(first["phase_generation"], json.loads((task_dir / "state/runtime_active_intent.json").read_text(encoding="utf-8"))["phase_generation"])
            self.assertEqual(first["source_file"], "state/paper_understanding_spawn_requests.json")
            self.assertIn("paper_reader.py", first["record_command"])
            self.assertEqual(first["expected_result_schema_version"], 2)

            marked = mark_spawned(task_dir, first["request_id"], "paper-agent-001")
            self.assertEqual(marked["status"], "spawned", marked)
            duplicate = mark_spawned(task_dir, first["request_id"], "paper-agent-duplicate")
            self.assertEqual(duplicate["status"], "invalid", duplicate)
            self.assertEqual(duplicate["error"], "duplicate_spawn")

            active = next(batch for batch in collect_paper_understanding_status(task_dir)["batches"] if batch["batch_id"] == first["batch_id"])
            output_file = Path(tmp) / "paper-worker-output.json"
            output_file.write_text(json.dumps(self.paper_understanding_result(active, task_dir), sort_keys=True), encoding="utf-8")
            recorded = record_agent_output(task_dir, first["request_id"], output_file)
            self.assertEqual(recorded["status"], "result_recorded", recorded)
            self.assertEqual(recorded["record_result"]["status"], "recorded")
            self.assertEqual(recorded["record_result"]["component"], "paper_reader")
            self.assertEqual(len((task_dir / "state/paper_mechanism_cards.jsonl").read_text(encoding="utf-8").splitlines()), 5)
            self.assertTrue((task_dir / "state/paper_cards/p001.json").exists())
            queue = [json.loads(line) for line in (task_dir / "state/runtime_dispatch_queue.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(next(row for row in queue if row["request_id"] == first["request_id"])["status"], "result_recorded")
            sessions = [json.loads(line) for line in (task_dir / "state/runtime_agent_sessions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(sessions[-1]["spawned_agent_id"], "paper-agent-001")

    def test_survey_driver_dispatches_discovery_workers_from_empty_run(self):
        from scripts.runtime_dispatcher import collect_pending, mark_failed, mark_spawned, record_agent_output
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "fresh discovery run", target="full")
            self.write_topic_profile(task_dir, topic="fresh discovery run")
            status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_discovery_agent_spawn_required", status)
            self.assertEqual(status["next_action"], "spawn_discovery_agents")
            pending = collect_pending(task_dir)
            self.assertEqual([row["request_type"] for row in pending["pending_requests"]], ["discovery"])
            request = pending["pending_requests"][0]
            self.assertIn("discovery_runtime_executor.py", request["record_command"])
            batches = json.loads((task_dir / "state/discovery_batches.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(batches["batches"]), 5)

            for idx in range(len(batches["batches"])):
                self.assertEqual(mark_spawned(task_dir, request["request_id"], f"discovery-agent-{idx + 1:03d}")["status"], "spawned")
                output = {
                    "batch_id": request["batch_id"],
                    "status": "resolved",
                    "raw_candidates": self.raw_candidates(),
                    "search_routes": self.search_routes(),
                    "lqs_scores": self.lqs_scores(),
                    "corpus_expansion": self.corpus_expansion(),
                    "validator_results": [{"validator": "validate_discovery_route", "status": "passed"}],
                    "remaining_blockers": [],
                }
                output_file = Path(tmp) / f"discovery-output-{idx}.json"
                output_file.write_text(json.dumps(output, sort_keys=True), encoding="utf-8")
                recorded = record_agent_output(task_dir, request["request_id"], output_file)
                self.assertEqual(recorded["status"], "result_recorded", recorded)
                status = run_survey_until_complete(task_dir, target="full", max_steps=5)
                if idx == 0:
                    self.assertEqual(read_jsonl(task_dir / "state/raw_candidates.jsonl"), [])
                    self.assertEqual(status["next_action"], "spawn_discovery_agents", status)
                if idx < len(batches["batches"]) - 1:
                    pending = collect_pending(task_dir)
                    self.assertEqual(pending["status"], "pending_spawn", pending)
                    request = pending["pending_requests"][0]

            self.assertGreaterEqual(len(read_jsonl(task_dir / "state/raw_candidates.jsonl")), 200)
            self.assertEqual(len(read_jsonl(task_dir / "state/search_routes.jsonl")), 8)
            after = evaluate_phase_barriers(task_dir, "full")
            self.assertTrue(after["phases"]["discovery"]["passed"])
            self.assertEqual(after["blocked_by_phase"], "source_verification")

    def test_blocked_discovery_result_reopens_batch_for_retry(self):
        from scripts.runtime_dispatcher import collect_pending, mark_spawned, record_agent_output
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "blocked discovery retry", target="full")
            self.write_topic_profile(task_dir, topic="blocked discovery retry")
            status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["next_action"], "spawn_discovery_agents")
            first = collect_pending(task_dir)["pending_requests"][0]
            self.assertEqual(mark_spawned(task_dir, first["request_id"], "discovery-agent-001")["status"], "spawned")
            output = {
                "batch_id": first["batch_id"],
                "status": "blocked",
                "raw_candidates": [{"paper_id": "p001", "title": "real but insufficient"}],
                "search_routes": [{"route_id": "r1", "route_type": "arXiv keyword", "result_count": 1}],
                "lqs_scores": [{"paper_id": "p001", "score": 90}],
                "corpus_expansion": {"blocked_limitations": ["insufficient_raw_candidates"]},
                "validator_results": [{"validator": "validate_discovery", "status": "not_passed"}],
                "remaining_blockers": ["insufficient_raw_candidates"],
            }
            output_file = Path(tmp) / "blocked-discovery-output.json"
            output_file.write_text(json.dumps(output, sort_keys=True), encoding="utf-8")
            recorded = record_agent_output(task_dir, first["request_id"], output_file)
            self.assertEqual(recorded["status"], "result_recorded", recorded)
            self.assertEqual(read_jsonl(task_dir / "state/raw_candidates.jsonl"), [])
            batches = json.loads((task_dir / "state/discovery_batches.json").read_text(encoding="utf-8"))
            self.assertEqual(batches["active_batch_id"], "D001")
            self.assertEqual(batches["batches"][0]["status"], "pending_spawn")
            self.assertEqual(batches["batches"][0]["attempt"], 2)
            retry = collect_pending(task_dir)
            self.assertEqual(retry["status"], "pending_spawn", retry)
            retry_request = retry["pending_requests"][0]
            self.assertEqual(retry_request["request_type"], "discovery")
            self.assertNotEqual(retry_request["request_id"], first["request_id"])

    def test_discovery_prefetch_snapshot_is_carried_in_worker_request(self):
        from scripts.discovery_runtime_executor import DISCOVERY_ROUTE_PLAN_VERSION, prepare_discovery_batches

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "prefetched discovery request", target="full")
            self.write_topic_profile(task_dir, topic="prefetched discovery request")
            first = prepare_discovery_batches(task_dir)
            self.assertEqual(first["next_action"], "spawn_discovery_agents")
            write_jsonl(
                task_dir / "state/discovery_prefetch_snapshots.jsonl",
                [
                    {
                        "schema_version": 1,
                        "route_plan_version": DISCOVERY_ROUTE_PLAN_VERSION,
                        "batch_id": "D001",
                        "prefetched_candidates": [
                            {
                                "candidate_id": "prefetch-001",
                                "title": "Visual Workspace Reasoning",
                                "url": "https://example.org/visual-workspace",
                                "source": "OpenAlex",
                                "query": "visual workspace multimodal reasoning",
                            }
                        ],
                        "prefetch_errors": [],
                        "prefetched_at": "2026-07-05T00:00:00+00:00",
                    }
                ],
            )
            refreshed = prepare_discovery_batches(task_dir)
            request = refreshed["spawn_requests"][0]
            self.assertEqual(request["prefetched_candidates"][0]["candidate_id"], "prefetch-001")
            self.assertEqual(request["prefetch_snapshot_at"], "2026-07-05T00:00:00+00:00")

    def test_dispatcher_stales_discovery_request_when_prefetch_changes_payload(self):
        from scripts.discovery_runtime_executor import DISCOVERY_ROUTE_PLAN_VERSION, prepare_discovery_batches
        from scripts.runtime_dispatcher import collect_pending
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "prefetch stale discovery row", target="full")
            self.write_topic_profile(task_dir, topic="prefetch stale discovery row")
            run_survey_until_complete(task_dir, target="full", max_steps=5)
            first_pending = collect_pending(task_dir)
            first_request = first_pending["pending_requests"][0]
            self.assertEqual(first_request["request_type"], "discovery")

            write_jsonl(
                task_dir / "state/discovery_prefetch_snapshots.jsonl",
                [
                    {
                        "schema_version": 1,
                        "route_plan_version": DISCOVERY_ROUTE_PLAN_VERSION,
                        "batch_id": "D001",
                        "prefetched_candidates": [{"candidate_id": "prefetch-001", "title": "Visual Workspace Reasoning"}],
                        "prefetch_errors": [],
                        "prefetched_at": "2026-07-05T00:00:00+00:00",
                    }
                ],
            )
            prepare_discovery_batches(task_dir)
            run_survey_until_complete(task_dir, target="full", max_steps=5)
            refreshed = collect_pending(task_dir)
            self.assertEqual(len(refreshed["pending_requests"]), 1, refreshed)
            self.assertNotEqual(refreshed["pending_requests"][0]["request_id"], first_request["request_id"])
            queue = read_jsonl(task_dir / "state/runtime_dispatch_queue.jsonl")
            old = next(row for row in queue if row["request_id"] == first_request["request_id"])
            self.assertEqual(old["status"], "stale_superseded")

    def test_discovery_prefetch_can_record_route_result_without_canonical_corpus(self):
        from scripts.discovery_runtime_executor import DISCOVERY_ROUTE_PLAN_VERSION, prepare_discovery_batches, record_prefetch_as_discovery_result

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "record prefetch discovery", target="full")
            self.write_topic_profile(task_dir, topic="record prefetch discovery")
            prepare_discovery_batches(task_dir)
            write_jsonl(
                task_dir / "state/discovery_prefetch_snapshots.jsonl",
                [
                    {
                        "schema_version": 1,
                        "route_plan_version": DISCOVERY_ROUTE_PLAN_VERSION,
                        "batch_id": "D001",
                        "prefetched_candidates": [
                            {
                                "candidate_id": "prefetch-001",
                                "title": "Visual Workspace Reasoning",
                                "url": "https://example.org/visual-workspace",
                                "source": "OpenAlex",
                                "query": "visual workspace multimodal reasoning",
                                "route_id": "D001-prefetch-01",
                                "route_type": "keyword",
                            }
                        ],
                        "prefetch_errors": [],
                        "prefetched_at": "2026-07-05T00:00:00+00:00",
                    }
                ],
            )
            recorded = record_prefetch_as_discovery_result(task_dir, "prefetch-script")
            self.assertEqual(recorded["status"], "recorded", recorded)
            self.assertEqual(recorded["batch_id"], "D001")
            batches = json.loads((task_dir / "state/discovery_batches.json").read_text(encoding="utf-8"))
            self.assertEqual(batches["batches"][0]["status"], "resolved")
            self.assertEqual(batches["active_batch_id"], "D002")
            self.assertEqual(read_jsonl(task_dir / "state/raw_candidates.jsonl"), [])

    def test_discovery_known_system_route_uses_direct_system_queries(self):
        from scripts.discovery_runtime_executor import prepare_discovery_batches

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "mllm think with image route plan", target="full")
            self.write_topic_profile(task_dir, topic="mllm think with image")
            prepare_discovery_batches(task_dir)
            batches = json.loads((task_dir / "state/discovery_batches.json").read_text(encoding="utf-8"))
            d007 = next(batch for batch in batches["batches"] if batch["batch_id"] == "D007")
            joined_queries = "\n".join(d007["seed_queries"]).lower()
            self.assertIn("visual sketchpad", joined_queries)
            self.assertIn("openthinkimg", joined_queries)
            self.assertNotIn(" references", joined_queries)

    def test_discovery_benchmark_route_uses_metadata_friendly_queries(self):
        from scripts.discovery_runtime_executor import prepare_discovery_batches

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "mllm benchmark route plan", target="full")
            self.write_topic_profile(task_dir, topic="mllm think with image")
            prepare_discovery_batches(task_dir)
            batches = json.loads((task_dir / "state/discovery_batches.json").read_text(encoding="utf-8"))
            d005 = next(batch for batch in batches["batches"] if batch["batch_id"] == "D005")
            joined_queries = "\n".join(d005["seed_queries"]).lower()
            self.assertIn("benchmark", joined_queries)
            self.assertNotIn("awesome", joined_queries)

    def test_arxiv_prefetch_uses_term_conjunction_for_long_queries(self):
        from scripts.discovery_runtime_executor import _arxiv_search_expression

        expression = _arxiv_search_expression("survey visual reasoning large multimodal models chain of thought")
        self.assertIn("+AND+", expression)
        self.assertIn("all:visual", expression)
        self.assertNotIn('all:"', expression)

    def test_prefetch_route_result_preserves_batch_route_type(self):
        from scripts.discovery_runtime_executor import DISCOVERY_ROUTE_PLAN_VERSION, record_prefetch_as_discovery_result

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "route type prefetch", target="full")
            state = task_dir / "state"
            write_jsonl(state / "discovery_prefetch_snapshots.jsonl", [
                {
                    "schema_version": 1,
                    "route_plan_version": DISCOVERY_ROUTE_PLAN_VERSION,
                    "batch_id": "D007",
                    "prefetched_candidates": [
                        {
                            "candidate_id": "prefetch-known-system-001",
                            "title": "Visual Sketchpad: Sketching as a Visual Chain of Thought for Multimodal Language Models",
                            "query": '"Visual Sketchpad" "multimodal reasoning"',
                            "route_id": "D007-prefetch-01",
                        }
                    ],
                    "prefetch_errors": [],
                    "prefetched_at": "2026-07-05T00:00:00+00:00",
                }
            ])
            (state / "discovery_batches.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "plan_hash": "test-plan",
                        "route_plan_version": DISCOVERY_ROUTE_PLAN_VERSION,
                        "active_batch_id": "D007",
                        "batches": [
                            {
                                "batch_id": "D007",
                                "status": "pending_spawn",
                                "attempt": 1,
                                "required_route_types": ["snowball", "author_group"],
                            }
                        ],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            recorded = record_prefetch_as_discovery_result(task_dir, "prefetch-script")
            self.assertEqual(recorded["status"], "recorded", recorded)
            result_rows = read_jsonl(state / "discovery_results.jsonl")
            self.assertEqual(result_rows[-1]["search_routes"][0]["route_type"], "snowball")

    def test_discovery_enrichment_batch_has_seed_queries(self):
        from scripts.discovery_runtime_executor import _ensure_enrichment_batch

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "mllm enrichment route plan", target="full")
            self.write_topic_profile(task_dir, topic="mllm think with image")
            doc = {"batches": []}
            _ensure_enrichment_batch(task_dir, doc, ["raw_candidates", "related_surveys"], "2026-07-05T00:00:00+00:00")
            batches = {batch["batch_id"]: batch for batch in doc["batches"]}
            self.assertEqual(set(batches), {"D999R", "D999C"})
            self.assertIn("related_survey_refs", batches["D999R"]["required_route_types"])
            self.assertIn("keyword", batches["D999C"]["required_route_types"])
            self.assertGreaterEqual(len(batches["D999R"]["seed_queries"]), 4)
            self.assertGreaterEqual(len(batches["D999C"]["seed_queries"]), 4)
            self.assertGreater(batches["D999R"]["max_search_queries"], 0)
            self.assertGreater(batches["D999C"]["max_search_queries"], 0)
            related_queries = "\n".join(batches["D999R"]["seed_queries"]).lower()
            raw_queries = "\n".join(batches["D999C"]["seed_queries"]).lower()
            self.assertIn("survey", related_queries)
            self.assertIn("visual", raw_queries)

    def test_resolved_discovery_enrichment_appends_retry_batch(self):
        from scripts.discovery_runtime_executor import _ensure_enrichment_batch

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "mllm resolved enrichment retry", target="full")
            self.write_topic_profile(task_dir, topic="mllm think with image")
            doc = {
                "batches": [
                    {
                        "batch_id": "D999R",
                        "status": "resolved",
                        "attempt": 1,
                        "resolved_at": "2026-07-05T00:00:00+00:00",
                        "subagent_session_id": "old-prefetch",
                    }
                ]
            }
            _ensure_enrichment_batch(task_dir, doc, ["related_surveys"], "2026-07-05T00:05:00+00:00")
            original = next(batch for batch in doc["batches"] if batch["batch_id"] == "D999R")
            retry = next(batch for batch in doc["batches"] if batch["batch_id"] == "D999R2")
            self.assertEqual(original["status"], "resolved")
            self.assertEqual(original["subagent_session_id"], "old-prefetch")
            self.assertEqual(retry["status"], "pending_spawn")
            self.assertEqual(retry["retry_of"], "D999R")

    def test_raw_candidate_enrichment_retry_uses_fresh_queries(self):
        from scripts.discovery_runtime_executor import _ensure_enrichment_batch

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "mllm raw retry enrichment", target="full")
            self.write_topic_profile(task_dir, topic="mllm think with image")
            doc = {
                "batches": [
                    {
                        "batch_id": "D999C",
                        "status": "resolved",
                        "attempt": 1,
                        "seed_queries": ["survey visual reasoning large multimodal models visual chain of thought"],
                        "resolved_at": "2026-07-05T00:00:00+00:00",
                    }
                ]
            }
            _ensure_enrichment_batch(task_dir, doc, ["raw_candidates"], "2026-07-05T00:05:00+00:00")
            retry = next(batch for batch in doc["batches"] if batch["batch_id"] == "D999C2")
            joined_queries = "\n".join(retry["seed_queries"]).lower()
            self.assertIn("pixel-space reasoning", joined_queries)
            self.assertNotEqual(retry["seed_queries"], doc["batches"][0]["seed_queries"])

    def test_scoring_enrichment_does_not_create_raw_candidate_retry(self):
        from scripts.discovery_runtime_executor import _ensure_enrichment_batch

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "mllm scoring enrichment", target="full")
            self.write_topic_profile(task_dir, topic="mllm think with image")
            doc = {
                "batches": [
                    {
                        "batch_id": "D999C",
                        "status": "resolved",
                        "attempt": 1,
                        "seed_queries": ["old raw query"],
                        "resolved_at": "2026-07-05T00:00:00+00:00",
                    }
                ]
            }
            _ensure_enrichment_batch(task_dir, doc, ["lqs_scores", "corpus_expansion_incomplete"], "2026-07-05T00:05:00+00:00")
            self.assertFalse(any(batch["batch_id"] == "D999C2" for batch in doc["batches"]))
            scoring = next(batch for batch in doc["batches"] if batch["batch_id"] == "D999S")
            self.assertTrue(scoring["uses_existing_candidates"])
            self.assertEqual(scoring["max_search_queries"], 0)
            self.assertEqual(scoring["seed_queries"], [])

    def test_corpus_expansion_merge_treats_resolved_route_audits_as_complete(self):
        from scripts.discovery_runtime_executor import _merge_corpus_expansion

        merged = _merge_corpus_expansion(
            [
                {
                    "required": True,
                    "status": "metadata_verification_resolved_for_supplied_candidates",
                    "visible_external_count": 3,
                    "retained_candidate_count": 3,
                    "curated_lists_checked": ["local records"],
                    "recent_surveys_checked": ["arxiv metadata"],
                    "why_retained_corpus_is_sufficient": "Verified supplied related survey records.",
                },
                {
                    "required": False,
                    "status": "sufficient_for_D007_route_batch_not_full_corpus",
                    "visible_external_count": 23,
                    "retained_candidate_count": 23,
                },
            ],
            raw_count=213,
            route_count=75,
        )
        self.assertEqual(merged["status"], "complete")
        self.assertTrue(merged["required"])

    def test_collect_status_supersedes_obsolete_raw_enrichment_retry(self):
        from scripts.discovery_runtime_executor import collect_discovery_status

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "obsolete raw enrichment", target="full")
            self.write_topic_profile(task_dir, topic="mllm think with image")
            state = task_dir / "state"
            raw = self.raw_candidates(total=210, related_surveys=8)
            routes = self.search_routes() + [
                {
                    "route_id": f"extra-{idx}",
                    "route_type": "keyword",
                    "query": f"extra visual reasoning {idx}",
                    "results_seen": 5,
                    "candidates_retained": 5,
                }
                for idx in range(9, 12)
            ]
            lqs = self.lqs_scores(total=100)
            write_jsonl(
                state / "discovery_results.jsonl",
                [
                    {
                        "batch_id": "D999C",
                        "status": "resolved",
                        "raw_candidates": raw,
                        "search_routes": routes,
                        "lqs_scores": lqs,
                        "corpus_expansion": {
                            "required": True,
                            "status": "metadata_verification_resolved_for_supplied_candidates",
                            "visible_external_count": 210,
                            "retained_candidate_count": 210,
                            "curated_lists_checked": ["fixture"],
                            "recent_surveys_checked": ["fixture"],
                            "why_retained_corpus_is_sufficient": "Fixture corpus is visible and retained; scoring is incomplete.",
                        },
                        "validator_results": [{"validator": "validate_discovery", "status": "passed"}],
                        "remaining_blockers": [],
                        "subagent_session_id": "fixture",
                    }
                ],
            )
            (state / "discovery_batches.json").write_text(
                json.dumps(
                    {
                        "batches": [
                            {"batch_id": "D999C", "status": "resolved"},
                            {"batch_id": "D999C2", "status": "pending_spawn", "retry_of": "D999C"},
                        ]
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            status = collect_discovery_status(task_dir)
            batches = {batch["batch_id"]: batch for batch in status["batches"]}
            self.assertEqual(batches["D999C2"]["status"], "superseded")
            self.assertEqual(batches["D999C2"]["superseded_by"], "D999S")
            self.assertEqual(batches["D999S"]["status"], "pending_spawn")
            self.assertEqual(status["active_batch_id"], "D999S")
            spawn_requests = json.loads((state / "discovery_spawn_requests.json").read_text(encoding="utf-8"))["spawn_requests"]
            self.assertEqual(spawn_requests[0]["batch_id"], "D999S")
            self.assertTrue(spawn_requests[0]["existing_raw_candidates"])

    def test_pending_discovery_enrichment_clears_stale_resolved_metadata(self):
        from scripts.discovery_runtime_executor import _ensure_enrichment_batch

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "mllm pending enrichment cleanup", target="full")
            self.write_topic_profile(task_dir, topic="mllm think with image")
            doc = {
                "batches": [
                    {
                        "batch_id": "D999R",
                        "status": "pending_spawn",
                        "attempt": 1,
                        "resolved_at": "2026-07-05T00:00:00+00:00",
                        "subagent_session_id": "old-prefetch",
                    }
                ]
            }
            _ensure_enrichment_batch(task_dir, doc, ["related_surveys"], "2026-07-05T00:05:00+00:00")
            batch = doc["batches"][0]
            self.assertEqual(batch["status"], "pending_spawn")
            self.assertNotIn("resolved_at", batch)
            self.assertNotIn("subagent_session_id", batch)

    def test_corpus_pipeline_facade_preserves_topic_boundary_before_discovery(self):
        from scripts.corpus_pipeline import collect_status as collect_corpus_status
        from scripts.corpus_pipeline import prepare as prepare_corpus

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "corpus facade empty", target="full")
            empty = prepare_corpus(task_dir, target="full")
            self.assertEqual(empty["status"], "blocked_topic_profile_required", empty)
            self.assertEqual(empty["next_action"], "spawn_topic_profile_agents")
            self.assertFalse((task_dir / "state/discovery_spawn_requests.json").exists())

            self.write_topic_profile(task_dir, topic="corpus facade empty")
            discovery = prepare_corpus(task_dir, target="full")
            self.assertEqual(discovery["status"], "blocked_discovery_agent_spawn_required", discovery)
            self.assertEqual(discovery["next_action"], "spawn_discovery_agents")
            self.assertEqual(discovery["corpus_step"], "discovery")
            self.assertEqual(discovery["component"], "corpus_pipeline")
            self.assertTrue((task_dir / "state/discovery_spawn_requests.json").exists())

            status = collect_corpus_status(task_dir, target="full")
            self.assertEqual(status["status"], "blocked_discovery_agent_spawn_required", status)
            self.assertEqual(status["corpus_step"], "discovery")

    def test_corpus_pipeline_facade_routes_source_corpus_audits(self):
        from scripts.corpus_pipeline import collect_status as collect_corpus_status
        from scripts.corpus_pipeline import prepare as prepare_corpus

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "corpus facade topic audit", target="full")
            self.populate_source_verified_task(task_dir)
            (task_dir / "state/topic_relevance_audit.jsonl").write_text("", encoding="utf-8")

            status = prepare_corpus(task_dir, target="full")
            self.assertEqual(status["status"], "blocked_topic_relevance_agent_spawn_required", status)
            self.assertEqual(status["next_action"], "spawn_topic_relevance_agents")
            self.assertEqual(status["corpus_step"], "topic_relevance_audit")
            self.assertEqual(status["summary"]["public_artifacts"]["topic_relevance_audit"], "missing")

            collected = collect_corpus_status(task_dir, target="full")
            self.assertEqual(collected["status"], "blocked_topic_relevance_agent_spawn_required", collected)
            self.assertEqual(collected["corpus_step"], "topic_relevance_audit")
            self.assertGreater(collected["summary"]["pending_batch_count"], 0)

    def knowledge_tree_worker_result(self) -> dict:
        return {
            "batch_id": "KT001",
            "status": "resolved",
            "knowledge_tree": {
                "schema_version": 1,
                "root_claim": "Memory research is organized by how evidence changes downstream decisions.",
                "branches": [
                    {
                        "name": "retrieval memory",
                        "definition": "Systems that retrieve past evidence to condition later decisions.",
                        "included_papers": ["p001", "p002"],
                        "representative_papers": ["p001"],
                        "shared_assumptions_or_boundaries": "Retrieval is useful only when evidence is grounded and timely.",
                        "evidence_standard": "Requires no-memory, oracle-evidence, and wrong-evidence comparisons.",
                        "failure_modes": ["wrong evidence", "stale evidence"],
                        "related_survey_delta": "Existing surveys discuss retrieval but not evidence-to-action failure tests.",
                    }
                ],
                "candidate_taxonomies": ["method-first", "evidence-flow-first"],
                "selected_spine": "evidence-flow-first",
            },
            "paper_clusters": [{"cluster_id": "KT001", "name": "retrieval memory", "paper_ids": ["p001", "p002"]}],
            "taxonomy_candidates": {"candidate_taxonomies": ["method-first", "evidence-flow-first"], "selected_spine": "evidence-flow-first"},
            "spine_decision": (
                "# Spine Decision\n\n"
                "Existing related surveys organize the topic by method families and benchmark settings.\n\n"
                "Candidate taxonomies: method-first and evidence-flow-first.\n\n"
                "Why this spine is better for the current corpus: paper-card evidence shows evidence flow changes downstream claims.\n\n"
                "Section-to-evidence map: retrieval memory uses p001 and p002.\n"
            ),
            "validator_results": [{"validator": "validate_knowledge_tree", "status": "passed"}],
            "remaining_blockers": [],
        }

    def spine_plan_worker_result(self) -> dict:
        return {
            "batch_id": "SP001",
            "status": "resolved",
            "selected_spine": "evidence-flow-first",
            "candidate_taxonomies": ["method-first", "evidence-flow-first"],
            "spine_decision": (
                "# Spine Decision\n\n"
                "Existing related surveys organize the topic by method families, benchmark recipes, and deployment assumptions.\n\n"
                "Candidate taxonomies: method-first and evidence-flow-first.\n\n"
                "Why this spine is better for the current corpus: p001 and p002 show that evidence flow, not paper chronology, changes downstream claims.\n\n"
                "Section-to-evidence map: S1 uses p001 and p002 to explain retrieval memory evidence flow.\n"
            ),
            "section_to_evidence_map": {"S1": {"paper_ids": ["p001", "p002"], "role": "retrieval evidence flow"}},
            "validator_results": [{"validator": "validate_spine_plan", "status": "passed"}],
            "remaining_blockers": [],
        }

    def test_knowledge_tree_builder_records_worker_artifacts(self):
        from scripts.knowledge_tree_builder import prepare_knowledge_tree_request, record_knowledge_tree_result
        from scripts.knowledge_tree_store import mirror_knowledge_tree, validate_knowledge_tree_store
        from scripts.paper_card_store import mirror_paper_cards

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "knowledge tree missing cards", target="full")
            blocked = prepare_knowledge_tree_request(task_dir, target="full")
            self.assertEqual(blocked["status"], "blocked_paper_cards_required", blocked)
            self.assertFalse((task_dir / "state/knowledge_tree_spawn_requests.json").exists())

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "knowledge tree worker", target="full")
            self.populate_full_task(task_dir)
            mirror_paper_cards(task_dir)
            for relative in [
                "outputs/contribution_tree.yml",
                "outputs/knowledge_tree.yml",
                "state/paper_clusters.jsonl",
                "state/taxonomy_candidates.yml",
                "state/spine_decision.md",
            ]:
                path = task_dir / relative
                if path.exists():
                    path.unlink()

            prepared = prepare_knowledge_tree_request(task_dir, target="full")
            self.assertEqual(prepared["status"], "blocked_knowledge_tree_agent_spawn_required", prepared)
            self.assertEqual(prepared["next_action"], "spawn_knowledge_tree_agents")
            self.assertEqual(prepared["spawn_requests"][0]["request_type"], "knowledge_tree")
            recorded = record_knowledge_tree_result(task_dir, self.knowledge_tree_worker_result(), "knowledge-tree-agent-001")
            self.assertEqual(recorded["status"], "recorded", recorded)
            self.assertTrue((task_dir / "outputs/knowledge_tree.yml").exists())
            self.assertTrue((task_dir / "outputs/contribution_tree.yml").exists())
            self.assertTrue((task_dir / "state/paper_clusters.jsonl").exists())
            self.assertTrue((task_dir / "state/spine_decision.md").exists())
            self.assertTrue(validate_knowledge_tree_store(task_dir)["valid"])

            mirrored = mirror_knowledge_tree(task_dir)
            self.assertEqual(mirrored["status"], "mirrored")

    def test_spine_planner_prepares_and_records_worker_spine(self):
        from scripts.knowledge_tree_builder import record_knowledge_tree_result
        from scripts.paper_card_store import mirror_paper_cards
        from scripts.spine_planner import prepare_spine_plan_request, record_spine_plan_result, validate_spine_plan

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "spine planner missing tree", target="full")
            blocked = prepare_spine_plan_request(task_dir, target="full")
            self.assertEqual(blocked["status"], "blocked_knowledge_tree_required", blocked)
            self.assertFalse((task_dir / "state/spine_planner_spawn_requests.json").exists())

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "spine planner worker", target="full")
            self.populate_full_task(task_dir)
            mirror_paper_cards(task_dir)
            recorded_tree = record_knowledge_tree_result(task_dir, self.knowledge_tree_worker_result(), "knowledge-tree-agent-001")
            self.assertEqual(recorded_tree["status"], "recorded", recorded_tree)
            (task_dir / "state/spine_decision.md").write_text("# Weak Spine\n\nThis does not compare surveys or map evidence.\n", encoding="utf-8")
            invalid = validate_spine_plan(task_dir, target="full")
            self.assertFalse(invalid["valid"], invalid)
            self.assertIn("spine_decision_missing_existing_related_surveys", invalid["errors"])

            prepared = prepare_spine_plan_request(task_dir, target="full")
            self.assertEqual(prepared["status"], "blocked_spine_planner_agent_spawn_required", prepared)
            self.assertEqual(prepared["next_action"], "spawn_spine_planner_agents")
            self.assertEqual(prepared["spawn_requests"][0]["request_type"], "spine_planner")
            self.assertIn("spine_planner.py", prepared["spawn_requests"][0]["record_command"])

            recorded = record_spine_plan_result(task_dir, self.spine_plan_worker_result(), "spine-agent-001")
            self.assertEqual(recorded["status"], "recorded", recorded)
            valid = validate_spine_plan(task_dir, target="full")
            self.assertTrue(valid["valid"], valid)
            self.assertIn("p001", valid["trace_paper_ids"])
            tree = json.loads((task_dir / "outputs/knowledge_tree.yml").read_text(encoding="utf-8"))
            self.assertEqual(tree["selected_spine"], "evidence-flow-first")

    def test_survey_driver_routes_missing_knowledge_tree_to_worker_queue(self):
        from scripts.runner import run_until_complete as run_public_runner
        from scripts.runtime_dispatcher import mark_spawned
        from scripts.task_queue import collect_pending, record_agent_output

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "knowledge tree driver", target="full")
            self.populate_full_task(task_dir)
            for relative in [
                "outputs/contribution_tree.yml",
                "outputs/knowledge_tree.yml",
                "state/paper_clusters.jsonl",
                "state/taxonomy_candidates.yml",
                "state/spine_decision.md",
            ]:
                path = task_dir / relative
                if path.exists():
                    path.unlink()

            status = run_public_runner(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_knowledge_tree_agent_spawn_required", status)
            self.assertEqual(status["next_action"], "spawn_knowledge_tree_agents")
            pending = collect_pending(task_dir)
            self.assertEqual([row["request_type"] for row in pending["tasks"]], ["knowledge_tree"])
            request = pending["tasks"][0]
            packet = json.loads((task_dir / request["packet"]).read_text(encoding="utf-8"))
            self.assertIn("knowledge_tree_builder.py", packet["record_command"])
            mark_spawned(task_dir, request["task_id"], "knowledge-tree-agent-001")
            output_file = Path(tmp) / "knowledge-tree-result.json"
            output_file.write_text(json.dumps(self.knowledge_tree_worker_result(), sort_keys=True), encoding="utf-8")
            recorded = record_agent_output(task_dir, request["task_id"], output_file)
            self.assertEqual(recorded["status"], "result_recorded", recorded)
            self.assertEqual(recorded["record_result"]["status"], "recorded")
            self.assertTrue((task_dir / "outputs/knowledge_tree.yml").exists())

    def test_runtime_dispatcher_routes_spine_planner_output(self):
        from scripts.knowledge_tree_builder import record_knowledge_tree_result
        from scripts.paper_card_store import mirror_paper_cards
        from scripts.runner import run_until_complete as run_public_runner
        from scripts.task_queue import collect_pending, mark_spawned, record_agent_output

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "spine planner driver", target="full")
            self.populate_full_task(task_dir)
            mirror_paper_cards(task_dir)
            recorded_tree = record_knowledge_tree_result(task_dir, self.knowledge_tree_worker_result(), "knowledge-tree-agent-001")
            self.assertEqual(recorded_tree["status"], "recorded", recorded_tree)
            (task_dir / "state/spine_decision.md").write_text("# Weak Spine\n\nNo related survey comparison.\n", encoding="utf-8")

            status = run_public_runner(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_spine_planner_agent_spawn_required", status)
            self.assertEqual(status["next_action"], "spawn_spine_planner_agents")
            pending = collect_pending(task_dir)
            self.assertEqual([row["request_type"] for row in pending["tasks"]], ["spine_planner"])
            request = pending["tasks"][0]
            packet = json.loads((task_dir / request["packet"]).read_text(encoding="utf-8"))
            self.assertIn("spine_planner.py", packet["record_command"])
            mark_spawned(task_dir, request["task_id"], "spine-agent-001")
            output_file = Path(tmp) / "spine-plan-result.json"
            output_file.write_text(json.dumps(self.spine_plan_worker_result(), sort_keys=True), encoding="utf-8")
            recorded = record_agent_output(task_dir, request["task_id"], output_file)
            self.assertEqual(recorded["status"], "result_recorded", recorded)
            self.assertEqual(recorded["record_result"]["status"], "recorded")
            self.assertIn("evidence-flow-first", (task_dir / "state/spine_decision.md").read_text(encoding="utf-8"))

    def test_runner_requires_topic_profile_before_discovery(self):
        from scripts.runner import run_until_complete as run_public_runner
        from scripts.runtime_dispatcher import collect_pending
        from scripts.task_queue import sync_tasks
        from scripts.topic_profile import record_topic_profile_result

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "topic profile first", target="full")
            phase_before = evaluate_phase_barriers(task_dir, "full")
            self.assertEqual(phase_before["blocked_by_phase"], "topic_profile")
            self.assertEqual(phase_before["allowed_next_phase"], "topic_profile")
            status = run_public_runner(task_dir, target="full", max_steps=5)
            self.assertEqual(status["component"], "runner")
            self.assertEqual(status["status"], "blocked_topic_profile_agent_spawn_required", status)
            self.assertEqual(status["next_action"], "spawn_topic_profile_agents")
            self.assertEqual(status["blocked_by_phase"], "topic_profile")
            pending = collect_pending(task_dir)
            self.assertEqual([row["request_type"] for row in pending["pending_requests"]], ["topic_profile"])
            self.assertEqual(read_jsonl(task_dir / "state/tasks.jsonl")[0]["phase"], "topic_profile")

            stale_discovery = {
                "request_id": "discovery-stale",
                "request_type": "discovery",
                "phase_generation": "old",
                "source_file": "state/discovery_spawn_requests.json",
                "status": "stale_superseded",
                "error": "runtime_intent_changed",
            }
            write_jsonl(task_dir / "state/runtime_dispatch_queue.jsonl", read_jsonl(task_dir / "state/runtime_dispatch_queue.jsonl") + [stale_discovery])
            tasks = sync_tasks(task_dir)
            self.assertEqual([task["request_type"] for task in tasks["tasks"]], ["topic_profile"])
            self.assertEqual(tasks["summary"]["task_count"], 1)

            invalid_profile = {
                "topic": "topic profile first",
                "central_question": "How should the survey boundary be set?",
                "positive_anchors": ["visual scratchpad"],
                "negative_anchors": [],
                "allowed_background": ["generic MLLM surveys as background only"],
                "core_claim_types": ["taxonomy claims"],
                "search_seed_queries": ["visual scratchpad multimodal reasoning"],
                "acceptance_rubric": {
                    "paper_relevance": "directly studies visual intermediate-state reasoning",
                    "survey_spine": "spine follows paper-card evidence",
                    "paper_understanding": "A/B papers require full-text cards",
                },
                "validator_results": [{"validator": "validate_topic_profile", "status": "passed"}],
                "remaining_blockers": [],
            }
            invalid_record = record_topic_profile_result(task_dir, invalid_profile, "topic-agent-invalid")
            self.assertEqual(invalid_record["status"], "invalid")
            self.assertFalse((task_dir / "state/topic_profile.json").exists())

            valid_profile = dict(invalid_profile)
            valid_profile["negative_anchors"] = ["generic LLM survey without visual workspace reasoning"]
            valid_profile["positive_anchors"] = [
                "visual scratchpad",
                "image-as-workspace",
                "visual intermediate-state reasoning",
            ]
            valid_profile["search_seed_queries"] = [
                "visual scratchpad multimodal reasoning",
                "image as workspace MLLM reasoning",
                "visual intermediate state reasoning",
            ]
            recorded = record_topic_profile_result(task_dir, valid_profile, "topic-agent-001")
            self.assertEqual(recorded["status"], "recorded", recorded)
            phase_after_profile = evaluate_phase_barriers(task_dir, "full")
            self.assertTrue(phase_after_profile["phases"]["topic_profile"]["passed"])
            self.assertEqual(phase_after_profile["blocked_by_phase"], "discovery")
            next_status = run_public_runner(task_dir, target="full", max_steps=5)
            self.assertEqual(next_status["next_action"], "spawn_discovery_agents")
            discovery_request = next_status["spawn_requests"][0]
            self.assertIn("topic_profile", discovery_request)
            self.assertIn("visual scratchpad", discovery_request["message"])
            self.assertIn("generic LLM survey", discovery_request["message"])

    def test_survey_driver_repeated_blocker_does_not_preempt_runtime_intent_rebuild(self):
        from scripts.runtime_dispatcher import collect_pending, mark_spawned
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "old topic runtime history", target="full")
            self.populate_source_verified_task(task_dir)
            (task_dir / "state/topic_relevance_audit.jsonl").write_text("", encoding="utf-8")
            stale_history_row = {
                "status": "blocked_topic_relevance_agent_spawn_required",
                "next_action": "spawn_topic_relevance_agents",
                "blocked_by_phase": "source_verification",
                "active_batch_id": "TR001",
                "candidate_hash": "",
                "paper_cards_hash": "",
                "full_text_sources_hash": "",
                "blocker_fingerprint": "blocked_topic_relevance_agent_spawn_required|spawn_topic_relevance_agents|source_verification|TR001",
            }
            write_jsonl(task_dir / "state/survey_driver_history.jsonl", [stale_history_row, stale_history_row, stale_history_row])
            (task_dir / "state/runtime_active_intent.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "active_phase": None,
                        "next_action": None,
                        "allowed_request_types": [],
                        "phase_generation": "",
                        "source_hashes": {},
                        "generated_at": None,
                    }
                ),
                encoding="utf-8",
            )

            rebuilt = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(rebuilt["status"], "blocked_topic_relevance_agent_spawn_required", rebuilt)
            self.assertEqual(rebuilt["next_action"], "spawn_topic_relevance_agents")
            self.assertNotEqual(rebuilt["status"], "blocked_repeated_no_progress")
            pending = collect_pending(task_dir)
            self.assertEqual(pending["status"], "pending_spawn", pending)
            self.assertEqual([row["request_type"] for row in pending["pending_requests"]], ["topic_relevance"])

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "runtime progress fingerprint", target="full")
            self.populate_source_verified_task(task_dir)
            (task_dir / "state/topic_relevance_audit.jsonl").write_text("", encoding="utf-8")
            first = run_survey_until_complete(task_dir, target="full", max_steps=5)
            first_generation = json.loads((task_dir / "state/runtime_active_intent.json").read_text(encoding="utf-8"))["phase_generation"]
            request = collect_pending(task_dir)["pending_requests"][0]
            self.assertEqual(mark_spawned(task_dir, request["request_id"], "topic-agent-progress")["status"], "spawned")
            after_spawn_generation = json.loads((task_dir / "state/runtime_active_intent.json").read_text(encoding="utf-8"))["phase_generation"]
            self.assertEqual(first_generation, after_spawn_generation)
            for _ in range(3):
                status = run_survey_until_complete(task_dir, target="full", max_steps=5)
                self.assertEqual(status["status"], first["status"], status)
                self.assertNotEqual(status["status"], "blocked_repeated_no_progress")

    def test_runtime_dispatcher_requires_active_intent_and_prunes_stale_downstream_requests(self):
        from scripts.paper_understanding_runtime_executor import collect_paper_understanding_status, prepare_paper_understanding_batches
        from scripts.runtime_dispatcher import collect_pending, mark_failed, mark_spawned, record_agent_output
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dispatcher intent required", target="full")
            self.populate_source_verified_task(task_dir)
            prepare_paper_understanding_batches(task_dir, batch_size=5)
            no_intent = collect_pending(task_dir)
            self.assertEqual(no_intent["status"], "blocked_runtime_intent_required")
            self.assertEqual(no_intent["pending_requests"], [])

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dispatcher stale downstream", target="full")
            self.populate_source_verified_task(task_dir)
            paper_status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(paper_status["next_action"], "spawn_paper_understanding_agents")
            paper_pending = collect_pending(task_dir)
            self.assertEqual({row["request_type"] for row in paper_pending["pending_requests"]}, {"paper_understanding"})
            stale_paper_request = paper_pending["pending_requests"][0]

            (task_dir / "state/topic_relevance_audit.jsonl").write_text("", encoding="utf-8")
            topic_status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(topic_status["next_action"], "spawn_topic_relevance_agents")
            topic_pending = collect_pending(task_dir)
            self.assertEqual([row["request_type"] for row in topic_pending["pending_requests"]], ["topic_relevance"])
            queue = read_jsonl(task_dir / "state/runtime_dispatch_queue.jsonl")
            stale_rows = [row for row in queue if row.get("request_type") == "paper_understanding"]
            self.assertTrue(stale_rows)
            self.assertTrue(all(row["status"] == "stale_superseded" for row in stale_rows))

            stale_mark = mark_spawned(task_dir, stale_paper_request["request_id"], "paper-agent-stale")
            self.assertEqual(stale_mark["status"], "stale_request_rejected", stale_mark)
            active = next(batch for batch in collect_paper_understanding_status(task_dir)["batches"] if batch["batch_id"] == stale_paper_request["batch_id"])
            output_file = Path(tmp) / "stale-paper-output.json"
            output_file.write_text(json.dumps(self.paper_understanding_result(active, task_dir), sort_keys=True), encoding="utf-8")
            stale_record = record_agent_output(task_dir, stale_paper_request["request_id"], output_file)
            self.assertEqual(stale_record["status"], "stale_request_rejected", stale_record)
            self.assertEqual(read_text_if_exists(task_dir / "state/paper_mechanism_cards.jsonl"), "")
            self.assertEqual(read_text_if_exists(task_dir / "state/full_text_sources.jsonl"), "")

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dispatcher stale topic reactivation", target="full")
            self.populate_source_verified_task(task_dir)
            (task_dir / "state/topic_relevance_audit.jsonl").write_text("", encoding="utf-8")
            topic_status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(topic_status["next_action"], "spawn_topic_relevance_agents")
            topic_request = collect_pending(task_dir)["pending_requests"][0]

            (task_dir / "state/runtime_active_intent.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "active_phase": None,
                        "next_action": None,
                        "allowed_request_types": [],
                        "phase_generation": "",
                        "source_hashes": {},
                        "generated_at": None,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(collect_pending(task_dir)["status"], "blocked_runtime_intent_required")
            self.assertEqual(
                next(row for row in read_jsonl(task_dir / "state/runtime_dispatch_queue.jsonl") if row["request_id"] == topic_request["request_id"])["status"],
                "stale_superseded",
            )

            restored = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(restored["next_action"], "spawn_topic_relevance_agents")
            restored_pending = collect_pending(task_dir)
            self.assertEqual(restored_pending["status"], "pending_spawn", restored_pending)
            self.assertEqual([row["request_id"] for row in restored_pending["pending_requests"]], [topic_request["request_id"]])
            restored_row = restored_pending["pending_requests"][0]
            self.assertEqual(restored_row["status"], "pending_spawn")
            self.assertIn("reactivated_at", restored_row)

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dispatcher stale spawned retry", target="full")
            self.populate_source_verified_task(task_dir)
            (task_dir / "state/topic_relevance_audit.jsonl").write_text("", encoding="utf-8")
            run_survey_until_complete(task_dir, target="full", max_steps=5)
            first_request = collect_pending(task_dir)["pending_requests"][0]
            self.assertEqual(mark_spawned(task_dir, first_request["request_id"], "topic-agent-old")["status"], "spawned")
            (task_dir / "state/runtime_active_intent.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "active_phase": None,
                        "next_action": None,
                        "allowed_request_types": [],
                        "phase_generation": "",
                        "source_hashes": {},
                        "generated_at": None,
                    }
                ),
                encoding="utf-8",
            )
            collect_pending(task_dir)
            stale_spawned = next(row for row in read_jsonl(task_dir / "state/runtime_dispatch_queue.jsonl") if row["request_id"] == first_request["request_id"])
            self.assertEqual(stale_spawned["status"], "stale_spawned")

            run_survey_until_complete(task_dir, target="full", max_steps=5)
            retry_pending = collect_pending(task_dir)
            self.assertEqual(retry_pending["status"], "pending_spawn", retry_pending)
            retry_request = retry_pending["pending_requests"][0]
            self.assertNotEqual(retry_request["request_id"], first_request["request_id"])
            self.assertEqual(retry_request["previous_request_id"], first_request["request_id"])
            stale_old_output = Path(tmp) / "stale-topic-output.json"
            stale_old_output.write_text(json.dumps({"batch_id": first_request["batch_id"], "status": "blocked"}), encoding="utf-8")
            stale_record = record_agent_output(task_dir, first_request["request_id"], stale_old_output)
            self.assertEqual(stale_record["status"], "stale_request_rejected", stale_record)

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dispatcher spawned failure retry", target="full")
            self.write_topic_profile(task_dir, topic="dispatcher spawned failure retry")
            run_survey_until_complete(task_dir, target="full", max_steps=5)
            first_request = collect_pending(task_dir)["pending_requests"][0]
            self.assertEqual(mark_spawned(task_dir, first_request["request_id"], "discovery-agent-timeout")["status"], "spawned")
            failed = mark_failed(task_dir, first_request["request_id"], "worker_timeout")
            self.assertEqual(failed["status"], "worker_failed", failed)
            retry_pending = collect_pending(task_dir)
            self.assertEqual(retry_pending["status"], "pending_spawn", retry_pending)
            retry_request = retry_pending["pending_requests"][0]
            self.assertNotEqual(retry_request["request_id"], first_request["request_id"])
            self.assertEqual(retry_request["previous_request_id"], first_request["request_id"])

    def test_runtime_dispatcher_rejects_invalid_output_and_routes_gate7_repair(self):
        from scripts.gate7_runtime_executor import collect_runtime_repair_status
        from scripts.runtime_dispatcher import collect_pending, mark_spawned, record_agent_output
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dispatcher invalid paper output", target="full")
            self.populate_source_verified_task(task_dir)
            run_survey_until_complete(task_dir, target="full", max_steps=5)
            first = collect_pending(task_dir)["pending_requests"][0]
            mark_spawned(task_dir, first["request_id"], "paper-agent-invalid")
            output_file = Path(tmp) / "not-json.txt"
            output_file.write_text("worker returned prose instead of JSON", encoding="utf-8")
            recorded = record_agent_output(task_dir, first["request_id"], output_file)
            self.assertEqual(recorded["status"], "invalid_result", recorded)
            self.assertEqual(read_text_if_exists(task_dir / "state/paper_mechanism_cards.jsonl"), "")
            self.assertEqual(read_text_if_exists(task_dir / "state/full_text_sources.jsonl"), "")

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dispatcher gate7 repair", target="full")
            self.populate_full_task(task_dir)
            weakness = {
                **self.weakness("BW1"),
                "route_to": "article_quality",
                "affected_sections": ["Related Surveys"],
                "affected_papers": [],
                "affected_claims": [],
            }
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", self.expert_reviews(score=8.8, weaknesses=[weakness]))
            write_jsonl(task_dir / "state/expert_review_invocations.jsonl", self.expert_invocations())
            (task_dir / "state/expert_review_adjudication.json").write_text(json.dumps({"review_round_id": None, "all_major_weaknesses_adjudicated": False, "canonical_weaknesses": []}), encoding="utf-8")
            status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_repair_agent_spawn_required")
            pending = collect_pending(task_dir)
            repair_request = next(row for row in pending["pending_requests"] if row["request_type"] == "gate7_repair")
            self.assertIn("gate7_runtime_executor.py", repair_request["record_command"])
            mark_spawned(task_dir, repair_request["request_id"], "repair-agent-001")
            runtime = collect_runtime_repair_status(task_dir)
            active = next(batch for batch in runtime["batches"] if batch["batch_id"] == runtime["active_batch_id"])
            candidate = task_dir / "outputs/survey_candidate.md"
            candidate.write_text(candidate.read_text(encoding="utf-8") + "\n\nDispatcher-routed repair completed.\n", encoding="utf-8")
            output_file = Path(tmp) / "repair-output.json"
            output_file.write_text(json.dumps(self.runtime_repair_result(active, task_dir), sort_keys=True), encoding="utf-8")
            recorded = record_agent_output(task_dir, repair_request["request_id"], output_file)
            self.assertEqual(recorded["status"], "result_recorded", recorded)
            repair_rows = [json.loads(line) for line in (task_dir / "state/repair_actions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(repair_rows), 1)

    def test_runtime_dispatcher_routes_gate7_reviewer_output(self):
        from scripts.runtime_dispatcher import collect_pending, mark_spawned, record_agent_output
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dispatcher reviewer", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "state/expert_review_reports.jsonl").write_text("", encoding="utf-8")
            status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_subagent_spawn_required")
            self.assertEqual(status["next_action"], "spawn_reviewers")
            pending = collect_pending(task_dir)
            reviewer_request = next(row for row in pending["pending_requests"] if row["request_type"] == "gate7_reviewer")
            self.assertIn("gate7_loop.py", reviewer_request["record_command"])
            mark_spawned(task_dir, reviewer_request["request_id"], "review-agent-001")
            review = next(report for report in self.expert_reviews() if report["reviewer_id"] == reviewer_request["reviewer_id"])
            output_file = Path(tmp) / "review-output.json"
            output_file.write_text(json.dumps(review, sort_keys=True), encoding="utf-8")
            recorded = record_agent_output(task_dir, reviewer_request["request_id"], output_file)
            self.assertEqual(recorded["status"], "result_recorded", recorded)
            report_rows = [json.loads(line) for line in (task_dir / "state/expert_review_reports.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(report_rows), 1)
            self.assertEqual(report_rows[0]["reviewer_id"], reviewer_request["reviewer_id"])

    def test_runtime_dispatcher_marks_paper_downgrade_rebalance_required(self):
        from scripts.paper_understanding_runtime_executor import collect_paper_understanding_status
        from scripts.runtime_dispatcher import collect_pending, mark_spawned, record_agent_output
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "dispatcher rebalance", target="full")
            self.populate_source_verified_task(task_dir)
            run_survey_until_complete(task_dir, target="full", max_steps=5)
            first = collect_pending(task_dir)["pending_requests"][0]
            mark_spawned(task_dir, first["request_id"], "paper-agent-blocked")
            active = next(batch for batch in collect_paper_understanding_status(task_dir)["batches"] if batch["batch_id"] == first["batch_id"])
            blocked = self.paper_understanding_result(active, task_dir, status="blocked")
            blocked["full_text_sources"] = []
            blocked["paper_mechanism_cards"] = []
            blocked["unavailable_or_downgrade_candidates"] = [{"paper_id": "p001", "reason": "publisher full text unavailable"}]
            blocked.pop("artifact_hashes_after")
            output_file = Path(tmp) / "blocked-paper-output.json"
            output_file.write_text(json.dumps(blocked, sort_keys=True), encoding="utf-8")
            recorded = record_agent_output(task_dir, first["request_id"], output_file)
            self.assertEqual(recorded["status"], "rebalance_required", recorded)
            result_rows = [json.loads(line) for line in (task_dir / "state/runtime_agent_results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(result_rows[-1]["status"], "rebalance_required")
            self.assertEqual(result_rows[-1]["unavailable_paper_ids"], ["p001"])

    def test_survey_driver_consumes_dispatcher_rebalance_requests(self):
        from scripts.paper_understanding_runtime_executor import collect_paper_understanding_status
        from scripts.runtime_dispatcher import collect_pending, mark_spawned, record_agent_output
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "driver rebalance consume", target="full")
            self.populate_source_verified_task(task_dir)
            run_survey_until_complete(task_dir, target="full", max_steps=5)
            first = collect_pending(task_dir)["pending_requests"][0]
            mark_spawned(task_dir, first["request_id"], "paper-agent-blocked")
            active = next(batch for batch in collect_paper_understanding_status(task_dir)["batches"] if batch["batch_id"] == first["batch_id"])
            blocked = self.paper_understanding_result(active, task_dir, status="blocked")
            blocked["full_text_sources"] = []
            blocked["paper_mechanism_cards"] = []
            blocked["unavailable_or_downgrade_candidates"] = [{"paper_id": "p001", "reason": "publisher full text unavailable"}]
            blocked.pop("artifact_hashes_after")
            output_file = Path(tmp) / "blocked-paper-output.json"
            output_file.write_text(json.dumps(blocked, sort_keys=True), encoding="utf-8")
            self.assertEqual(record_agent_output(task_dir, first["request_id"], output_file)["status"], "rebalance_required")

            status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_paper_understanding_agent_spawn_required")
            self.assertEqual(status["next_action"], "spawn_paper_understanding_agents")
            citation = [json.loads(line) for line in (task_dir / "state/citation_plan.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            depth = {row["paper_id"]: row["depth"] for row in citation}
            self.assertEqual(depth["p001"], "C")
            self.assertEqual(sum(1 for value in depth.values() if value == "A"), 25)
            self.assertEqual(sum(1 for value in depth.values() if value == "B"), 70)
            rebalance_status = json.loads((task_dir / "state/runtime_rebalance_status.json").read_text(encoding="utf-8"))
            self.assertTrue(rebalance_status["handled_result_hashes"])
            batches = json.loads((task_dir / "state/paper_understanding_batches.json").read_text(encoding="utf-8"))
            self.assertNotIn("p001", [pid for batch in batches["batches"] for pid in batch.get("paper_ids") or []])

    def test_real_topic_drift_fixture_requires_topic_relevance_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "real topic drift missing audit", target="full")
            self.populate_topic_fixture_task(task_dir, "mllm_think_with_image_drift", include_audit=False)
            status = evaluate_phase_barriers(task_dir, "full")
            source = status["phases"]["source_verification"]
            self.assertFalse(source["passed"], source)
            self.assertEqual(status["blocked_by_phase"], "source_verification")
            self.assertEqual(status["allowed_next_phase"], "topic_relevance_audit")
            self.assertIn("topic_relevance_audit_missing", source["details"]["topic_relevance"]["errors"])

    def test_real_topic_drift_fixture_audit_blocks_broad_ab_papers(self):
        from scripts.validate_topic_relevance import validate_topic_relevance

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "real topic drift with audit", target="full")
            self.populate_topic_fixture_task(task_dir, "mllm_think_with_image_drift", include_audit=True)
            state = task_dir / "state"
            topic = validate_topic_relevance(
                read_jsonl(state / "raw_candidates.jsonl"),
                read_jsonl(state / "papers.jsonl"),
                read_jsonl(state / "citation_plan.jsonl"),
                read_jsonl(state / "topic_relevance_audit.jsonl"),
                (state / "survey_type_plan.yml").read_text(encoding="utf-8"),
                "full",
                secondary_audits=read_jsonl(state / "topic_relevance_second_audits.jsonl"),
            )
            self.assertFalse(topic["valid"], topic)
            self.assertIn("ab_topic_relevance_failed", topic["errors"])
            self.assertIn("related_survey_relevance_failed", topic["errors"])
            self.assertGreater(topic["summary"]["invalid_ab_count"], 30)

            status = evaluate_phase_barriers(task_dir, "full")
            source = status["phases"]["source_verification"]
            self.assertFalse(source["passed"], source)
            self.assertEqual(status["allowed_next_phase"], "topic_relevance_rebalance")
            self.assertIn("ab_topic_relevance_failed", source["details"]["topic_relevance"]["errors"])

    def test_real_topic_anchor_fixture_passes_topic_relevance(self):
        from scripts.validate_topic_relevance import validate_topic_relevance

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "real topic anchor", target="short")
            self.populate_topic_fixture_task(task_dir, "mllm_think_with_image_anchor", include_audit=True)
            state = task_dir / "state"
            topic = validate_topic_relevance(
                read_jsonl(state / "raw_candidates.jsonl"),
                read_jsonl(state / "papers.jsonl"),
                read_jsonl(state / "citation_plan.jsonl"),
                read_jsonl(state / "topic_relevance_audit.jsonl"),
                (state / "survey_type_plan.yml").read_text(encoding="utf-8"),
                "short",
            )
            self.assertTrue(topic["valid"], topic)
            self.assertGreaterEqual(topic["summary"]["core_ab_count"], 3)

            status = evaluate_phase_barriers(task_dir, "short")
            self.assertTrue(status["phases"]["source_verification"]["passed"], status["phases"]["source_verification"])

    def test_real_topic_full_anchor_fixture_passes_full_source_gate(self):
        from scripts.validate_topic_relevance import validate_topic_relevance

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "real topic full anchor", target="full")
            self.populate_topic_fixture_task(task_dir, "mllm_think_with_image_full_anchor", include_audit=True)
            state = task_dir / "state"
            topic = validate_topic_relevance(
                read_jsonl(state / "raw_candidates.jsonl"),
                read_jsonl(state / "papers.jsonl"),
                read_jsonl(state / "citation_plan.jsonl"),
                read_jsonl(state / "topic_relevance_audit.jsonl"),
                (state / "survey_type_plan.yml").read_text(encoding="utf-8"),
                "full",
                secondary_audits=read_jsonl(state / "topic_relevance_second_audits.jsonl"),
            )
            self.assertTrue(topic["valid"], topic)
            self.assertGreaterEqual(topic["summary"]["verified_related_survey_count"], 6)
            status = evaluate_phase_barriers(task_dir, "full")
            self.assertTrue(status["phases"]["source_verification"]["passed"], status["phases"]["source_verification"])

    def test_topic_coverage_support_is_layered_by_raw_verified_and_ab_sets(self):
        raw = self.raw_candidates()
        papers = self.papers()
        citation = self.citation_plan()
        audit = self.topic_relevance_audit(raw, papers, citation)
        for row in audit:
            if row["paper_id"] in {"p200", "p201"}:
                row.update(
                    {
                        "relevance_grade": "core",
                        "allowed_depth": "C",
                        "allowed_role": "background",
                        "family_label_supported": True,
                        "corrected_family": "rare raw only family",
                    }
                )
        raw_only = validate_coverage(
            raw,
            self.search_routes(),
            self.lqs_scores(),
            self.corpus_expansion(),
            papers,
            citation,
            "full",
            core_families=["rare raw only family"],
            topic_relevance_audit=audit,
        )
        self.assertFalse(raw_only["valid"], raw_only)
        self.assertIn("core_family_verified_undercovered", raw_only["retained_missing"])

        audit = self.topic_relevance_audit(raw, papers, citation)
        for row in audit:
            if row["paper_id"] in {"p150", "p151"}:
                row.update(
                    {
                        "relevance_grade": "core",
                        "allowed_depth": "C",
                        "allowed_role": "background",
                        "family_label_supported": True,
                        "corrected_family": "verified c only family",
                    }
                )
        verified_c_only = validate_coverage(
            raw,
            self.search_routes(),
            self.lqs_scores(),
            self.corpus_expansion(),
            papers,
            citation,
            "full",
            core_families=["verified c only family"],
            topic_relevance_audit=audit,
        )
        self.assertFalse(verified_c_only["valid"], verified_c_only)
        self.assertIn("core_family_undercovered", verified_c_only["retained_missing"])

    def test_related_survey_relevance_counts_only_verified_retained_direct_surveys(self):
        from scripts.validate_topic_relevance import validate_topic_relevance

        raw = self.raw_candidates()
        papers = self.papers()
        citation = self.citation_plan()
        audit = self.topic_relevance_audit(raw, papers, citation)
        for row in audit:
            if row["paper_id"] in {"p200", "p201", "p202", "p203", "p204", "p205"}:
                row.update(
                    {
                        "relevance_grade": "direct_related_survey",
                        "allowed_depth": "C",
                        "allowed_role": "related_survey",
                        "family_label_supported": False,
                        "corrected_family": "related surveys and field context",
                    }
                )
            elif row.get("relevance_grade") == "direct_related_survey":
                row.update({"relevance_grade": "adjacent_background", "allowed_role": "background"})
        topic = validate_topic_relevance(raw, papers, citation, audit, "", "full")
        self.assertFalse(topic["valid"], topic)
        self.assertIn("related_survey_relevance_failed", topic["errors"])

    def test_topic_relevance_requires_second_audit_for_high_risk_ab_core_records(self):
        from scripts.runtime_dispatcher import collect_pending, mark_spawned, record_agent_output
        from scripts.survey_driver import run_until_complete as run_survey_until_complete
        from scripts.validate_topic_relevance import validate_topic_relevance

        raw = self.raw_candidates()
        papers = self.papers()
        citation = self.citation_plan()
        audit = self.topic_relevance_audit(raw, papers, citation)
        first = next(row for row in audit if row["paper_id"] == "p001")
        first.update(
            {
                "relevance_grade": "core",
                "allowed_depth": "A",
                "allowed_role": "core",
                "family_label_supported": True,
                "evidence_used": [{"field": "title", "text": first["title"]}, {"field": "query", "text": "embodied memory survey"}],
                "positive_topic_signals": [],
                "rationale": "Core paper.",
                "subagent_session_id": "primary-topic-agent",
            }
        )
        high_risk = validate_topic_relevance(raw, papers, citation, audit, "", "full")
        self.assertFalse(high_risk["valid"], high_risk)
        self.assertIn("topic_relevance_second_audit_required", high_risk["errors"])
        self.assertIn("p001", high_risk["second_audit_required_paper_ids"])

        second_audits = [
            {
                "paper_id": "p001",
                "primary_audit_session_id": "primary-topic-agent",
                "subagent_session_id": "secondary-topic-agent",
                "trigger_reasons": ["title_query_only_evidence", "missing_topic_boundary_rationale"],
                "evidence_used": [
                    {"field": "abstract", "text": "The paper uses image-grounded reasoning actions and visual intermediate-state reasoning."},
                    {"field": "source_metadata", "text": "The source metadata links it to visual workspace reasoning."},
                ],
                "decision": "confirm_core",
                "allowed_depth": "A",
                "allowed_role": "core",
                "rationale": "Independent secondary audit confirms the topic boundary using abstract and source metadata evidence.",
            }
        ]
        repaired = validate_topic_relevance(raw, papers, citation, audit, "", "full", secondary_audits=second_audits)
        self.assertNotIn("topic_relevance_second_audit_required", repaired["errors"])

        missing_primary_session_audit = [{key: value for key, value in row.items() if key not in {"subagent_session_id", "auditor_id"}} for row in audit]
        missing_session = validate_topic_relevance(raw, papers, citation, missing_primary_session_audit, "", "full", secondary_audits=second_audits)
        self.assertFalse(missing_session["valid"], missing_session)
        self.assertIn("topic_relevance_second_audit_required", missing_session["errors"])
        self.assertIn("invalid_topic_relevance_second_audit", missing_session["errors"])
        self.assertIn("missing_primary_audit_session_id:p001", missing_session["secondary_audit_errors"])

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "topic second audit route", target="full")
            state = task_dir / "state"
            self.write_topic_profile(task_dir, topic="mllm think with image")
            write_jsonl(state / "raw_candidates.jsonl", raw)
            write_jsonl(state / "search_routes.jsonl", self.search_routes())
            write_jsonl(state / "lqs_scores.jsonl", self.lqs_scores())
            (state / "corpus_expansion.json").write_text(json.dumps(self.corpus_expansion()), encoding="utf-8")
            write_jsonl(state / "papers.jsonl", papers)
            write_jsonl(state / "citation_plan.jsonl", citation)
            write_jsonl(state / "topic_relevance_audit.jsonl", audit)
            phase_status = evaluate_phase_barriers(task_dir, "full")
            self.assertEqual(phase_status["blocked_by_phase"], "source_verification")
            self.assertEqual(phase_status["allowed_next_phase"], "topic_relevance_second_audit")

            driver_status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(driver_status["status"], "blocked_topic_relevance_second_audit_agent_spawn_required", driver_status)
            self.assertEqual(driver_status["next_action"], "spawn_topic_relevance_second_audit_agents")
            pending = collect_pending(task_dir)
            self.assertEqual([row["request_type"] for row in pending["pending_requests"]], ["topic_relevance_second_audit"])
            request = pending["pending_requests"][0]
            payload = request["payload"]
            self.assertEqual(payload["expected_paper_ids"], ["p001"])
            self.assertEqual(payload["trigger_reasons_by_paper"]["p001"], ["title_query_only_evidence", "missing_topic_boundary_rationale"])

            mark_spawned(task_dir, request["request_id"], "primary-topic-agent")
            same_session_output = Path(tmp) / "same-session-second-audit.json"
            bad_result = {
                "batch_id": request["batch_id"],
                "status": "resolved",
                "paper_ids": ["p001"],
                "secondary_audit_records": [{**second_audits[0], "subagent_session_id": "primary-topic-agent"}],
                "validator_results": [{"validator": "validate_topic_relevance_second_audit", "status": "passed"}],
                "remaining_blockers": [],
            }
            same_session_output.write_text(json.dumps(bad_result, sort_keys=True), encoding="utf-8")
            same_session_record = record_agent_output(task_dir, request["request_id"], same_session_output)
            self.assertEqual(same_session_record["status"], "invalid_result", same_session_record)
            self.assertIn("secondary_audit_not_independent", same_session_record["record_result"]["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "topic second audit valid", target="full")
            state = task_dir / "state"
            self.write_topic_profile(task_dir, topic="mllm think with image")
            write_jsonl(state / "raw_candidates.jsonl", raw)
            write_jsonl(state / "search_routes.jsonl", self.search_routes())
            write_jsonl(state / "lqs_scores.jsonl", self.lqs_scores())
            (state / "corpus_expansion.json").write_text(json.dumps(self.corpus_expansion()), encoding="utf-8")
            write_jsonl(state / "papers.jsonl", papers)
            write_jsonl(state / "citation_plan.jsonl", citation)
            write_jsonl(state / "topic_relevance_audit.jsonl", audit)
            run_survey_until_complete(task_dir, target="full", max_steps=5)
            request = collect_pending(task_dir)["pending_requests"][0]
            mark_spawned(task_dir, request["request_id"], "secondary-topic-agent")
            valid_output = Path(tmp) / "valid-second-audit.json"
            valid_result = {
                "batch_id": request["batch_id"],
                "status": "resolved",
                "paper_ids": ["p001"],
                "secondary_audit_records": second_audits,
                "validator_results": [{"validator": "validate_topic_relevance_second_audit", "status": "passed"}],
                "remaining_blockers": [],
            }
            valid_output.write_text(json.dumps(valid_result, sort_keys=True), encoding="utf-8")
            valid_record = record_agent_output(task_dir, request["request_id"], valid_output)
            self.assertEqual(valid_record["status"], "result_recorded", valid_record)
            after_second_audit = evaluate_phase_barriers(task_dir, "full")
            self.assertNotEqual(after_second_audit["allowed_next_phase"], "topic_relevance_second_audit")

        downgraded = [
            {
                **second_audits[0],
                "decision": "downgrade_to_C",
                "allowed_depth": "C",
                "allowed_role": "background",
                "rationale": "Independent secondary audit finds this is useful background but not within the A/B topic boundary.",
            }
        ]
        downgraded_status = validate_topic_relevance(raw, papers, citation, audit, "", "full", secondary_audits=downgraded)
        self.assertIn("ab_topic_relevance_failed", downgraded_status["errors"])
        self.assertIn("p001", downgraded_status["invalid_ab_paper_ids"])

    def test_topic_relevance_runtime_and_dispatcher_use_real_fixture_records(self):
        from scripts.runtime_dispatcher import collect_pending, mark_spawned, record_agent_output
        from scripts.topic_relevance_runtime_executor import collect_topic_relevance_status, prepare_topic_relevance_batches
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "topic relevance dispatcher", target="short")
            self.populate_topic_fixture_task(task_dir, "mllm_think_with_image_anchor", include_audit=False)
            status = run_survey_until_complete(task_dir, target="short", max_steps=5)
            self.assertEqual(status["status"], "blocked_topic_relevance_agent_spawn_required")
            self.assertEqual(status["next_action"], "spawn_topic_relevance_agents")
            pending = collect_pending(task_dir)
            request = next(row for row in pending["pending_requests"] if row["request_type"] == "topic_relevance")
            self.assertIn("topic_relevance_runtime_executor.py", request["record_command"])
            mark_spawned(task_dir, request["request_id"], "topic-agent-001")
            runtime = collect_topic_relevance_status(task_dir)
            active = next(batch for batch in runtime["batches"] if batch["batch_id"] == request["batch_id"])
            fixture_rows = read_jsonl(ROOT / "tests" / "fixtures" / "topic_relevance" / "mllm_think_with_image_anchor" / "topic_relevance_audit.jsonl")
            output_file = Path(tmp) / "topic-worker-output.json"
            output = {
                "batch_id": active["batch_id"],
                "status": "resolved",
                "audit_records": [row for row in fixture_rows if row["paper_id"] in set(active["paper_ids"])],
                "validator_results": [{"validator": "validate_topic_relevance", "status": "passed", "command": "validate_topic_relevance", "result": "OK"}],
                "remaining_blockers": [],
            }
            output_file.write_text(json.dumps(output, sort_keys=True), encoding="utf-8")
            recorded = record_agent_output(task_dir, request["request_id"], output_file)
            self.assertEqual(recorded["status"], "result_recorded", recorded)
            self.assertEqual(recorded["record_result"]["status"], "recorded")
            recorded_audits = read_jsonl(task_dir / "state/topic_relevance_audit.jsonl")
            self.assertTrue(recorded_audits)
            self.assertTrue(
                all(row.get("subagent_session_id") == "topic-agent-001" for row in recorded_audits if row["paper_id"] in set(active["paper_ids"]))
            )

    def test_topic_relevance_rebalance_uses_audited_replacement_pool(self):
        from scripts.rebalance_ab_selection import rebalance_ab_selection
        from scripts.validate_topic_relevance import validate_topic_relevance

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "topic relevance rebalance", target="full")
            self.populate_topic_fixture_task(task_dir, "mllm_think_with_image_drift", include_audit=True)
            state = task_dir / "state"
            before = validate_topic_relevance(
                read_jsonl(state / "raw_candidates.jsonl"),
                read_jsonl(state / "papers.jsonl"),
                read_jsonl(state / "citation_plan.jsonl"),
                read_jsonl(state / "topic_relevance_audit.jsonl"),
                (state / "survey_type_plan.yml").read_text(encoding="utf-8"),
                "full",
            )
            blocked = before["invalid_ab_paper_ids"][:3]
            self.assertTrue(blocked, before)
            result = rebalance_ab_selection(task_dir, blocked, target="full", reason="topic_relevance")
            self.assertIn(result["status"], {"rebalanced", "rebalanced_but_coverage_invalid"}, result)
            citation = read_jsonl(state / "citation_plan.jsonl")
            depth = {row["paper_id"]: row["depth"] for row in citation}
            self.assertTrue(all(depth[pid] == "C" for pid in blocked))
            decisions = read_jsonl(state / "ab_rebalance_decisions.jsonl")
            self.assertTrue(all(item["reason"] == "topic_relevance_failed_for_a_b" for item in decisions[-len(blocked):]))

    def test_survey_driver_routes_paper_understanding_and_gate7(self):
        from scripts.paper_understanding_runtime_executor import collect_paper_understanding_status, record_paper_understanding_result
        from scripts.survey_driver import run_until_complete as run_survey_until_complete

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "survey driver paper phase", target="full")
            self.populate_source_verified_task(task_dir)
            status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["schema_version"], 1)
            self.assertEqual(status["component"], "survey_driver")
            self.assertEqual(status["status"], "blocked_paper_understanding_agent_spawn_required")
            self.assertEqual(status["next_action"], "spawn_paper_understanding_agents")
            self.assertEqual(status["blocked_by_phase"], "paper_understanding")
            self.assertEqual(status["active_batch_id"], "PU001")
            history = [json.loads(line) for line in (task_dir / "state/survey_driver_history.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(history[-1]["blocked_by_phase"], "paper_understanding")

            runtime = collect_paper_understanding_status(task_dir)
            active = runtime["batches"][0]
            recorded = record_paper_understanding_result(task_dir, self.paper_understanding_result(active, task_dir), "paper-agent-001")
            self.assertEqual(recorded["status"], "recorded", recorded)
            next_status = run_survey_until_complete(task_dir, target="full", max_steps=2)
            self.assertEqual(next_status["status"], "blocked_paper_understanding_agent_spawn_required")
            self.assertEqual(next_status["active_batch_id"], "PU002")

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "survey driver gate7", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "state/expert_review_reports.jsonl").write_text("", encoding="utf-8")
            status = run_survey_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["component"], "survey_driver")
            self.assertEqual(status["status"], "blocked_subagent_spawn_required")
            self.assertEqual(status["next_action"], "spawn_reviewers")
            self.assertEqual(status["summary"]["delegated_component"], "gate7_driver")

    def test_full_text_source_planner_and_rebalance_helpers(self):
        from scripts.full_text_source_planner import build_full_text_fetch_plan
        from scripts.rebalance_ab_selection import rebalance_ab_selection

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "source planner", target="full")
            self.populate_source_verified_task(task_dir)
            papers = self.papers()
            papers[0]["arxiv_id"] = "2401.00001"
            papers[1]["openreview_url"] = "https://openreview.net/forum?id=test"
            write_jsonl(task_dir / "state/papers.jsonl", papers)
            plan = build_full_text_fetch_plan(task_dir)
            self.assertEqual(plan["schema_version"], 1)
            self.assertEqual(plan["summary"]["planned_paper_count"], 95)
            first = [json.loads(line) for line in (task_dir / "state/full_text_fetch_plan.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()][0]
            self.assertIn("https://arxiv.org/pdf/2401.00001", first["candidate_urls"])

            result = rebalance_ab_selection(task_dir, ["p001"])
            self.assertEqual(result["status"], "rebalanced")
            citation = [json.loads(line) for line in (task_dir / "state/citation_plan.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            depth = {row["paper_id"]: row["depth"] for row in citation}
            self.assertEqual(depth["p001"], "C")
            self.assertEqual(sum(1 for value in depth.values() if value == "A"), 25)
            self.assertEqual(sum(1 for value in depth.values() if value == "B"), 70)
            decisions = [json.loads(line) for line in (task_dir / "state/ab_rebalance_decisions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(decisions[-1]["downgraded_paper_id"], "p001")

    def test_gate7_driver_stops_at_major_rebuild_not_repair_with_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "gate7 major rebuild", target="full")
            self.populate_full_task(task_dir)
            weakness = {
                **self.weakness("BW1"),
                "route_to": "paper_understanding",
                "affected_sections": ["Method Families"],
                "affected_papers": ["p001"],
                "affected_claims": ["c1"],
            }
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", self.expert_reviews(score=4.1, weaknesses=[weakness]))
            write_jsonl(task_dir / "state/expert_review_invocations.jsonl", self.expert_invocations())
            (task_dir / "state/expert_review_adjudication.json").write_text(json.dumps({"review_round_id": None, "all_major_weaknesses_adjudicated": False, "canonical_weaknesses": []}), encoding="utf-8")
            status = run_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["schema_version"], 1)
            self.assertEqual(status["component"], "gate7_driver")
            self.assertEqual(status["status"], "blocked_repair_agent_spawn_required")
            self.assertEqual(status["next_action"], "spawn_repair_agents")
            self.assertFalse(status["terminal"])
            self.assertTrue(status["blocked"])
            self.assertEqual(status["active_batch_id"], "RB001")
            self.assertEqual(status["summary"]["active_batch_id"], "RB001")
            self.assertEqual(status["summary"]["spawn_request_count"], 1)
            plan = json.loads((task_dir / "state/gate7_repair_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["schema_version"], 1)
            self.assertEqual(plan["rerun_policy"], "full_gate7_round")
            self.assertTrue(plan["major_rebuild_required"])
            runtime_action = json.loads((task_dir / "state/gate7_runtime_action.json").read_text(encoding="utf-8"))
            self.assertEqual(runtime_action["status"], "pending_runtime_repair")
            self.assertEqual(runtime_action["rerun_policy"], "full_gate7_round")
            self.assertEqual(runtime_action["active_batch_id"], "RB001")
            self.assertEqual(runtime_action["schema_version"], 1)
            self.assertEqual(runtime_action["summary"]["active_batch_id"], "RB001")
            self.assertEqual(runtime_action["summary"]["active_rollback_phase"], "paper_understanding")
            iteration = json.loads((task_dir / "state/review_iteration_status.json").read_text(encoding="utf-8"))
            self.assertEqual(iteration["last_median_score"], 4.1)
            self.assertEqual(iteration["status"], "major_rebuild_required")

    def test_gate7_runtime_executor_batches_repairs_by_phase_and_records_results(self):
        from scripts.gate7_runtime_executor import collect_runtime_repair_status, record_runtime_repair_result

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "gate7 runtime executor", target="full")
            self.populate_full_task(task_dir)
            reports = self.expert_reviews(score=4.1)
            reports[0]["blocking_weaknesses"] = [
                {
                    **self.weakness("BW1"),
                    "route_to": "paper_understanding",
                    "affected_sections": ["Method Families"],
                    "affected_papers": ["p001"],
                    "affected_claims": ["c1"],
                },
                {
                    **self.weakness("BW2"),
                    "route_to": "article_quality",
                    "affected_sections": ["Related Surveys"],
                    "affected_papers": [],
                    "affected_claims": [],
                },
            ]
            reports[2]["blocking_weaknesses"] = [
                {
                    **self.weakness("BW3"),
                    "route_to": "claim_evidence",
                    "affected_sections": ["Evidence and Limitations"],
                    "affected_papers": ["p001"],
                    "affected_claims": ["c1"],
                }
            ]
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", reports)
            write_jsonl(task_dir / "state/expert_review_invocations.jsonl", self.expert_invocations())
            (task_dir / "state/expert_review_adjudication.json").write_text(json.dumps({"review_round_id": None, "all_major_weaknesses_adjudicated": False, "canonical_weaknesses": []}), encoding="utf-8")

            status = run_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_repair_agent_spawn_required")
            self.assertEqual(status["next_action"], "spawn_repair_agents")
            self.assertEqual(status["spawn_request_count"], 1)
            batches = json.loads((task_dir / "state/gate7_repair_batches.json").read_text(encoding="utf-8"))
            self.assertEqual(batches["schema_version"], 1)
            self.assertEqual(batches["summary"]["batch_count"], 3)
            self.assertEqual(batches["summary"]["active_batch_id"], "RB001")
            self.assertEqual(batches["summary"]["active_rollback_phase"], "paper_understanding")
            self.assertEqual(batches["summary"]["pending_batch_count"], 3)
            self.assertEqual(batches["summary"]["resolved_batch_count"], 0)
            self.assertEqual(batches["summary"]["rerun_policy"], "full_gate7_round")
            self.assertEqual([batch["rollback_phase"] for batch in batches["batches"]], ["paper_understanding", "synthesis", "article"])
            self.assertEqual(batches["active_batch_id"], "RB001")
            self.assertEqual(batches["batches"][0]["status"], "pending_spawn")
            self.assertEqual(batches["batches"][1]["status"], "blocked_by_upstream")
            self.assertEqual(batches["batches"][2]["status"], "blocked_by_upstream")
            spawn_requests = json.loads((task_dir / "state/gate7_spawn_requests.json").read_text(encoding="utf-8"))
            self.assertEqual(len(spawn_requests["spawn_requests"]), 1)
            self.assertEqual(spawn_requests["spawn_requests"][0]["batch_id"], "RB001")
            self.assertEqual(spawn_requests["spawn_requests"][0]["repair_item_count"], 1)
            self.assertEqual(spawn_requests["spawn_requests"][0]["result_schema_version"], 1)
            self.assertEqual(spawn_requests["spawn_requests"][0]["expected_weakness_ids"], ["CW001"])
            self.assertEqual(
                spawn_requests["spawn_requests"][0]["expected_changed_artifacts"],
                batches["batches"][0]["changed_artifacts"],
            )
            self.assertEqual(
                spawn_requests["spawn_requests"][0]["expected_acceptance_validators"],
                batches["batches"][0]["acceptance_validators"],
            )
            self.assertIn("batch_id", spawn_requests["spawn_requests"][0]["required_result_keys"])

            for expected_batch_id in ["RB001", "RB002", "RB003"]:
                runtime = collect_runtime_repair_status(task_dir)
                self.assertEqual(runtime["schema_version"], 1)
                self.assertEqual(runtime["component"], "gate7_runtime_executor")
                self.assertEqual(runtime["next_action"], "spawn_repair_agents")
                self.assertFalse(runtime["terminal"])
                self.assertTrue(runtime["blocked"])
                self.assertEqual(runtime["active_batch_id"], expected_batch_id)
                self.assertEqual(runtime["summary"]["active_batch_id"], expected_batch_id)
                active = next(batch for batch in runtime["batches"] if batch["batch_id"] == expected_batch_id)
                candidate = task_dir / "outputs/survey_candidate.md"
                candidate.write_text(candidate.read_text(encoding="utf-8") + f"\n\nRuntime repair completed for {expected_batch_id}.\n", encoding="utf-8")
                recorded = record_runtime_repair_result(task_dir, self.runtime_repair_result(active, task_dir), f"repair-agent-{expected_batch_id}")
                self.assertEqual(recorded["status"], "recorded", recorded)

            runtime_done = collect_runtime_repair_status(task_dir)
            self.assertTrue(runtime_done["terminal"])
            self.assertFalse(runtime_done["blocked"])
            self.assertEqual(runtime_done["next_action"], "reset_full_review_round")
            self.assertTrue(runtime_done["all_batches_resolved"], runtime_done)
            self.assertTrue(runtime_done["ready_for_full_reround"], runtime_done)
            repair_rows = [json.loads(line) for line in (task_dir / "state/repair_actions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            regression_rows = [json.loads(line) for line in (task_dir / "state/regression_checks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(repair_rows), 3)
            self.assertEqual(len(regression_rows), 3)
            reround = run_until_complete(task_dir, target="full", max_steps=10)
            self.assertEqual(reround["status"], "blocked_subagent_spawn_required")
            self.assertEqual(reround["next_action"], "spawn_reviewers")
            self.assertEqual(reround["spawn_request_count"], 5)

    def test_gate7_runtime_executor_rejects_partial_batch_results_before_recording(self):
        from scripts.gate7_runtime_executor import collect_runtime_repair_status, record_runtime_repair_result

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "gate7 partial batch", target="full")
            self.populate_full_task(task_dir)
            reports = self.expert_reviews(score=4.1)
            reports[0]["blocking_weaknesses"] = [
                {
                    **self.weakness("BW1"),
                    "route_to": "synthesis_dossiers",
                    "affected_sections": ["Method Families"],
                    "affected_papers": ["p001"],
                    "affected_claims": ["c1"],
                    "repair_acceptance_criteria": "Repair method family synthesis.",
                },
                {
                    **self.weakness("BW2"),
                    "route_to": "benchmark_dossiers",
                    "affected_sections": ["Benchmark and Evaluation"],
                    "affected_papers": ["p002"],
                    "affected_claims": ["c1"],
                    "repair_acceptance_criteria": "Repair benchmark synthesis.",
                },
            ]
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", reports)
            write_jsonl(task_dir / "state/expert_review_invocations.jsonl", self.expert_invocations())
            (task_dir / "state/expert_review_adjudication.json").write_text(json.dumps({"review_round_id": None, "all_major_weaknesses_adjudicated": False, "canonical_weaknesses": []}), encoding="utf-8")

            status = run_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_repair_agent_spawn_required")
            runtime = collect_runtime_repair_status(task_dir)
            active = next(batch for batch in runtime["batches"] if batch["batch_id"] == runtime["active_batch_id"])
            self.assertEqual(active["repair_item_count"], 2)
            candidate = task_dir / "outputs/survey_candidate.md"
            candidate.write_text(candidate.read_text(encoding="utf-8") + "\n\nPartial batch repair attempt.\n", encoding="utf-8")

            partial = self.runtime_repair_result(active, task_dir)
            partial["repair_records"] = partial["repair_records"][:1]
            partial["regression_checks"] = partial["regression_checks"][:1]
            recorded = record_runtime_repair_result(task_dir, partial, "repair-agent-partial")
            self.assertEqual(recorded["status"], "invalid", recorded)
            self.assertEqual(recorded["error"], "invalid_repair_result")
            self.assertIn("missing_batch_repair_records", recorded["errors"])
            self.assertIn("missing_batch_regression_checks", recorded["errors"])
            self.assertEqual((task_dir / "state/repair_actions.jsonl").read_text(encoding="utf-8"), "")
            self.assertEqual((task_dir / "state/regression_checks.jsonl").read_text(encoding="utf-8"), "")
            still_active = collect_runtime_repair_status(task_dir)
            self.assertEqual(still_active["active_batch_id"], active["batch_id"])

            extra = self.runtime_repair_result(active, task_dir)
            extra["repair_records"].append(self.repair_actions("CW999")[0])
            extra["regression_checks"].append(self.regression_checks("CW999")[0])
            recorded_extra = record_runtime_repair_result(task_dir, extra, "repair-agent-extra")
            self.assertEqual(recorded_extra["status"], "invalid", recorded_extra)
            self.assertIn("unknown_repair_weakness_ids", recorded_extra["errors"])
            self.assertIn("unknown_regression_weakness_ids", recorded_extra["errors"])
            self.assertEqual((task_dir / "state/repair_actions.jsonl").read_text(encoding="utf-8"), "")
            self.assertEqual((task_dir / "state/regression_checks.jsonl").read_text(encoding="utf-8"), "")

            duplicate = self.runtime_repair_result(active, task_dir)
            duplicate["repair_records"].append(dict(duplicate["repair_records"][0]))
            duplicate["regression_checks"].append(dict(duplicate["regression_checks"][0]))
            recorded_duplicate = record_runtime_repair_result(task_dir, duplicate, "repair-agent-duplicate")
            self.assertEqual(recorded_duplicate["status"], "invalid", recorded_duplicate)
            self.assertIn("duplicate_repair_weakness_ids", recorded_duplicate["errors"])
            self.assertIn("duplicate_regression_weakness_ids", recorded_duplicate["errors"])
            self.assertEqual((task_dir / "state/repair_actions.jsonl").read_text(encoding="utf-8"), "")
            self.assertEqual((task_dir / "state/regression_checks.jsonl").read_text(encoding="utf-8"), "")

    def test_gate7_runtime_executor_requires_changed_artifact_hash_audit(self):
        from scripts.gate7_runtime_executor import collect_runtime_repair_status, record_runtime_repair_result

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "gate7 artifact hash audit", target="full")
            self.populate_full_task(task_dir)
            weakness = {
                **self.weakness("BW1"),
                "route_to": "paper_understanding",
                "affected_sections": ["Method Families"],
                "affected_papers": ["p001"],
                "affected_claims": ["c1"],
            }
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", self.expert_reviews(score=4.1, weaknesses=[weakness]))
            write_jsonl(task_dir / "state/expert_review_invocations.jsonl", self.expert_invocations())
            (task_dir / "state/expert_review_adjudication.json").write_text(json.dumps({"review_round_id": None, "all_major_weaknesses_adjudicated": False, "canonical_weaknesses": []}), encoding="utf-8")

            status = run_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_repair_agent_spawn_required")
            runtime = collect_runtime_repair_status(task_dir)
            active = next(batch for batch in runtime["batches"] if batch["batch_id"] == runtime["active_batch_id"])
            self.assertTrue(active["changed_artifacts"])
            candidate = task_dir / "outputs/survey_candidate.md"
            candidate.write_text(candidate.read_text(encoding="utf-8") + "\n\nArtifact hash repair attempt.\n", encoding="utf-8")
            first_artifact = active["changed_artifacts"][0]

            missing_changed = self.runtime_repair_result(active, task_dir)
            missing_changed["changed_artifacts"] = [artifact for artifact in missing_changed["changed_artifacts"] if artifact != first_artifact]
            recorded_missing_changed = record_runtime_repair_result(task_dir, missing_changed, "repair-agent-missing-changed")
            self.assertEqual(recorded_missing_changed["status"], "invalid", recorded_missing_changed)
            self.assertIn("missing_changed_artifacts", recorded_missing_changed["errors"])
            self.assertEqual((task_dir / "state/repair_actions.jsonl").read_text(encoding="utf-8"), "")
            self.assertEqual((task_dir / "state/regression_checks.jsonl").read_text(encoding="utf-8"), "")

            missing_hash = self.runtime_repair_result(active, task_dir)
            missing_hash["artifact_hashes_after"].pop(first_artifact)
            recorded_missing_hash = record_runtime_repair_result(task_dir, missing_hash, "repair-agent-missing-hash")
            self.assertEqual(recorded_missing_hash["status"], "invalid", recorded_missing_hash)
            self.assertIn("missing_artifact_hashes_after", recorded_missing_hash["errors"])
            self.assertEqual((task_dir / "state/repair_actions.jsonl").read_text(encoding="utf-8"), "")
            self.assertEqual((task_dir / "state/regression_checks.jsonl").read_text(encoding="utf-8"), "")

            mismatch = self.runtime_repair_result(active, task_dir)
            mismatch["artifact_hashes_after"][first_artifact] = "not-the-real-hash"
            recorded_mismatch = record_runtime_repair_result(task_dir, mismatch, "repair-agent-hash-mismatch")
            self.assertEqual(recorded_mismatch["status"], "invalid", recorded_mismatch)
            self.assertIn("artifact_hash_mismatch", recorded_mismatch["errors"])
            self.assertEqual((task_dir / "state/repair_actions.jsonl").read_text(encoding="utf-8"), "")
            self.assertEqual((task_dir / "state/regression_checks.jsonl").read_text(encoding="utf-8"), "")

    def test_gate7_runtime_executor_requires_acceptance_validator_coverage(self):
        from scripts.gate7_runtime_executor import collect_runtime_repair_status, record_runtime_repair_result

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "gate7 validator coverage", target="full")
            self.populate_full_task(task_dir)
            weakness = {
                **self.weakness("BW1"),
                "route_to": "paper_understanding",
                "affected_sections": ["Method Families"],
                "affected_papers": ["p001"],
                "affected_claims": ["c1"],
            }
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", self.expert_reviews(score=4.1, weaknesses=[weakness]))
            write_jsonl(task_dir / "state/expert_review_invocations.jsonl", self.expert_invocations())
            (task_dir / "state/expert_review_adjudication.json").write_text(json.dumps({"review_round_id": None, "all_major_weaknesses_adjudicated": False, "canonical_weaknesses": []}), encoding="utf-8")

            status = run_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_repair_agent_spawn_required")
            runtime = collect_runtime_repair_status(task_dir)
            active = next(batch for batch in runtime["batches"] if batch["batch_id"] == runtime["active_batch_id"])
            self.assertGreater(len(active["acceptance_validators"]), 1)
            candidate = task_dir / "outputs/survey_candidate.md"
            candidate.write_text(candidate.read_text(encoding="utf-8") + "\n\nValidator coverage repair attempt.\n", encoding="utf-8")

            missing = self.runtime_repair_result(active, task_dir)
            missing["validator_results"] = missing["validator_results"][:1]
            recorded = record_runtime_repair_result(task_dir, missing, "repair-agent-missing-validator")
            self.assertEqual(recorded["status"], "invalid", recorded)
            self.assertEqual(recorded["error"], "invalid_repair_result")
            self.assertIn("missing_acceptance_validators", recorded["errors"])
            self.assertEqual((task_dir / "state/repair_actions.jsonl").read_text(encoding="utf-8"), "")
            self.assertEqual((task_dir / "state/regression_checks.jsonl").read_text(encoding="utf-8"), "")

            unnamed = self.runtime_repair_result(active, task_dir)
            unnamed["validator_results"] = [{"command": "phase validators", "status": "passed", "result": "OK"}]
            recorded_unnamed = record_runtime_repair_result(task_dir, unnamed, "repair-agent-unnamed-validator")
            self.assertEqual(recorded_unnamed["status"], "invalid", recorded_unnamed)
            self.assertIn("missing_acceptance_validators", recorded_unnamed["errors"])
            self.assertEqual((task_dir / "state/repair_actions.jsonl").read_text(encoding="utf-8"), "")
            self.assertEqual((task_dir / "state/regression_checks.jsonl").read_text(encoding="utf-8"), "")

    def test_gate7_runtime_executor_local_article_repair_uses_targeted_rereview(self):
        from scripts.gate7_runtime_executor import collect_runtime_repair_status, record_runtime_repair_result

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "gate7 article repair", target="full")
            self.populate_full_task(task_dir)
            weakness = {
                **self.weakness("BW1"),
                "route_to": "article_quality",
                "affected_sections": ["Related Surveys"],
                "affected_papers": [],
                "affected_claims": [],
            }
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", self.expert_reviews(score=8.8, weaknesses=[weakness]))
            write_jsonl(task_dir / "state/expert_review_invocations.jsonl", self.expert_invocations())
            (task_dir / "state/expert_review_adjudication.json").write_text(json.dumps({"review_round_id": None, "all_major_weaknesses_adjudicated": False, "canonical_weaknesses": []}), encoding="utf-8")

            status = run_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_repair_agent_spawn_required")
            self.assertEqual(status["rerun_policy"], "targeted_rereview")
            runtime = collect_runtime_repair_status(task_dir)
            active = next(batch for batch in runtime["batches"] if batch["batch_id"] == runtime["active_batch_id"])
            candidate = task_dir / "outputs/survey_candidate.md"
            candidate.write_text(candidate.read_text(encoding="utf-8") + "\n\nLocal prose repair adds publication-ready cleanup.\n", encoding="utf-8")
            recorded = record_runtime_repair_result(task_dir, self.runtime_repair_result(active, task_dir), "repair-agent-article")
            self.assertEqual(recorded["status"], "recorded", recorded)
            after_repair = run_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(after_repair["status"], "blocked_subagent_spawn_required")
            self.assertEqual(after_repair["next_action"], "spawn_targeted_rereviewers")

    def test_gate7_driver_repeated_blocker_and_quality_limited_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "gate7 waiting blocker", target="full")
            self.populate_full_task(task_dir)
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", self.expert_reviews()[:4])
            write_jsonl(task_dir / "state/expert_review_invocations.jsonl", self.expert_invocations()[:4])
            (task_dir / "state/expert_review_round_status.json").write_text(json.dumps(self.review_round_status(returned=4)), encoding="utf-8")
            first = run_until_complete(task_dir, target="full", max_steps=2)
            second = run_until_complete(task_dir, target="full", max_steps=2)
            third = run_until_complete(task_dir, target="full", max_steps=2)
            self.assertEqual(first["status"], "waiting_for_expert_reviews")
            self.assertEqual(second["status"], "waiting_for_expert_reviews")
            self.assertEqual(third["status"], "blocked_repeated_no_progress")
            history = [json.loads(line) for line in (task_dir / "state/gate7_driver_history.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreaterEqual(len(history), 3)
            self.assertEqual(history[-1]["blocker_fingerprint"], history[-2]["blocker_fingerprint"])

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "gate7 quality limited", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "state/review_iteration_status.json").write_text(json.dumps({"round": 3, "last_median_score": 8.2, "previous_median_score": 8.1, "status": "quality_limited"}), encoding="utf-8")
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "quality_limited_stop")
            stopped = run_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(stopped["status"], "quality_limited_stop")
            self.assertEqual(stopped["next_action"], "quality_limited_stop")

    def test_gate7_stale_adjudication_rebuilds_and_unions_route_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "gate7 stale adjudication", target="full")
            self.populate_full_task(task_dir)
            weakness = {
                **self.weakness("BW1"),
                "route_to": "claim_evidence",
                "required_evidence_check": ["section_evidence_plans"],
                "affected_sections": ["Evidence and Limitations"],
                "affected_papers": [],
                "affected_claims": [],
            }
            reports = self.expert_reviews(weaknesses=[weakness])
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", reports)
            stale = {
                "review_round_id": "round-1",
                "all_major_weaknesses_adjudicated": True,
                "canonical_weaknesses": [
                    {
                        "weakness_id": "BW1",
                        "severity": "major",
                        "source_reviewers": ["domain_expert"],
                        "source_weakness_ids": ["BW1"],
                        "affected_sections": ["Evidence and Limitations"],
                        "affected_papers": [],
                        "affected_claims": [],
                        "route_to": "claim_evidence",
                        "required_evidence_check": ["section_evidence_plans"],
                        "repair_acceptance_criteria": "Repair claim evidence.",
                    }
                ],
            }
            (task_dir / "state/expert_review_adjudication.json").write_text(json.dumps(stale), encoding="utf-8")
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "adjudicate")
            adjudicated = adjudicate_reports(task_dir)
            canonical = adjudicated["canonical_weaknesses"][0]
            self.assertEqual(canonical["weakness_id"], "CW001")
            self.assertIn("domain_expert:BW1", canonical["source_weakness_ids"])
            self.assertIn("claim_evidence_spans", canonical["required_evidence_check"])
            self.assertIn("full_text_source", canonical["required_evidence_check"])
            self.assertIn("section_evidence_plans", canonical["required_evidence_check"])
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "repair_with_evidence")
            plan = build_repair_plan(task_dir, "full")
            self.assertIn("claim_evidence_spans", plan["repair_items"][0]["required_evidence_check"])
            self.assertIn("full_text_source", plan["repair_items"][0]["required_evidence_check"])

    def test_gate7_full_reround_after_runtime_repair_resets_active_round(self):
        from scripts.gate7_runtime_executor import collect_runtime_repair_status, record_runtime_repair_result

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "gate7 full reround", target="full")
            self.populate_full_task(task_dir)
            weakness = {
                **self.weakness("BW1"),
                "route_to": "paper_understanding",
                "affected_sections": ["Method Families"],
                "affected_papers": ["p001"],
                "affected_claims": ["c1"],
            }
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", self.expert_reviews(score=4.1, weaknesses=[weakness]))
            write_jsonl(task_dir / "state/expert_review_invocations.jsonl", self.expert_invocations())
            (task_dir / "state/expert_review_adjudication.json").write_text(json.dumps({"review_round_id": None, "all_major_weaknesses_adjudicated": False, "canonical_weaknesses": []}), encoding="utf-8")
            first = run_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(first["status"], "blocked_repair_agent_spawn_required")

            candidate = task_dir / "outputs/survey_candidate.md"
            candidate.write_text(candidate.read_text(encoding="utf-8") + "\n\nRepair adds source-grounded mechanism evidence.\n", encoding="utf-8")
            runtime = collect_runtime_repair_status(task_dir)
            active = next(batch for batch in runtime["batches"] if batch["batch_id"] == runtime["active_batch_id"])
            recorded = record_runtime_repair_result(task_dir, self.runtime_repair_result(active, task_dir), "repair-agent-full")
            self.assertEqual(recorded["status"], "recorded", recorded)
            write_jsonl(
                task_dir / "state/gate7_regression_requests.jsonl",
                [{"request_id": "regression-before-reround", "status": "pending"}],
            )

            second = run_until_complete(task_dir, target="full", max_steps=10)
            self.assertEqual(second["status"], "blocked_subagent_spawn_required")
            self.assertEqual(second["next_action"], "spawn_reviewers")
            self.assertEqual(second["spawn_request_count"], 5)
            self.assertEqual(read_text_if_exists(task_dir / "state/expert_review_reports.jsonl"), "")
            self.assertEqual((task_dir / "state/repair_actions.jsonl").read_text(encoding="utf-8"), "")
            self.assertTrue(list((task_dir / "state/gate7_rounds").glob("*")))
            active_adjudication = json.loads((task_dir / "state/expert_review_adjudication.json").read_text(encoding="utf-8"))
            self.assertEqual(active_adjudication["canonical_weaknesses"], [])
            spawn_requests = json.loads((task_dir / "state/gate7_spawn_requests.json").read_text(encoding="utf-8"))
            self.assertEqual(len(spawn_requests["spawn_requests"]), 5)
            archive_dir = next((task_dir / "state/gate7_rounds").glob("*"))
            archived_names = {path.name for path in archive_dir.iterdir()}
            for filename in [
                "gate7_repair_batches.json",
                "gate7_repair_results.jsonl",
                "gate7_driver_history.jsonl",
                "gate7_regression_requests.jsonl",
            ]:
                self.assertIn(filename, archived_names)
            active_batches = json.loads((task_dir / "state/gate7_repair_batches.json").read_text(encoding="utf-8"))
            self.assertEqual(active_batches["active_batch_id"], None)
            self.assertEqual(active_batches["batches"], [])
            self.assertEqual(active_batches["summary"]["batch_count"], 0)
            self.assertEqual((task_dir / "state/gate7_repair_results.jsonl").read_text(encoding="utf-8"), "")
            active_history = [json.loads(line) for line in (task_dir / "state/gate7_driver_history.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(active_history), 1)
            self.assertEqual(active_history[0]["active_batch_id"], None)
            self.assertEqual(active_history[0]["next_action"], "spawn_reviewers")
            self.assertEqual((task_dir / "state/gate7_regression_requests.jsonl").read_text(encoding="utf-8"), "")
            active_spawn_requests = json.loads((task_dir / "state/gate7_spawn_requests.json").read_text(encoding="utf-8"))
            self.assertEqual(active_spawn_requests["next_action"], "spawn_reviewers")
            self.assertEqual(len(active_spawn_requests["spawn_requests"]), 5)

    def test_bad_sample_fixture_blocks_early_and_gate7_requires_full_reround(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "bad mllm sample", target="full")
            self.populate_full_task(task_dir)
            bad_cards = self.mechanism_cards()
            for card in bad_cards:
                card["deep_read_notes"] = "The card records how the paper should be read rather than paper-specific evidence."
            write_jsonl(task_dir / "state/paper_mechanism_cards.jsonl", bad_cards)
            bad_claims = self.claims()
            bad_claims[0]["evidence_spans"][0]["excerpt"] = "Section-level full-text evidence is available for this claim."
            write_jsonl(task_dir / "state/claim_evidence_spans.jsonl", bad_claims)
            (task_dir / "outputs/survey_candidate.md").write_text(self.review_text() + "\n在“证据是否可靠”这一问题上，本文给出模板化回答。\n", encoding="utf-8")
            (task_dir / "outputs/appendix.md").write_text("", encoding="utf-8")
            weakness = {**self.weakness("BW1"), "route_to": "claim_evidence", "required_evidence_check": ["section_evidence_plans"]}
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", self.expert_reviews(score=4.1, weaknesses=[weakness]))
            write_jsonl(task_dir / "state/expert_review_invocations.jsonl", self.expert_invocations())
            (task_dir / "state/expert_review_adjudication.json").write_text(json.dumps(self.adjudication("BW1")), encoding="utf-8")

            phase = evaluate_phase_barriers(task_dir, "full")
            self.assertFalse(phase["phases"]["paper_understanding"]["passed"])
            self.assertFalse(phase["phases"]["synthesis"]["passed"])
            self.assertFalse(phase["phases"]["article"]["passed"])
            self.assertIn("template_deep_read_notes", phase["phases"]["paper_understanding"]["details"]["invalid_cards"]["p001"])
            claim_errors = phase["phases"]["synthesis"]["details"]["claim_evidence"]["invalid_claims"]["c1"]
            self.assertTrue(any(error.startswith("pseudo_evidence_span_for_strong_claim") for error in claim_errors))
            self.assertIn("empty_appendix", phase["phases"]["article"]["details"]["errors"])

            status = run_until_complete(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_repair_agent_spawn_required")
            self.assertEqual(status["rerun_policy"], "full_gate7_round")

    def test_phase_gate_blocks_downstream_when_paper_understanding_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            write_jsonl(task_dir / "state/paper_mechanism_cards.jsonl", self.mechanism_cards(94))
            status = evaluate_phase_barriers(task_dir, "full")
            self.assertEqual(status["schema_version"], 1)
            self.assertEqual(status["component"], "phase_gate")
            self.assertEqual(status["status"], "blocked")
            self.assertEqual(status["next_action"], status["allowed_next_phase"])
            self.assertFalse(status["terminal"])
            self.assertTrue(status["blocked"])
            self.assertEqual(status["active_batch_id"], None)
            self.assertEqual(status["summary"]["blocked_by_phase"], "paper_understanding")
            self.assertFalse(status["phases"]["paper_understanding"]["passed"])
            self.assertIn("illegal_downstream_artifacts", status["phases"]["paper_understanding"])

    def test_phase_gate_routes_blocked_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "state/expert_review_reports.jsonl").write_text("", encoding="utf-8")
            status = evaluate_phase_barriers(task_dir, "full")
            self.assertEqual(status["schema_version"], 1)
            self.assertEqual(status["component"], "phase_gate")
            self.assertEqual(status["status"], "blocked")
            self.assertEqual(status["next_action"], "spawn_expert_reviewers")
            self.assertFalse(status["terminal"])
            self.assertTrue(status["blocked"])
            self.assertEqual(status["blocked_by_phase"], "expert_review")
            self.assertEqual(status["allowed_next_phase"], "spawn_expert_reviewers")
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "outputs/survey_candidate.md").write_text("# Survey\n\n## Introduction\nA concise but underdeveloped draft.\n", encoding="utf-8")
            (task_dir / "outputs/survey_candidate.html").write_text("<html><h1>Survey</h1></html>", encoding="utf-8")
            (task_dir / "state/expansion_audit.jsonl").write_text("", encoding="utf-8")
            missing = evaluate_phase_barriers(task_dir, "full")
            self.assertEqual(missing["blocked_by_phase"], "article")
            self.assertEqual(missing["allowed_next_phase"], "expansion_audit")
            write_jsonl(task_dir / "state/expansion_audit.jsonl", self.expansion_audit())
            ready = evaluate_phase_barriers(task_dir, "full")
            self.assertEqual(ready["blocked_by_phase"], "article")
            self.assertEqual(ready["allowed_next_phase"], "article_repair_after_expansion_audit")

    def test_gate_check_full_fixture_passes_and_blocks_understanding_shortfall(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            legacy_name = "review" + ".md"
            (task_dir / "outputs" / legacy_name).write_text("# Legacy review\n", encoding="utf-8")
            legacy_gates = evaluate_gates(task_dir, "full")
            self.assertFalse(legacy_gates["gate_6_article_quality"]["passed"])
            self.assertFalse(legacy_gates["all_blocking_gates_passed"])
            (task_dir / "outputs" / legacy_name).unlink()
            self.assertTrue(evaluate_gates(task_dir, "full")["all_blocking_gates_passed"])
            (task_dir / "state/expert_review_reports.jsonl").write_text("", encoding="utf-8")
            (task_dir / "outputs/survey.md").write_text("# Premature final\n", encoding="utf-8")
            premature_gates = evaluate_gates(task_dir, "full")
            self.assertFalse(premature_gates["gate_6_article_quality"]["passed"])
            self.assertIn("premature_final_survey_artifact", premature_gates["gate_6_article_quality"]["errors"])
            self.assertEqual(premature_gates["completion_level"], "draft")
            (task_dir / "outputs/survey.md").unlink()
            write_jsonl(task_dir / "state/expert_review_reports.jsonl", self.expert_reviews())
            cards = self.mechanism_cards()
            for card in cards:
                card.update({"reading_depth": "abstract_metadata_only", "full_text_accessed": False, "source_type": "curated list metadata", "sections_read": ["title and abstract"], "evidence_span_locations": ["curated-list row"]})
            write_jsonl(task_dir / "state/paper_mechanism_cards.jsonl", cards)
            gates = evaluate_gates(task_dir, "full")
            self.assertTrue(gates["gate_4_coverage"]["coverage_expanded"])
            self.assertFalse(gates["gate_2_paper_understanding"]["paper_understanding_complete"])
            self.assertFalse(gates["all_blocking_gates_passed"])

    def test_release_promotion_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            self.assertFalse((task_dir / "outputs/survey.md").exists())
            manifest = promote_release(task_dir, "full")
            self.assertTrue(manifest["released"], manifest)
            self.assertEqual(manifest["completion_level"], "publication_ready")
            self.assertTrue((task_dir / "outputs/survey.md").exists())
            self.assertTrue((task_dir / "outputs/survey.html").exists())
            self.assertTrue(evaluate_gates(task_dir, "full")["all_blocking_gates_passed"])
            self.assertTrue(evaluate_gates(task_dir, "full")["survey_complete"])
            self.assertEqual(collect_gate7_status(task_dir, "full")["next_action"], "complete")
            topic_rows = read_jsonl(task_dir / "state/topic_relevance_audit.jsonl")
            write_jsonl(task_dir / "state/topic_relevance_audit.jsonl", topic_rows[:-1])
            self.assertNotEqual(collect_gate7_status(task_dir, "full")["next_action"], "complete")
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "embodied memory system", target="full")
            self.populate_full_task(task_dir)
            (task_dir / "state/expert_review_reports.jsonl").write_text("", encoding="utf-8")
            (task_dir / "outputs/survey.md").write_text("# Stale final\n", encoding="utf-8")
            (task_dir / "outputs/survey.html").write_text("<html>stale final</html>", encoding="utf-8")
            manifest = promote_release(task_dir, "full")
            self.assertFalse(manifest["released"], manifest)
            self.assertFalse(manifest["survey_complete"])
            self.assertTrue(manifest["stale_final_quarantined"], manifest)
            self.assertFalse((task_dir / "outputs/survey.md").exists())
            self.assertFalse((task_dir / "outputs/survey.html").exists())
            stale_dir = Path(manifest["stale_release_dir"])
            self.assertTrue((stale_dir / "survey.md").exists())
            self.assertTrue((stale_dir / "survey.html").exists())
            stale_manifest = json.loads((stale_dir / "stale_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(stale_manifest["stale_final_quarantined"])
            self.assertEqual(stale_manifest["blocked_by_phase"], "article")
            self.assertIn("final release is not valid", (task_dir / "outputs/final_report.md").read_text(encoding="utf-8"))

    def test_init_runner_and_dashboard_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "runner topic")
            for relative in [
                "state/task_spec.md",
                "state/progress.json",
                "state/heartbeat.json",
                "state/run_state.json",
                "state/tasks.jsonl",
                "state/failure_ledger.jsonl",
                "state/paper_cards",
                "outputs/release_manifest.json",
                "logs/orchestrator.jsonl",
            ]:
                self.assertTrue((task_dir / relative).exists())
            for relative in [
                "state/raw_candidates.jsonl",
                "state/search_routes.jsonl",
                "state/papers.jsonl",
                "state/citation_plan.jsonl",
                "state/topic_relevance_audit.jsonl",
                "state/topic_relevance_second_audits.jsonl",
                "state/paper_mechanism_cards.jsonl",
                "state/full_text_sources.jsonl",
                "state/claim_evidence_spans.jsonl",
                "state/section_evidence_plans.jsonl",
                "state/expert_review_reports.jsonl",
                "state/runtime_dispatch_queue.jsonl",
                "state/runtime_active_intent.json",
                "state/discovery_batches.json",
                "state/topic_relevance_batches.json",
                "state/paper_understanding_batches.json",
                "state/gate7_repair_batches.json",
                "outputs/coverage_matrix.md",
                "outputs/related_survey_matrix.md",
                "outputs/references.bib",
                "outputs/final_report.md",
                "outputs/contribution_tree.yml",
                "outputs/knowledge_tree.yml",
                "state/spine_decision.md",
            ]:
                self.assertFalse((task_dir / relative).exists(), relative)
            self.assertEqual(read_jsonl(task_dir / "state/tasks.jsonl"), [])
            self.assertEqual(read_jsonl(task_dir / "state/failure_ledger.jsonl"), [])
            self.assertFalse((task_dir / "outputs/survey_candidate.md").exists())
            self.assertFalse((task_dir / "outputs/survey_body_draft.md").exists())
            self.assertFalse((task_dir / "outputs/survey_candidate.html").exists())
            self.assertFalse((task_dir / "outputs/article_plan.md").exists())
            self.assertFalse((task_dir / "outputs/appendix.md").exists())
            self.assertFalse((task_dir / "outputs/survey.md").exists())
            self.assertFalse((task_dir / "outputs/survey.html").exists())
            self.assertFalse((task_dir / "outputs" / ("review" + ".md")).exists())
            skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("init_task.py --base-dir", skill_text)
            self.assertNotIn("init_task.py --task-dir <run>", skill_text)
            (task_dir / "outputs/survey_candidate.md").write_text("# Survey\n\n## Intro\ntext\n", encoding="utf-8")
            (task_dir / "outputs/appendix.md").write_text("# Appendix\n", encoding="utf-8")
            (task_dir / "state/argument_graph.yml").write_text("central_thesis: x\n", encoding="utf-8")
            write_jsonl(task_dir / "state/section_evidence_plans.jsonl", [{"section_id": "S1"}])
            self.assertTrue(freeze_review_round(task_dir, "round-test")["review_freeze"]["frozen_artifacts"]["outputs/survey_candidate.md"])
            dispatched = dispatch_packets(task_dir, "round-test")
            self.assertEqual(dispatched["packets"], 5)
            self.assertEqual(dispatched["status"], "blocked_waiting_external_review")
            invocations = [json.loads(line) for line in (task_dir / "state/expert_review_invocations.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertTrue(all(item["status"] == "blocked_waiting_external_review" for item in invocations))
            self.assertTrue(all(item["fresh_context"] is False for item in invocations))
            self.assertEqual(read_text_if_exists(task_dir / "state/expert_review_reports.jsonl"), "")
            prompts = make_reviewer_prompts(task_dir)
            self.assertEqual(len(prompts["reviewer_prompts"]), 5)
            self.assertIn("multi_agent_v1.spawn_agent", prompts["execution_note"])
            report = self.expert_reviews()[0]
            self.assertEqual(record_review_report(task_dir, report, "subagent-domain-expert")["status"], "recorded")
            self.assertFalse(collect_status(task_dir)["all_reports_received"])
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "wait_all_reports")
            reports = self.expert_reviews(weaknesses=[self.weakness()])
            for reviewer_id, _persona in self.personas:
                record_review_report(task_dir, next(item for item in reports if item["reviewer_id"] == reviewer_id), f"subagent-{reviewer_id}")
            adjudicated = adjudicate_reports(task_dir)
            self.assertTrue(adjudicated["all_major_weaknesses_adjudicated"])
            self.assertEqual(adjudicated["canonical_weakness_count"], 1)
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "repair_with_evidence")
            invalid_repair = self.repair_actions("w1", evidence=False)[0]
            self.assertEqual(record_repair_action(task_dir, invalid_repair)["status"], "invalid")
            self.assertEqual(record_repair_action(task_dir, self.repair_actions("w1")[0])["status"], "invalid")
            (task_dir / "outputs/survey_candidate.md").write_text("# Survey\n\n## Intro\ntext\n\nRepair adds evidence-backed comparison.\n", encoding="utf-8")
            repaired = record_repair_action(task_dir, self.repair_actions("w1")[0])
            self.assertEqual(repaired["status"], "recorded")
            repaired_hash = json.loads((task_dir / "state/expert_review_round_status.json").read_text(encoding="utf-8"))["repaired_article_hash"]
            self.assertTrue(repaired_hash)
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "run_regression_checks")
            self.assertEqual(record_regression_check(task_dir, {"weakness_id": "w1", "status": "failed", "command": "python3 -m unittest tests/test_scripts.py", "result": "FAIL"})["status"], "recorded")
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "run_regression_checks")
            self.assertEqual(record_regression_check(task_dir, self.regression_checks("w1")[0])["status"], "recorded")
            rereview_prompts = make_targeted_rereview_prompts(task_dir)
            self.assertEqual(rereview_prompts["next_action"], "spawn_targeted_rereviewers")
            self.assertEqual(len(rereview_prompts["targeted_rereview_prompts"]), 1)
            self.assertIn("Return exactly one JSON object", rereview_prompts["targeted_rereview_prompts"][0]["message"])
            rereview = self.targeted_rereviews("w1", article_hash=repaired_hash)[0]
            self.assertEqual(record_targeted_rereview(task_dir, rereview, "subagent-rereview-w1")["status"], "recorded")
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "rerun_gate_check")
            (task_dir / "outputs/release_manifest.json").write_text(json.dumps({"released": False}), encoding="utf-8")
            (task_dir / "state/gate_check_full.json").write_text(json.dumps({"release_allowed": True, "all_blocking_gates_passed": True}), encoding="utf-8")
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "rerun_gate_check")
            (task_dir / "state/gate_check_full.json").write_text(json.dumps({"release_allowed": True, "all_blocking_gates_passed": True, "candidate_hash": "stale", "generated_at": "2026-07-03T00:00:00Z"}), encoding="utf-8")
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "rerun_gate_check")
            (task_dir / "state/gate_check_full.json").write_text(json.dumps({"release_allowed": True, "all_blocking_gates_passed": True, "candidate_hash": repaired_hash, "generated_at": "2026-07-03T00:00:00Z"}), encoding="utf-8")
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "promote_release")
            (task_dir / "outputs/release_manifest.json").write_text(json.dumps({"released": True}), encoding="utf-8")
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "promote_release")
            (task_dir / "outputs/survey.md").write_text((task_dir / "outputs/survey_candidate.md").read_text(encoding="utf-8"), encoding="utf-8")
            (task_dir / "outputs/survey.html").write_text("<html>released survey</html>", encoding="utf-8")
            (task_dir / "outputs/release_manifest.json").write_text(json.dumps({
                "released": True,
                "released_at": "2026-07-03T00:01:00Z",
                "candidate_hash": "stale",
                "survey_hash": sha256_file(task_dir / "outputs/survey.md"),
                "survey_html_hash": sha256_file(task_dir / "outputs/survey.html"),
                "gate_check_hash": "gate-hash",
            }), encoding="utf-8")
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "promote_release")
            (task_dir / "outputs/release_manifest.json").write_text(json.dumps({
                "released": True,
                "released_at": "2026-07-03T00:01:00Z",
                "candidate_hash": repaired_hash,
                "survey_hash": "stale",
                "survey_html_hash": sha256_file(task_dir / "outputs/survey.html"),
                "gate_check_hash": "gate-hash",
            }), encoding="utf-8")
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "promote_release")
            (task_dir / "outputs/release_manifest.json").write_text(json.dumps({
                "released": True,
                "released_at": "2026-07-03T00:01:00Z",
                "candidate_hash": repaired_hash,
                "survey_hash": sha256_file(task_dir / "outputs/survey.md"),
                "survey_html_hash": sha256_file(task_dir / "outputs/survey.html"),
                "gate_check_hash": "gate-hash",
            }), encoding="utf-8")
            self.assertEqual(collect_gate7_status(task_dir)["next_action"], "promote_release")
            current_gate_hash = stable_gate_hash(evaluate_gates(task_dir, "full"))
            (task_dir / "outputs/release_manifest.json").write_text(json.dumps({
                "released": True,
                "released_at": "2026-07-03T00:01:00Z",
                "candidate_hash": repaired_hash,
                "survey_hash": sha256_file(task_dir / "outputs/survey.md"),
                "survey_html_hash": sha256_file(task_dir / "outputs/survey.html"),
                "gate_check_hash": current_gate_hash,
            }), encoding="utf-8")
            self.assertNotEqual(collect_gate7_status(task_dir)["next_action"], "complete")
            self.assertEqual(dispatch_expansion_audit_packet(task_dir, "audit-test")["status"], "dispatched")
            self.assertFalse(collect_expansion_audit_status(task_dir)["returned"])
            write_jsonl(task_dir / "state/expansion_audit.jsonl", self.expansion_audit())
            self.assertTrue(collect_expansion_audit_status(task_dir)["returned"])
            html = render_dashboard(task_dir, "short").read_text(encoding="utf-8")
            self.assertIn("gate_7_expert_review", html)
            self.assertIn("A/B full-text deep-read", html)

    def test_render_survey_html_outputs_article_and_reference_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "html topic")
            (task_dir / "outputs/survey_candidate.md").write_text("# Sample Survey\n\n## Finding\nThe article text cites a verified paper [@p001].\n", encoding="utf-8")
            write_jsonl(
                task_dir / "state/papers.jsonl",
                [
                    {
                        "paper_id": "p001",
                        "title": "Verified HTML Paper",
                        "authors": ["A. Author"],
                        "year": 2026,
                        "venue": "TestConf",
                        "doi": "10.1234/html-paper",
                    }
                ],
            )
            html_path = render_survey_html(task_dir)
            page = html_path.read_text(encoding="utf-8")
            self.assertIn("Sample Survey", page)
            self.assertIn("The article text cites a verified paper", page)
            self.assertIn("Verified HTML Paper", page)
            self.assertIn("https://doi.org/10.1234/html-paper", page)
            self.assertIn('href="#ref-p001"', page)
            self.assertIn('id="ref-p001"', page)

    def test_v2_slim_core_facades_derive_authoritative_state(self):
        from scripts.failure_ledger import append_failures_from_adjudication, collect_failure_ledger
        from scripts.gate_engine import evaluate_all, evaluate_phase, explain_blocker, route_repair
        from scripts.knowledge_tree_store import mirror_knowledge_tree, validate_knowledge_tree_store
        from scripts.paper_card_store import mirror_paper_cards, validate_paper_card_store
        from scripts.run_state import sync_run_state
        from scripts.task_queue import sync_tasks

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "slim core topic", target="full")
            self.populate_full_task(task_dir)

            gates = evaluate_all(task_dir, "full")
            self.assertEqual(gates["component"], "gate_engine")
            self.assertTrue(gates["all_blocking_gates_passed"])
            phase = evaluate_phase(task_dir, "full", "paper_understanding")
            self.assertEqual(phase["component"], "gate_engine")
            self.assertEqual(phase["phase"], "paper_understanding")
            self.assertTrue(phase["passed"])

            run_state = sync_run_state(task_dir, "full")
            self.assertEqual(run_state["component"], "run_state")
            self.assertEqual(run_state["target"], "full")
            self.assertEqual(run_state["research_assets"]["paper_cards"]["canonical"], "state/paper_cards")
            self.assertEqual(run_state["research_assets"]["failure_ledger"]["status"], "empty")
            self.assertEqual(run_state["workflow"]["public_entrypoint"], "runner.py")

            mirrored = mirror_paper_cards(task_dir)
            self.assertEqual(mirrored["status"], "mirrored")
            card_path = task_dir / "state/paper_cards/p001.json"
            self.assertTrue(card_path.exists())
            card = json.loads(card_path.read_text(encoding="utf-8"))
            self.assertIn("survey_use", card)
            self.assertTrue(card["survey_use"]["changes_knowledge_tree"])
            card_status = validate_paper_card_store(task_dir)
            self.assertTrue(card_status["valid"], card_status)

            tree = mirror_knowledge_tree(task_dir)
            self.assertEqual(tree["status"], "mirrored", tree)
            self.assertTrue((task_dir / "outputs/knowledge_tree.yml").exists())
            self.assertTrue((task_dir / "state/paper_clusters.jsonl").exists())
            self.assertTrue((task_dir / "state/taxonomy_candidates.yml").exists())
            self.assertTrue((task_dir / "state/spine_decision.md").exists())
            tree_status = validate_knowledge_tree_store(task_dir)
            self.assertTrue(tree_status["valid"], tree_status)
            self.assertIn("p001", tree_status["paper_ids_with_cards"])
            synced_after_tree = sync_run_state(task_dir, "full")
            self.assertEqual(synced_after_tree["research_assets"]["knowledge_tree"]["status"], "ready")
            self.assertEqual(synced_after_tree["research_assets"]["spine_decision"]["status"], "ready")

            (task_dir / "state/expert_review_adjudication.json").write_text(json.dumps(self.adjudication("CW001")), encoding="utf-8")
            ledger = append_failures_from_adjudication(task_dir)
            self.assertEqual(ledger["status"], "recorded")
            failures = collect_failure_ledger(task_dir)
            self.assertEqual(failures["unresolved_count"], 1)
            self.assertEqual(failures["failures"][0]["root_cause"], "taxonomy_not_field_native")

            tasks = sync_tasks(task_dir)
            self.assertEqual(tasks["component"], "task_queue")
            self.assertTrue((task_dir / "state/tasks.jsonl").exists())
            task_rows = read_jsonl(task_dir / "state/tasks.jsonl")
            self.assertIsInstance(task_rows, list)

            blocked_task = initialize_task(Path(tmp), "blocked topic explanation", target="full")
            explanation = explain_blocker(blocked_task, "full")
            self.assertEqual(explanation["component"], "gate_engine")
            self.assertEqual(explanation["status"], "blocked")
            self.assertEqual(explanation["blocked_by_phase"], "topic_profile")
            self.assertEqual(explanation["allowed_next_phase"], "topic_profile")
            self.assertEqual(explanation["validator"], "validate_topic_profile")
            self.assertIn("missing_topic", explanation["errors"])
            self.assertIn("runner.py --task-dir", explanation["recommended_commands"][0])
            self.assertIn("task_queue.py --task-dir", explanation["recommended_commands"][1])
            route = route_repair(blocked_task, "full")
            self.assertEqual(route["component"], "gate_engine")
            self.assertEqual(route["status"], "blocked_worker_required")
            self.assertEqual(route["repair_route"]["blocked_by_phase"], "topic_profile")
            self.assertEqual(route["repair_route"]["next_public_action"], "spawn_topic_profile_agents")
            self.assertEqual(route["repair_route"]["queue_request_type"], "topic_profile")
            self.assertIn("state/topic_profile.json", route["repair_route"]["required_artifacts"])
            self.assertIn("task_queue.py --task-dir", route["recommended_commands"][1])

    def test_task_queue_facade_records_worker_output(self):
        from scripts.runner import run_until_complete as run_public_runner
        from scripts.task_queue import collect_pending, mark_spawned, record_agent_output

        with tempfile.TemporaryDirectory() as tmp:
            task_dir = initialize_task(Path(tmp), "task queue facade topic", target="full")
            status = run_public_runner(task_dir, target="full", max_steps=5)
            self.assertEqual(status["status"], "blocked_topic_profile_agent_spawn_required", status)

            pending = collect_pending(task_dir)
            self.assertEqual(pending["component"], "task_queue")
            self.assertNotIn("pending_requests", pending)
            self.assertEqual([task["request_type"] for task in pending["tasks"]], ["topic_profile"])
            task = pending["tasks"][0]
            self.assertEqual(task["status"], "pending")
            self.assertIn("packet", task)
            self.assertNotIn("payload", task)
            self.assertNotIn("message", task)
            self.assertNotIn("record_command", task)
            packet_path = task_dir / task["packet"]
            self.assertTrue(packet_path.exists())
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            self.assertEqual(packet["task_id"], task["task_id"])
            self.assertEqual(packet["request_type"], "topic_profile")
            self.assertIn("Topic Boundary Agent", packet["message"])
            self.assertIn("topic_profile.py", packet["record_command"])
            task_rows = read_jsonl(task_dir / "state/tasks.jsonl")
            self.assertEqual(task_rows[0]["packet"], task["packet"])
            self.assertNotIn("payload", task_rows[0])

            spawned = mark_spawned(task_dir, task["task_id"], "topic-profile-agent-001")
            self.assertEqual(spawned["component"], "task_queue")
            self.assertEqual(spawned["status"], "spawned", spawned)

            output_file = Path(tmp) / "topic-profile-output.json"
            profile = self.topic_profile("task queue facade topic")
            profile["validator_results"] = [{"validator": "validate_topic_profile", "status": "passed"}]
            profile["remaining_blockers"] = []
            output_file.write_text(json.dumps(profile, sort_keys=True), encoding="utf-8")
            recorded = record_agent_output(task_dir, task["task_id"], output_file)
            self.assertEqual(recorded["component"], "task_queue")
            self.assertEqual(recorded["status"], "result_recorded", recorded)
            self.assertTrue((task_dir / "state/topic_profile.json").exists())
            tasks = read_jsonl(task_dir / "state/tasks.jsonl")
            self.assertEqual(tasks[0]["status"], "result_recorded")

    def test_clean_main_flow_has_no_legacy_schema_terms(self):
        self.assertFalse((ROOT / "references" / ("review" + "_contract.md")).exists())
        main_text = "\n".join(path.read_text(encoding="utf-8") for path in [ROOT / "SKILL.md", ROOT / "scripts/gate_check.py", ROOT / "scripts/init_task.py", ROOT / "scripts/run_expert_reviews.py"])
        for old in ["section_" + "cards", "worked_" + "examples", "review_" + "scorecard", "review_" + "depth"]:
            self.assertNotIn(old, main_text)
        self.assertIn("paper_cards", main_text)
        self.assertIn("knowledge tree", main_text.lower())
        for unused in ["review" + "_contract", "weakness" + "_routes", "review" + "_rounds", "phase" + "_summaries", "figures" + "_plan", "dispatch-" + "subagents", "dispatch_" + "subagents"]:
            self.assertNotIn(unused, main_text)
        self.assertNotIn("outputs/" + "review" + ".md", main_text)
        self.assertNotIn("review" + "_body_draft.md", main_text)


if __name__ == "__main__":
    unittest.main()
