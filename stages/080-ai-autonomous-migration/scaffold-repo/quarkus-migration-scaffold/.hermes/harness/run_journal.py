#!/usr/bin/env python3
"""ADR-43 — single-sourced run-journal addressing.

Three log classes (W4-602 / ADR-43):
  EPHEMERAL     — scratch; deletable by its writer
  RUN-JOURNAL   — evidence of run R; addressed by run_id; never overwritten
  DURABLE       — repo artifacts (ADR-36/39); out of scope here

Callers construct journal paths ONLY through this module. Archiver copies
``journal_files()`` wholesale — no parallel glob lists for journal content.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

RUN_ID_ENV = "HARNESS_RUN_ID"
JOURNAL_ROOT_ENV = "HARNESS_JOURNAL_ROOT"
DEFAULT_JOURNAL_ROOT = Path("/tmp/hj")

_PHASES = frozenset({"m1", "m2", "m3", "m4", "m5", "outer", "gate"})

# Paths that remain scratch (may be deleted freely). Not exhaustive — used by
# is_ephemeral() for cleaner decisions; unknown paths default to journal-safe.
_EPHEMERAL_NAME_RE = re.compile(
    r"(?:^|/)(?:"
    r"sensor-[^/]+\.log|"
    r"sonar-violations\.txt|"
    r"style-autofix\.log|"
    r"[^/]*-failure\.txt|"
    r"outer-heartbeat-progress\.txt|"
    r"v10-wake-oc\.err"
    r")$"
)


def run_id() -> str:
    """Return HARNESS_RUN_ID; create ``<utcTs>-<shortSha>`` if unset."""
    rid = (os.environ.get(RUN_ID_ENV) or "").strip()
    if rid:
        return rid
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sha = "unknown"
    try:
        import subprocess

        sha = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            or "unknown"
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass
    rid = f"{ts}-{sha}"
    os.environ[RUN_ID_ENV] = rid
    return rid


def journal_root(rid: Optional[str] = None) -> Path:
    base = Path(os.environ.get(JOURNAL_ROOT_ENV) or DEFAULT_JOURNAL_ROOT)
    root = base / (rid or run_id())
    root.mkdir(parents=True, exist_ok=True)
    return root


def phase_dir(phase: str, rid: Optional[str] = None) -> Path:
    p = (phase or "outer").lower().strip()
    if p not in _PHASES:
        # Unknown phase still gets a directory — F-archive-covers-journal.
        p = re.sub(r"[^a-z0-9_-]+", "-", p)[:40] or "other"
    d = journal_root(rid) / p
    d.mkdir(parents=True, exist_ok=True)
    return d


def seat_log(phase: str, unit: str, attempt: int = 1, rid: Optional[str] = None) -> Path:
    """Append-only seat transcript: ``<phase>/<unit>.attempt<N>.log``."""
    u = re.sub(r"[^A-Za-z0-9._-]+", "-", (unit or "seat").strip())[:120] or "seat"
    n = max(1, int(attempt))
    path = phase_dir(phase, rid) / f"{u}.attempt{n}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def journal_files(rid: Optional[str] = None) -> list[Path]:
    """Every file under the run journal — the ONLY journal enumeration."""
    root = journal_root(rid)
    if not root.is_dir():
        return []
    out: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            out.append(Path(dirpath) / name)
    return sorted(out)


def is_ephemeral(path: Path | str) -> bool:
    p = str(path).replace("\\", "/")
    if "/hj/" in p or p.startswith(str(DEFAULT_JOURNAL_ROOT)):
        return False
    return bool(_EPHEMERAL_NAME_RE.search(p))


def archive_journal_to(dest: Path, rid: Optional[str] = None) -> int:
    """Copy journal_files() into dest/journal/ (wholesale). Returns file count."""
    dest = Path(dest)
    jdest = dest / "journal"
    jdest.mkdir(parents=True, exist_ok=True)
    n = 0
    root = journal_root(rid)
    for src in journal_files(rid):
        try:
            rel = src.relative_to(root)
        except ValueError:
            rel = Path(src.name)
        target = jdest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, target)
            n += 1
        except OSError:
            continue
    (dest / "JOURNAL_RUN_ID.txt").write_text(
        f"{rid or run_id()}\n", encoding="utf-8"
    )
    return n


def cmd_ensure(_args: argparse.Namespace) -> int:
    root = journal_root()
    print(f"HARNESS_RUN_ID={run_id()}")
    print(f"journal_root={root}")
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    n = archive_journal_to(Path(args.dest))
    print(f"archived_journal_files={n}")
    return 0


def cmd_seat(args: argparse.Namespace) -> int:
    p = seat_log(args.phase, args.unit, attempt=args.attempt)
    print(p)
    return 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="ADR-43 run journal")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("ensure")
    e.set_defaults(func=cmd_ensure)
    a = sub.add_parser("archive-to")
    a.add_argument("dest")
    a.set_defaults(func=cmd_archive)
    s = sub.add_parser("seat-log")
    s.add_argument("phase")
    s.add_argument("unit")
    s.add_argument("--attempt", type=int, default=1)
    s.set_defaults(func=cmd_seat)
    args = ap.parse_args(list(argv) if argv is not None else None)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
