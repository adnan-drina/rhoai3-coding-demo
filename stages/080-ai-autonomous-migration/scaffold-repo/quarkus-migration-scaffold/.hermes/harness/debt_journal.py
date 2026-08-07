#!/usr/bin/env python3
"""ADR-48 (c) — debt.md is an append-only incident journal, not completion SoT.

Freeze-worthy sensor kinds (task|milestone|sonar|seat-budget) projected into
``migration/debt.md`` must never coexist with ledger ``state=ADVANCE`` for the
same task id (F-advance-debt / O-DEBTADVANCE).

Full migration of debt rows into ``model.json`` remains sequenced later.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FREEZE_WORTHY = frozenset({"task", "milestone", "sonar", "seat-budget"})

# Matches supervisor record_debt headers:
#   ## S02-TC-Foo — task RED
_FREEZE_HEADER = re.compile(
    r"^##\s+(\S+)\s+—\s+(task|milestone|sonar|seat-budget)\s+RED\s*$",
    re.MULTILINE,
)


def unresolved_freeze_debt(
    tid: str,
    *,
    debt_path: Path | None = None,
    root: Path | None = None,
) -> list[str]:
    """Return freeze-worthy kind names still open for ``tid`` in debt.md."""
    if not tid:
        return []
    path = debt_path
    if path is None:
        base = root if root is not None else Path(".")
        path = base / "migration" / "debt.md"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    kinds: list[str] = []
    for m in _FREEZE_HEADER.finditer(text):
        if m.group(1) == tid:
            kinds.append(m.group(2))
    return kinds


def advance_with_debt_forbidden(
    tid: str,
    *,
    debt_path: Path | None = None,
    root: Path | None = None,
) -> str:
    """Empty string if ok; else refusal detail for O-DEBTADVANCE."""
    kinds = unresolved_freeze_debt(tid, debt_path=debt_path, root=root)
    if not kinds:
        return ""
    return (
        f"O-DEBTADVANCE: {tid} has unresolved freeze-worthy debt "
        f"({', '.join(kinds)}) — ADVANCE unrepresentable (ADR-48c); "
        f"demote to DEBT or clear journal first"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("unresolved", "check-advance"))
    ap.add_argument("--task", required=True)
    ap.add_argument("--debt", default="migration/debt.md")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    debt = root / args.debt if not Path(args.debt).is_absolute() else Path(args.debt)
    if args.cmd == "unresolved":
        kinds = unresolved_freeze_debt(args.task, debt_path=debt)
        if not kinds:
            print("O-DEBTADVANCE:NONE")
            return 0
        print(f"O-DEBTADVANCE:UNRESOLVED {args.task} {' '.join(kinds)}")
        return 1
    detail = advance_with_debt_forbidden(args.task, debt_path=debt)
    if not detail:
        print("O-DEBTADVANCE:OK")
        return 0
    print(detail, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
