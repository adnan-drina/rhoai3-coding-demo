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

The binding is also RECORDED: `evidence/verdicts/m4-verdict.bound.json` holds
the digest of the verdict file as bound, a copy of it, and the three bindings.
The bound verdict is the verdict. A bound verdict edited afterwards -- a floor
re-typed, `failed_floors` changed, a binding blanked (v9's t_caf2ad51 revised a
bound PROVISIONAL_ACCEPT into a REFUSE with card_id "" by hand) -- no longer
digests to the record: this tool refuses to re-bind it, the lint refuses it,
and `resume-after-m4.py` refuses to consume it, each naming the fields that
differ. A new composition is a verdict WITHOUT bindings; binding it supersedes
the record, and the superseded binding (with its verdict copy) stays on the
record for the audit.

Exit 0 bound, 1 an input the binding is read from is missing or unusable, or
the bound verdict was edited after binding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERDICT = Path("evidence") / "verdicts" / "m4-verdict.json"
BINDING_RECORD = Path("evidence") / "verdicts" / "m4-verdict.bound.json"
RECORD_SCHEMA = "rhoai3.m4-verdict-binding/v1"
BINDINGS = ("card_id", "receipt_sha256", "parity_receipt_sha256")
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


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_binding_record(root: Path) -> dict[str, Any] | None:
    """The record bind wrote, or None when there is none (or it is unreadable:
    a broken record binds nothing, and the consumers refuse on that)."""
    rp = Path(root) / BINDING_RECORD
    if not rp.is_file():
        return None
    try:
        doc = _load(rp)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict) or str(doc.get("schema") or "") != RECORD_SCHEMA:
        return None
    return doc


def verdict_drift(bound: Any, current: Any) -> list[str]:
    """The top-level fields whose values differ between the bound copy and the
    verdict on disk, sorted -- what a refusal names."""
    b = bound if isinstance(bound, dict) else {}
    c = current if isinstance(current, dict) else {}
    return sorted(k for k in set(b) | set(c) if b.get(k) != c.get(k))


def write_binding_record(root: Path, verdict_path: Path, verdict: dict[str, Any],
                         previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record the verdict AS BOUND: its file digest, a copy, the three bindings.

    `previous` is the record being superseded by a new composition; it is
    kept (minus its own history) so the audit can read every verdict this
    card bound, in order."""
    superseded = list((previous or {}).get("superseded") or [])
    if previous:
        superseded.append({k: previous.get(k) for k in ("verdict_sha256", "bound_at", *BINDINGS, "verdict")})
    record = {
        "schema": RECORD_SCHEMA,
        "verdict_path": VERDICT.as_posix(),
        "verdict_sha256": sha256_file(verdict_path),
        "bound_at": _now(),
        **{k: str(verdict.get(k) or "") for k in BINDINGS},
        "verdict": verdict,
        "superseded": superseded,
    }
    rp = Path(root) / BINDING_RECORD
    rp.parent.mkdir(parents=True, exist_ok=True)
    _write_canonical(rp, record)
    return record


def edited_after_binding(record: dict[str, Any] | None, verdict_path: Path, verdict: dict[str, Any]) -> str:
    """Why this bound verdict is not the one on the record, or "" when it is
    (or when there is no record / the verdict carries no bindings yet)."""
    if record is None or not all(str(verdict.get(k) or "").strip() for k in BINDINGS):
        return ""
    on_disk = sha256_file(verdict_path)
    bound = str(record.get("verdict_sha256") or "")
    if on_disk == bound:
        return ""
    drift = verdict_drift(record.get("verdict"), verdict)
    return ("the bound verdict was edited after binding: bound %s at %s, on disk %s; fields that differ: %s. "
            "A bound verdict is not revised -- its measured fields are what the floors returned when it was "
            "composed. A new measurement is composed as a new verdict WITHOUT bindings and bound; this binding "
            "then stays on the record as superseded"
            % (bound[:12], record.get("bound_at") or "?", on_disk[:12], ", ".join(drift) or "(byte-level only)"))


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

    # The bound verdict is the verdict. One already bound and unchanged is a
    # no-op; one already bound and CHANGED is a hand revision, refused.
    record = load_binding_record(root)
    why = edited_after_binding(record, vp, verdict)
    if why:
        return _fail(why)
    if record is not None and all(str(verdict.get(k) or "").strip() for k in BINDINGS):
        print("OK: m4-verdict already bound (card=%s receipt=%s parity=%s) at %s; unchanged since"
              % (verdict.get("card_id"), str(verdict.get("receipt_sha256"))[:12],
                 str(verdict.get("parity_receipt_sha256"))[:12], record.get("bound_at")))
        return 0

    was = {k: str(verdict.get(k) or "") for k in BINDINGS}
    verdict["card_id"] = card_id
    verdict["receipt_sha256"] = receipt_sha
    verdict["parity_receipt_sha256"] = parity_sha
    _write_canonical(vp, verdict)
    written = write_binding_record(root, vp, verdict, previous=record)

    changed = [k for k, v in was.items() if v != str(verdict[k])]
    print("OK: m4-verdict bound (card=%s receipt=%s parity=%s); %s; recorded %s (verdict %s%s)"
          % (card_id, receipt_sha[:12], parity_sha[:12],
             ("rewrote " + ", ".join(sorted(changed))) if changed else "bindings were already these values",
             BINDING_RECORD.as_posix(), written["verdict_sha256"][:12],
             (", superseding %s bound at %s" % (str(record.get("verdict_sha256") or "")[:12], record.get("bound_at")))
             if record else ""))
    print("   next: python3 .hermes/skills/gates/compose-m4-verdict/scripts/assert-m4-verdict-schema.py %s"
          % VERDICT.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
