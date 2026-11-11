#!/usr/bin/env bash
# Self-test: one check per "done when" line of SPEC.md. $BASE_URL is the running app. Exit non-zero on any failure.
set -euo pipefail
check() { echo "CHECK: $1"; }

check "the app answers /health"
out=$(curl -fsS "$BASE_URL/health"); grep -q '"ok":true' <<<"$out"  # not curl | grep -q: SIGPIPE fails under pipefail

echo "ALL CHECKS PASSED"
