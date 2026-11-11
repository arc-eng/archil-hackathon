"""The golden-sandbox connector: the MCP server Marco adds to his Claude app (arc-eng/hq#781).

Tonight's entry point only. The three app tools answer "not built yet" until the build at 6 pm fills them in.

Env (Cloud Run sets these; locally `.env`):
  PORT                     port to listen on (Cloud Run sets it; default 8080)
  CONNECTOR_PATH_SECRET    the secret part of the address: MCP is served at /mcp/<secret>. Required, 32+ chars.
                           The service has no sign-in in front, so this is the guard. Never post it on GitHub.
  ARCHIL_API_KEY           Archil key (the archil SDK reads it from the environment)
  ARCHIL_REGION            Archil region (same)
  CLAUDE_CODE_OAUTH_TOKEN  Marco's Claude Code token, passed into sandbox commands' env, never written to disk

Run: `uv run connector.py`. Health: GET /health (no secret, says nothing about the setup).
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse

MIN_SECRET = 32
NOT_BUILT = "Not built yet: the app builder goes in tonight. Nothing was started and no sandbox time was used."


def mcp_path() -> str:
    secret = os.environ.get("CONNECTOR_PATH_SECRET", "")
    if len(secret) < MIN_SECRET or not secret.replace("-", "").replace("_", "").isalnum():
        raise SystemExit(f"CONNECTOR_PATH_SECRET must be set: {MIN_SECRET}+ characters, letters, digits, - or _")
    return f"/mcp/{secret}"


server = MCPServer(
    "golden-sandbox",
    instructions="Builds small apps on request in a fork of the company's golden sandbox and serves each at a link.",
)


@server.tool()
def request_app(what: str, who: str) -> str:
    """Ask for a new app. `what`: the app in plain words ("an app that ..."). `who`: the person asking."""
    return NOT_BUILT


@server.tool()
def my_apps(who: str) -> str:
    """List the apps this person asked for, with status and link."""
    return NOT_BUILT


@server.tool()
def stop_app(name: str) -> str:
    """Stop an app by its name and free its sandbox."""
    return NOT_BUILT


@server.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


def build_app():
    # host="0.0.0.0": behind Cloud Run the Host header is the public name, so the SDK's localhost-only
    # DNS-rebinding check (on by default for 127.0.0.1) would refuse every real call.
    return server.streamable_http_app(streamable_http_path=mcp_path(), stateless_http=True, host="0.0.0.0")


def main() -> None:
    import uvicorn

    load_dotenv()
    try:
        app = build_app()
    except SystemExit as e:
        print(e, file=sys.stderr)
        raise SystemExit(2) from None
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    main()
