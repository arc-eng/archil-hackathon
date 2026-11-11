"""The golden-sandbox connector: the MCP server Marco adds to his Claude app (arc-eng/hq#781).

Claude acts as the product owner: it interviews the person, plays the spec back, then calls `request_app`. Each
person gets their own Archil sandbox (copied once from the golden sandbox); the build runs there in the background;
the company's builder deploys the result to its own Cloud Run app and the link lands in the registry.

Env (Cloud Run sets these; locally `.env`):
  PORT                     port to listen on (Cloud Run sets it; default 8080)
  CONNECTOR_PATH_SECRET    the secret part of the address: MCP is served at /mcp/<secret>. Required, 32+ chars.
                           The service has no sign-in in front, so this is the guard. Never post it on GitHub.
  ARCHIL_API_KEY           Archil key (the archil SDK reads it from the environment)
  ARCHIL_REGION            Archil region (same)
  CLAUDE_CODE_OAUTH_TOKEN  Marco's Claude Code token, passed into sandbox commands' env, never written to disk
  PUBLIC_URL               optional: this service's public address, for status links (default: the Cloud Run one)

Pages: /status/<request id> (one request, public by its random id) and /admin/<admin key> (everything).
`uv run connector.py --admin-path` prints the admin path. Health: GET /health.
"""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

MIN_SECRET = 32
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://golden-sandbox-42301619537.us-west1.run.app").rstrip("/")
WEB = Path(__file__).parent / "web" / "dist"

INSTRUCTIONS = """You help people at this company get small internal apps built, without an engineer. You act as their \
product owner: the builder can't ask follow-up questions, so the spec you hand over must be complete enough to build \
in one go.

Before calling request_app:
1. Ask the person's name if you don't know it.
2. Interview them in a few short questions (two or three rounds at most): who uses the app and for what, the main \
screens or actions, the data it keeps, what "done" looks like, and what is out.
3. Play the spec back in plain words, part by part, and get a yes. Only then call request_app.

To change an app they already have ("add a CSV export to my tracker"), call my_apps first and pass that app's name as \
change_of. When request_app answers, give them the status link: the app's own link appears there (and in my_apps) when \
it's live, usually within a few minutes. Apps can't send company data outside the company (no personal Dropbox, \
personal email or outside webhooks); such requests are refused, so say so plainly."""


def mcp_path() -> str:
    secret = os.environ.get("CONNECTOR_PATH_SECRET", "")
    if len(secret) < MIN_SECRET or not secret.replace("-", "").replace("_", "").isalnum():
        raise SystemExit(f"CONNECTOR_PATH_SECRET must be set: {MIN_SECRET}+ characters, letters, digits, - or _")
    return f"/mcp/{secret}"


def admin_key() -> str:
    return hashlib.sha256((os.environ.get("CONNECTOR_PATH_SECRET", "") + ":admin").encode()).hexdigest()[:24]


server = MCPServer("golden-sandbox", instructions=INSTRUCTIONS)
_service = None


def service():
    """Built on first use, so tests can swap it and the server starts without Archil."""
    global _service
    if _service is None:
        from registry import ArchilStore, Registry
        from service import Service

        _service = Service(Registry(ArchilStore()))
    return _service


def set_service(s) -> None:
    global _service
    _service = s


def status_url(id_: str) -> str:
    return f"{PUBLIC_URL}/status/{id_}"


def _line(a) -> str:
    link = f" · open: {a.url}" if a.url else ""
    why = f" · {a.reason}" if a.status in ("failed", "refused") and a.reason else ""
    return f"- {a.app} ({a.title}): {a.status}{link}{why} · status page: {status_url(a.id)}"


@server.tool()
def request_app(
    who: str,
    ask: str,
    title: str,
    for_whom: str,
    screens: str,
    data: str,
    done_when: list[str],
    out_of_scope: str,
    change_of: str = "",
) -> str:
    """Build a new app (or change one) from a full spec. Call it only after interviewing the person and getting a yes
    on the spec played back to them.

    who: the person's name. ask: their request in their own words. title: a short name for the app.
    for_whom: who uses it and what for. screens: the main screens or actions. data: what it reads and writes.
    done_when: two or more checks you could test ("adding a loan shows it in the table"). out_of_scope: what's out.
    change_of: to change an existing app, its name from my_apps; empty for a new app."""
    spec = dict(ask=ask, title=title, for_whom=for_whom, screens=screens, data=data, done_when=list(done_when or []), out_of_scope=out_of_scope)
    e, missing = service().request(who, spec, change_of=change_of)
    if missing:
        return "Not started: the spec needs " + "; ".join(missing) + ". Ask the person, play the spec back, then call request_app again."
    if e.status == "refused":
        return f"Refused, nothing was built. {e.rule} Tell {e.who} plainly; it's on the admin page. Status: {status_url(e.id)}"
    what = f"Changing '{e.app}'" if change_of else f"Building '{e.app}'"
    return f"{what} for {e.who} in their own sandbox. Status page (flips to live with the app's link): {status_url(e.id)}"


