#!/usr/bin/env python3
"""Investigate a failure no card can carry — and change nothing.

When a gate fails with a message that names no file of this tree, the loop has
nowhere to put the work: there is no cluster, so no card, so no attempt, and
the run stops with a blocker it cannot describe. Pilot v7 ended exactly there.

This is the Operator's answer, and it is deliberately NOT a card kind. A card
is a licence to edit the product; an investigation is a licence to read it. So
this tool grants no write authority at all: the only thing it may leave behind
is its own report, and it refuses to close if anything else in the product tree
moved while it ran.

It is also bounded. Two attempts of ten minutes each, per failure, for the life
of the run. A third attempt is not a longer investigation — it is the answer
that this failure needs a decision rather than more looking.

Finishing an investigation does not discharge anything. The blocker is exactly
as blocking afterwards; what changes is that the run now carries a written
conclusion an Operator or an architect can act on.

  diagnose.py --root . --list
  diagnose.py --root . --failure rt:package:583bde63a --open
  diagnose.py --root . --failure rt:package:583bde63a --close \
      --conclusion DECISION_REQUIRED \
      --investigated "grepped the tree for the offending value; read the extension's docs" \
      --finding "the SpEL @Value is in RootRestController and the platform does not implement it" \
      --proposed-action "an ADR choosing a replacement for the servlet context path"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import candidate_sha256, ensure_hermes_lib, product_paths_changed  # noqa: E402

ensure_hermes_lib()

from planner.canonical import load_json, sha256_file, write_canonical  # noqa: E402
from planner.paths import WORKLIST  # noqa: E402

DIAGNOSIS_DIR = Path("evidence") / "diagnosis"
ATTEMPT_LIMIT = 2
MINUTES = 10
CONCLUSIONS = ("LOCATED", "ENVIRONMENT", "DECISION_REQUIRED", "INCONCLUSIVE")


def _refuse(msg: str) -> int:
    print("REFUSE: DIAGNOSIS %s" % msg, file=sys.stderr)
    return 1


def failure_dir(root: Path, failure: str) -> Path:
    return root / DIAGNOSIS_DIR / failure.replace(":", "-").replace("/", "-")


def attempts(root: Path, failure: str) -> list[dict]:
    d = failure_dir(root, failure)
    if not d.is_dir():
        return []
    return [load_json(p) for p in sorted(d.glob("[0-9]*.json"))]


def _known_failures(root: Path) -> list[dict]:
    doc = load_json(root / WORKLIST) if (root / WORKLIST).is_file() else {}
    return list(doc.get("unlocatable") or [])


def _append(path: Path, event: dict) -> dict:
    """Append-only: a record grows, and no event already in it is rewritten."""
    doc = load_json(path) if path.is_file() else {"schema": "rhoai3.diagnosis-attempt/v1", "events": []}
    doc["events"] = list(doc.get("events") or []) + [event]
    write_canonical(path, doc)
    return doc


def _cmd_list(root: Path) -> int:
    rows = _known_failures(root)
    if not rows:
        print("no failure is currently unlocatable; nothing to investigate")
        return 0
    for row in rows:
        spent = attempts(root, row["id"])
        open_one = [a for a in spent if not any(e.get("event") == "close" for e in a.get("events") or [])]
        print("%-40s %-12s attempts %d/%d%s\n    %s" % (
            row["id"], row.get("kind"), len(spent), ATTEMPT_LIMIT,
            "  [OPEN]" if open_one else "", (row.get("detail") or "")[:160]))
    return 0


def _cmd_open(root: Path, failure: str, row: dict) -> int:
    spent = attempts(root, failure)
    for a in spent:
        if not any(e.get("event") == "close" for e in a.get("events") or []):
            started = next((e for e in a.get("events") or [] if e.get("event") == "open"), {})
            return _refuse("attempt %s is already open (started %s); close it before starting another"
                           % (a.get("attempt"), started.get("at")))
    if len(spent) >= ATTEMPT_LIMIT:
        return _refuse("this failure has had its %d attempts; a third is not a longer look, it is the finding that "
                       "the failure needs a decision. Record that conclusion and escalate." % ATTEMPT_LIMIT)
    n = len(spent) + 1
    d = failure_dir(root, failure)
    (d / ("scratch-%d" % n)).mkdir(parents=True, exist_ok=True)
    now = time.time()
    doc = _append(d / ("%d.json" % n), {
        "event": "open",
        "attempt": n,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "deadline_epoch": int(now) + MINUTES * 60,
        "failure": {k: row.get(k) for k in ("id", "kind", "gate", "cause", "detail")},
        # The whole content of the product tree, not the list of names in it.
        # A file that was already dirty stays dirty however many times it is
        # edited, so a name list says nothing (measured: an investigation
        # changed an already-modified file twice and closed clean).
        "inputs": {"worklist_present": (root / WORKLIST).is_file(),
                   "product_paths_changed": product_paths_changed(root),
                   "candidate_sha256": candidate_sha256(root),
                   "worklist_sha256": sha256_file(root / WORKLIST) if (root / WORKLIST).is_file() else ""},
        "scratch": (DIAGNOSIS_DIR / failure.replace(":", "-").replace("/", "-") / ("scratch-%d" % n)).as_posix(),
    })
    doc["attempt"] = n
    doc["failure"] = failure
    write_canonical(d / ("%d.json" % n), doc)
    print("OK: DIAGNOSIS OPEN %s attempt %d of %d, %d minutes.\n"
          "    Read anything. Write only in %s.\n"
          "    Close with --close --conclusion {%s} --investigated ... --finding ... --proposed-action ...\n"
          "    Closing discharges nothing: the blocker stays blocking."
          % (failure, n, ATTEMPT_LIMIT, MINUTES, doc["events"][0]["scratch"], "|".join(CONCLUSIONS)))
    return 0


def _cmd_close(root: Path, failure: str, args: argparse.Namespace) -> int:
    spent = attempts(root, failure)
    cur = next((a for a in spent if not any(e.get("event") == "close" for e in a.get("events") or [])), None)
    if cur is None:
        return _refuse("no attempt is open for %s" % failure)
    n = int(cur.get("attempt") or len(spent))
    opened = next((e for e in cur.get("events") or [] if e.get("event") == "open"), {})
    if args.conclusion not in CONCLUSIONS:
        return _refuse("--conclusion must be one of %s" % ", ".join(CONCLUSIONS))
    for name in ("investigated", "finding", "proposed_action"):
        if len(str(getattr(args, name) or "").strip()) < 12:
            return _refuse("--%s must say something a reader can act on" % name.replace("_", "-"))
    # the one authority this tool does not have: the product tree must be
    # exactly as it was, or the investigation edited what it came to look at
    moved = product_paths_changed(root)
    inputs = opened.get("inputs") or {}
    before = list(inputs.get("product_paths_changed") or [])
    before_content = str(inputs.get("candidate_sha256") or "")
    now_content = candidate_sha256(root)
    names_differ = sorted(moved) != sorted(before)
    content_differs = bool(before_content) and before_content != now_content
    if names_differ or content_differs or not before_content:
        detail = (", ".join(sorted(set(moved) ^ set(before))[:5]) if names_differ
                  else ("the same files, different content (%s -> %s)" % (before_content[:12], now_content[:12])
                        if before_content else "this attempt recorded no content digest to compare against"))
        _append(failure_dir(root, failure) / ("%d.json" % n), {
            "event": "refused", "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "reason": "the product tree changed during the investigation",
            "paths": sorted(set(moved) ^ set(before)),
            "candidate_sha256": {"at_open": before_content, "at_close": now_content},
        })
        return _refuse("the product tree changed while this investigation ran (%s); an investigation reads, it does "
                       "not repair. Revert it; the refusal is on the record." % detail)
    late = time.time() > float(opened.get("deadline_epoch") or 0)
    conclusion = "INCONCLUSIVE" if (late and args.conclusion != "INCONCLUSIVE") else args.conclusion
    event = {
        "event": "close",
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "identity": {"failure": failure, "attempt": n, "of": ATTEMPT_LIMIT},
        "investigation": str(args.investigated).strip(),
        "finding": str(args.finding).strip(),
        "conclusion": conclusion,
        "proposed_action": str(args.proposed_action).strip(),
        "path": str(args.path or ""),
        "over_deadline": late,
        "candidate_sha256": now_content,
        "discharges": [],
    }
    if late:
        event["deadline_note"] = ("the %d-minute limit passed, so this closes INCONCLUSIVE whatever it found; "
                                  "what it found is still recorded" % MINUTES)
    _append(failure_dir(root, failure) / ("%d.json" % n), event)
    left = ATTEMPT_LIMIT - n
    print("OK: DIAGNOSIS %s %s attempt %d/%d -> %s\n    proposed: %s\n    %s"
          % (conclusion, failure, n, ATTEMPT_LIMIT, event["finding"][:160], event["proposed_action"][:160],
             ("%d attempt(s) left" % left) if left else "no attempts left: this failure now needs a decision, not more looking"))
    print("    nothing was discharged; the work list is unchanged")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--list", action="store_true", help="the failures no card can carry, and what has been spent on them")
    ap.add_argument("--failure", default="")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--close", action="store_true")
    ap.add_argument("--conclusion", default="", help="|".join(CONCLUSIONS))
    ap.add_argument("--investigated", default="", help="what you actually did")
    ap.add_argument("--finding", default="", help="what is true, not what you suspect")
    ap.add_argument("--proposed-action", dest="proposed_action", default="", help="what someone should do next")
    ap.add_argument("--path", default="", help="the file the failure turned out to be in, if it has one")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    if args.list or not args.failure:
        return _cmd_list(root)
    row = next((r for r in _known_failures(root) if r["id"] == args.failure), None)
    if row is None:
        known = ", ".join(r["id"] for r in _known_failures(root)) or "none"
        return _refuse("%r is not an open unlocatable failure (known: %s)" % (args.failure, known))
    if args.open and args.close:
        return _refuse("open an attempt or close one, not both")
    if args.open:
        return _cmd_open(root, args.failure, row)
    if args.close:
        return _cmd_close(root, args.failure, args)
    print(json.dumps({"failure": row, "attempts": attempts(root, args.failure)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
