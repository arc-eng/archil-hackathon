"""The app registry: every request, its owner, status, minutes and link. One JSON object on an Archil disk, so it
survives connector redeploys (arc-eng/hq#781). In memory with a lock; written through on every change."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

DISK_NAME = "golden-registry"
KEY = "registry.json"
SLOTS = [f"app-{i:02d}" for i in range(1, 11)]
STATUSES = ("queued", "building", "deploying", "live", "failed", "refused", "stopped")


@dataclass
class App:
    id: str
    app: str  # folder name in the employee's sandbox
    title: str
    who: str
    spec: str
    ask: str = ""  # the request in the person's own words
    rule: str = ""  # for a refusal: the house rule it broke
    status: str = "queued"
    reason: str = ""
    slot: str = ""
    url: str = ""
    sandbox: str = ""
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    build_seconds: float = 0.0
    steps: list[str] = field(default_factory=list)
    changes: int = 0  # how many times this app was changed after its first build


class MemoryStore:
    def __init__(self, data: bytes | None = None):
        self.data = data

    def get(self) -> bytes | None:
        return self.data

    def put(self, body: bytes) -> None:
        self.data = body


class ArchilStore:
    """registry.json on a small Archil disk, created on first use."""

    def __init__(self):
        import archil

        disk = next((d for d in archil.list_disks() if getattr(d, "name", None) == DISK_NAME), None)
        self.disk = disk or archil.create_disk(name=DISK_NAME).disk

    def get(self) -> bytes | None:
        return self.disk.get_object(KEY) if self.disk.object_exists(KEY) else None

    def put(self, body: bytes) -> None:
        self.disk.put_object(KEY, body, content_type="application/json")


class Registry:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        raw = store.get()
        self.apps: dict[str, App] = {}
        if raw:
            for d in json.loads(raw):
                self.apps[d["id"]] = App(**d)

    def _save(self) -> None:
        self.store.put(json.dumps([asdict(a) for a in self.apps.values()], indent=1).encode())

    def add(self, *, app: str, title: str, who: str, spec: str, ask: str = "", **kw) -> App:
        with self.lock:
            a = App(id=uuid.uuid4().hex[:10], app=app, title=title, who=who, spec=spec, ask=ask, **kw)
            self.apps[a.id] = a
            self._save()
            return a

    def update(self, id_: str, **kw) -> App:
        with self.lock:
            a = self.apps[id_]
            for k, v in kw.items():
                setattr(a, k, v)
            a.updated = time.time()
            self._save()
            return a

    def step(self, id_: str, msg: str) -> None:
        with self.lock:
            a = self.apps[id_]
            a.steps.append(f"{time.strftime('%H:%M:%S')} {msg}")
            a.updated = time.time()
            self._save()

    def get(self, id_: str) -> App | None:
        return self.apps.get(id_)

    def all(self) -> list[App]:
        with self.lock:
            return sorted(self.apps.values(), key=lambda a: a.created, reverse=True)

    def of(self, who: str) -> list[App]:
        return [a for a in self.all() if a.who.strip().lower() == who.strip().lower()]

    def find(self, who: str, app: str) -> App | None:
        """The person's latest entry for this app folder (to change an existing app)."""
        return next((a for a in self.of(who) if a.app == app), None)

    def busy(self) -> int:
        return sum(1 for a in self.all() if a.status in ("queued", "building", "deploying"))

    def free_slot(self, keep: str = "") -> str | None:
        """The app's own slot if it has one, else the next slot no live/deploying app holds."""
        with self.lock:
            if keep:
                return keep
            taken = {a.slot for a in self.apps.values() if a.slot and a.status in ("live", "deploying")}
            return next((s for s in SLOTS if s not in taken), None)
