"""Load scenarios and the operator catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

CORPUS = Path(__file__).resolve().parent
SCENARIOS = CORPUS / "scenarios"
OPERATORS_PATH = CORPUS / "operators.yaml"


def load_operators() -> dict[str, dict]:
    raw = yaml.safe_load(OPERATORS_PATH.read_text())
    return {item["id"]: item for item in raw["operators"]}


def load_scenario(scenario_id: str) -> dict:
    path = SCENARIOS / f"{scenario_id}.yaml"
    if not path.exists():
        known = sorted(p.stem for p in SCENARIOS.glob("*.yaml"))
        raise KeyError(f"Unknown scenario {scenario_id!r}. Known: {known}")
    data = yaml.safe_load(path.read_text())
    data["roles_by_id"] = {role["id"]: role for role in data["roles"]}
    return data


def list_scenarios() -> list[str]:
    return sorted(p.stem for p in SCENARIOS.glob("*.yaml"))
