#!/usr/bin/env python3
"""A: mandated actions in the official task log, not artefact presence.

GATE-VALIDATION-DESIGN.md §3 / Architect ``190526ZA``: compare claimed
process to ``$HERMES_HOME/kanban/logs/<task_id>.log``. Provenance, not
proof (same-uid). Dual-write KEEP — this does not replace PVC paths.

Negative first (§6): dest-9 M2 ``t_af875a24`` must REFUSE —
``specify workflow run speckit`` appears and never succeeds. A version
that PASSes that log has not implemented the check.

``--help`` is not the mandated run. ``kanban_complete`` around that red
is the dest-9 terminator, not a pass.

Exit 0: at least one non-help ``specify workflow run speckit`` with exit 0.
Exit 1: mandated run absent, or present and never succeeding.
Exit 2: usage / missing log.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

EXIT_RE = re.compile(r"\[exit (\d+)\]")
SPECIFY_RUN = "specify workflow run speckit"


def _fail(msg: str) -> int:
    print("REFUSE: CARD_PERFORMED " + msg, file=sys.stderr)
    return 1


def resolve_log(task_id: str | None, log: Path | None) -> Path | None:
    if log is not None:
        return log
    if not task_id:
        return None
    home = os.environ.get("HERMES_HOME", "")
    if not home:
        return None
    return Path(home) / "kanban" / "logs" / (task_id + ".log")


def specify_runs(text: str) -> list[tuple[str, int | None]]:
    """Hermes terminal invocations of ``specify workflow run speckit``.

    Reasoning/prose that *mentions* the argv is not a run. ``--help`` is
    not the mandated dispatch.
    """
    out: list[tuple[str, int | None]] = []
    for raw in text.splitlines():
        if SPECIFY_RUN not in raw:
            continue
        if "$" not in raw:
            continue
        cmd = raw.split("$", 1)[1]
        if "--help" in cmd:
            continue
        m = EXIT_RE.search(raw)
        rc = int(m.group(1)) if m else None
        out.append((raw.strip(), rc))
    return out


def evaluate(text: str) -> int:
    runs = specify_runs(text)
    unknown = "Unknown skill(s): speckit-specify" in text
    if not runs:
        return _fail(
            "mandated action absent from official log: " + SPECIFY_RUN
        )
    succeeded = [r for r in runs if r[1] == 0]
    if succeeded:
        print(
            "OK: CARD_PERFORMED specify workflow run speckit exit 0 "
            "(%s non-help run(s))" % len(runs)
        )
        return 0
    exits = [str(r[1]) if r[1] is not None else "omitted" for r in runs]
    extra = ""
    if unknown:
        extra = "; Unknown skill(s): speckit-specify"
    if "preparing kanban_complete" in text or "kanban_complete call succeeded" in text:
        extra += "; kanban_complete around speckit red"
    return _fail(
        "specify workflow run speckit never succeeded "
        "(runs=%s exits=%s%s). tasks.md presence is B, not A."
        % (len(runs), ",".join(exits), extra)
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task_id", nargs="?", help="t_… (reads $HERMES_HOME/kanban/logs)")
    ap.add_argument(
        "--log",
        type=Path,
        help="official log path (workshop fixture; dest-9 t_af875a24)",
    )
    args = ap.parse_args(argv)
    path = resolve_log(args.task_id, args.log)
    if path is None:
        return 2
    if not path.is_file():
        return _fail("missing official log %s" % path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return _fail("unreadable official log %s: %s" % (path, exc))
    return evaluate(text)


if __name__ == "__main__":
    raise SystemExit(main())
