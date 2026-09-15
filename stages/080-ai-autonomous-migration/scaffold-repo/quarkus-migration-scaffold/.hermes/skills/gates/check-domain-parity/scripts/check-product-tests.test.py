#!/usr/bin/env python3
"""AR-2.8 measured by execution records and declared scenario capabilities.

Every tree here is built from a NAMING SCHEME, and each decision is asserted
twice: once on a petclinic-flavoured specimen and once on a specimen whose
packages, types, methods and scenario ids share nothing with it. A floor that
decides differently under renaming is reading literals, which is the defect
ADR-015 removed. Not dest.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-product-tests.py"
FIX = HERE.parent / "fixtures" / "product-tests"

CORPUS_SHA = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"


def _fail(msg: str, *extra: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    for e in extra:
        print(e, file=sys.stderr)
    return 1


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), str(root), *args], text=True, capture_output=True)


def out_of(cp: subprocess.CompletedProcess) -> str:
    return cp.stdout + cp.stderr


# ---------------------------------------------------------------------------
# two specimens, nothing in common but shape
# ---------------------------------------------------------------------------

PETCLINIC = {
    "name": "petclinic",
    "pkg": "org.example.petclinic",
    "retained_class": "ValidatorTests",   # *Tests.java: the suffix the old floor excluded
    "retained_method": "testHasErrors",
    "retained_named_class": "ReadOwnersTests",
    "scenarios": ["sc:read-owners", "sc:create-owner", "sc:cors-preflight-owners"],
}
LEDGER = {
    "name": "ledger",
    "pkg": "com.acme.ledger.rules",
    "retained_class": "AmountRulesTest",
    "retained_method": "rejectsNegative",
    "retained_named_class": "ListAccountsTest",
    "scenarios": ["op:list-accounts", "op:open-account", "op:preflight-accounts"],
}


def camel(scenario: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[^A-Za-z0-9]+", scenario) if part)


def gen_class(spec: dict, scenario: str, opaque: bool = False) -> str:
    """A generated class normally carries the scenario id; ``opaque`` names it
    nothing a name rule could match, so only the manifest can bind it."""
    if opaque:
        return "%s.Case%dIT" % (spec["pkg"], spec["scenarios"].index(scenario) + 1)
    return "%s.%s%s" % (spec["pkg"], camel(scenario), "IT")


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")


def write_source(root: Path, fqcn: str, test_root: str = "src/test/java") -> None:
    pkg, _, cls = fqcn.rpartition(".")
    p = root / test_root / pkg.replace(".", "/") / (cls + ".java")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("package %s;\n\npublic class %s {\n}\n" % (pkg, cls), encoding="utf-8")


def write_report(root: Path, fqcn: str, cases: list[tuple[str, str]]) -> None:
    """cases: (method, "pass" | "skip" | "fail")"""
    body = []
    for name, status in cases:
        inner = {"pass": "", "skip": "<skipped/>", "fail": '<failure message="assertion">x</failure>'}[status]
        body.append('<testcase classname="%s" name="%s">%s</testcase>' % (fqcn, name, inner))
    p = root / "target" / "surefire-reports" / ("TEST-%s.xml" % fqcn)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<testsuite name="%s" tests="%d">%s</testsuite>\n'
                 % (fqcn, len(cases), "".join(body)), encoding="utf-8")


def write_summary(root: Path, *, tests: int, reports: int, failures: list[tuple[str, str]] | None = None) -> None:
    write_json(root / "verification" / "build" / "surefire.json", {
        "schema": "rhoai3.surefire/v1", "ran": True, "reports": reports, "tests": tests,
        "failures": [{"classname": c, "name": n, "message": "assertion", "path": ""} for c, n in (failures or [])]})


def write_corpus(root: Path, spec: dict, *, schema: str = "rhoai3.scenario-corpus/v1") -> None:
    write_json(root / "verification" / "scenarios" / "corpus.json", {
        "schema": schema,
        "derived_from": {"producer": "derive-source-scenarios.py", "evidence_bundle_sha256": CORPUS_SHA},
        "scenarios": [{"id": sid, "entry_point": "ep:%s.Api#op%d():http" % (spec["pkg"], i),
                       "method": "GET", "path": "/api/thing/%d" % i, "body_absent": True}
                      for i, sid in enumerate(spec["scenarios"])]})


def write_qualification(root: Path, spec: dict, *, passing: list[str] | None = None, corpus_sha: str = CORPUS_SHA) -> None:
    names = spec["scenarios"] if passing is None else passing
    write_json(root / "verification" / "source-oracles" / "scenarios" / "_qualification.json", {
        "schema": "rhoai3.scenario-qualification/v1", "corpus_sha256": corpus_sha,
        "scenarios": {sid: {"capability": "PASS" if sid in names else "FAIL", "verdict": "PASS" if sid in names else "FAIL",
                            "evidence": {"status": "USABLE"}, "intent": "positive", "reason": ""}
                      for sid in spec["scenarios"]},
        "verdict": "PASS" if len(names) == len(spec["scenarios"]) else "FAIL"})


def write_manifest(root: Path, spec: dict, scenarios: list[str], *, corpus_sha: str = CORPUS_SHA, opaque: bool = False,
                   out: str = "") -> None:
    doc = {
        "schema": "rhoai3.generated-tests/v1", "corpus_sha256": corpus_sha,
        "generator": "generate-scenario-tests.py", "cases": [
            {"scenario": sid, "class": gen_class(spec, sid, opaque), "method": "run",
             "entry_point": "ep:%s.Api#op():http" % spec["pkg"]} for sid in scenarios]}
    if out:
        doc["out"] = out
    write_json(root / "evidence" / "tests" / "generated-manifest.json", doc)


def retained_only_tree(root: Path, spec: dict) -> None:
    """The v9 state: one retained *Tests.java, freshly executed, and a corpus
    of qualified capabilities none of it covers."""
    fq = "%s.%s" % (spec["pkg"], spec["retained_class"])
    write_source(root, fq)
    write_report(root, fq, [(spec["retained_method"], "pass"), (spec["retained_method"] + "Empty", "pass")])
    write_summary(root, tests=2, reports=1)
    write_corpus(root, spec)
    write_qualification(root, spec)


def generated_tree(root: Path, spec: dict, covered: list[str], *, manifest_sha: str = CORPUS_SHA, opaque: bool = False) -> None:
    retained_only_tree(root, spec)
    for sid in covered:
        fq = gen_class(spec, sid, opaque)
        write_source(root, fq)
        write_report(root, fq, [("run", "pass")])
    write_manifest(root, spec, covered, corpus_sha=manifest_sha, opaque=opaque)
    write_summary(root, tests=2 + len(covered), reports=1 + len(covered))


# ---------------------------------------------------------------------------
# the decisions, asserted on both specimens
# ---------------------------------------------------------------------------


def decisions(spec: dict) -> int:
    tag = spec["name"]
    with tempfile.TemporaryDirectory(prefix="ar28-%s-" % tag) as td:
        base = Path(td)

        # 1. a product test source that never ran is not acceptance
        t = base / "no-exec"
        write_source(t, "%s.%s" % (spec["pkg"], spec["retained_class"]))
        cp = run(t)
        if cp.returncode != 1 or "execution record" not in cp.stderr:
            return _fail("[%s] a compiled, never-executed product test must refuse" % tag, out_of(cp))

        # 2. a summary that says a phase ran, with no per-case report to bind
        t = base / "summary-only"
        write_source(t, "%s.%s" % (spec["pkg"], spec["retained_class"]))
        write_summary(t, tests=3, reports=1)
        cp = run(t)
        if cp.returncode != 1 or "per-case report" not in cp.stderr:
            return _fail("[%s] a failure-only summary can never bind an execution to a source" % tag, out_of(cp))

        # 3. executed but SKIPPED is not executed
        t = base / "skipped"
        fq = "%s.%s" % (spec["pkg"], spec["retained_class"])
        write_source(t, fq)
        write_report(t, fq, [(spec["retained_method"], "skip")])
        write_summary(t, tests=1, reports=1)
        cp = run(t)
        if cp.returncode != 1 or "skipped" not in cp.stderr:
            return _fail("[%s] a skipped case is not a passed case" % tag, out_of(cp))

        # 4. *Tests.java with a fresh execution record COUNTS as a product test
        #    (ADR-015 floor correction (a)); with no corpus, capability
        #    coverage is N/A with its reason, never idle
        t = base / "no-corpus"
        write_source(t, fq)
        write_report(t, fq, [(spec["retained_method"], "pass")])
        write_summary(t, tests=1, reports=1)
        cp = run(t)
        if cp.returncode != 0:
            return _fail("[%s] a freshly executed *Tests.java is a product test" % tag, out_of(cp))
        if "N/A: AR-2.8 capability coverage" not in cp.stdout or "not idle" not in cp.stdout:
            return _fail("[%s] no declared capability is N/A with a reason, not idle" % tag, out_of(cp))
        if spec["retained_class"] not in cp.stdout:
            return _fail("[%s] the floor must name the executed class it counted" % tag, out_of(cp))

        # 5. the v9 state: the retained test executes and covers NO declared
        #    capability -> refuse, naming exactly which are uncovered
        t = base / "retained-only"
        retained_only_tree(t, spec)
        cp = run(t)
        if cp.returncode != 1:
            return _fail("[%s] retained-only coverage of 3 capabilities must refuse" % tag, out_of(cp))
        if "no executed product test covers ANY declared capability" not in cp.stderr:
            return _fail("[%s] the refusal must be about capability coverage, not about an empty suite" % tag, out_of(cp))
        for sid in spec["scenarios"]:
            if sid not in cp.stderr:
                return _fail("[%s] the message must name every uncovered capability (%s missing)" % (tag, sid), out_of(cp))
        if spec["retained_class"] not in cp.stderr:
            return _fail("[%s] the refusal must state that the retained test DID execute" % tag, out_of(cp))
        if "no execution record" in cp.stderr or "is clean and bound" in cp.stderr:
            return _fail("[%s] ValidatorTests-shaped evidence must not read as an unexecuted suite" % tag, out_of(cp))

        # 6. a manifest-bound generated case covers its capability
        t = base / "generated-all"
        generated_tree(t, spec, list(spec["scenarios"]))
        cp = run(t)
        if cp.returncode != 0 or "3 of 3" not in cp.stdout:
            return _fail("[%s] every capability covered by a generated, executed case is a pass" % tag, out_of(cp))
        cp = run(t, "--require-coverage")
        if cp.returncode != 0:
            return _fail("[%s] full coverage must also pass --require-coverage" % tag, out_of(cp))
        if "generated" not in cp.stdout:
            return _fail("[%s] the report must say a capability is covered by a GENERATED case" % tag, out_of(cp))

        # 7. partial coverage: a gap by default, a refusal under --require-coverage,
        #    naming exactly the uncovered capability
        covered = list(spec["scenarios"][:2])
        missing = spec["scenarios"][2]
        t = base / "generated-partial"
        generated_tree(t, spec, covered)
        cp = run(t)
        if cp.returncode != 0 or "GAP: AR-2.8" not in cp.stdout or missing not in cp.stdout:
            return _fail("[%s] partial coverage is a named gap, not a refusal, by default" % tag, out_of(cp))
        cp = run(t, "--require-coverage")
        if cp.returncode != 1 or missing not in cp.stderr:
            return _fail("[%s] --require-coverage must refuse and name the uncovered capability" % tag, out_of(cp))
        head = cp.stderr.splitlines()[0]
        if any(sid in head for sid in covered):
            return _fail("[%s] the refusal line must name only what is uncovered" % tag, out_of(cp))

        # 8. a generated case that did not execute cleanly does not count,
        #    and the floor says the manifest declared it
        t = base / "generated-red"
        generated_tree(t, spec, list(spec["scenarios"]))
        write_report(t, gen_class(spec, missing), [("run", "fail")])
        cp = run(t, "--require-coverage")
        if cp.returncode != 1 or missing not in cp.stderr or "declared generated" not in cp.stderr:
            return _fail("[%s] a declared generated case that failed is not coverage" % tag, out_of(cp))

        # 9. a manifest generated from another corpus proves nothing here
        t = base / "manifest-foreign"
        generated_tree(t, spec, list(spec["scenarios"]), manifest_sha="f" * 64, opaque=True)
        cp = run(t)
        if cp.returncode != 1 or "prove nothing" not in cp.stderr:
            return _fail("[%s] a manifest bound to another corpus must not count" % tag, out_of(cp))

        # 10. a HAND-RETAINED test that names the capability covers it, with no
        #     manifest anywhere (absence of the manifest is not an error)
        t = base / "retained-named"
        named = "%s.%s" % (spec["pkg"], spec["retained_named_class"])
        write_corpus(t, spec)
        write_qualification(t, spec, passing=[spec["scenarios"][0]])
        write_source(t, named)
        write_report(t, named, [("run", "pass")])
        write_summary(t, tests=1, reports=1)
        cp = run(t, "--require-coverage")
        if cp.returncode != 0 or "retained" not in cp.stdout:
            return _fail("[%s] a retained test naming the capability covers it" % tag, out_of(cp))
        if "no %s" % "evidence/tests/generated-manifest.json" not in cp.stdout:
            return _fail("[%s] an absent manifest is stated, not an error" % tag, out_of(cp))
        if "N/A: AR-2.8 2 scenario(s) the source did not qualify" not in cp.stdout:
            return _fail("[%s] an unqualified scenario is never demanded, and says so" % tag, out_of(cp))

        # 11. unreadable evidence is exit 2, never a quiet green
        t = base / "bad-corpus"
        write_source(t, fq)
        write_report(t, fq, [(spec["retained_method"], "pass")])
        write_corpus(t, spec, schema="rhoai3.scenario-corpus/v0")
        cp = run(t)
        if cp.returncode != 2 or "unreadable evidence" not in cp.stderr:
            return _fail("[%s] a corpus that is not its schema is exit 2" % tag, out_of(cp))

        # 12. the snapshot wins over a cleaned target/
        t = base / "snapshot"
        retained_only_tree(t, spec)
        shutil.copytree(t / "target" / "surefire-reports", t / "evidence" / "m4-pre-rebuild" / "test-reports")
        shutil.rmtree(t / "target")
        cp = run(t)
        if cp.returncode != 1 or spec["retained_class"] not in cp.stderr:
            return _fail("[%s] the pre-rebuild snapshot is an execution record" % tag, out_of(cp))
    return 0


def no_specimen_literals() -> int:
    """The defect ADR-015 removed: the floor must carry no specimen name."""
    text = SCRIPT.read_text(encoding="utf-8").lower()
    banned = ("petclinic", "ownercrud", "franklin", "owner", "vet", "specialty", "validatortests", "/q/health", "ar28:")
    hit = sorted(t for t in banned if t in text)
    if hit:
        return _fail("check-product-tests.py still carries specimen literals: %s" % ", ".join(hit))
    return 0


def receipt_case() -> int:
    with tempfile.TemporaryDirectory(prefix="ar28-receipt-") as td:
        root = Path(td)
        generated_tree(root, PETCLINIC, list(PETCLINIC["scenarios"]))
        cp = run(root, "--write-receipt")
        rec = root / "evidence" / "receipts" / "gates" / "check-domain-parity.json"
        if cp.returncode != 0:
            return _fail("--write-receipt rc=%s" % cp.returncode, out_of(cp))
        if not rec.is_file():
            return _fail("--write-receipt did not write %s" % rec)
        doc = json.loads(rec.read_text(encoding="utf-8"))
        if doc.get("gate") != "check-domain-parity" or "argv" not in doc:
            return _fail("domain receipt schema %s" % doc)
    return 0


def probe_only_case() -> int:
    cp = run(FIX / "ar28-probe-only")
    if cp.returncode != 1 or "probe-only" not in cp.stderr:
        return _fail("harness probes are never product acceptance", out_of(cp))
    return 0


def generated_root_case(spec: dict) -> int:
    """ADR-015: the generated cases live in the root the manifest's ``out``
    names, because nothing but the m4-parity profile may compile them. A floor
    that scans only src/test/java calls every one of their executions
    ``unbound`` -- an execution belonging to no test source of this tree --
    which is the mirror of counting a source that never ran."""
    tag = spec["name"]
    with tempfile.TemporaryDirectory(prefix="ar28-genroot-%s-" % tag) as td:
        base = Path(td)
        covered = [spec["scenarios"][0]]

        # 1. a generated case in the generated root, executed clean: counted,
        #    and it covers its capability
        for out_root in ("src/parity-test/java", "src/m4-parity/java"):
            t = base / ("generated-" + out_root.replace("/", "-"))
            retained_only_tree(t, spec)
            fq = gen_class(spec, covered[0])
            write_source(t, fq, out_root)
            write_report(t, fq, [("run", "pass")])
            # the manifest's own root is what the floor reads; the default is
            # only what the generator ships with
            write_manifest(t, spec, covered, out=("" if out_root == "src/parity-test/java" else out_root))
            write_summary(t, tests=3, reports=2)
            cp = run(t)
            if cp.returncode != 0:
                return _fail("[%s] a generated case under %s must count" % (tag, out_root), out_of(cp))
            if "%s: generated" % covered[0] not in out_of(cp):
                return _fail("[%s] the generated case must cover its capability from %s" % (tag, out_root), out_of(cp))
            if "belong to no test source" in out_of(cp):
                return _fail("[%s] a generated case in a scanned root is never unbound" % tag, out_of(cp))

        # 2. a case under NEITHER root is unbound: its source is not this
        #    tree's product acceptance, whatever executed under its name
        t = base / "neither-root"
        retained_only_tree(t, spec)
        fq = gen_class(spec, covered[0])
        write_source(t, fq, "src/elsewhere/java")
        write_report(t, fq, [("run", "pass")])
        write_manifest(t, spec, covered)
        write_summary(t, tests=3, reports=2)
        cp = run(t)
        if "%s: generated" % covered[0] in out_of(cp):
            return _fail("[%s] a source under neither test root must not count as coverage" % tag, out_of(cp))
        if "%s#run" % fq not in out_of(cp) or "UNCOVERED" not in out_of(cp):
            return _fail("[%s] the capability the unbound case claimed must be reported UNCOVERED" % tag, out_of(cp))

        # 3. the empty-acceptance refusal names both roots
        t = base / "empty"
        write_corpus(t, spec)
        write_qualification(t, spec)
        cp = run(t)
        if cp.returncode != 1:
            return _fail("[%s] a tree with no product test source must refuse" % tag, out_of(cp))
        for needle in ("src/test/java", "src/parity-test/java"):
            if needle not in cp.stderr:
                return _fail("[%s] the empty-acceptance refusal must name %s" % (tag, needle), out_of(cp))
    return 0


def main() -> int:
    if (no_specimen_literals() or probe_only_case() or decisions(PETCLINIC) or decisions(LEDGER) or generated_root_case(PETCLINIC) or generated_root_case(LEDGER) or receipt_case()):
        return 1
    print("OK: check-product-tests (executed *Test/*Tests/*IT bound to this tree; a skipped, failed or unbound case is not an "
          "execution; capabilities are the corpus scenarios the source qualified PASS; generated coverage is manifest-bound and "
          "corpus-bound, retained coverage is a case that names the capability; no capability covered refuses, --require-coverage "
          "refuses every gap by name; the generated root the manifest names is scanned beside src/test/java and a source under "
          "neither is unbound; unreadable evidence is 2 — the same decisions under a fully renamed specimen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
