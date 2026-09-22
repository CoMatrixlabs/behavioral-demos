"""Run the control genomes and the featured bad genomes."""

from __future__ import annotations

from pathlib import Path

from apps.claude_skills.runner import format_report, run_skills
from apps.email_desk.graph import run_prompts as run_email
from apps.langchain_ops.graph import run_prompts

ROOT = Path(__file__).resolve().parent


def main() -> None:
    runs = [
        run_skills(ROOT / "apps" / "claude_skills" / "skills"),
        run_skills(ROOT / "apps" / "claude_skills" / "genomes" / "narrative_peer"),
        run_prompts(ROOT / "apps" / "langchain_ops" / "prompts"),
        run_prompts(ROOT / "apps" / "langchain_ops" / "genomes" / "time_to_green"),
        run_email(ROOT / "apps" / "email_desk" / "prompts"),
        run_email(ROOT / "apps" / "email_desk" / "genomes" / "inbox_send"),
    ]
    for trace in runs:
        print(format_report(trace))
        print()


if __name__ == "__main__":
    main()
