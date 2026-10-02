#!/usr/bin/env python3
"""Bounded local qualification of the repeatable initial M3 plan (plan semantics v1).

Runs ONLY in disposable directories. No model call, no live Kanban board (a
FakeNative stands in, SYNTHETIC), no cluster, no network. Reports every
case with its proof level, the commands' tool identities, durations, the
initial-plan comparison (fingerprints and plan digests) and every missing
prerequisite as an explicit NOT-RUN, never as a pass.

Proof levels:

  producer-replay   the pinned producers that can run here, executed on
                    independent clean copies (JdkDiagnostics under two JVM
                    locales, on two polluted-then-cleaned trees and a warm
                    replay; the decided-repairs engine on the JDK parse tree)
  recorded-evidence the M1 -> M2 chain on SYNTHETIC specimen evidence
                    (planner.specimens: bundle, bootstrap, simulated
                    verification, work list, baseline, admission) through the
                    production consumers: source requirements, the one
                    initial graph builder, admission's plan contract and seal,
                    and disposable native publication. It proves planning
                    determinism for fixed evidence, never live source
                    behaviour or a successful migration.

  preserved         --specimen DIR: the same consumers on PRESERVED M1
                    evidence of a real run (structure, entry points, corpus,
                    admission-time work list), two reordered copies; no
                    producer is re-run on it

  --source DIR      the M1 structure producer (JdkModelExtract) re-run on two
                    clean copies of a FROZEN source with an offline classpath

  --fresh A B       two INDEPENDENT fresh M1 -> M2 roots of one frozen source
                    (producers re-run on each by the caller): requirements,
                    logical graph and compatibility-objective membership
                    compared outcome by outcome

  --build-fresh DIR the driver BUILDS the two fresh roots itself: the existing
                    M1 -> M2 producer sequence (rehearse-legacy.sh: freeze,
                    build evidence, JDK model, MTA when a CLI is on PATH,
                    evidence bundle, bootstrap, first verification) run twice
                    on two clean copies of the frozen source DIR, then the
                    offline corpus derivations (derive-source-scenarios.py,
                    both modes); each step's receipt is judged per root, the
                    roots are compared as --fresh does and, when both ran
                    MTA, their findings are compared. Source CAPTURES (they
                    start the source runtime and its database) are named
                    NOT-RUN, never faked. --producer CMD replaces the
                    producer (fixtures only; the claim then says so).

  MTA               (producer level, with --source) the M1 MTA producer
                    (scan-with-mta mta-analyze-legacy.sh, its own ensure_cli
                    resolution and pins) run on two clean frozen copies; the
                    semantic findings (rule id, file relative to the
                    analysed copy, line) compared. NOT-RUN only when no CLI
                    resolves or ensure_cli refuses it as unusable, with the
                    reason; a non-admissible CLI is run, compared and named
                    non-admissible in the claim boundary.

  --patches A B     two INDEPENDENT applications on the same frozen inputs:
                    their typed-repair records (rhoai3.typed-repair-record/v1
                    under verification/loop/typed-repair/) compared per
                    cluster, recipe and target; a deterministic recipe
                    (catalog implementation.kind typed-repair or
                    decided-repairs) must stage the identical patch digest
                    with the same outcome and changed files

  check schedule    (recorded-evidence, always run) the check-schedule/v1
                    view (roadmap M-2: each check's kind, owner, verification
                    prerequisites, earliest measurement point, causal order,
                    both acceptance states, typed findings) derived twice from
                    two shuffled specimen checkouts under compatibility
                    objectives, and from the saved v29 initial plan
                    (lib/planner/fixtures/v29-plan-r1-schedule.json.gz) twice
                    and in reversed order: identical logical ownership,
                    checks, dependencies and budgets, nothing unschedulable

Usage: qualify-repeatability.py [--out FILE] [--keep DIR] [--specimen DIR] [--source DIR] [--fresh A B]
                                [--build-fresh DIR [--producer CMD]] [--patches A B] [--no-producers]
Exit 0 when no case FAILED (NOT-RUN cases are listed, with their reason).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HERMES = HERE.parents[3]
sys.path.insert(0, str(HERMES / "lib"))
sys.path.insert(0, str(HERMES / "kernel"))

from planner import outcome_graph as OG  # noqa: E402
from planner import outcome_lifecycle as L  # noqa: E402
from planner import plan_semantics as PS  # noqa: E402
from planner import source_requirements as SR  # noqa: E402
from planner import specimens as S  # noqa: E402
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import PLAN_SEMANTICS, PLAN_VIEW  # noqa: E402

LOOP = HERMES / "skills/migration/fix-until-green/scripts"
TOOL = LOOP / "jdk-diagnostics/JdkDiagnostics.java"
EXPORTS = ["--add-exports", "jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED",
           "--add-exports", "jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED"]
PASS, FAIL, NOT_RUN = "PASS", "FAIL", "NOT-RUN"


def decisions(**kw) -> dict:
    d = S.full_decisions(**kw)
    d["loop"] = {"plan_semantics": "v1"}
    d["build_profiles"] = {"adr": "ADR-001", "active": ["spring-data-jpa"]}
    return d


class Q:
    def __init__(self, tmp: Path, specimen: Path | None = None, source: Path | None = None):
        self.tmp = tmp
        self.specimen = specimen
        self.source = source
        self.cases: list[dict] = []
        self.evidence: dict = {}

    def case(self, name: str, level: str, fn) -> None:
        t0 = time.time()
        try:
            status, detail = fn()
        except Exception as exc:  # a crash is a failure, with its cause
            status, detail = FAIL, "%s: %s" % (type(exc).__name__, str(exc)[:400])
        self.cases.append({"case": name, "level": level, "status": status, "detail": detail,
                           "seconds": round(time.time() - t0, 2)})

    def dest(self, name: str, *, spec="migration", names=None, base="org.acme.clinic", seed=None, dec=None,
             errors=None, run_id="", structure_status="ok") -> Path:
        d = self.tmp / name
        S.build_dest(d, S.specimen(spec, base=base, names=names) if spec == "migration" else S.specimen(spec, base=base),
                     decisions=dec if dec is not None else decisions(), seed=seed, structure_status=structure_status)
        S.prepare_loop(d, errors=errors or [], diag_producer=S.CURRENT_DIAG_PRODUCER)
        if run_id:
            (d / "run-budget.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
        return d


def sem(root: Path) -> dict:
    return load_json(root / PLAN_SEMANTICS)


# ---------------------------------------------------------------------------
# recorded-evidence cases
# ---------------------------------------------------------------------------

def run_cases(q: Q) -> None:
    a = q.dest("petclinic-a", run_id="run-a")
    b = q.dest("petclinic-b", seed=11, run_id="run-b")          # shuffled producer sets, other checkout, other run

    def clean_copies():
        ra, rb = load_json(a / "evidence/planning/admission-receipt.json"), load_json(b / "evidence/planning/admission-receipt.json")
        if ra["status"] != "ADMITTED" or rb["status"] != "ADMITTED":
            return FAIL, "admission %s / %s: %s" % (ra["status"], rb["status"], (ra["reasons"] + rb["reasons"])[:3])
        c = PS.compare(sem(a), sem(b))
        pa, pb = L.initial_plan_from_root(a), L.initial_plan_from_root(b)
        q.evidence["initial_plan_comparison"] = {
            "a": {"root": str(a), "run_id": "run-a", "input_fingerprint": sem(a)["input_fingerprint"],
                  "plan_fingerprint": sem(a)["plan_fingerprint"], "sealed": ra["seals"]["plan_semantics"],
                  "run_bound_revision_digest": pa["digest"]},
            "b": {"root": str(b), "run_id": "run-b", "input_fingerprint": sem(b)["input_fingerprint"],
                  "plan_fingerprint": sem(b)["plan_fingerprint"], "sealed": rb["seals"]["plan_semantics"],
                  "run_bound_revision_digest": pb["digest"]},
            "equal": c["equal"], "differences": c["differences"], "audit_only": [x["where"] for x in c["audit_differences"]],
            "logical_graph_equal": PS.graph_projection(pa) == PS.graph_projection(pb),
        }
        q.evidence["initial_logical_m3_inventory"] = load_json(a / PLAN_VIEW)
        if not c["equal"] or ra["seals"]["plan_semantics"] != rb["seals"]["plan_semantics"]:
            return FAIL, "semantic plans differ: %s" % json.dumps(c["differences"])[:400]
        if PS.graph_projection(pa) != PS.graph_projection(pb) or pa["digest"] == pb["digest"]:
            return FAIL, "the run-bound revisions must differ only in their run binding"
        return PASS, "plan %s equal across two clean copies; run-bound revision digests %s / %s differ" % (
            sem(a)["plan_fingerprint"][:16], pa["digest"][:12], pb["digest"][:12])

    q.case("two clean copies, same qualified inputs", "recorded-evidence", clean_copies)

    def bindings():
        pa, pb = L.initial_plan_from_root(a), L.initial_plan_from_root(b)
        ka = {n["outcome_id"]: n["budget"]["key"] for n in pa["nodes"] if n.get("budget")}
        kb = {n["outcome_id"]: n["budget"]["key"] for n in pb["nodes"] if n.get("budget")}
        if set(ka) != set(kb) or any(ka[k] == kb[k] for k in ka) or not all("run-a" in v for v in ka.values()):
            return FAIL, "budget keys must be the same outcomes bound to each run"
        run = load_json(a / "verification/build/run.json")
        run["total_ms"] = 999999
        write_canonical(a / "verification/build/run.json", run)
        if PS.from_root(a)["plan_fingerprint"] != sem(a)["plan_fingerprint"]:
            return FAIL, "an elapsed time changed the plan"
        return PASS, "%d outcomes, every budget key bound to its own run; elapsed time audit-only" % len(ka)

    q.case("different run ids, paths, timestamps, elapsed times", "recorded-evidence", bindings)
    q.case("shuffled producer sets", "recorded-evidence",
           lambda: (PASS, "seed 11 vs unshuffled compared equal above") if q.evidence.get("initial_plan_comparison", {}).get("equal")
           else (FAIL, "see the clean-copies case"))

    def twin():
        t = q.dest("ledger-twin", base="com.example.ledger", names=S.LEDGER_NAMES)
        shape = lambda d: sorted((r["rule"], r["status"], (r.get("recipe") or {}).get("id")) for r in sem(d)["plan"]["requirements"])  # noqa: E731
        if shape(t) != shape(a):
            return FAIL, "renamed twin rule applications differ"
        return PASS, "%d requirement rule applications identical under renamed packages, classes and members" % len(shape(t))

    q.case("renamed structural twin", "recorded-evidence", twin)

    def non_http():
        d = q.dest("warehouse", spec="scheduled", base="org.acme.warehouse")
        reqs = [r for r in sem(d)["plan"]["requirements"] if r["rule"] == "behavior-verification/v1"]
        kinds = sorted({r["facts"]["kind"] for r in reqs})
        if not reqs or "http" in kinds or any(r["status"] != "unresolved" for r in reqs):
            return FAIL, "non-HTTP entry points must be named unresolved verification responsibilities: %s" % kinds
        return PASS, "%d non-HTTP entry points (%s) retained as unresolved verification responsibilities" % (len(reqs), ", ".join(kinds))

    q.case("structurally different application, non-HTTP entry points", "recorded-evidence", non_http)

    def partial():
        doc = PS.from_root(a)
        types = [t for t in load_json(a / "evidence/planning/evidence-bundle.json")["structure"]["types"] if "Repository" not in t["fqn"]]
        bundle = load_json(a / "evidence/planning/evidence-bundle.json")
        out = SR.derive(types=types, entry_points=bundle["entry_points"], catalog=load_json(a / ".hermes/planning/catalogs/compat-mapping.json"),
                        decisions={}, oracles=None, structure_complete=False, generator=None, generator_known=False)
        na = [r["id"] for r in out["requirements"] if r["status"] == "not-applicable"]
        repo = [r for r in out["requirements"] if r["id"] == "req:repository-architecture:*"]
        if na or not repo or repo[0]["status"] != "unresolved" or not doc["plan"]["requirements"]:
            return FAIL, "partial model proved an absence: %s" % na
        return PASS, "a partial model yields named unknowns (%s), no not-applicable, no dropped obligation" % repo[0]["unknowns"][0][:80]

    q.case("missing or partial source model", "recorded-evidence", partial)

    def missing_oracle():
        g = (sem(a)["plan"]["graph"] or {})
        unres = [u for u in g.get("unresolved") or [] if u["id"].startswith("unresolved:verification:")]
        if not unres or any("PASS" in str(n.get("acceptance")) for n in g.get("nodes") or []):
            return FAIL, "missing oracles must be unresolved responsibilities"
        return PASS, "%d verification responsibility row(s) unresolved, blocking ship; no invented scenario" % len(unres)

    q.case("missing behaviour oracle", "recorded-evidence", missing_oracle)

    def deltas():
        d1 = q.dest("delta-decision", dec=decisions(max_attempts=5))
        c1 = PS.compare(sem(a), sem(d1))
        d2 = q.tmp / "delta-recipe"
        shutil.copytree(a, d2)
        cat = load_json(d2 / ".hermes/planning/catalogs/compat-mapping.json")
        cat["migration_recipes"]["handler-validation-translation"]["version"] = "2"
        (d2 / ".hermes/planning/catalogs/compat-mapping.json").write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        c2 = PS.compare(sem(a), PS.from_root(d2))
        ok = (not c1["equal"] and c1["first_divergent_producer"] == "decisions"
              and not c2["equal"] and c2["first_divergent_producer"] == "contracts" and any(x["class"] == "recipe" for x in c2["differences"]))
        return (PASS if ok else FAIL), "decision delta first diverges at %s; recipe-version delta at %s (%s)" % (
            c1["first_divergent_producer"], c2["first_divergent_producer"], sorted({x["class"] for x in c2["differences"]}))

    q.case("different decision / recipe pin", "recorded-evidence", deltas)

    def ownership():
        g = L.initial_plan_from_root(a)
        val = [r for r in g["requirements"] if r["rule"] == "request-validation/v1"]
        owner = g["requirement_ownership"][val[0]["id"]]
        hits = {OG.owner_of_finding(g, {"id": "par:%d" % i, "kind": "parity", "entry_point": ep}).get("owner")
                for i, r in enumerate(val) for ep in r["consumers"]}
        hits.add(OG.owner_of_finding(g, {"id": "err:1", "kind": "compile", "path": val[0]["paths"][0]}).get("owner"))
        budget = next(n["budget"] for n in g["nodes"] if n["outcome_id"] == owner)
        new = OG.owner_of_finding(g, {"id": "err:2", "kind": "compile", "path": "src/main/java/org/acme/clinic/Unplanned.java"})
        if hits != {owner} or new.get("owner") is not None or new.get("class") != "missing-planning-rule":
            return FAIL, "owners %s, new finding %s" % (hits, new)
        return PASS, "compile and behaviour findings through both handlers resolve to %s (budget %s unchanged); an unowned finding is %s" % (
            owner, budget["limit"], new["class"])

    q.case("same defect via several endpoints / genuine new failure", "recorded-evidence", ownership)

    def oversize():
        g = L.initial_plan_from_root(a)
        big = copy.deepcopy(next(r for r in g["requirements"] if r["rule"] == "repository-architecture/v1"))
        big["paths"] = ["src/main/java/p/F%02d.java" % i for i in range(25)]
        wl = load_json(a / "evidence/planning/worklist.json")
        g2 = OG.derive_initial_graph(run_id="q", worklist=wl, entry_points=[], oracles=None, references=None,
                                     provenance={"snapshot_kind": "synthetic", "scope_note": "oversize", "construction": "qualify",
                                                 "observed_migration_event": False}, requirements=[big])
        u = [x for x in g2["unresolved"] if big["id"] in (x.get("requirements") or [])]
        return (PASS, u[0]["reason"][:90]) if u and "UNIT_OVERSIZE" in u[0]["reason"] else (FAIL, "no typed blocker")

    q.case("oversize unit", "recorded-evidence", oversize)

    def brief():
        import importlib.util
        spec = importlib.util.spec_from_file_location("brief_mod", LOOP / "brief.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ctrl = [c for c in load_json(a / "evidence/planning/worklist.json")["clusters"] if c["path"].endswith("OwnerRestController.java")][0]
        got = mod.planned_requirements(a, ctrl["write_set"])
        legacy = mod.planned_requirements(q.tmp / "no-such-root", ctrl["write_set"])
        ids = sorted((g["recipe"] or {}).get("id") or "-" for g in got)
        if legacy or "handler-validation-translation" not in ids or not all(g["acceptance"] for g in got):
            return FAIL, "brief planned requirements: %s" % ids
        return PASS, "the controller card's brief names %d planned requirement(s) with recipes %s and their checks" % (len(got), ids)

    q.case("card brief carries the planned recipe and checks", "recorded-evidence", brief)

    def publication():
        from planner.outcome_native import FakeNative
        import k4_graph as G
        root = q.tmp / "publish"
        root.mkdir()
        plan = L.initial_plan_from_root(a)
        native = FakeNative(q.tmp)
        m2 = native.create(title="M2 PLAN", body="plan", assignee="implementer", parents=[], key="m2-plan",
                           skills=["paved-road-m2"], workspace="", max_retries=1)
        store = G.init_store(root, run_id="run-a", m2_task=m2, native_db=native.db_path, protocol="outcome-board/v1")
        G.persist_plan(store, plan)
        native.fail_after = {"create": 3}
        try:
            G.publish_plan(root, store, native, plan, m2_task=m2)
            interrupted = False
        except Exception:
            interrupted = True
        G.publish_plan(root, store, native, plan, m2_task=m2)
        G.publish_plan(root, store, native, plan, m2_task=m2)
        keys = [r[0] for r in store.conn.execute("SELECT native_key FROM publication")]
        dup = [k for k in keys if len(native.by_key(k)) != 1]
        if not interrupted or dup or len(keys) != len(plan["nodes"]):
            return FAIL, "interrupted=%s duplicates=%s keys=%d nodes=%d" % (interrupted, dup[:3], len(keys), len(plan["nodes"]))
        return PASS, "publication interrupted after 3 creates, retried twice: %d native keys, one task each (FakeNative, SYNTHETIC)" % len(keys)

    q.case("interrupted publication / retry", "recorded-evidence", publication)

    def legacy():
        d = q.dest("legacy", dec=S.full_decisions())
        r = load_json(d / "evidence/planning/admission-receipt.json")
        p = L.initial_plan_from_root(d)
        if (d / PLAN_SEMANTICS).exists() or "plan_semantics" in r["seals"] or "requirements" in p or "plan_semantics" in load_json(d / "evidence/planning/worklist.json"):
            return FAIL, "a run without the decision gained v1 records"
        return PASS, "no decision: no semantics file, no seal, no requirements, legacy work list (existing mixed-protocol refusals: outcome_board.test.py)"

    q.case("old pinned run", "recorded-evidence", legacy)

    def tamper():
        d = q.tmp / "tamper"
        shutil.copytree(b, d)
        doc = load_json(d / PLAN_SEMANTICS)
        doc["plan"]["requirements"] = doc["plan"]["requirements"][1:]
        write_canonical(d / PLAN_SEMANTICS, doc)
        _r, gaps = verify_receipt(d, require_admitted=True)
        wl = load_json(d / "evidence/planning/worklist.json")
        wl["candidate_sha256"] = "0" * 64
        write_canonical(d / "evidence/planning/worklist.json", wl)
        _r2, gaps2 = verify_receipt(d, require_admitted=True)
        ok = any("plan semantics" in g for g in gaps) and any("worklist digest" in g for g in gaps2)
        return (PASS if ok else FAIL), "semantic file tamper: %s; foreign candidate in the work list: %s" % (gaps[:1], [g for g in gaps2 if "worklist" in g][:1])

    q.case("raw receipt tampering / wrong candidate", "recorded-evidence", tamper)

    # --- WP8 matrix rows the first delivery left uncovered (2026-09-26) ---

    def source_profile_generator_deltas():
        """A meaningful source, profile or generator change is an EXPLAINED
        plan delta (its class and first divergent producer), never a false
        equivalence."""
        out = []
        # decided build profile
        dec = decisions()
        dec["build_profiles"] = {"adr": "ADR-001", "active": ["jdbc"]}
        d1 = q.dest("delta-profile", dec=dec)
        c1 = PS.compare(sem(a), sem(d1))
        if c1["equal"] or c1["first_divergent_producer"] != "decisions":
            return FAIL, "a profile change must diverge at decisions: %s" % c1["first_divergent_producer"]
        out.append("profile -> %s (%s)" % (c1["first_divergent_producer"], ",".join(sorted({x["class"] for x in c1["differences"]}))))
        # source: one more handler asking a BindingResult
        d2 = q.tmp / "delta-source"
        shutil.copytree(a, d2)
        bundle = load_json(d2 / "evidence/planning/evidence-bundle.json")
        ctrl = next(t for t in bundle["structure"]["types"] if t["fqn"].endswith("RestController"))
        extra = copy.deepcopy(next(m for m in ctrl["methods"] if any(p.get("type", "").endswith("BindingResult") for p in m.get("params") or [])))
        extra["name"] = extra["name"] + "Again"
        extra["signature"] = extra["name"] + extra["signature"][extra["signature"].index("("):]
        ctrl["methods"].append(extra)
        ep = copy.deepcopy(next(e for e in bundle["entry_points"] if e.get("type") == ctrl["fqn"]
                                and e.get("member", "").split("(", 1)[0] == extra["name"][:-len("Again")]))
        ep["member"] = extra["signature"]
        ep["id"] = ep["id"].replace(ep["id"].split("#", 1)[1].split(":", 1)[0], extra["signature"])
        bundle["entry_points"].append(ep)
        write_canonical(d2 / "evidence/planning/evidence-bundle.json", bundle)
        c2 = PS.compare(sem(a), PS.from_root(d2))
        added = [x for x in c2["differences"] if "added" in x["class"]]
        if c2["equal"] or not added:
            return FAIL, "an added BindingResult handler must ADD planned work: %s" % [x["class"] for x in c2["differences"]]
        out.append("source -> %s (%s)" % (c2["first_divergent_producer"], ",".join(sorted({x["class"] for x in c2["differences"]}))))
        # generator pin: the destination plugin version
        d3 = q.tmp / "delta-generator"
        shutil.copytree(a, d3)
        pom = (d3 / "pom.xml").read_text(encoding="utf-8")
        gen = SR.for_root(a)
        gver = next((r["facts"].get("plugin_version") for r in gen["requirements"] if r["rule"] == "generator-configuration/v1"), "")
        if not gver or gver not in pom:
            return FAIL, "the specimen's generator version is not in its pom (%r)" % gver
        (d3 / "pom.xml").write_text(pom.replace(gver, "9.9.9", 1), encoding="utf-8")
        c3 = PS.compare(sem(a), PS.from_root(d3))
        if c3["equal"]:
            return FAIL, "a generator pin change must change the plan"
        out.append("generator -> %s (%s)" % (c3["first_divergent_producer"], ",".join(sorted({x["class"] for x in c3["differences"]}))))
        return PASS, "; ".join(out)

    q.case("different source / profile / generator pin", "recorded-evidence", source_profile_generator_deltas)

    def cycle_and_ambiguity():
        """A requirement dependency cycle is a TYPED refusal, the same every
        time (never an arbitrary file order); a requirement two clusters could
        own resolves to the same owner whatever the cluster order."""
        g = L.initial_plan_from_root(a)
        base = [r for r in g["requirements"] if r["status"] == "applicable" and r["rule"] in ("request-validation/v1", "handler-parameter-binding/v1")]
        r1, r2 = copy.deepcopy(base[0]), copy.deepcopy(base[0])
        r1["id"], r2["id"] = r1["id"] + "#c1", r1["id"] + "#c2"
        r1["subject"], r2["subject"] = r1["subject"] + "#c1", r2["subject"] + "#c2"
        r1["paths"], r2["paths"] = ["src/main/java/q/C1.java"], ["src/main/java/q/C2.java"]
        r1["dependencies"], r2["dependencies"] = [r2["id"]], [r1["id"]]
        wl = load_json(a / "evidence/planning/worklist.json")
        codes = []
        for _ in range(2):
            try:
                OG.derive_initial_graph(run_id="q", worklist=wl, entry_points=[], oracles=None, references=None,
                                        provenance={"snapshot_kind": "synthetic", "scope_note": "cycle", "construction": "qualify",
                                                    "observed_migration_event": False}, requirements=[r1, r2])
                codes.append("none")
            except OG.PlanError as exc:
                codes.append("%s: %s" % (exc.code, exc.detail))
        if codes[0] != codes[1] or not codes[0].startswith("GRAPH_CYCLE"):
            return FAIL, "a dependency cycle must be the same typed refusal every time: %s" % codes
        # ambiguous shared ownership: the requirement's file is in two clusters
        amb = copy.deepcopy(base[0])
        owners = set()
        for order in (1, -1):
            w = copy.deepcopy(wl)
            path = amb["paths"][0]
            holders = [c for c in w["clusters"] if path in (c.get("write_set") or [])]
            if not holders:
                return FAIL, "the specimen has no cluster holding %s" % path
            twin = copy.deepcopy(holders[0])
            twin["id"] = twin["id"] + ":twin"
            first = next(i for i in w["items"] if i["id"] in holders[0]["items"])
            item = dict(copy.deepcopy(first), id=first["id"] + ":twin")
            w["items"] = (w["items"] + [item])[::order]
            twin["items"] = [item["id"]]
            w["clusters"] = (w["clusters"] + [twin])[::order]
            g2 = OG.derive_initial_graph(run_id="q", worklist=w, entry_points=[], oracles=None, references=None,
                                         provenance={"snapshot_kind": "synthetic", "scope_note": "ambiguity", "construction": "qualify",
                                                     "observed_migration_event": False}, requirements=[amb])
            owners.add(g2["requirement_ownership"][amb["id"]])
        if len(owners) != 1:
            return FAIL, "shared ownership resolved to different owners by cluster order: %s" % owners
        return PASS, "cycle -> %s (twice); two candidate owners -> %s under both cluster orders" % (codes[0][:60], owners.pop())

    q.case("cyclic dependencies / ambiguous shared ownership", "recorded-evidence", cycle_and_ambiguity)

    def mixed_protocol():
        from planner import outcome_protocol as P
        d = q.tmp / "mixed"
        d.mkdir()
        (d / P.STORE_FILE).parent.mkdir(parents=True, exist_ok=True)
        (d / P.STORE_FILE).write_bytes(b"")
        serial = P.mixed_state(d)
        e = q.tmp / "mixed-outcome"
        e.mkdir()
        (e / "run-defaults.json").write_text(json.dumps({"schema": "rhoai3.run-defaults/v1", "budget": {},
                                                        "configuration": {"board_protocol": P.OUTCOME}}), encoding="utf-8")
        write_canonical(e / "verification/loop/issued.json", {"idempotency_key": "k4:c:1:0000", "task_id": "t_x"})
        outcome = P.mixed_state(e)
        if not serial or serial[0][0] != "PROTOCOL_MIXED" or not outcome or outcome[0][0] != "PROTOCOL_MIXED":
            return FAIL, "mixed state must refuse both ways: %s / %s" % (serial, outcome)
        return PASS, "serial run with an outcome store and outcome run with a K4 serial record both refuse PROTOCOL_MIXED"

    q.case("mixed protocol state", "recorded-evidence", mixed_protocol)

    def check_schedule():
        from planner import compatibility_objectives as CO
        dec = decisions()
        dec["loop"]["compatibility_objectives"] = "v1"
        s1 = q.dest("schedule-a", dec=dec, run_id="run-a")
        s2 = q.dest("schedule-b", dec=copy.deepcopy(dec), seed=11, run_id="run-b")
        ga, gb, ga2 = _graph_of(s1, "run-a")["graph"], _graph_of(s2, "run-b")["graph"], _graph_of(s1, "run-a")["graph"]
        if not ga.get("check_schedule") or _schedule_view(ga) != _schedule_view(gb) or _schedule_view(ga) != _schedule_view(ga2):
            return FAIL, "the specimen schedule differs between derivations, checkouts or run ids"
        src = load_json_gz(V29_SCHEDULE_FIXTURE)["plan"]
        runs = []
        for order in (1, 1, -1):
            d = copy.deepcopy(src)
            d["nodes"], d["requirements"] = d["nodes"][::order], d["requirements"][::order]
            CO.schedule_checks(d)
            runs.append(d)
        views = [_schedule_view(d) for d in runs]
        if views[0] != views[1] or views[0] != views[2]:
            return FAIL, "the v29 r1 inputs gave two schedules"
        for k in ("ownership", "requirement_ownership", "composition"):
            if runs[0].get(k) != src.get(k):
                return FAIL, "the schedule changed the v29 %s" % k
        found = runs[0]["check_schedule"]["findings"] + ga["check_schedule"]["findings"]
        nodes = {n["outcome_id"]: n for n in runs[0]["nodes"]}
        at = {k: sorted({p for r in n.get("check_plan") or [] if r["check"].startswith("behavior:repository-effects:")
                         for p in r["earliest"]["at"]})
              for k, n in nodes.items() if k.startswith("objective:selected-repository-implementation:")}
        q.evidence["check_schedule"] = {"specimen_counts": ga["check_schedule"]["counts"],
                                        "v29_counts": runs[0]["check_schedule"]["counts"],
                                        "v29_repository_effects_first_measured_at": at, "findings": found}
        if found:
            return FAIL, "unschedulable checks: %s" % json.dumps(found)[:300]
        return PASS, "specimen schedule identical over two checkouts/run ids; v29 r1 schedule identical twice and reordered " \
                     "(%d later checks, %d repository contracts first measured before M4); no findings" % (
                         sum(c["later"] for c in runs[0]["check_schedule"]["counts"].values()),
                         sum(1 for v in at.values() if v and all(p.startswith("behavior:") for p in v)))

    q.case("check schedule: same inputs, same owners, checks, dependencies and budgets", "recorded-evidence", check_schedule)


V29_SCHEDULE_FIXTURE = HERMES / "lib/planner/fixtures/v29-plan-r1-schedule.json.gz"


def load_json_gz(path: Path) -> dict:
    import gzip
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def _schedule_view(g: dict) -> dict:
    """The logical schedule of a revision, without its run binding: each
    outcome's check plan (kind, owner, prerequisites, earliest point, causal
    order), acceptance states, dependency kinds, causal scope, parents,
    ownership and budget limit/accounts; the plan-level schedule summary."""
    out = {n["outcome_id"]: {k: n.get(k) for k in ("check_plan", "acceptance_states", "dependency_kinds", "causal_scope",
                                                     "parents", "obligations", "requirements")}
           for n in g.get("nodes") or []}
    for n in g.get("nodes") or []:
        out[n["outcome_id"]]["budget"] = {k: v for k, v in (n.get("budget") or {}).items() if k != "key"}
    out["_schedule"] = g.get("check_schedule")
    out["_ownership"] = [g.get("ownership"), g.get("requirement_ownership")]
    return out


def _graph_of(d: Path, run_id: str, scope_note: str = "preserved specimen replay") -> dict:
    """The one initial graph builder on a root's recorded M1/M2 evidence, with
    the compatibility objectives the root's decisions pin (None when they pin
    none: the per-unit plan, byte for byte)."""
    from planner.outcome_checks import objective_inputs
    reqs = SR.for_root(d, oracles=L._oracles(d))
    wl = load_json(d / "evidence/planning/worklist.json")
    inv = load_json(d / "evidence/entry-point-inventory.json")
    g = OG.derive_initial_graph(run_id=run_id, worklist=wl, entry_points=inv["entry_points"], oracles=L._oracles(d),
                                references=None, provenance={"snapshot_kind": "admission", "scope_note": scope_note,
                                                              "construction": "qualify-repeatability"},
                                requirements=reqs["requirements"], objectives=objective_inputs(d, wl))
    return {"requirements": reqs, "graph": g}


def _membership(g: dict) -> dict:
    """objective -> its constituent clusters and requirements: the grouping a
    reviewer compares, independent of run binding."""
    comp = g.get("composition") or {}
    return {n["outcome_id"]: {"clusters": sorted(n.get("clusters") or []), "requirements": sorted(n.get("requirements") or []),
                              "parents": sorted(n.get("parents") or [])}
            for n in g["nodes"]} | ({"_budget": comp.get("budget")} if comp else {})


FRESH_CASE = "two fresh M1 -> M2 derivations of one frozen source"
BUILT_CASE = "built fresh roots: two M1 -> M2 derivations of one frozen source"
BUILT_PRODUCERS_CASE = "built fresh roots: M1 -> M2 producers run twice on the frozen source"
BUILT_MTA_CASE = "MTA CLI in the built fresh roots: two fresh analyses compared"
MTA_CASE = "MTA CLI on the frozen source: two independent clean copies"
PATCH_CASE = "typed-repair patches of two independent applications on the same frozen inputs"


def fresh_cases(q: Q, a: Path, b: Path, name: str = FRESH_CASE, level: str = "producer-replay (fresh roots)",
                key: str = "fresh_comparison") -> None:
    """Two INDEPENDENT fresh M1 -> M2 derivations of the same frozen source
    with the same tool and decision pins (producers re-run on each; the
    caller made them). Their requirements, logical graph -- objectives
    included when the decisions pin them -- and objective membership must be
    equal; only the run binding may differ. Any difference is reported by
    outcome, never normalised away."""
    def installed(root: Path, name: str) -> Path:
        # a disposable copy planned with THIS golden's decisions and catalogs (the policy under
        # qualification); the root's own recorded evidence is what differs between the two
        d = q.tmp / name
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(root, d, symlinks=True, ignore=shutil.ignore_patterns("target", ".git"))
        shutil.copy(HERMES.parent / "decisions.yaml", d / "decisions.yaml")
        shutil.copytree(HERMES / "planning", d / ".hermes/planning", dirs_exist_ok=True)
        return d

    def compare():
        from planner.canonical import digest
        ca, cb = installed(a, key + "-a"), installed(b, key + "-b")
        ga, gb = _graph_of(ca, "run-fresh-a", "fresh derivation"), _graph_of(cb, "run-fresh-b", "fresh derivation")
        ra, rb = digest(ga["requirements"]["requirements"]), digest(gb["requirements"]["requirements"])
        pa, pb = PS.graph_projection(ga["graph"]), PS.graph_projection(gb["graph"])
        ma, mb = _membership(ga["graph"]), _membership(gb["graph"])
        diff = sorted(k for k in set(ma) | set(mb) if ma.get(k) != mb.get(k))
        q.evidence[key] = {
            "a": str(a), "b": str(b), "decisions_and_catalogs": "this golden's", "requirements_digest": [ra, rb],
            "logical_graph_digest": [digest(pa), digest(pb)], "policy": (ga["graph"].get("policy") or {}).get("id") if isinstance(ga["graph"].get("policy"), dict) else (ga["graph"].get("policy") or "per-unit"), "objectives": sum(1 for k in ma if k.startswith("objective:") and "/part:" not in k),
            "membership_differences": diff[:40], "equal": ra == rb and pa == pb and not diff}
        if ra != rb or pa != pb or diff:
            return FAIL, "fresh derivations differ: requirements %s/%s; outcomes %s" % (ra[:12], rb[:12], diff[:6])
        return PASS, "%d requirements, %d outcomes (%s, %d objective(s)) identical across two fresh derivations" % (
            len(ga["requirements"]["requirements"]), len(ga["graph"]["nodes"]), ga["graph"].get("policy") or "per-unit",
            q.evidence[key]["objectives"])

    q.case(name, level, compare)


def specimen_cases(q: Q, specimen: Path) -> None:
    """Recorded-evidence replay on PRESERVED PetClinic M1 evidence (not
    synthetic): the frozen structural model, entry points, captured corpus
    and admission-time work list a real run produced. Two disposable copies
    (other paths, other run ids, every producer set in reverse order) must
    derive the same requirements and the same logical initial graph with the
    golden's decisions and catalogs; the V17 rows are recorded in the
    inventory. It re-runs no producer: it proves planning determinism for
    this recorded evidence only."""
    def load_copy(name: str, reverse: bool) -> Path:
        d = q.tmp / name
        shutil.copytree(specimen, d)
        shutil.copy(HERMES.parent / "decisions.yaml", d / "decisions.yaml")
        (d / ".hermes").mkdir(exist_ok=True)
        shutil.copytree(HERMES / "planning", d / ".hermes/planning", dirs_exist_ok=True)
        if reverse:
            b = load_json(d / "evidence/planning/evidence-bundle.json")
            b["structure"]["types"] = list(reversed(b["structure"]["types"]))
            for t in b["structure"]["types"]:
                t["methods"] = list(reversed(t.get("methods") or []))
            b["entry_points"] = list(reversed(b["entry_points"]))
            write_canonical(d / "evidence/planning/evidence-bundle.json", b)
            # a producer that emitted this order would have had the corpus derived against THIS
            # bundle: re-bind the derivation receipts as that derivation records them (the corpus
            # content is the same scenarios; corpus_binding_gaps refuses a receipt naming another bundle)
            from planner.canonical import digest as _digest
            for rel in ("verification/scenarios/_derive.json", "verification/scenarios-enabled/_derive.json"):
                p = d / rel
                if p.is_file():
                    r = load_json(p)
                    r["evidence_bundle_sha256"] = _digest(b)
                    write_canonical(p, r)
            for rel in ("verification/scenarios/corpus.json",):
                p = d / rel
                if p.is_file():
                    c = load_json(p)
                    c["scenarios"] = list(reversed(c.get("scenarios") or []))
                    write_canonical(p, c)
            # the work list's own order is an input to objective composition too
            w = load_json(d / "evidence/planning/worklist.json")
            w["clusters"] = list(reversed(w.get("clusters") or []))
            w["items"] = list(reversed(w.get("items") or []))
            write_canonical(d / "evidence/planning/worklist.json", w)
        return d

    graph_of = _graph_of

    def replay():
        a = load_copy("specimen-a", False)
        b = load_copy("specimen-b", True)
        ga, gb = graph_of(a, "run-specimen-a"), graph_of(b, "run-specimen-b")
        from planner.canonical import digest
        ra, rb = digest(ga["requirements"]["requirements"]), digest(gb["requirements"]["requirements"])
        pa, pb = PS.graph_projection(ga["graph"]), PS.graph_projection(gb["graph"])
        q.evidence["specimen_comparison"] = {
            "specimen": str(specimen), "a": str(a), "b": str(b), "requirements_digest": [ra, rb],
            "logical_graph_digest": [digest(pa), digest(pb)], "run_bound_revision_digest": [ga["graph"]["digest"], gb["graph"]["digest"]],
            "equal": ra == rb and pa == pb}
        reqs = ga["requirements"]["requirements"]
        q.evidence["specimen_inventory"] = {
            "note": "logical M3 inventory derived from PRESERVED PetClinic M1 evidence with the golden decisions and catalogs "
                    "(recorded-evidence replay; no producer re-run)",
            "requirements": [{k: r.get(k) for k in ("id", "rule", "status", "recipe", "acceptance", "dependencies", "paths", "unknowns")}
                             for r in reqs],
            "repository_behaviour": {r["facts"]["fragment"]: {"owed_implementation": r["facts"].get("owed_implementation"),
                                                               "members": [(m["signature"], m["kind"], m.get("source"),
                                                                            [t["id"] for t in m.get("translations") or []])
                                                                           for m in (r["facts"].get("behaviour") or {}).get("members") or []],
                                                               "not_behaviour_sources": [n["type"] for n in (r["facts"].get("behaviour") or {}).get("not_behaviour_sources") or []],
                                                               "verification": r["facts"].get("verification")}
                                     for r in reqs if r["rule"] == "repository-architecture/v1"},
            "graph": {"nodes": [{k: n.get(k) for k in ("outcome_id", "role", "class", "parents", "requirements", "planned_units", "clusters")}
                                for n in ga["graph"]["nodes"]],
                      "unresolved": ga["graph"]["unresolved"], "requirement_ownership": ga["graph"].get("requirement_ownership")},
            "unknowns": ga["requirements"]["unknowns"]}
        if ra != rb or pa != pb:
            return FAIL, "the preserved evidence derived different plans under reordering: requirements %s/%s" % (ra[:12], rb[:12])
        if ga["graph"]["digest"] == gb["graph"]["digest"]:
            return FAIL, "the run-bound revisions must differ in their run binding"
        flush = [m for r in reqs if r["rule"] == "repository-architecture/v1"
                 for m in (r["facts"].get("behaviour") or {}).get("members") or [] if m.get("translations")]
        return PASS, ("%d requirements, %d outcomes, %d unresolved, identical across reordered copies with distinct run bindings; "
                      "%d member(s) carry a persistence translation" % (len(reqs), len(ga["graph"]["nodes"]), len(ga["graph"]["unresolved"]), len(flush)))

    q.case("preserved PetClinic M1 evidence: two reordered copies", "recorded-evidence (preserved, not synthetic)", replay)


# ---------------------------------------------------------------------------
# producer replay
# ---------------------------------------------------------------------------

def producer_cases(q: Q) -> None:
    def run_test(rel: str):
        p = subprocess.run([sys.executable, str(HERMES / rel)], capture_output=True, text=True, timeout=900)
        last = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.startswith(("OK", "FAIL", "SKIP"))]
        if p.returncode != 0:
            return FAIL, (last or ["rc %d" % p.returncode])[-1][:300]
        if last and last[-1].startswith("SKIP"):
            return NOT_RUN, last[-1][:300]
        return PASS, (last or ["ok"])[-1][:300]

    if not shutil.which("javac") or not shutil.which("java"):
        for name in ("JVM locale", "stale generated/class output", "two symbols at one site", "bootstrap recipe twice / wrong transformation"):
            q.case(name, "producer-replay", lambda: (NOT_RUN, "no JDK on PATH"))
        return
    q.case("JVM locale; two symbols at one site", "producer-replay", lambda: run_test("lib/planner/plan_semantics.test.py"))
    q.case("stale generated/class output; the initial analysis never reuses a warm-up", "producer-replay",
           lambda: (lambda a, b: (a[0] if a[0] != PASS else b[0], "%s; %s" % (a[1][:140], b[1][:140])))(
               run_test("skills/migration/fix-until-green/scripts/prepare-initial-analysis.test.py"),
               run_test("skills/migration/fix-until-green/scripts/run-verify-initial-cache.test.py")))
    q.case("bootstrap recipe twice; wrong transformation that still parses", "producer-replay",
           lambda: run_test("skills/migration/bootstrap-destination/scripts/retire-annotation.test.py"))
    def run_fns(rel: str, names: list[str]):
        """Named cases of an existing suite, run through its own module (the
        real JDK producers they call run here)."""
        import importlib.util
        import io
        from contextlib import redirect_stderr, redirect_stdout
        path = HERMES / rel
        sys.path.insert(0, str(path.parent))
        spec = importlib.util.spec_from_file_location("q_" + path.stem.replace(".", "_").replace("-", "_"), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        done = []
        for n in names:
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                rc = getattr(mod, n)()
            if rc:
                return FAIL, "%s.%s: %s" % (path.name, n, err.getvalue().strip()[-300:])
            done.append(n)
        return PASS, "%s: %s" % (path.name, ", ".join(done))

    q.case("recursive / declared references: no false isolation", "producer-replay",
           lambda: run_fns("lib/planner/worklist.test.py", ["_real_generic_leaf_case", "_real_partial_leaf_case", "_leaf_evidence_case"]))
    def wrong_but_compiles():
        first = run_test("skills/migration/fix-until-green/scripts/fragment-behaviour.test.py")
        if first[0] != PASS:
            return first
        second = run_fns("lib/planner/worklist.test.py", ["_real_location_null_argument_case", "_static_generated_body_case"])
        return second[0], "fragment-behaviour.test.py OK; " + second[1]

    q.case("wrong semantic transformation that still compiles (stub delegates V17-3, null Location V17-5, generated body V17-4)",
           "producer-replay", wrong_but_compiles)
    q.case("issued briefs carry the applicable repair actions (V17-2 package unit, V17-4 generated body, V17-5 Location)",
           "producer-replay",
           lambda: run_fns("skills/migration/fix-until-green/scripts/brief.test.py",
                           ["_package_unit_production_brief_case", "_planned_generated_body_brief_case",
                            "_location_obligation_production_brief_case"]))
    if q.source is not None:
        q.case("M1 build + structure producers (capture-build-evidence, JdkModelExtract) on the frozen source: two independent clean copies", "producer-replay",
               lambda: m1_structure_replay(q, q.source))
    q.case(MTA_CASE, "producer-replay", lambda: mta_probe(q))


# ---------------------------------------------------------------------------
# fresh MTA: the M1 MTA producer itself, twice
# ---------------------------------------------------------------------------

MTA_SCRIPTS = HERMES / "skills/analysis/scan-with-mta/scripts"
MTA_ANALYZE = MTA_SCRIPTS / "mta-analyze-legacy.sh"
FREEZE = HERMES / "skills/analysis/freeze-migration-input/scripts/freeze-migration-input.py"
MTA_TIMEOUT_S = int(os.environ.get("QUALIFY_MTA_TIMEOUT_S") or 2700)
# mta-analyze-legacy.sh's own refusal when ensure_cli resolves nothing usable
ENSURE_CLI_REFUSAL = "mta-cli/kantra missing or unusable"


def mta_cli_candidates() -> list[str]:
    """The CLIs mta-analyze-legacy.sh's ensure_cli would probe, in its order:
    $MTA_CLI_HOME/mta-cli, $KANTRA_HOME/kantra, then kantra and mta-cli on
    PATH. Presence only; the script's own capability probe decides usability."""
    found = []
    for p in (Path(os.environ.get("MTA_CLI_HOME") or "/opt/mta-cli") / "mta-cli",
              Path(os.environ.get("KANTRA_HOME") or "/projects/.tools/kantra") / "kantra"):
        if p.is_file() and os.access(str(p), os.X_OK):
            found.append(str(p))
    for name in ("kantra", "mta-cli"):
        w = shutil.which(name)
        if w and w not in found:
            found.append(w)
    return found


