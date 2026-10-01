#!/usr/bin/env python3
"""The brief names WHY a card's outcome is not accepted, in the checks' own words (v30, 2026-10-01).

v30 t_223c101e: advance.py's unmet checks said exactly what to do -- "SpringDataPetRepositoryImpl does not
carry @ApplicationScoped ... annotate it @ApplicationScoped @Typed(SpringDataPetRepositoryImpl.class)" -- but
that detail lived only in a JSON comment. The worker re-verified the unchanged tree four times and crashed;
the Operator misdiagnosed the card from the typed executor's wording. The digest now leads with the deciding
checks of the latest acceptance record, verbatim; nothing is shown once the outcome is accepted."""
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


class FakeBoard:
    def __init__(self, recs):
        self.recs = recs

    def records(self, task, kind=None):
        return [r for r in self.recs if kind is None or r["kind"] == kind]


def rec(kind, accepted, unmet=None, run=34):
    return {"kind": kind, "run": run, "commit": "32a021a31284dc70", "outcome_accepted": accepted,
            "measurement": {"unmet_checks": unmet or {}}}


def main() -> int:
    ok = True

    def check(cond, what, detail=""):
        nonlocal ok
        print(("ok " if cond else "FAIL ") + what + ("" if cond else ": %r" % (detail,)))
        ok = ok and cond

    os.environ["HERMES_KANBAN_TASK"] = "t_223c101e"
    root = Path(tempfile.mkdtemp())
    unmet = {"req:R<-PetRepositoryOverride|structure:single-injectable-implementation": {"status": "fail", "detail": DETAIL},
             "req:R<-PetRepositoryOverride|unit:fragment-implementation": {"status": "fail", "detail": DETAIL}}
    board = FakeBoard([rec("issue", None), rec("accept-commit", False, unmet, 33), rec("accept-evaluated", False, unmet, 34)])
    u = B.outcome_unmet(root, board=board)
    check(u and u["run"] == 34 and u["record"] == "accept-evaluated" and len(u["checks"]) == 2,
          "the LATEST acceptance record's unmet checks are the section", u)
    lines = B.outcome_unmet_lines(u)
    check(lines and lines[0].startswith("WHY THE OUTCOME IS NOT ACCEPTED") and "annotate it" in "\n".join(lines)
          and "[fail]" in lines[1], "the digest quotes each deciding check, its state and its own detail", lines)
    check(B.outcome_unmet(root, board=FakeBoard([rec("accept-commit", False, unmet), rec("accept-evaluated", True, {})])) is None,
          "nothing once the latest record accepted the outcome")
    check(B.outcome_unmet(root, board=FakeBoard([rec("accept-evaluated", False, {})])) is None, "no unmet checks, no section")
    check(B.outcome_unmet(root, board=FakeBoard([rec("issue", None)])) is None, "no acceptance record yet, no section")
    many = {"c%d" % i: {"status": "unknown", "detail": "scenario sc:%d was not measured on this tree" % i} for i in range(9)}
    lines = B.outcome_unmet_lines({"record": "accept-evaluated", "run": 70, "commit": "cc04f9e", "checks": many})
    check(len(lines) == 8 and "3 more" in lines[-1], "a long list is bounded and says how to read the rest", lines)
    check(B.outcome_unmet_lines(None) == [], "no section, no lines")
    digest = B.brief_digest({"outcome_unmet": u, "procedure": "verify then advance", "issued_not_open": {}}, "x")
    check("WHY THE OUTCOME IS NOT ACCEPTED" in digest and digest.index("WHY THE OUTCOME") < len(digest),
          "brief_digest renders the section", digest[:400])
    print("OK: brief outcome_unmet" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
