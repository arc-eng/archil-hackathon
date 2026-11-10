"""A Pydantic AI agent that works in Archil sandboxes (archil_tools.py).

    uv run agent.py "Set up a python:3.12 sandbox with requests installed, then check which of requests 2.31 and 2.32 pass `python -c 'import requests'`"
    uv run agent.py --keep "..."    # leave the sandboxes up afterwards (Archil still stops them after 30 min)

The model comes from ARCHIL_AGENT_MODEL (any Pydantic AI model string), default anthropic:claude-sonnet-5-5, with its
key from the provider's usual variable (ANTHROPIC_API_KEY, OPENAI_API_KEY, ...) in .env. ARCHIL_API_KEY too.
"""

from __future__ import annotations

import argparse
import asyncio
import os

from dotenv import load_dotenv
from pydantic_ai import Agent

from archil_tools import ArchilDeps, archil_toolset, cleanup

DEFAULT_MODEL = "anthropic:claude-sonnet-5-5"

INSTRUCTIONS = """\
You get work done in Archil sandboxes: fast microVMs you can fork, so every fork starts from the same warm state.

How to work:
1. Create one sandbox and set it up once (install, clone, build). Check the setup works with one quick command.
2. For variants (versions, upgrades, approaches), call fork_and_run on that warm sandbox with one job per variant,
   instead of setting each one up again. Each job's command changes one thing and runs the check.
3. Read failures with run / read_file in that fork if you need the reason.
4. Delete sandboxes you're done with. Sandbox time is scarce: no idle sandboxes, no repeated setup.
5. Finish with a short markdown table: variant, result (pass/fail), time, and the key error line for failures.
Never invent results: report only what a command returned.
"""


def build_agent(model: str | None = None) -> Agent[ArchilDeps, str]:
    return Agent(model or os.environ.get("ARCHIL_AGENT_MODEL", DEFAULT_MODEL), deps_type=ArchilDeps, toolsets=[archil_toolset], instructions=INSTRUCTIONS)


async def main(task: str, keep: bool) -> int:
    deps = ArchilDeps()
    agent = build_agent()
    try:
        result = await agent.run(task, deps=deps)
        print("\n" + result.output)
        return 0
    finally:
        if keep:
            print(f"\nkept: {', '.join(deps.created) or 'none'} (Archil stops them after {deps.ttl_seconds // 60} min)")
        else:
            left = await cleanup(deps)
            if left:
                print("\ncouldn't delete:", *left, sep="\n  ")


if __name__ == "__main__":
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("task")
    p.add_argument("--keep", action="store_true", help="leave the sandboxes up afterwards")
    a = p.parse_args()
    raise SystemExit(asyncio.run(main(a.task, a.keep)))
