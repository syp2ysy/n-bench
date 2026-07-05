#!/usr/bin/env python3
"""Shared status envelope helpers for survey-autoresearch scripts."""

from __future__ import annotations


STATUS_SCHEMA_VERSION = 1

TERMINAL_STATUSES = {
    "complete",
    "quality_limited_stop",
    "blocked_repeated_no_progress",
    "blocked_no_progress",
    "blocked_unknown_action",
}


def status_envelope(
    component: str,
    status: str,
    *,
    next_action: str | None = None,
    terminal: bool | None = None,
    blocked: bool | None = None,
    blocked_by_phase: str | None = None,
    active_batch_id: str | None = None,
    summary: dict | None = None,
) -> dict:
    """Return the stable top-level status shape used by scripts and tests."""
    if terminal is None:
        terminal = status in TERMINAL_STATUSES
    if blocked is None:
        blocked = bool(blocked_by_phase) or status.startswith("blocked") or status.startswith("waiting")
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "component": component,
        "status": status,
        "next_action": next_action,
        "terminal": bool(terminal),
        "blocked": bool(blocked),
        "blocked_by_phase": blocked_by_phase,
        "active_batch_id": active_batch_id,
        "summary": summary or {},
    }
