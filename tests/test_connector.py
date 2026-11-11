"""The connector: spec checks, the rule check, the background build → deploy, stop, and the pages' JSON, over real MCP
JSON-RPC where it matters. Build and deploy are fakes: no Archil, no GCP."""

import json
import threading

import pytest
from starlette.testclient import TestClient

import builder
import connector
from registry import MemoryStore, Registry
from service import Service

SECRET = "s" * 40
HOST = "golden-sandbox-abc123-uw.a.run.app"
HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json", "host": HOST}

GOOD = dict(
    ask="I need to track which laptops are lent to whom",
    title="Loan tracker",
    for_whom="The office manager tracks lent equipment so nothing goes missing",
    screens="One page: a lend form and a table of open loans with a Returned button",
    data="Loans: item, borrower, due date, returned yes/no",
    done_when=["Adding a loan shows it in the table", "Pressing Returned removes it from the table"],
    out_of_scope="Sign-in, email reminders",
)


class Fakes:
    def __init__(self):
        self.built, self.deployed, self.cleared = [], [], []
        self.build_result = "built"
        self.deploy_error = None
        self.gate = None  # a threading.Event to hold builds mid-way

    def build(self, who, app, spec, on_step=None):
        if self.gate:
            self.gate.wait(5)
        self.built.append((who, app, spec))
        on_step and on_step("Claude Code is building")
        r = builder.BuildResult(status=self.build_result, seconds=90)
        if self.build_result == "built":
            r.source = f"/tmp/{app}.tgz"
        else:
            r.reason = "its own checks failed: CHECK x" if self.build_result == "failed" else "Sends data to Dropbox"
        return r

    def deploy(self, src, slot):
        if self.deploy_error:
            raise self.deploy_error
        self.deployed.append((src, slot))
        return f"https://{slot}.example"

    def clear(self, slot):
        self.cleared.append(slot)


@pytest.fixture
def fx():
    f = Fakes()
    svc = Service(Registry(MemoryStore()), build=f.build, deploy=f.deploy, clear=f.clear)
    f.svc = svc
    connector.set_service(svc)
    yield f
    connector.set_service(None)


def drain(svc):
    svc.pool.shutdown(wait=True)
    from concurrent.futures import ThreadPoolExecutor

    svc.pool = ThreadPoolExecutor(max_workers=2)


# --- spec checks ------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("field", ["title", "for_whom", "screens", "data", "out_of_scope", "ask"])
@pytest.mark.parametrize("value", ["", "-", ".", "n/a", "TBD", "  ", "stuff"])
def test_vague_part_is_refused_with_what_is_missing(fx, field, value):
    e, missing = fx.svc.request("Dana", {**GOOD, field: value})
    assert e is None and missing
    assert not fx.svc.reg.all()


@pytest.mark.parametrize("done", [[], ["Adding a loan shows it"], ["Adding a loan shows it", "n/a"], ["-", "."]])
def test_needs_two_concrete_done_checks(fx, done):
    e, missing = fx.svc.request("Dana", {**GOOD, "done_when": done})
    assert e is None and any("done when" in m for m in missing)


def test_good_spec_builds_and_goes_live(fx):
    e, missing = fx.svc.request("Dana", GOOD)
    assert missing is None  # (the fake build may already be done: status is read after drain)
    drain(fx.svc)
    a = fx.svc.reg.get(e.id)
    assert a.status == "live" and a.url == "https://app-01.example" and a.slot == "app-01"
    assert a.build_seconds == 90 and a.sandbox == "emp-dana"
    assert "**Done when:**" in fx.built[0][2] and "Pressing Returned" in fx.built[0][2]


# --- the rule ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "where",
    ["send a copy to my personal Dropbox", "back it up to dropbox", "email it to my personal gmail", "post each loan to a webhook", "save to Google Drive"],
)
def test_outside_data_is_refused_before_any_build(fx, where):
    e, missing = fx.svc.request("Sam", {**GOOD, "data": GOOD["data"] + ", and " + where})
    assert missing is None and e.status == "refused" and "stays inside the company" in e.rule
    drain(fx.svc)
    assert fx.built == [] and fx.deployed == []


def test_rule_does_not_refuse_ordinary_words(fx):
    e, _ = fx.svc.request("Sam", {**GOOD, "data": "Drops in stock levels, box counts, drive times for deliveries"})
    assert e.status != "refused"


def test_refusal_in_the_sandbox_shows_as_refused(fx):
    fx.build_result = "refused"
    e, _ = fx.svc.request("Sam", GOOD)
    drain(fx.svc)
    a = fx.svc.reg.get(e.id)
    assert a.status == "refused" and a.rule == "Sends data to Dropbox" and fx.deployed == []


