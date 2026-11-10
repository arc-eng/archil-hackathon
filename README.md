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
