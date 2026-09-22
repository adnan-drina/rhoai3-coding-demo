#!/usr/bin/env python3
"""Refuse an M4 verdict object that omits failed_floors, calls a fail idle, or
names no run.

Operator 143706ZO: dest-8 invented a shape with no failed-floor field.
This parser is the schema; check-release-readiness remains lint.

v9's second M4 card is why the bindings are required here. It composed a
`REFUSE` from measured exits and wrote no `card_id`, because `card_id` was
optional and the worker that had written one before wrote it from memory. The
card completed; `resume-after-m4.py` then refused the verdict as a verdict for
no run, and the measurement was stranded. A verdict is bound to what it judged
BY THE TOOL, never by a worker's recollection, so the three bindings are
required fields and each is checked against the artifact it names:

  * `card_id` is the issued close card (`verification/loop/issued.json`
    `task_id`, or `$HERMES_KANBAN_TASK` when that is the only one on record);
  * `receipt_sha256` is the admission receipt that card was minted under
    (the same file's `receipt_sha256`);
  * `parity_receipt_sha256` is the digest of `verification/parity/receipt.json`
    itself -- the parity evidence this verdict judged.

A stale or foreign binding refuses by name (`M4_VERDICT_BINDING`), so a verdict
composed for another card, under another seal, or over a parity receipt that
has since been re-composed cannot be read as this run's answer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = (
    "gate",
    "phase",
    "ran",
    "verdict",
    "ship",
    "failed_floors",
    "floors",
    "coverage_account",
    "card_id",
    "receipt_sha256",
    "parity_receipt_sha256",
)
FLOOR_FIELDS = ("name", "rc", "idle")
ACCEPT_TOKENS = frozenset({"PROVISIONAL_ACCEPT", "ACCEPT", "SCOPED_ACCEPT"})

# The two artifacts the bindings are checked against. Harness paths, never a
# specimen's: the same two `resume-after-m4.py` binds on.
ISSUED = Path("verification") / "loop" / "issued.json"
PARITY_RECEIPT = Path("verification") / "parity" / "receipt.json"
BINDING = "M4_VERDICT_BINDING"
# An omitted binding is not a missing key like any other: it is the v9 defect,
# so the refusal names the run it leaves unbound rather than a field name.
MISSING_BINDING = {
    "card_id": "%s missing card_id; a verdict that names no card is a verdict for no run "
               "(bind-m4-verdict.py fills it from %s)" % (BINDING, ISSUED.as_posix()),
    "receipt_sha256": "%s missing receipt_sha256; the verdict must name the admission receipt its card was minted "
                      "under (%s)" % (BINDING, ISSUED.as_posix()),
    "parity_receipt_sha256": "%s missing parity_receipt_sha256; the verdict must name the digest of the parity "
                             "receipt it judged (%s)" % (BINDING, PARITY_RECEIPT.as_posix()),
}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def sha256_file(path: Path) -> str:
    """Digest of the file's bytes -- what `planner.canonical.sha256_file`
    computes, recomputed here so this parser stays stdlib-only."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_verdict(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("verdict is not an object")
    return data


