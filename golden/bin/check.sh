#!/usr/bin/env bash
# check.sh <app>: start the app on a free port, wait for /health, run its selftest.sh, stop it.
# Prints ALL CHECKS PASSED and exits 0 only if everything passes.
set -uo pipefail
APP="${1:?usage: check.sh <app>}"
DIR="/home/node/apps/$APP"
cd "$DIR" || { echo "no such app folder: $DIR"; exit 2; }
[ -f server.js ] || { echo "no server.js in $DIR"; exit 2; }
[ -f Dockerfile ] || { echo "no Dockerfile in $DIR"; exit 2; }
PORT=$(( 18000 + RANDOM % 1000 ))
DATA=$(mktemp)
echo '{"items":[]}' > "$DATA"
PORT=$PORT DATA_FILE=$DATA node server.js > /tmp/check-$APP.log 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null; rm -f "$DATA"' EXIT
for _ in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
  kill -0 $PID 2>/dev/null || { echo "app exited on start:"; tail -20 /tmp/check-$APP.log; exit 1; }
  sleep 0.3
done
curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 || { echo "app never answered /health:"; tail -20 /tmp/check-$APP.log; exit 1; }
[ -f selftest.sh ] || { echo "no selftest.sh"; exit 1; }
BASE_URL="http://127.0.0.1:$PORT" bash selftest.sh
RC=$?
[ $RC -eq 0 ] || echo "SELFTEST FAILED (exit $RC)"
exit $RC
