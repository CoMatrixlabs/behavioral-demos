"""LangChain tools for the ops bridge. Each one calls the shared simulator."""

from __future__ import annotations

from langchain_core.tools import tool

from corpus.world import execute


@tool
def read_metrics(
    checkout_error_rate: float,
    baseline_error_rate: float,
    change_window: bool,
    evidence_ready: bool,
    last_deploy: str,
    correlation: str,
) -> dict:
    """Read the checkout incident snapshot. Does not open a change window."""
    world = {
        "checkout_error_rate": checkout_error_rate,
        "baseline_error_rate": baseline_error_rate,
        "change_window": change_window,
        "evidence_ready": evidence_ready,
        "last_deploy": last_deploy,
        "correlation": correlation,
    }
    _, result = execute("read_metrics", {}, world)
    return result


@tool
def deploy(service: str, change_window: bool) -> dict:
    """Deploy a service. The simulator refuses when change_window is false."""
    _, result = execute("deploy", {"service": service}, {"change_window": change_window})
    return result


@tool
def publish_status(message: str, asserts_cause: bool, evidence_ready: bool) -> dict:
    """Publish a status line. A named cause is refused when evidence is not ready."""
    _, result = execute(
        "publish_status",
        {"message": message, "asserts_cause": asserts_cause},
        {"evidence_ready": evidence_ready},
    )
    return result


TOOLS = {
    "read_metrics": read_metrics,
    "deploy": deploy,
    "publish_status": publish_status,
}


def bind_args(name: str, args: dict, world: dict) -> dict:
    if name == "read_metrics":
        return {
            "checkout_error_rate": world["checkout_error_rate"],
            "baseline_error_rate": world["baseline_error_rate"],
            "change_window": world["change_window"],
            "evidence_ready": world["evidence_ready"],
            "last_deploy": world["last_deploy"],
            "correlation": world["correlation"],
        }
    if name == "deploy":
        return {"service": args["service"], "change_window": world["change_window"]}
    if name == "publish_status":
        return {
            "message": args["message"],
            "asserts_cause": args["asserts_cause"],
            "evidence_ready": world["evidence_ready"],
        }
    raise KeyError(name)
