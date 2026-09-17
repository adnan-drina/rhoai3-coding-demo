#!/usr/bin/env python3
"""Make a SEALED comparison of the accepted tree the loop's parity baseline.

After an Operator step or a rewind the accepted parity baseline is UNMEASURED
(the receipt on disk described another tree). The Operator then runs the whole
phase, sealed, on the accepted tree:

  python3 .hermes/skills/paved-road/paved-road-m4/scripts/run-parity.py --root .   # no --issued: sealed
  python3 .hermes/skills/migration/fix-until-green/scripts/refresh-accepted-parity.py \\
      --root . --operator operator:NAME --reason "..."

and this command snapshots that receipt and its records into
verification/loop/accepted/parity, rebuilds the work list, re-seals admission,
records the refresh in steps.json (``parity_refreshes``, and on the last step)
and, unless --no-mint, mints the next card.

It REFUSES (nothing changed) when:
  * a card is issued (its candidate may be on the tree), or the product tree is
    not clean;
  * the tree on disk is not the accepted tree (the loop state's candidate
    digest, measured by the last verification);
  * the receipt is not a whole (unscoped), sealed, default-mode comparison
    its runner says it composed (parity_not_of_this_tree);
  * the receipt or the runner's record is bound to another admission receipt
    than the current one;
  * the runner's record names no artifact, or an artifact other than the one
    the packaging and startup gates verified on this tree.

Exit 0 refreshed; 1 refused; 2 usage.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import (PARITY_REFRESHES, PARITY_SNAPSHOT, archive_parity_baseline, PARITY_SOURCE_SCHEMA, candidate_sha256, ensure_hermes_lib, load_issued,  # noqa: E402
                          load_state, load_steps, parity_not_of_this_tree, product_paths_changed, save_steps, snapshot_parity)

ensure_hermes_lib()
from planner import pipeline  # noqa: E402
from planner.canonical import load_json, sha256_file  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, LOOP_ACCEPTED, PARITY_DIR, VERIFY_BOOT, VERIFY_PACKAGE  # noqa: E402
from planner.worklist import build_worklist  # noqa: E402


def _refuse(msg: str) -> int:
    print("REFUSE: LOOP_PARITY_REFRESH %s" % msg, file=sys.stderr)
    return 1


def _doc(p: Path) -> dict:
    try:
        d = load_json(p)
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def check(root: Path) -> tuple[str, dict]:
    """(why the receipt on disk may not become the baseline, the facts checked)."""
    if load_issued(root):
        return "a card is issued; refresh the baseline only between cards", {}
    dirty = product_paths_changed(root)
    if dirty:
        return "the product tree is not clean: %s" % ", ".join(dirty[:5]), {}
    state = load_state(root) or {}
    tree = candidate_sha256(root)
    if not state.get("candidate_sha256") or str(state.get("candidate_sha256")) != tree:
        return ("the tree on disk (%s) is not the one the last verification measured (%s)"
                % (tree[:12], str(state.get("candidate_sha256") or "")[:12])), {}
    why = parity_not_of_this_tree(root, direct=True)
    if why:
        return why, {}
    receipt = _doc(root / PARITY_DIR / "receipt.json")
    record = _doc(root / PARITY_DIR / "_run.json")
    admission = str(_doc(root / ADMISSION_RECEIPT).get("receipt_digest") or "")
    if not admission:
        return "there is no admission receipt to bind to", {}
    for name, got in (("the receipt", str(receipt.get("receipt_sha256") or "")),
                      ("the runner's record", str(record.get("receipt_sha256") or ""))):
        if got != admission:
            return "%s is bound to admission receipt %s, the current one is %s" % (name, got[:12] or "nothing", admission[:12]), {}
    art = record.get("artifact") if isinstance(record.get("artifact"), dict) else {}
    packaged = str(_doc(root / VERIFY_PACKAGE).get("artifact_sha256") or "")
    booted = str(_doc(root / VERIFY_BOOT).get("artifact_sha256") or "")
    if not str(art.get("sha256") or ""):
        return "the runner's record names no artifact (%s)" % (art.get("reason") or "no digest"), {}
    if str(art.get("sha256")) != packaged or (booted and booted != packaged):
        return ("the compared artifact %s is not the one packaging (%s) and startup (%s) verified on this tree"
                % (str(art.get("sha256"))[:12], packaged[:12] or "none", booted[:12] or "none")), {}
    return "", {"candidate_sha256": tree, "admission_receipt": admission, "artifact_sha256": packaged,
                "receipt_file_sha256": sha256_file(root / PARITY_DIR / "receipt.json"),
                "verdict": str(receipt.get("verdict") or ""), "security_mode": str(receipt.get("security_mode") or "")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--operator", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--no-mint", action="store_true")
    ap.add_argument("--hermes", default="hermes")
    ap.add_argument("--check", action="store_true", help="report whether the receipt may become the baseline; change nothing")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    why, facts = check(root)
    if why:
        return _refuse(why)
    if args.check:
        print("OK: LOOP_PARITY_REFRESH may snapshot %s (%s) of tree %s" % (facts["receipt_file_sha256"][:12], facts["verdict"], facts["candidate_sha256"][:12]))
        return 0
    steps = load_steps(root)
    recorded = list(steps.get("steps") or [])
    if not recorded:
        return _refuse("no step is recorded; the baseline is the bootstrap's")
    prior = _doc(root / LOOP_ACCEPTED / PARITY_SNAPSHOT / "receipt.json")
    source = {"schema": PARITY_SOURCE_SCHEMA, "mode": "refreshed", "by": args.operator, "reason": args.reason,
              "step": len(recorded) - 1, "commit": str(recorded[-1].get("commit") or ""), **facts,
              "replaces": {"verdict": str(prior.get("verdict") or ""),
                           "unmeasured": dict(prior.get("unmeasured") or {}) if isinstance(prior.get("unmeasured"), dict) else {}}}
    kept = snapshot_parity(root, source=source)
    wl = build_worklist(root)
    pipeline.admit(root)
    row = dict(source, at=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), records=len(kept),
               parity_mismatches=(wl.get("measure") or {}).get("parity_mismatches"))
    steps.setdefault("parity_refreshes", []).append(row)
    # kept by number: a later rewind to this step restores THIS baseline
    row["archive"] = archive_parity_baseline(root, len(steps["parity_refreshes"]) - 1).relative_to(root).as_posix()
    recorded[-1] = dict(recorded[-1], parity_refreshed=len(steps["parity_refreshes"]) - 1)
    steps["steps"] = recorded
    save_steps(root, steps)
    print("OK: LOOP_PARITY_REFRESH step %d baseline is the sealed comparison %s (%s, %d record(s)) of tree %s, artifact %s; "
          "%s parity obligation(s) in the rebuilt work list"
          % (len(recorded) - 1, facts["receipt_file_sha256"][:12], facts["verdict"], len(kept), facts["candidate_sha256"][:12],
             facts["artifact_sha256"][:12], row["parity_mismatches"]))
    if args.no_mint:
        return 0
    from advance import _mint  # noqa: E402

    return _mint(root, args.hermes)

if __name__ == "__main__":
    raise SystemExit(main())
