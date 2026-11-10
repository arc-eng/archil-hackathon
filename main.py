"""Smoke check: proves the Archil key in .env works. Read-only: it lists your disks and sandboxes, creates nothing."""

from dotenv import load_dotenv

load_dotenv()  # ARCHIL_API_KEY and ARCHIL_REGION from .env; archil reads them from the environment

import archil  # noqa: E402


def main() -> None:
    disks = archil.list_disks()
    sandboxes = archil.list_sandboxes()
    print(f"Archil OK: {len(disks)} disk(s), {len(sandboxes)} sandbox(es)")
    for d in disks:
        print(f"  disk {d.id} {getattr(d, 'name', '')}")


if __name__ == "__main__":
    main()