def _producer_env(base: Path) -> dict:
    """The M1 producers' environment, contained in the disposable directory:
    the analyzer's working directory (Equinox writes into its cwd) and the
    AD-003 heap bound when the caller's environment does not set one."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.setdefault("MTA_RUN_CWD", str(base / "mta-run"))
    env.setdefault("JVM_MAX_MEM", "4G")
    return env


def mta_analyze_copy(q: Q, source: Path, label: str) -> dict:
    """One clean frozen copy analysed by the M1 MTA producer exactly as M1
    runs it: freeze-migration-input (analysis copy + manifest), then
    mta-analyze-legacy.sh with the golden's migration.yaml targets, custom
    rules, canary and pins."""
    base = q.tmp / ("mta-%s" % label)
    shutil.rmtree(base, ignore_errors=True)
    src, root = base / "frozen", base / "root"
    shutil.copytree(source, src, ignore=shutil.ignore_patterns("target", ".git"))
    (root / ".hermes").mkdir(parents=True)
    shutil.copy(HERMES / "pins.json", root / ".hermes/pins.json")
    shutil.copytree(HERMES / "planning", root / ".hermes/planning")
    shutil.copy(HERMES.parent / "migration.yaml", root / "migration.yaml")
    frozen_copy = root / ".derived/frozen-input"
    f = subprocess.run([sys.executable, str(FREEZE), "--source", str(src), "--root", str(root), "--copy-to", str(frozen_copy)],
                       capture_output=True, text=True, timeout=600)
    if f.returncode != 0:
        return {"label": label, "root": root, "input": frozen_copy, "rc": None, "error": "freeze: " + (f.stdout + f.stderr)[-300:]}
    try:
        p = subprocess.run(["bash", str(MTA_ANALYZE), "--root", str(root)], capture_output=True, text=True,
                           timeout=MTA_TIMEOUT_S, env=_producer_env(base))
        rc, out = p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        rc, out = None, "the analysis exceeded the bound of %d s (QUALIFY_MTA_TIMEOUT_S)" % MTA_TIMEOUT_S
    return {"label": label, "root": root, "input": frozen_copy, "rc": rc, "tail": out[-600:]}


def mta_semantic_findings(findings: Path, input_root: Path) -> list[list]:
    """The findings as the plan consumes them: (section, rule id, file
    relative to the analysed copy, line), every incident, sorted. Timestamps,
    absolute paths, messages and code snippets are not semantic."""
    doc = load_json(findings)
    prefixes = sorted({str(input_root).rstrip("/"), os.path.realpath(str(input_root)).rstrip("/")}, key=len, reverse=True)
    rows = []
    for section in ("violations", "insights"):
        for rid, v in sorted((doc.get(section) or {}).items()):
            incidents = (v.get("incidents") or []) if isinstance(v, dict) else []
            for inc in (i for i in incidents if isinstance(i, dict)):
                path = str(inc.get("uri") or "")
                path = path[len("file://"):] if path.startswith("file://") else path
                for pre in prefixes:
                    if path.startswith(pre + "/"):
                        path = path[len(pre) + 1:]
                        break
                try:
                    line = int(inc.get("lineNumber") or 0)
                except (TypeError, ValueError):
                    line = 0
                rows.append([section, str(rid), path, line])
    return sorted(rows)


def judge_mta_pair(q: Q, runs: list, key: str = "mta_fresh"):
    """Two fresh MTA analyses: each must have completed (an ok receipt and
    its findings), and their semantic findings must be equal. ensure_cli
    refusing every resolved CLI on both copies is NOT-RUN with its reason;
    any other failure is FAIL."""
    for r in runs:
        r["receipt_doc"] = load_json(r["root"] / "evidence/producers/mta.json") if (r["root"] / "evidence/producers/mta.json").is_file() else {}
        r["findings"] = r["root"] / "evidence/mta-findings.json"
        r["ok"] = r["receipt_doc"].get("status") == "ok" and r["findings"].is_file()
    if not any(r["ok"] for r in runs):
        tails = [r.get("error") or r.get("tail") or "" for r in runs]
        if all(ENSURE_CLI_REFUSAL in t for t in tails):
            return NOT_RUN, ("an MTA CLI is present but mta-analyze-legacy.sh's ensure_cli refused it as unusable (its "
                             "capability probe, e.g. kantra-assert-exec under HUMAN_HOME): %s" % tails[0][-200:])
    bad = [r for r in runs if not r["ok"]]
    if bad:
        return FAIL, "copy %s: the MTA analysis did not complete (rc %s): %s" % (
            bad[0]["label"], bad[0].get("rc"), (bad[0].get("error") or bad[0].get("tail") or "")[-300:])
    fa, fb = (mta_semantic_findings(r["findings"], r["input"]) for r in runs)
    tools_ = [r["receipt_doc"].get("tool") or {} for r in runs]
    only_a = [x for x in fa if x not in fb][:20]
    only_b = [x for x in fb if x not in fa][:20]
    q.evidence[key] = {
        "roots": [str(r["root"]) for r in runs],
        "cli": [t.get("binary_realpath") for t in tools_], "version_measured": [t.get("version_measured") for t in tools_],
        "artifact_sha256": [t.get("artifact_sha256") for t in tools_],
        "admissible": all(t.get("admissible") for t in tools_), "provenance": sorted({str(t.get("provenance")) for t in tools_}),
        "incidents": [len(fa), len(fb)], "rules": [len({x[1] for x in fa}), len({x[1] for x in fb})],
        "semantic_digest": [hashlib.sha256(json.dumps(x).encode()).hexdigest() for x in (fa, fb)],
        "only_a": only_a, "only_b": only_b, "equal": fa == fb,
    }
    if tools_[0].get("artifact_sha256") != tools_[1].get("artifact_sha256"):
        return FAIL, "the two analyses ran different binaries (%s / %s): not the same pinned producer" % (
            tools_[0].get("artifact_sha256"), tools_[1].get("artifact_sha256"))
    if not fa:
        return FAIL, "both analyses report no incident at all (not even the canary): the analysis is not evidenced"
    if fa != fb:
        return FAIL, "the fresh MTA findings differ: %d / %d incidents; only in a %s; only in b %s" % (
            len(fa), len(fb), json.dumps(only_a[:3]), json.dumps(only_b[:3]))
    adm = q.evidence[key]["admissible"]
    return PASS, "%d incidents over %d rules identical across two fresh analyses (%s, %s%s)" % (
        len(fa), q.evidence[key]["rules"][0], tools_[0].get("version_measured") or "version unmeasured",
        "admissible" if adm else "NON-ADMISSIBLE",
        "" if adm else ": " + ", ".join(q.evidence[key]["provenance"]))


def mta_probe(q: Q):
    """The M1 MTA producer on two clean copies of the frozen source (--source).
    NOT-RUN only when no CLI resolves, or no frozen source was given; a
    resolved CLI is executed through the producer, whatever its admissibility,
    and the claim boundary names a non-admissible one."""
    clis = mta_cli_candidates()
    if not clis:
        return NOT_RUN, ("no MTA CLI: none of $MTA_CLI_HOME/mta-cli (default /opt/mta-cli), $KANTRA_HOME/kantra (default "
                         "/projects/.tools/kantra), kantra or mta-cli on PATH; MTA findings stay recorded evidence")
    if q.source is None:
        return NOT_RUN, "an MTA CLI is present (%s) but no frozen source was given (--source DIR): nothing to analyse" % clis[0]
    return judge_mta_pair(q, [mta_analyze_copy(q, q.source, label) for label in ("a", "b")])


# ---------------------------------------------------------------------------
# --build-fresh: the driver builds the two fresh M1 -> M2 roots
# ---------------------------------------------------------------------------

REHEARSE = HERE / "rehearse-legacy.sh"
DERIVE_SCENARIOS = HERMES / "skills/gates/capture-source-oracles/scripts/derive-source-scenarios.py"
BUILD_TIMEOUT_S = int(os.environ.get("QUALIFY_BUILD_TIMEOUT_S") or 7200)
# (step, the artefact that proves it ran); a producers/ receipt also carries its status
M1M2_STEPS = (
    ("freeze-migration-input", "evidence/producers/freeze.json"),
    ("capture-build-evidence", "evidence/producers/build.json"),
    ("inventory-legacy-surface", "evidence/producers/jdk-model.json"),
    ("scan-with-mta", "evidence/producers/mta.json"),
    ("assemble-evidence-bundle", "evidence/planning/evidence-bundle.json"),
    ("bootstrap-destination", "evidence/producers/bootstrap.json"),
    ("run-verify (work list)", "evidence/planning/worklist.json"),
)
REQUIRED_FOR_COMPARISON = ("evidence/planning/evidence-bundle.json", "evidence/planning/worklist.json",
                           "evidence/entry-point-inventory.json")
NOT_EXECUTED_HERE = {
    step: "starts the frozen source's isolated runtime and its per-run database: not executed by this builder; "
          "the plan comparison holds captures absent on both roots"
    for step in ("capture-source-scenarios", "qualify-source-captures",
                 "capture-source-scenarios-enabled", "qualify-source-captures-enabled")}


def build_fresh_root(q: Q, source: Path, label: str, producer: list) -> dict:
    """One fresh root: a clean copy of the frozen source, the producer
    (rehearse-legacy.sh: the M1 -> M2 producers in M1 order) into an empty
    root, then the offline corpus derivations of both security modes. Each
    step is judged by its own artefact, never by the producer's exit."""
    base = q.tmp / ("built-%s" % label)
    shutil.rmtree(base, ignore_errors=True)
    src, root = base / "frozen", base / "root"
    shutil.copytree(source, src, ignore=shutil.ignore_patterns("target", ".git"))
    try:
        p = subprocess.run(producer + ["--legacy", str(src), "--root", str(root)], capture_output=True, text=True,
                           timeout=BUILD_TIMEOUT_S, env=_producer_env(base))
        rc, tail = p.returncode, (p.stdout + p.stderr)[-600:]
    except subprocess.TimeoutExpired:
        rc, tail = None, "the producer exceeded the bound of %d s (QUALIFY_BUILD_TIMEOUT_S)" % BUILD_TIMEOUT_S
    steps = {}
    for step, rel in M1M2_STEPS:
        f = root / rel
        if not f.is_file():
            steps[step] = "absent"
        elif "/producers/" in rel:
            try:
                steps[step] = str(load_json(f).get("status") or "unknown")
            except (OSError, ValueError):
                steps[step] = "unreadable"
        else:
            steps[step] = "ok"
    notes = {}
    for step, extra in (("derive-source-scenarios", []), ("derive-source-scenarios-enabled", ["--security-mode", "enabled"])):
        if steps["assemble-evidence-bundle"] != "ok":
            steps[step] = "absent"
            continue
        d = subprocess.run([sys.executable, str(DERIVE_SCENARIOS), "--root", str(root)] + extra,
                           capture_output=True, text=True, timeout=900, env=_producer_env(base))
        steps[step] = "ok" if d.returncode == 0 else "failed"
        if d.returncode != 0:
            notes[step] = (d.stdout + d.stderr).strip()[-300:]
    return {"label": label, "root": root, "input": root / ".derived/frozen-input", "rc": rc, "tail": tail, "steps": steps,
            "notes": notes}


