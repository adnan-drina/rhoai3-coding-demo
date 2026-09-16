#!/usr/bin/env python3
"""Bind a composed M4 verdict to the card and the evidence it judged.

The verdict's measured content -- the floors, their exit codes, `failed_floors`,
the token, the coverage account -- is composed by the worker from what the
floors actually returned, and this tool NEVER touches any of it. What it writes
are the three facts no worker should be writing from memory:

  * `card_id`              ← `verification/loop/issued.json` `task_id`
                             (the issued close card; `$HERMES_KANBAN_TASK` when
                             the card was minted but the tree has not recorded
                             its id yet)
  * `receipt_sha256`       ← the same file's `receipt_sha256` (the admission
                             receipt the card was minted under)
  * `parity_receipt_sha256`← the digest of `verification/parity/receipt.json`
                             itself (the parity evidence the verdict judged)

v9's second M4 card is why this exists. It composed an honest `REFUSE` and
wrote no `card_id`, because the field was optional and the earlier card's
worker had typed one by hand. Nothing refused it, the card completed, and
`resume-after-m4.py` then had a measurement it could not attribute to a run.
Binding is mechanical, so it is done by a tool and asserted by a lint
(`assert-m4-verdict-schema.py`), which refuses a verdict whose bindings are
missing, stale or foreign.

Run it immediately after authoring the verdict, and re-run it on a verdict that
lacks the bindings -- never edit them in by hand, and never re-bind a verdict to
a parity receipt it did not judge (if the parity phase has run again since, the
verdict is stale: re-run the road and compose a new one).

Exit 0 bound, 1 an input the binding is read from is missing or unusable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

VERDICT = Path("evidence") / "verdicts" / "m4-verdict.json"
ISSUED = Path("verification") / "loop" / "issued.json"
PARITY_RECEIPT = Path("verification") / "parity" / "receipt.json"


def _fail(msg: str) -> int:
    print("FAIL: M4_VERDICT_BINDING " + msg, file=sys.stderr)
    return 1


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_canonical(path: Path, doc: Any) -> None:
    """The canonical form the planner artifacts use (planner.canonical), spelled
    out so this tool stays stdlib-only and can run wherever the verdict is."""
    path.write_bytes(
        (json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."), help="destination root (default: cwd)")
    ap.add_argument("--verdict", type=Path, default=None, help="default: <root>/%s" % VERDICT.as_posix())
    args = ap.parse_args(argv)
    root = args.root.resolve()
    vp = (args.verdict if args.verdict else root / VERDICT).resolve()

    if not vp.is_file():
        return _fail("no composed verdict at %s; compose-m4-verdict authors it first, this only binds it" % vp)
    try:
        verdict = _load(vp)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail("unreadable verdict %s: %s" % (vp, exc))
    if not isinstance(verdict, dict):
        return _fail("%s is not a verdict object" % vp)

    ip = root / ISSUED
    if not ip.is_file():
        return _fail("no %s; there is no issued card to bind this verdict to" % ISSUED.as_posix())
    try:
        issued = _load(ip)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail("unreadable %s: %s" % (ISSUED.as_posix(), exc))
    if not isinstance(issued, dict):
        return _fail("%s is not an issued-card object" % ISSUED.as_posix())

    kind = str(issued.get("kind") or "").strip()
    if kind and kind != "close":
        return _fail("the issued card is a %s card, not the M4 close card; an M4 verdict binds to the close card that "
                     "measured it" % kind)
    env_task = str(os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    task = str(issued.get("task_id") or "").strip()
    if task and env_task and task != env_task:
        return _fail("the issued close card is %s while $HERMES_KANBAN_TASK is %s; the tree and the running card "
                     "disagree about which card this is" % (task, env_task))
    card_id = task or env_task
    if not card_id:
        return _fail("the issued close card carries no task_id (it was converted but never minted) and "
                     "$HERMES_KANBAN_TASK is unset; nothing names the card this verdict is for")
    receipt_sha = str(issued.get("receipt_sha256") or "").strip()
    if not receipt_sha:
        return _fail("the issued close card records no receipt_sha256; nothing says which admission receipt it was "
                     "minted under")

    pp = root / PARITY_RECEIPT
    if not pp.is_file():
        return _fail("no %s; a verdict cannot bind to parity evidence that is not on disk (run the parity runner "
                     "first)" % PARITY_RECEIPT.as_posix())
    parity_sha = sha256_file(pp)

    was = {k: str(verdict.get(k) or "") for k in ("card_id", "receipt_sha256", "parity_receipt_sha256")}
    verdict["card_id"] = card_id
    verdict["receipt_sha256"] = receipt_sha
    verdict["parity_receipt_sha256"] = parity_sha
    _write_canonical(vp, verdict)

    changed = [k for k, v in was.items() if v != str(verdict[k])]
    print("OK: m4-verdict bound (card=%s receipt=%s parity=%s); %s"
          % (card_id, receipt_sha[:12], parity_sha[:12],
             ("rewrote " + ", ".join(sorted(changed))) if changed else "already bound"))
    print("   next: python3 .hermes/skills/gates/compose-m4-verdict/scripts/assert-m4-verdict-schema.py %s"
          % VERDICT.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
