"""Shared trace assembly for both runtimes."""

from __future__ import annotations

from corpus.grade import grade
from corpus.render import genome_name, render_prompt
from corpus.world import execute, initial_world


def blank_trace(scenario: dict, assigns: dict[str, list[str]], name: str | None = None) -> dict:
    return {
        "scenario": scenario["id"],
        "genome_name": name or genome_name(assigns),
        "genome": {role["id"]: list(assigns.get(role["id"], [])) for role in scenario["roles"]},
        "messages": [],
        "decisions": [],
        "tool_calls": [],
        "prompts": {},
        "world_start": initial_world(scenario),
    }


def apply_turn(trace: dict, turn: dict, world: dict, turn_index: int) -> None:
    for name, args in turn["tool_requests"]:
        recorded, result = execute(name, args, world)
        trace["tool_calls"].append({"role": turn["role"], "name": name, "args": recorded, "result": result})
    trace["decisions"].append(
        {
            "role": turn["role"],
            "node": turn["node"],
            "option": turn["option"],
            "reason": turn["reason"],
        }
    )
    trace["messages"].append({"role": turn["role"], "turn": turn_index, "content": turn["content"]})


def finish(scenario: dict, trace: dict, prompts: dict[str, str]) -> dict:
    trace["prompts"] = prompts
    trace.update(grade(scenario, trace))
    return trace


def prompts_for(scenario: dict, assigns: dict[str, list[str]]) -> dict[str, str]:
    return {
        role["id"]: render_prompt(role["baseline"], assigns.get(role["id"], []))
        for role in scenario["roles"]
    }
