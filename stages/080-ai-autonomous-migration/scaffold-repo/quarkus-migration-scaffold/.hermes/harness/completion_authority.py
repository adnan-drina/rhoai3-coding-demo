#!/usr/bin/env python3
"""ADR-48 — typed completion authority (prose is never a writer of outcome).

Seat end-state is decided by harness probes + the lifecycle ledger.
LLM escalation-noaction files are *requests* resolved here.

Verdicts:
  DISPATCH                 — task must run / continue
  SKIP_ALREADY             — already-complete.py said skip (caller may tip ALREADY COMPLETE)
  ADVANCE_OK               — ledger state is ADVANCE (completion stands)
  REJECT_COMPLETION_CLAIM  — prose claimed already-complete while state ≠ ADVANCE

Exit codes (CLI --resolve-null-action):
  0 — accept null_action (honest stop; not a false completion claim)
  1 — reject completion claim (caller must continue seat)
  2 — usage / IO error
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_HARNESS_DIR = Path(__file__).resolve().parent
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))

ADVANCE = "ADVANCE"

_ALREADY_COMPLETE_CLAIM = re.compile(
    r"already\s+complet(?:ed|e)\b|"
    r"already\s+satisfied\b|"
    r"already\s+exists\b|"
    r"no\s+action\s+needed\b|"
    r"task\s+\S+\s+already\s+completed\b",
    re.I,
)


def _load_row(tid: str, ledger_path: Path) -> dict:
    if not ledger_path.is_file():
        return {}
    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return (data.get("tasks") or {}).get(tid) or {}


def is_completion_claim(reason: str) -> bool:
    return bool(_ALREADY_COMPLETE_CLAIM.search(reason or ""))


def resolve_null_action(
    tid: str,
    reason: str,
    *,
    ledger_path: Path | None = None,
    root: Path | None = None,
) -> tuple[str, str]:
    """Return (verdict, detail).

    REJECT_COMPLETION_CLAIM when prose asserts completion but ledger is not
    ADVANCE — reopen / in-flight tasks cannot be closed by essay.
    Also rejects when ADVANCE∥freeze-worthy debt.md (ADR-48c / O-DEBTADVANCE).
    """
    base = ledger_path or Path("migration/task-lifecycle.json")
    debt_root = root if root is not None else Path(".")
    row = _load_row(tid, base)
    state = str(row.get("state") or "READY")
    text = (reason or "").strip()
    if not text:
        return "DISPATCH", "empty null_action reason"
    if is_completion_claim(text):
        if state != ADVANCE:
            return (
                "REJECT_COMPLETION_CLAIM",
                (
                    f"ADR-48: completion claim refused — ledger state={state} "
                    f"(not ADVANCE); reopen_gen={row.get('reopen_gen', 0)}; "
                    f"tip_sha observation={(str(row.get('tip_sha') or '')[:12] or 'none')}"
                ),
            )
        # ADR-48 (c): ADVANCE∥freeze-debt is unrepresentable — refuse completion.
        try:
            from debt_journal import advance_with_debt_forbidden
        except ImportError:
            sys.path.insert(0, str(_HARNESS_DIR))
            from debt_journal import advance_with_debt_forbidden
        refuse = advance_with_debt_forbidden(tid, root=debt_root)
        if refuse:
            return "REJECT_COMPLETION_CLAIM", refuse
        return "ADVANCE_OK", f"ledger ADVANCE; tip_sha={str(row.get('tip_sha') or '')[:12]}"
    # Honest non-completion stop (oracle absent, later dep, …)
    return "DISPATCH", "non-completion null_action request (supervisor may record debt)"


def tip_is_authority() -> bool:
    """ADR-48 (a): tip_sha must never be treated as restore authority."""
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", required=True)
    ap.add_argument("--reason-file", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--ledger", default="migration/task-lifecycle.json")
    ap.add_argument("--root", default=".")
    ap.add_argument(
        "--resolve-null-action",
        action="store_true",
        help="exit 0 accept / 1 reject completion claim",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    reason = args.reason
    if args.reason_file:
        rf = Path(args.reason_file)
        if not rf.is_file():
            print(f"completion_authority: missing {rf}", file=sys.stderr)
            return 2
        reason = rf.read_text(encoding="utf-8", errors="replace")
    verdict, detail = resolve_null_action(
        args.task,
        reason,
        ledger_path=root / args.ledger,
        root=root,
    )
    print(f"O-COMPLETION:{verdict} {detail}")
    if args.resolve_null_action:
        if verdict == "REJECT_COMPLETION_CLAIM":
            print(detail, file=sys.stderr)
            return 1
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
