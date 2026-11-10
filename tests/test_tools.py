"""The Archil tools against a fake Archil (no network, no sandbox time), driven by Pydantic AI's FunctionModel."""

from __future__ import annotations

import asyncio
import itertools
import json

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

import archil_tools
from archil_tools import ArchilDeps, archil_toolset, cleanup

ids = itertools.count(1)


class Aio:
    """A fake SDK method: callable, with .aio like synchronicity's."""

    def __init__(self, fn):
        self.fn = fn

    async def aio(self, *a, **k):
        return await self.fn(*a, **k)


class Result:
    def __init__(self, status="completed", exit_code=0, stdout="", stderr=""):
        self.status, self.exit_code, self.stdout, self.stderr = status, exit_code, stdout, stderr


class FakeSandbox:
    live: dict[str, "FakeSandbox"] = {}
    fail_fork_named: set[str] = set()
    running = 0
    peak = 0

    def __init__(self, name, files=None, parent=None):
        self.id, self.name, self.status, self.parent = f"sbx-{next(ids)}", name, "running", parent
        self.files_store = dict(files or {})
        FakeSandbox.live[self.id] = self
        self.exec = Aio(self._exec)
        self.fork = Aio(self._fork)
        self.delete = Aio(self._delete)
        self.stop = Aio(self._stop)
        self.refresh = Aio(self._refresh)
        sb = self

        class Files:
            async def _up(local, remote):
                sb.files_store[remote] = open(local).read()

            async def _down(remote, local):
                if remote not in sb.files_store:
                    raise FileNotFoundError(remote)
                open(local, "w").write(sb.files_store[remote])

            upload_file = Aio(_up)
            download_file = Aio(_down)

        self.files = Files

    async def _exec(self, command, cwd=None, timeout_seconds=None):
        FakeSandbox.running += 1
        FakeSandbox.peak = max(FakeSandbox.peak, FakeSandbox.running)
        await asyncio.sleep(0.01)
        FakeSandbox.running -= 1
        if command.startswith("fail"):
            return Result("failed", 1, "", "E   ImportError: boom\n")
        return Result(stdout=f"ran {command} in {self.name}")

    async def _fork(self, name=None):
        if name in FakeSandbox.fail_fork_named:
            raise RuntimeError("503 no capacity")
        return FakeSandbox(name, self.files_store, parent=self.id)

    async def _stop(self):
        self.status = "stopped"

    async def _delete(self):
        # Archil's rules, as the live run found them: stopped first, and no forks still around.
        if self.status == "running":
            raise RuntimeError("Stop the sandbox before deleting it unless it has exited or failed")
        if any(s.parent == self.id for s in FakeSandbox.live.values()):
            raise RuntimeError("sandbox has dependent forks: delete child sandbox disks first")
        FakeSandbox.live.pop(self.id, None)

    async def _refresh(self):
        return self


class FakeClient:
    class sandboxes:
        @staticmethod
        async def _create(name=None, base_image=None, **kw):
            return FakeSandbox(name)

        create = Aio(_create)


@pytest.fixture(autouse=True)
def fake_archil(monkeypatch):
    FakeSandbox.live, FakeSandbox.fail_fork_named, FakeSandbox.running, FakeSandbox.peak = {}, set(), 0, 0
    monkeypatch.setattr(archil_tools.archil, "Archil", lambda: FakeClient)
    monkeypatch.setenv("ARCHIL_AGENT_QUIET", "1")


def scripted(*steps):
    """A FunctionModel that makes the given tool calls in order (args may use earlier results), then answers."""
    steps = list(steps)

    def fn(messages, info):
        returns = [p for m in messages for p in getattr(m, "parts", []) if isinstance(p, ToolReturnPart)]
        if not steps:
            return ModelResponse(parts=[TextPart("done")])
        tool, args = steps.pop(0)
        if callable(args):
            args = args(returns)
        return ModelResponse(parts=[ToolCallPart(tool, json.dumps(args))])

    return FunctionModel(fn)


def last(returns, key="sandbox_id"):
    c = returns[-1].content
    return c[key] if isinstance(c, dict) else getattr(c, key)


async def go(*steps, deps=None):
    deps = deps or ArchilDeps()
    agent = Agent(scripted(*steps), deps_type=ArchilDeps, toolsets=[archil_toolset])
    result = await agent.run("go", deps=deps)
    return result, deps


def said(result):
    """What the tools told the model: returns and retries (2.66 sends a ModelRetry back as a tool return)."""
    return [str(p.content) for m in result.all_messages() for p in getattr(m, "parts", []) if p.part_kind in ("tool-return", "retry-prompt")]


