"""Golden image as code: snapshot, publish (pointer moves last), sync at every request, version on the app."""

import io
import tarfile
from types import SimpleNamespace

import pytest

import builder
import golden
from registry import MemoryStore, Registry
from service import Service
from tests.test_connector import GOOD, Fakes, drain


def names(body):
    with tarfile.open(fileobj=io.BytesIO(body)) as t:
        return set(t.getnames())


def test_snapshot_has_rules_skills_template_check_not_setup():
    n = names(golden.snapshot())
    assert {"claude/CLAUDE.md", "template/server.js", "template/public/index.html", "bin/check.sh"} <= n
    assert "setup.sh" not in n and not any(x.endswith(".gitkeep") for x in n)


def test_snapshot_picks_up_a_new_skill(tmp_path):
    src = tmp_path / "g"
    (src / "claude" / "skills" / "brand").mkdir(parents=True)
    (src / "claude" / "CLAUDE.md").write_text("rules")
    (src / "claude" / "skills" / "brand" / "SKILL.md").write_text("green")
    (src / "setup.sh").write_text("x")
    assert names(golden.snapshot(src)) == {"claude/CLAUDE.md", "claude/skills/brand/SKILL.md"}


class Box:
    def __init__(self, name, fail=False):
        self.name, self.fail, self.cmds, self.forks = name, fail, [], []
        self.files = SimpleNamespace(upload_file=lambda *a, **k: None)

    def exec(self, cmd, timeout_seconds=None, env=None):
        self.cmds.append(cmd)
        return SimpleNamespace(exit_code=1 if self.fail else 0, stdout="", stderr="boom" if self.fail else "")

    def fork(self, name):
        b = Box(name, fail=self.fail)
        self.forks.append(b)
        BOXES[name] = b
        return b


BOXES: dict = {}


@pytest.fixture
def fake_archil(monkeypatch):
    BOXES.clear()
    BOXES["golden"] = Box("golden")
    monkeypatch.setattr(builder, "_by_name", lambda n: BOXES.get(n))
    monkeypatch.setattr(builder, "_stop", lambda sb: None)
    monkeypatch.setattr(builder, "_running", lambda sb: sb)
    golden._cache.clear()
    return BOXES


def test_publish_numbers_versions_and_keeps_old_ones(fake_archil):
    st = golden.Store()
    assert st.latest() == 0
    assert golden.publish(st) == 1 and "golden-v1" in fake_archil
    assert golden.publish(st) == 2 and "golden-v2" in fake_archil
    assert st.latest() == 2 and st.get("golden/v1.tgz") and st.get("golden/v2.tgz")
    assert fake_archil["golden-v1"].forks[0].name == "golden-v2"  # v2 is a copy of v1
    assert "echo 2 > /home/node/.golden-version" in fake_archil["golden-v2"].cmds[-1]


def test_failed_publish_leaves_latest_alone(fake_archil):
    st = golden.Store()
    golden.publish(st)
    fake_archil["golden-v1"].fail = True
    with pytest.raises(RuntimeError):
        golden.publish(st)
    assert st.latest() == 1 and st.get("golden/v2.tgz") is None


def test_sync_installs_latest_and_says_which(fake_archil):
    st = golden.Store()
    sb = Box("emp-dana")
    assert golden.sync(sb, st) == 0  # nothing published: the deployed folder, as v0
    golden.publish(st)
    golden.publish(st)
    assert golden.sync(sb, st) == 2 and "echo 2 >" in sb.cmds[-1]
    assert "/home/node/.claude/skills" in sb.cmds[-1] and "rm -rf /home/node/apps" not in sb.cmds[-1]
    assert "chown node:node /home/node/.claude &&" in sb.cmds[-1]  # Claude Code (as node) must write its own config dir


def test_new_person_is_copied_from_the_latest_golden(fake_archil, monkeypatch):
    st = golden.Store()
    monkeypatch.setattr(golden, "_default", st)
    golden.publish(st)
    sb, new = builder.employee_sandbox("Dana")
    assert new and sb.name == "emp-dana" and fake_archil["golden-v1"].forks[-1] is sb


def test_app_records_its_golden_version():
    f = Fakes()

    def build(who, app, spec, on_step=None):
        r = f.build(who, app, spec, on_step)
        r.golden = 2
        return r

    s = Service(Registry(MemoryStore()), build=build, deploy=f.deploy, clear=f.clear)
    e, _ = s.request("Dana", GOOD)
    drain(s)
    assert s.reg.get(e.id).golden == 2


def test_publish_endpoint_needs_the_key(monkeypatch):
    from starlette.testclient import TestClient

    import connector

    monkeypatch.setenv("CONNECTOR_PATH_SECRET", "s" * 40)
    monkeypatch.setattr(golden, "publish", lambda: 7)
    st = golden.Store()
    st.put("golden/latest", b"3")
    monkeypatch.setattr(golden, "_default", st)
    connector.set_service(Service(Registry(MemoryStore())))
    try:
        with TestClient(connector.build_app()) as c:
            k = connector.admin_key()
            assert c.post("/api/admin/wrong/publish").status_code == 404
            assert c.post(f"/api/admin/{k}/publish").json() == {"published": 7}
            assert c.get(f"/api/admin/{k}").json()["golden"] == 3
    finally:
        connector.set_service(None)
