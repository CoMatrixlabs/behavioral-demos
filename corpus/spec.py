"""Load generated skill and prompt specs."""

from __future__ import annotations

from pathlib import Path

import yaml


def parse_spec(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ValueError("Spec is missing frontmatter")
    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front)
    return meta, body.strip()


def load_spec_dir(path: Path) -> tuple[dict[str, list[str]], dict[str, str], str]:
    files = sorted(path.glob("*/SKILL.md")) + sorted(path.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No specs in {path}")
    assigns: dict[str, list[str]] = {}
    prompts: dict[str, str] = {}
    for file in files:
        meta, body = parse_spec(file.read_text())
        assigns[meta["role"]] = list(meta.get("operators") or [])
        prompts[meta["role"]] = body
    genome = path / "genome.yaml"
    name = path.name
    if genome.exists():
        name = yaml.safe_load(genome.read_text())["name"]
    return assigns, prompts, name
