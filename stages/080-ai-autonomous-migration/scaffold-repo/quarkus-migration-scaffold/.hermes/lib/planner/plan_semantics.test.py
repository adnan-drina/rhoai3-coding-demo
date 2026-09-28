#!/usr/bin/env python3
"""plan_semantics selftest: the reviewed repeatability failures, executable.

Each case is a reproduction first (what the exact digests and the old identity
do) and then the semantic answer (what plan semantics v1 does), on production
functions: the real JdkDiagnostics producer under two JVM locales, the real
work-list builder, and the one initial outcome-graph builder over a full
M1 -> M2 specimen chain (planner.specimens.prepare_loop).

1. elapsed time only: items and clusters equal, the exact work-list digest
   differs (audit), the semantic plan is equal.
2. JVM locale: the diagnostic code is the same, the localized text differs
   (kept as message_jvm_locale), the legacy message-derived id differs, the
   v1 id is equal.
3. two identical diagnostics at one line and two symbols at one line: legacy
   collapses the first pair into one id twice (the graph refuses); v1 keeps
   every obligation distinct.
4. shuffled equivalent evidence, different checkout paths and run ids: the
   semantic documents are equal, the run bindings (budget keys, run id) differ.
5. a genuine change (a decision, a new compiler error) is NOT equal, and the
   comparison names the first divergent producer and the class.
6. legacy runs are unchanged: no v1 field appears without the decision.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import outcome_graph as OG  # noqa: E402
from planner import outcome_lifecycle as L  # noqa: E402
from planner import plan_semantics as PS  # noqa: E402
from planner import specimens as S  # noqa: E402
from planner import worklist as W  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402

HERMES = Path(__file__).resolve().parents[2]
TOOL = HERMES / "skills/migration/fix-until-green/scripts/jdk-diagnostics/JdkDiagnostics.java"
EXPORTS = ["--add-exports", "jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED",
           "--add-exports", "jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED"]
BASE = "src/main/java/org/acme/clinic"
ERRS = [(BASE + "/owner/OwnerController.java", 12, "cannot find symbol\n  symbol:   class RestController\n  location: class OwnerController"),
        (BASE + "/pet/PetController.java", 9, "cannot find symbol\n  symbol:   class RestController\n  location: class PetController")]
SAME_LOCUS = """package a;
public class A {
  Foo f; Bar b;
  void m() { Foo x = new Foo(); int y = missing(1); }
}
"""


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def v1_decisions(**kw) -> dict:
    d = S.full_decisions(**kw)
    d["loop"] = {"plan_semantics": "v1"}
    return d


def dest(tmp: Path, name: str, *, seed: int | None = None, decisions: dict | None = None, errors=None, spec: str = "http",
         run_id: str = "") -> Path:
    d = tmp / name
    S.build_dest(d, S.specimen(spec), decisions=decisions if decisions is not None else v1_decisions(), seed=seed)
    S.prepare_loop(d, errors=ERRS if errors is None else errors, diag_producer=S.CURRENT_DIAG_PRODUCER)
    if run_id:
        (d / "run-budget.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
    return d


_CLASSES: list[Path] = []


def run_producer(src_root: Path, out: Path, *, locale: str, exports: bool) -> dict:
    if not _CLASSES:
        c = Path(tempfile.mkdtemp(prefix="ps-diag-"))
        subprocess.run(["javac", "-d", str(c), str(TOOL)], check=True, capture_output=True)
        _CLASSES.append(c)
    lang, _, country = locale.partition("_")
    argv = ["java"] + (EXPORTS if exports else []) + ["-Duser.language=%s" % lang] + (["-Duser.country=%s" % country] if country else [])
    argv += ["-cp", str(_CLASSES[0]), "JdkDiagnostics", "--source", str(src_root), "--out", str(out), "--release", "21"]
    subprocess.run(argv, check=True, capture_output=True, timeout=120)
    return load_json(out)


def elapsed_time_case(tmp: Path) -> int:
    d = dest(tmp, "elapsed")
    w1 = load_json(d / "evidence/planning/worklist.json")
    doc1 = PS.from_root(d)
    run = load_json(d / "verification/build/run.json")
    run["total_ms"] = int(run.get("total_ms") or 0) + 12345
    run.setdefault("stages_ms", {})["diagnostics"] = 999
    write_canonical(d / "verification/build/run.json", run)
    w2 = W.build_worklist(d, write=True)
    if w1["items"] != w2["items"] or w1["clusters"] != w2["clusters"]:
        return _fail("an elapsed time changed the obligations or the clusters")
    if digest(w1) == digest(w2):
        return _fail("the exact work-list digest is expected to move with run.json (it seals the verification record): "
                     "the audit/semantic distinction has nothing to distinguish")
    doc2 = PS.from_root(d)
    c = PS.compare(doc1, doc2)
    if not c["equal"]:
        return _fail("an elapsed time changed the semantic plan: %s" % json.dumps(c["differences"])[:400])
    if not any(a["where"] == "audit.worklist_digest" for a in c["audit_differences"]):
        return _fail("the moved exact digest must be reported as an audit-only difference")
    return 0


def locale_case(tmp: Path) -> int:
    src = tmp / "locale-src"
    (src / "src/main/java/a").mkdir(parents=True)
    (src / "src/main/java/a/A.java").write_text(SAME_LOCUS, encoding="utf-8")
    for exports in (True, False):
        en = run_producer(src, tmp / ("en-%s.json" % exports), locale="en", exports=exports)
        ja = run_producer(src, tmp / ("ja-%s.json" % exports), locale="ja_JP", exports=exports)
        if [x["code"] for x in en["diagnostics"]] != [x["code"] for x in ja["diagnostics"]]:
            return _fail("the diagnostic codes differ between locales")
        if not any("message_jvm_locale" in x for x in ja["diagnostics"]):
            return _fail("the Japanese JVM rendering must be kept beside the pinned text for investigation")
        if en.get("rendering_locale") != "root" or ja.get("rendering_locale") != "root":
            return _fail("the producer must record its pinned rendering locale")
        if bool(en.get("args_available")) != exports:
            return _fail("args_available must say whether the compiler's structured arguments were read (exports=%s)" % exports)
        # the reproduction: the text a locale-following producer emitted, hashed the legacy way
        legacy_ja = dict(ja, diagnostics=[dict(x, message=x.get("message_jvm_locale", x["message"])) for x in ja["diagnostics"]])
        old_en = [i["id"] for i in W.compile_items(en)]
        old_ja = [i["id"] for i in W.compile_items(legacy_ja)]
        if old_en == old_ja:
            return _fail("reproduction lost: localized text no longer changes the legacy id")
        new_en = [i["id"] for i in W.compile_items(en, identity=W.IDENTITY_V1)]
        new_ja = [i["id"] for i in W.compile_items(ja, identity=W.IDENTITY_V1)]
        if new_en != new_ja:
            return _fail("v1 identity depends on the JVM locale (exports=%s)" % exports)
        conf = {i["identity_confidence"] for i in W.compile_items(en, identity=W.IDENTITY_V1)}
        if conf != ({"structured"} if exports else {"pinned-text"}):
            return _fail("identity confidence %s for exports=%s" % (conf, exports))
        # an older producer (no pinned locale) keeps its findings with a named lower confidence
        old_doc = {"diagnostics": [{k: v for k, v in x.items() if k not in ("args",)} for x in legacy_ja["diagnostics"]]}
        low = W.compile_items(old_doc, identity=W.IDENTITY_V1)
        if len(low) != len(ja["diagnostics"]) or {i["identity_confidence"] for i in low} != {"message-text"}:
            return _fail("an unpinned producer's findings must be kept with message-text confidence, never dropped")
    return 0


def same_locus_case(tmp: Path) -> int:
    src = tmp / "locus-src"
    (src / "src/main/java/a").mkdir(parents=True)
    (src / "src/main/java/a/A.java").write_text(SAME_LOCUS, encoding="utf-8")
    doc = run_producer(src, tmp / "locus.json", locale="en", exports=True)
    errors = [x for x in doc["diagnostics"] if x["kind"] == "ERROR"]
    legacy = [i["id"] for i in W.compile_items(doc)]
    if len(set(legacy)) == len(legacy):
        return _fail("reproduction lost: the two `new Foo`/`Foo x` diagnostics at one line no longer collide under legacy identity")
    v1 = W.compile_items(doc, identity=W.IDENTITY_V1)
    if len({i["id"] for i in v1}) != len(errors):
        return _fail("v1 collapsed distinct obligations: %d ids for %d diagnostics" % (len({i["id"] for i in v1}), len(errors)))
    # two different symbols at ONE line stay two, and differ from each other
    line3 = [i for i in v1 if i["line"] == 3]
    if len(line3) != 2 or line3[0]["id"] == line3[1]["id"]:
        return _fail("Foo and Bar at one line must be two obligations")
    # the work list the graph is built from: legacy duplicates refuse, v1 is conserved
    for items, want in ((W.compile_items(doc), "refuse"), (v1, "ok")):
        wl = {"items": items, "clusters": W.cluster_items(items, {}, set()), "unlocatable": [], "not_counted": [],
              "measure": {"known": True, "tuple": [0, len(items), 0]}}
        try:
            g = OG.derive_initial_graph(run_id="r", worklist=wl, entry_points=[], oracles=None, references=None,
                                        provenance={"snapshot_kind": "synthetic", "scope_note": "same-locus",
                                                    "construction": "plan_semantics.test", "observed_migration_event": False})
            got = "ok"
            owned = set(g["ownership"])
            if owned != {i["id"] for i in items}:
                return _fail("an obligation lost its owner")
        except OG.PlanError:
            got = "refuse"
        if got != want:
            return _fail("same-locus graph: expected %s, got %s" % (want, got))
    return 0


def run_identity_case(tmp: Path) -> tuple[int, dict]:
    a = dest(tmp, "checkout-a", run_id="run-a")
    b = dest(tmp, "checkout-b", seed=7, run_id="run-b")
    da, db = PS.from_root(a), PS.from_root(b)
    c = PS.compare(da, db)
    if not c["equal"]:
        return _fail("equivalent shuffled inputs in two checkouts gave different semantic plans: %s"
                     % json.dumps(c["differences"])[:600]), {}
    if not (da["plan"]["graph"] and da["plan"]["graph"]["nodes"]) or da["inputs"]["diagnostics"]["complete"] is not True:
        return _fail("the equality must be of a derived graph over complete diagnostics, not of two absences"), {}
    pa, pb = L.initial_plan_from_root(a), L.initial_plan_from_root(b)
    if pa["digest"] == pb["digest"]:
        return _fail("the run-bound revisions must differ (run id, budget keys)"), {}
    keys_a = {(n.get("budget") or {}).get("key") for n in pa["nodes"] if n.get("budget")}
    if not keys_a or not all("run-a" in k for k in keys_a):
        return _fail("run a's budget keys must be bound to run a"), {}
    if PS.graph_projection(pa) != PS.graph_projection(pb):
        return _fail("the logical graph differs between the two runs"), {}
    evidence = {"a": c["a"], "b": c["b"], "plan_digest_a": pa["digest"], "plan_digest_b": pb["digest"],
                "audit_differences": [x["where"] for x in c["audit_differences"]]}
    return 0, evidence


def semantic_change_case(tmp: Path) -> int:
    base = dest(tmp, "change-base")
    doc0 = PS.from_root(base)
    more = dest(tmp, "change-error", errors=ERRS + [(BASE + "/vet/VetController.java", 9, "cannot find symbol\n  symbol:   class GetMapping\n  location: class VetController")])
    c = PS.compare(doc0, PS.from_root(more))
    if c["equal"] or c["first_divergent_producer"] != "diagnostics":
        return _fail("a new compiler error must be a difference first seen at the diagnostics producer: %s" % c["first_divergent_producer"])
    if not any(x["class"] == "obligation-added" for x in c["differences"]):
        return _fail("the added compile obligation must be classified obligation-added")
    dec = dest(tmp, "change-decision", decisions=v1_decisions(max_attempts=5))
    c = PS.compare(doc0, PS.from_root(dec))
    if c["equal"] or c["first_divergent_producer"] != "decisions":
        return _fail("a different accepted decision must be an explained input difference at decisions: %s" % c["first_divergent_producer"])
    if not any(x["class"] == "budget" for x in c["differences"]):
        return _fail("the decided attempt threshold must show up as a budget difference in the graph")
    return 0


def legacy_case(tmp: Path) -> int:
    d = dest(tmp, "legacy", decisions=S.full_decisions())
    wl = load_json(d / "evidence/planning/worklist.json")
    if "plan_semantics" in wl or any("identity_confidence" in i for i in wl["items"]):
        return _fail("a run without decisions.loop.plan_semantics must form exactly today's work list")
    doc = {"diagnostics": [{"kind": "ERROR", "path": "src/main/java/a/A.java", "line": 2, "code": "x", "message": "e"}]}
    from planner.canonical import canonical_bytes, sha256_bytes
    want = "err:" + sha256_bytes(canonical_bytes({"path": "src/main/java/a/A.java", "line": 2, "code": "x", "message": "e"}))[:16]
    if W.compile_items(doc)[0]["id"] != want:
        return _fail("the legacy compile id changed")
    return 0


def plan_view_case(tmp: Path) -> int:
    """Round 3: the view claims only what it knows. From the frozen document
    alone it is the frozen initial plan -- no additions, no unfinished list;
    given the store's recorded revisions, a repair outcome a later revision
    added is reported with its revision and lineage."""
    del tmp
    n1 = {"outcome_id": "source:c:1", "role": "repair", "title": "M3 A", "parents": [], "class": "source"}
    n2 = {"outcome_id": "source:c:2", "role": "repair", "title": "M3 B", "parents": [], "class": "source",
          "lineage": {"class": "previously-unknown-behavior", "from": "assess:m4:g1"}}
    doc = {"plan": {"graph": {"nodes": [n1], "unresolved": [], "counts": {}}, "requirements": []}}
    frozen = PS.plan_view(doc, protocol="outcome-board/v1")
    if frozen.get("scope") != "frozen-initial-plan" or "additions" in frozen or "unfinished" in frozen:
        return _fail("the frozen view claims no additions or progress: %s" % sorted(frozen))
    live = PS.plan_view(doc, protocol="outcome-board/v1", revisions=[{"rev": 2, "doc": {"nodes": [n1, n2]}}, {"rev": 1, "doc": {"nodes": [n1]}}])
    if [(a["outcome_id"], a["added_in_revision"], a["revision_class"]) for a in live.get("additions") or []] != [("source:c:2", 2, "previously-unknown-behavior")]:
        return _fail("the recorded revisions give the real additions: %s" % live.get("additions"))
    if PS.plan_view(doc, protocol="outcome-board/v1", revisions=[{"rev": 1, "doc": {"nodes": [n1]}}]).get("additions") != []:
        return _fail("one revision has no additions")
    return 0


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="plan-semantics-"))
    try:
        for case in (elapsed_time_case, locale_case, same_locus_case, semantic_change_case, legacy_case, plan_view_case):
            if case(tmp):
                return 1
        rc, evidence = run_identity_case(tmp)
        if rc:
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK: plan semantics (elapsed time moves only the exact digest; the locale moves only message_jvm_locale; "
          "two diagnostics at one site stay two; shuffled equivalent evidence in two checkouts under two run ids "
          "gives one semantic plan %s with distinct run bindings; a decision or a new error is a named difference; "
          "legacy lists are unchanged)" % evidence["a"]["plan_fingerprint"][:16])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
