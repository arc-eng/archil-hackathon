"""Claude Code in an Archil sandbox, logged in with CLAUDE_CODE_OAUTH_TOKEN from .env (arc-eng/hq#771).
The token goes only in each process's env (never a file, never the command text, never printed).
Steps: base sandbox -> install claude + tiny repo with a failing test -> login check as `node` -> fork ->
headless fix in the fork -> test passes, base unchanged -> token not on disk -> delete everything, check none left.

    uv run smoke_claude.py
"""

import asyncio
import os
import sys
import time

import archil
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or ""
if not TOKEN:
    sys.exit("no CLAUDE_CODE_OAUTH_TOKEN in .env (run `claude setup-token` and add it)")

ENV = {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN, "HOME": "/home/node"}
AS_NODE = "runuser -u node -- "
t0 = time.time()


def show(label, r, secs):
    out = (r.stdout or "").replace(TOKEN, "<TOKEN>")[-1500:]
    err = (r.stderr or "").replace(TOKEN, "<TOKEN>")[-800:]
    print(f"\n## {label}: {r.status} exit={r.exit_code} {secs:.1f}s\n{out}\n{('stderr: ' + err) if err.strip() else ''}", flush=True)


async def run(sb, label, cmd, env=None, timeout=300):
    s = time.time()
    r = await sb.exec.aio(cmd, env=env, timeout_seconds=timeout)
    show(label, r, time.time() - s)
    return r


SETUP = r"""
set -e
npm install -g @anthropic-ai/claude-code >/dev/null 2>&1
claude --version
mkdir -p /home/node/proj && cd /home/node/proj
cat > calc.js <<'EOF'
function add(a, b) { return a - b; }
module.exports = { add };
EOF
cat > calc.test.js <<'EOF'
const assert = require('node:assert');
const { add } = require('./calc');
assert.strictEqual(add(2, 3), 5);
console.log('test passed');
EOF
chown -R node:node /home/node
(node calc.test.js && echo UNEXPECTED_PASS) || echo 'test fails as planned'
"""


async def main():
    made = []
    try:
        s = time.time()
        base = await archil.Archil().sandboxes.create.aio(name="hq771-claude-login", base_image="node:24-bookworm", max_ttl_seconds=1200, idle_ttl_seconds=300)
        made.append(base)
        print(f"base {base.id} up in {time.time() - s:.1f}s", flush=True)
        await run(base, "setup", SETUP)
        r = await run(base, "login check as node", AS_NODE + "claude -p 'Reply with exactly: LOGIN_OK' < /dev/null", env=ENV, timeout=120)
        login_ok = "LOGIN_OK" in (r.stdout or "")

        s = time.time()
        f = await base.fork.aio(name="hq771-claude-fix")
        made.append(f)
        print(f"\nfork {f.id} in {time.time() - s:.1f}s", flush=True)
        fix = await run(
            f,
            "headless fix in fork",
            "cd /home/node/proj && " + AS_NODE + "claude -p 'node calc.test.js fails. Fix calc.js so the test passes, then run the test.' "
            "--dangerously-skip-permissions --max-turns 8 < /dev/null",
            env=ENV,
            timeout=300,
        )
        t = await run(f, "test after fix", "cd /home/node/proj && node calc.test.js && cat calc.js")
        fixed = t.exit_code == 0
        b = await run(base, "base untouched", "cd /home/node/proj && cat calc.js")

        # Token on disk? Pass it in env to grep (-F, fixed string), list only file names.
        leak = await run(f, "token on disk (fork)", 'grep -rlF -- "$CLAUDE_CODE_OAUTH_TOKEN" /home /root /tmp /etc 2>/dev/null; echo "grep done"', env={"CLAUDE_CODE_OAUTH_TOKEN": TOKEN})
        leaked = [l for l in (leak.stdout or "").splitlines() if l.strip() and l.strip() != "grep done"]
        print(f"\nRESULT login_ok={login_ok} fixed={fixed} base_still_buggy={'a - b' in (b.stdout or '')} token_files={leaked or 'none'}")
    finally:
        for sb in reversed(made):
            try:
                try:
                    await sb.stop.aio()
                except Exception:
                    pass
                await sb.delete.aio()
                print(f"deleted {sb.id}")
            except Exception as e:
                print(f"COULD NOT DELETE {sb.id}: {e}")
        left = [s.id for s in archil.list_sandboxes() if s.id in {m.id for m in made}]
        print(f"left over: {left or 'none'} · {time.time() - t0:.0f}s total")


asyncio.run(main())
