"""Analysis-cell runner. Each role is a Claude Agent Skill on a message bus."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

from corpus.load import load_scenario
from corpus.scripted import analysis_tools, analysis_turn, make_turn
from corpus.spec import load_spec_dir
from corpus.trace import apply_turn, blank_trace, finish, prompts_for

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS = ROOT / "apps" / "claude_skills" / "skills"


def run(
    assigns: dict[str, list[str]] | None = None,
    name: str | None = None,
    prompts: dict[str, str] | None = None,
    live: bool = False,
) -> dict:
    scenario = load_scenario("analysis_cell")
    assigns = {role: list((assigns or {}).get(role, [])) for role in scenario["order"]}
    rendered = prompts or prompts_for(scenario, assigns)
    trace = blank_trace(scenario, assigns, name)
    world = trace["world_start"]
    nodes = {role["id"]: role["node"] for role in scenario["roles"]}
    for index, role in enumerate(scenario["order"], start=1):
        if live:
            turn = live_turn(role, nodes[role], rendered[role], trace["messages"])
        else:
            turn = analysis_turn(role, assigns.get(role, []), trace["messages"])
        apply_turn(trace, turn, world, index)
    return finish(scenario, trace, rendered)


def run_skills(path: Path, live: bool = False) -> dict:
    assigns, prompts, name = load_spec_dir(path)
    return run(assigns, name=name, prompts=prompts, live=live)


def live_turn(role: str, node: str, prompt: str, messages: list[dict]) -> dict:
    data = complete_claude(prompt, json.dumps({"peers": messages}))
    option = data["decision"]
    reason = data.get("reason", "")
    content = data.get("message_to_peers") or reason
    return make_turn(role, node, option, reason, content, analysis_tools(role, option))


def complete_claude(system: str, user: str) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Set ANTHROPIC_API_KEY to run --live")
    payload = {
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        "max_tokens": 400,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read().decode())
    return _parse_json(body["content"][0]["text"])


def _parse_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"Model did not return JSON: {text[:200]}")
    return json.loads(text[start : end + 1])


def format_report(trace: dict) -> str:
    lines = [
        f"{trace['scenario']}  {trace['genome_name']}  {trace['verdict']}",
    ]
    for decision in trace["decisions"]:
        lines.append(f"  {decision['role']}: {decision['option']}")
    for call in trace["tool_calls"]:
        lines.append(f"  tool {call['name']} {call['args']} -> {call['result']}")
    for item in trace["violations"]:
        if item["kind"] == "decision":
            lines.append(f"  break {item['node']} {item['option']}")
        else:
            lines.append(f"  break {item['check']}")
    for message in trace["messages"]:
        lines.append(f"  msg {message['role']}: {message['content']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the analysis-cell skills.")
    parser.add_argument("--skills", type=Path, default=DEFAULT_SKILLS)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    print(format_report(run_skills(args.skills, live=args.live)))


if __name__ == "__main__":
    main()
