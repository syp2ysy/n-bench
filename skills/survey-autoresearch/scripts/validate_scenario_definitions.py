#!/usr/bin/env python3
"""Validate scenario/domain definitions for survey synthesis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_SCENARIO_FIELDS = [
    "scenario",
    "required_fields",
    "typical_benchmarks",
    "unsuitable_claims",
    "evaluation_pressure",
]


def parse_structured_text(text: str):
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    data: dict[str, object] = {}
    scenarios: list[dict] = []
    current: dict | None = None
    current_key: str | None = None
    for raw in stripped.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("scenarios:"):
            data["scenarios"] = scenarios
            current_key = "scenarios"
            continue
        if line.lstrip().startswith("- "):
            item = line.lstrip()[2:].strip()
            if current_key == "scenarios":
                if current:
                    scenarios.append(current)
                current = {}
                if ":" in item:
                    key, value = item.split(":", 1)
                    current[key.strip()] = _parse_value(value.strip())
                continue
            if current is not None and current_key:
                current.setdefault(current_key, [])
                if isinstance(current[current_key], list):
                    current[current_key].append(_parse_value(item))
                continue
        if current is not None and ":" in line:
            key, value = line.strip().split(":", 1)
            current_key = key.strip()
            current[current_key] = _parse_value(value.strip())
        elif ":" in line and not raw.startswith(" "):
            key, value = line.split(":", 1)
            data[key.strip()] = _parse_value(value.strip())
    if current:
        scenarios.append(current)
    if scenarios:
        data["scenarios"] = scenarios
    return data


def _parse_value(value: str):
    value = value.strip().strip("\"'")
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip("\"'") for part in inner.split(",")]
    return value


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def validate_scenario_definitions(definitions, target: str = "full") -> dict:
    data = parse_structured_text(definitions) if isinstance(definitions, str) else (definitions or {})
    scenarios = data.get("scenarios") or data.get("contexts") or data.get("domains") or []
    if not isinstance(scenarios, list):
        scenarios = []
    errors: list[str] = []
    invalid: dict[str, list[str]] = {}
    min_count = 0 if target == "short" else 4
    if len(scenarios) < min_count:
        errors.append("too_few_scenarios")
    for idx, scenario in enumerate(scenarios, start=1):
        name = str(scenario.get("scenario") or scenario.get("context") or scenario.get("domain") or f"scenario_{idx}")
        item_errors = []
        if not _nonempty(scenario.get("object_definition") or scenario.get("definition") or scenario.get("capability_definition")):
            item_errors.append("missing_definition")
        for field in REQUIRED_SCENARIO_FIELDS:
            if field == "scenario":
                if not _nonempty(scenario.get("scenario") or scenario.get("context") or scenario.get("domain")):
                    item_errors.append("missing_scenario")
            elif field == "typical_benchmarks":
                if not _nonempty(scenario.get("typical_benchmarks") or scenario.get("evaluation_settings") or scenario.get("benchmarks")):
                    item_errors.append("missing_typical_benchmarks")
            elif field == "failure_risks":
                continue
            elif not _nonempty(scenario.get(field)):
                item_errors.append(f"missing_{field}")
        if not _nonempty(scenario.get("failure_risks") or scenario.get("risks") or scenario.get("confounders")):
            item_errors.append("missing_failure_risks")
        if item_errors:
            invalid[name] = item_errors
    if invalid:
        errors.append("invalid_scenario_definitions")
    return {
        "valid": not errors,
        "errors": errors,
        "total_scenarios": len(scenarios),
        "invalid_scenarios": invalid,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-definitions", required=True, type=Path)
    parser.add_argument("--target", choices=["short", "full", "csur"], default="full")
    args = parser.parse_args()
    result = validate_scenario_definitions(args.scenario_definitions.read_text(encoding="utf-8"), args.target)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
