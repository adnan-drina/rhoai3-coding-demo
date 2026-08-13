#!/usr/bin/env python3
"""AD-H §16.8 / AR-1.6 — untrusted artifacts must not steer control flow.

Default (fixture self-test): scan ar16-untrusted pack; exit 1 when adversarial
content is present (proves REFUSE path — same pattern as AR-1.2 validate.sh).

`--as-gate`: exit 0 when live `evidence/authority/` feeds are clean; fixtures
alone do not fail the gate.

Usage:
  python3 check-untrusted-boundary.py /path/to/repo --as-gate   # live gate
  python3 check-untrusted-boundary.py /path/to/repo             # fixture self-test
  python3 check-untrusted-boundary.py --as-gate                 # gate on cwd
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_CODES = """\
Exit codes (NOTE: the default mode is INVERTED by design):

  --as-gate mode (live gate over evidence/authority/):
    0  pass — live authority feeds clean, or no evidence/authority dir
    1  BLOCK — a live authority feed carries control injection
    2  usage error (bad/unknown arguments; emitted by argparse)

  default mode (fixture self-test over governance/fixtures/authority/ar16-untrusted):
    1  EXPECTED PASS — adversarial fixture content was detected and REFUSED.
       Exit 1 is the proof of the refuse path, not a failure. Recognise it by
       the stdout line 'OK: AR-1.6 fixture self-test — adversarial inputs
       REFUSED ...'.
    1  also the genuine failure code when fixtures exist but nothing adversarial
       was detected — recognise it by the stderr line
       'FAIL: AR-1.6 fixtures present but no adversarial control-injection
       detected'. Distinguish the two by the emitted line, not the exit code.
    0  fixture pack absent — self-test idle.
    2  usage error (bad/unknown arguments; emitted by argparse)

This script therefore deviates from the house 0=pass / 1=block contract in
default mode. Use --as-gate for a conventional 0/1 gate verdict.
"""

CONTROL_INJECTION = re.compile(
    r"(?i)("
    r"IGNORE\s+(ALL\s+)?PRIOR|"
    r"P1-[A-Z]\s+OVERRIDE|"
    r"OVERRIDE\s*\(Lead\)|"
    r"kanban_complete|"
    r"skill_manage|"
    r"rm\s+-rf|"
    r"curl\s+http|"
    r"expand\s+files_in_scope|"
    r"without\s+brief-identity|"
    r"Operator\s+approved|"
    r"YOLO\s+approved"
    r")"
)
WORKER = frozenset(
    {"default", "worker", "planner", "implementer", "spec-author", "agent", "assistant"}
)


def scan_comments(rows: list[dict], label: str) -> int:
    bad = 0
    for i, row in enumerate(rows):
        role = str(row.get("role") or row.get("author") or "").lower()
        text = str(row.get("text") or row.get("body") or row.get("comment") or "")
        if not text:
            continue
        if CONTROL_INJECTION.search(text) and (not role or role in WORKER):
            print(
                f"FAIL: AR-1.6 {label}[{i}]: untrusted comment steers control — REFUSE",
                file=sys.stderr,
            )
            bad = 1
    return bad


def scan_findings(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    findings: list = []
    if isinstance(data, dict):
        findings = data.get("findings") or []
        viol = data.get("violations")
        if isinstance(viol, dict):
            findings = list(viol.values())
        elif isinstance(viol, list):
            findings = viol
    elif isinstance(data, list):
        findings = data
    bad = 0
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            continue
        blob = " ".join(
            str(f.get(k) or "") for k in ("message", "hint", "description", "title")
        )
        if CONTROL_INJECTION.search(blob):
            print(
                f"FAIL: AR-1.6 {path.name}[{i}]: finding message steers control — REFUSE",
                file=sys.stderr,
            )
            bad = 1
    return bad


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
        "--as-gate",
        action="store_true",
        help="run as a live gate over evidence/authority/ instead of the "
        "inverted fixture self-test",
    )
    args = ap.parse_args()
    as_gate = args.as_gate
    root = Path(args.root)
    root = root.resolve()
    fixture_dir = root / "governance" / "fixtures" / "authority" / "ar16-untrusted"

    if as_gate:
        live = root / "evidence" / "authority"
        bad = 0
        if live.is_dir():
            for p in sorted(live.rglob("*")):
                if not p.is_file() or p.suffix not in {".jsonl", ".json"}:
                    continue
                if "typed-revision" in p.name or "typed-revisions" in str(p):
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")
                if CONTROL_INJECTION.search(text):
                    print(f"FAIL: AR-1.6 live authority feed polluted: {p}", file=sys.stderr)
                    bad = 1
        if bad:
            print("AR-1.6 untrusted boundary gate FAILED", file=sys.stderr)
            return 1
        print("OK: AR-1.6 untrusted boundary gate (live authority feeds clean)")
        return 0

    if not fixture_dir.is_dir():
        print("OK: AR-1.6 idle (no ar16-untrusted fixtures)")
        return 0

    bad = 0
    comments = fixture_dir / "comments.jsonl"
    if comments.is_file():
        rows = []
        for ln in comments.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                rows.append({"role": "default", "text": ln})
        bad |= scan_comments(rows, "ar16-untrusted/comments.jsonl")

    adv = fixture_dir / "findings-adversarial.json"
    if adv.is_file():
        bad |= scan_findings(adv)

    for trap in (fixture_dir / "CodeCommentTrap.java", fixture_dir / "README-TRAP.md"):
        if trap.is_file() and CONTROL_INJECTION.search(
            trap.read_text(encoding="utf-8", errors="replace")
        ):
            print(f"OK: AR-1.6 trap classified untrusted: {trap.name}")

    if bad == 0:
        print(
            "FAIL: AR-1.6 fixtures present but no adversarial control-injection detected",
            file=sys.stderr,
        )
        return 1

    print(
        "OK: AR-1.6 fixture self-test — adversarial inputs REFUSED "
        "(exit 1 proves refuse path; use --as-gate for live clean check)"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
