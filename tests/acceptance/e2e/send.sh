#!/usr/bin/env bash
# qa part 8: send spec files to the deployed connector's request_app, in order. Run from the repo root:
#   bash tests/acceptance/e2e/send.sh <path to .env> <spec name> [<spec name> ...]
set -u
ENVF="$1"; shift
for f in "$@"; do
  echo "== $f"
  PYTHONPATH=. uv run --env-file "$ENVF" python tests/acceptance/e2e_call.py request_app "$(cat "tests/acceptance/e2e/$f.json")" 2>&1 | tail -3
done
