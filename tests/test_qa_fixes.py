"""qa's findings on archil-hackathon#2: a secret in the app's files stops the deploy; a stopping app keeps its slot."""

import threading
from types import SimpleNamespace

import pytest

import builder
from registry import MemoryStore, Registry
from service import Service
from tests.test_connector import GOOD, Fakes, drain

TOKEN = "sk-ant-oat01-REALTOKENVALUE"


class FakeSandbox:
    """Answers builder's commands; `grep_out` is what the secret search prints."""

    def __init__(self, grep_out="CLEAN\n"):
        self.grep_out = grep_out
        self.cmds = []
        self.files = SimpleNamespace(upload_file=lambda *a, **k: None, download_file=lambda *a, **k: None)

    def exec(self, cmd, env=None, timeout_seconds=None):
        self.cmds.append((cmd, env))
        out = ""
        if "grep -rqF" in cmd:
            out = self.grep_out
        elif "check.sh" in cmd:
            out = "ALL CHECKS PASSED\n"
        return SimpleNamespace(exit_code=0, stdout=out, stderr="")


@pytest.fixture
def fake_sb(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", TOKEN)
    monkeypatch.setattr(builder, "BUILDS_DIR", tmp_path)
    monkeypatch.setattr(builder, "_stop", lambda sb: None)
    import golden

    monkeypatch.setattr(golden, "_default", golden.Store())
    holder = {}

    def make(grep_out):
        sb = FakeSandbox(grep_out)
        monkeypatch.setattr(builder, "employee_sandbox", lambda who: (sb, False))
        holder["sb"] = sb
        return sb

    return make


@pytest.mark.parametrize("grep_out", ["FOUND\n", "", "grep: error\n"])
def test_secret_or_bad_read_stops_the_build_before_packing(fake_sb, grep_out):
    sb = fake_sb(grep_out)
    r = builder.build("Dana", "app", "# spec")
    assert r.status == "failed" and "secret" in r.reason and r.source == ""
    assert not any("tar czf" in c for c, _ in sb.cmds)


def test_clean_app_is_packed(fake_sb):
    sb = fake_sb("CLEAN\n")
    r = builder.build("Dana", "app", "# spec")
    assert r.status == "built" and any("tar czf" in c for c, _ in sb.cmds)


def test_token_is_never_on_a_command_line(fake_sb):
    sb = fake_sb("CLEAN\n")
    builder.build("Dana", "app", "# spec")
    assert all(TOKEN not in c for c, _ in sb.cmds)
    grep_env = next(env for c, env in sb.cmds if "grep -rqF" in c)
    assert grep_env == {"T": TOKEN}
    grep_cmd = next(c for c, _ in sb.cmds if "grep -rqF" in c)
    assert '"$T"' in grep_cmd and "sk-ant-" in grep_cmd


# --- slots ---------------------------------------------------------------------------------------------------------
@pytest.fixture
def svc():
    f = Fakes()
    s = Service(Registry(MemoryStore()), build=f.build, deploy=f.deploy, clear=f.clear)
    s.f = f
    return s


def test_stopping_app_keeps_its_slot_until_cleared(svc):
    gate = threading.Event()
    order = []
    svc._clear = lambda slot: (gate.wait(5), order.append(("clear", slot)))
    real_deploy = svc._deploy
    svc._deploy = lambda src, slot: (order.append(("deploy", slot)), real_deploy(src, slot))[1]
    a, _ = svc.request("Dana", GOOD)
    drain(svc)
    svc.stop("Dana", "loan-tracker")
    assert svc.reg.get(a.id).status == "stopping" and svc.reg.free_slot() == "app-02"
    b, _ = svc.request("Lee", GOOD)
    gate.set()
    drain(svc)
    assert svc.reg.get(a.id).status == "stopped"
    bslot = svc.reg.get(b.id).slot
    # the new app is never in a slot that gets cleared after it was deployed there
    last = max(i for i, x in enumerate(order) if x == ("deploy", bslot))
    assert ("clear", bslot) not in order[last + 1 :], order
    assert svc.reg.get(b.id).status == "live"


def test_failed_clear_keeps_slot_taken(svc):
    def bad_clear(slot):
        raise RuntimeError("denied")

    svc._clear = bad_clear
    a, _ = svc.request("Dana", GOOD)
    drain(svc)
    svc.stop("Dana", "loan-tracker")
    drain(svc)
    e = svc.reg.get(a.id)
    assert e.status == "stopping" and "couldn't clear" in e.reason and svc.reg.free_slot() == "app-02"


def test_building_change_holds_its_slot(svc):
    a, _ = svc.request("Dana", GOOD)
    drain(svc)
    svc.f.gate = threading.Event()
    c, _ = svc.request("Dana", {**GOOD, "ask": "add a CSV export please"}, change_of="loan-tracker")
    svc.reg.update(a.id, status="stopped")  # the old version goes away while the change builds
    assert svc.reg.free_slot() == "app-02"  # app-01 is still the change's
    svc.f.gate.set()
    drain(svc)
    assert svc.reg.get(c.id).slot == "app-01"


# --- purge (test entries before the demo) --------------------------------------------------------------------------
def test_purge_clears_live_slots_and_removes_only_that_person(svc):
    a, _ = svc.request("Test Run", GOOD)
    b, _ = svc.request("Dana", GOOD)
    drain(svc)
    deleted = []
    slots = svc.purge("test run", deleted.append)
    assert slots == [svc.f.deployed[0][1]] and svc.f.cleared == slots
    assert svc.reg.get(a.id) is None and svc.reg.get(b.id) and deleted == ["test run"]
    assert svc.reg.free_slot() == slots[0]


def test_purge_refuses_while_building_and_keeps_everything_on_a_failed_clear(svc):
    svc.f.gate = threading.Event()
    a, _ = svc.request("Test Run", GOOD)
    with pytest.raises(ValueError):
        svc.purge("Test Run")
    svc.f.gate.set()
    drain(svc)

    def bad(slot):
        raise RuntimeError("denied")

    svc._clear = bad
    with pytest.raises(RuntimeError):
        svc.purge("Test Run")
    assert svc.reg.get(a.id).status == "live"