# --- failures are never silent ----------------------------------------------------------------------------------------
def test_failed_build_shows_reason(fx):
    fx.build_result = "failed"
    e, _ = fx.svc.request("Dana", GOOD)
    drain(fx.svc)
    a = fx.svc.reg.get(e.id)
    assert a.status == "failed" and "checks failed" in a.reason and fx.deployed == []


def test_failed_deploy_shows_reason(fx):
    fx.deploy_error = RuntimeError("cloud build failure: denied")
    e, _ = fx.svc.request("Dana", GOOD)
    drain(fx.svc)
    a = fx.svc.reg.get(e.id)
    assert a.status == "failed" and "denied" in a.reason


def test_build_that_raises_shows_failed(fx):
    def boom(*a, **k):
        raise RuntimeError("archil down")

    fx.svc._build = boom
    e, _ = fx.svc.request("Dana", GOOD)
    drain(fx.svc)
    assert fx.svc.reg.get(e.id).status == "failed"


def test_all_slots_taken_fails_with_reason(fx):
    for i in range(10):
        fx.svc.request(f"P{i}", {**GOOD, "title": f"App number {i}"})
    drain(fx.svc)
    e, _ = fx.svc.request("Late", GOOD)
    drain(fx.svc)
    a = fx.svc.reg.get(e.id)
    assert a.status == "failed" and "slots" in a.reason
    assert sorted(s for _, s in fx.deployed) == [f"app-{i:02d}" for i in range(1, 11)]


# --- two at once, changes, stop -------------------------------------------------------------------------------------
def test_two_requests_at_once_get_different_slots(fx):
    fx.gate = threading.Event()
    a, _ = fx.svc.request("Dana", GOOD)
    b, _ = fx.svc.request("Lee", GOOD)
    fx.gate.set()
    drain(fx.svc)
    slots = {fx.svc.reg.get(a.id).slot, fx.svc.reg.get(b.id).slot}
    assert slots == {"app-01", "app-02"}


def test_same_title_twice_gets_its_own_folder(fx):
    a, _ = fx.svc.request("Dana", GOOD)
    b, _ = fx.svc.request("Dana", GOOD)
    assert a.app == "loan-tracker" and b.app == "loan-tracker-2"


def test_change_keeps_old_version_live_until_new_one_is(fx):
    first, _ = fx.svc.request("Dana", GOOD)
    drain(fx.svc)
    fx.gate = threading.Event()
    change, missing = fx.svc.request("Dana", {**GOOD, "ask": "add a CSV export to my tracker"}, change_of="loan-tracker")
    assert missing is None and change.app == "loan-tracker" and change.slot == "app-01" and change.changes == 1
    assert fx.svc.reg.get(first.id).status == "live"  # still up while the change builds
    fx.gate.set()
    drain(fx.svc)
    assert fx.svc.reg.get(change.id).status == "live" and fx.svc.reg.get(change.id).slot == "app-01"
    assert fx.svc.reg.get(first.id).status == "stopped"
    assert "## Change requested" in fx.built[-1][2] and "add a CSV export" in fx.built[-1][2]


def test_change_of_unknown_app_is_refused(fx):
    e, missing = fx.svc.request("Dana", GOOD, change_of="nope")
    assert e is None and "my_apps" in missing[0]


def test_stop_clears_slot_and_frees_it(fx):
    e, _ = fx.svc.request("Dana", GOOD)
    drain(fx.svc)
    got, err = fx.svc.stop("Dana", "loan-tracker")
    drain(fx.svc)
    assert err == "" and fx.cleared == ["app-01"] and fx.svc.reg.get(e.id).status == "stopped"
    n, _ = fx.svc.request("Lee", GOOD)
    drain(fx.svc)
    assert fx.svc.reg.get(n.id).slot == "app-01"


def test_stop_someone_elses_or_not_live(fx):
    fx.svc.request("Dana", GOOD)
    drain(fx.svc)
    assert fx.svc.stop("Lee", "loan-tracker")[1]
    fx.build_result = "failed"
    fx.svc.request("Lee", GOOD)
    drain(fx.svc)
    assert "isn't live" in fx.svc.stop("Lee", "loan-tracker")[1]
    assert fx.cleared == []


def test_registry_survives_a_restart(fx):
    store = MemoryStore()
    r = Registry(store)
    a = r.add(app="x", title="X", who="Dana", spec="s", ask="a")
    r.update(a.id, status="live", slot="app-03")
    again = Registry(MemoryStore(store.get()))
    assert again.get(a.id).status == "live" and again.free_slot() == "app-01"
    again.update(a.id, status="live")
    assert "app-03" not in [again.free_slot()]


