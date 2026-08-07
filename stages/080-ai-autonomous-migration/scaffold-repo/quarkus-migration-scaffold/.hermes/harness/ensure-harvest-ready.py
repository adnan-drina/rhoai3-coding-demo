#!/usr/bin/env python3
"""O-HARVESTREADY — orchestrate harvest compile-readiness before O-T6 / worker.

See ``harvest_ready.py`` for the architectural contract. This entrypoint:

1. Collects on-disk Java signals (validation / mapstruct / jpa).
2. Runs registered ensurer plugins in a fixed order (deps before jdbc wire).
3. Prints one machine-readable line for supervisor logging.

Plugins keep their bank ids (O-VALDEPADD / O-MAPPRESEED / O-DSKIND). New
implied capabilities MUST register here — do not add a parallel supervisor
``if`` wire.

Exit 0 always on successful scan/run (skip is ok). Exit 2 on misuse.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
HARNESS = Path(__file__).resolve().parent

# Ordered: content transforms first (SPRINGRESIDUE), then classpath ensurers.
# (signal names match harvest_ready.SIGNAL_*)
ENSURERS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("spring", "ensure-harvest-spring-clean.py", frozenset({"spring"})),
    ("valdep", "ensure-hibernate-validator-pom.py", frozenset({"validation"})),
    ("mapstruct", "ensure-mapstruct-pom.py", frozenset({"mapstruct"})),
    ("dskind", "ensure-dskind.py", frozenset({"jpa"})),
)


def _run_plugin(script: str) -> str:
    path = HARNESS / script
    if not path.is_file():
        return f"missing:{script}"
    try:
        proc = subprocess.run(
            [sys.executable, str(path), str(ROOT)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"error:{exc}"
    line = (proc.stdout or "").strip().splitlines()
    out = line[-1] if line else f"rc={proc.returncode}"
    if proc.returncode != 0:
        return f"rc={proc.returncode}:{out}"
    return out


def _pom_dirty() -> bool:
    pom = ROOT / "pom.xml"
    if not pom.is_file():
        return False
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", "pom.xml"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return bool((proc.stdout or "").strip())


def main() -> int:
    sys.path.insert(0, str(HARNESS))
    from harvest_ready import collect_signals  # noqa: WPS433

    sigs = collect_signals(ROOT)
    if not sigs:
        print("ok:signals=none|ran=|pom=0")
        return 0

    ran: list[str] = []
    for name, script, need in ENSURERS:
        if not (sigs & need):
            continue
        ran.append(f"{name}:{_run_plugin(script)}")

    pom = 1 if _pom_dirty() else 0
    print(
        "ok:signals="
        + ",".join(sorted(sigs))
        + "|ran="
        + ",".join(ran)
        + f"|pom={pom}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
