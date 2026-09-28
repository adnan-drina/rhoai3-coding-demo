"""What a verification actually executed on a candidate, and the measurement
class labels that execution proves.

v23 (2026-09-28): every accept-commit carried ``classes: [build, compile,
tests]`` because ``_outcome_bridge._measurement`` stamped them, and the M2
baseline shortcut repeated the stamp, while the measure tuple read
``[4, 233, 0]``: zero failing tests on a tree that could not compile, so no
test ever ran. A class label is not a result. Each stage here records whether
it ran on this candidate, its result, and the tree it is bound to:

    passed | failed    it ran and its result is known
    blocked            it could not run (tests on a tree that does not compile)
    not-run            this verification did not run it
    unknown            it ran, or may have, but its result cannot be read

The numeric progress tuple (worklist.MEASURE_KEYS) is unchanged: it may read
zero failing tests while compilation prevents tests. The execution record is
the separate answer to "did the tests run".
"""
from __future__ import annotations

from typing import Any

SCHEMA = "rhoai3.measurement-execution/v1"
PASSED, FAILED, BLOCKED, NOT_RUN, UNKNOWN = "passed", "failed", "blocked", "not-run", "unknown"
KNOWN = (PASSED, FAILED)
STAGES = ("build", "compile", "tests", "runtime", "parity")


def _stage(state: str, detail: str, **extra: Any) -> dict[str, Any]:
    return dict({"state": state, "detail": detail}, **extra)


def execution(worklist: dict[str, Any] | None, run: dict[str, Any] | None, tree: str = "") -> dict[str, Any]:
    """The execution record of the verification that produced ``worklist``
    (``run`` is its run.json). ``tree`` is the product tree being judged: the
    record describes it only when the work list and the run are bound to it."""
    wl = worklist if isinstance(worklist, dict) else {}
    rn = run if isinstance(run, dict) else {}
    wl_tree = str(wl.get("candidate_sha256") or "")
    run_tree = str(rn.get("candidate_sha256") or "")
    bound = bool(wl_tree) and wl_tree == run_tree and (not tree or tree == wl_tree)
    out: dict[str, Any] = {"schema": SCHEMA, "tree": wl_tree, "bound": bound, "mode": str(rn.get("mode") or "")}
    if not bound:
        why = ("the verification record is bound to %s, not to %s" % ((wl_tree or run_tree or "no tree")[:16], tree[:16])
               if (wl_tree or run_tree) else "no verification record")
        out["stages"] = {s: _stage(UNKNOWN, why) for s in STAGES}
        return out
    m = wl.get("measure") or {}
    blocked = [str(b) for b in m.get("blocked") or []]
    stages: dict[str, dict[str, Any]] = {}

    cp = rn.get("classpath") or {}
    if any(b.startswith("build unresolvable") for b in blocked):
        stages["build"] = _stage(FAILED, "the build could not be resolved")
    elif cp.get("ran") and cp.get("rc") == 0:
        stages["build"] = _stage(PASSED, "the build classpath resolved on this candidate")
    elif cp.get("ran"):
        stages["build"] = _stage(FAILED, "classpath resolution exited %s" % cp.get("rc"))
    else:
        stages["build"] = _stage(NOT_RUN, "the classpath stage did not run")

    diag = rn.get("diagnostics") or {}
    ce = m.get("compile_errors")
    if diag.get("ran") and ce is not None:
        stages["compile"] = _stage(PASSED if ce == 0 else FAILED, "%d compile error(s) measured" % ce, count=ce)
    elif not diag.get("ran"):
        stages["compile"] = _stage(NOT_RUN, "the compiler diagnostics did not run")
    else:
        stages["compile"] = _stage(UNKNOWN, "; ".join(blocked) or "compile errors unknown")

    tr = rn.get("tests") or {}
    ft = m.get("failing_tests")
    sure = (wl.get("sources") or {}).get("surefire") or {}
    if ce:  # tests cannot run on a tree that does not compile; the tuple's 0 is the compile count's stand-in
        stages["tests"] = _stage(BLOCKED, "compilation failed (%d error(s)): the tests could not run" % ce)
    elif tr.get("ran") and sure and int(sure.get("reports") or 0) > 0 and ft is not None:
        ok = ft == 0 and tr.get("rc") == 0
        stages["tests"] = _stage(PASSED if ok else FAILED, "%d failing test(s); mvn test exited %s" % (ft, tr.get("rc")),
                                 count=ft, reports=int(sure.get("reports") or 0))
    elif not tr.get("ran"):
        stages["tests"] = _stage(NOT_RUN, "the tests did not run in this verification")
    else:
        stages["tests"] = _stage(UNKNOWN, "; ".join(b for b in blocked if "test" in b) or "no surefire report for this run")

    rt = wl.get("runtime") or {}
    ran_rt = any(isinstance(rt.get(g), dict) and rt[g].get("ran") for g in ("package", "boot"))
    stages["runtime"] = (_stage(PASSED, "the application packaged and started on this candidate") if rt.get("ready")
                         else _stage(FAILED, "a runtime gate ran and did not pass") if ran_rt
                         else _stage(NOT_RUN, "the runtime gates did not run"))

    parity = ((rn.get("runtime") or {}).get("parity") or {})
    scen = sorted(str(s) for s in parity.get("scenarios") or [])
    stages["parity"] = (_stage(PASSED, "%d scenario(s) replayed" % len(scen), scenarios=scen) if scen
                        else _stage(NOT_RUN, "no parity scenario was replayed"))
    out["stages"] = stages
    return out


