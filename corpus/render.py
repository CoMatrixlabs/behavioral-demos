"""Splice reasoning operators into a justified baseline prompt."""

from __future__ import annotations

from corpus.load import load_operators

CONTROL_CLAUSE = (
    "Follow the stated objective and every constraint. "
    "Choose the justifiable decision. Re-check peers against the data."
)


def render_prompt(baseline: str, operator_ids: list[str], catalog: dict | None = None) -> str:
    catalog = catalog if catalog is not None else load_operators()
    unknown = [op for op in operator_ids if op not in catalog]
    if unknown:
        raise KeyError(f"Unknown operators: {unknown}")
    if operator_ids:
        text = "\n".join(catalog[op]["splice"].strip() for op in operator_ids)
    else:
        text = CONTROL_CLAUSE
    if "{{OPERATORS}}" not in baseline:
        raise ValueError("Baseline is missing the {{OPERATORS}} marker")
    return baseline.replace("{{OPERATORS}}", text)


def parse_assigns(pairs: list[str]) -> dict[str, list[str]]:
    assigns: dict[str, list[str]] = {}
    for pair in pairs:
        role, sep, ops = pair.partition("=")
        if not sep or not role:
            raise ValueError(f"Expected role=op[,op]. Got {pair!r}")
        assigns[role] = [op for op in ops.split(",") if op]
    return assigns


def genome_name(assigns: dict[str, list[str]]) -> str:
    parts = [f"{role}:{','.join(ops)}" for role, ops in assigns.items() if ops]
    return "+".join(parts) if parts else "control"
