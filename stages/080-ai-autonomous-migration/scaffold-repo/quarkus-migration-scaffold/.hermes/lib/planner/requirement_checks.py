"""Measure the requirement checks of a plan-semantics-v1 outcome on ONE tree.

An outcome that owns source requirements (outcome_graph.attach_requirements)
carries ``acceptance.requirement_checks``: the named checks of every
requirement it owns. ``outcome_lifecycle._covers`` accepts such an outcome
only when a measurement of the current tree RECORDS each of them. This module
is that measurement: it recomputes every check from existing producers --
never from a worker's claim -- and records the ones that PASS.

  gate:compile / gate:package / gate:augmentation / gate:startup
      the rebuilt work list of this tree: no open javac item in the
      requirement's files (the whole tree when it names none), and the
      runtime gate row (package; startup = boot) ran with rc 0
  structure:annotation-absent:<fqn>
      the destination model: no type declared in the requirement's paths
      carries the annotation (type, member or field); an unmodelled file is
      unknown
  unit:fragment-implementation / unit:fragment-behaviour-bodies /
  structure:single-injectable-implementation
      worklist._assess_implementations over the owed implementation the
      requirement names (existence, `implements`, a body per member, no stub
      body -- V17-3 -- and the concrete-only CDI exposure)
  parity:<scenario>
      the scenario was measured on this tree (the measurement's scenarios)
      and the rebuilt work list holds no open item for it
  behavior:repository-effects:<fragment>
      every planned repository verification row of the requirement is
      covered (none unresolved) and each of its scenarios passes as above
  anything else (unit:handler-validation-guards, unit:handler-parameter-sites,
  adapter:*, parity:*-mode:*, config:decided-keys, build:clean-generation,
  parity:request-body-positive-negative, coverage:unresolved)
      NOT measured here yet: recorded as unknown, so an outcome that owns one
      cannot be accepted (fail closed). ``coverage:unresolved`` is never met.

Pure over its inputs except for reading the destination model.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"
MEASURED_KINDS = ("gate:", "structure:annotation-absent:", "unit:fragment-implementation", "unit:fragment-behaviour-bodies",
                  "structure:single-injectable-implementation", "parity:", "behavior:repository-effects:")


def _open_scenarios(worklist: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for i in worklist.get("items") or []:
        if not isinstance(i, dict):
            continue
        for s in [i.get("scenario")] + list(i.get("scenarios") or []):
            if s:
                out.add(str(s))
    return out


def _gate(worklist: dict[str, Any], name: str) -> str:
    from planner.worklist import _gate_passing
    rt = worklist.get("runtime") if isinstance(worklist.get("runtime"), dict) else {}
    row = rt.get(name) if isinstance(rt.get(name), dict) else None
    if row is None or not row.get("ran"):
        return UNKNOWN
    return PASS if _gate_passing(rt, name) else FAIL


def _fragment_rows(requirement: dict[str, Any]) -> list[dict[str, Any]]:
    """The owed implementation obligation a repository requirement names, in
    the shape worklist._assess_implementations judges."""
    from planner.worklist import FRAGMENT_IMPL_CDI_SOURCE, FRAGMENT_IMPL_CONTRACT, FRAGMENT_IMPL_SCOPE, FRAGMENT_IMPL_TYPED
    facts = requirement.get("facts") or {}
    owed = str(facts.get("owed_implementation") or "")
    parent = str(facts.get("fragment") or "")
    if not owed or not parent:
        return []
    return [{"parent": parent, "type": parent + "Impl", "path": owed, "members": list(facts.get("members") or []),
             "contract": FRAGMENT_IMPL_CONTRACT, "behaviour": facts.get("behaviour") or {},
             "cdi": {"scope": FRAGMENT_IMPL_SCOPE, "typed": FRAGMENT_IMPL_TYPED, "types": [parent + "Impl"],
                     "source": FRAGMENT_IMPL_CDI_SOURCE}}]


def measure(root: Path, requirements: list[dict[str, Any]], *, worklist: dict[str, Any], scenarios: list[str],
            model: dict[str, Any] | None = None) -> dict[str, dict[str, str]]:
    """{check: {"status": pass|fail|unknown, "detail"}} for every check the
    given requirements name, on the tree `worklist` measures. `scenarios` are
    the parity scenarios this measurement ran; `model` the destination model
    (read on demand when a structural check needs it)."""
    from planner.dest_model import DestModelUnavailable, dest_model
    from planner.worklist import _assess_implementations, _unit_path, _unit_types
    out: dict[str, dict[str, str]] = {}
    ran = {str(s) for s in scenarios or []}
    open_sc = _open_scenarios(worklist)
    state = {"model": model, "tried": model is not None}

    def get_model() -> dict[str, Any] | None:
        if not state["tried"]:
            state["tried"] = True
            try:
                state["model"] = dest_model(Path(root))
            except DestModelUnavailable:
                state["model"] = None
        return state["model"]

    def scen(sid: str) -> tuple[str, str]:
        if sid not in ran:
            return UNKNOWN, "scenario %s was not measured on this tree" % sid
        if sid in open_sc:
            return FAIL, "scenario %s still has an open obligation" % sid
        return PASS, "scenario %s measured and discharged" % sid

    for req in requirements or []:
        if not isinstance(req, dict):
            continue
        for chk in req.get("acceptance") or []:
            chk = str(chk)
            if chk in out and out[chk]["status"] != PASS:
                continue  # a check that failed or is unknown for one requirement stays so
            status, detail = UNKNOWN, "no measurement producer for this check yet (fail closed)"
            if chk == "gate:compile":
                # the requirement's own compile half: no open javac item in
                # its files (the whole tree compiling is M4's measurement)
                scope = set(req.get("paths") or [])
                javac = [i for i in worklist.get("items") or [] if isinstance(i, dict) and str(i.get("source") or "") == "javac"
                         and (not scope or str(i.get("path") or "") in scope)]
                known = bool((worklist.get("measure") or {}).get("known"))
                status = (FAIL if javac else PASS) if known else UNKNOWN
                detail = ("%d open compile item(s) in %s" % (len(javac), ", ".join(sorted(scope)) or "the tree")) if known else "the measure is unknown"
            elif chk in ("gate:package", "gate:augmentation"):
                status, detail = _gate(worklist, "package"), "the package gate row of this measurement"
            elif chk == "gate:startup":
                status, detail = _gate(worklist, "boot"), "the boot gate row of this measurement"
            elif chk.startswith("structure:annotation-absent:"):
                ann = chk.split(":", 2)[2]
                model_ = get_model()
                paths = set(req.get("paths") or [])
                rows = [t for t in _unit_types(model_) if _unit_path(t) in paths] if model_ else []
                if model_ is None or {_unit_path(t) for t in rows} != paths:
                    status, detail = UNKNOWN, "the destination model does not cover %s" % ", ".join(sorted(paths))
                else:
                    named = any(str(a.get("fqn") or "") == ann for t in rows
                                for d in [t] + list(t.get("declared") or []) + list(t.get("fields") or [])
                                for a in (d.get("annotations") or []) if isinstance(a, dict))
                    status, detail = (FAIL, "%s still carries %s" % (", ".join(sorted(paths)), ann)) if named else (
                        PASS, "%s no longer carries %s" % (", ".join(sorted(paths)), ann))
            elif chk in ("unit:fragment-implementation", "unit:fragment-behaviour-bodies",
                         "structure:single-injectable-implementation"):
                rows = _fragment_rows(req)
                model_ = get_model()
                if not rows:
                    status, detail = UNKNOWN, "the requirement names no owed implementation to assess"
                elif model_ is None:
                    status, detail = UNKNOWN, "the destination model is unavailable"
                else:
                    by_path: dict[str, list[dict[str, Any]]] = {}
                    for t in _unit_types(model_):
                        by_path.setdefault(_unit_path(t), []).append(t)
                    verdicts = _assess_implementations(Path(root), {"implementation_obligations": rows}, model_, by_path,
                                                       "requirement:repository-architecture")
                    bad = [v for v in verdicts if v.get("verdict") != "ok"]
                    if any(v.get("verdict") == "violates" for v in bad):
                        status, detail = FAIL, "; ".join(str(v.get("detail")) for v in bad)[:400]
                    elif bad:
                        status, detail = UNKNOWN, "; ".join(str(v.get("detail")) for v in bad)[:400]
                    else:
                        status, detail = PASS, "the owed implementation exists, implements its parent, carries no stub body and the concrete-only CDI exposure"
            elif chk.startswith("behavior:repository-effects:"):
                ver = [v for v in ((req.get("facts") or {}).get("verification") or []) if isinstance(v, dict)]
                if not ver or any(v.get("status") != "applicable" for v in ver):
                    status, detail = UNKNOWN, ("the repository's functional coverage is unresolved for %s (owned verification "
                                               "debt; never PASS)" % ", ".join(str(v.get("member")) for v in ver
                                                                                if v.get("status") != "applicable")[:300])
                else:
                    res = [scen(str(s)) for v in ver for s in v.get("scenarios") or []]
                    if any(r[0] == FAIL for r in res):
                        status, detail = FAIL, "; ".join(r[1] for r in res if r[0] == FAIL)[:300]
                    elif any(r[0] == UNKNOWN for r in res):
                        status, detail = UNKNOWN, "; ".join(r[1] for r in res if r[0] == UNKNOWN)[:300]
                    else:
                        status, detail = PASS, "every read and committed write effect measured and discharged"
            elif chk.startswith("parity:") and "-mode:" not in chk and chk != "parity:request-body-positive-negative":
                status, detail = scen(chk[len("parity:"):])
            elif chk == "coverage:unresolved":
                status, detail = UNKNOWN, "unresolved coverage is never met"
            out[chk] = {"status": status, "detail": detail}
    return out


def passed(measured: dict[str, dict[str, str]]) -> list[str]:
    return sorted(k for k, v in measured.items() if v.get("status") == PASS)
