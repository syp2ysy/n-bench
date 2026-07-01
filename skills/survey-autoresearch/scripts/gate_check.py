#!/usr/bin/env python3
"""Evaluate completion gates for a survey-autoresearch run."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from .coverage_report import build_coverage
    from .validate_claims import validate_claim_records
    from .validate_csur_style_patterns import validate_csur_style_patterns
    from .validate_node_cards import validate_node_cards
    from .validate_paper_cards import validate_paper_cards
    from .validate_section_cards import validate_section_cards
except ImportError:  # pragma: no cover - used when run as a standalone script
    from coverage_report import build_coverage
    from validate_claims import validate_claim_records
    from validate_csur_style_patterns import validate_csur_style_patterns
    from validate_node_cards import validate_node_cards
    from validate_paper_cards import validate_paper_cards
    from validate_section_cards import validate_section_cards


TARGETS = {
    "short": {"min_refs": 80},
    "full": {"min_refs": 150},
    "csur": {"min_refs": 150},
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def nonempty(path: Path) -> bool:
    return path.exists() and path.read_text(encoding="utf-8").strip() != ""


def text_or_empty(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def review_reader_artifacts(review_text: str, target: str) -> dict:
    """Check deterministic reader artifacts expected of full tutorial surveys."""
    if target not in {"full", "csur"}:
        return {"required": False, "missing": []}

    text = review_text.lower()
    artifact_terms = {
        "benchmark landscape": [
            "benchmark landscape",
            "benchmarks",
            "benchmark",
            "基准",
            "数据集",
        ],
        "method taxonomy": [
            "method taxonomy",
            "method families",
            "方法分类",
            "方法谱系",
            "方法族",
        ],
        "method design pipeline": [
            "design pipeline",
            "method design pipeline",
            "设计流程",
            "设计管线",
            "如何设计",
        ],
        "evaluation protocol": [
            "evaluation protocol",
            "evaluation and metrics",
            "metrics",
            "评测协议",
            "评测设计",
            "评估协议",
            "指标",
        ],
        "practical design guidelines": [
            "practical design guidelines",
            "design guidelines",
            "设计指南",
            "实践指南",
            "实践建议",
            "方法选择指南",
        ],
    }
    missing = [
        artifact
        for artifact, terms in artifact_terms.items()
        if not any(term in text for term in terms)
    ]
    if text.count("| ---") < 3:
        missing.append("synthesis tables")
    return {"required": True, "missing": missing}


def review_criticality_artifacts(review_text: str, target: str) -> dict:
    """Require explicit critical analysis, not only taxonomy and positive synthesis."""
    if target not in {"full", "csur"}:
        return {"required": False, "present": [], "missing": []}

    text = review_text.lower()
    categories = {
        "benchmark limitations": [
            "benchmark limitation",
            "dataset limitation",
            "limitation",
            "limitations",
            "局限",
            "限制",
        ],
        "failure modes": [
            "failure mode",
            "failure modes",
            "failure",
            "fails when",
            "失效",
            "失败",
        ],
        "disagreement": [
            "disagreement",
            "disagree",
            "conflict",
            "contradiction",
            "controversy",
            "trade-off",
            "tradeoff",
            "分歧",
            "争议",
            "冲突",
            "权衡",
        ],
        "negative evidence": [
            "negative result",
            "negative evidence",
            "counterexample",
            "counter-example",
            "反例",
            "负面",
            "失败案例",
        ],
    }
    present = [
        category
        for category, terms in categories.items()
        if any(term in text for term in terms)
    ]
    missing = [] if len(present) >= 2 else ["critical analysis"]
    return {"required": True, "present": present, "missing": missing}


PROCESS_LEAKAGE_PATTERNS = [
    re.compile(r"不是[^。\n]{0,60}(综述|survey|review|任务列表|论文列表|主线|组织轴|附属)", re.IGNORECASE),
    re.compile(r"[^。\n]{0,30}不是[^。\n]{0,40}(主线|综述主线|组织轴)", re.IGNORECASE),
    re.compile(r"按任务堆"),
    re.compile(r"(过程性|内部纠偏|内部纠正|审计后纠偏|用户审计后|范围修正|范围纠偏)", re.IGNORECASE),
    re.compile(r"\bnot\s+(?:a|an|the)?\s*[^.\n]{0,60}\b(survey|review)\b", re.IGNORECASE),
    re.compile(r"\bnot\b[^.\n]{0,60}\b(task list|paper list|task-centered)\b", re.IGNORECASE),
    re.compile(r"\b(tasks?)\b[^.\n]{0,60}\bnot\b[^.\n]{0,40}\b(spine|main line|organizing axis)\b", re.IGNORECASE),
    re.compile(r"\b(internal|process|scope)\s+correction\b", re.IGNORECASE),
]


def review_process_leakage(review_text: str, target: str) -> dict:
    """Detect audit/process-correction language that should not appear in a survey body."""
    if target not in {"full", "csur"}:
        return {"required": False, "matches": []}

    matches = []
    for pattern in PROCESS_LEAKAGE_PATTERNS:
        for match in pattern.finditer(review_text):
            start = max(0, match.start() - 24)
            end = min(len(review_text), match.end() + 24)
            snippet = " ".join(review_text[start:end].split())
            matches.append(snippet)
            break
    return {"required": True, "matches": matches}


SCAFFOLD_LEAKAGE_PATTERNS = [
    re.compile(r"[^。\n]{0,60}暴露[^。\n；;]{1,90}[；;][^。\n]{0,90}暴露"),
    re.compile(r"(好的|优秀的|合格的)(方法|综述|基准|benchmark|survey|review)", re.IGNORECASE),
    re.compile(r"(放回|映射回|归入|放入)[^。\n]{0,60}(框架|framework|contract|taxonomy)", re.IGNORECASE),
    re.compile(r"\b(?:map|mapped|mapping|put|placed)\s+back\s+(?:to|into)\b[^.\n]{0,60}\b(framework|contract|taxonomy)\b", re.IGNORECASE),
    re.compile(r"(工作稿\s*v?\d+|draft\s+v\d+|csur[- ]style\s+redo|\bredo\b)", re.IGNORECASE),
    re.compile(r"\b(papers|citation_plan|claims|paper_facts)\.jsonl\b", re.IGNORECASE),
    re.compile(r"(如果用于正式投稿|正式投稿还需要|for formal submission|formal submission[^.\n]{0,80}need)", re.IGNORECASE),
    re.compile(r"(压力面|内部脚手架|内部分析框架|scaffold sentence|scaffold leakage)", re.IGNORECASE),
]


def review_scaffold_leakage(review_text: str, target: str) -> dict:
    """Detect internal scaffold notes that should be translated into article prose."""
    if target not in {"full", "csur"}:
        return {"required": False, "matches": []}

    matches = []
    for pattern in SCAFFOLD_LEAKAGE_PATTERNS:
        for match in pattern.finditer(review_text):
            start = max(0, match.start() - 32)
            end = min(len(review_text), match.end() + 32)
            snippet = " ".join(review_text[start:end].split())
            matches.append(snippet)
            break
    return {"required": True, "matches": matches}


def citation_verification_cadence(task_dir: Path, papers: list[dict], target: str) -> dict:
    """Check AutoResearch-style periodic verification records for long runs."""
    state_dir = task_dir / "state"
    managed_run = (state_dir / "task_spec.md").exists() or (state_dir / "progress.json").exists()
    if target not in {"full", "csur"} or len(papers) < 20 or not managed_run:
        return {"required": False, "passed": True}

    verification_path = task_dir / "logs" / "verification.jsonl"
    verification_records = read_jsonl(verification_path)
    paper_ids = {item.get("paper_id") for item in papers if item.get("paper_id")}
    checked_ids = {
        item.get("paper_id")
        for item in verification_records
        if item.get("paper_id") in paper_ids
        and ("verified" in item or item.get("checks") or item.get("source"))
    }
    required_batches = (len(paper_ids) + 19) // 20
    batch_records = [
        item
        for item in verification_records
        if item.get("event") in {"citation_batch_verified", "verification_batch", "citation_verification_batch"}
    ]
    passed = len(checked_ids) >= required_batches or len(batch_records) >= required_batches
    return {
        "required": True,
        "passed": passed,
        "checked_papers": len(checked_ids),
        "papers": len(paper_ids),
        "batch_records": len(batch_records),
        "required_batches": required_batches,
    }


def related_survey_differentiation(related_text: str) -> bool:
    rows = [
        line
        for line in related_text.splitlines()
        if line.strip().startswith("|") and "---" not in line
    ]
    if len(rows) < 2:
        return False
    body_rows = rows[1:]
    strong_terms = [
        "ablation",
        "agenda",
        "angle",
        "benchmark",
        "causal",
        "design",
        "evidence",
        "evaluation",
        "failure",
        "framework",
        "matrix",
        "mechanism",
        "method",
        "meta-analysis",
        "protocol",
        "taxonomy",
        "分类",
        "框架",
        "证据",
        "基准",
        "方法",
        "机制",
        "评测",
        "协议",
    ]
    generic_only = ["more recent", "newer", "latest", "broader", "larger", "more comprehensive", "更新", "更宽", "更全面"]
    strong_rows = 0
    for row in body_rows:
        lower = row.lower()
        if any(term in lower for term in strong_terms) and not all(term in lower for term in generic_only):
            strong_rows += 1
    return strong_rows >= max(1, len(body_rows) // 2)


CSUR_ACCEPTED_EXEMPLARS = {
    "10.1145/3711118": 2025,
    "10.1145/3704262": 2025,
    "10.1145/3665926": 2025,
    "10.1145/3713070": 2025,
    "10.1145/3716628": 2025,
    "10.1145/3744238": 2026,
    "10.1145/3769292": 2026,
    "10.1145/3787585": 2026,
    "10.1145/3789261": 2026,
    "10.1145/3789253": 2026,
}


UNACCEPTED_SURVEY_STATUS_TERMS = ["under review", "submitted", "arxiv only"]


def csur_imitation_plan_status(plan_text: str) -> dict:
    """Validate that CSUR style imitation is based on recent official ACM DL records."""
    lower = plan_text.lower()
    required_terms = {
        "selected exemplars": ["selected csur exemplars", "selected exemplars", "选用"],
        "section skeleton": ["section skeleton", "section structure", "章节结构"],
        "abstract moves": ["abstract move", "摘要"],
        "reader function": ["reader function", "读者"],
        "internal exclusions": ["internal notes", "excluded", "禁止", "不得"],
    }
    missing_sections = [
        name
        for name, terms in required_terms.items()
        if not any(term in lower or term in plan_text for term in terms)
    ]
    banned_terms = [
        term
        for term in [*UNACCEPTED_SURVEY_STATUS_TERMS, "accepted claim without acm", "non-csur"]
        if term in lower
    ]
    dois = sorted(set(re.findall(r"10\.1145/\d+", plan_text)))
    official_dois = [doi for doi in dois if doi in CSUR_ACCEPTED_EXEMPLARS]
    rejected_dois = [doi for doi in dois if doi not in CSUR_ACCEPTED_EXEMPLARS]
    has_recent_official = len(official_dois) >= 2
    has_acm_context = "acm computing surveys" in lower and "dl.acm.org/doi/" in lower
    passed = (
        not missing_sections
        and not banned_terms
        and not rejected_dois
        and has_recent_official
        and has_acm_context
    )
    return {
        "passed": passed,
        "missing_sections": missing_sections,
        "official_dois": official_dois,
        "rejected_dois": rejected_dois,
        "banned_terms": banned_terms,
    }


MULTI_AGENT_CLAIM_PATTERNS = [
    re.compile(r"\bmulti[-\s]?agent\b", re.IGNORECASE),
    re.compile(r"\bsub[-\s]?agents?\b", re.IGNORECASE),
    re.compile(r"\bagent\s+discussion\b", re.IGNORECASE),
    re.compile(r"多\s*agent", re.IGNORECASE),
    re.compile(r"多\s*智能体"),
    re.compile(r"多\s*代理"),
]


def multi_agent_claim_status(task_dir: Path) -> dict:
    """Reject final claims of multi-agent production unless run state proves it."""
    final_text = text_or_empty(task_dir / "outputs" / "final_report.md")
    review_text = text_or_empty(task_dir / "outputs" / "review.md")
    combined_text = f"{final_text}\n{review_text}"
    claims_multi_agent = any(pattern.search(combined_text) for pattern in MULTI_AGENT_CLAIM_PATTERNS)
    agent_rounds = read_jsonl(task_dir / "state" / "agent_rounds.jsonl")
    merge_decisions = read_jsonl(task_dir / "state" / "merge_decisions.jsonl")
    substantiated = bool(agent_rounds) and bool(merge_decisions)
    passed = not claims_multi_agent or substantiated
    return {
        "required": claims_multi_agent,
        "passed": passed,
        "claims_multi_agent": claims_multi_agent,
        "agent_rounds": len(agent_rounds),
        "merge_decisions": len(merge_decisions),
    }


def conceptual_framework_status(text: str) -> dict:
    lower = text.lower()
    required_terms = [
        "central thesis",
        "system diagram",
        "node",
        "taxonomy",
        "running example",
        "prior-survey",
    ]
    missing = [term for term in required_terms if term not in lower]
    return {"passed": bool(text.strip()) and not missing, "missing_terms": missing}


def deep_synthesis_readiness(task_dir: Path, target: str) -> dict:
    """Check required deep-synthesis artifacts for full and CSUR runs."""
    if target not in {"full", "csur"}:
        return {"required": False, "passed": True}

    state_dir = task_dir / "state"
    outputs_dir = task_dir / "outputs"
    required_files = [
        state_dir / "paper_cards.jsonl",
        state_dir / "system_node_cards.jsonl",
        state_dir / "section_cards.jsonl",
        state_dir / "research_questions_by_perspective.md",
        outputs_dir / "conceptual_framework.md",
    ]
    if target == "csur":
        required_files.append(state_dir / "csur_style_patterns.yml")

    missing_artifacts = [
        str(path.relative_to(task_dir))
        for path in required_files
        if not nonempty(path)
    ]

    paper_cards = read_jsonl(state_dir / "paper_cards.jsonl")
    node_cards = read_jsonl(state_dir / "system_node_cards.jsonl")
    section_cards = read_jsonl(state_dir / "section_cards.jsonl")
    paper_status = validate_paper_cards(paper_cards) if paper_cards else {
        "valid": False,
        "errors": ["missing paper_cards"],
        "total_cards": 0,
    }
    node_status = validate_node_cards(node_cards) if node_cards else {
        "valid": False,
        "errors": ["missing system_node_cards"],
        "total_cards": 0,
    }
    section_status = validate_section_cards(section_cards) if section_cards else {
        "valid": False,
        "errors": ["missing section_cards"],
        "total_cards": 0,
    }
    framework_status = conceptual_framework_status(
        text_or_empty(outputs_dir / "conceptual_framework.md")
    )
    perspective_text = text_or_empty(state_dir / "research_questions_by_perspective.md")
    perspective_status = {
        "passed": bool(perspective_text.strip()) and len(
            [line for line in perspective_text.splitlines() if line.strip().startswith(("-", "*", "RQ"))]
        ) >= 2
    }
    csur_style_status = {"valid": True}
    if target == "csur":
        csur_style_text = text_or_empty(state_dir / "csur_style_patterns.yml")
        csur_style_status = validate_csur_style_patterns(csur_style_text) if csur_style_text else {
            "valid": False,
            "missing": ["csur_style_patterns"],
        }

    checks = {
        "paper-card depth": bool(paper_status["valid"]),
        "node depth": bool(node_status["valid"]),
        "section argument": bool(section_status["valid"]),
        "newcomer comprehension": bool(framework_status["passed"]) and perspective_status["passed"],
    }
    if target == "csur":
        checks["CSUR rhetoric"] = bool(csur_style_status["valid"])
    failed_checks = [name for name, passed in checks.items() if not passed]
    return {
        "required": True,
        "passed": not missing_artifacts and not failed_checks,
        "missing_artifacts": missing_artifacts,
        "failed_checks": failed_checks,
        "checks": checks,
        "paper_cards": paper_status,
        "system_node_cards": node_status,
        "section_cards": section_status,
        "conceptual_framework": framework_status,
        "perspective_questions": perspective_status,
        "csur_style_patterns": csur_style_status,
    }


def csur_readiness(task_dir: Path, citation_plan: list[dict]) -> dict:
    """Check deterministic artifacts needed before claiming CSUR readiness."""
    state_dir = task_dir / "state"
    outputs_dir = task_dir / "outputs"
    required_files = [
        state_dir / "research_questions.md",
        state_dir / "search_protocol.md",
        state_dir / "related_surveys.md",
        state_dir / "paper_facts.jsonl",
        state_dir / "paper_cards.jsonl",
        state_dir / "csur_imitation_plan.md",
        state_dir / "csur_style_patterns.yml",
        outputs_dir / "synthesis_tables.md",
        outputs_dir / "figures_plan.md",
        outputs_dir / "conceptual_framework.md",
    ]
    missing_artifacts = [
        str(path.relative_to(task_dir))
        for path in required_files
        if not nonempty(path)
    ]

    checks: dict[str, object] = {}

    rq_text = (state_dir / "research_questions.md").read_text(encoding="utf-8") if (state_dir / "research_questions.md").exists() else ""
    checks["research_questions"] = rq_text.lower().count("rq") >= 3

    protocol_text = (state_dir / "search_protocol.md").read_text(encoding="utf-8") if (state_dir / "search_protocol.md").exists() else ""
    protocol_lower = protocol_text.lower()
    checks["search_protocol"] = all(
        term in protocol_lower
        for term in ["database", "inclusion", "exclusion", "screening"]
    ) or all(
        term in protocol_text
        for term in ["数据库", "纳入", "排除", "筛选"]
    )
    route_terms = {
        "database": ["database", "数据库"],
        "venue": ["venue", "proceedings", "conference", "journal", "会议", "期刊"],
        "citation_snowball": ["citation", "snowball", "backward", "forward", "引用", "引文"],
        "related_survey": ["related survey", "prior survey", "相关综述", "已有综述"],
        "query": ["query", "keyword", "search string", "关键词", "检索式"],
    }
    route_hits = [
        name
        for name, terms in route_terms.items()
        if any(term in protocol_lower or term in protocol_text for term in terms)
    ]
    checks["discovery_routes"] = len(route_hits) >= 3

    related_text = (state_dir / "related_surveys.md").read_text(encoding="utf-8") if (state_dir / "related_surveys.md").exists() else ""
    related_rows = [line for line in related_text.splitlines() if line.strip().startswith("|") and "---" not in line]
    checks["related_surveys"] = len(related_rows) >= 9
    checks["related_survey_differentiation"] = related_survey_differentiation(related_text)
    related_lower = related_text.lower()
    checks["related_survey_status"] = not any(
        term in related_lower for term in UNACCEPTED_SURVEY_STATUS_TERMS
    )

    facts = read_jsonl(state_dir / "paper_facts.jsonl")
    ab_ids = {
        item.get("paper_id")
        for item in citation_plan
        if item.get("depth") in {"A", "B"} and item.get("paper_id")
    }
    fact_ids = {item.get("paper_id") for item in facts if item.get("paper_id")}
    checks["paper_fact_coverage"] = bool(ab_ids) and len(ab_ids - fact_ids) == 0
    required_fact_fields = {
        "paper_id",
        "method_family",
        "task_family",
        "benchmark_or_dataset",
        "metrics",
        "mechanism_or_contribution",
        "ablations",
        "limitations",
    }
    checks["paper_fact_schema"] = bool(facts) and all(
        required_fact_fields.issubset(item.keys())
        and item.get("metrics")
        and item.get("mechanism_or_contribution")
        for item in facts
    )

    synthesis_text = (outputs_dir / "synthesis_tables.md").read_text(encoding="utf-8") if (outputs_dir / "synthesis_tables.md").exists() else ""
    synthesis_lower = synthesis_text.lower()
    checks["synthesis_tables"] = (
        synthesis_text.count("| ---") >= 2
        and ("metric" in synthesis_lower or "指标" in synthesis_text)
        and ("ablation" in synthesis_lower or "消融" in synthesis_text)
        and ("method" in synthesis_lower or "方法" in synthesis_text)
    )

    figures_text = (outputs_dir / "figures_plan.md").read_text(encoding="utf-8") if (outputs_dir / "figures_plan.md").exists() else ""
    figure_lines = [
        line
        for line in figures_text.splitlines()
        if line.strip().startswith(("-", "*")) or line.strip()[:2] in {"1.", "2.", "3."}
    ]
    checks["figures_plan"] = len(figure_lines) >= 3

    imitation_text = text_or_empty(state_dir / "csur_imitation_plan.md")
    imitation_status = csur_imitation_plan_status(imitation_text) if imitation_text else {
        "passed": False,
        "missing_sections": ["csur_imitation_plan"],
        "official_dois": [],
        "rejected_dois": [],
        "banned_terms": [],
    }
    checks["csur_imitation_plan"] = imitation_status["passed"]

    failed_checks = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not missing_artifacts and not failed_checks,
        "missing_artifacts": missing_artifacts,
        "failed_checks": failed_checks,
        "checks": checks,
        "csur_imitation_plan": imitation_status,
        "a_b_papers": len(ab_ids),
        "paper_facts": len(facts),
    }


def evaluate_gates(task_dir: Path, target: str = "short") -> dict:
    state_dir = task_dir / "state"
    outputs_dir = task_dir / "outputs"
    papers = read_jsonl(state_dir / "papers.jsonl")
    citation_plan = read_jsonl(state_dir / "citation_plan.jsonl")
    claims = read_jsonl(state_dir / "claims.jsonl")
    known_ids = {item["paper_id"] for item in papers if item.get("paper_id")}
    target_config = TARGETS.get(target, TARGETS["short"])

    verified_count = sum(1 for item in papers if item.get("verified"))
    accepted_count = sum(1 for item in papers if item.get("accepted"))
    verification_rate = verified_count / len(papers) if papers else 0.0
    accepted_rate = accepted_count / len(papers) if papers else 0.0
    coverage = build_coverage(citation_plan)
    all_cells_covered = coverage["summary"]["failing_cells"] == 0 and coverage["summary"]["total_cells"] > 0

    gate_1_passed = (
        len(papers) >= target_config["min_refs"]
        and verification_rate >= 0.80
        and accepted_rate >= 0.30
        and all_cells_covered
        and coverage["summary"].get("assigned_ab_coverage_passed", True)
    )
    citation_cadence = citation_verification_cadence(task_dir, papers, target)
    gate_1_passed = gate_1_passed and citation_cadence["passed"]

    taxonomy_text = (state_dir / "taxonomy.md").read_text(encoding="utf-8") if (state_dir / "taxonomy.md").exists() else ""
    gate_2_passed = (
        "axis" in taxonomy_text.lower()
        and "gap analysis" in taxonomy_text.lower()
        and len(taxonomy_text.strip()) > 40
    )

    paper_cards = read_jsonl(state_dir / "paper_cards.jsonl")
    claim_validation = validate_claim_records(
        claims,
        known_ids,
        paper_cards=paper_cards if target in {"full", "csur"} and paper_cards else None,
    )
    gate_3_passed = bool(claims) and claim_validation["valid"]

    review_path = outputs_dir / "review.md"
    review_text = review_path.read_text(encoding="utf-8") if review_path.exists() else ""
    artifact_status = review_reader_artifacts(review_text, target)
    criticality_status = review_criticality_artifacts(review_text, target)
    process_leakage_status = review_process_leakage(review_text, target)
    scaffold_leakage_status = review_scaffold_leakage(review_text, target)
    multi_agent_status = multi_agent_claim_status(task_dir)
    missing_review_artifacts = list(artifact_status["missing"])
    missing_review_artifacts.extend(criticality_status["missing"])
    if process_leakage_status["matches"]:
        missing_review_artifacts.append("process-leakage framing")
    if scaffold_leakage_status["matches"]:
        missing_review_artifacts.append("scaffold-leakage framing")
    if not multi_agent_status["passed"]:
        missing_review_artifacts.append("unsubstantiated multi-agent claim")
    gate_4_files_present = all(
        nonempty(path)
        for path in [
            review_path,
            outputs_dir / "evidence_table.csv",
            outputs_dir / "references.bib",
        ]
    )
    gate_4_passed = gate_4_files_present and not missing_review_artifacts

    gates = {
        "gate_1_literature": {
            "passed": gate_1_passed,
            "papers": len(papers),
            "min_refs": target_config["min_refs"],
            "verification_rate": round(verification_rate, 3),
            "accepted_rate": round(accepted_rate, 3),
            "coverage": coverage["summary"],
            "citation_verification_cadence": citation_cadence,
        },
        "gate_2_taxonomy": {"passed": gate_2_passed},
        "gate_3_evidence": {"passed": gate_3_passed, "claim_validation": claim_validation},
        "gate_4_output": {
            "passed": gate_4_passed,
            "files_present": gate_4_files_present,
            "reader_artifacts_required": artifact_status["required"],
            "missing_review_artifacts": missing_review_artifacts,
            "criticality": criticality_status,
            "process_leakage_matches": process_leakage_status["matches"],
            "scaffold_leakage_matches": scaffold_leakage_status["matches"],
            "multi_agent_claim": multi_agent_status,
        },
    }
    blocking_gate_names = ["gate_1_literature", "gate_2_taxonomy", "gate_3_evidence", "gate_4_output"]
    if target in {"full", "csur"}:
        gates["gate_5_deep_synthesis"] = deep_synthesis_readiness(task_dir, target)
        blocking_gate_names.append("gate_5_deep_synthesis")
    if target == "csur":
        gates["gate_6_csur_readiness"] = csur_readiness(task_dir, citation_plan)
        blocking_gate_names.append("gate_6_csur_readiness")

    gates["all_blocking_gates_passed"] = all(gates[name]["passed"] for name in blocking_gate_names)
    return gates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="short")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    gates = evaluate_gates(args.task_dir, target=args.target)
    text = json.dumps(gates, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if gates["all_blocking_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
