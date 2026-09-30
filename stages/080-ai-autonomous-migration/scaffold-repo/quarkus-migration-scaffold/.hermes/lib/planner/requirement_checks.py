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
  unit:handler-validation-guards / unit:handler-parameter-sites /
  unit:location-null-arguments
      worklist._assess_handler_parameters on the handler site, the guards and
      Location arguments against the FROZEN source's (no frozen source: unknown)
  adapter:<contract>
      response_adapters.verify against the rows rendered from the source policy
  parity:<adapter>-mode:<mode>
      that mode's receipt, bound to this tree, records the consumers PASS
  config:decided-keys
      datasource: check-datasource-decision.check; build_profiles: the decided
      list in application.properties and .mvn/maven.config; security: the
      decided switch key with a decided value
  build:clean-generation
      the compiler producer recorded every generated root with files, and no
      generated-source or unresolvable-build error is open
  parity:request-body-positive-negative
      the static generated-body condition no longer holds and every captured
      case scenario passes; a case with no source capture is unknown
  coverage:unresolved
      never met: missing SOURCE coverage stays unresolved

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
    if not parent:
        return []
    impl, path = parent + "Impl", owed
    if not owed:
        # the source already implements the fragment: nothing is owed, and the ONE implementation
        # selected in the decided build profile is what the checks judge (v21 t_0bc6319b: the
        # PetRepositoryOverride <- SpringDataPetRepositoryImpl facts named no owed implementation, so
        # every fragment check stayed UNKNOWN and no candidate could be accepted). None or several
        # selected: nothing to judge here (the recipe refuses those cases).
        selected = [str(x) for x in facts.get("selected") or [] if str(x)]
        if len(selected) != 1:
            return []
        impl = selected[0]
        path = "src/main/java/%s.java" % impl.replace(".", "/")
    return [{"parent": parent, "type": impl, "path": path, "members": list(facts.get("members") or []),
             "contract": FRAGMENT_IMPL_CONTRACT, "behaviour": facts.get("behaviour") or {},
             "cdi": {"scope": FRAGMENT_IMPL_SCOPE, "typed": FRAGMENT_IMPL_TYPED, "types": [impl],
                     "source": FRAGMENT_IMPL_CDI_SOURCE}}]


def corpus_scenario_modes(root: Path | None) -> dict[str, str]:
    """{scenario id (no sc: prefix): security mode} for every scenario exactly one bound corpus holds
    (ADR-014: one corpus per mode). The same authority the issued verification scope is derived from."""
    import json
    from planner.worklist import SCENARIO_CORPORA, SECURITY_MODES, _sid
    if root is None:
        return {}
    seen: dict[str, set[str]] = {}
    for mode, rel in zip(SECURITY_MODES, SCENARIO_CORPORA):
        p = Path(root) / rel
        try:
            doc = json.loads(p.read_text()) if p.is_file() else {}
        except (OSError, ValueError):
            continue
        for sc in doc.get("scenarios") or []:
            if isinstance(sc, dict) and sc.get("id"):
                seen.setdefault(_sid(sc["id"]), set()).add(mode)
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def _mode_record(root: Path, sid: str, mode: str) -> dict[str, Any]:
    """The one verdict record of `sid` in `mode`'s OWN scenario directory, or {}."""
    import json
    from planner.paths import PARITY_DIR
    from planner.worklist import PARITY_SCENARIO_SUBDIRS, SECURITY_MODES, _sid
    d = Path(root) / PARITY_DIR / PARITY_SCENARIO_SUBDIRS[SECURITY_MODES.index(mode)]
    hits = []
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            doc = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and _sid(doc.get("scenario")) == _sid(sid):
            hits.append(doc)
    return hits[0] if len(hits) == 1 else {}


