# Archil hackathon

Marco's build for [Agents Need Solid Ground: An Archil Hackathon](https://luma.com/t9hsthtk), Nov 10, 2026. Python, with the
[Archil SDK](https://pypi.org/project/archil/) (`archil` 0.21) installed through uv.

## Run

On this Mac it's ready: `~/code/arcane/archil-hackathon` already has the `.env` with the key.

```bash
cd ~/code/arcane/archil-hackathon
uv run main.py        # → "Archil OK: 0 disk(s), 0 sandbox(es)"
```

On another machine:

```bash
git clone https://github.com/arc-eng/archil-hackathon && cd archil-hackathon
cp .env.example .env  # then fill in ARCHIL_API_KEY and ARCHIL_REGION
uv run main.py
```

`ArchilApiError ... status 401` means the key in `.env` is wrong or missing. `.env` is git-ignored: never commit it.

## The SDK in four lines

The key and region are read from the environment (`load_dotenv()` loads `.env`).

```python
import archil
disk = archil.create_disk(name="demo").disk            # shared persistent disk
print(disk.exec("ls -la /mnt").stdout)                  # run a command in a microVM with the disk mounted
box = archil.create_sandbox(name="agent", base_image="python:3.12-slim")
fork = box.fork(name="try-2")                           # branch a sandbox: parallel agents, keep the best
```

Also in the SDK: agent tools that turn a disk into a filesystem toolset for OpenAI Agents and LangChain
(`archil.agent_tools`), S3-style reads and writes on a disk, exposing a sandbox port as a public URL
(`expose_port`), and images built from any OCI image. Full docs: [docs.archil.com](https://docs.archil.com/getting-started/introduction); every SDK call with examples:
[the package page](https://pypi.org/project/archil/).

`main.py` only reads (lists disks and sandboxes), so it creates nothing and costs nothing. Clean up what you create with
`disk.delete()`, `sandbox.stop()` and `sandbox.delete()`.

## The agent: Pydantic AI over Archil

`agent.py` is a Pydantic AI agent with Archil as plain tools (`archil_tools.py`), so no LangChain. Archil only ships
OpenAI Agents and LangChain adapters.

```bash
uv run agent.py "Create a python:3.12 sandbox, pip install packaging 23.2, then fork it to try packaging 24.2 and 25.0 \
  and tell me which import and print their version"
uv run agent.py --keep "..."   # leave the sandboxes up to look around (Archil still stops them after 30 min)
```

**Model:** `ARCHIL_AGENT_MODEL` in `.env`, any Pydantic AI model string, default `anthropic:claude-sonnet-5-5`, plus
that provider's key (`ANTHROPIC_API_KEY=` or `OPENAI_API_KEY=` with e.g. `openai:gpt-5.2`). `.env` is git-ignored.

**Tools** (only on sandboxes this run created; at most 6 per run; all deleted at the end unless `--keep`):

| Tool | Does |
|---|---|
| `create_sandbox(name, base_image?)` | a new microVM, default `python:3.12-slim`, stopped by Archil after 30 min even if we crash |
| `run(sandbox_id, command, cwd?, timeout_seconds?)` | a shell command; exit code, seconds, the last 4,000 chars of stdout/stderr |
| `fork(sandbox_id, name)` | a copy of the whole warm state in a new sandbox |
| `fork_and_run(sandbox_id, jobs, timeout_seconds?)` | **the fan-out:** a fork per job, each job's command in its own fork, at most 5 at once, one result per job (one bad fork doesn't sink the rest) |
| `write_file` / `read_file` | text files in a sandbox |
| `list_sandboxes` / `delete_sandbox` | this run's sandboxes; forks are deleted before their base |

**Tonight's upgrade sweep** fits it directly: `create_sandbox` → `run` the setup once (Postgres, Poetry install, a test
run to time it) → `fork_and_run` with one job per capped package (`sed` the cap in `pyproject.toml` → `poetry lock` →
tests) → a table of pass/fail per upgrade. Or skip the model and call the tools from a script, as `smoke_live.py` does.

**Archil's rules, learned on the first live run:** a running sandbox must be stopped before it's deleted, and forks go
before the sandbox they came from. The tools do both.

### Checks

```bash
uv run pytest -q          # the tools against a fake Archil: no network, no sandbox time
uv run smoke_live.py      # real Archil, scripted model (no LLM key): ~3 sandboxes for ~15 s, then checks none are left
```

Free plan: 1 sandbox-hour a month, 30-minute sessions. `smoke_live.py` uses about a minute of it.
