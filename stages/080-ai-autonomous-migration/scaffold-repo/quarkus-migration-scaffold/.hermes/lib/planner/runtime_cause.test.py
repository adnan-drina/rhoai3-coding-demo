#!/usr/bin/env python3
"""runtime_cause: attribution is not causation.

1. The counterexample: a CHANGED caller passes an UNCHANGED callee invalid
   input; the callee throws; the callee's file was committed by another
   cluster's accepted step. The baseline measured the scenario PASSING, so the
   candidate caused it: candidate-regression (never the callee's owner).
2. The v17 shape: the baseline tree already failed that scenario with the same
   exception from the same frame of the owner's stub (the record bound to the
   baseline tree): pre-existing-owner-defect, owner named.
3. No baseline measurement of the scenario: ambiguous (no owner).
4. More ambiguity: the baseline record bound to another tree; the throwing
   file changed by the candidate; a changed file on the failing path with a
   different stack; no product stack; no recorded owner; two owners.
5. A failure that differs from the baseline's is candidate-regression; any
   regression among several failures wins.
6. classify is pure: it reads nothing (a root that does not exist is fine),
   and the same inputs give the same answer. The same cases again with
   renamed types and paths.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import runtime_cause as RC  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def world(pkg: str, callee: str, caller: str, sid: str) -> dict:
    src = "src/main/java/%s/" % pkg.replace(".", "/")
    callee_path, caller_path = src + callee + ".java", src + caller + ".java"
    frame = {"class": "%s.%s" % (pkg, callee), "method": "findAll", "file": callee_path, "line": 12}
    caller_frame = {"class": "%s.%s" % (pkg, caller), "method": "list", "file": caller_path, "line": 30}
    tree = "b" * 64
    return {
        "callee": callee_path, "caller": caller_path, "sid": sid, "tree": tree,
        "issued": {"cluster": "u:cors", "task_id": "t_cors", "items": ["par:1"], "scenarios": [sid]},
        "steps": [{"cluster": "bootstrap", "verdict": "baseline", "changed": [], "candidate_sha256": "a" * 64},
                  {"cluster": "u:repo", "card": "t_repo", "commit": "c0ffee" * 6, "verdict": "accepted",
                   "changed": [callee_path], "candidate_sha256": tree}],
        "failure": {"obligation": "par:1", "scenario": sid, "entry_point": "ep:x", "exception": "java.lang.UnsupportedOperationException",
                    "frames": [frame, caller_frame], "stack_sha256": "s1"},
        "baseline_fail": {"verdict": "FAIL", "reason": "status 500 vs 200", "binding": {"candidate_sha256": tree},
                          "server_error": {"exception": "java.lang.UnsupportedOperationException", "frames": [frame, caller_frame],
                                           "stack_sha256": "s1"}},
        "baseline_pass": {"verdict": "PASS", "reason": "", "binding": {"candidate_sha256": tree}},
    }


def run(w: dict, *, changed: list[str], record: dict | None, failure: dict | None = None, steps=None, tree=None) -> dict:
    cur = {"failures": [failure or w["failure"]], "changed": changed}
    base = {"tree": w["tree"] if tree is None else tree, "records": {w["sid"]: record} if record is not None else {}}
    return RC.classify(Path("/nonexistent/root"), w["issued"], cur, w["steps"] if steps is None else steps, base)


def cases(pkg: str, callee: str, caller: str, sid: str) -> int:
    w = world(pkg, callee, caller, sid)
    # 1. the counterexample: changed caller, exception in the unchanged callee, baseline PASS
    got = run(w, changed=[w["caller"]], record=w["baseline_pass"])
    if got["class"] != RC.REGRESSION or got["owner"] is not None:
        return _fail("[%s] a changed caller breaking an unchanged callee is the candidate's regression: %s" % (pkg, got))
    # 2. the v17 shape: the baseline already failed identically in the owner's stub
    got = run(w, changed=["src/main/resources/application.properties"], record=w["baseline_fail"])
    if got["class"] != RC.PRE_EXISTING or (got["owner"] or {}).get("cluster") != "u:repo" or got["owner"]["paths"] != [w["callee"]]:
        return _fail("[%s] the baseline's identical failure in the owner's file is pre-existing: %s" % (pkg, got))
    # 3. no baseline measurement of the scenario
    got = run(w, changed=[], record=None)
    if got["class"] != RC.AMBIGUOUS or got["owner"] is not None or "no recorded measurement" not in got["reason"]:
        return _fail("[%s] a missing baseline measurement is ambiguous: %s" % (pkg, got))
    # 4. more ambiguity
    other = dict(w["baseline_fail"], binding={"candidate_sha256": "f" * 64})
    if run(w, changed=[], record=other)["class"] != RC.AMBIGUOUS:
        return _fail("[%s] a baseline record bound to another tree proves nothing" % pkg)
    if run(w, changed=[w["callee"]], record=w["baseline_fail"])["class"] != RC.AMBIGUOUS:
        return _fail("[%s] the candidate changed the throwing file: ambiguous" % pkg)
    diff_stack = dict(w["failure"], stack_sha256="s2")
    got = run(w, changed=[w["caller"]], record=w["baseline_fail"], failure=diff_stack)
    if got["class"] != RC.AMBIGUOUS or "failing path" not in got["reason"]:
        return _fail("[%s] a changed file on the failing path with another stack is ambiguous: %s" % (pkg, got))
    same_stack = run(w, changed=[w["caller"]], record=w["baseline_fail"])
    if same_stack["class"] != RC.PRE_EXISTING:
        return _fail("[%s] the identical stack through an edited caller is still the baseline's failure: %s" % (pkg, same_stack))
    nostack = dict(w["failure"], frames=[], exception="")
    if run(w, changed=[], record=w["baseline_fail"], failure=nostack)["class"] != RC.AMBIGUOUS:
        return _fail("[%s] no product stack: ambiguous" % pkg)
    if run(w, changed=[], record=w["baseline_fail"], steps=w["steps"][:1])["class"] != RC.AMBIGUOUS:
        return _fail("[%s] a pre-existing failure with no recorded owner has no one to name" % pkg)
    own = copy.deepcopy(w["steps"])
    own[1]["cluster"] = "u:cors"
    if run(w, changed=[], record=w["baseline_fail"], steps=own)["class"] != RC.AMBIGUOUS:
        return _fail("[%s] the card's own earlier step is not another owner" % pkg)
    if run(w, changed=[], record=w["baseline_fail"], tree="")["class"] != RC.AMBIGUOUS:
        return _fail("[%s] an unknown baseline tree proves nothing" % pkg)
    # 5. a different baseline failure is a regression; a regression among several wins
    moved = copy.deepcopy(w["baseline_fail"])
    moved["server_error"]["exception"] = "java.lang.IllegalStateException"
    if run(w, changed=[], record=moved)["class"] != RC.REGRESSION:
        return _fail("[%s] a failure that differs from the baseline's is the candidate's" % pkg)
    two = {"failures": [w["failure"], dict(w["failure"], scenario=sid + "-b", obligation="par:2")], "changed": []}
    base = {"tree": w["tree"], "records": {sid: w["baseline_fail"], sid + "-b": w["baseline_pass"]}}
    if RC.classify(None, w["issued"], two, w["steps"], base)["class"] != RC.REGRESSION:
        return _fail("[%s] one regression among the failures makes the candidate's" % pkg)
    # 6. deterministic
    a = run(w, changed=[], record=w["baseline_fail"])
    if a != run(w, changed=[], record=w["baseline_fail"]):
        return _fail("[%s] the classifier is not deterministic" % pkg)
    return 0


def main() -> int:
    for args in (("org.acme.clinic.repository", "OwnerStoreImpl", "OwnerService", "sc:cors-actual-owners"),
                 ("com.example.depot.store", "CrateLedgerImpl", "CrateDesk", "sc:list-crates")):
        if cases(*args):
            return 1
    print("OK: runtime cause (a changed caller breaking an unchanged callee is candidate-regression when the baseline "
          "passed; the baseline's identical, tree-bound failure in another cluster's file is pre-existing-owner-defect "
          "with that owner; a missing, foreign-bound or stackless baseline, a changed throwing file, a changed path with "
          "another stack, no owner or two owners are ambiguous; pure and deterministic; twice, renamed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
