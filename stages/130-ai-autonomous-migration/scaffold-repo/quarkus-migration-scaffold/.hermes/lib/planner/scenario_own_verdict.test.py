#!/usr/bin/env python3
"""A scenario is judged on its own mode record -- but only as part of the comparison that measured it
(v30 H-12, architect review of 4dfdd8d6, 2026-10-01).

v30 t_557b0bed: the Owner follow-up's effects check failed with "scenario sc:auth-anonymous-read-api-owners
is FAIL in the enabled-mode receipt" while that scenario's own enabled-mode record, bound to the candidate,
said PASS: parity_state gives every scenario its entry-point row's aggregate, and the getOwners row failed on
a SIBLING scenario. The own record bound to this tree decides PASS/FAIL. But the scenario must be in the
mode's receipt bound to this tree: the first H-12 patch accepted a leftover own record of a scenario the
receipt does not list (or a receipt with no rows) as PASS; those are UNKNOWN."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import requirement_checks as RC  # noqa: E402
from planner.worklist import PARITY_RECEIPT_SCHEMA  # noqa: E402

TREE = "a" * 64
EP = "ep:x.OwnerRestController#getOwners():http"
OWN, SIB = "sc:auth-anonymous-read-api-owners", "sc:cors-enabled-actual-anonymous-1"


def write_records(root: Path, records: list[dict]) -> None:
    d = root / "verification" / "parity" / "scenarios-enabled"
    d.mkdir(parents=True, exist_ok=True)
    for p in d.glob("*.json"):
        p.unlink()
    for n, rec in enumerate(records):
        (d / ("r%d.json" % n)).write_text(json.dumps(rec))


def own(verdict="PASS", *, tree=TREE, mode="enabled", sid=OWN) -> dict:
    return {"scenario": sid, "verdict": verdict, "security_mode": mode, "binding": {"mode": "candidate", "candidate_sha256": tree}}


def receipt(scenarios=(OWN, SIB), *, verdict="FAIL", schema=PARITY_RECEIPT_SCHEMA, tree=TREE) -> dict:
    rows = [{"entry_point": EP, "verdict": verdict, "scenarios": list(scenarios)}] if scenarios is not None else []
    return {"schema": schema, "security_mode": "enabled", "verdict": verdict,
            "binding": {"mode": "candidate", "candidate_sha256": tree}, "entry_points": rows}


def main() -> int:
    ok = True

    def check(cond, what, detail=""):
        nonlocal ok
        print(("ok " if cond else "FAIL ") + what + ("" if cond else ": %r" % (detail,)))
        ok = ok and cond

    req = {"id": "req:r", "acceptance": ["parity:" + OWN]}
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)

        def status(records, rc, *, modes=None, governed=True):
            write_records(root, records)
            return RC.measure(root, [req], worklist={"items": [], "measure": {"known": True}}, scenarios=[OWN, SIB],
                              tree=TREE, receipts={"enabled": rc},
                              scenario_modes={OWN: "enabled", SIB: "enabled"} if modes is None else modes,
                              governed=governed)["parity:" + OWN]

        r = status([own("PASS")], receipt())
        check(r["status"] == RC.PASS, "sibling FAIL + own PASS bound to this tree: PASS (H-12)", r)
        r = status([own("FAIL")], receipt(verdict="PASS"))
        check(r["status"] == RC.FAIL, "own FAIL record is a FAIL even in a PASS row", r)
        r = status([own("PASS")], receipt(scenarios=[SIB]))
        check(r["status"] == RC.UNKNOWN and "not recorded" in r["detail"], "receipt lists only the sibling: UNKNOWN, never PASS", r)
        r = status([own("PASS")], receipt(scenarios=None))
        check(r["status"] == RC.UNKNOWN, "receipt with no entry-point rows: UNKNOWN, never PASS", r)
        r = status([own("PASS")], receipt(schema="something-else/v9"))
        check(r["status"] == RC.UNKNOWN, "malformed receipt (unknown schema): UNKNOWN", r)
        r = status([own("PASS")], receipt(tree="b" * 64))
        check(r["status"] == RC.UNKNOWN, "receipt bound to another tree: UNKNOWN", r)
        r = status([], receipt())
        check(r["status"] == RC.FAIL and "receipt" in r["detail"], "no own record: the row stands in (FAIL)", r)
        r = status([own("PASS"), own("PASS")], receipt())
        check(r["status"] == RC.FAIL, "duplicate own records are no single record: the row stands in", r)
        r = status([own("PASS", tree="b" * 64)], receipt())
        check(r["status"] == RC.FAIL, "an own record of ANOTHER candidate is not this tree's: the row stands in", r)
        r = status([own("PASS", mode="disabled")], receipt())
        check(r["status"] == RC.UNKNOWN and "mode" in r["detail"], "an own record taken in the wrong mode: UNKNOWN", r)
        r = status([own("INCONCLUSIVE")], receipt(verdict="PASS"))
        check(r["status"] != RC.PASS, "an inconclusive own record never reads as PASS", r)
        r = status([own("PASS")], receipt(), modes={SIB: "enabled"})
        check(r["status"] == RC.UNKNOWN and "issued" in r["detail"], "a scenario outside the issued scope: UNKNOWN", r)

        # the outcome acceptance caller (outcome_checks.requirement_measurement with the issued scope) sees the same
        from planner.outcome_checks import requirement_measurement
        rp = Path(root) / "verification" / "parity" / "receipt-enabled.json"
        from planner.worklist import parity_receipt_file
        rp = Path(root) / parity_receipt_file("enabled")
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(receipt(scenarios=[SIB])))
        write_records(root, [own("PASS")])
        plan = {"requirements": [req]}
        node = {"outcome_id": "o", "requirements": ["req:r"], "acceptance": {"requirement_checks": ["parity:" + OWN]}}
        got = requirement_measurement(root, plan, node, {"items": [], "measure": {"known": True}}, [OWN, SIB], TREE,
                                      issued_scope={"scenarios_by_mode": {"enabled": [OWN, SIB]}})
        check(got["parity:" + OWN]["status"] == RC.UNKNOWN,
              "acceptance caller: a scenario absent from the receipt is UNKNOWN, not a leftover PASS", got)
    print("OK: scenario own verdict" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
