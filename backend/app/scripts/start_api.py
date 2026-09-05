from __future__ import annotations

import os
import subprocess
import sys


def _run(label: str, command: list[str]) -> None:
    print(f"Drovixa startup: {label}...", flush=True)
    subprocess.run(command, check=True)  # noqa: S603 - commands are fixed below


def main() -> None:
    _run("applying database migrations", ["alembic", "upgrade", "head"])
    _run(
        "checking the initial administrator",
        [sys.executable, "-m", "app.scripts.bootstrap_superuser_once"],
    )
    _run(
        "synchronizing the showcase catalog",
        [sys.executable, "-m", "app.scripts.demo_catalog", "sync"],
    )

    port = os.environ.get("PORT", "8000")
    command = [
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",  # noqa: S104 - required inside the Render container
        "--port",
        port,
        "--proxy-headers",
    ]
    print(f"Drovixa startup: launching API on port {port}.", flush=True)
    os.execvp(command[0], command)  # noqa: S606 - replace startup process with Uvicorn


if __name__ == "__main__":
    main()
