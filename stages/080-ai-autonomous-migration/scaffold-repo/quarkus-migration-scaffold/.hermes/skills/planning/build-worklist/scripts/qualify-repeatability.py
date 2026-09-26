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

Usage: qualify-repeatability.py [--out FILE] [--keep DIR] [--specimen DIR] [--source DIR] [--no-producers]
Exit 0 when no case FAILED (NOT-RUN cases are listed, with their reason).
"""
from __future__ import annotations

import argparse
import copy
import json
import platform
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
            for rel in ("verification/scenarios/corpus.json",):
                p = d / rel
                if p.is_file():
                    c = load_json(p)
                    c["scenarios"] = list(reversed(c.get("scenarios") or []))
                    write_canonical(p, c)
        return d

    def graph_of(d: Path, run_id: str) -> dict:
        reqs = SR.for_root(d, oracles=L._oracles(d))
        wl = load_json(d / "evidence/planning/worklist.json")
        inv = load_json(d / "evidence/entry-point-inventory.json")
        g = OG.derive_initial_graph(run_id=run_id, worklist=wl, entry_points=inv["entry_points"], oracles=L._oracles(d),
                                    references=None, provenance={"snapshot_kind": "admission", "scope_note": "preserved specimen replay",
                                                                  "construction": "qualify-repeatability"},
                                    requirements=reqs["requirements"])
        return {"requirements": reqs, "graph": g}

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
    q.case("MTA CLI 8.2 (pinned) on the frozen source: two independent clean copies", "producer-replay", mta_probe)


def mta_probe():
    """The pinned MTA CLI is admissible only as mta-cli 8.2.x (pins.mta_cli).
    This driver does not run any other analyzer as a stand-in: a host
    mta-cli of another version, or none, is NOT-RUN with the version it
    reports."""
    cli = shutil.which("mta-cli")
    if not cli:
        return NOT_RUN, "no mta-cli on PATH: the pinned MTA CLI 8.2 producer was not executed; MTA findings stay recorded evidence"
    try:
        v = subprocess.run([cli, "version"], capture_output=True, text=True, timeout=60)
        line = next((ln for ln in (v.stdout + v.stderr).splitlines() if ln.lower().startswith("version")), "unknown")
    except (OSError, subprocess.SubprocessError) as exc:
        line = "unreadable (%s)" % exc
    ver = line.split(":", 1)[-1].strip()
    if not ver.startswith("8.2"):
        return NOT_RUN, ("the host mta-cli (%s) reports version %s, not the pinned 8.2.x: not admissible, not run as a "
                         "stand-in; MTA findings stay recorded evidence" % (cli, ver))
    return NOT_RUN, ("mta-cli %s is present; this driver does not yet execute an MTA analysis replay (bounded: recorded "
                     "evidence only)" % ver)


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
    named as such."""
    ran = {c["case"]: c["status"] for c in q.cases}
    fresh = [k for k, v in ran.items() if v == PASS and k.startswith(("M1 build + structure", "MTA CLI"))]
    not_run = [k for k, v in ran.items() if v == NOT_RUN]
    return {
        "covers": ["planning determinism for FIXED evidence (recorded-evidence cases: synthetic specimens"
                   + (", and the preserved PetClinic M1 evidence" if q.specimen is not None else "") + ")"]
                  + ["fresh producer execution: %s" % k for k in fresh],
        "does_not_cover": ["equal initial plans from a FRESH end-to-end M1 analysis beyond the producers listed as fresh",
                           "live source behaviour, a successful migration, native outcome execution readiness"]
                          + ["not run here: %s" % k for k in not_run],
        "initial_analysis_cache": "the initial M2 analysis always rebuilds (no warm-up reuse; run.json warmup.cache "
                                  "not-reused-initial-analysis); routine verification may reuse a matching warm-up",
    }


def tools() -> dict:
    def out(argv):
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            return (p.stdout + p.stderr).strip().splitlines()[0][:120]
        except (OSError, subprocess.SubprocessError, IndexError):
            return "absent"
    return {"python": platform.python_version(), "java": out(["java", "-version"]), "javac": out(["javac", "-version"]),
            "mvn": out(["mvn", "-v"]) if shutil.which("mvn") else "absent",
            "mta-cli": shutil.which("mta-cli") or "absent"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    ap.add_argument("--keep", default="")
    ap.add_argument("--no-producers", action="store_true", help="recorded-evidence level only")
    ap.add_argument("--specimen", default="", help="a PRESERVED M1 evidence tree (evidence/, verification/) to replay")
    ap.add_argument("--source", default="", help="a FROZEN source tree to run the M1 structure producer on (two clean copies)")
    a = ap.parse_args(argv)
    tmp = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="qualify-repeatability-"))
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    q = Q(tmp, Path(a.specimen) if a.specimen else None, Path(a.source) if a.source else None)
    try:
        run_cases(q)
        if q.specimen is not None:
            specimen_cases(q, q.specimen)
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
