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


def execution(worklist: dict[str, Any] | None, run: dict[str, Any] | None, tree: str = "",
              root: Any = None) -> dict[str, Any]:
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

    stages["parity"] = parity_stage(rn, wl_tree, root)
    out["stages"] = stages
    return out


def parity_stage(run: dict[str, Any], tree: str, root: Any = None) -> dict[str, Any]:
    """Requested scope, actual execution and measured verdict of the parity
    comparison, kept apart (review F3: a non-empty REQUESTED scenario list was
    reported as passed, even for rc 1 and verdict FAIL).

    The verdict comes only from the composed receipt of the run's security
    mode, bound to THIS candidate tree (compose-parity-receipt's binding), read
    through worklist.parity_state; the runner's rc is never a verdict. A scoped
    run passes when every requested scenario (and re-run read oracle) is PASS
    in that receipt; an unscoped run by the receipt's verdict. ``scenarios`` are
    the ones the receipt measured, never the ones requested."""
    par = ((run or {}).get("runtime") or {}).get("parity") if isinstance(run, dict) else None
    if not isinstance(par, dict) or not par.get("ran"):
        req = sorted(str(x) for x in ((par or {}).get("scenarios") or [])) if isinstance(par, dict) else []
        return _stage(NOT_RUN, "no parity comparison ran" + (" (%d requested)" % len(req) if req else ""), requested=req, scenarios=[])
    requested = sorted(str(x) for x in par.get("scenarios") or [])
    oracles = sorted(str(x) for x in par.get("read_oracles_rerun") or [])
    mode = str(par.get("security_mode") or "disabled")
    base = {"requested": requested, "scenarios": [], "security_mode": mode, "scoped": bool(par.get("scoped"))}
    if root is None:
        return _stage(UNKNOWN, "no destination root to read the %s-mode receipt from" % mode, **base)
    from planner.worklist import load_parity_receipt, parity_state
    receipt = load_parity_receipt(root, mode)
    if not receipt:
        return _stage(UNKNOWN, "the comparison ran and no %s-mode receipt was composed" % mode, **base)
    if str(receipt.get("security_mode") or "disabled") != mode:
        return _stage(UNKNOWN, "the receipt was taken in another security mode", **base)
    bind = receipt.get("binding") if isinstance(receipt.get("binding"), dict) else {}
    if str(bind.get("candidate_sha256") or "") != tree or not tree:
        return _stage(UNKNOWN, "the %s-mode receipt is bound to %s, not to this candidate" % (mode, str(bind.get("candidate_sha256") or "nothing")[:12]), **base)
    st = parity_state(receipt)
    if not st["known"]:
        return _stage(UNKNOWN, "the %s-mode receipt measured nothing" % mode, **base)
    scen_v, ep_v = st.get("scenarios") or {}, st.get("entry_points") or {}
    if requested or oracles:
        verdicts = [scen_v.get(x, "") for x in requested] + [ep_v.get(e, "") for e in oracles]
        measured = sorted(x for x in requested if scen_v.get(x))
    else:
        verdicts = [str(receipt.get("verdict") or "")]
        measured = sorted(scen_v)
    base["scenarios"] = measured
    if verdicts and all(v == "PASS" for v in verdicts):
        return _stage(PASSED, "%d requested check(s) PASS in the bound %s-mode receipt" % (len(verdicts), mode), **base)
    if any(v == "FAIL" for v in verdicts):
        return _stage(FAILED, "%d FAIL in the bound %s-mode receipt" % (sum(1 for v in verdicts if v == "FAIL"), mode), **base)
    return _stage(UNKNOWN, "inconclusive or unmeasured in the bound %s-mode receipt" % mode, **base)


def classes(ex: dict[str, Any] | None) -> list[str]:
    """The legacy class labels this execution proves. ``build`` and
    ``runtime`` when they passed; ``compile``, ``tests`` and ``parity`` when
    they ran with a known, bound result (the counts and verdicts, not the
    labels, say whether they are clean). Nothing for an unbound record."""
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
    if state("parity") in KNOWN:
        out.append("parity")    # the comparison executed with a bound verdict; the verdict itself gates acceptance
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
