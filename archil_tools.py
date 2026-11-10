"""Archil as Pydantic AI tools: plain tools over the `archil` SDK, no LangChain (Archil only ships OpenAI Agents and
LangChain adapters).

The tools fit a fan-out job such as tonight's upgrade sweep: set up one warm sandbox, fork it once per variant, run the
same command in every fork at once, and read back a table. The agent can only touch sandboxes it created in this run,
and `cleanup()` deletes them all at the end (the free plan has 1 sandbox-hour a month).
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass, field

import archil
from pydantic import BaseModel
from pydantic_ai import FunctionToolset, ModelRetry, RunContext

TAIL = 4000  # characters of stdout/stderr returned to the model; the full output stays in the sandbox if you tee it


@dataclass
class ArchilDeps:
    base_image: str = "python:3.12-slim"
    max_sandboxes: int = 6  # hard cap per run, forks included
    max_parallel: int = 5  # forks running at once in fork_and_run
    ttl_seconds: int = 1800  # Archil stops a sandbox after this even if we crash (free plan sessions are 30 min)
    idle_ttl_seconds: int = 600
    created: dict[str, object] = field(default_factory=dict)  # sandbox id → Sandbox, only what this run made, in order
    parent: dict[str, str] = field(default_factory=dict)  # fork id → the sandbox it was forked from
    log: list[str] = field(default_factory=list)

    def note(self, line: str) -> None:
        self.log.append(line)
        if os.environ.get("ARCHIL_AGENT_QUIET") != "1":
            print(f"  · {line}", flush=True)


class Run(BaseModel):
    sandbox_id: str
    status: str  # completed / failed / cancelled / timed_out
    exit_code: int | None
    seconds: float
    stdout_tail: str
    stderr_tail: str


class Job(BaseModel):
    name: str  # the fork's name, e.g. "django-6"
    command: str  # what to run in that fork, e.g. "sed -i ... pyproject.toml && poetry lock && pytest -q"


class JobResult(BaseModel):
    name: str
    sandbox_id: str | None
    ok: bool
    run: Run | None
    error: str | None = None


def _tail(s: str | None) -> str:
    s = s or ""
    return s if len(s) <= TAIL else "…" + s[-TAIL:]


def _mine(deps: ArchilDeps, sandbox_id: str):
    sb = deps.created.get(sandbox_id)
    if sb is None:
        raise ModelRetry(f"{sandbox_id} isn't a sandbox from this run. Yours: {list(deps.created) or 'none yet'}")
    return sb


def _room(deps: ArchilDeps, n: int = 1) -> None:
    if len(deps.created) + n > deps.max_sandboxes:
        raise ModelRetry(f"that would make {len(deps.created) + n} sandboxes; the cap is {deps.max_sandboxes}. Delete some first.")


async def _exec(deps: ArchilDeps, sandbox_id: str, command: str, cwd: str | None, timeout_seconds: int) -> Run:
    sb = _mine(deps, sandbox_id)
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    r = await sb.exec.aio(command, cwd=cwd, timeout_seconds=timeout_seconds)
    secs = round(loop.time() - t0, 1)
    deps.note(f"{sandbox_id}: `{command[:80]}` → {r.status} {r.exit_code} in {secs}s")
    return Run(sandbox_id=sandbox_id, status=r.status, exit_code=r.exit_code, seconds=secs, stdout_tail=_tail(r.stdout), stderr_tail=_tail(r.stderr))


async def create_sandbox(ctx: RunContext[ArchilDeps], name: str, base_image: str | None = None) -> dict:
    """Start a new Archil sandbox (a microVM) and return its id. Use one, set it up, then fork it for variants.

    Args:
        name: a short name, e.g. "base".
        base_image: an OCI image; defaults to python:3.12-slim.
    """
    d = ctx.deps
    _room(d)
    sb = await archil.Archil().sandboxes.create.aio(
        name=name, base_image=base_image or d.base_image, max_ttl_seconds=d.ttl_seconds, idle_ttl_seconds=d.idle_ttl_seconds
    )
    d.created[sb.id] = sb
    d.note(f"created {sb.id} ({name}, {base_image or d.base_image})")
    return {"sandbox_id": sb.id, "name": sb.name, "status": sb.status}


async def run(ctx: RunContext[ArchilDeps], sandbox_id: str, command: str, cwd: str | None = None, timeout_seconds: int = 600) -> Run:
    """Run a shell command in one of your sandboxes and wait for it. Returns exit code and the tail of stdout/stderr.

    Args:
        sandbox_id: from create_sandbox or fork.
        command: run with sh -c semantics, e.g. "pip install -q pytest && pytest -q".
        cwd: working directory inside the sandbox.
        timeout_seconds: the command is stopped after this (default 600).
    """
    return await _exec(ctx.deps, sandbox_id, command, cwd, timeout_seconds)


async def fork(ctx: RunContext[ArchilDeps], sandbox_id: str, name: str) -> dict:
    """Fork a sandbox: a copy of its whole state (files, installed packages, running setup) in a new sandbox.

    Args:
        sandbox_id: the sandbox to copy.
        name: the fork's name, e.g. "django-6".
    """
    d = ctx.deps
    src = _mine(d, sandbox_id)
    _room(d)
    f = await src.fork.aio(name=name)
    d.created[f.id] = f
    d.parent[f.id] = sandbox_id
    d.note(f"forked {sandbox_id} → {f.id} ({name})")
    return {"sandbox_id": f.id, "name": f.name, "status": f.status, "forked_from": sandbox_id}


async def fork_and_run(ctx: RunContext[ArchilDeps], sandbox_id: str, jobs: list[Job], timeout_seconds: int = 900) -> list[JobResult]:
    """Fan out: fork the sandbox once per job and run each job's command in its own fork, all at once (at most 5 at a
    time). Returns one result per job: ok means exit code 0. The forks stay up so you can look into a failure; delete
    them when done.

    Args:
        sandbox_id: the warm sandbox to fork, already set up.
        jobs: one per variant, e.g. [{"name": "django-6", "command": "..."}].
        timeout_seconds: per job.
    """
    d = ctx.deps
    src = _mine(d, sandbox_id)
    if not jobs:
        raise ModelRetry("give at least one job")
    _room(d, len(jobs))
    gate = asyncio.Semaphore(d.max_parallel)

    async def one(job: Job) -> JobResult:
        async with gate:
            try:
                f = await src.fork.aio(name=job.name)
            except Exception as e:  # one failed fork must not sink the others
                return JobResult(name=job.name, sandbox_id=None, ok=False, run=None, error=f"fork failed: {e}")
            d.created[f.id] = f
            d.parent[f.id] = sandbox_id
            d.note(f"forked {sandbox_id} → {f.id} ({job.name})")
            try:
                r = await _exec(d, f.id, job.command, None, timeout_seconds)
                return JobResult(name=job.name, sandbox_id=f.id, ok=r.status == "completed" and r.exit_code == 0, run=r)
            except Exception as e:
                return JobResult(name=job.name, sandbox_id=f.id, ok=False, run=None, error=f"run failed: {e}")

    return list(await asyncio.gather(*(one(j) for j in jobs)))


async def write_file(ctx: RunContext[ArchilDeps], sandbox_id: str, path: str, content: str) -> str:
    """Write a text file into a sandbox (absolute path), replacing it if it exists."""
    sb = _mine(ctx.deps, sandbox_id)
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as t:
        t.write(content)
    try:
        await sb.files.upload_file.aio(t.name, path)
    finally:
        os.unlink(t.name)
    ctx.deps.note(f"{sandbox_id}: wrote {path} ({len(content)} chars)")
    return f"wrote {len(content)} characters to {path}"


async def read_file(ctx: RunContext[ArchilDeps], sandbox_id: str, path: str, max_chars: int = 20000) -> str:
    """Read a text file from a sandbox (absolute path). Long files are cut to max_chars."""
    sb = _mine(ctx.deps, sandbox_id)
    with tempfile.TemporaryDirectory() as tmp:
        local = os.path.join(tmp, "f")
        try:
            await sb.files.download_file.aio(path, local)
        except Exception as e:
            raise ModelRetry(f"can't read {path}: {e}")
        with open(local, encoding="utf-8", errors="replace") as f:
            text = f.read(max_chars + 1)
    return text if len(text) <= max_chars else text[:max_chars] + "\n…(cut)"


async def list_sandboxes(ctx: RunContext[ArchilDeps]) -> list[dict]:
    """The sandboxes this run created, with their current status."""
    out = []
    for sid, sb in ctx.deps.created.items():
        try:
            sb = await sb.refresh.aio()
            ctx.deps.created[sid] = sb
            out.append({"sandbox_id": sid, "name": sb.name, "status": sb.status})
        except Exception as e:
            out.append({"sandbox_id": sid, "status": f"unknown ({e})"})
    return out


async def _stop_and_delete(sb) -> None:
    # Archil refuses to delete a running sandbox ("Stop the sandbox before deleting it"), and a sandbox that still has
    # forks ("delete child sandbox disks first"): found on the first live run.
    if getattr(sb, "status", None) not in ("stopped", "failed", "exited"):
        try:
            await sb.stop.aio()
        except Exception:
            pass  # already stopping or stopped; the delete says if it really can't go
    await sb.delete.aio()


async def delete_sandbox(ctx: RunContext[ArchilDeps], sandbox_id: str) -> str:
    """Delete one of your sandboxes (stops it first). Delete forks before the sandbox they came from."""
    d = ctx.deps
    sb = _mine(d, sandbox_id)
    kids = [k for k, parent in d.parent.items() if parent == sandbox_id and k in d.created]
    if kids:
        raise ModelRetry(f"{sandbox_id} still has forks: delete {', '.join(kids)} first")
    await _stop_and_delete(sb)
    del d.created[sandbox_id]
    ctx.deps.note(f"deleted {sandbox_id}")
    return f"deleted {sandbox_id}"


archil_toolset = FunctionToolset([create_sandbox, run, fork, fork_and_run, write_file, read_file, list_sandboxes, delete_sandbox])


async def cleanup(deps: ArchilDeps) -> list[str]:
    """Delete every sandbox this run created, newest first so forks go before their base. Call it in a finally:
    block. Returns what it couldn't delete."""
    left = []
    for sid, sb in reversed(list(deps.created.items())):
        try:
            await _stop_and_delete(sb)
            del deps.created[sid]
            deps.note(f"cleanup: deleted {sid}")
        except Exception as e:
            left.append(f"{sid}: {e}")
    return left
