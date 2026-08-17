"""Fail-open run-audit snapshots on kanban lifecycle hooks.

Observer only. Callback errors must not affect the worker. Hermes has no
create-hook; create is snapshotted from the mint Procedure (`mint-m3-hermes.md`).
Reclaim is the claimed event firing again.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _script() -> Path | None:
    env_root = os.environ.get("HERMES_WRITE_SAFE_ROOT", "")
    candidates = []
    if env_root:
        candidates.append(
            Path(env_root)
            / ".hermes"
            / "skills"
            / "harness"
            / "record-run-evidence"
            / "scripts"
            / "snapshot-card-boundary.sh"
        )
    home = os.environ.get("HERMES_HOME")
    if home:
        candidates.append(
            Path(home).parent
            / "skills"
            / "harness"
            / "record-run-evidence"
            / "scripts"
            / "snapshot-card-boundary.sh"
        )
    cwd = Path.cwd()
    candidates.append(
        cwd
        / ".hermes"
        / "skills"
        / "harness"
        / "record-run-evidence"
        / "scripts"
        / "snapshot-card-boundary.sh"
    )
    for p in candidates:
        if p.is_file():
            return p
    return None


def _snap(boundary: str) -> None:
    script = _script()
    if script is None:
        return
    try:
        subprocess.run(
            ["bash", str(script), boundary],
            check=False,
            timeout=120,
            capture_output=True,
        )
    except Exception:
        return


def register(ctx):  # noqa: ARG001 — Hermes plugin contract
    def on_claimed(**kwargs):
        _snap("claim")

    def on_completed(**kwargs):
        _snap("complete")

    def on_blocked(**kwargs):
        _snap("block")

    ctx.register_hook("kanban_task_claimed", on_claimed)
    ctx.register_hook("kanban_task_completed", on_completed)
    ctx.register_hook("kanban_task_blocked", on_blocked)
