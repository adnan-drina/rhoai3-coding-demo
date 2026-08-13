#!/usr/bin/env python3
"""AD-H §16.4 / ER#2 F2 — seat probe: prohibited writes must fail.

Exit 0 only when every deny-path probe gets PermissionError (or equivalent)
after apply-write-fence.sh lock. Does not claim release_qualified.

This probe MUTATES the tree under ROOT: it attempts (and, where the fence is
absent, succeeds at) creating and deleting probe files under evidence/acks,
evidence/verdicts, .hermes/skills and governance/fixtures. Point it at the
workspace you actually mean to probe.

Usage:
  python3 probe-write-fence.py                 # probe the current directory
  python3 probe-write-fence.py /path/to/repo   # probe an explicit root
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

EXIT_CODES = """\
Exit codes:
  0  pass — every deny path refused the write AND the positive control was
     still writable (fence effective, not a total lockdown)
  1  BLOCK — at least one FAIL: line on stderr (a deny path accepted the write,
     i.e. the fence is not effective; or the positive control was not writable,
     i.e. the fence is too broad)
  2  usage error (bad/unknown arguments; emitted by argparse)
"""

DENY_PROBE_RELS = (
    "evidence/acks/.f2-seat-probe",
    "evidence/verdicts/.f2-seat-probe",
    ".hermes/skills/.f2-seat-probe",
)


def try_write(path: Path) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return f"mkdir_{type(e).__name__}"
    try:
        path.write_text("f2-probe\n", encoding="utf-8")
        try:
            path.unlink()
        except OSError:
            pass
        return "WRITE_OK"
    except OSError as e:
        return f"{type(e).__name__}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="workspace root to probe — WRITES here (default: current directory)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    bad = 0
    results: list[tuple[str, str]] = []

    for rel in DENY_PROBE_RELS:
        path = root / rel
        outcome = try_write(path)
        results.append((rel, outcome))
        if outcome == "WRITE_OK":
            print(f"FAIL: probe wrote {rel} (fence not effective)", file=sys.stderr)
            bad = 1
        else:
            print(f"OK: probe denied {rel} ({outcome})")

    # Positive control: implementer must still write under src/ (or tmp under root)
    ctrl_dir = root / "governance" / "fixtures"
    ctrl_dir.mkdir(parents=True, exist_ok=True)
    # Prefer a path that should remain writable; fall back to tempfile under root
    ctrl = ctrl_dir / ".f2-positive-control"
    ctrl_outcome = try_write(ctrl)
    if ctrl_outcome != "WRITE_OK":
        # fixtures may be locked in some overlays — try tempfile in cwd root tmp
        fd, name = tempfile.mkstemp(prefix=".f2-pos-", dir=str(root))
        os.close(fd)
        ctrl = Path(name)
        try:
            ctrl.write_text("ok\n", encoding="utf-8")
            ctrl_outcome = "WRITE_OK"
        except OSError as e:
            ctrl_outcome = type(e).__name__
        finally:
            try:
                ctrl.unlink()
            except OSError:
                pass
    if ctrl_outcome != "WRITE_OK":
        print(
            f"FAIL: positive control not writable ({ctrl_outcome}) — fence too broad?",
            file=sys.stderr,
        )
        bad = 1
    else:
        print("OK: positive control writable (fence not total lockdown)")

    if bad:
        print("F2 seat probe FAILED", file=sys.stderr)
        return 1
    print("OK: F2 proving-min seat probe PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
