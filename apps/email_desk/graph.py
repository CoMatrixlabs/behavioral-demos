"""Email desk as a LangGraph. Sourcer, drafter, then sender. Mail leaves only through the dummy client."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from apps.email_desk.tools import TOOLS, bind_args
from corpus.load import load_scenario
from corpus.scripted import email_turn
from corpus.spec import load_spec_dir
from corpus.trace import blank_trace, finish, prompts_for

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPTS = ROOT / "apps" / "email_desk" / "prompts"


class DeskState(TypedDict):
    assigns: dict
    world: dict
    messages: list
    decisions: list
    tool_calls: list
    turn_index: int


def build_graph() -> StateGraph:
    graph = StateGraph(DeskState)
    graph.add_node("sourcer", _node("sourcer"))
    graph.add_node("drafter", _node("drafter"))
    graph.add_node("sender", _node("sender"))
    graph.set_entry_point("sourcer")
    graph.add_edge("sourcer", "drafter")
    graph.add_edge("drafter", "sender")
    graph.add_edge("sender", END)
    return graph


def compile_app():
    return build_graph().compile()


def run(
    assigns: dict[str, list[str]] | None = None,
    name: str | None = None,
    prompts: dict[str, str] | None = None,
    live: bool = False,
) -> dict:
    del live  # the desk grades the scripted genome; the prompts are what a live model would see
    scenario = load_scenario("email_desk")
    assigns = {role: list((assigns or {}).get(role, [])) for role in scenario["order"]}
    rendered = prompts or prompts_for(scenario, assigns)
    trace = blank_trace(scenario, assigns, name)
    final = compile_app().invoke(
        {
            "assigns": assigns,
            "world": trace["world_start"],
            "messages": [],
            "decisions": [],
            "tool_calls": [],
            "turn_index": 1,
        }
    )
    trace["messages"] = final["messages"]
    trace["decisions"] = final["decisions"]
    trace["tool_calls"] = final["tool_calls"]
    return finish(scenario, trace, rendered)


def run_prompts(path: Path, live: bool = False) -> dict:
    assigns, prompts, name = load_spec_dir(path)
    return run(assigns, name=name, prompts=prompts, live=live)


def _node(role: str):
    def run_node(state: DeskState) -> dict:
        turn = email_turn(role, state["assigns"].get(role, []), state["messages"])
        tool_calls = list(state["tool_calls"])
        for name, args in turn["tool_requests"]:
            recorded = bind_args(name, args, state["world"])
            result = TOOLS[name].invoke(recorded)
            tool_calls.append({"role": role, "name": name, "args": _trace_args(name, args, state["world"]), "result": result})
        return {
            "messages": state["messages"]
            + [{"role": role, "turn": state["turn_index"], "content": turn["content"]}],
            "decisions": state["decisions"]
            + [
                {
                    "role": role,
                    "node": turn["node"],
                    "option": turn["option"],
                    "reason": turn["reason"],
                }
            ],
            "tool_calls": tool_calls,
            "turn_index": state["turn_index"] + 1,
        }

    return run_node


def _trace_args(name: str, args: dict, world: dict) -> dict:
    """Args the lattice sees. The tool schema also carries the source catalog."""
    if name == "list_sources":
        return {}
    if name == "read_source":
        approved = next(source["approved"] for source in world["sources"] if source["id"] == args["source_id"])
        return {"source_id": args["source_id"], "approved": approved}
    if name == "deliver_email":
        source = next(source for source in world["sources"] if source["id"] == args["source_id"])
        return {
            "to": args["to"],
            "subject": args["subject"],
            "body": args["body"],
            "source_id": source["id"],
            "source_approved": source["approved"],
            "allowlisted": args["to"] in world["allowlist"],
        }
    return dict(args)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the email-desk LangGraph.")
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    args = parser.parse_args(argv)
    from apps.claude_skills.runner import format_report

    print(format_report(run_prompts(args.prompts)))


if __name__ == "__main__":
    main()
