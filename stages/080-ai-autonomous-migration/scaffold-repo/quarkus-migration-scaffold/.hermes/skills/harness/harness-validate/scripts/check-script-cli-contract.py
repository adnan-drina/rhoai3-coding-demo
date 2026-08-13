#!/usr/bin/env python3
"""R-SK.12 — bundled scripts must honour the official agent CLI contract.

Official guidance (agentskills.io/skill-creation/using-scripts) calls `--help`
"the primary way an agent learns your script's interface". Two failure modes
found in the E-20260813T125813Z audit make that actively dangerous here:

  1. SYNTAX  — a shell entry point that does not parse. `dispatch-phase.sh` and
     `create-m3-implementer.sh` both carried orphaned `|| die` continuations
     left behind when a command was commented out, so NO phase could dispatch.

  2. FALSE-GREEN HELP — ~36 gate scripts parse argv positionally, ignore
     `--help`, run the gate against a default root, and print `OK: <gate> idle`
     with exit 0. An agent probing the interface receives what looks like a
     PASSING GATE VERDICT and may bank it as evidence. A gate that cannot be
     asked what it is must never answer "everything is fine".

Checks, per bundled script under <skills-root>:
  A. every *.sh parses (`bash -n`)
  B. every *.py compiles (py_compile)
  C. `--help` must NOT print an OK:/PASS verdict line, and must not exit 0
     while doing so. Emitting usage (exit 0) or rejecting the flag (exit 2)
     are both acceptable; answering with a gate verdict is not.

Usage:
  python3 check-script-cli-contract.py --root .hermes/skills
  python3 check-script-cli-contract.py --root .hermes/skills --only help

Exit codes:
  0  all bundled scripts honour the contract
  1  one or more violations (printed as SCRIPT:RULE:detail)
  2  usage / bad root
"""
from __future__ import annotations

import argparse
import py_compile
import re
import subprocess
import tempfile
import sys
from pathlib import Path

VERDICT_PREFIXES = ("OK:", "PASS:", "OK ", "PASS ")
# Summary lines are also pass-shaped answers to an interface probe
# (Deputy E-20260813T140743Z / E-20260813T144954Z P2). Keep this list of
# known suite-summary keys — do not match arbitrary ENV=1 examples in --help.
VERDICT_SUMMARY_RX = re.compile(
    r"\b(VIOLATIONS|CHECKED|BUNDLES|SCRIPTS|HERMETICITY_FILES|GOLDEN_CLEANLINESS_FILES)=\d+"
)
SKIP_DIRS = {"__pycache__", "examples", "assets", "references", "templates"}
# Library modules are imported, never invoked as an agent entry point.
LIB_SUFFIXES = ("_lib.py", "specimen_agnostic.py", "verdict.py", "resolve_loaded_soul.py")


def bundled_scripts(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in {".py", ".sh"}:
            continue
        if set(p.parts) & SKIP_DIRS:
            continue
        if "scripts" not in p.parts:
            continue
        out.append(p)
    return out


def is_entry_point(path: Path) -> bool:
    if path.name.endswith(LIB_SUFFIXES):
        return False
    return "__main__" in path.read_text(encoding="utf-8", errors="replace") or path.suffix == ".sh"


def check_syntax(path: Path) -> list[str]:
    rel = path.as_posix()
    if path.suffix == ".sh":
        r = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
        if r.returncode != 0:
            first = (r.stderr.strip().splitlines() or ["parse error"])[0]
            return [f"{rel}:R-SK.12-SYNTAX:{first}"]
        return []
    with tempfile.TemporaryDirectory() as td:
        try:
            py_compile.compile(
                str(path), doraise=True, cfile=str(Path(td) / "out.pyc")
            )
        except py_compile.PyCompileError as exc:
            return [f"{rel}:R-SK.12-SYNTAX:{str(exc).splitlines()[0]}"]
    return []


def check_help(path: Path) -> list[str]:
    rel = path.as_posix()
    cmd = ["bash", str(path), "--help"] if path.suffix == ".sh" else [
        sys.executable, str(path), "--help"
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    except subprocess.TimeoutExpired:
        return [f"{rel}:R-SK.12-HELP:--help hung (agents run non-interactively)"]
    except Exception as exc:  # pragma: no cover - environment dependent
        return [f"{rel}:R-SK.12-HELP:could not invoke ({exc})"]
    combined = (r.stdout or "") + (r.returncode == 0 and "" or "")
    for line in (r.stdout or "").splitlines():
        s = line.strip()
        if s.startswith(VERDICT_PREFIXES) or VERDICT_SUMMARY_RX.search(s):
            return [
                f"{rel}:R-SK.12-HELP:--help emitted a gate verdict "
                f"({s[:60]!r}) with exit {r.returncode} — an interface probe "
                f"must never read as a PASS"
            ]
    del combined
    return []


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--root", default=".hermes/skills", help="skills root to scan")
    ap.add_argument(
        "--only",
        choices=("syntax", "help", "all"),
        default="all",
        help="restrict to one check family (default: all)",
    )
    args = ap.parse_args()
    root = Path(args.root)
    if not root.is_dir():
        print(f"Error: --root must be an existing directory. Received: {args.root!r}", file=sys.stderr)
        return 2

    scripts = bundled_scripts(root)
    errs: list[str] = []
    checked = 0
    for p in scripts:
        checked += 1
        if args.only in ("syntax", "all"):
            errs += check_syntax(p)
        if args.only in ("help", "all") and is_entry_point(p):
            errs += check_help(p)

    for e in errs:
        print(e, file=sys.stderr)
    print(f"SCRIPTS={checked} VIOLATIONS={len(errs)}")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
