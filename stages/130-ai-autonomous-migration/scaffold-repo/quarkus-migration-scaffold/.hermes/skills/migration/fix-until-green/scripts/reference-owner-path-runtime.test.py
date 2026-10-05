#!/usr/bin/env python3
"""M-3 reference qualification, application level: the Owner path through
controller -> service -> repository -> PostgreSQL on the pinned target stack,
measured on a REAL candidate tree and compared with the frozen source oracle.

The tree (fixtures/reference-qualification/candidate/candidate.json): the v28
destination's final loop commit plus only the listed recipe applications
(servlet-redirect-response: the SpEL field v28 left on RootRestController,
without which the tree does not package). It is a qualification candidate --
not v28's output and not an accepted tree -- and every row names it.

Measured (each row bound to artifact, engine and mode):
  clean-generation   no generated DTO is committed; `mvn clean package`
                     regenerates them with the destination generator, whose
                     name/library/version must be the catalog's qualified
                     generated-body-binding row
  package            the candidate packages offline with the pinned platform
  per corpus step    the candidate on PostgreSQL 16 (podman; the tree's own
                     initDB.sql + baseline-data.sql), security disabled and
                     enabled, compared with the frozen source's PostgreSQL
                     captures for the same mode (source-oracle/postgresql-*):
                     startup/root path, Owner reads, create with omitted /
                     null / empty collections, invalid bodies and their
                     `errors` header, update, delete with dependents (read back
                     over HTTP and on a NEW database connection), Location,
                     CORS preflight/actual, basic authentication
  source-engine      the source's own hsqldb vs PostgreSQL captures (no boot):
                     which contract points depend on the engine

This is a MEASUREMENT of the candidate: a MISMATCH is a finding reported in
the results, not a harness failure. The exit status is 1 only when the
measurement itself could not be made correctly (or with --require-match when
anything mismatched). A missing input prints SKIP with the reason and exits 0;
reference-qualification.sh never counts a SKIP as a pass.

Options: --bundle <v28-dest.bundle> (or REFQUAL_V28_BUNDLE), --results <json>,
--keep <dir> (keep the built tree and logs), --require-match, --rehearsal.

--rehearsal measures the REHEARSAL tree instead (fixtures/reference-
qualification/rehearsal/rehearsal.json: the candidate plus one patch per
guided repair, each applied as the catalog guidance instructs a worker),
under the test id reference-owner-path-rehearsal. It is labelled REHEARSAL:
not a migration output and not a run result. Oracles, corpus and comparator
are the same.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reference_qualification as rq  # noqa: E402
import test_runtime_fixture as rt  # noqa: E402

TEST_ID = "reference-owner-path-runtime"
REHEARSAL_TEST_ID = "reference-owner-path-rehearsal"
DTO_REL = "org/springframework/samples/petclinic/dto"


def _row(case, step, executed, outcome, mode, artifact, evidence, db="postgresql"):
    return {"case": case, "test_id": "%s::%s" % (TEST_ID, step), "executed": executed, "outcome": outcome,
            "db": db, "mode": mode, "artifact": artifact, "evidence": evidence}


# The catalog guidance a worker now receives for a remaining difference (M-4, ADR-025
# follow-up). A MISMATCH row is "guided" only when EVERY difference maps to a row here;
# a Content-Type difference that follows a guided status difference is that status's.
GUIDANCE = {
    "content-type-parameter": "PARITY_CONTENT_TYPE: source-media-type-parameter-adapter/v1 (restore-source-response-shape, ADR-019)",
    "cors": "PARITY_CORS: source-cors-response-adapter/v1 (restore-source-response-shape, ADR-019)",
    "object-name": "validation_helpers getObjectName(): Introspector.decapitalize(<body short name>) (validation-object-name)",
    "absent-row": "repository_behaviour.query_result_semantics + the unit check static_triggers.absent_result_verdict",
    "required-read-only": "build_plugins jaxrs-spec required_read_only, planned as plan:gbro (static_triggers.required_read_only_items)",
    "advice": "exception_advice.request-body-unreadable (reader-exception mappers answering through the application's advice)",
}


def _ct(v: str) -> str:
    return (v or "").strip('"').split(";")[0].strip().lower()


def guidance_for(step_id: str, diffs: list) -> tuple:
    """(guidance keys, unexplained differences) for one remaining MISMATCH."""
    keys, rest = [], []
    status = next((d for d in diffs if d.startswith("status:")), "")
    for d in diffs:
        if d.startswith("header access-control-"):
            keys.append("cors")
        elif d.startswith("status: source 404, destination 500"):
            keys.append("absent-row")
        elif d.startswith("status: source 400, destination 500"):
            keys.append("required-read-only")
        elif d.startswith("header content-type:"):
            m = re.match(r'header content-type: source (.*), destination (.*)$', d)
            src, dst = (m.group(1), m.group(2)) if m else ("", "")
            if src.startswith('"application/json"') and "charset" in dst and _ct(src) == _ct(dst):
                keys.append("content-type-parameter")
            elif status:
                continue                      # follows the status difference
            elif "text/plain" in src and dst == "null":
                keys.append("advice")
            else:
                rest.append(d)
        elif d.startswith("header errors:"):
            m = re.match(r"header errors: source (.*), destination (.*)$", d)
            try:
                a, b = json.loads(m.group(1)), json.loads(m.group(2))
            except (AttributeError, ValueError):
                a, b = None, None
            lower = lambda rows: [dict(r, objectName=(r["objectName"][:1].lower() + r["objectName"][1:]))  # noqa: E731
                                  for r in rows] if isinstance(rows, list) else rows
            if isinstance(a, list) and isinstance(b, list) and a != b and lower(b) == a:
                keys.append("object-name")
            elif status:
                continue
            else:
                rest.append(d)
        elif d.startswith("body at") and status:
            continue
        elif d.startswith("body at") and '"className"' in d and '"exMessage"' in d:
            keys.append("advice")
        else:
            rest.append(d)
    return sorted(set(keys)), rest


def clean_generation(root: Path) -> tuple:
    """(outcome, evidence) for the generated-body-binding row's build:clean-generation check."""
    catalog = json.loads((rt.GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json").read_text())
    q = catalog["migration_recipes"]["generated-body-binding"]["qualified"]
    pom = (root / "pom.xml").read_text(encoding="utf-8")
    m = re.search(r"<artifactId>openapi-generator-maven-plugin</artifactId>(.*?)</plugin>", pom, re.S)
    block = m.group(1) if m else ""
    ver_prop = re.search(r"<openapi-generator-maven-plugin.version>([^<]+)<", pom)
    gen = (re.search(r"<generatorName>([^<]+)<", block) or [None, None])[1]
    lib = (re.search(r"<library>([^<]+)<", block) or [None, None])[1]
    jc = (re.search(r"<generateJsonCreator>([^<]+)<", block) or [None, "(default true)"])[1]
    ver = ver_prop.group(1) if ver_prop else None
    committed = subprocess.run(["git", "-C", str(root), "ls-files", "--", "src/main/java/%s" % DTO_REL],
                               capture_output=True, text=True).stdout.split()
    generated = sorted(p.name for p in root.glob("target/generated-sources/**/%s/*.java" % DTO_REL))
    qualified = gen in q and lib in q[gen]["libraries"] and ver in q[gen]["plugin_versions"]
    ev = {"generator": gen, "library": lib, "plugin_version": ver, "generateJsonCreator": jc,
          "catalog_qualified": qualified, "committed_generated_files": committed,
          "regenerated_models": generated}
    ok = qualified and not committed and "OwnerDto.java" in generated
    return ("PASS" if ok else "FAIL"), ev


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default="")
    ap.add_argument("--results", default="")
    ap.add_argument("--keep", default="")
    ap.add_argument("--require-match", action="store_true")
    ap.add_argument("--rehearsal", action="store_true")
    a = ap.parse_args()
    global TEST_ID
    if a.rehearsal:
        TEST_ID = REHEARSAL_TEST_ID
    rows = []
    started = time.time()
    try:
        rt.need_tools("mvn", "java", "git", "podman")
        ok, why = rq.podman_ready()
        if not ok:
            raise rt.Skip(why)
        corpus = rq.load_corpus()
        oracles = {m: rq.load_reference_oracles(corpus, m) for m in ("disabled", "enabled")}
        work = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="refqual-owner-"))
        work.mkdir(parents=True, exist_ok=True)
        tree = work / "candidate"
        if tree.exists():
            shutil.rmtree(tree)
        ident = (rq.build_rehearsal if a.rehearsal else rq.build_candidate)(a.bundle or None, tree)
        rows.append(_row("candidate-build", "candidate", True, "PASS", "n/a", ident,
                         {"note": ("%s: candidate + one patch per guided repair; every step's tree id verified"
                                   % rq.REHEARSAL_LABEL) if a.rehearsal else
                          "baseline + recipe patches only; tree ids verified"}, db="n/a"))
        ok, out = rq.package_tree(tree)
        art = dict(ident, **(rq.artifact_identity(tree) if ok else {}))
        first_err = next((ln.strip() for ln in out.splitlines() if "[error]" in ln or "ERROR] Failed" in ln), "")
        rows.append(_row("package", "package", True, "PASS" if ok else "FAIL", "n/a", art,
                         {"first_error": first_err[:600]} if not ok else {"platform": rt.pin()["version"]}, db="n/a"))
        g_out, g_ev = clean_generation(tree)
        rows.append(_row("clean-generation", "clean-generation", True, g_out, "n/a", art, g_ev, db="n/a"))
        if not ok:
            for step in corpus["steps"]:
                for m in step.get("modes") or ["disabled"]:
                    rows.append(_row(step.get("case", ""), step["id"], False, "NOT_EXECUTED", m, art,
                                     {"reason": "the candidate did not package: %s" % first_err[:300]}))
        else:
            spec = json.loads(rq.CANDIDATE.read_text(encoding="utf-8"))
            seed = [tree / s for s in spec["database"]["destination_seed"]]
            for mode in ("disabled", "enabled"):
                with rq.seeded_postgres(seed) as pg:
                    log = work / ("candidate-%s.log" % mode)
                    with rq.boot_candidate(tree, pg, mode, log) as base:
                        dest = rq.run_corpus(base, corpus, mode, "postgresql", pg)
                    db_ev = {"image": rt.PG_IMAGE, "seed": [{"path": str(Path(s["path"]).relative_to(tree)),
                                                             "sha256": s["sha256"]} for s in pg["scripts"]]}
                logtext = log.read_text(errors="replace")
                soe = logtext.count("java.lang.StackOverflowError")
                (work / ("destination-%s.json" % mode)).write_text(json.dumps(dest, indent=1, sort_keys=True))
                adr = rq.adr_accepted(rt.GOLDEN)
                raw_rows = rq.compare_all(corpus, oracles[mode], dest, mode, "postgresql")
                cmp_rows = rq.compare_all(corpus, oracles[mode], dest, mode, "postgresql", adr025=adr)
                for sid, r in cmp_rows.items():
                    ex = dest.get(sid, {})
                    raw = raw_rows.get(sid) or {}
                    keys, rest = guidance_for(sid, r["differences"]) if r["outcome"] == "MISMATCH" else ([], [])
                    ev = {"differences": r["differences"], "difference_classes": r["difference_classes"],
                          "adr025": {"accepted": adr, "equivalences": r.get("equivalences") or [],
                                     "outcome_without": raw.get("outcome"), "differences_without": raw.get("differences")},
                          "classification": (None if r["outcome"] != "MISMATCH" else
                                             {"class": "guided" if keys and not rest else "candidate-defect",
                                              "guidance": [GUIDANCE[k] for k in keys], "unexplained": rest}),
                          "db": db_ev, "oracle": "source-oracle/%s.json" % r["oracle"],
                          "oracle_db": r["oracle"].split("-security-")[0],
                          "destination_status": (ex.get("response") or {}).get("status"),
                          "destination_log_stackoverflow_count": soe}
                    rows.append(_row(r["case"], sid, r["outcome"] != "UNMEASURED", r["outcome"], mode, art, ev,
                                     db="destination postgresql; oracle source %s" % ev["oracle_db"]))
        # the source's own engine sensitivity (captures only; nothing booted)
        for mode in ("disabled", "enabled"):
            try:
                h = rq.load_oracle("hsqldb", mode)
            except rt.Skip as exc:
                rows.append(_row("source-engine-sensitivity", "source-engine-%s" % mode, False, "NOT_EXECUTED", mode,
                                 {"compared": "source hsqldb vs source postgresql captures"}, {"reason": str(exc)},
                                 db="hsqldb-vs-postgresql"))
                continue
            pg_o = rq.load_oracle("postgresql", mode)
            diff = rq.compare_all(corpus, {"http": pg_o, "sql": pg_o}, h["steps"], mode, "hsqldb")
            differing = {k: v["differences"] for k, v in diff.items() if v["outcome"] == "MISMATCH"}
            rows.append(_row("source-engine-sensitivity", "source-engine-%s" % mode, True,
                             "DIFFERENT" if differing else "SAME", mode,
                             {"compared": "source hsqldb vs source postgresql captures",
                              "jar_sha256": pg_o["provenance"]["source_jar_sha256"]},
                             {"differing_steps": differing}, db="hsqldb-vs-postgresql"))
    except rt.Skip as exc:
        print("SKIP: %s: %s" % (TEST_ID, exc))
        rq.write_results(a.results, {"test": TEST_ID, "status": "SKIP", "reason": str(exc), "rows": rows,
                                     "seconds": round(time.time() - started, 1)})
        return 0
    cand = [r for r in rows if r["test_id"].split("::")[1] not in ("candidate", "package", "clean-generation")
            and r["case"] != "source-engine-sensitivity"]
    # the three-way account the ADR-025 ruling asks for: of the mismatches WITHOUT the ruling,
    # (b) equal under ADR-025, (a) guided (a worker now receives the repair), (c) candidate defects
    account = {"equal_under_adr025": [], "guided": [], "candidate_defect": []}
    for r in cand:
        adr_ev = (r["evidence"] or {}).get("adr025") if isinstance(r["evidence"], dict) else None
        if not adr_ev or adr_ev.get("outcome_without") != "MISMATCH":
            continue
        sid = "%s[%s]" % (r["test_id"].split("::")[1], r["mode"])
        if r["outcome"] == "MATCH":
            account["equal_under_adr025"].append(sid)
        elif (r["evidence"].get("classification") or {}).get("class") == "guided":
            account["guided"].append(sid)
        else:
            account["candidate_defect"].append(sid)
    counts = {}
    for r in cand:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    for r in rows:
        d = r["evidence"].get("differences") if isinstance(r["evidence"], dict) else None
        print("%-26s %-44s %-8s %-12s %s" % (r["case"], r["test_id"].split("::")[1], r["mode"], r["outcome"],
                                              ("; ".join(d)[:220] if d else "")))
    status = "MEASURED"
    payload = {"test": TEST_ID, "status": status, "counts": counts, "rows": rows, "adr025_account": account,
               "seconds": round(time.time() - started, 1)}
    if a.rehearsal:
        payload["label"] = rq.REHEARSAL_LABEL
    rq.write_results(a.results, payload)
    print("ADR-025 account of the mismatches without the ruling: (b) equal under ADR-025 %d, (a) guided %d, (c) candidate "
          "defects %d" % (len(account["equal_under_adr025"]), len(account["guided"]), len(account["candidate_defect"])))
    art0 = rows[0]["artifact"]
    print("MEASURED: %s (%s tree %s, PostgreSQL 16 in podman, pinned platform %s): %s"
          % (TEST_ID, "REHEARSAL" if a.rehearsal else "candidate",
             (art0.get("measured_tree") or art0.get("candidate_tree") or "?")[:12], rt.pin()["version"],
             ", ".join("%s %d" % kv for kv in sorted(counts.items()))))
    if a.require_match and counts.get("MISMATCH"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
