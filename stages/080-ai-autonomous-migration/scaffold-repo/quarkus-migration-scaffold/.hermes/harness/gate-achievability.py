#!/usr/bin/env python3
"""N14 O-GATEACHIEVE — classify ship/preflight RED as code-fixable vs decision-needed.

Decision-needed (do not burn MiniMax seats): Sonar new_coverage gap ≥ threshold
points with no issue/violation blockers. Code-fixable: violations, compile,
fidelity, hotspots, residue.

Usage:
  gate-achievability.py <preflight-or-sonar-log>

Exit 0 = code-fixable (dispatch fix).
Exit 10 = decision-needed (page operator; write /tmp/gate-decision-needed.txt).
Exit 1 = unparsed / treat as code-fixable (fail-open to fix attempt).

D2 durable form: factory keeps the 80% new_coverage bar; this triage stops
unachievable coverage chases from consuming ship-fix attempts.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Points below the gate before we treat coverage as a policy decision.
# S02 witness: 38.6 vs 80 → 41.4 pt gap burned a full fix round.
COVERAGE_DECISION_GAP = float(
    __import__("os").environ.get("GATE_COVERAGE_DECISION_GAP", "15")
)


def classify(text: str) -> str:
    t = text or ""
    # Explicit compile / test / fidelity failures → always code-fixable
    if re.search(
        r"(?i)COMPILATION ERROR|BUILD FAILURE|Tests run:.*(Failures|Errors): [1-9]"
        r"|FIDELITY|harvest.fidelity|UnsatisfiedResolution|SENSOR RED",
        t,
    ):
        return "code-fixable"
    if re.search(r"(?i)QUALITYGATE FAIL .*(blocker|critical|major|violat|issue|hotspot)", t):
        return "code-fixable"
    if re.search(r"(?i)\b(BLOCKER|CRITICAL)\b.*java:S", t):
        return "code-fixable"

    cov = re.search(
        r"COVERAGE new_coverage=([0-9.]+)%\s*\(gate requires >=\s*([0-9.]+)%\)",
        t,
    )
    if not cov:
        cov = re.search(
            r"new_coverage[=:]?\s*([0-9.]+).*?(?:threshold|requires|gate)[^\d]*([0-9.]+)",
            t,
            re.I,
        )
    if cov:
        actual = float(cov.group(1))
        need = float(cov.group(2))
        gap = need - actual
        # Coverage-only (or coverage-dominant) RED with large gap → decision
        has_issue_blockers = bool(
            re.search(r"(?i)issues?=|[1-9]\d*\s+(blocker|critical|major)", t)
        )
        if gap >= COVERAGE_DECISION_GAP and not has_issue_blockers:
            return "decision-needed"
        return "code-fixable"

    qg = re.search(
        r"QUALITYGATE FAIL[^\n]*new_coverage[^\n]*actual=([0-9.]+)[^\n]*threshold=([0-9.]+)",
        t,
        re.I,
    )
    if qg:
        gap = float(qg.group(2)) - float(qg.group(1))
        if gap >= COVERAGE_DECISION_GAP:
            return "decision-needed"

    return "code-fixable"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: gate-achievability.py <log>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    kind = classify(text)
    print(kind)
    if kind == "decision-needed":
        out = Path("/tmp/gate-decision-needed.txt")
        out.write_text(
            "O-GATEACHIEVE / N14: decision-needed RED — do not burn ship-fix seats.\n"
            f"coverage gap ≥ {COVERAGE_DECISION_GAP} pts (D2 durable form: keep factory "
            "80% bar; operator/page to fund tests or restate bar).\n"
            f"source: {path}\n",
            encoding="utf-8",
        )
        return 10
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
