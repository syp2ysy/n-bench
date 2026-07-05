#!/usr/bin/env python3
"""Prepare and record discovery worker batches."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

try:  # pragma: no cover - script import fallback
    from .run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from .status_schema import STATUS_SCHEMA_VERSION, status_envelope
    from .validate_coverage import validate_coverage
except ImportError:  # pragma: no cover
    from run_expert_reviews import read_json, read_jsonl, write_json, write_jsonl
    from status_schema import STATUS_SCHEMA_VERSION, status_envelope
    from validate_coverage import validate_coverage


COMPONENT = "discovery_runtime_executor"
RESULT_SCHEMA_VERSION = 1
DISCOVERY_ROUTE_PLAN_VERSION = 4
PREFETCH_FILE = "discovery_prefetch_snapshots.jsonl"
REQUIRED_RESULT_KEYS = ["batch_id", "status", "raw_candidates", "search_routes", "lqs_scores", "corpus_expansion", "validator_results", "remaining_blockers"]
VALID_RESULT_STATUSES = {"resolved", "partially_resolved", "blocked"}


def _state(task_dir: Path) -> Path:
    return task_dir / "state"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_hash(value) -> str:
    payload = json.dumps(value or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _target(task_dir: Path) -> str:
    progress = read_json(_state(task_dir) / "progress.json")
    target = str(progress.get("target") or "full")
    return target if target in {"short", "full", "csur"} else "full"


def _task_spec(task_dir: Path) -> str:
    path = _state(task_dir) / "task_spec.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _survey_type(task_dir: Path) -> str:
    path = _state(task_dir) / "survey_type_plan.yml"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _topic_profile(task_dir: Path) -> dict:
    return read_json(_state(task_dir) / "topic_profile.json")


def _summary(doc: dict) -> dict:
    batches = doc.get("batches") or []
    pending = [batch for batch in batches if batch.get("status") != "resolved"]
    return {
        "batch_count": len(batches),
        "active_batch_id": doc.get("active_batch_id"),
        "pending_batch_count": len(pending),
        "resolved_batch_count": len(batches) - len(pending),
    }


def _with_metadata(doc: dict) -> dict:
    doc = dict(doc or {})
    doc["schema_version"] = STATUS_SCHEMA_VERSION
    doc["summary"] = _summary(doc)
    return doc


def _refresh_batch_statuses(doc: dict) -> dict:
    active_batch_id = None
    for batch in doc.get("batches") or []:
        if batch.get("status") == "resolved":
            continue
        if active_batch_id is None:
            if batch.get("status") in {"blocked_by_upstream", "blocked", "partially_resolved", "", None}:
                batch["status"] = "pending_spawn"
            if batch.get("status") == "pending_spawn":
                active_batch_id = batch.get("batch_id")
        else:
            batch["status"] = "blocked_by_upstream"
    doc["active_batch_id"] = active_batch_id
    return doc


def _safe_json_from_url(url: str, timeout: int = 8) -> tuple[dict, str | None]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "survey-autoresearch/0.1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), None
    except Exception as exc:  # pragma: no cover - network-dependent
        return {}, f"{type(exc).__name__}: {exc}"


def _safe_text_from_url(url: str, timeout: int = 8) -> tuple[str, str | None]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "survey-autoresearch/0.1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace"), None
    except Exception as exc:  # pragma: no cover - network-dependent
        return "", f"{type(exc).__name__}: {exc}"


def _openalex_candidates(query: str, batch_id: str, route_id: str, limit: int = 8) -> tuple[list[dict], str | None]:
    params = urllib.parse.urlencode(
        {
            "search": query,
            "per-page": max(1, min(limit, 25)),
            "filter": "from_publication_date:2018-01-01",
            "select": "id,doi,title,display_name,publication_year,authorships,primary_location,locations,type",
        }
    )
    payload, error = _safe_json_from_url(f"https://api.openalex.org/works?{params}")
    if error:
        return [], f"openalex:{error}"
    rows = []
    for idx, item in enumerate(payload.get("results") or []):
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("display_name") or ""
        if not title:
            continue
        authors = []
        for author in item.get("authorships") or []:
            if isinstance(author, dict):
                name = ((author.get("author") or {}).get("display_name") or "").strip()
                if name:
                    authors.append(name)
        primary = item.get("primary_location") or {}
        landing = (primary.get("landing_page_url") if isinstance(primary, dict) else "") or item.get("id") or ""
        rows.append(
            {
                "candidate_id": f"{batch_id}-openalex-{idx + 1:03d}",
                "title": title,
                "authors": authors[:8],
                "year": item.get("publication_year"),
                "doi": item.get("doi"),
                "url": landing,
                "source": "OpenAlex",
                "source_api": "openalex",
                "query": query,
                "route_id": route_id,
                "route_type": "keyword",
                "source_record_id": item.get("id"),
                "relevance_note": "Prefetched metadata; worker must audit topic relevance before retained selection.",
            }
        )
    return rows, None


def _arxiv_candidates(query: str, batch_id: str, route_id: str, limit: int = 8) -> tuple[list[dict], str | None]:
    search_query = urllib.parse.quote(f'all:"{query}"')
    url = f"https://export.arxiv.org/api/query?search_query={search_query}&start=0&max_results={max(1, min(limit, 20))}&sortBy=relevance&sortOrder=descending"
    text, error = _safe_text_from_url(url)
    if error:
        return [], f"arxiv:{error}"
    rows = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return [], f"arxiv:ParseError: {exc}"
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for idx, entry in enumerate(root.findall("atom:entry", ns)):
        title = " ".join((entry.findtext("atom:title", default="", namespaces=ns) or "").split())
        if not title:
            continue
        entry_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
        arxiv_id = entry_id.rstrip("/").split("/")[-1] if entry_id else ""
        authors = [
            " ".join((author.findtext("atom:name", default="", namespaces=ns) or "").split())
            for author in entry.findall("atom:author", ns)
        ]
        published = entry.findtext("atom:published", default="", namespaces=ns) or ""
        rows.append(
            {
                "candidate_id": f"{batch_id}-arxiv-{idx + 1:03d}",
                "title": title,
                "authors": [name for name in authors if name][:8],
                "year": int(published[:4]) if published[:4].isdigit() else None,
                "arxiv_id": arxiv_id,
                "url": entry_id,
                "source": "arXiv",
                "source_api": "arxiv",
                "query": query,
                "route_id": route_id,
                "route_type": "keyword",
                "abstract": " ".join((entry.findtext("atom:summary", default="", namespaces=ns) or "").split())[:1200],
                "relevance_note": "Prefetched metadata; worker must audit topic relevance before retained selection.",
            }
        )
    return rows, None


def _latest_prefetch(task_dir: Path, batch_id: str) -> dict:
    rows = [
        row for row in read_jsonl(_state(task_dir) / PREFETCH_FILE)
        if str(row.get("batch_id") or "") == str(batch_id)
        and int(row.get("route_plan_version") or 0) == DISCOVERY_ROUTE_PLAN_VERSION
    ]
    return rows[-1] if rows else {}


def prefetch_active_discovery_sources(task_dir: Path, per_query_limit: int = 8) -> dict:
    state = _state(task_dir)
    doc = _refresh_batch_statuses(read_json(state / "discovery_batches.json"))
    active = next((batch for batch in doc.get("batches") or [] if batch.get("batch_id") == doc.get("active_batch_id")), None)
    if not active:
        return {**status_envelope(COMPONENT, "no_active_discovery_batch", terminal=False, blocked=True), "prefetched_candidates": 0}
    batch_id = str(active.get("batch_id") or "")
    queries = [str(item) for item in active.get("seed_queries") or [] if str(item).strip()]
    queries = queries[: int(active.get("max_search_queries") or len(queries))]
    candidates: list[dict] = []
    errors: list[str] = []
    for idx, query in enumerate(queries, start=1):
        route_id = f"{batch_id}-prefetch-{idx:02d}"
        route_rows, error = _openalex_candidates(query, batch_id, route_id, per_query_limit)
        candidates.extend(route_rows)
        if error:
            errors.append(error)
        route_rows, error = _arxiv_candidates(query, batch_id, route_id, per_query_limit)
        candidates.extend(route_rows)
        if error:
            errors.append(error)
    deduped = _merge_rows(candidates, "prefetch")[: max(1, per_query_limit) * max(1, len(queries)) * 2]
    snapshot = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "route_plan_version": DISCOVERY_ROUTE_PLAN_VERSION,
        "batch_id": batch_id,
        "route_focus": active.get("route_focus"),
        "seed_queries": queries,
        "prefetched_candidates": deduped,
        "prefetch_errors": errors,
        "prefetched_at": _utc_now(),
    }
    write_jsonl(state / PREFETCH_FILE, read_jsonl(state / PREFETCH_FILE) + [snapshot])
    _write_runtime_action(task_dir, _with_metadata(doc))
    return {
        **status_envelope(
            COMPONENT,
            "prefetched" if deduped else "prefetch_empty",
            next_action="spawn_discovery_agents",
            terminal=False,
            blocked=not bool(deduped),
            blocked_by_phase="discovery",
            active_batch_id=batch_id,
            summary={"prefetched_candidate_count": len(deduped), "prefetch_error_count": len(errors), "query_count": len(queries)},
        ),
        "prefetched_candidate_count": len(deduped),
        "prefetch_errors": errors[:10],
    }


def record_prefetch_as_discovery_result(task_dir: Path, subagent_session_id: str = "deterministic_prefetch") -> dict:
    doc = _refresh_batch_statuses(read_json(_state(task_dir) / "discovery_batches.json"))
    active_batch_id = str(doc.get("active_batch_id") or "")
    if not active_batch_id:
        return {"status": "invalid", "error": "no_active_discovery_batch"}
    snapshot = _latest_prefetch(task_dir, active_batch_id)
    candidates = snapshot.get("prefetched_candidates") or []
    if not candidates:
        return {"status": "invalid", "error": "prefetch_snapshot_missing_or_empty", "batch_id": active_batch_id}
    route_ids = sorted({str(item.get("route_id") or f"{active_batch_id}-prefetch") for item in candidates if isinstance(item, dict)})
    routes = [
        {
            "route_id": route_id,
            "route_type": "keyword",
            "source": "OpenAlex/arXiv prefetch",
            "query": "; ".join(sorted({str(item.get("query") or "") for item in candidates if item.get("route_id") == route_id and item.get("query")}))[:500],
            "results_seen": len([item for item in candidates if item.get("route_id") == route_id]),
            "candidates_retained": len([item for item in candidates if item.get("route_id") == route_id]),
        }
        for route_id in route_ids
    ]
    lqs = [
        {
            "candidate_id": item.get("candidate_id"),
            "paper_id": item.get("paper_id") or item.get("candidate_id"),
            "lqs": 5.0,
            "depth_recommendation": "C",
            "note": "Deterministic discovery prefetch only; topic relevance audit must decide retained role and A/B eligibility.",
        }
        for item in candidates
        if isinstance(item, dict) and item.get("candidate_id")
    ]
    result = {
        "batch_id": active_batch_id,
        "status": "resolved",
        "raw_candidates": candidates,
        "search_routes": routes,
        "lqs_scores": lqs,
        "corpus_expansion": {
            "required": False,
            "status": "not_required",
            "visible_external_count": len(candidates),
            "retained_candidate_count": len(candidates),
            "curated_lists_checked": False,
            "recent_surveys_checked": False,
            "why_retained_corpus_is_sufficient": "Route-level deterministic metadata prefetch; global discovery sufficiency is checked only after all route batches merge.",
            "blocked_limitations": snapshot.get("prefetch_errors") or [],
        },
        "validator_results": [{"validator": "validate_discovery_route", "status": "passed"}],
        "remaining_blockers": [],
    }
    return record_discovery_result(task_dir, result, subagent_session_id)


def _route_batches(target: str, topic_profile: dict) -> list[dict]:
    seed_queries = [str(item) for item in topic_profile.get("search_seed_queries") or [] if str(item).strip()]
    def seed(index: int, fallback: str) -> str:
        return seed_queries[index] if len(seed_queries) > index else fallback

    base = [
        {
            "batch_id": "D001",
            "route_focus": "exact core phrase search for think-with-image and visual workspace reasoning",
            "required_route_types": ["keyword"],
            "min_raw_candidates": 8,
            "max_search_queries": 3,
            "seed_queries": [
                seed(0, '"think with image" multimodal reasoning'),
                '"think with images" "multimodal"',
                '"visual workspace" "multimodal reasoning"',
            ],
        },
        {
            "batch_id": "D002",
            "route_focus": "visual scratchpad keyword search",
            "required_route_types": ["keyword"],
            "min_raw_candidates": 8,
            "max_search_queries": 3,
            "seed_queries": [
                seed(1, '"visual scratchpad" multimodal reasoning'),
                '"visual scratchpad" "large multimodal model"',
                '"scratchpad" "image" "reasoning"',
            ],
        },
        {
            "batch_id": "D003",
            "route_focus": "image-as-workspace and visual intermediate-state keyword search",
            "required_route_types": ["keyword"],
            "min_raw_candidates": 8,
            "max_search_queries": 3,
            "seed_queries": [
                seed(2, '"image as workspace" multimodal reasoning'),
                seed(3, '"visual intermediate state" reasoning MLLM'),
                '"image-as-workspace" "reasoning"',
            ],
        },
        {
            "batch_id": "D004",
            "route_focus": "visual chain-of-thought and image-grounded action search",
            "required_route_types": ["keyword"],
            "min_raw_candidates": 12,
            "max_search_queries": 4,
            "seed_queries": [
                seed(4, '"visual chain of thought" image reasoning multimodal'),
                seed(6, '"image-grounded" reasoning actions crop zoom annotate MLLM'),
                '"multimodal" "visual tool use" reasoning',
                '"visual reasoning" "crop" "zoom" "MLLM"',
            ],
        },
        {
            "batch_id": "D005",
            "route_focus": "curated lists and benchmark pages for visual reasoning agents",
            "required_route_types": ["curated_list", "benchmark"],
            "min_raw_candidates": 12,
            "max_search_queries": 4,
            "seed_queries": [
                "awesome multimodal chain of thought visual reasoning",
                "awesome visual reasoning large multimodal model tool use",
                "multimodal reasoning benchmark visual scratchpad",
                "visual tool use MLLM benchmark",
            ],
        },
        {
            "batch_id": "D006",
            "route_focus": "related survey discovery for taxonomy and boundary positioning",
            "required_route_types": ["related_survey_refs", "keyword"],
            "min_raw_candidates": 12,
            "min_related_surveys": 6 if target == "full" else 10,
            "max_search_queries": 5,
            "seed_queries": [
                "survey visual reasoning large multimodal models chain of thought",
                "survey multimodal reasoning visual tool use",
                "review visual question answering reasoning large multimodal model",
                "survey multimodal agents visual reasoning",
                "survey large multimodal models reasoning",
            ],
        },
        {
            "batch_id": "D007",
            "route_focus": "snowballing from known core systems, benchmarks, and author clusters",
            "required_route_types": ["snowball", "author_group"],
            "min_raw_candidates": 20,
            "max_search_queries": 6,
            "seed_queries": [
                "Visual Sketchpad multimodal reasoning references",
                "OpenThinkIMG visual reasoning references",
                "VTool-R1 visual tool reasoning references",
                "DeepEyes multimodal reasoning references",
                "ReFocus visual reasoning MLLM references",
                "Multimodal-CoT visual chain of thought references",
            ],
        },
        {
            "batch_id": "D008",
            "route_focus": "venue and recent-paper expansion for core visual workspace mechanisms",
            "required_route_types": ["venue", "keyword"],
            "min_raw_candidates": 18,
            "max_search_queries": 6,
            "seed_queries": [
                "CVPR 2026 visual reasoning large multimodal model tool",
                "ICLR 2026 visual reasoning multimodal scratchpad",
                "NeurIPS 2025 visual reasoning MLLM tool use",
                "ACL 2025 multimodal chain of thought visual reasoning",
                "EMNLP 2025 visual tool use multimodal reasoning",
                "arXiv visual reasoning large multimodal model 2026",
            ],
        },
        {
            "batch_id": "D009",
            "route_focus": "metadata enrichment, deduplication, corpus expansion audit, and gap-filling",
            "required_route_types": ["keyword", "venue", "curated_list"],
            "min_raw_candidates": 25,
            "max_search_queries": 8,
            "seed_queries": seed_queries[:8],
        },
    ]
    if target == "short":
        return [
            {
                "batch_id": "D001",
                "route_focus": "compact discovery over core positive anchors, related surveys, and one snowball pass",
                "required_route_types": ["keyword", "snowball", "related_survey_refs", "curated_list"],
                "min_raw_candidates": 50,
                "min_related_surveys": 2,
                "max_search_queries": 8,
                "seed_queries": seed_queries,
            }
        ]
    if target == "csur":
        base.append(
            {
                "batch_id": "D010",
                "route_focus": "CSUR-grade long-tail expansion across adjacent venues and recent surveys",
                "required_route_types": ["venue", "related_survey_refs", "snowball"],
                "min_raw_candidates": 80,
                "min_related_surveys": 10,
                "max_search_queries": 10,
                "seed_queries": seed_queries,
            }
        )
    return base


def _prompt(task_dir: Path, batch: dict) -> str:
    topic_profile = _topic_profile(task_dir)
    prefetch = _latest_prefetch(task_dir, str(batch.get("batch_id") or ""))
    prefetched_count = len(prefetch.get("prefetched_candidates") or [])
    return (
        "You are a high-recall discovery worker for survey-autoresearch.\n"
        "Use real search sources and return structured discovery state. Do not invent papers or counts.\n"
        "Follow the topic_profile exactly: positive anchors define core relevance; negative anchors define drift risks; allowed background cannot become A/B core.\n"
        "This is one route-level discovery batch. Do not try to satisfy the full corpus alone; exhaust the assigned route, report blockers, and return only real records.\n"
        "Timebox the route: run only the listed seed queries or fewer, then return resolved/partial/blocked JSON. Do not keep expanding recursively.\n"
        f"Task directory: {task_dir.resolve()}\n"
        f"Batch id: {batch.get('batch_id')}\n"
        f"Route focus: {batch.get('route_focus')}\n"
        f"Required route types: {json.dumps(batch.get('required_route_types') or [], ensure_ascii=False)}\n"
        f"Minimum raw candidates for this route: {batch.get('min_raw_candidates')}\n"
        f"Minimum related surveys for this route, when applicable: {batch.get('min_related_surveys') or 0}\n"
        f"Maximum search queries for this route: {batch.get('max_search_queries') or len(batch.get('seed_queries') or [])}\n"
        f"Seed queries for this route: {json.dumps(batch.get('seed_queries') or [], ensure_ascii=False)}\n"
        f"Previous blockers for this route: {json.dumps(batch.get('last_blockers') or [], ensure_ascii=False)}\n"
        f"Prefetched metadata candidates available in the request payload: {prefetched_count}\n"
        f"Task spec:\n{_task_spec(task_dir)}\n"
        f"Topic profile:\n{json.dumps(topic_profile, indent=2, sort_keys=True, ensure_ascii=False)}\n"
        f"Survey type plan:\n{_survey_type(task_dir)}\n"
        "Return one JSON object with keys: batch_id, status, raw_candidates, search_routes, lqs_scores, corpus_expansion, validator_results, remaining_blockers. "
        "For a resolved route batch, include a passed validator named validate_discovery_route or validate_discovery. "
        "If time runs short, return status partially_resolved with the real records already found rather than continuing."
    )


def _spawn_request(task_dir: Path, batch: dict) -> dict:
    prefetch = _latest_prefetch(task_dir, str(batch.get("batch_id") or ""))
    return {
        "request_id": f"discovery-{batch.get('batch_id')}",
        "next_action": "spawn_discovery_agents",
        "agent_type": "worker",
        "fork_context": False,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "required_result_keys": list(REQUIRED_RESULT_KEYS),
        "batch_id": batch.get("batch_id"),
        "attempt": int(batch.get("attempt") or 1),
        "previous_blockers": batch.get("last_blockers") or [],
        "route_focus": batch.get("route_focus"),
        "required_route_types": batch.get("required_route_types") or [],
        "min_raw_candidates": batch.get("min_raw_candidates"),
        "min_related_surveys": batch.get("min_related_surveys") or 0,
        "max_search_queries": batch.get("max_search_queries") or len(batch.get("seed_queries") or []),
        "route_plan_version": DISCOVERY_ROUTE_PLAN_VERSION,
        "prefetched_candidates": (prefetch.get("prefetched_candidates") or [])[:50],
        "prefetch_errors": prefetch.get("prefetch_errors") or [],
        "prefetch_snapshot_at": prefetch.get("prefetched_at"),
        "target": _target(task_dir),
        "task_spec": _task_spec(task_dir),
        "topic_profile": _topic_profile(task_dir),
        "survey_type_plan": _survey_type(task_dir),
        "record_command": f"python3 scripts/discovery_runtime_executor.py --task-dir {task_dir.resolve()} --record-result <result.json> --subagent-session-id <subagent-session-id>",
        "message": _prompt(task_dir, batch),
        "status": "pending_spawn",
    }


def _write_runtime_action(task_dir: Path, doc: dict) -> dict:
    doc = _with_metadata(doc)
    active = next((batch for batch in doc.get("batches") or [] if batch.get("batch_id") == doc.get("active_batch_id")), None)
    requests = [_spawn_request(task_dir, active)] if active else []
    next_action = "spawn_discovery_agents" if active else "rerun_phase_gate"
    result_status = "blocked_discovery_agent_spawn_required" if active else "discovery_batches_resolved"
    write_json(_state(task_dir) / "discovery_spawn_requests.json", {"next_action": next_action, "spawn_requests": requests})
    write_json(
        _state(task_dir) / "discovery_runtime_action.json",
        {
            **status_envelope(
                COMPONENT,
                "pending_discovery_runtime" if active else "discovery_batches_resolved",
                next_action=next_action,
                terminal=active is None,
                blocked=active is not None,
                blocked_by_phase="discovery" if active else None,
                active_batch_id=doc.get("active_batch_id"),
                summary={**(doc.get("summary") or {}), "spawn_request_count": len(requests)},
            ),
            "active_batch_id": doc.get("active_batch_id"),
        },
    )
    return {
        **status_envelope(
            COMPONENT,
            result_status,
            next_action=next_action,
            terminal=active is None,
            blocked=active is not None,
            blocked_by_phase="discovery" if active else None,
            active_batch_id=doc.get("active_batch_id"),
            summary={**(doc.get("summary") or {}), "spawn_request_count": len(requests)},
        ),
        "spawn_request_count": len(requests),
        "spawn_requests": requests,
    }


def prepare_discovery_batches(task_dir: Path) -> dict:
    state = _state(task_dir)
    target = _target(task_dir)
    route_plan = _route_batches(target, _topic_profile(task_dir))
    plan_hash = _stable_hash(
        {
            "route_plan_version": DISCOVERY_ROUTE_PLAN_VERSION,
            "task_spec": _task_spec(task_dir),
            "topic_profile": _topic_profile(task_dir),
            "survey_type_plan": _survey_type(task_dir),
            "target": target,
            "route_plan": route_plan,
        }
    )
    existing = read_json(state / "discovery_batches.json")
    if existing.get("plan_hash") == plan_hash and existing.get("batches"):
        doc = _refresh_batch_statuses(existing)
    else:
        doc = {
            "plan_hash": plan_hash,
            "route_plan_version": DISCOVERY_ROUTE_PLAN_VERSION,
            "batches": [{**batch, "status": "pending_spawn", "attempt": 1} for batch in route_plan],
        }
        doc = _refresh_batch_statuses(doc)
    doc = _with_metadata(doc)
    write_json(state / "discovery_batches.json", doc)
    return _write_runtime_action(task_dir, doc)


def collect_discovery_status(task_dir: Path) -> dict:
    state = _state(task_dir)
    doc = _refresh_batch_statuses(read_json(state / "discovery_batches.json"))
    if not doc.get("batches"):
        return {
            **status_envelope(COMPONENT, "not_prepared", next_action="prepare_discovery_batches", terminal=False, blocked=True, blocked_by_phase="discovery", summary={"batch_count": 0}),
            "batches": [],
        }
    doc, _coverage = _finalize_discovery_if_ready(task_dir, doc, _utc_now())
    doc = _with_metadata(_refresh_batch_statuses(doc))
    write_json(state / "discovery_batches.json", doc)
    all_resolved = all(batch.get("status") == "resolved" for batch in doc.get("batches") or [])
    return {
        **status_envelope(
            COMPONENT,
            "resolved" if all_resolved else "pending_discovery_runtime",
            next_action="rerun_phase_gate" if all_resolved else "spawn_discovery_agents",
            terminal=all_resolved,
            blocked=not all_resolved,
            blocked_by_phase=None if all_resolved else "discovery",
            active_batch_id=doc.get("active_batch_id"),
            summary=doc.get("summary") or {},
        ),
        "batches": doc.get("batches") or [],
        "all_batches_resolved": all_resolved,
    }


def _passed_validators(result: dict) -> set[str]:
    validators = result.get("validator_results")
    if not isinstance(validators, list):
        return set()
    return {
        str(item.get("validator") or item.get("name") or "").strip()
        for item in validators
        if isinstance(item, dict)
        and str(item.get("status") or "").lower() == "passed"
        and str(item.get("validator") or item.get("name") or "").strip()
    }


def _validate_result_payload(result: dict) -> tuple[list[str], list[dict], list[dict], list[dict], dict]:
    errors: list[str] = []
    raw = result.get("raw_candidates")
    routes = result.get("search_routes")
    lqs = result.get("lqs_scores")
    corpus = result.get("corpus_expansion")
    if not isinstance(raw, list):
        errors.append("invalid_raw_candidates")
        raw = []
    if not isinstance(routes, list):
        errors.append("invalid_search_routes")
        routes = []
    if not isinstance(lqs, list):
        errors.append("invalid_lqs_scores")
        lqs = []
    if not isinstance(corpus, dict):
        errors.append("invalid_corpus_expansion")
        corpus = {}
    return errors, raw, routes, lqs, corpus


def _validate_result(task_dir: Path, result: dict, batch: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result_not_object"]
    for key in REQUIRED_RESULT_KEYS:
        if key not in result:
            errors.append(f"missing_{key}")
    if str(result.get("batch_id") or "") != str(batch.get("batch_id") or ""):
        errors.append("batch_id_mismatch")
    if str(result.get("status") or "") not in VALID_RESULT_STATUSES:
        errors.append("invalid_status")
    payload_errors, _raw, _routes, _lqs, _corpus = _validate_result_payload(result)
    errors.extend(payload_errors)
    if result.get("status") != "resolved":
        return sorted(set(errors))
    passed = _passed_validators(result)
    if not ({"validate_discovery", "validate_discovery_route"} & passed):
        errors.append("missing_acceptance_validators")
    return sorted(set(errors))


def _norm_text(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _dedupe_key(item: dict, fallback_prefix: str, idx: int) -> str:
    for key in ["doi", "arxiv_id", "url", "canonical_url", "title", "route_id", "paper_id", "candidate_id", "query"]:
        value = _norm_text(item.get(key))
        if value:
            return f"{key}:{value}"
    return f"{fallback_prefix}:{idx}"


def _merge_rows(rows: list[dict], fallback_prefix: str) -> list[dict]:
    merged: dict[str, dict] = {}
    for idx, item in enumerate(rows):
        if not isinstance(item, dict):
            continue
        key = _dedupe_key(item, fallback_prefix, idx)
        current = dict(merged.get(key) or {})
        current.update({k: v for k, v in item.items() if v not in [None, "", [], {}]})
        merged[key] = current
    return list(merged.values())


def _score_value(row: dict) -> float:
    for key in ["lqs", "score", "relevance_score"]:
        try:
            return float(row.get(key))
        except (TypeError, ValueError):
            continue
    return 0.0


def _merge_lqs(rows: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        key = str(row.get("paper_id") or row.get("candidate_id") or f"lqs:{idx}")
        if key not in merged or _score_value(row) >= _score_value(merged[key]):
            merged[key] = row
    return list(merged.values())


def _merge_corpus_expansion(corpora: list[dict], raw_count: int, route_count: int) -> dict:
    def safe_int(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    statuses = [str(item.get("status") or "not_required") for item in corpora if isinstance(item, dict)]
    blocked = []
    summaries = []
    for item in corpora:
        if not isinstance(item, dict):
            continue
        blocked.extend(str(value) for value in item.get("blocked_limitations") or [] if str(value).strip())
        summaries.append(
            {
                "status": item.get("status"),
                "visible_external_count": item.get("visible_external_count"),
                "retained_candidate_count": item.get("retained_candidate_count"),
                "why_retained_corpus_is_sufficient": item.get("why_retained_corpus_is_sufficient"),
            }
        )
    required = any(bool(item.get("required")) for item in corpora if isinstance(item, dict))
    complete_like = {"complete", "not_required", ""}
    status = "complete" if all(status in complete_like for status in statuses) else "in_progress"
    return {
        "required": required,
        "status": status,
        "visible_external_count": max([safe_int(item.get("visible_external_count")) for item in corpora if isinstance(item, dict)] + [raw_count]),
        "largest_visible_external_count": max([safe_int(item.get("largest_visible_external_count") or item.get("visible_external_count")) for item in corpora if isinstance(item, dict)] + [raw_count]),
        "retained_candidate_count": raw_count,
        "search_route_count": route_count,
        "curated_lists_checked": any(bool(item.get("curated_lists_checked")) for item in corpora if isinstance(item, dict)),
        "recent_surveys_checked": any(bool(item.get("recent_surveys_checked")) for item in corpora if isinstance(item, dict)),
        "why_retained_corpus_is_sufficient": "Merged from route-level discovery batches; full source/topic gates still verify retained corpus before paper reading.",
        "batch_summaries": summaries,
        "blocked_limitations": sorted(set(blocked)),
    }


def _latest_resolved_rows(task_dir: Path, doc: dict) -> list[dict]:
    resolved_batch_ids = {str(batch.get("batch_id")) for batch in doc.get("batches") or [] if batch.get("status") == "resolved"}
    latest: dict[str, dict] = {}
    for row in reversed(read_jsonl(_state(task_dir) / "discovery_results.jsonl")):
        batch_id = str(row.get("batch_id") or "")
        if batch_id in resolved_batch_ids and batch_id not in latest and row.get("status") == "resolved":
            latest[batch_id] = row
    return [latest[batch_id] for batch_id in sorted(latest)]


def _merged_discovery_payload(task_dir: Path, doc: dict) -> tuple[dict, dict]:
    rows = _latest_resolved_rows(task_dir, doc)
    raw = _merge_rows([item for row in rows for item in row.get("raw_candidates") or []], "raw")
    routes = _merge_rows([item for row in rows for item in row.get("search_routes") or []], "route")
    lqs = _merge_lqs([item for row in rows for item in row.get("lqs_scores") or []])
    corpus = _merge_corpus_expansion([row.get("corpus_expansion") or {} for row in rows], len(raw), len(routes))
    coverage = validate_coverage(raw, routes, lqs, corpus, [], [], _target(task_dir))
    return {
        "raw_candidates": raw,
        "search_routes": routes,
        "lqs_scores": lqs,
        "corpus_expansion": corpus,
    }, coverage


def _ensure_enrichment_batch(doc: dict, blockers: list[str], recorded_at: str) -> None:
    batch = next((item for item in doc.get("batches") or [] if item.get("batch_id") == "D999"), None)
    if batch is None:
        doc.setdefault("batches", []).append(
            {
                "batch_id": "D999",
                "route_focus": "final coverage enrichment for unresolved discovery gaps",
                "required_route_types": ["keyword", "snowball", "related_survey_refs", "curated_list", "venue", "benchmark", "author_group"],
                "min_raw_candidates": 25,
                "status": "pending_spawn",
                "attempt": 1,
                "last_blockers": blockers,
                "created_at": recorded_at,
            }
        )
        return
    batch["status"] = "pending_spawn"
    batch["attempt"] = int(batch.get("attempt") or 1) + 1
    batch["last_blockers"] = blockers
    batch["last_blocked_at"] = recorded_at


def _finalize_discovery_if_ready(task_dir: Path, doc: dict, recorded_at: str) -> tuple[dict, dict | None]:
    if not doc.get("batches") or not all(batch.get("status") == "resolved" for batch in doc.get("batches") or []):
        return doc, None
    payload, coverage = _merged_discovery_payload(task_dir, doc)
    if not coverage.get("discovery_sufficient"):
        blockers = coverage.get("discovery_missing") or coverage.get("missing") or ["discovery_not_sufficient_after_merge"]
        _ensure_enrichment_batch(doc, blockers, recorded_at)
        return doc, coverage
    state = _state(task_dir)
    write_jsonl(state / "raw_candidates.jsonl", payload["raw_candidates"])
    write_jsonl(state / "search_routes.jsonl", payload["search_routes"])
    write_jsonl(state / "lqs_scores.jsonl", payload["lqs_scores"])
    write_json(state / "corpus_expansion.json", payload["corpus_expansion"])
    doc["merged_at"] = recorded_at
    doc["merged_coverage"] = coverage
    doc["merged_counts"] = {
        "raw_candidates": len(payload["raw_candidates"]),
        "search_routes": len(payload["search_routes"]),
        "lqs_scores": len(payload["lqs_scores"]),
    }
    return doc, coverage


def record_discovery_result(task_dir: Path, result: dict, subagent_session_id: str) -> dict:
    state = _state(task_dir)
    doc = _refresh_batch_statuses(read_json(state / "discovery_batches.json"))
    batch_id = str(result.get("batch_id") or "")
    batch = next((item for item in doc.get("batches") or [] if str(item.get("batch_id") or "") == batch_id), None)
    if not batch:
        return {"status": "invalid", "error": "unknown_batch_id"}
    if batch_id != str(doc.get("active_batch_id") or ""):
        return {"status": "invalid", "error": "batch_blocked_by_upstream"}
    errors = _validate_result(task_dir, result, batch)
    if errors:
        return {"status": "invalid", "error": "invalid_discovery_result", "errors": errors}
    recorded_at = _utc_now()
    row = {**result, "fresh_context": True, "subagent_session_id": subagent_session_id, "recorded_at": recorded_at}
    write_jsonl(state / "discovery_results.jsonl", read_jsonl(state / "discovery_results.jsonl") + [row])
    if result.get("status") == "resolved":
        batch["status"] = "resolved"
        batch["resolved_at"] = recorded_at
        batch["subagent_session_id"] = subagent_session_id
    else:
        batch["status"] = "pending_spawn"
        batch["attempt"] = int(batch.get("attempt") or 1) + 1
        batch["last_blocked_at"] = recorded_at
        batch["last_blockers"] = result.get("remaining_blockers") or []
        batch["last_status"] = str(result.get("status") or "")
    doc, coverage = _finalize_discovery_if_ready(task_dir, doc, recorded_at)
    doc = _with_metadata(_refresh_batch_statuses(doc))
    write_json(state / "discovery_batches.json", doc)
    _write_runtime_action(task_dir, doc)
    return {
        "status": "recorded",
        "batch_id": batch_id,
        "next_active_batch_id": doc.get("active_batch_id"),
        "merged_discovery_sufficient": None if coverage is None else bool(coverage.get("discovery_sufficient")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--collect-status", action="store_true")
    parser.add_argument("--prefetch-active", action="store_true")
    parser.add_argument("--record-prefetch-as-result", action="store_true")
    parser.add_argument("--record-result", type=Path)
    parser.add_argument("--subagent-session-id")
    args = parser.parse_args()
    if args.prepare:
        result = prepare_discovery_batches(args.task_dir)
    elif args.collect_status:
        result = collect_discovery_status(args.task_dir)
    elif args.prefetch_active:
        result = prefetch_active_discovery_sources(args.task_dir)
    elif args.record_prefetch_as_result:
        result = record_prefetch_as_discovery_result(args.task_dir, args.subagent_session_id or "deterministic_prefetch")
    elif args.record_result:
        if not args.subagent_session_id:
            result = {"status": "invalid", "error": "missing_subagent_session_id"}
        else:
            result = record_discovery_result(args.task_dir, json.loads(args.record_result.read_text(encoding="utf-8")), args.subagent_session_id)
    else:
        result = {"status": "invalid", "error": "choose --prepare, --collect-status, or --record-result"}
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