@server.tool()
def my_apps(who: str) -> str:
    """The person's apps with status (building, live, failed, refused, stopped) and links."""
    apps = service().reg.of(who)
    if not apps:
        return f"{who} has no apps yet."
    return f"{who}'s apps ({service().minutes(who)} sandbox minutes so far):\n" + "\n".join(_line(a) for a in apps)


@server.tool()
def stop_app(who: str, app: str) -> str:
    """Take one of the person's apps offline by its name from my_apps. Its code stays in their sandbox."""
    e, err = service().stop(who, app)
    return err or f"Stopped '{app}'. Its link now shows a 'stopped' page; the code stays in {who}'s sandbox."


# --- pages and their JSON -------------------------------------------------------------------------------------------
def _public(a) -> dict:
    d = asdict(a)
    d.pop("spec", None)
    d["minutes"] = round(a.build_seconds / 60, 1)
    return d


@server.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


@server.custom_route("/api/status/{id}", methods=["GET"])
async def api_status(req: Request) -> JSONResponse:
    reg = service().reg
    a = reg.get(req.path_params["id"])
    if not a:
        return JSONResponse({"error": "not found"}, status_code=404)
    d = _public(a)
    # a version replaced by a change points on to the live one, so an old status link never dead-ends
    now = next((x for x in reg.of(a.who) if x.app == a.app and x.status == "live" and x.id != a.id), None)
    d["current_url"] = now.url if now else ""
    return JSONResponse(d)


@server.custom_route("/api/admin/{key}", methods=["GET"])
async def api_admin(req: Request) -> JSONResponse:
    if req.path_params["key"] != admin_key():
        return JSONResponse({"error": "not found"}, status_code=404)
    s = service()
    people: dict[str, dict] = {}
    for a in s.reg.all():
        p = people.setdefault(a.who.strip().lower(), {"who": a.who, "apps": [], "minutes": 0.0})
        p["apps"].append(_public(a))
        p["minutes"] = round(p["minutes"] + a.build_seconds / 60, 1)
    refused = [_public(a) for a in s.reg.all() if a.status == "refused"]
    return JSONResponse({"people": list(people.values()), "refused": refused})


@server.custom_route("/api/admin/{key}/purge", methods=["POST"])
async def api_purge(req: Request) -> JSONResponse:
    """Remove one person's entries and sandbox (test runs, before the demo). Same key as the admin page."""
    if req.path_params["key"] != admin_key():
        return JSONResponse({"error": "not found"}, status_code=404)
    body = (await req.json()) or {}
    who, id_ = str(body.get("who", "")).strip(), str(body.get("id", "")).strip()
    if id_:
        try:
            service().remove_entry(id_)
        except KeyError:
            return JSONResponse({"error": "not found"}, status_code=404)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        return JSONResponse({"removed": id_})
    if not who:
        return JSONResponse({"error": "say who or id"}, status_code=400)
    import asyncio

    import builder

    try:
        slots = await asyncio.to_thread(service().purge, who, builder.delete_employee_sandbox)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)[:300]}, status_code=409)
    return JSONResponse({"removed": who, "cleared": slots})


def _page() -> Response:
    index = WEB / "index.html"
    return FileResponse(index) if index.exists() else Response("page not built", status_code=503)


@server.custom_route("/status/{id}", methods=["GET"])
async def status_page(_: Request) -> Response:
    return _page()


@server.custom_route("/admin/{key}", methods=["GET"])
async def admin_page(req: Request) -> Response:
    return _page() if req.path_params["key"] == admin_key() else Response("not found", status_code=404)


@server.custom_route("/how", methods=["GET"])
async def how_page(_: Request) -> Response:
    """The architecture slide for the demo: who owns the apps (arc-eng/hq#782)."""
    f = WEB / "how.html"
    return FileResponse(f) if f.exists() else Response("page not built", status_code=503)


@server.custom_route("/assets/{file}", methods=["GET"])
async def assets(req: Request) -> Response:
    f = (WEB / "assets" / req.path_params["file"]).resolve()
    if not str(f).startswith(str((WEB / "assets").resolve())) or not f.is_file():
        return Response("not found", status_code=404)
    return FileResponse(f)


def build_app():
    # host="0.0.0.0": behind Cloud Run the Host header is the public name, so the SDK's localhost-only
    # DNS-rebinding check (on by default for 127.0.0.1) would refuse every real call.
    return server.streamable_http_app(streamable_http_path=mcp_path(), stateless_http=True, host="0.0.0.0")


def main() -> None:
    import uvicorn

    load_dotenv()
    if "--admin-path" in sys.argv:
        mcp_path()
        print(f"/admin/{admin_key()}")
        return
    try:
        app = build_app()
    except SystemExit as e:
        print(e, file=sys.stderr)
        raise SystemExit(2) from None
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    main()
