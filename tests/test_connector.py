"""The connector entry point: health, the secret MCP path, and the three app tools over real MCP JSON-RPC."""

import json

import pytest
from starlette.testclient import TestClient

import connector

SECRET = "s" * 40
HOST = "golden-sandbox-abc123-uw.a.run.app"  # what Cloud Run puts in the Host header
HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json", "host": HOST}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CONNECTOR_PATH_SECRET", SECRET)
    with TestClient(connector.build_app(), base_url=f"https://{HOST}") as c:
        yield c


def rpc(client, method, params=None, path=f"/mcp/{SECRET}", id_=1):
    r = client.post(path, headers=HEADERS, json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}})
    return r


def body(r):
    if r.headers.get("content-type", "").startswith("text/event-stream"):
        data = [line[5:].strip() for line in r.text.splitlines() if line.startswith("data:")]
        return json.loads(data[-1])
    return r.json()


INIT = {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}


def test_health(client):
    r = client.get("/health", headers={"host": HOST})
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_initialize_with_a_public_host_header(client):
    r = rpc(client, "initialize", INIT)
    assert r.status_code == 200, r.text
    assert body(r)["result"]["serverInfo"]["name"] == "golden-sandbox"


def test_lists_the_three_app_tools(client):
    r = rpc(client, "tools/list")
    assert r.status_code == 200, r.text
    assert sorted(t["name"] for t in body(r)["result"]["tools"]) == ["my_apps", "request_app", "stop_app"]


@pytest.mark.parametrize(
    "name,args",
    [("request_app", {"what": "an app that tracks invoices", "who": "Dana"}), ("my_apps", {"who": "Dana"}), ("stop_app", {"name": "x"})],
)
def test_tools_answer_not_built_yet(client, name, args):
    r = rpc(client, "tools/call", {"name": name, "arguments": args})
    assert r.status_code == 200, r.text
    result = body(r)["result"]
    assert not result.get("isError")
    assert result["content"][0]["text"] == connector.NOT_BUILT


@pytest.mark.parametrize("path", ["/mcp", "/mcp/", f"/mcp/{SECRET[:-1]}", f"/mcp/{SECRET}x", "/mcp/wrong"])
def test_wrong_path_is_not_found(client, path):
    assert rpc(client, "tools/list", path=path).status_code == 404


@pytest.mark.parametrize("value", [None, "", "short", "a" * 31, "a" * 31 + "/", "a" * 40 + " "])
def test_refuses_to_start_without_a_good_secret(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("CONNECTOR_PATH_SECRET", raising=False)
    else:
        monkeypatch.setenv("CONNECTOR_PATH_SECRET", value)
    with pytest.raises(SystemExit):
        connector.build_app()