def build_cases(q: Q, source: Path, producer: list | None = None) -> None:
    default = producer is None
    producer = producer or ["bash", str(REHEARSE)]
    runs = []

    def build():
        runs.extend(build_fresh_root(q, source, label, producer) for label in ("a", "b"))
        a, b = runs
        q.evidence["built_fresh_roots"] = {
            "source": str(source), "producer": producer, "producer_is_harness_default": default,
            "roots": [str(a["root"]), str(b["root"])], "producer_rc": [a["rc"], b["rc"]],
            "steps": {"a": a["steps"], "b": b["steps"]}, "step_notes": {"a": a["notes"], "b": b["notes"]},
            "not_executed": NOT_EXECUTED_HERE}
        if a["steps"] != b["steps"]:
            diff = {k: [a["steps"].get(k), b["steps"].get(k)] for k in a["steps"] if a["steps"].get(k) != b["steps"].get(k)}
            return FAIL, "the two fresh builds' steps differ: %s" % json.dumps(diff)[:400]
        missing = [rel for rel in REQUIRED_FOR_COMPARISON if not (a["root"] / rel).is_file()]
        if missing:
            return NOT_RUN, "the producers did not reach M2 on this host (missing %s; steps %s): %s" % (
                ", ".join(missing), json.dumps(a["steps"]), a["tail"][-240:])
        return PASS, "two roots built by %s: steps %s (identical); not executed here: %s" % (
            "rehearse-legacy.sh" if default else "a caller-supplied producer", json.dumps(a["steps"]), ", ".join(sorted(NOT_EXECUTED_HERE)))

    q.case(BUILT_PRODUCERS_CASE, "producer-run (built here)", build)
    if not runs or q.cases[-1]["status"] != PASS:
        return
    a, b = runs
    fresh_cases(q, a["root"], b["root"], name=BUILT_CASE, level="producer-run (built here)", key="built_fresh_comparison")

    def mta():
        sa, sb = a["steps"]["scan-with-mta"], b["steps"]["scan-with-mta"]
        if sa == "absent" and sb == "absent":
            return NOT_RUN, ("no MTA analysis in either root: the producer found no mta-cli or kantra on PATH "
                             "(rehearse-legacy.sh step 4); the plans compared carry no fresh MTA findings")
        return judge_mta_pair(q, [a, b], key="built_mta_fresh")

    q.case(BUILT_MTA_CASE, "producer-run (built here)", mta)


