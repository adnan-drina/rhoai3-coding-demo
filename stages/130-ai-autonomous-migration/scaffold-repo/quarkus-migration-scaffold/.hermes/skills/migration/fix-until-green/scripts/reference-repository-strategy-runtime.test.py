#!/usr/bin/env python3
"""M-3 reference qualification, repository strategy: the SELECTED source
repository strategy (Spring Data under the decided build profile
spring-data-jpa, served on the destination through the generated
SpringDataOwnerRepository and its OwnerRepositoryImpl fragment delegate) on
the REAL candidate tree, PostgreSQL 16, packaged and spoken to over HTTP.

Only OwnerRepositoryImpl.java changes between variants
(fixtures/reference-qualification/repository-variants/); every other file is
the candidate tree (candidate/candidate.json). Each variant is packaged with
the pinned platform, booted on a freshly seeded database (the tree's own
initDB.sql + baseline-data.sql), and the corpus's `repository` steps run:
reads, create/update/delete each read back by a later independent request AND
on a NEW database connection (committed state), and the owner delete with its
dependents (owner -> pets -> visits). Expected values are the frozen source's
captures only (the corpus's reference_oracle). Scope: repository effects --
status, body, Location, errors header and committed state; Content-Type is
measured by reference-owner-path-runtime and is not this test's subject.

Controls (asserted; a control that does not hold is exit 1):
  reference-port        written from the selected source: the @Query texts of
                        SpringDataOwnerRepository verbatim over property paths,
                        SimpleJpaRepository CRUD semantics, a single-entity
                        query answering null when absent; never the inactive
                        JpaOwnerRepositoryImpl. Every repository step MATCHES.
  routed-back           delegates to the Spring Data repository that extends
                        its own fragment (INTERVENTIONS I-6): REJECTED, and the
                        destination log shows java.lang.StackOverflowError
  throwing-placeholder  REJECTED; the log shows UnsupportedOperationException
  noop-writes           reads MATCH; every committed-state write check REJECTED
  duplicate-beans       the reference port without @Typed: augmentation refuses
                        it (AmbiguousResolutionException); nothing boots
Measured, not asserted:
  as-is                 the candidate's own OwnerRepositoryImpl (v28's file)

A missing input prints SKIP with the reason and exits 0; the runner never
counts a SKIP as a pass. Options: --bundle, --results <json>, --keep <dir>,
--variants a,b,...
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reference_qualification as rq  # noqa: E402
import test_runtime_fixture as rt  # noqa: E402

TEST_ID = "reference-repository-strategy-runtime"
REL = "src/main/java/org/springframework/samples/petclinic/repository/OwnerRepositoryImpl.java"
VARIANTS = ["as-is", "reference-port", "routed-back", "throwing-placeholder", "noop-writes", "duplicate-beans"]
SCOPE_IGNORED = ["content-type"]
WRITE_SQL = ["owner-create-omitted-pets-sql", "owner-update-sql", "owner-update-seeded-sql", "owner-delete-created-sql",
             "owner-delete-dependents-sql"]
SEEDED_WRITE_SQL = ["owner-update-seeded-sql", "owner-delete-dependents-sql"]


def measure(tree: Path, variant: str, work: Path, corpus: dict, oracles: dict, base_ident: dict) -> dict:
    root = work / variant
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(tree, root, ignore=shutil.ignore_patterns("target"))
    replaced = {}
    if variant != "as-is":
        src = rq.QUAL / "repository-variants" / ("%s.java" % variant)
        shutil.copyfile(src, root / REL)
        replaced[REL] = src
    ident = rq.tree_identity(root, base_ident, replaced)
    started = time.time()
    ok, out = rq.package_tree(root)
    res = {"variant": variant, "artifact": ident, "packaged": ok}
    if not ok:
        res["package_error"] = next((ln.strip() for ln in out.splitlines() if "[error]" in ln), out[-400:])[:700]
        res["ambiguous"] = "AmbiguousResolutionException" in out
        res["seconds"] = round(time.time() - started, 1)
        return res
    res["artifact"] = dict(ident, **rq.artifact_identity(root))
    spec = __import__("json").loads(rq.CANDIDATE.read_text(encoding="utf-8"))
    with rq.seeded_postgres([root / s for s in spec["database"]["destination_seed"]]) as pg:
        log = work / ("%s.log" % variant)
        with rq.boot_candidate(root, pg, "disabled", log) as base:
            dest = rq.run_corpus(base, corpus, "disabled", "postgresql", pg, only_tags=["repository"])
    text = log.read_text(errors="replace")
    res["log"] = {"stackoverflow": text.count("java.lang.StackOverflowError"),
                  "unsupported_operation": text.count("java.lang.UnsupportedOperationException")}
    res["steps"] = rq.compare_all(corpus, oracles, dest, "disabled", "postgresql", only_tags=["repository"],
                                  ignore_headers=SCOPE_IGNORED)
    res["seconds"] = round(time.time() - started, 1)
    return res


def verdict(res: dict) -> str:
    if not res["packaged"]:
        return "REJECTED_AT_AUGMENTATION"
    return "ACCEPTED" if all(s["outcome"] == "MATCH" for s in res["steps"].values()) else "REJECTED"


def controls(results: dict) -> list:
    """(variant, holds, why) for every control that was measured."""
    out = []
    r = results.get("reference-port")
    if r:
        out.append(("reference-port", verdict(r) == "ACCEPTED",
                    "every repository step matches the source oracle"))
    r = results.get("routed-back")
    if r:
        out.append(("routed-back", verdict(r) != "ACCEPTED" and r.get("log", {}).get("stackoverflow", 0) > 0,
                    "rejected, with java.lang.StackOverflowError in the destination log"))
    r = results.get("throwing-placeholder")
    if r:
        out.append(("throwing-placeholder", verdict(r) != "ACCEPTED" and r.get("log", {}).get("unsupported_operation", 0) > 0,
                    "rejected, with UnsupportedOperationException in the destination log"))
    r = results.get("noop-writes")
    if r and r["packaged"]:
        reads = [s for k, s in r["steps"].items() if "write" not in s["tags"]]
        writes = [r["steps"][k] for k in WRITE_SQL if k in r["steps"]]
        seeded = [r["steps"][k] for k in SEEDED_WRITE_SQL if k in r["steps"]]
        out.append(("noop-writes", all(s["outcome"] == "MATCH" for s in reads) and bool(writes)
                    and all(s["outcome"] != "MATCH" for s in writes)
                    and len(seeded) == len(SEEDED_WRITE_SQL) and all(s["outcome"] == "MISMATCH" for s in seeded),
                    "reads match; no committed-state write check matches, and the writes to seeded rows "
                    "(update, delete with dependents) are measured and differ"))
    elif r:
        out.append(("noop-writes", False, "did not package"))
    r = results.get("duplicate-beans")
    if r:
        out.append(("duplicate-beans", (not r["packaged"]) and r.get("ambiguous", False),
                    "augmentation refuses it with AmbiguousResolutionException"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default="")
    ap.add_argument("--results", default="")
    ap.add_argument("--keep", default="")
    ap.add_argument("--variants", default=",".join(VARIANTS))
    a = ap.parse_args()
    started = time.time()
    results = {}
    try:
        rt.need_tools("mvn", "java", "git", "podman")
        ok, why = rq.podman_ready()
        if not ok:
            raise rt.Skip(why)
        corpus = rq.load_corpus()
        oracles = rq.load_reference_oracles(corpus, "disabled")
        work = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="refqual-repo-"))
        work.mkdir(parents=True, exist_ok=True)
        tree = work / "candidate"
        if tree.exists():
            shutil.rmtree(tree)
        base_ident = rq.build_candidate(a.bundle or None, tree)
        for v in [x for x in a.variants.split(",") if x]:
            results[v] = measure(tree, v, work, corpus, oracles, base_ident)
    except rt.Skip as exc:
        print("SKIP: %s: %s" % (TEST_ID, exc))
        rq.write_results(a.results, {"test": TEST_ID, "status": "SKIP", "reason": str(exc),
                                     "seconds": round(time.time() - started, 1)})
        return 0
    rows = []
    for v, r in results.items():
        vv = verdict(r)
        failing = {k: s["differences"] for k, s in (r.get("steps") or {}).items() if s["outcome"] != "MATCH"}
        print("%-22s %-26s %s" % (v, vv, ("package: " + r["package_error"][:200]) if not r["packaged"] else
                                  "; ".join("%s: %s" % (k, d[0][:90]) for k, d in sorted(failing.items()))[:600]))
        rows.append({"case": "repository-strategy:%s" % v, "test_id": "%s::%s" % (TEST_ID, v), "executed": True,
                     "outcome": vv, "db": "postgresql", "mode": "disabled", "artifact": r["artifact"],
                     "evidence": {"scope": "repository effects (status, body, Location, errors, committed state); "
                                           "content-type measured by reference-owner-path-runtime",
                                  "log": r.get("log"), "package_error": r.get("package_error"),
                                  "failing_steps": failing, "seconds": r.get("seconds"),
                                  "steps": {k: s["outcome"] for k, s in (r.get("steps") or {}).items()}}})
    ctl = controls(results)
    bad = [c for c in ctl if not c[1]]
    for name, holds, why in ctl:
        print("control %-22s %s  (%s)" % (name, "holds" if holds else "DOES NOT HOLD", why))
        for row in rows:
            if row["test_id"].endswith("::" + name):
                row["control"] = {"expected": why, "holds": holds}
    rq.write_results(a.results, {"test": TEST_ID, "status": "FAIL" if bad else "PASS", "rows": rows,
                                 "controls": [{"variant": n, "holds": h, "expected": w} for n, h, w in ctl],
                                 "seconds": round(time.time() - started, 1)})
    if bad:
        print("FAIL: %s: control(s) did not hold: %s" % (TEST_ID, ", ".join(c[0] for c in bad)), file=sys.stderr)
        return 1
    print("OK: %s (candidate tree %s, PostgreSQL 16 in podman, pinned platform %s): the reference port of the selected "
          "Spring Data strategy matches every repository step of the frozen source; routed-back recursion, throwing "
          "placeholders, no-op writes and duplicate beans are each rejected; as-is measured: %s"
          % (TEST_ID, base_ident["candidate_tree"][:12], rt.pin()["version"],
             verdict(results["as-is"]) if "as-is" in results else "not run"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
