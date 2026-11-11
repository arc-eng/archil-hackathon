"""qa acceptance (arc-eng/hq#782 part 1): the golden sandbox exists on Archil and is stopped. Read-only: lists only.
Run from the repo root with the connector's .env: `uv run --env-file <path to .env> python tests/acceptance/golden_exists.py`."""

import archil

rows = [(getattr(s, "name", None), str(getattr(s, "status", "")), getattr(s, "id", None)) for s in archil.list_sandboxes()]
for name, status, id_ in rows:
    print(f"{name}\t{status}\t{id_}")
golden = [r for r in rows if r[0] == "golden" and "delet" not in r[1].lower()]
print("GOLDEN:", "found, " + golden[0][1] if golden else "MISSING")
