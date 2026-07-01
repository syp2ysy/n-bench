#!/usr/bin/env python3
"""Validate topic-level survey architecture diagnosis."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ALLOWED_PRIMARY_TYPES = {
    "system-object",
    "method-family",
    "benchmark/evaluation",
    "application-domain",
    "risk/threat",
}

SURVEY_TYPE_ALIASES = {
    "system object": "system-object",
    "system_object": "system-object",
    "method family": "method-family",
    "method_family": "method-family",
    "benchmark": "benchmark/evaluation",
    "evaluation": "benchmark/evaluation",
    "application domain": "application-domain",
    "application_domain": "application-domain",
    "risk": "risk/threat",
    "threat": "risk/threat",
}


def parse_structured_text(text: str) -> dict:
    """Parse JSON or a small YAML-like subset used by this skill."""
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    data: dict[str, object] = {}
    current_key: str | None = None
    current_section: str | None = None
    for raw_line in stripped.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = re.match(r"^([A-Za-z_][A-Za-z0-9_/-]*):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2).strip()
            current_key = key
            current_section = None
            if value:
                data[key] = _parse_scalar_or_list(value)
            else:
                data[key] = [] if key.endswith(("lenses", "pressures", "structure", "templates")) else {}
            continue
        nested = re.match(r"^\s{2,}([A-Za-z0-9_ /-]+):\s*(.*)$", line)
        if nested and current_key:
            name, value = nested.group(1).strip(), nested.group(2).strip()
            if not isinstance(data.get(current_key), dict):
                data[current_key] = {}
            if value:
                data[current_key][name] = _parse_scalar_or_list(value)
                current_section = None
            else:
                data[current_key][name] = []
                current_section = name
            continue
        nested_item = re.match(r"^\s{4,}-\s*(.+)$", line)
        if nested_item and current_key and current_section and isinstance(data.get(current_key), dict):
            data[current_key].setdefault(current_section, [])
            data[current_key][current_section].append(_parse_scalar_or_list(nested_item.group(1).strip()))
            continue
        item = re.match(r"^\s*-\s*(.+)$", line)
        if item and current_key:
            value = item.group(1).strip()
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            data[current_key].append(_parse_scalar_or_list(value))
            continue
    return data


def _parse_scalar_or_list(value: str):
    value = value.strip().strip("\"'")
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [part.strip().strip("\"'") for part in inner.split(",") if part.strip()]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value is None or value == "":
        return []
    return [value]


def _normalize_type(value: str) -> str:
    lower = str(value or "").strip().lower()
    return SURVEY_TYPE_ALIASES.get(lower, lower)


def validate_topic_diagnosis(data_or_text) -> dict:
    data = parse_structured_text(data_or_text) if isinstance(data_or_text, str) else (data_or_text or {})
    errors: list[str] = []
    primary = _normalize_type(data.get("primary_survey_type") or data.get("primary"))
    if primary not in ALLOWED_PRIMARY_TYPES:
        errors.append("missing_or_unknown_primary_survey_type")
    if not _as_list(data.get("secondary_lenses")):
        errors.append("missing_secondary_lenses")
    if not _as_list(data.get("domain_pressures")):
        errors.append("missing_domain_pressures")
    if not isinstance(data.get("evidence_norm"), dict) or not data.get("evidence_norm"):
        errors.append("missing_evidence_norm")
    if len(_as_list(data.get("recommended_structure"))) < 3:
        errors.append("recommended_structure_too_thin")
    if not _as_list(data.get("excluded_templates")):
        errors.append("missing_excluded_templates")
    section_grammar = data.get("section_grammar")
    if not isinstance(section_grammar, dict) or len(section_grammar) < 2:
        errors.append("missing_section_grammar")
    else:
        thin = [
            name for name, moves in section_grammar.items()
            if len(_as_list(moves)) < 3
        ]
        if thin:
            errors.append("thin_section_grammar:" + ",".join(sorted(thin)))
    return {
        "valid": not errors,
        "errors": errors,
        "primary_survey_type": primary,
        "secondary_lenses": _as_list(data.get("secondary_lenses")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic-diagnosis", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_topic_diagnosis(args.topic_diagnosis.read_text(encoding="utf-8"))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
