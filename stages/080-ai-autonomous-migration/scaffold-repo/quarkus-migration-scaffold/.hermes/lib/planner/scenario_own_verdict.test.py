#!/usr/bin/env python3
"""A scenario is judged on its own mode record, not on its entry point's aggregate (v30 H-12, 2026-10-01).

v30 t_557b0bed: the Owner follow-up's effects check failed with "scenario sc:auth-anonymous-read-api-owners
is FAIL in the enabled-mode receipt" while that scenario's own enabled-mode record, bound to the candidate,
said PASS. parity_state gives every scenario its entry-point row's verdict, and the getOwners row failed on a
SIBLING scenario. The scenario's own record bound to this tree now decides; the row only stands in when no
such record exists."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import requirement_checks as RC  # noqa: E402
from planner.worklist import PARITY_RECEIPT_SCHEMA  # noqa: E402

TREE = "b94d4879a8ea05e2"
EP = "ep:x.OwnerRestController#getOwners():http"
OWN, SIB = "sc:auth-anonymous-read-api-owners", "sc:cors-enabled-actual-anonymous-1"


def setup(root: Path, own_verdict: str | None, *, bound: str = TREE) -> dict:
    d = root / "verification" / "parity" / "scenarios-enabled"
    d.mkdir(parents=True, exist_ok=True)
    for p in d.glob("*.json"):
        p.unlink()
    if own_verdict:
        (d / "sc_auth-anonymous-read-api-owners.json").write_text(json.dumps(
            {"scenario": OWN, "verdict": own_verdict, "security_mode": "enabled",
             "binding": {"mode": "candidate", "candidate_sha256": bound}}))
    # the receipt row of the entry point FAILS because of the sibling
    return {"schema": PARITY_RECEIPT_SCHEMA, "security_mode": "enabled", "verdict": "FAIL",
            "binding": {"candidate_sha256": TREE},
            "entry_points": [{"entry_point": EP, "verdict": "FAIL", "scenarios": [OWN, SIB]}]}


def main() -> int:
    ok = True

    def check(cond, what, detail=""):
        nonlocal ok
        print(("ok " if cond else "FAIL ") + what + ("" if cond else ": %r" % (detail,)))
        ok = ok and cond

    req = {"id": "req:r", "acceptance": ["parity:" + OWN]}
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)

        def status(own_verdict, **kw):
            rc = setup(root, own_verdict, **kw)
            out = RC.measure(root, [req], worklist={"items": [], "measure": {"known": True}}, scenarios=[OWN, SIB],
                             tree=TREE, receipts={"enabled": rc}, scenario_modes={OWN: "enabled", SIB: "enabled"},
                             governed=True)
            return out["parity:" + OWN]

        r = status("PASS")
        check(r["status"] == RC.PASS, "own enabled-mode PASS bound to this tree stands beside a sibling-failed row", r)
        r = status("FAIL")
        check(r["status"] == RC.FAIL, "own FAIL record is a FAIL", r)
        r = status(None)
        check(r["status"] == RC.FAIL and "receipt" in r["detail"], "no own record: the row stands in (FAIL)", r)
        r = status("PASS", bound="another-candidate")
        check(r["status"] == RC.FAIL, "an own record of ANOTHER candidate is not this tree's: the row stands in", r)
        r = status("INCONCLUSIVE")
        check(r["status"] != RC.PASS, "an inconclusive own record never reads as PASS", r)
    print("OK: scenario own verdict" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
