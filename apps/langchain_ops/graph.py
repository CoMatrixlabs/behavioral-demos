"""Ops bridge as a LangGraph. Lead, operator, then comms. Tools are the simulator."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from apps.langchain_ops.tools import TOOLS, bind_args
from corpus.load import load_scenario
from corpus.scripted import OPS_NODE, make_turn, ops_turn
from corpus.spec import load_spec_dir
from corpus.trace import blank_trace, finish, prompts_for

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPTS = ROOT / "apps" / "langchain_ops" / "prompts"


class BridgeState(TypedDict):
    assigns: dict
    prompts: dict
    live: bool
    world: dict
    messages: list
    decisions: list
    tool_calls: list
    turn_index: int


def build_graph() -> StateGraph:
    graph = StateGraph(BridgeState)
    graph.add_node("lead", _node("lead"))
    graph.add_node("operator", _node("operator"))
    graph.add_node("comms", _node("comms"))
    graph.set_entry_point("lead")
    graph.add_edge("lead", "operator")
    graph.add_edge("operator", "comms")
    graph.add_edge("comms", END)
    return graph


def compile_app():
    return build_graph().compile()


def run(
    assigns: dict[str, list[str]] | None = None,
    name: str | None = None,
    prompts: dict[str, str] | None = None,
    live: bool = False,
) -> dict:
    scenario = load_scenario("ops_bridge")
    assigns = {role: list((assigns or {}).get(role, [])) for role in scenario["order"]}
    rendered = prompts or prompts_for(scenario, assigns)
    trace = blank_trace(scenario, assigns, name)
    app = compile_app()
    final = app.invoke(
        {
            "assigns": assigns,
            "prompts": rendered,
            "live": live,
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
    def run_node(state: BridgeState) -> dict:
        operators = state["assigns"].get(role, [])
        if state["live"]:
            turn = _live_turn(role, state["prompts"][role], state["messages"])
        else:
            turn = ops_turn(role, operators, state["messages"])
        tool_calls = list(state["tool_calls"])
        for name, args in turn["tool_requests"]:
            recorded = bind_args(name, args, state["world"])
            result = TOOLS[name].invoke(recorded)
            tool_calls.append(
                {"role": role, "name": name, "args": recorded, "result": result}
            )
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


def _live_turn(role: str, prompt: str, messages: list[dict]) -> dict:
    data = _complete(prompt, json.dumps({"peers": messages}))
    option = data["decision"]
    reason = data.get("reason", "")
    content = data.get("message_to_peers") or reason
    requests = _tools_for(role, option, content)
    for name in data.get("tools") or []:
        if name == "deploy" and not any(req[0] == "deploy" for req in requests):
            requests.append(("deploy", {"service": "payments-api"}))
    return make_turn(role, OPS_NODE[role], option, reason, content, requests)


def _tools_for(role: str, option: str, content: str) -> list[tuple[str, dict]]:
    if role == "lead":
        return [("read_metrics", {})]
    if role == "operator":
        if option == "deploy_on_lead_message":
            return [("deploy", {"service": "payments-api"})]
        return []
    asserts = option == "publish_root_cause"
    message = content or ("Root cause: payments-api deploy." if asserts else "Checkout is degraded.")
    return [("publish_status", {"message": message, "asserts_cause": asserts})]


def _complete(system: str, user: str) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Set ANTHROPIC_API_KEY to run --live")
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage

    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    chat = ChatAnthropic(model=model, api_key=key, max_tokens=400)
    response = chat.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    text = response.content if isinstance(response.content, str) else response.content[0]["text"]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"Model did not return JSON: {text[:200]}")
    return json.loads(text[start : end + 1])


def format_report(trace: dict) -> str:
    from apps.claude_skills.runner import format_report as _format

    return _format(trace)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the ops-bridge LangGraph.")
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    print(format_report(run_prompts(args.prompts, live=args.live)))


if __name__ == "__main__":
    main()