def measure(root: Path, requirements: list[dict[str, Any]], *, worklist: dict[str, Any], scenarios: list[str],
            model: dict[str, Any] | None = None, tree: str = "", receipts: dict[str, dict[str, Any]] | None = None,
            diagnostics: dict[str, Any] | None = None, scenario_modes: dict[str, str] | None = None,
            governed: bool = False) -> dict[str, dict[str, str]]:
    """{check: {"status": pass|fail|unknown, "detail"}} for every check the
    given requirements name, on the tree `worklist` measures. `scenarios` are
    the parity scenarios this measurement ran; `model` the destination model
    (read on demand when a structural check needs it); `tree` the product-tree
    digest measured; `receipts` the parity receipt per security mode
    ({"disabled": doc, "enabled": doc}) -- a receipt counts only when it is
    bound to `tree`; `diagnostics` the compiler producer's document of this
    measurement (generated-root provenance). An authority passes what it
    measured itself; nothing here trusts a caller's PASS."""
    from planner.dest_model import DestModelUnavailable, dest_model
    from planner.worklist import _assess_implementations, _unit_path, _unit_types
    out: dict[str, dict[str, str]] = {}
    from planner.paths import PARITY_DIR
    from planner.worklist import _sid, parity_state, scenario_record
    ran = {_sid(s) for s in scenarios or []}
    # governed (a planned verification): the ISSUED assignment is the authority and nothing falls back to
    # either mode's evidence; otherwise the bound corpora say which mode a scenario belongs to
    expected_mode = {_sid(k): v for k, v in (scenario_modes if scenario_modes is not None
                                             else corpus_scenario_modes(root)).items()}
    open_sc = {_sid(s) for s in _open_scenarios(worklist)}
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
        """PASS only for a verdict this measurement ran, recorded PASS and
        bound to THIS tree: an empty work list, an INCONCLUSIVE record or a
        record of another candidate never stands for a measured PASS."""
        if _sid(sid) not in ran:
            return UNKNOWN, "scenario %s was not measured on this tree" % sid
        if _sid(sid) in open_sc:
            return FAIL, "scenario %s still has an open obligation" % sid
        mode = expected_mode.get(_sid(sid))
        if mode:
            # judged ONLY in its assigned mode (architect review of 7d77d14f: an enabled scenario passed on
            # disabled evidence): that mode's receipt, bound to this tree, records it PASS, and its own record
            # sits in that mode's directory, bound to this tree
            rc = (receipts or {}).get(mode) or {}
            rbind = rc.get("binding") if isinstance(rc.get("binding"), dict) else {}
            if str(rc.get("security_mode") or "disabled") != mode or (tree and str(rbind.get("candidate_sha256") or "") != tree):
                return UNKNOWN, "scenario %s has no %s-mode receipt bound to this tree" % (sid, mode)
            rv = {_sid(k): v for k, v in (parity_state(rc).get("scenarios") or {}).items()}.get(_sid(sid), "")
            if rv == "FAIL":
                return FAIL, "scenario %s is FAIL in the %s-mode receipt" % (sid, mode)
            if rv != "PASS":
                return UNKNOWN, "scenario %s is %s in the %s-mode receipt" % (sid, rv or "not recorded", mode)
            rec = _mode_record(Path(root), sid, mode) if root is not None else {}
            if rec and str(rec.get("security_mode") or mode) != mode:
                return UNKNOWN, "scenario %s's record was taken in %s mode, not %s" % (sid, rec.get("security_mode"), mode)
        elif governed:
            return UNKNOWN, "scenario %s is not in the issued verification scope" % sid
        else:
            rec = scenario_record(Path(root) / PARITY_DIR, sid) if root is not None else {}
        verdict = str(rec.get("verdict") or "")
        if verdict == "FAIL":
            return FAIL, "scenario %s came back FAIL: %s" % (sid, str(rec.get("reason") or "")[:200])
        if verdict != "PASS":
            return UNKNOWN, "scenario %s has %s" % (sid, ("verdict %s" % verdict) if rec else "no single verdict record")
        bound = rec.get("binding") if isinstance(rec.get("binding"), dict) else {}
        if tree and (str(bound.get("mode") or "") != "candidate" or str(bound.get("candidate_sha256") or "") != tree):
            return UNKNOWN, "scenario %s PASS is bound to %s, not to this tree %s" % (
                sid, str(bound.get("candidate_sha256") or bound.get("mode") or "nothing")[:12], tree[:12])
        return PASS, "scenario %s measured PASS on this tree" % sid

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
            elif chk in ("unit:handler-validation-guards", "unit:handler-parameter-sites", "unit:location-null-arguments"):
                status, detail = _handler_check(root, req, chk, get_model())
            elif chk.startswith("adapter:"):
                status, detail = _adapter_check(root, chk.split(":", 1)[1])
            elif chk.startswith("parity:") and "-mode:" in chk:
                status, detail = _mode_check(req, chk.rsplit(":", 1)[1], receipts or {}, tree)
            elif chk == "config:decided-keys":
                status, detail = _config_check(root, req)
            elif chk == "config:application-path":
                status, detail = _app_path_check(root, req)
            elif chk == "build:clean-generation":
                status, detail = _generation_check(worklist, diagnostics)
            elif chk == "parity:request-body-positive-negative":
                status, detail = _body_check(root, req, scen)
            elif chk.startswith("parity:"):
                status, detail = scen(chk[len("parity:"):])
            elif chk.startswith("location:"):
                # the comparator requires the source's Location on every exchange that builds one
                # (compare-scenario-parity.py): the Location is measured by the scenarios that cover it
                cov = [str(s) for s in (((req.get("facts") or {}).get("location") or {}).get("coverage") or []) if str(s)]
                res = [scen(s) for s in cov]
                if not cov:
                    status, detail = UNKNOWN, "no scenario measures the Location built at %s" % chk.split(":", 1)[1]
                elif any(r[0] == FAIL for r in res):
                    status, detail = FAIL, "; ".join(r[1] for r in res if r[0] == FAIL)[:300]
                elif any(r[0] == UNKNOWN for r in res):
                    status, detail = UNKNOWN, "; ".join(r[1] for r in res if r[0] == UNKNOWN)[:300]
                else:
                    status, detail = PASS, "every scenario covering this Location measured PASS on this tree"
            elif chk == "coverage:unresolved":
                status, detail = UNKNOWN, "unresolved coverage is never met"
            out[chk] = {"status": status, "detail": detail}
    return out


