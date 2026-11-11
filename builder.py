"""The golden sandbox and the build core (arc-eng/hq#781, parts 1 and 2).

- `ensure_golden()`: the company's golden sandbox (Claude Code, the app template, house rules, check script), stopped.
- `employee_sandbox(who)`: that person's own sandbox. Copied from golden the first time, reused (started) after.
- `build(who, app, spec_md)`: Claude Code builds the app from SPEC.md in the employee's sandbox. Then *we* run the
  check (not Claude's word for it), pack the folder for the deploy, and stop the sandbox (stopped keeps everything).

The token goes only into each command's env, never onto a disk. Sync API: the connector runs builds in a thread.
"""

from __future__ import annotations

import os
import re
import shlex
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import archil

GOLDEN_NAME = "golden"
EMP_PREFIX = "emp-"
HERE = Path(__file__).parent / "golden"
APPS = "/home/node/apps"
AS_NODE = "runuser -u node -- "
BUILDS_DIR = Path(os.environ.get("BUILDS_DIR", "/tmp/builds"))
CLAUDE_TIMEOUT = 900
MAX_TTL = 1800  # plan limit: 30 min per session
IDLE_TTL = 600

SETUP = (Path(__file__).parent / "golden" / "setup.sh").read_text()


def slug(text: str, n: int = 30) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n].strip("-")
    return s or "x"


def _env() -> dict[str, str]:
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if not token:
        raise RuntimeError("CLAUDE_CODE_OAUTH_TOKEN is not set")
    return {"CLAUDE_CODE_OAUTH_TOKEN": token, "HOME": "/home/node"}


def _scrub(s: str | None) -> str:
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or "\0"
    return (s or "").replace(token, "<TOKEN>")


def _by_name(name: str):
    for sb in archil.list_sandboxes():
        if getattr(sb, "name", None) == name and "delet" not in str(getattr(sb, "status", "")).lower():
            return sb
    return None


def _status(sb) -> str:
    return str(getattr(sb.refresh(), "status", "")).lower().split(".")[-1]


def _running(sb):
    st = _status(sb)
    if "running" not in st:
        sb.start()
    return sb


def _stop(sb) -> None:
    try:
        if "running" in _status(sb) or "paused" in _status(sb):
            sb.stop()
    except Exception:
        pass


def _sh(sb, cmd: str, *, env=None, timeout=300):
    return sb.exec(cmd, env=env, timeout_seconds=timeout)


def _upload_text(sb, text: str, remote: str, mode: int | None = None) -> None:
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write(text)
    try:
        sb.files.upload_file(f.name, remote, mode=mode)
    finally:
        os.unlink(f.name)


def ensure_golden(fresh: bool = False):
    """Return the golden sandbox, creating it if missing. Leaves it stopped.
    `fresh`: upload the house rules, template and scripts again, in place (a golden with employee copies can't be
    deleted; copies made earlier keep the old files)."""
    sb = _by_name(GOLDEN_NAME)
    if sb and not fresh:
        return sb
    if sb:
        _running(sb)
    else:
        sb = archil.create_sandbox(name=GOLDEN_NAME, base_image="node:24-bookworm", max_ttl_seconds=MAX_TTL, idle_ttl_seconds=IDLE_TTL)
        r = _sh(sb, SETUP)
        if r.exit_code != 0:
            raise RuntimeError(f"golden setup failed: {_scrub(r.stderr)[-400:]}")
    import golden

    golden.install(sb, golden.snapshot(), 0)  # the base; published versions are copies of it (golden.publish)
    _stop(sb)
    return sb


def delete_employee_sandbox(who: str) -> None:
    sb = _by_name(EMP_PREFIX + slug(who))
    if sb:
        _stop(sb)
        sb.delete()


def employee_sandbox(who: str):
    """The person's own sandbox, running. First time: a copy of golden."""
    name = EMP_PREFIX + slug(who)
    sb = _by_name(name)
    if sb:
        return _running(sb), False
    import golden

    base = golden.latest_sandbox() or ensure_golden()
    sb = base.fork(name=name)
    _stop(base)  # forking may wake it
    return _running(sb), True


SECRET_SHAPES = ["sk-ant-"]  # any Anthropic key or token, not only ours


def has_secret(sb, d: str) -> bool:
    """True if Marco's token, or anything shaped like a Claude key, is in the app's folder. The token goes in through
    env only, never on the command line (qa on #2, finding 1)."""
    pats = " ".join(f"-e {shlex.quote(p)}" for p in SECRET_SHAPES)
    # grep: 0 = found, 1 = clean, 2+ = error. Only exit 1 counts as clean (qa on #3: `|| echo CLEAN` also caught errors).
    r = _sh(sb, f'grep -rqF -e "$T" {pats} {shlex.quote(d)}; case $? in 1) echo CLEAN;; 0) echo FOUND;; *) echo ERROR;; esac',
            env={"T": _env()["CLAUDE_CODE_OAUTH_TOKEN"]})
    out = (r.stdout or "").strip()
    return out != "CLEAN"  # anything but a clean answer counts as found: never deploy on a bad read


