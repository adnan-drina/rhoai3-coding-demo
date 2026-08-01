#!/usr/bin/env python3
"""N12 O-SENSORGATE — refuse migration commits when the task sensor is RED.

Usage:
  sensor-gate.py decide <sensor_rc>     # exit 0 allow / 1 refuse
  sensor-gate.py needs-gate <subject>   # exit 0 if subject must be gated
  sensor-gate.py install-hook <repo>    # write .git/hooks/commit-msg

Standing law: never commit a T-NNN / sensor-fix / preflight tip on a RED
task sensor (S02: 11 sensor_red_post_commit events). Post-commit reset
(O-SFIXSCOPE) remains as backstop; this is the pre-commit refuse.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_GATE_SUBJ = re.compile(
    r"^(T-\d+|S\d+\b|M[0-9] |Preflight fix|.*\bsensor fix:)",
    re.I,
)


def needs_gate(subject: str) -> bool:
    return bool(_GATE_SUBJ.search((subject or "").strip()))


def decide(sensor_rc: int) -> int:
    """0 = allow commit, 1 = refuse."""
    return 0 if sensor_rc == 0 else 1


_HOOK = r'''#!/bin/bash
# O-SENSORGATE (N12) — installed by sensor-gate.py; do not hand-edit.
set -euo pipefail
MSG_FILE="${1:-}"
[ -n "$MSG_FILE" ] && [ -f "$MSG_FILE" ] || exit 0
[ "${SKIP_SENSOR_GATE:-0}" = "1" ] && exit 0
subj=$(head -1 "$MSG_FILE" || true)
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
GATE="$ROOT/.hermes/harness/sensor-gate.py"
SENSORS="$ROOT/.hermes/harness/sensors.sh"
[ -f "$GATE" ] || exit 0
python3 "$GATE" needs-gate "$subj" || exit 0
[ -x "$SENSORS" ] || [ -f "$SENSORS" ] || exit 0
if ! "$SENSORS" task > /tmp/sensor-gate-hook.log 2>&1; then
  echo "O-SENSORGATE: refusing commit — task sensor RED (see /tmp/sensor-gate-hook.log)" >&2
  exit 1
fi
exit 0
'''


def install_hook(repo: Path) -> int:
    hooks = repo / ".git" / "hooks"
    if not (repo / ".git").exists():
        print("NO_GIT", file=sys.stderr)
        return 2
    hooks.mkdir(parents=True, exist_ok=True)
    path = hooks / "commit-msg"
    path.write_text(_HOOK, encoding="utf-8")
    path.chmod(0o755)
    print(f"INSTALLED {path}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: sensor-gate.py decide|needs-gate|install-hook …", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "decide":
        if len(argv) < 3:
            return 2
        try:
            rc = int(argv[2])
        except ValueError:
            return 2
        return decide(rc)
    if cmd == "needs-gate":
        subj = argv[2] if len(argv) > 2 else ""
        return 0 if needs_gate(subj) else 1
    if cmd == "install-hook":
        root = Path(argv[2] if len(argv) > 2 else ".")
        return install_hook(root.resolve())
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
