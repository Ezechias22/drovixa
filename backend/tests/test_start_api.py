from __future__ import annotations

import subprocess

from app.scripts import start_api


def test_start_api_runs_setup_before_uvicorn(monkeypatch) -> None:
    events: list[tuple[str, list[str]]] = []

    def fake_run(command: list[str], *, check: bool) -> None:
        assert check is True
        events.append(("run", command))

    def fake_execvp(file: str, command: list[str]) -> None:
        assert file == "uvicorn"
        events.append(("exec", command))

    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(start_api.os, "execvp", fake_execvp)

    start_api.main()

    assert events[0] == ("run", ["alembic", "upgrade", "head"])
    assert events[1][0] == "run"
    assert events[1][1][-1] == "app.scripts.bootstrap_superuser_once"
    assert events[2][0] == "run"
    assert events[2][1][-2:] == ["app.scripts.original_catalog", "sync"]
    assert events[3] == (
        "exec",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",  # noqa: S104 - expected Render container binding
            "--port",
            "10000",
            "--proxy-headers",
        ],
    )