def binding_issues(doc: dict[str, Any], root: Path) -> list[str]:
    """Refuse a verdict whose bindings do not name THIS run's card and evidence.

    Every expected value is READ from an artifact of the tree, so the check is
    an equality between two files and never a judgement about what the worker
    remembers. A binding that names nothing, something else, or evidence that
    has since moved is refused by name."""
    issues: list[str] = []
    card_id = str(doc.get("card_id") or "").strip()
    receipt_sha = str(doc.get("receipt_sha256") or "").strip()
    parity_sha = str(doc.get("parity_receipt_sha256") or "").strip()
    env_task = str(os.environ.get("HERMES_KANBAN_TASK") or "").strip()

    if not card_id:
        issues.append("%s card_id is empty; a verdict that names no card is a verdict for no run" % BINDING)
    if not receipt_sha:
        issues.append("%s receipt_sha256 is empty; the verdict must name the admission receipt its card was minted "
                      "under" % BINDING)
    if not parity_sha:
        issues.append("%s parity_receipt_sha256 is empty; the verdict must name the parity receipt it judged" % BINDING)

    ip = root / ISSUED
    issued: dict[str, Any] = {}
    if not ip.is_file():
        issues.append("%s no %s under %s; nothing binds this verdict to an issued card (pass --root when the verdict "
                      "is not at <root>/evidence/verdicts/)" % (BINDING, ISSUED.as_posix(), root))
    else:
        try:
            loaded = json.loads(ip.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            loaded = None
            issues.append("%s unreadable %s: %s" % (BINDING, ISSUED.as_posix(), exc))
        if isinstance(loaded, dict):
            issued = loaded
        elif loaded is not None:
            issues.append("%s %s is not an issued-card object" % (BINDING, ISSUED.as_posix()))

    if issued:
        kind = str(issued.get("kind") or "").strip()
        task = str(issued.get("task_id") or "").strip()
        want_receipt = str(issued.get("receipt_sha256") or "").strip()
        if kind and kind != "close":
            issues.append("%s the issued card is a %s card, not the M4 close card; an M4 verdict binds to the close "
                          "card that measured it" % (BINDING, kind))
        if task and env_task and task != env_task:
            issues.append("%s the issued close card is %s while $HERMES_KANBAN_TASK is %s; the tree and the running "
                          "card disagree about which card this is" % (BINDING, task, env_task))
        expected = task or env_task
        if not expected:
            issues.append("%s the issued close card carries no task_id and $HERMES_KANBAN_TASK is unset; there is no "
                          "card to bind the verdict to" % BINDING)
        elif card_id and card_id != expected:
            issues.append("%s card_id %s is not the issued close card %s (%s)"
                          % (BINDING, card_id, expected, ISSUED.as_posix() if task else "$HERMES_KANBAN_TASK"))
        if not want_receipt:
            issues.append("%s the issued close card records no receipt_sha256; nothing says which admission receipt "
                          "it was minted under" % BINDING)
        elif receipt_sha and receipt_sha != want_receipt:
            issues.append("%s receipt_sha256 %s is not the admission receipt the issued close card was minted under "
                          "(%s)" % (BINDING, receipt_sha[:12], want_receipt[:12]))

    pp = root / PARITY_RECEIPT
    if not pp.is_file():
        issues.append("%s no %s under %s; the verdict judges parity evidence that is not on disk"
                      % (BINDING, PARITY_RECEIPT.as_posix(), root))
    elif parity_sha:
        try:
            have = sha256_file(pp)
        except OSError as exc:
            have = ""
            issues.append("%s unreadable %s: %s" % (BINDING, PARITY_RECEIPT.as_posix(), exc))
        if have and parity_sha != have:
            issues.append("%s parity_receipt_sha256 %s is not the digest of %s (%s); the verdict names parity "
                          "evidence this tree does not hold"
                          % (BINDING, parity_sha[:12], PARITY_RECEIPT.as_posix(), have[:12]))
    return issues


BINDING_RECORD = Path("evidence") / "verdicts" / "m4-verdict.bound.json"
RECORD_SCHEMA = "rhoai3.m4-verdict-binding/v1"


def record_issues(verdict_path: Path, doc: dict[str, Any], root: Path) -> list[str]:
    """The bound verdict is the verdict: it must digest to what bind-m4-verdict.py
    recorded. No record means the bindings were typed by hand (not a binding);
    a different digest means the verdict was edited after it was bound (v9's
    t_caf2ad51 revised a bound verdict into a REFUSE with card_id "")."""
    rp = root / BINDING_RECORD
    if not rp.is_file():
        return ["%s no binding record %s; bind-m4-verdict.py writes it when it binds -- bindings typed by hand are "
                "not a binding" % (BINDING, BINDING_RECORD.as_posix())]
    try:
        record = json.loads(rp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ["%s unreadable binding record %s: %s" % (BINDING, BINDING_RECORD.as_posix(), exc)]
    if not isinstance(record, dict) or str(record.get("schema") or "") != RECORD_SCHEMA:
        return ["%s %s is not a %s record" % (BINDING, BINDING_RECORD.as_posix(), RECORD_SCHEMA)]
    bound = str(record.get("verdict_sha256") or "")
    on_disk = sha256_file(verdict_path)
    if on_disk != bound:
        copy = record.get("verdict") if isinstance(record.get("verdict"), dict) else {}
        drift = sorted(k for k in set(copy) | set(doc) if copy.get(k) != doc.get(k))
        return ["%s the verdict was edited after binding: bound %s at %s, on disk %s; fields that differ: %s -- a "
                "bound verdict is not revised; a new measurement is composed as a new verdict without bindings and "
                "bound" % (BINDING, bound[:12], record.get("bound_at") or "?", on_disk[:12], ", ".join(drift) or "(byte-level only)")]
    return []


def check(doc: dict[str, Any], root: Path) -> list[str]:
    issues: list[str] = []
    for key in REQUIRED_FIELDS:
        if key not in doc:
            issues.append(MISSING_BINDING.get(key) or "M4_VERDICT_SCHEMA missing %s" % key)
    if issues:
        return issues

    if str(doc.get("gate") or "") != "M4_VERDICT":
        issues.append("M4_VERDICT_SCHEMA gate %r" % doc.get("gate"))
    if str(doc.get("phase") or "").upper() != "M4":
        issues.append("M4_VERDICT_SCHEMA phase %r" % doc.get("phase"))
    if doc.get("ship") is True:
        issues.append("M4_VERDICT_SCHEMA ship must be false at M4")
    issues.extend(binding_issues(doc, root))

    account = doc.get("coverage_account")
    if not isinstance(account, dict):
        issues.append("M4_VERDICT_SCHEMA coverage_account must be an object {retired, remaining_gaps}")
    else:
        for key in ("retired", "remaining_gaps"):
            if not isinstance(account.get(key), int) or isinstance(account.get(key), bool):
                issues.append("M4_VERDICT_SCHEMA coverage_account %s must be int" % key)

    failed = doc.get("failed_floors")
    if not isinstance(failed, list):
        issues.append("M4_VERDICT_SCHEMA failed_floors must be a list")
        return issues
    failed_names = [str(x).strip() for x in failed if str(x).strip()]

    floors = doc.get("floors")
    if not isinstance(floors, list) or not floors:
        issues.append("M4_VERDICT_SCHEMA floors must be a non-empty list")
        return issues

    seen: set[str] = set()
    reason = str(doc.get("reason") or "")
    for i, row in enumerate(floors):
        if not isinstance(row, dict):
            issues.append("M4_VERDICT_SCHEMA floors[%d] not an object" % i)
            continue
        for key in FLOOR_FIELDS:
            if key not in row:
                issues.append("M4_VERDICT_SCHEMA floors[%d] missing %s" % (i, key))
        name = str(row.get("name") or "").strip()
        rc = row.get("rc")
        idle = row.get("idle")
        if not name:
            issues.append("M4_VERDICT_SCHEMA floors[%d] name empty" % i)
            continue
        seen.add(name)
        if not isinstance(rc, int) or isinstance(rc, bool):
            issues.append("M4_VERDICT_SCHEMA floors[%d] rc must be int" % i)
            continue
        if idle is not True and idle is not False:
            issues.append("M4_VERDICT_SCHEMA floors[%d] idle must be bool" % i)
            continue
        if rc != 0 and idle is True:
            issues.append(
                "FAILED_FLOOR_AS_IDLE %s rc=%s idle=true" % (name, rc)
            )
        if rc != 0 and name not in failed_names:
            issues.append("M4_VERDICT_SCHEMA %s rc=%s missing from failed_floors" % (name, rc))
        if rc == 0 and name in failed_names:
            issues.append("M4_VERDICT_SCHEMA %s rc=0 must not be in failed_floors" % name)
        if idle is True and name in failed_names:
            issues.append("FAILED_FLOOR_AS_IDLE %s in failed_floors with idle=true" % name)
        if rc != 0 and "idle" in reason.lower():
            issues.append(
                "FAILED_FLOOR_AS_IDLE reason names idle while %s rc=%s" % (name, rc)
            )

    for name in failed_names:
        if name not in seen:
            issues.append("M4_VERDICT_SCHEMA failed_floors %s not in floors[]" % name)

    token = str(doc.get("verdict") or "").strip().upper().replace("-", "_")
    if failed_names and token in ACCEPT_TOKENS:
        issues.append(
            "ACCEPT_WITH_FAILED_FLOOR verdict=%s failed_floors=%s"
            % (token, failed_names)
        )
    if token == "ACCEPT":
        issues.append("M4_VERDICT_SCHEMA M4 must not emit ACCEPT")
    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("verdict", type=Path)
    ap.add_argument(
        "--root",
        type=Path,
        default=None,
        help="destination root the bindings are read from (default: the verdict's own "
             "<root>/evidence/verdicts/ parent)",
    )
    args = ap.parse_args(argv)
    path = args.verdict
    if not path.is_file():
        return _fail("verdict file missing: " + str(path))
    # The verdict lives at <root>/evidence/verdicts/m4-verdict.json, so the root
    # is two directories above it. K4's exit runs this with a relative path from
    # the destination root, which resolves to the same place.
    root = args.root.resolve() if args.root else path.resolve().parents[2]
    try:
        doc = load_verdict(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return _fail("unreadable verdict: " + str(exc))
    issues = check(doc, root)
    if not issues:
        issues = record_issues(path.resolve(), doc, root)
    if issues:
        for issue in issues:
            print("FAIL: " + issue, file=sys.stderr)
        return 1
    print(
        "OK: m4-verdict schema (failed_floors=%d floors=%d token=%s card=%s receipt=%s parity=%s)"
        % (
            len(doc.get("failed_floors") or []),
            len(doc.get("floors") or []),
            doc.get("verdict"),
            doc.get("card_id"),
            str(doc.get("receipt_sha256") or "")[:12],
            str(doc.get("parity_receipt_sha256") or "")[:12],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