VERIFICATION_SCOPE_SCHEMA = "rhoai3.verification-scope/v1"


def verification_scope(root: Path, plan: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    """What a planned unit's own checks must MEASURE, from the admitted plan
    and the bound scenario corpora -- never from the remaining work list
    (v29 Owner: the behavior-verification unit was issued with no scenarios,
    no comparison ran and all 28 checks stayed unknown).

      parity:sc:<id>   that scenario, in the security mode of the corpus that
                       holds it (ADR-014: one corpus per mode)
      parity:ep:<ep>   that entry point's read oracle (default mode)
      location:<ep>    every scenario the requirement's facts.location.coverage
                       names: the comparator requires the source's Location
      the outcome's own scenarios (acceptance asks each of them measured)

    {schema, checks, scenarios_by_mode: {mode: [ids]}, read_oracles,
    corpus_sha256: {mode: digest}, unresolved: [{check, why}]}. A target no
    corpus holds, or two corpora hold, is unresolved -- never guessed."""
    import hashlib
    from planner.worklist import SCENARIO_CORPORA, SECURITY_MODES, _sid
    reqs = {str(r.get("id")): r for r in plan.get("requirements") or [] if isinstance(r, dict)}
    corpora: dict[str, set[str]] = {}
    digests: dict[str, str] = {}
    for mode, rel in zip(SECURITY_MODES, SCENARIO_CORPORA):
        p = Path(root) / rel
        if not p.is_file():
            continue
        data = p.read_bytes()
        digests[mode] = hashlib.sha256(data).hexdigest()
        try:
            import json
            doc = json.loads(data)
        except ValueError:
            continue
        corpora[mode] = {_sid(s.get("id")) for s in doc.get("scenarios") or [] if isinstance(s, dict) and s.get("id")}
    rows = [r for r in node.get("check_plan") or [] if isinstance(r, dict) and r.get("stage") == "immediate"]
    by_mode: dict[str, set[str]] = {}
    oracles: set[str] = set()
    unresolved: list[dict[str, str]] = []

    def place(sid: str, check: str) -> None:
        modes = [m for m, ids in corpora.items() if _sid(sid) in ids]
        if len(modes) != 1:
            unresolved.append({"check": check, "why": "scenario %s is in %s" % (
                sid, " and ".join(modes) + " corpora" if modes else "no bound corpus")})
            return
        by_mode.setdefault(modes[0], set()).add("sc:" + _sid(sid))

    for row in rows:
        chk = str(row.get("check") or "")
        if chk.startswith("parity:sc:"):
            place(chk[len("parity:"):], chk)
        elif chk.startswith("parity:ep:"):
            oracles.add(chk[len("parity:"):])
        elif chk.startswith("location:"):
            cov = ((reqs.get(str(row.get("requirement"))) or {}).get("facts") or {}).get("location") or {}
            sids = [str(s) for s in cov.get("coverage") or [] if str(s)]
            if not sids:
                unresolved.append({"check": chk, "why": "the requirement names no scenario that measures this Location"})
            for s in sids:
                place(s, chk)
    # the outcome's own scenarios are acceptance scope too (_covers asks each one measured)
    for s in node.get("scenarios") or []:
        place(str(s), "scenario:%s" % s)
    return {"schema": VERIFICATION_SCOPE_SCHEMA, "checks": sorted({str(r.get("check")) for r in rows}),
            "scenarios_by_mode": {m: sorted(v) for m, v in sorted(by_mode.items())},
            "read_oracles": sorted(oracles), "corpus_sha256": digests, "unresolved": unresolved}


def passed(measured: dict[str, dict[str, str]]) -> list[str]:
    return sorted(k for k, v in measured.items() if v.get("status") == PASS)


# ---------------------------------------------------------------------------
# the check classes whose implementation is ours (round 2): each asks the
# existing producer or checker, and an input it cannot read is UNKNOWN
# ---------------------------------------------------------------------------

def _site_of(req: dict[str, Any]) -> tuple[str, str, str, str]:
    """(path, type fqn, member name, parameter) of a handler requirement."""
    subject = str(req.get("subject") or "").split("|", 1)[0]
    typ, _, sig = subject.partition("#")
    facts = req.get("facts") or {}
    return (sorted(req.get("paths") or [""])[0], typ, sig.split("(", 1)[0], str(facts.get("parameter") or ""))


def _handler_check(root: Path, req: dict[str, Any], chk: str, model: dict[str, Any] | None) -> tuple[str, str]:
    """worklist._assess_handler_parameters on the requirement's handler site:
    the guard translation against the FROZEN source handler's guards
    (unit:handler-validation-guards), the parameter binding
    (unit:handler-parameter-sites), the Location arguments against the frozen
    source's buildAndExpand (unit:location-null-arguments). A comparison that
    needs the frozen source and cannot model it is UNKNOWN -- never the
    checker's silent "no claim"."""
    from planner.worklist import FROZEN_INPUT, _assess_handler_parameters, _unit_path, _unit_types, frozen_source_model
    facts = req.get("facts") or {}
    path, typ, name, param = _site_of(req)
    ptype = str(facts.get("parameter_type") or "")
    if not (path and typ and name and ptype):
        return UNKNOWN, "the requirement does not name its handler site"
    if model is None:
        return UNKNOWN, "the destination model is unavailable"
    row: dict[str, Any] = {"from": ptype, "to": "", "handler_parameter": True,
                           "sites": [{"path": path, "type": typ, "member": name, "signature": "", "parameter": param}]}
    if chk == "unit:handler-validation-guards":
        if not isinstance(facts.get("translation"), dict):
            return UNKNOWN, "the requirement carries no guard translation"
        row["translation"] = dict(facts["translation"])
    if chk == "unit:location-null-arguments":
        if not isinstance(facts.get("location"), dict):
            return UNKNOWN, "the requirement carries no Location obligation"
        row["location_translation"] = dict(facts["location"])
    if chk != "unit:handler-parameter-sites":
        if not (Path(root) / FROZEN_INPUT).is_dir():
            return UNKNOWN, "no frozen source (%s) to compare the handler with" % FROZEN_INPUT
        src, gap = frozen_source_model(Path(root))
        if src is None:
            return UNKNOWN, "the frozen source could not be modelled: %s" % gap
    by_path: dict[str, list[dict[str, Any]]] = {}
    for t in _unit_types(model):
        by_path.setdefault(_unit_path(t), []).append(t)
    verdicts = _assess_handler_parameters({"target_symbols": [row]}, by_path, "requirement:" + chk, root=Path(root))
    if not verdicts:
        return UNKNOWN, "the checker assessed nothing at %s.%s" % (typ, name)
    bad = [v for v in verdicts if v.get("verdict") != "ok"]
    if any(v.get("verdict") == "violates" for v in bad):
        return FAIL, "; ".join(str(v.get("detail")) for v in bad)[:400]
    if bad:
        return UNKNOWN, "; ".join(str(v.get("detail")) for v in bad)[:400]
    return PASS, "; ".join(str(v.get("detail")) for v in verdicts)[:300]


def _adapter_check(root: Path, contract: str) -> tuple[str, str]:
    """response_adapters.verify: the adapter file is the contract's template
    byte for byte and the configuration carries exactly the rows rendered from
    the SOURCE policy. A contract whose rendering needs a decision this tree
    does not record is UNKNOWN."""
    import response_adapters as ra
    kind = next((k for k, c in ra.CONTRACTS.items() if c.get("contract") == contract), "")
    if not kind:
        return UNKNOWN, "no registered adapter implements %s" % contract
    try:
        rows, _basis = ra.rows_for(Path(root), kind)
    except Exception as exc:  # noqa: BLE001 - an unrenderable policy is unknown, never a pass
        return UNKNOWN, "the %s rendering cannot be derived here: %s" % (contract, str(exc)[:200])
    problems = ra.verify(Path(root), kind, rows)
    if problems:
        return FAIL, "; ".join(problems)[:400]
    return PASS, "%s installed as rendered (%d row(s))" % (contract, len(rows))


def _mode_check(req: dict[str, Any], mode: str, receipts: dict[str, dict[str, Any]], tree: str) -> tuple[str, str]:
    """The security mode's composed receipt, bound to THIS tree, records every
    consumer entry point of the requirement PASS."""
    from planner.worklist import parity_state
    rec = receipts.get(mode) if isinstance(receipts.get(mode), dict) else None
    if not rec:
        return UNKNOWN, "no %s-mode receipt for this tree" % mode
    bound = str(((rec.get("binding") or {}) if isinstance(rec.get("binding"), dict) else {}).get("candidate_sha256") or "")
    if not tree or bound != tree:
        return UNKNOWN, "the %s-mode receipt is bound to %s, not to this tree" % (mode, bound[:12] or "nothing")
    st = parity_state(rec)
    if not st["known"]:
        return UNKNOWN, "the %s-mode receipt measured nothing" % mode
    eps = [str(e) for e in req.get("consumers") or []]
    if not eps:
        return UNKNOWN, "the requirement names no entry point to judge in %s mode" % mode
    verdicts = {ep: st["entry_points"].get(ep, "") for ep in eps}
    if any(v == "FAIL" for v in verdicts.values()):
        return FAIL, "%s mode: %s" % (mode, ", ".join("%s %s" % (k, v) for k, v in sorted(verdicts.items()) if v == "FAIL")[:300])
    if any(v != "PASS" for v in verdicts.values()):
        return UNKNOWN, "%s mode: %s not measured PASS" % (mode, ", ".join(k for k, v in sorted(verdicts.items()) if v != "PASS")[:300])
    return PASS, "%s mode: %d entry point(s) PASS on this tree" % (mode, len(eps))


def _config_check(root: Path, req: dict[str, Any]) -> tuple[str, str]:
    """The decided configuration the requirement names, as the destination
    renders it: datasource -> check-datasource-decision.check (the M2
    checker); build_profiles -> quarkus.profile in application.properties and
    -Dquarkus.profile in .mvn/maven.config, both the decided list; security ->
    the source's switch key present with one of its two decided values (its
    behaviour in each mode is the adapter/parity checks' question)."""
    import importlib.util
    from planner.decisions import load_decisions
    subject = str(req.get("subject") or "")
    try:
        doc = load_decisions(Path(root))
    except (OSError, ValueError) as exc:
        return UNKNOWN, "decisions.yaml unreadable: %s" % str(exc)[:200]
    props_p = Path(root) / "src/main/resources/application.properties"
    props = props_p.read_text(encoding="utf-8", errors="replace").splitlines() if props_p.is_file() else []
    values: dict[str, str] = {}
    for ln in props:
        t = ln.strip()
        if t and not t.startswith(("#", "!")) and "=" in t:
            k, v = t.split("=", 1)
            values[k.strip()] = v.strip()
    if subject == "datasource":
        chk = Path(__file__).resolve().parents[2] / "skills/migration/bootstrap-destination/scripts/check-datasource-decision.py"
        spec = importlib.util.spec_from_file_location("check_datasource_decision", chk)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        findings = mod.check(Path(root))
        return (FAIL, "; ".join(findings)[:400]) if findings else (PASS, "the rendered datasource is the decided one")
    if subject == "build_profiles":
        active = [str(x) for x in ((doc.get("build_profiles") or {}).get("active") or [])]
        if not active:
            return UNKNOWN, "no build profile is decided"
        want = ",".join(active)
        cfg = Path(root) / ".mvn/maven.config"
        mvn = cfg.read_text(encoding="utf-8").split() if cfg.is_file() else []
        gaps = []
        if values.get("quarkus.profile") != want:
            gaps.append("application.properties quarkus.profile=%s, decided %s" % (values.get("quarkus.profile"), want))
        if "-Dquarkus.profile=%s" % want not in mvn:
            gaps.append(".mvn/maven.config lacks -Dquarkus.profile=%s" % want)
        return (FAIL, "; ".join(gaps)) if gaps else (PASS, "the decided build profiles %s reach the build and the runtime" % want)
    if subject == "security":
        sw = ((doc.get("security") or {}).get("switch") or {}) if isinstance(doc.get("security"), dict) else {}
        key = str(sw.get("key") or "")
        if not key:
            return UNKNOWN, "the security decision names no switch key"
        allowed = {str(sw.get("disabled_value") or ""), str(sw.get("enabled_value") or "")} - {""}
        got = values.get(key)
        if got is None:
            return FAIL, "the decided security switch %s is not in application.properties" % key
        if got not in allowed and not got.startswith("${"):
            return FAIL, "%s=%s is neither decided value (%s)" % (key, got, ", ".join(sorted(allowed)))
        return PASS, "the decided security switch %s is present (%s)" % (key, got)
    return UNKNOWN, "no checker for decided configuration %r" % subject


def _generation_check(worklist: dict[str, Any], diagnostics: dict[str, Any] | None) -> tuple[str, str]:
    """The generator ran cleanly in THIS measurement: the compiler producer
    recorded every registered generated root with files, and the work list
    holds no generated-source error or unresolvable build."""
    if not isinstance(diagnostics, dict):
        return UNKNOWN, "no compiler diagnostics document for this measurement"
    roots = [r for r in diagnostics.get("generated_roots") or [] if isinstance(r, dict)]
    if not roots:
        return UNKNOWN, "the measurement recorded no generated root: generation is unproven"
    empty = [str(r.get("root") or r.get("path") or "?") for r in roots if not int(r.get("files") or 0)]
    bad = [str(i.get("id")) for i in worklist.get("items") or [] if isinstance(i, dict)
           and str(i.get("rule_id") or "") in ("GENERATED_SOURCE_ERROR", "BUILD_UNRESOLVABLE")]
    if bad:
        return FAIL, "generated-source / build errors: %s" % ", ".join(bad[:4])
    if empty:
        return FAIL, "generated root(s) with no files: %s" % ", ".join(empty)
    return PASS, "%d generated root(s) regenerated and compiled without error" % len(roots)


def _body_check(root: Path, req: dict[str, Any], scen: Any) -> tuple[str, str]:
    """The generated-body contract: the static condition (a qualified
    creator/setter pair refusing a body an ACCEPTED source capture sends)
    no longer holds on this tree (worklist.static_generated_body_items), and
    every omitted/null/empty/invalid case bound to a capture was measured and
    discharged. A case no capture sends is missing SOURCE coverage: UNKNOWN."""
    from planner.canonical import load_json
    from planner.paths import EVIDENCE_BUNDLE
    from planner.worklist import static_generated_body_items
    try:
        bundle = load_json(Path(root) / EVIDENCE_BUNDLE)
    except (OSError, ValueError):
        return UNKNOWN, "the evidence bundle is unreadable"
    items, notes = static_generated_body_items(Path(root), bundle)
    if items:
        return FAIL, "the generated-body condition still holds: %s" % items[0].get("message", "")[:300]
    if notes:
        return UNKNOWN, "; ".join(notes)[:300]
    cases = [c for c in ((req.get("facts") or {}).get("body_cases") or []) if isinstance(c, dict)]
    if not cases:
        return UNKNOWN, "the requirement names no request-body case"
    uncovered = ["%s.%s %s" % (c.get("model"), c.get("property"), c.get("case")) for c in cases if c.get("status") != "covered"]
    res = [scen(str(sid)) for c in cases if c.get("status") == "covered" for sid in c.get("scenarios") or []]
    if any(r[0] == FAIL for r in res):
        return FAIL, "; ".join(r[1] for r in res if r[0] == FAIL)[:300]
    if uncovered:
        return UNKNOWN, "no source capture for %s: the source's behaviour there is unknown" % ", ".join(uncovered[:6])
    if any(r[0] == UNKNOWN for r in res):
        return UNKNOWN, "; ".join(r[1] for r in res if r[0] == UNKNOWN)[:300]
    return PASS, "the static condition no longer holds and %d captured case scenario(s) pass" % len(res)


def _app_path_check(root: Path, req: dict[str, Any]) -> tuple[str, str]:
    """config:application-path (round 3): the destination's EFFECTIVE value
    of the owed key -- application.properties, a %<profile>. key of a decided
    build profile overriding the unprefixed one -- is the owed path (both
    normalised: leading slash, no trailing slash but the root)."""
    from response_adapters import read_properties
    from planner.decisions import load_decisions
    from planner.source_requirements import _norm_path
    facts = req.get("facts") or {}
    key, want = str(facts.get("dest_key") or ""), str(facts.get("dest_value") or "")
    if not key or not want:
        return UNKNOWN, "the requirement names no destination key or value"
    props_p = Path(root) / "src/main/resources/application.properties"
    if not props_p.is_file():
        return FAIL, "application.properties does not exist; %s is owed %s" % (key, want)
    props = read_properties(props_p.read_text(encoding="utf-8", errors="replace"))
    try:
        active = [str(x) for x in ((load_decisions(Path(root)).get("build_profiles") or {}).get("active") or [])]
    except (OSError, ValueError):
        active = []
    got, where = props.get(key), key
    for prof in active:
        if "%%%s.%s" % (prof, key) in props:
            got, where = props["%%%s.%s" % (prof, key)], "%%%s.%s" % (prof, key)
    if got is None:
        return FAIL, "%s is not set; the source serves at %s (%s=%s)" % (key, want, facts.get("source_key"), facts.get("source_value"))
    if _norm_path(got) != want:
        return FAIL, "%s=%s, owed %s (source %s=%s)" % (where, got, want, facts.get("source_key"), facts.get("source_value"))
    return PASS, "%s=%s serves where the source's %s=%s did" % (where, got, facts.get("source_key"), facts.get("source_value"))
