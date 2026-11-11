"""qa acceptance (arc-eng/hq#782 parts 5, 6): serve the status and admin pages locally on a COPY of the real registry
plus one refused and one failed request. Nothing is written to the real registry: the copy lives in memory, and
builds/deploys are fakes. Run from the repo root:
  uv run --env-file <.env> python tests/acceptance/pages_local.py <port> <outfile for paths>"""

import sys

import connector
from registry import ArchilStore, MemoryStore, Registry
from service import Service

port, out = int(sys.argv[1]), sys.argv[2]
real = ArchilStore().get()  # read only
reg = Registry(MemoryStore(real))
svc = Service(reg, build=lambda *a, **k: None, deploy=lambda *a: "", clear=lambda s: None)
svc.pool.submit = lambda *a, **k: None  # never start a build
connector.set_service(svc)

refused, _ = svc.request(
    "Coach B",
    dict(
        ask="send my client list to my personal Dropbox every night",
        title="Client list backup",
        for_whom="a solo coach backing up their client list",
        screens="none, it runs every night",
        data="the client list, sent to Dropbox",
        done_when=["the list arrives in Dropbox each night", "a log shows each nightly upload"],
        out_of_scope="restoring from the backup",
    ),
)
failed = reg.add(app="habit-log", title="Habit check-in log", who="Coach B", spec="# x", ask="a daily habit check-in log for my clients")
reg.update(failed.id, status="failed", reason="its own checks failed: CHECK adding a check-in shows it in the list")
building = reg.add(app="package-tracker", title="Client package tracker", who="Coach A", spec="# x", ask="sessions left per client")
reg.update(building.id, status="building", build_seconds=40)
reg.step(building.id, "Claude Code is building")

with open(out, "w") as f:
    f.write(f"/admin/{connector.admin_key()}\n/status/{refused.id}\n/status/{failed.id}\n/status/{building.id}\n")
    live = next((a for a in reg.all() if a.status == "live"), None)
    f.write(f"/status/{live.id}\n" if live else "")
    stopped = next((a for a in reg.all() if a.status == "stopped"), None)
    f.write(f"/status/{stopped.id}\n" if stopped else "")

import uvicorn  # noqa: E402

connector.mcp_path()
uvicorn.run(connector.build_app(), host="127.0.0.1", port=port, log_level="warning")