def classes(ex: dict[str, Any] | None) -> list[str]:
    """The legacy class labels this execution proves. ``build`` and
    ``runtime`` when they passed; ``compile`` and ``tests`` when they ran with a
    known result (the counts, not the labels, say whether they are clean);
    ``parity`` when scenarios were replayed. Nothing for an unbound record."""
    if not isinstance(ex, dict) or not ex.get("bound"):
        return []
    st = ex.get("stages") or {}
    state = lambda s: str((st.get(s) or {}).get("state") or UNKNOWN)  # noqa: E731
    out = []
    if state("build") == PASSED:
        out.append("build")
    if state("compile") in KNOWN:
        out.append("compile")
    if state("tests") in KNOWN:
        out.append("tests")
    if state("runtime") == PASSED:
        out.append("runtime")
    if state("parity") == PASSED:
        out.append("parity")
    return out


def tests_status(ex: dict[str, Any] | None) -> tuple[str, str]:
    """(pass|fail|unknown, detail) of the full test suite on this execution:
    the M4 owner of a deferred ``measure:tests`` passes only on a bound,
    executed, passing suite."""
    if not isinstance(ex, dict) or not ex.get("bound"):
        return "unknown", "no verification bound to this candidate"
    t = (ex.get("stages") or {}).get("tests") or {}
    s = str(t.get("state") or UNKNOWN)
    if s == PASSED:
        return "pass", str(t.get("detail") or "")
    if s == FAILED:
        return "fail", str(t.get("detail") or "")
    return "unknown", "tests %s: %s" % (s, t.get("detail") or "")


def needed_classes(node: dict[str, Any]) -> set[str]:
    """The measurement classes a node's DECLARED acceptance requires now: one
    per ``measure:<class>`` check still on the node (a check deferred at
    publication has moved to M4 and is not required here), plus the class
    implied by gate/parity checks. The contract and its consumer read the same
    list."""
    acc = node.get("acceptance") or {}
    checks = [str(c) for c in acc.get("checks") or []]
    need = {c.split(":", 1)[1] for c in checks if c.startswith("measure:")}
    if "gate:runtime" in checks:
        need.add("runtime")
    if "parity:scenarios" in checks:
        need.add("parity")
    return need