# ---------------------------------------------------------------------------
# --patches: typed-repair patches of two independent applications
# ---------------------------------------------------------------------------

TYPED_REPAIR_DIR = Path("verification/loop/typed-repair")
TYPED_REPAIR_SCHEMA = "rhoai3.typed-repair-record/v1"
DETERMINISTIC_KINDS = ("typed-repair", "decided-repairs")


def typed_repair_applications(root: Path) -> dict:
    """cluster|recipe|target -> its attempts in order, each with the outcome,
    changed files, recipe version, executor and the sha256 of the complete
    staged patch (out/patch.diff, the root's own path removed). Read from the
    per-attempt directories the executor writes (record.json beside out/)."""
    out: dict = {}
    base = Path(root) / TYPED_REPAIR_DIR
    prefixes = sorted({str(root).rstrip("/") + "/", os.path.realpath(str(root)).rstrip("/") + "/"}, key=len, reverse=True)
    for rec_path in sorted(base.glob("*/*/record.json")):
        try:
            rec = load_json(rec_path)
        except (OSError, ValueError):
            continue
        if rec.get("schema") != TYPED_REPAIR_SCHEMA:
            continue
        attempt = rec_path.parent
        patch = attempt / "out/patch.diff"
        text = patch.read_text(encoding="utf-8") if patch.is_file() else ""
        for pre in prefixes:
            text = text.replace(pre, "")
        tail = attempt.name.rsplit("-", 1)[-1]
        recipe = rec.get("recipe") or {}
        key = "%s|%s|%s" % (rec.get("cluster"), recipe.get("id"), json.dumps(rec.get("target"), sort_keys=True))
        out.setdefault(key, []).append((int(tail) if tail.isdigit() else 0, {
            "recipe": recipe.get("id"), "recipe_version": recipe.get("version"), "operation": recipe.get("operation"),
            "outcome": rec.get("outcome"), "changed_files": sorted(rec.get("changed_files") or []),
            "executor_sha256": (rec.get("executor") or {}).get("sha256"),
            "patch_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text.strip() else None}))
    return {k: [x for _o, x in sorted(v, key=lambda t: t[0])] for k, v in out.items()}


def _final_view(attempts: list) -> dict:
    """What two applications must agree on: the last attempt's outcome and
    the patch the last APPLIED attempt staged (with its changed files)."""
    last = attempts[-1]
    applied = [x for x in attempts if x["outcome"] == "applied"]
    return {"outcome": last["outcome"], "recipe_version": last["recipe_version"],
            "patch_sha256": applied[-1]["patch_sha256"] if applied else None,
            "changed_files": applied[-1]["changed_files"] if applied else []}


def compare_patches(a: Path, b: Path, catalog: dict | None = None) -> dict:
    a, b = Path(a), Path(b)
    if catalog is None:
        cat_path = a / ".hermes/planning/catalogs/compat-mapping.json"
        catalog = load_json(cat_path if cat_path.is_file() else HERMES / "planning/catalogs/compat-mapping.json")
    kinds = {k: ((v.get("implementation") or {}).get("kind") if isinstance(v, dict) else None)
             for k, v in (catalog.get("migration_recipes") or {}).items()}
    ra, rb = typed_repair_applications(a), typed_repair_applications(b)
    det, agent, diffs = [], [], []
    executors = sorted({str(x["executor_sha256"]) for r in (ra, rb) for v in r.values() for x in v})
    for key in sorted(set(ra) | set(rb)):
        recipe = key.split("|", 2)[1]
        if kinds.get(recipe) not in DETERMINISTIC_KINDS:
            agent.append(key)
            continue
        det.append(key)
        if key not in ra or key not in rb:
            diffs.append({"key": key, "only_in": "a" if key in ra else "b"})
            continue
        va, vb = _final_view(ra[key]), _final_view(rb[key])
        if va != vb:
            diffs.append({"key": key, "a": va, "b": vb})
    return {"a": str(a), "b": str(b), "deterministic": det, "not_compared_agent_or_unclassified": agent,
            "executors": executors, "differences": diffs, "equal": not diffs,
            "applied": sum(1 for k in det if k in ra and _final_view(ra[k])["patch_sha256"])}


def patch_cases(q: Q, a: Path, b: Path) -> None:
    def compare():
        c = compare_patches(a, b)
        q.evidence["patch_comparison"] = c
        if not c["deterministic"]:
            return NOT_RUN, "no typed-repair record of a deterministic recipe in either application (%d other record key(s))" % len(
                c["not_compared_agent_or_unclassified"])
        if len(c["executors"]) > 1:
            return NOT_RUN, "the two applications used different executors (%s): not the same frozen inputs" % ", ".join(
                x[:12] for x in c["executors"])
        if not c["equal"]:
            return FAIL, "deterministic recipe applications differ: %s" % json.dumps(c["differences"][:3])[:400]
        return PASS, "%d deterministic recipe application(s) identical (%d staged patch digest(s) equal, same outcomes); " \
                     "%d agent-authored or unclassified record key(s) not compared by patch" % (
                         len(c["deterministic"]), c["applied"], len(c["not_compared_agent_or_unclassified"]))

    q.case(PATCH_CASE, "recorded applications (caller-supplied roots)", compare)


def m1_structure_replay(q: Q, source: Path):
    """The pinned M1 structure producer (inventory-legacy-surface
    run-jdk-model-extract.sh: JdkModelExtract on the toolchain JDK, then
    normalize-structure.py) executed on two independent clean copies of the
    frozen source, each with its own offline Maven classpath and its own
    offline `mvn compile` (the build producer's generated sources and
    target/classes, which the extractor reads); then the source requirements
    derived from each. Equal structure and equal requirements, or
    FAIL. A missing JDK/Maven or an offline resolution failure is NOT-RUN."""
    from planner.canonical import digest
    from planner.decisions import load_decisions
    from planner.evidence import derive_entry_points, load_catalogs
    if not (shutil.which("javac") and shutil.which("mvn")):
        return NOT_RUN, "javac or mvn is not on PATH"
    script = HERMES / "skills/analysis/inventory-legacy-surface/scripts/run-jdk-model-extract.sh"
    build_script = HERMES / "skills/analysis/capture-build-evidence/scripts/capture-build-evidence.sh"
    outs = {}
    builds: dict[str, dict] = {}
    for label in ("a", "b"):
        base = q.tmp / ("m1-%s" % label)
        src, root = base / "frozen", base / "root"
        shutil.copytree(source, src, ignore=shutil.ignore_patterns("target", ".git"))
        (root / ".hermes").mkdir(parents=True)
        shutil.copy(HERMES / "pins.json", root / ".hermes/pins.json")
        shutil.copytree(HERMES / "planning", root / ".hermes/planning")
        write_canonical(root / "evidence/producers/freeze.json", {"schema": "rhoai3.producer-receipt/v1", "producer": "freeze",
                                                                  "status": "ok", "analysis_copy": str(src)})
        # the pinned M1 BUILD producer itself (capture-build-evidence.sh: the
        # warm-up, the effective pom, the offline compile, the classpath and
        # its receipt), then the structure producer on what it built
        bp = subprocess.run(["bash", str(build_script), "--root", str(root)], capture_output=True, text=True, timeout=1800)
        brec = root / "evidence/producers/build.json"
        if bp.returncode != 0 or not brec.is_file():
            return NOT_RUN, "the build producer did not complete on copy %s: %s" % (label, (bp.stdout + bp.stderr)[-200:])
        builds[label] = load_json(brec)
        p = subprocess.run(["bash", str(script), "--root", str(root)], capture_output=True, text=True, timeout=900)
        st = root / "evidence/structure/structure.json"
        if p.returncode != 0 or not st.is_file():
            return FAIL, "copy %s: the structure producer failed: %s" % (label, (p.stdout + p.stderr)[-300:])
        outs[label] = (root, load_json(st))
    def build_facts(r: dict) -> dict:
        # the build's own facts, not its timings or paths
        return {k: r.get(k) for k in ("status", "outcome", "classpath_available", "classpath_entries", "source_roots",
                                      "generated_source_roots", "toolchain", "managed_versions") if k in r}
    if build_facts(builds["a"]) != build_facts(builds["b"]):
        return FAIL, "the two clean builds recorded different facts: %s / %s" % (build_facts(builds["a"]), build_facts(builds["b"]))
    q.evidence.setdefault("m1_structure_replay", {})["build_facts"] = build_facts(builds["a"])
    ta = outs["a"][1].get("types") or []
    tb = outs["b"][1].get("types") or []
    if digest(ta) != digest(tb):
        diff = sorted({t["fqn"] for t in ta} ^ {t["fqn"] for t in tb})
        return FAIL, "the two clean copies produced different structure (%d vs %d types; %s)" % (len(ta), len(tb), diff[:3])
    catalogs = load_catalogs(HERMES.parent)
    dec = load_decisions(HERMES.parent)
    cat = load_json(HERMES / "planning/catalogs/compat-mapping.json")
    reqs = {}
    for label, (root, doc) in outs.items():
        eps = derive_entry_points({"types": doc["types"]}, catalogs)
        oracles, facts = (None, None)
        if q.specimen is not None:
            from planner.worklist import corpus_scenario_facts
            oracles, facts = corpus_scenario_facts(q.specimen)
        reqs[label] = SR.derive(types=doc["types"], entry_points=eps, catalog=cat, decisions=dec, oracles=oracles,
                                structure_complete=True, generator=None, scenario_facts=facts,
                                source_config=SR.source_configuration(root, frozen_dir=q.tmp / ("m1-%s" % label) / "frozen"))
    if digest(reqs["a"]) != digest(reqs["b"]):
        return FAIL, "equal structure derived different requirements"
    partial = sum(1 for t in ta if str(t.get("resolution") or "full") != "full")
    vs_preserved = ""
    if q.specimen is not None:
        # the same derivation over the PRESERVED run's M1 evidence: equal
        # requirements mean the re-run producer reproduces the recorded plan
        pb = load_json(q.specimen / "evidence/planning/evidence-bundle.json")
        from planner.worklist import corpus_scenario_facts
        oracles, facts = corpus_scenario_facts(q.specimen)
        pres = SR.derive(types=pb["structure"]["types"], entry_points=pb["entry_points"], catalog=cat, decisions=dec, oracles=oracles,
                         structure_complete=True, generator=None, scenario_facts=facts,
                         source_config=SR.source_configuration(q.specimen, frozen_dir=q.source))
        ids_f = {(r["id"], r["status"]) for r in reqs["a"]["requirements"]}
        ids_p = {(r["id"], r["status"]) for r in pres["requirements"]}
        vs_preserved = ("; vs the preserved run's M1 evidence: requirements %s (%d only fresh, %d only preserved)"
                        % ("IDENTICAL" if digest(pres) == digest(reqs["a"]) else "differ", len(ids_f - ids_p), len(ids_p - ids_f)))
        q.evidence.setdefault("m1_structure_replay", {})["vs_preserved"] = {
            "identical": digest(pres) == digest(reqs["a"]), "only_fresh": sorted("%s %s" % x for x in ids_f - ids_p)[:40],
            "only_preserved": sorted("%s %s" % x for x in ids_p - ids_f)[:40]}
    q.evidence.setdefault("m1_structure_replay", {}).update({
        "types": len(ta), "partial_types": partial, "structure_digest": digest(ta), "requirements_digest": digest(reqs["a"]),
        "requirements": sorted("%s %s" % (r["rule"], r["status"]) for r in reqs["a"]["requirements"])})
    rows = sum(1 for r in reqs["a"]["requirements"] if r["rule"] == "repository-architecture/v1")
    return PASS, ("capture-build-evidence + JdkModelExtract + normalize-structure on two clean copies: identical build facts; %d types (%d partial) "
                  "identical; %d requirements (%d repository) identical%s" % (len(ta), partial, len(reqs["a"]["requirements"]), rows,
                                                                            vs_preserved))


def claim_boundary(q: Q) -> dict:
    """What this run's repeatability claim covers, from the cases that ran --
    never wider (round 3): equal plans from RECORDED evidence are not equal
    results from a FRESH M1 analysis, and a producer not executed here is
    named as such. `claims` grades the three M-7 claims (repeatable
    planning, transformations, migration) MEASURED / PARTIAL / NOT-MEASURED /
    FAILED with what each is missing."""
    ran = {c["case"]: c["status"] for c in q.cases}
    fresh = [k for k, v in ran.items() if v == PASS and k.startswith(("M1 build + structure", "MTA CLI", "built fresh roots"))]
    not_run = [k for k, v in ran.items() if v == NOT_RUN]
    covers = (["planning determinism for FIXED evidence (recorded-evidence cases: synthetic specimens"
               + (", and the preserved PetClinic M1 evidence" if q.specimen is not None else "") + ")"]
              + ["fresh producer execution: %s" % k for k in fresh])
    if ran.get(FRESH_CASE) == PASS:
        covers.append("equal plans from two caller-supplied fresh roots (their freshness is the caller's claim)")
    if ran.get(PATCH_CASE) == PASS:
        covers.append("identical deterministic typed-repair patches from two caller-supplied applications")
    does_not = ["equal initial plans from a FRESH end-to-end M1 analysis beyond the producers listed as fresh",
                "live source behaviour, a successful migration, native outcome execution readiness"]
    for name, key in ((MTA_CASE, "mta_fresh"), (BUILT_MTA_CASE, "built_mta_fresh")):
        ev = q.evidence.get(key) or {}
        if ran.get(name) == PASS and not ev.get("admissible"):
            does_not.append("the pinned MTA CLI 8.2: %s ran a NON-ADMISSIBLE CLI (%s); its repeatability was measured, "
                            "its admissibility was not" % (name, ", ".join(ev.get("provenance") or [])))
    return {
        "covers": covers,
        "does_not_cover": does_not + ["not run here: %s" % k for k in not_run],
        "claims": _claims(q, ran),
        "initial_analysis_cache": "the initial M2 analysis always rebuilds (no warm-up reuse; run.json warmup.cache "
                                  "not-reused-initial-analysis); routine verification may reuse a matching warm-up",
    }


def _claims(q: Q, ran: dict) -> dict:
    def grade(failed: list, basis: list, missing: list) -> str:
        return "FAILED" if failed else "MEASURED" if basis and not missing else "PARTIAL" if basis else "NOT-MEASURED"

    planning_cases = (BUILT_PRODUCERS_CASE, BUILT_CASE, BUILT_MTA_CASE, FRESH_CASE, MTA_CASE)
    m1 = [k for k in ran if k.startswith("M1 build + structure")]
    failed = [k for k in planning_cases + tuple(m1) if ran.get(k) == FAIL]
    basis = [k for k in (BUILT_CASE, BUILT_MTA_CASE, FRESH_CASE, MTA_CASE) + tuple(m1) if ran.get(k) == PASS]
    built = q.evidence.get("built_fresh_roots") or {}
    missing = []
    if ran.get(BUILT_CASE) != PASS:
        missing.append("two fresh M1 -> M2 roots built and compared by this driver (--build-fresh): %s" % (
            ran.get(BUILT_CASE) or ran.get(BUILT_PRODUCERS_CASE) or "not attempted"))
    else:
        if not built.get("producer_is_harness_default"):
            missing.append("the fresh roots were built by a caller-supplied producer, not the harness's rehearse-legacy.sh")
        incomplete = {k: v for k, v in ((built.get("steps") or {}).get("a") or {}).items() if v != "ok" and k != "scan-with-mta"}
        if incomplete:
            missing.append("complete fresh roots: these M1 -> M2 steps did not succeed on either root: %s" % json.dumps(incomplete))
    mta = q.evidence.get("built_mta_fresh") or {}
    if ran.get(BUILT_MTA_CASE) != PASS:
        missing.append("fresh MTA findings in both built roots: %s" % (ran.get(BUILT_MTA_CASE) or "not attempted"))
    elif not mta.get("admissible"):
        missing.append("the ADMISSIBLE pinned MTA CLI 8.2 in the built roots (ran %s)" % ", ".join(mta.get("provenance") or []))
    planning = {"status": grade(failed, basis, missing), "basis": basis, "failed": failed, "missing": missing,
                "held_fixed": "source captures (the runtime capture steps are not executed by this driver)"}

    pt = ran.get(PATCH_CASE)
    transformations = {
        "status": "FAILED" if pt == FAIL else "PARTIAL" if pt == PASS else "NOT-MEASURED",
        "basis": [PATCH_CASE] if pt == PASS else [], "failed": [PATCH_CASE] if pt == FAIL else [],
        "missing": ([] if pt == PASS else ["identical deterministic patches from two independent applications (--patches A B): %s"
                                           % (pt or "not attempted")])
                   + ["agent-authored exceptions judged against the same independent behaviour contract in both runs "
                      "(M4 parity of each run): not compared by this driver",
                      "second-application no-op: the executor's own recipe tests, not run by this driver"],
    }
    migration = {"status": "NOT-MEASURED", "basis": [], "failed": [],
                 "missing": ["a clean M1 -> M5 full-release run, then one confirming run on the same supported inputs without "
                             "overlays, manual repairs or Operator rescue (needs the cluster and a live model)"]}
    return {"repeatable_planning": planning, "repeatable_transformations": transformations, "repeatable_migration": migration}


def tools() -> dict:
    def out(argv):
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            return (p.stdout + p.stderr).strip().splitlines()[0][:120]
        except (OSError, subprocess.SubprocessError, IndexError):
            return "absent"
    return {"python": platform.python_version(), "java": out(["java", "-version"]), "javac": out(["javac", "-version"]),
            "mvn": out(["mvn", "-v"]) if shutil.which("mvn") else "absent",
            "mta-cli": shutil.which("mta-cli") or "absent", "mta_cli_candidates": mta_cli_candidates()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    ap.add_argument("--keep", default="")
    ap.add_argument("--no-producers", action="store_true", help="recorded-evidence level only")
    ap.add_argument("--specimen", default="", help="a PRESERVED M1 evidence tree (evidence/, verification/) to replay")
    ap.add_argument("--source", default="", help="a FROZEN source tree to run the M1 structure producer on (two clean copies)")
    ap.add_argument("--fresh", nargs=2, default=None, metavar=("ROOT_A", "ROOT_B"),
                    help="two independently derived fresh M1 -> M2 roots of one frozen source to compare")
    ap.add_argument("--build-fresh", default="", metavar="SOURCE",
                    help="build two fresh M1 -> M2 roots of this FROZEN source with the harness producers, then compare them")
    ap.add_argument("--producer", default="", help="--build-fresh producer command (fixtures only; default rehearse-legacy.sh)")
    ap.add_argument("--patches", nargs=2, default=None, metavar=("ROOT_A", "ROOT_B"),
                    help="two independent applications on the same frozen inputs: compare their typed-repair patches")
    a = ap.parse_args(argv)
    tmp = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="qualify-repeatability-"))
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    q = Q(tmp, Path(a.specimen) if a.specimen else None, Path(a.source) if a.source else None)
    try:
        run_cases(q)
        if q.specimen is not None:
            specimen_cases(q, q.specimen)
        if a.fresh:
            fresh_cases(q, Path(a.fresh[0]).resolve(), Path(a.fresh[1]).resolve())
        if a.build_fresh:
            build_cases(q, Path(a.build_fresh).resolve(), shlex.split(a.producer) if a.producer else None)
        if a.patches:
            patch_cases(q, Path(a.patches[0]).resolve(), Path(a.patches[1]).resolve())
        if not a.no_producers:
            producer_cases(q)
    finally:
        if not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    report = {"schema": "rhoai3.repeatability-qualification/v1", "synthetic_evidence": True,
              "preserved_evidence": str(q.specimen) if q.specimen is not None else "",
              "claim_boundary": claim_boundary(q),
              "tools": tools(), "seconds": round(time.time() - t0, 1), "cases": q.cases, **q.evidence}
    text = json.dumps(report, indent=2, sort_keys=True)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    failed = [c for c in q.cases if c["status"] == FAIL]
    for c in q.cases:
        print("%-7s %-17s %s :: %s" % (c["status"], c["level"], c["case"], c["detail"][:160]))
    print("%s: repeatability qualification (%d pass, %d not-run, %d fail)" % (
        "FAIL" if failed else "OK", sum(c["status"] == PASS for c in q.cases), sum(c["status"] == NOT_RUN for c in q.cases), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
