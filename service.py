"""What the connector tools do (arc-eng/hq#781): spec checks, the rule check, and the background build → deploy.

`request_app` answers at once; a worker thread builds in the employee's sandbox (at most 2 at once) and then deploys
(one at a time). Every outcome lands in the registry: live, failed with a reason, or refused with the rule."""

from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor

import builder
import deploy as deploy_mod
from registry import Registry

MAX_BUILDS = 2
VAGUE = {"", "-", "--", ".", "n/a", "na", "none", "tbd", "todo", "?", "...", "whatever", "anything", "something", "stuff", "idk", "x"}

# Requests that send company data outside the company break a house rule; refused before any sandbox time is spent.
OUTSIDE = [
    (r"\bdrop\s?box\b", "personal Dropbox"),
    (r"\bgoogle\s?drive\b|\bgdrive\b", "Google Drive"),
    (r"\bone\s?drive\b", "OneDrive"),
    (r"\bicloud\b", "iCloud"),
    (r"\b(personal|private|my own)\s+(e-?mail|gmail|inbox|account)\b|\bgmail\b", "a personal email account"),
    (r"\bwebhooks?\b|\bzapier\b|\bifttt\b", "an outside webhook"),
    (r"\bgoogle analytics\b|\btracking pixel\b|\bmixpanel\b", "outside tracking"),
]
RULE = "Company data stays inside the company: no sending it to {where}."


class SpecError(ValueError):
    pass


def _vague(s: str) -> bool:
    t = (s or "").strip().lower()
    return t in VAGUE or len(t) < 8


def check_spec(spec: dict) -> list[str]:
    """What's missing or too vague, in words Claude can relay. Empty list = good."""
    missing = []
    for key, label in (
        ("title", "a short name for the app"),
        ("for_whom", "who uses it and what for"),
        ("screens", "the main screens or actions"),
        ("data", "the data it reads and writes"),
        ("out_of_scope", "what is out of scope"),
    ):
        if _vague(str(spec.get(key) or "")):
            missing.append(label)
    done = [d for d in (spec.get("done_when") or []) if not _vague(str(d))]
    if len(done) < 2:
        missing.append('at least two concrete "done when" checks, each something you can test')
    if _vague(str(spec.get("ask") or "")):
        missing.append("the person's request in their own words")
    return missing


def broken_rule(spec: dict) -> str:
    text = " ".join(str(v) for v in spec.values() if isinstance(v, str)) + " " + " ".join(spec.get("done_when") or [])
    for pat, where in OUTSIDE:
        if re.search(pat, text, re.I):
            return RULE.format(where=where)
    return ""


def spec_md(spec: dict) -> str:
    done = "\n".join(f"- {d}" for d in spec["done_when"])
    return (
        f"# {spec['title']}\n\n**Asked for (their words):** {spec['ask']}\n\n**What it does and for whom:** {spec['for_whom']}\n\n"
        f"**Screens / main actions:** {spec['screens']}\n\n**Data it reads and writes:** {spec['data']}\n\n"
        f"**Done when:**\n{done}\n\n**Out of scope:** {spec['out_of_scope']}\n"
    )


class Service:
    def __init__(self, registry: Registry, *, build=builder.build, deploy=deploy_mod.deploy, clear=deploy_mod.clear):
        self.reg = registry
        self._build, self._deploy, self._clear = build, deploy, clear
        self.pool = ThreadPoolExecutor(max_workers=MAX_BUILDS, thread_name_prefix="build")
        self.deploy_lock = threading.Lock()

    # --- request -----------------------------------------------------------------
    def request(self, who: str, spec: dict, change_of: str = ""):
        """Returns (entry, None) when accepted or refused, or (None, [missing parts]) for a spec to fix."""
        who = (who or "").strip()
        missing = check_spec(spec)
        if _vague(who) and len(who) < 2:
            missing.insert(0, "the person's name")
        if missing:
            return None, missing
        prev = self.reg.find(who, change_of) if change_of else None
        if change_of and not prev:
            return None, [f"no app called '{change_of}' for {who}: call my_apps to see their apps"]
        app = prev.app if prev else builder.slug(spec["title"])
        if not prev:  # a new app gets its own folder, even if the title repeats
            names = {a.app for a in self.reg.of(who)}
            base, n = app, 2
            while app in names:
                app, n = f"{base}-{n}", n + 1
        rule = broken_rule(spec)
        text = spec_md(spec)
        if prev:
            text = prev.spec + f"\n\n## Change requested\n\n{text}"
        e = self.reg.add(app=app, title=spec["title"], who=who, spec=text, ask=spec["ask"], slot=prev.slot if prev and prev.status in ("live", "deploying") else "", changes=(prev.changes + 1) if prev else 0)
        if rule:
            return self.reg.update(e.id, status="refused", rule=rule, reason="Refused before building: " + rule), None
        self.pool.submit(self._run, e.id)
        return e, None

    # --- background ----------------------------------------------------------------
    def _run(self, id_: str) -> None:
        e = self.reg.get(id_)
        try:
            self.reg.update(id_, status="building")
            r = self._build(e.who, e.app, e.spec, on_step=lambda m: self.reg.step(id_, m))
            self.reg.update(id_, build_seconds=r.seconds, sandbox=builder.EMP_PREFIX + builder.slug(e.who))
            if r.status == "refused":
                self.reg.update(id_, status="refused", rule=r.reason, reason="Refused in the sandbox: " + r.reason)
                return
            if r.status != "built":
                self.reg.update(id_, status="failed", reason=r.reason or "the build failed")
                return
            with self.deploy_lock:
                slot = self.reg.free_slot(keep=self.reg.get(id_).slot)
                if not slot:
                    self.reg.update(id_, status="failed", reason="all 10 app slots are in use: stop an app first")
                    return
                self.reg.update(id_, status="deploying", slot=slot)
                self.reg.step(id_, f"the company's builder is deploying it to {slot}")
                url = self._deploy(r.source, slot)
            self.reg.update(id_, status="live", url=url, reason="")
            self.reg.step(id_, "live")
            for old in self.reg.of(e.who):  # the version this one replaces
                if old.app == e.app and old.id != id_ and old.status == "live":
                    self.reg.update(old.id, status="stopped", url="", reason="replaced by a newer version")
        except Exception as ex:  # noqa: BLE001 - never a silent stop
            self.reg.update(id_, status="failed", reason=f"{type(ex).__name__}: {str(ex)[:300]}")

    # --- stop ------------------------------------------------------------------------
    def stop(self, who: str, app: str):
        e = self.reg.find(who, app)
        if not e:
            return None, f"no app called '{app}' for {who}"
        if e.status != "live":
            return e, f"'{app}' isn't live (it's {e.status}), so there's nothing to stop"
        slot = e.slot
        self.reg.update(e.id, status="stopped", url="", reason="stopped by its owner")

        def _clear():
            try:
                with self.deploy_lock:
                    self._clear(slot)
                self.reg.step(e.id, f"{slot} cleared")
            except Exception as ex:  # noqa: BLE001
                self.reg.step(e.id, f"clearing {slot} failed: {ex}")

        self.pool.submit(_clear)
        return e, ""

    def minutes(self, who: str) -> float:
        return round(sum(a.build_seconds for a in self.reg.of(who)) / 60, 1)
