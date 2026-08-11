#!/usr/bin/env python3
"""Fail-closed: Hermes Managed Scope must be active before kanban spawn.

Official mechanism (Hermes docs — Managed Scope):
  HERMES_MANAGED_DIR (default /etc/hermes) supplies config.yaml + .env that
  overlay $HERMES_HOME. Do **not** symlink or copy Managed Scope into
  HERMES_HOME (R-HX.5). Workers that lack HERMES_MANAGED_DIR in their
  process environment stillborn with "no API keys or providers found".

Dev Spaces often exports HERMES_MANAGED_DIR only from ~/.bashrc; non-login
spawns (oc exec python, nohup without export) drop it — this gate refuses.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


DEFAULT_MANAGED = "/projects/.platform/hermes"


def _hermes_venv_python() -> Optional[Path]:
    for cand in (
        Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python",
        Path("/home/user/.hermes/hermes-agent/venv/bin/python"),
    ):
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    return None


def _reexec_under_hermes_venv() -> None:
    """Hermes agent requires its venv (Py≥3.10 + PyYAML). Re-exec if needed."""
    if os.environ.get("HERMES_ASSERT_NO_REEXEC") == "1":
        return
    vpy = _hermes_venv_python()
    if vpy is None:
        return
    try:
        if Path(sys.executable).resolve() == vpy.resolve():
            return
    except OSError:
        pass
    os.environ["HERMES_ASSERT_NO_REEXEC"] = "1"
    os.execv(str(vpy), [str(vpy), *sys.argv])


def _ensure_hermes_importable() -> None:
    try:
        import hermes_cli  # noqa: F401
        return
    except ImportError:
        pass
    for cand in (
        Path.home() / ".hermes" / "hermes-agent",
        Path("/home/user/.hermes/hermes-agent"),
    ):
        if (cand / "hermes_cli").is_dir():
            p = str(cand)
            if p not in sys.path:
                sys.path.insert(0, p)
            return


def main() -> int:
    _reexec_under_hermes_venv()
    managed = (os.environ.get("HERMES_MANAGED_DIR") or "").strip()
    if not managed:
        print(
            "FAIL: HERMES_MANAGED_DIR unset — Hermes Managed Scope inactive. "
            f"Export HERMES_MANAGED_DIR={DEFAULT_MANAGED} (or /etc/hermes) "
            "before kanban daemon/dispatch. Official overlay — do not symlink "
            "Managed config into HERMES_HOME (R-HX.5).",
            file=sys.stderr,
        )
        return 1
    managed_path = Path(managed)
    if not managed_path.is_dir():
        print(f"FAIL: HERMES_MANAGED_DIR not a directory: {managed}", file=sys.stderr)
        return 1
    cfg = managed_path / "config.yaml"
    if not cfg.is_file():
        print(f"FAIL: missing Managed Scope config: {cfg}", file=sys.stderr)
        return 1

    try:
        _ensure_hermes_importable()
        from hermes_cli.managed_scope import get_managed_dir  # type: ignore
        from hermes_cli.main import _has_any_provider_configured  # type: ignore

        resolved = get_managed_dir()
        if resolved is None or Path(resolved).resolve() != managed_path.resolve():
            print(
                f"FAIL: hermes get_managed_dir()={resolved!r} "
                f"(expected {managed})",
                file=sys.stderr,
            )
            return 1
        if not _has_any_provider_configured():
            print(
                "FAIL: Managed Scope present but no usable provider "
                "(_has_any_provider_configured=False). Check managed "
                f"{cfg} + {managed_path / '.env'}.",
                file=sys.stderr,
            )
            return 1
    except Exception as exc:
        if os.environ.get("HERMES_ASSERT_MANAGED_FILES_ONLY") == "1":
            print(f"OK: managed files present (import skip: {exc})")
            return 0
        print(
            f"FAIL: cannot verify provider via hermes import ({exc}). "
            "Run with hermes venv python, or set "
            "HERMES_ASSERT_MANAGED_FILES_ONLY=1 for file-only check.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: Managed Scope active dir={managed} provider=yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