def returns_of(result):
    return [p for m in result.all_messages() for p in getattr(m, "parts", []) if isinstance(p, ToolReturnPart)]


async def test_setup_once_then_fan_out_with_one_bad_variant():
    FakeSandbox.fail_fork_named = {"broken-fork"}
    jobs = [{"name": f"v{i}", "command": "pytest -q"} for i in range(5)] + [{"name": "bad", "command": "fail please"}, {"name": "broken-fork", "command": "x"}]
    deps = ArchilDeps(max_sandboxes=10, max_parallel=3)
    result, deps = await go(
        ("create_sandbox", {"name": "base"}),
        ("run", lambda r: {"sandbox_id": last(r), "command": "pip install -q pytest"}),
        ("fork_and_run", lambda r: {"sandbox_id": r[0].content["sandbox_id"], "jobs": jobs}),
        deps=deps,
    )
    table = returns_of(result)[-1].content
    by = {j.name: j for j in table}
    assert [by[f"v{i}"].ok for i in range(5)] == [True] * 5
    assert by["bad"].ok is False and "ImportError" in by["bad"].run.stderr_tail
    assert by["broken-fork"].ok is False and "fork failed" in by["broken-fork"].error  # one bad fork doesn't sink the rest
    assert FakeSandbox.peak <= 3  # never more than max_parallel at once
    assert len(deps.created) == 1 + 6  # base + the 6 forks that worked
    assert await cleanup(deps) == [] and FakeSandbox.live == {}


async def test_only_its_own_sandboxes_and_a_cap():
    stranger = FakeSandbox("someone-elses")
    result, deps = await go(
        ("run", {"sandbox_id": stranger.id, "command": "rm -rf /"}),
        ("delete_sandbox", {"sandbox_id": stranger.id}),
        ("create_sandbox", {"name": "a"}),
        ("create_sandbox", {"name": "b"}),
        ("fork_and_run", lambda r: {"sandbox_id": last(r), "jobs": [{"name": "c", "command": "x"}, {"name": "d", "command": "x"}]}),
        deps=ArchilDeps(max_sandboxes=3),
    )
    texts = said(result)
    assert sum("isn't a sandbox from this run" in t for t in texts) == 2
    assert any("the cap is 3" in t for t in texts)
    assert stranger.id in FakeSandbox.live  # never touched
    assert len(deps.created) == 2
    await cleanup(deps)
    assert list(FakeSandbox.live) == [stranger.id]  # cleanup deletes only ours


async def test_files_round_trip_and_fork_copies_state():
    result, deps = await go(
        ("create_sandbox", {"name": "base"}),
        ("write_file", lambda r: {"sandbox_id": last(r), "path": "/work/notes.txt", "content": "hello archil"}),
        ("fork", lambda r: {"sandbox_id": r[0].content["sandbox_id"], "name": "copy"}),
        ("read_file", lambda r: {"sandbox_id": last(r), "path": "/work/notes.txt"}),
        ("read_file", lambda r: {"sandbox_id": r[0].content["sandbox_id"], "path": "/nope"}),
        ("list_sandboxes", {}),
    )
    rets = returns_of(result)
    assert rets[3].content == "hello archil"  # read back from the fork
    assert {s["name"] for s in rets[-1].content} == {"base", "copy"}
    retries = said(result)
    assert any("can't read /nope" in t for t in retries)
    await cleanup(deps)


async def test_long_output_is_cut_to_the_tail():
    sb = FakeSandbox("x")

    async def loud(command, cwd=None, timeout_seconds=None):
        return Result(stdout="a" * 10_000 + "THE END")

    sb.exec = Aio(loud)
    deps = ArchilDeps()
    deps.created[sb.id] = sb
    r = await archil_tools._exec(deps, sb.id, "x", None, 5)
    assert len(r.stdout_tail) <= archil_tools.TAIL + 1 and r.stdout_tail.endswith("THE END")


def test_agent_builds_without_a_model_key(monkeypatch):
    import agent

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert agent.build_agent("test") is not None  # Pydantic AI's TestModel: no key needed


async def test_delete_asks_for_forks_first_and_cleanup_gets_the_order_right():
    result, deps = await go(
        ("create_sandbox", {"name": "base"}),
        ("fork", lambda r: {"sandbox_id": last(r), "name": "child"}),
        ("delete_sandbox", lambda r: {"sandbox_id": r[0].content["sandbox_id"]}),
        ("delete_sandbox", lambda r: {"sandbox_id": r[1].content["sandbox_id"]}),
    )
    assert any("still has forks" in t for t in said(result))
    assert [s.name for s in FakeSandbox.live.values()] == ["base"]  # the child went, the base waited
    assert await cleanup(deps) == [] and FakeSandbox.live == {}
