"""Emit Claude Agent Skills or LangGraph prompts from a scenario and a genome."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from corpus.load import load_scenario
from corpus.render import genome_name, parse_assigns, render_prompt

ROOT = Path(__file__).resolve().parent


def skill_text(role: dict, operators: list[str], prompt: str) -> str:
    header = {
        "name": role["id"],
        "role": role["id"],
        "description": role["description"],
        "operators": operators,
        "provenance": "generated",
    }
    front = yaml.safe_dump(header, sort_keys=False).strip()
    contract = (
        '{"decision": "<lattice option>", "reason": "<one sentence>", '
        '"message_to_peers": "<conclusion the next agent will read>"}'
    )
    return (
        f"---\n{front}\n---\n\n"
        f"# Agent Prompt\n\n{prompt.strip()}\n\n"
        f"## Output Contract\n\n{contract}\n"
    )


def prompt_text(role: dict, operators: list[str], prompt: str) -> str:
    header = {
        "role": role["id"],
        "description": role["description"],
        "operators": operators,
        "node": role["node"],
        "provenance": "generated",
    }
    front = yaml.safe_dump(header, sort_keys=False).strip()
    return f"---\n{front}\n---\n\n{prompt.strip()}\n"


def emit(
    scenario_id: str,
    assigns: dict[str, list[str]],
    out: Path,
    name: str | None = None,
) -> Path:
    scenario = load_scenario(scenario_id)
    known = set(scenario["roles_by_id"])
    unknown = set(assigns) - known
    if unknown:
        raise KeyError(f"Roles {sorted(unknown)} are not in {scenario_id}")
    out.mkdir(parents=True, exist_ok=True)
    for role in scenario["roles"]:
        operators = list(assigns.get(role["id"], []))
        prompt = render_prompt(role["baseline"], operators)
        if scenario["runtime"] == "claude_skills":
            path = out / role["id"] / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(skill_text(role, operators, prompt))
        else:
            path = out / f"{role['id']}.md"
            path.write_text(prompt_text(role, operators, prompt))
    (out / "genome.yaml").write_text(
        yaml.safe_dump(
            {
                "scenario": scenario_id,
                "name": name or genome_name(assigns),
                "assigns": {role["id"]: list(assigns.get(role["id"], [])) for role in scenario["roles"]},
            },
            sort_keys=False,
        )
    )
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate a genome of agent specs.")
    parser.add_argument("--scenario", required=True, choices=["analysis_cell", "ops_bridge"])
    parser.add_argument("--assign", action="append", default=[], help="role=operator[,operator]")
    parser.add_argument("--name", default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    dest = emit(args.scenario, parse_assigns(args.assign), args.out, name=args.name)
    print(dest)


if __name__ == "__main__":
    main()
