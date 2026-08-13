#!/usr/bin/env python3
"""AD-H §16.8 / AR-1.3 — one Kanban task ⇒ exactly one role.

Refuses:
  - phase-dispatch.yaml phase with missing/blank role
  - task packets declaring combined roles (planner+implementer, "a/b", list)
  - M2 planner/spec packets that claim destination source writes (seat probe)

Usage:
  python3 check-one-role-dispatch.py                        # current directory
  python3 check-one-role-dispatch.py /path/to/repo          # explicit root
  python3 check-one-role-dispatch.py /path/to/repo --fixtures
  python3 check-one-role-dispatch.py . extra/packet.json extra/packets/
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_CODES = """\
Exit codes:
  0  pass — phase-dispatch roles single-valued and every packet declares exactly
     one role; also printed when no phase-dispatch.yaml exists and no packet
     declares a role (packets_checked=0)
  1  BLOCK — at least one FAIL: line on stderr (missing/combined phase role,
     unparseable packet, absent or multi role, or an M2 source-write probe)
  2  usage error (bad/unknown arguments; emitted by argparse)
"""

COMBINED = re.compile(r"[+,/|]| and ")
M2_ROLES = frozenset({"planner", "spec-author", "spec_author"})
SRC_PREFIXES = ("src/", "src/main/", "src/test/")


def parse_phase_roles(text: str) -> dict[str, str]:
    roles: dict[str, str] = {}
    cur: str | None = None
    for ln in text.splitlines():
        m = re.match(r"^  (M[1-5]):\s*$", ln)
        if m:
            cur = m.group(1)
            continue
        if cur and re.match(r"^  [A-Za-z0-9_]+:\s*$", ln) and not re.match(
            r"^  M[1-5]:", ln
        ):
            cur = None
            continue
        if cur is None:
            continue
        rm = re.match(r"^    role:\s*(\S+)\s*$", ln)
        if rm:
            roles[cur] = rm.group(1).strip()
    return roles


def role_tokens(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip().lower() for x in raw if str(x).strip()]
    s = str(raw).strip().lower()
    if not s:
        return []
    if COMBINED.search(s):
        return [p.strip() for p in re.split(r"[+,/|]| and ", s) if p.strip()]
    return [s.replace("_", "-")]


def writes_of(obj: dict) -> list[str]:
    for key in ("writes", "files_touched", "files_written", "filesWritten"):
        v = obj.get(key)
        if isinstance(v, list):
            return [str(x) for x in v]
    return []


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
        help="workspace root to scan (default: current directory)",
    )
    ap.add_argument(
        "extra",
        nargs="*",
        metavar="PACKET",
        help="additional task-packet .json files or directories of them",
    )
    ap.add_argument(
        "--fixtures",
        action="store_true",
        help="also scan migration/fixtures/authority/ar13-one-role under root",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    bad = 0

    yml = root / ".hermes" / "phase-dispatch.yaml"
    if yml.is_file():
        roles = parse_phase_roles(yml.read_text(encoding="utf-8"))
        for phase in ("M1", "M2", "M3", "M4", "M5"):
            r = roles.get(phase)
            if not r:
                print(f"FAIL: AR-1.3 {phase} missing role in phase-dispatch.yaml", file=sys.stderr)
                bad = 1
            elif COMBINED.search(r):
                print(f"FAIL: AR-1.3 {phase} combined role {r!r}", file=sys.stderr)
                bad = 1
    else:
        print("OK: AR-1.3 idle (no phase-dispatch.yaml)")

    packets: list[Path] = []
    for d in (root / "migration/tasks", root / "migration/kanban"):
        if d.is_dir():
            packets.extend(sorted(d.glob("*.json")))
    # Explicit fixture self-test: pass fixture dir or --fixtures
    if args.fixtures:
        fix = root / "migration/fixtures/authority/ar13-one-role"
        if fix.is_dir():
            packets.extend(sorted(fix.glob("*.json")))
    for arg in args.extra:
        if arg.startswith("-"):
            continue
        p = Path(arg)
        if p.is_file() and p.suffix == ".json":
            packets.append(p)
        elif p.is_dir():
            packets.extend(sorted(p.glob("*.json")))

    checked = 0
    for path in packets:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"FAIL: {path}: {e}", file=sys.stderr)
            bad = 1
            continue
        items = data if isinstance(data, list) else [data]
        for i, obj in enumerate(items):
            if not isinstance(obj, dict):
                continue
            if "role" not in obj and "actor" not in obj and "roles" not in obj:
                continue
            checked += 1
            try:
                label = str(path.resolve().relative_to(root))
            except ValueError:
                label = str(path)
            if len(items) > 1:
                label = f"{label}[{i}]"
            toks = role_tokens(obj.get("roles") if obj.get("roles") is not None else obj.get("role") or obj.get("actor"))
            if len(toks) == 0:
                print(f"FAIL: AR-1.3 {label}: absent role", file=sys.stderr)
                bad = 1
                continue
            if len(toks) != 1:
                print(f"FAIL: AR-1.3 {label}: combined/multi role {toks}", file=sys.stderr)
                bad = 1
                continue
            role = toks[0].replace("_", "-")
            writes = writes_of(obj)
            if role in M2_ROLES or role == "spec-author":
                for w in writes:
                    wn = w.lstrip("./")
                    if any(wn == p.rstrip("/") or wn.startswith(p) for p in SRC_PREFIXES):
                        print(
                            f"FAIL: AR-1.3 {label}: M2 role={role} source-write probe "
                            f"refused path {w}",
                            file=sys.stderr,
                        )
                        bad = 1

    if bad:
        print("AR-1.3 one-role dispatch FAILED", file=sys.stderr)
        return 1
    print(f"OK: AR-1.3 one-role dispatch (packets_checked={checked})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
