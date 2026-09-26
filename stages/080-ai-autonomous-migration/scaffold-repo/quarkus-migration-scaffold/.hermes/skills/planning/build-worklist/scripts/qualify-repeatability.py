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

Usage: qualify-repeatability.py [--out FILE] [--keep DIR]
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
    def __init__(self, tmp: Path):
        self.tmp = tmp
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
    q.case("stale generated/class output; clean vs warm replay", "producer-replay",
           lambda: run_test("skills/migration/fix-until-green/scripts/prepare-initial-analysis.test.py"))
    q.case("bootstrap recipe twice; wrong transformation that still parses", "producer-replay",
           lambda: run_test("skills/migration/bootstrap-destination/scripts/retire-annotation.test.py"))
    q.case("MTA / structure / build producers on the preserved pinned PetClinic specimen", "producer-replay",
           lambda: (NOT_RUN, "no preserved, pinned PetClinic source+M1 evidence specimen exists in this worktree; the MTA, "
                             "jdk-model and build producers were not executed on independent clean copies"))


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
    a = ap.parse_args(argv)
    tmp = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="qualify-repeatability-"))
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    q = Q(tmp)
    try:
        run_cases(q)
        if not a.no_producers:
            producer_cases(q)
    finally:
        if not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    report = {"schema": "rhoai3.repeatability-qualification/v1", "synthetic_evidence": True,
              "claim_boundary": "planning determinism for fixed evidence and the producers listed; not live source behaviour, "
                                "not a successful migration, not native outcome execution readiness",
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