# --- over MCP and the pages ------------------------------------------------------------------------------------------
@pytest.fixture
def client(fx, monkeypatch):
    monkeypatch.setenv("CONNECTOR_PATH_SECRET", SECRET)
    with TestClient(connector.build_app(), base_url=f"https://{HOST}") as c:
        yield c


def rpc(client, method, params=None, path=f"/mcp/{SECRET}"):
    return client.post(path, headers=HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})


def body(r):
    if r.headers.get("content-type", "").startswith("text/event-stream"):
        return json.loads([line[5:].strip() for line in r.text.splitlines() if line.startswith("data:")][-1])
    return r.json()


def call(client, name, args):
    r = rpc(client, "tools/call", {"name": name, "arguments": args})
    assert r.status_code == 200, r.text
    return body(r)["result"]["content"][0]["text"]


def test_health(client):
    assert client.get("/health", headers={"host": HOST}).json() == {"ok": True}


def test_lists_three_tools_and_instructions(client):
    r = rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}})
    assert "product owner" in body(r)["result"]["instructions"]
    names = sorted(t["name"] for t in body(rpc(client, "tools/list"))["result"]["tools"])
    assert names == ["my_apps", "request_app", "stop_app"]


def test_request_app_over_mcp(client, fx):
    text = call(client, "request_app", {"who": "Dana", **GOOD})
    assert "Building 'loan-tracker' for Dana" in text and "/status/" in text
    drain(fx.svc)
    mine = call(client, "my_apps", {"who": "dana"})
    assert "live" in mine and "https://app-01.example" in mine
    assert "Stopped" in call(client, "stop_app", {"who": "Dana", "app": "loan-tracker"})


def test_vague_request_over_mcp_says_what_is_missing(client, fx):
    text = call(client, "request_app", {"who": "Dana", **GOOD, "screens": "n/a", "done_when": ["x"]})
    assert text.startswith("Not started") and "main screens" in text and "done when" in text


def test_refused_over_mcp(client, fx):
    text = call(client, "request_app", {"who": "Sam", **GOOD, "data": "send it to my personal Dropbox"})
    assert text.startswith("Refused") and "Dropbox" in text


@pytest.mark.parametrize("path", ["/mcp", "/mcp/", f"/mcp/{SECRET[:-1]}", "/mcp/wrong"])
def test_wrong_mcp_path_is_not_found(client, path):
    assert rpc(client, "tools/list", path=path).status_code == 404


def test_status_api(client, fx):
    e, _ = fx.svc.request("Dana", GOOD)
    drain(fx.svc)
    d = client.get(f"/api/status/{e.id}").json()
    assert d["status"] == "live" and d["url"] and "spec" not in d and d["minutes"] == 1.5
    assert client.get("/api/status/nope").status_code == 404


def test_admin_api_needs_key_and_groups_people(client, fx):
    fx.svc.request("Dana", GOOD)
    fx.svc.request("Sam", {**GOOD, "data": "to my personal Dropbox"})
    drain(fx.svc)
    assert client.get("/api/admin/wrong").status_code == 404
    assert client.get("/admin/wrong").status_code == 404
    d = client.get(f"/api/admin/{connector.admin_key()}").json()
    assert {p["who"] for p in d["people"]} == {"Dana", "Sam"}
    assert len(d["refused"]) == 1 and "Dropbox" in d["refused"][0]["ask"] + d["refused"][0]["rule"]


@pytest.mark.parametrize("value", [None, "", "short", "a" * 31, "a" * 31 + "/", "a" * 40 + " "])
def test_refuses_to_start_without_a_good_secret(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("CONNECTOR_PATH_SECRET", raising=False)
    else:
        monkeypatch.setenv("CONNECTOR_PATH_SECRET", value)
    with pytest.raises(SystemExit):
        connector.build_app()


def test_replaced_version_status_points_to_the_live_one(client, fx):
    first, _ = fx.svc.request("Dana", GOOD)
    drain(fx.svc)
    change, _ = fx.svc.request("Dana", {**GOOD, "ask": "add a CSV export please"}, change_of="loan-tracker")
    drain(fx.svc)
    d = client.get(f"/api/status/{first.id}").json()
    assert d["status"] == "stopped" and d["current_url"] == "https://app-01.example"
    assert client.get(f"/api/status/{change.id}").json()["current_url"] == ""


def test_pages_serve_the_built_page(client, fx):
    e, _ = fx.svc.request("Dana", GOOD)
    r = client.get(f"/status/{e.id}")
    assert r.status_code == 200 and "<div id=\"root\">" in r.text
    assert client.get(f"/admin/{connector.admin_key()}").status_code == 200
    asset = next(p for p in (connector.WEB / "assets").iterdir() if p.suffix == ".js")
    assert client.get(f"/assets/{asset.name}").status_code == 200
    assert client.get("/assets/..%2F..%2Fconnector.py").status_code == 404
