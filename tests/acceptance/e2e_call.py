"""qa acceptance (arc-eng/hq#782 part 8): call one connector tool on the DEPLOYED connector, as Claude would.
Prints the tool's answer. Never prints the secret path.
  uv run --env-file <.env> python tests/acceptance/e2e_call.py list
  uv run --env-file <.env> python tests/acceptance/e2e_call.py <tool> '<json args>'"""

import asyncio
import json
import os
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

BASE = os.environ.get("PUBLIC_URL", "https://golden-sandbox-42301619537.us-west1.run.app").rstrip("/")
URL = f"{BASE}/mcp/{os.environ['CONNECTOR_PATH_SECRET']}"


async def main() -> None:
    async with streamable_http_client(URL) as (r, w, *_):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if sys.argv[1] == "list":
                print([t.name for t in (await s.list_tools()).tools])
                return
            res = await s.call_tool(sys.argv[1], json.loads(sys.argv[2]))
            print("\n".join(getattr(c, "text", "") for c in res.content))


asyncio.run(main())
