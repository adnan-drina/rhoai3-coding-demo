#!/usr/bin/env python3
"""M1 verifier — mechanical artifacts only (Architect E-20260818T095340Z).

M1 ONLY. M3 waits. Script exit is the authority: refuse-on-nonzero.
Complete the M1 ACK GATE only on exit 0. Nonzero → typed needs_input;
do not kanban_complete the gate.

NOT a pre_tool_call complete-deny hook (Architect E-20260818T095728Z OBJECT).

Exit: 0=pass; 1=FAIL (refuse-on-nonzero); 2=missing harness script.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REQUIRED = (
    "evidence/derived/legacy-at-3.json",
    "evidence/entry-point-inventory.json",
    "evidence/mta-findings.json",
    "evidence/findings-handoff.json",
    "evidence/required-extensions.json",
)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    missing = [rel for rel in REQUIRED if not (root / rel).is_file()]
    if missing:
        print(
            "FAIL: refuse-on-nonzero — missing M1 artifacts: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 1
    handoff = (
        root
        / ".hermes"
        / "skills"
        / "analysis"
        / "scan-with-mta"
        / "scripts"
        / "check-findings-handoff.py"
    )
    if not handoff.is_file():
        print("FAIL: missing check-findings-handoff.py (harness)", file=sys.stderr)
        return 2
    proc = subprocess.run(
        [sys.executable, str(handoff), str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        print(
            f"FAIL: refuse-on-nonzero — check-findings-handoff exit {proc.returncode}",
            file=sys.stderr,
        )
        return 1 if proc.returncode == 1 else 2
    issuer = (
        root
        / ".hermes"
        / "skills"
        / "harness"
        / "enforce-authority-boundary"
        / "scripts"
        / "issue-m1-findings-ack.py"
    )
    if not issuer.is_file():
        print("FAIL: missing issue-m1-findings-ack.py (harness)", file=sys.stderr)
        return 2
    issued = subprocess.run(
        [sys.executable, str(issuer), str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if issued.stdout:
        sys.stdout.write(issued.stdout)
    if issued.stderr:
        sys.stderr.write(issued.stderr)
    if issued.returncode != 0:
        print(
            f"FAIL: refuse-on-nonzero — 5.1 issue-m1-findings-ack exit {issued.returncode}",
            file=sys.stderr,
        )
        return 1 if issued.returncode == 1 else 2
    print("OK: M1 verifier pass (refuse-on-nonzero would have blocked; 5.1 record issued)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
