#!/usr/bin/env python3
"""A follow-up without a check plan is issued the verification of the requirements it owns.

v30 t_557b0bed (2026-10-01): an M3 orphan route created
followup:objective:selected-repository-implementation:<owner>:m3g1 from a
scheduled check. It owns the Owner repository requirement and its acceptance
judges behavior:repository-effects:<OwnerRepository>, but the node carries no
check plan. verification_scope read only the immediate check plan, the issue
attached no verification, run-verify compared nothing, and the check stayed
UNKNOWN ("scenario sc:auth-allowed-delete-cascading-owners-1 was not measured on
this tree") on every run while every open behavior card waited on it."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.requirement_checks import measured_check_rows, verification_scope  # noqa: E402

REQ = "req:repository-architecture:R<-OwnerRepository"


def corpora(root: Path, disabled: list[str], enabled: list[str]) -> None:
    for rel, ids in (("verification/scenarios/corpus.json", disabled), ("verification/scenarios-enabled/corpus.json", enabled)):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"scenarios": [{"id": i} for i in ids]}))


def main() -> int:
    ok = True

    def check(cond: bool, what: str, detail: object = "") -> None:
        nonlocal ok
        print(("ok " if cond else "FAIL ") + what + ("" if cond else ": %r" % (detail,)))
        ok = ok and cond

    EFF = "behavior:repository-effects:OwnerRepository"
    plan = {"requirements": [{"id": REQ, "acceptance": [EFF, "unit:fragment-implementation", "parity:sc:cors-actual-1",
                                                        "parity:sc:create-owners"],
                              "facts": {"verification": [{"member": "OwnerRepository#delete", "status": "applicable", "scenarios": [
                                  "sc:delete-cascading-owners-1", "sc:auth-allowed-delete-cascading-owners-1",
                                  "sc:auth-anonymous-delete-cascading-owners-1"]}]}}]}
    followup = {"outcome_id": "followup:objective:o:m3g1", "requirements": [REQ], "check_plan": [],
                "acceptance": {"requirement_checks": [EFF]}}
    owner = {"outcome_id": "objective:o", "requirements": [REQ],
             "check_plan": [{"check": "gate:package", "stage": "immediate"},
                            {"check": "parity:sc:delete-cascading-owners-1", "stage": "later"}]}
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        corpora(root, ["delete-cascading-owners-1"],
                ["auth-allowed-delete-cascading-owners-1", "auth-anonymous-delete-cascading-owners-1"])
        rows = measured_check_rows(plan, followup)
        check([r["check"] for r in rows] == ["parity:sc:delete-cascading-owners-1", "parity:sc:auth-allowed-delete-cascading-owners-1",
                                             "parity:sc:auth-anonymous-delete-cascading-owners-1"],
              "a follow-up with no check plan measures exactly the scenarios its owned effects check judges -- not the "
              "requirement's other parity entries (CORS, create), which other outcomes own", rows)
        s = verification_scope(root, plan, followup)
        check(s["scenarios_by_mode"] == {"disabled": ["sc:delete-cascading-owners-1"],
                                         "enabled": ["sc:auth-allowed-delete-cascading-owners-1", "sc:auth-anonymous-delete-cascading-owners-1"]}
              and not s["unresolved"], "both modes are issued, each scenario in the corpus that holds it", s)
        check(measured_check_rows(plan, owner) == [{"check": "gate:package", "stage": "immediate"}],
              "a node WITH an immediate check plan keeps exactly that plan (no requirement rows added)")
        check(measured_check_rows({"requirements": []}, {"requirements": [], "check_plan": []}) == [],
              "no check plan and no requirement: nothing to measure")
        check(measured_check_rows(plan, dict(followup, acceptance={"requirement_checks": ["parity:sc:create-owners"]}))
              == [{"check": "parity:sc:create-owners", "stage": "immediate", "requirement": REQ, "derived": "owned requirement check"}],
              "an owned parity check measures itself")
        corpora(root, ["delete-cascading-owners-1"], ["delete-cascading-owners-1", "auth-allowed-delete-cascading-owners-1",
                                                       "auth-anonymous-delete-cascading-owners-1"])
        s = verification_scope(root, plan, followup)
        check(any("delete-cascading-owners-1" in u["why"] for u in s["unresolved"]),
              "a scenario two corpora hold is unresolved, never guessed", s["unresolved"])
    print("OK: follow-up verification scope" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