@dataclass
class BuildResult:
    status: str  # built | failed | refused
    reason: str = ""
    golden: int = 0  # the golden version the build ran on
    seconds: float = 0.0
    source: str = ""  # local folder with the app's code + Dockerfile, ready to deploy
    log: list[str] = field(default_factory=list)


PROMPT = (
    "Build the app described in SPEC.md in this folder, following the company's house rules (your CLAUDE.md) and "
    "using the company's skills wherever they apply. "
    "Finish only when `/home/node/bin/check.sh {app}` prints ALL CHECKS PASSED, or after writing REFUSED.md."
)


def build(who: str, app: str, spec_md: str, *, on_step=None) -> BuildResult:
    """Build (or change) `app` for `who` from `spec_md`. Never raises: failures come back as status 'failed'."""
    t0 = time.time()
    res = BuildResult(status="failed")

    def step(msg: str) -> None:
        res.log.append(f"{time.time() - t0:5.0f}s {msg}")
        if on_step:
            on_step(msg)

    sb = None
    try:
        step("starting your sandbox")
        sb, new = employee_sandbox(who)
        step("copied the golden sandbox for you" if new else "your sandbox is back, with your earlier apps")
        import golden

        res.golden = golden.sync(sb)
        step(f"golden v{res.golden}: the company's current house rules and skills are in place")
        d = f"{APPS}/{app}"
        _sh(sb, f"mkdir -p {d} && rm -f {d}/REFUSED.md")
        _upload_text(sb, spec_md, f"{d}/SPEC.md")
        _sh(sb, f"chown -R node:node {d}")
        step("Claude Code is building")
        r = _sh(
            sb,
            f"cd {d} && {AS_NODE}claude -p {shlex.quote(PROMPT.format(app=app))} --dangerously-skip-permissions --max-turns 60 < /dev/null",
            env=_env(),
            timeout=CLAUDE_TIMEOUT,
        )
        if r.exit_code != 0:
            res.reason = f"Claude Code stopped (exit {r.exit_code}): {_scrub(r.stderr or r.stdout)[-300:].strip()}"
            return res
        refused = _sh(sb, f"cat {d}/REFUSED.md 2>/dev/null")
        if refused.exit_code == 0 and (refused.stdout or "").strip():
            res.status, res.reason = "refused", (refused.stdout or "").strip()[:500]
            step("refused under the house rules")
            return res
        step("checking it starts and passes its own tests")
        chk = _sh(sb, f"{AS_NODE}/home/node/bin/check.sh {shlex.quote(app)}", timeout=120)
        if chk.exit_code != 0 or "ALL CHECKS PASSED" not in (chk.stdout or ""):
            res.reason = "its own checks failed: " + _scrub(chk.stdout)[-300:].strip()
            return res
        if has_secret(sb, d):
            res.reason = "the app's files contained a secret (a Claude key), so it wasn't deployed"
            step("stopped: a secret was found in the app's files")
            return res
        step("packing the code for the company's builder")
        tgz = f"/tmp/{app}.tgz"
        p = _sh(sb, f"tar czf {tgz} -C {d} --exclude=data.json --exclude=node_modules .")
        if p.exit_code != 0:
            res.reason = f"packing failed: {_scrub(p.stderr)[-200:]}"
            return res
        out = BUILDS_DIR / f"{slug(who)}-{app}-{int(t0)}"
        out.mkdir(parents=True, exist_ok=True)
        sb.files.download_file(tgz, str(out / "src.tgz"))
        res.status, res.source = "built", str(out / "src.tgz")
        step("built")
        return res
    except Exception as e:  # noqa: BLE001 - every failure becomes a visible "failed" with a reason
        res.reason = f"{type(e).__name__}: {_scrub(str(e))[:300]}"
        return res
    finally:
        res.seconds = time.time() - t0
        if sb is not None:
            _stop(sb)


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    if sys.argv[1:2] == ["publish"]:
        import golden

        print(f"published golden v{golden.publish()}")
    elif sys.argv[1:2] == ["golden"]:
        g = ensure_golden(fresh="--fresh" in sys.argv)
        print(f"golden {g.id} status={_status(g)}")
    elif sys.argv[1:2] == ["build"]:
        who, app, spec_file = sys.argv[2:5]
        r = build(who, app, Path(spec_file).read_text(), on_step=lambda m: print("·", m, flush=True))
        print(f"RESULT {r.status} {r.seconds:.0f}s {r.reason} {r.source}")
    else:
        print("usage: builder.py publish | golden [--fresh] | build <who> <app> <spec.md>")
