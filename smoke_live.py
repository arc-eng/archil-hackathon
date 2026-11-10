"""One real run of the tools against Archil, with a scripted model (no LLM key needed). Uses ~3 sandboxes for a
couple of minutes, then deletes them and checks none are left.

    uv run smoke_live.py
"""

from __future__ import annotations

import asyncio
import json
import time

import archil
from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from archil_tools import ArchilDeps, archil_toolset, cleanup


def script():
    def base(r):
        return next(p.content["sandbox_id"] for p in r if p.tool_name == "create_sandbox")

    def a_fork(r):
        table = next(p.content for p in r if p.tool_name == "fork_and_run")
        return next(j.sandbox_id for j in table if j.ok)

    steps = [
        ("create_sandbox", lambda r: {"name": "smoke-base"}),
        ("run", lambda r: {"sandbox_id": base(r), "command": "python -V && pip install -q 'packaging==23.2' && python -c 'import packaging; print(packaging.__version__)'", "timeout_seconds": 240}),
        ("write_file", lambda r: {"sandbox_id": base(r), "path": "/tmp/setup.txt", "content": "set up once, in the base"}),
        ("fork_and_run", lambda r: {"sandbox_id": base(r), "timeout_seconds": 240, "jobs": [
            {"name": "smoke-packaging-24", "command": "pip install -q 'packaging==24.2' && python -c 'import packaging; print(packaging.__version__)' && cat /tmp/setup.txt"},
            {"name": "smoke-bad", "command": "python -c 'import not_a_module'"},
        ]}),
        ("read_file", lambda r: {"sandbox_id": a_fork(r), "path": "/tmp/setup.txt"}),
        ("list_sandboxes", lambda r: {}),
    ]

    def fn(messages, info):
        r = [p for m in messages for p in getattr(m, "parts", []) if isinstance(p, ToolReturnPart)]
        if not steps:
            return ModelResponse(parts=[TextPart("smoke done")])
        tool, args = steps.pop(0)
        return ModelResponse(parts=[ToolCallPart(tool, json.dumps(args(r)))])

    return FunctionModel(fn)


async def main() -> int:
    before = {s.id for s in archil.list_sandboxes()}
    deps = ArchilDeps(max_sandboxes=4)
    t0 = time.time()
    try:
        result = await Agent(script(), deps_type=ArchilDeps, toolsets=[archil_toolset]).run("smoke", deps=deps)
        for m in result.all_messages():
            for p in getattr(m, "parts", []):
                if isinstance(p, ToolReturnPart):
                    c = p.content
                    print(f"\n{p.tool_name} →", c if isinstance(c, (str, dict, list)) and not (isinstance(c, list) and c and hasattr(c[0], "model_dump")) else [x.model_dump() for x in c] if isinstance(c, list) else c.model_dump())
    finally:
        left = await cleanup(deps)
        print("\ncleanup left:", left or "nothing", f"· {round(time.time() - t0)}s total")
    after = {s.id for s in archil.list_sandboxes()}
    print("sandboxes before:", len(before), "after:", len(after), "new left over:", after - before or "none")
    return 0 if not (after - before) else 1


if __name__ == "__main__":
    load_dotenv()
    raise SystemExit(asyncio.run(main()))
