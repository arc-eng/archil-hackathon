"""The golden image as code (arc-eng/hq#782): the `golden/` folder is the source; publishing makes version N.

- `publish()`: snapshot `golden/` (house rules, skills, template, check script) as `golden/vN.tgz` on the registry's
  Archil disk, and make sandbox `golden-vN`: a copy of the previous golden with that snapshot installed. New people
  are copied from the latest one. Older versions are kept. The `latest` pointer moves last, so a failed publish
  changes nothing.
- `sync(sb)`: install the latest published snapshot into a person's sandbox at the start of every request, so a
  rule or skill change reaches everyone on their next request. Only the company's files are replaced: the person's
  apps and Claude Code's own history stay.

In the sandbox: `golden/claude/CLAUDE.md` and `golden/claude/skills/` go to Claude Code's config folder for `node`
(`~/.claude/`), `template/` and `bin/` (root-owned) to `/home/node/`, and the version to `/home/node/.golden-version`.
"""

from __future__ import annotations

import io
import os
import tarfile
import tempfile
import threading
from pathlib import Path

SRC = Path(__file__).parent / "golden"
SKIP = {"setup.sh"}  # runs once per golden sandbox, not synced
CLAUDE_DIR = "/home/node/" + ".claude"
PREFIX = "golden/"
_cache: dict[int, bytes] = {}
_lock = threading.Lock()


def snapshot(src: Path = SRC) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for p in sorted(src.rglob("*")):
            rel = p.relative_to(src).as_posix()
            if p.is_file() and rel not in SKIP and not p.name.startswith(".gitkeep"):
                t.add(p, arcname=rel)
    return buf.getvalue()


class Store:
    """golden/latest and golden/vN.tgz on an Archil disk (the registry's), or in memory for tests."""

    def __init__(self, disk=None):
        self.disk = disk
        self.mem: dict[str, bytes] = {}

    def get(self, key: str) -> bytes | None:
        if self.disk is None:
            return self.mem.get(key)
        return self.disk.get_object(key) if self.disk.object_exists(key) else None

    def put(self, key: str, body: bytes) -> None:
        if self.disk is None:
            self.mem[key] = body
        else:
            self.disk.put_object(key, body)

    def latest(self) -> int:
        raw = self.get(PREFIX + "latest")
        return int(raw.decode().strip()) if raw else 0

    def version(self, v: int) -> bytes:
        with _lock:
            if v not in _cache:
                body = self.get(f"{PREFIX}v{v}.tgz")
                if body is None:
                    raise RuntimeError(f"golden v{v} is missing from the store")
                _cache[v] = body
            return _cache[v]


_default: Store | None = None


def default_store() -> Store:
    global _default
    if _default is None:
        from registry import ArchilStore

        _default = Store(ArchilStore().disk)
    return _default


INSTALL = r"""set -e
rm -rf /tmp/g && mkdir -p /tmp/g && tar xzf /tmp/golden.tgz -C /tmp/g --no-same-owner
rm -rf /home/node/template /home/node/bin && cp -r /tmp/g/template /tmp/g/bin /home/node/
mkdir -p {cd} && rm -rf {cd}/skills && mkdir -p {cd}/skills
cp /tmp/g/claude/CLAUDE.md {cd}/CLAUDE.md
[ -d /tmp/g/claude/skills ] && cp -r /tmp/g/claude/skills/. {cd}/skills/ || true
rm -f /home/node/apps/CLAUDE.md
echo {v} > /home/node/.golden-version
mkdir -p /home/node/apps && chown node:node /home/node/apps /home/node/.golden-version
chown node:node {cd} && chown -R node:node /home/node/template {cd}/CLAUDE.md {cd}/skills
chown -R root:root /home/node/bin && chmod 755 /home/node/bin /home/node/bin/*.sh && chmod +x /home/node/template/selftest.sh
rm -rf /tmp/g /tmp/golden.tgz
"""


def install(sb, body: bytes, v: int) -> None:
    with tempfile.NamedTemporaryFile(suffix=".tgz", delete=False) as f:
        f.write(body)
    try:
        sb.files.upload_file(f.name, "/tmp/golden.tgz")
    finally:
        os.unlink(f.name)
    r = sb.exec(INSTALL.format(cd=CLAUDE_DIR, v=v), timeout_seconds=120)
    if r.exit_code != 0:
        raise RuntimeError(f"installing golden v{v} failed: {(r.stderr or r.stdout or '')[-300:]}")


def sync(sb, store: Store | None = None) -> int:
    """Install the latest published version into a running sandbox. Returns its number (0: nothing published yet,
    so the folder as deployed is installed)."""
    store = store or default_store()
    v = store.latest()
    install(sb, store.version(v) if v else snapshot(), v)
    return v


def sandbox_name(v: int) -> str:
    return f"golden-v{v}"


def publish(store: Store | None = None, *, base_name: str = "golden") -> int:
    """Publish `golden/` as the next version. Returns the new number."""
    import builder

    store = store or default_store()
    prev = store.latest()
    v = prev + 1
    body = snapshot()
    base = builder._by_name(sandbox_name(prev) if prev else base_name)
    if base is None:
        base = builder.ensure_golden()
    builder._stop(base)
    sb = builder._by_name(sandbox_name(v)) or base.fork(name=sandbox_name(v))
    builder._stop(base)
    try:
        builder._running(sb)
        install(sb, body, v)
    finally:
        builder._stop(sb)
    store.put(f"{PREFIX}v{v}.tgz", body)
    store.put(PREFIX + "latest", str(v).encode())  # last: only a finished publish moves the pointer
    with _lock:
        _cache[v] = body
    return v


def latest_sandbox(store: Store | None = None):
    import builder

    v = (store or default_store()).latest()
    return builder._by_name(sandbox_name(v)) if v else None
