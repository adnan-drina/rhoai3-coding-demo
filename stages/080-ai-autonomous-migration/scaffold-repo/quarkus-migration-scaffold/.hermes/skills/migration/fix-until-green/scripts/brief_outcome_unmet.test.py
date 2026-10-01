#!/usr/bin/env python3
"""The brief names WHY a card's outcome is not accepted, with the action each state calls for and the tree it
was measured on (v30, 2026-10-01; architect review of 49b1c13d).

v30 t_223c101e: the deciding detail ("SpringDataPetRepositoryImpl does not carry @ApplicationScoped ...") lived
only in a JSON comment; the worker re-verified an unchanged tree four times. The first summary added the line
"re-verifying an unchanged tree cannot change them", which is FALSE when the check is UNKNOWN because evidence is
missing (H-10: a fresh comparison is exactly what resolves it). Now: a measured FAIL is product work, a missing
or stale measurement is verification work, anything else blocks; a record of another tree is history."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import brief as B  # noqa: E402

DETAIL = ("org.springframework.samples.petclinic.repository.springdatajpa.SpringDataPetRepositoryImpl does not carry "
          "@jakarta.enterprise.context.ApplicationScoped: the delegate keeps its scope and restricts its bean types -- "
          "annotate it @jakarta.enterprise.context.ApplicationScoped @jakarta.enterprise.inject.Typed(SpringDataPetRepositoryImpl.class)")
TREE, OTHER = "a" * 64, "b" * 64


class FakeBoard:
    def __init__(self, recs):
        self.recs = recs

    def records(self, task, kind=None):
        return [r for r in self.recs if kind is None or r["kind"] == kind]


def rec(kind, accepted, unmet=None, run=34, tree=TREE):
    return {"kind": kind, "run": run, "commit": "32a021a31284dc70", "outcome_accepted": accepted, "tree": tree,
            "measurement": {"unmet_checks": unmet or {}}}


def main() -> int:
    ok = True

    def check(cond, what, detail=""):
        nonlocal ok
        print(("ok " if cond else "FAIL ") + what + ("" if cond else ": %r" % (detail,)))
        ok = ok and cond

    os.environ["HERMES_KANBAN_TASK"] = "t_223c101e"
    root = Path(tempfile.mkdtemp())
    fail = {"req:R|unit:fragment-implementation": {"status": "fail", "detail": DETAIL}}
    unknown = {"parity:sc:auth-anonymous-read-api-owners": {"status": "unknown", "detail": "scenario was not measured on this tree"}}

    u = B.outcome_unmet(root, board=FakeBoard([rec("accept-commit", False, fail, 33), rec("accept-evaluated", False, fail, 34)]),
                        current_tree=TREE)
    check(u and u["run"] == 34 and u["current"] is True, "the LATEST acceptance record, measured on THIS tree", u)
    lines = B.outcome_unmet_lines(u)
    text = "\n".join(lines)
    check("REPAIR" in lines[1] and "annotate it" in text and "THIS tree" in lines[0],
          "a measured FAIL on this tree calls for a product repair, quoting the check's detail", lines)
    check("cannot change" not in text, "no absolute claim that re-verifying cannot help", text)

    # the architect's probe: an UNKNOWN check (missing measurement) on an old record
    u = B.outcome_unmet(root, board=FakeBoard([rec("accept-evaluated", False, unknown, 70, tree=OTHER)]), current_tree=TREE)
    lines = B.outcome_unmet_lines(u)
    text = "\n".join(lines)
    check("VERIFY" in lines[1] and "no product edit" in lines[1], "UNKNOWN calls for verification, not a repair", lines)
    check("HISTORY" in lines[0] and u["current"] is False, "a record of another tree is labelled history", lines[0])
    check("cannot change" not in text, "the false 'cannot change' advice is gone (architect A6 probe)", text)

    # UNKNOWN -> fresh measured PASS on the same product tree: the section disappears
    board = FakeBoard([rec("accept-evaluated", False, unknown, 70), rec("accept-evaluated", True, {}, 71)])
    check(B.outcome_unmet(root, board=board, current_tree=TREE) is None,
          "after a fresh comparison accepts the outcome on the same tree, no unmet section remains")

    other = {"check:x": {"status": "blocked", "detail": "issued scope unresolved"}}
    lines = B.outcome_unmet_lines(B.outcome_unmet(root, board=FakeBoard([rec("accept-evaluated", False, other)]), current_tree=TREE))
    check("BLOCKED" in lines[1], "a state that is neither FAIL nor UNKNOWN is a blocker", lines)

    check(B.outcome_unmet(root, board=FakeBoard([rec("accept-evaluated", False, {})]), current_tree=TREE) is None,
          "no unmet checks, no section")
    check(B.outcome_unmet(root, board=FakeBoard([rec("issue", None)]), current_tree=TREE) is None, "no acceptance record yet")
    many = {"c%d" % i: {"status": "unknown", "detail": "scenario sc:%d was not measured on this tree" % i} for i in range(9)}
    lines = B.outcome_unmet_lines({"record": "accept-evaluated", "run": 70, "commit": "cc04f9e", "measured_tree": "a" * 16,
                                   "current": True, "checks": many})
    check(len(lines) == 8 and "3 more" in lines[-1], "a long list is bounded and names the selector for the rest", lines)
    check(B.outcome_unmet_lines(None) == [], "no section, no lines")
    digest = B.brief_digest({"outcome_unmet": B.outcome_unmet(root, board=FakeBoard([rec("accept-evaluated", False, fail)]),
                                                             current_tree=TREE),
                             "procedure": "verify then advance", "issued_not_open": {}}, "x")
    check("WHY THE OUTCOME IS NOT ACCEPTED" in digest, "brief_digest renders the section", digest[:400])
    print("OK: brief outcome_unmet" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
