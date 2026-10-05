#!/usr/bin/env python3
"""AR-2.8 -- product acceptance tests, measured by EXECUTION and by the
capabilities the evidence declares (ADR-015, architect ruling 2026-09-15).

Two corrections this floor used to get wrong, both reproduced on v9's first
M4 verdict:

  * it discovered ``*Test.java`` and ``*IT.java`` and nothing else, so
    ``*Tests.java`` -- the one retained, freshly executed product test in the
    destination -- was excluded by a FILENAME rule and counted for nothing.
  * it decided coverage by scanning test SOURCE for literals taken from one
    pilot's own type names, its seed data and a platform probe route. A
    literal from one specimen is not a measurement of any other, and a source
    file that compiles and never runs is exactly the failure this floor exists
    to catch.

Both are replaced by evidence:

  a product test counts when a file for it exists under one of this tree's
  test roots (``*Test.java``, ``*Tests.java``, ``*IT.java``, outside the
  harness probe package) AND an execution record names that class with the
  case neither skipped nor failed nor errored.

  There are TWO such roots. ``src/test/java`` is the loop's own, and the
  generated parity suite lives in the root the generated manifest's ``out``
  names (default ``src/parity-test/java``), which nothing compiles but the
  harness-owned ``m4-parity`` profile (ADR-015). Scanning only the first one
  was a floor measuring a root the harness had deliberately moved its cases
  out of: every generated case then executed, and every one of them was
  ``unbound`` -- an execution belonging to no test source of this tree.

  the coverage this floor demands is the set of DECLARED SCENARIO
  CAPABILITIES: every scenario of ``verification/scenarios/corpus.json``
  (derived -- it names its producer in ``derived_from`` -- or hand-authored)
  whose record in ``verification/source-oracles/scenarios/_qualification.json``
  has capability PASS. A scenario the source never demonstrated is not a
  capability and is never demanded here. Nothing is required that the tree's
  own evidence does not declare, which is the standing rule behind Architect
  130828ZA (do not invent a platform probe route the harvest never found)
  expressed as a measurement instead of a heuristic.

EXECUTION RECORDS
  Per-case records are the surefire/failsafe XML this destination already
  keeps: ``evidence/m4-pre-rebuild/test-reports`` when that snapshot exists
  (a later ``mvn clean`` cannot hide a result), otherwise
  ``target/surefire-reports`` and ``target/failsafe-reports``.
  ``verification/build/surefire.json`` (``rhoai3.surefire/v1``) is read
  alongside them: it says whether a test phase RAN at all, and every failure
  it lists marks that class red even when the XML for it is absent. It carries
  no per-case roster of what passed, so it can never on its own bind an
  execution to a file: a phase that ran and left no bindable per-case report
  is a REFUSAL, not a pass. No report never means green.

COVERAGE
  A capability is covered when an executed, clean product test case names it.
  Two ways, in this order:

  generated -- ``evidence/tests/generated-manifest.json``, written by the
      harness capability that owns the generated files:

        {"schema": "rhoai3.generated-tests/v1",
         "corpus_sha256": "<digest of the corpus the cases were generated from>",
         "cases": [{"scenario": "<scenario id>",
                    "class": "<fully qualified test class>",
                    "method": "<test method>",
                    "entry_point": "<entry point id>"}, ...]}

      A manifest case counts only when that exact class (and method, when the
      records name one) executed cleanly. The manifest is OPTIONAL: its
      absence means "no generated coverage", never an error. A manifest whose
      ``corpus_sha256`` does not match the corpus in this tree is reported and
      its cases do not count -- cases generated from another corpus prove
      nothing about this one.

  retained -- an executed, clean case whose class or method NAMES the
      scenario: the normalised scenario id (letters and digits only, folded to
      lower case), or its local part after the last ``:`` when that part is at
      least 6 normalised characters, appears in the normalised
      ``Class#method``. The 6-character floor keeps a short local part from
      matching by accident.

EXIT CODES
  0  the floor is satisfied, or capability coverage is N/A with its reason
     stated (see IDLE).
  1  a refusal: no product test source at all; only harness probes; no
     execution record; no executed clean product case bound to this tree; the
     declared capabilities exist and NOT ONE of them is covered; or, with
     ``--require-coverage``, any capability uncovered. Every refusal names the
     capabilities it is about.
  2  evidence that cannot be read: unparseable surefire/failsafe XML, a
     corpus, qualification or generated manifest that is not its declared
     schema or is not JSON. Unreadable is never silently green.

IDLE
  "N/A" is declared with its evidence and is never idle-in-ACCEPT. There is
  exactly one N/A here: the tree declares no qualified scenario capability (no
  corpus, no qualification, or no scenario qualified PASS). Capability
  coverage is then N/A and the floor still requires at least one executed,
  clean product test -- an empty suite is never an accept path. A capability
  that exists and is uncovered is a GAP, printed by name; without
  ``--require-coverage`` a gap does not fail the floor as long as at least one
  capability is covered, and with it every gap fails.

``--require-coverage`` is off by default: coverage is restored a capability at
a time and the floor must not turn a partially restored suite into a red that
hides the real one.

The harness probe package ``com.example.tooling.smoke.*`` never counts toward
product acceptance (pair AR-3.6).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

HARNESS_PREFIX = "com/example/tooling/smoke/"
TEST_SUFFIXES = ("Test.java", "Tests.java", "IT.java")

TEST_ROOT = Path("src") / "test" / "java"
# The generated parity suite's root (ADR-015). Read from the manifest, because
# the generator's --out decides it; this is only the default it ships with.
GENERATED_TEST_ROOT = Path("src") / "parity-test" / "java"
REPORT_SNAPSHOT = Path("evidence") / "m4-pre-rebuild" / "test-reports"
REPORT_LIVE = (Path("target") / "surefire-reports", Path("target") / "failsafe-reports")
SUREFIRE_JSON = Path("verification") / "build" / "surefire.json"
SUREFIRE_SCHEMA = "rhoai3.surefire/v1"
CORPUS = Path("verification") / "scenarios" / "corpus.json"
CORPUS_SCHEMA = "rhoai3.scenario-corpus/v1"
QUALIFICATION = Path("verification") / "source-oracles" / "scenarios" / "_qualification.json"
QUALIFICATION_SCHEMA = "rhoai3.scenario-qualification/v1"
GENERATED_MANIFEST = Path("evidence") / "tests" / "generated-manifest.json"
GENERATED_SCHEMA = "rhoai3.generated-tests/v1"

MIN_LOCAL_PART = 6  # normalised characters; below this a local part matches by accident


class Unreadable(ValueError):
    """Evidence that exists and cannot be read: exit 2, never a quiet pass."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Unreadable("%s could not be read: %s" % (path.name, exc)) from exc


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


# ---------------------------------------------------------------------------
# the tree: which test sources are product acceptance at all
# ---------------------------------------------------------------------------


def generated_test_root(root: Path) -> Path:
    """The root the harness generated its parity cases into, as the manifest
    says. A manifest that cannot be read does not decide the root here -- it is
    read again, and refused, where the manifest itself is the evidence."""
    p = Path(root) / GENERATED_MANIFEST
    if not p.is_file():
        return GENERATED_TEST_ROOT
    try:
        doc = _load_json(p)
    except Unreadable:
        return GENERATED_TEST_ROOT
    out = str(doc.get("out") or "") if isinstance(doc, dict) else ""
    return Path(out) if out else GENERATED_TEST_ROOT


def test_roots(root: Path) -> list[Path]:
    """The loop's test root and the generated parity root, in that order, with
    no duplicate when a tree happens to declare them the same."""
    roots = [TEST_ROOT, generated_test_root(root)]
    seen: list[Path] = []
    for rel in roots:
        if rel not in seen:
            seen.append(rel)
    return seen


def product_test_sources(root: Path) -> dict[str, str]:
    """{fully qualified class name: path relative to root} for every product
    acceptance test source, over BOTH test roots (ADR-015). ``*Tests.java`` is
    one of them: the suffix says nothing about what the file tests."""
    out: dict[str, str] = {}
    for rel in test_roots(root):
        base = Path(root) / rel
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.java")):
            if not p.name.endswith(TEST_SUFFIXES):
                continue
            inner = p.relative_to(base).as_posix()
            if inner.startswith(HARNESS_PREFIX):
                continue
            out[inner[: -len(".java")].replace("/", ".")] = p.relative_to(root).as_posix()
    return out


def harness_test_sources(root: Path) -> list[str]:
    found: list[str] = []
    for rel in test_roots(root):
        base = Path(root) / rel
        if not base.is_dir():
            continue
        found += [
            p.relative_to(root).as_posix()
            for p in base.rglob("*.java")
            if p.name.endswith(TEST_SUFFIXES)
            and p.relative_to(base).as_posix().startswith(HARNESS_PREFIX)
        ]
    return sorted(found)


# ---------------------------------------------------------------------------
# execution records
# ---------------------------------------------------------------------------


def report_dirs(root: Path) -> list[Path]:
    """The snapshot when it holds reports, otherwise the live report dirs."""
    snap = Path(root) / REPORT_SNAPSHOT
    if snap.is_dir() and any(snap.rglob("*.xml")):
        return [snap]
    return [Path(root) / rel for rel in REPORT_LIVE]


def execution_cases(root: Path) -> list[dict[str, Any]]:
    """Every ``<testcase>`` of every report, as
    {classname, name, skipped, failed, report}. Raises Unreadable on XML that
    exists and does not parse."""
    cases: list[dict[str, Any]] = []
    for directory in report_dirs(root):
        if not directory.is_dir():
            continue
        for p in sorted(directory.rglob("*.xml")):
            try:
                tree = ET.parse(p)
            except ET.ParseError as exc:
                raise Unreadable("%s is not XML: %s" % (p.name, exc)) from exc
            for tc in tree.getroot().iter("testcase"):
                failed = any(tc.find(tag) is not None for tag in ("failure", "error"))
                cases.append({
                    "classname": str(tc.get("classname") or ""),
                    "name": str(tc.get("name") or ""),
                    "skipped": tc.find("skipped") is not None,
                    "failed": failed,
                    "report": p.relative_to(root).as_posix(),
                })
    return cases


def surefire_summary(root: Path) -> dict[str, Any] | None:
    """``verification/build/surefire.json``: did a test phase run, and which
    classes did it report red? It carries no roster of what PASSED."""
    p = Path(root) / SUREFIRE_JSON
    if not p.is_file():
        return None
    doc = _load_json(p)
    if not isinstance(doc, dict) or str(doc.get("schema") or "") != SUREFIRE_SCHEMA:
        raise Unreadable("%s is not a %s document" % (SUREFIRE_JSON, SUREFIRE_SCHEMA))
    red = sorted({str(f.get("classname") or "") for f in (doc.get("failures") or []) if isinstance(f, dict)})
    ran = bool(doc.get("ran")) or int(doc.get("tests") or 0) > 0 or bool(doc.get("failures"))
    return {"ran": ran, "tests": int(doc.get("tests") or 0), "reports": int(doc.get("reports") or 0), "red_classes": [c for c in red if c]}


def executed_product_cases(root: Path, sources: dict[str, str]) -> dict[str, Any]:
    """Split the execution records against the product test sources of THIS
    tree. ``clean`` is what may count as product acceptance."""
    cases = execution_cases(root)
    summary = surefire_summary(root)
    red = set((summary or {}).get("red_classes") or [])
    clean: list[dict[str, Any]] = []
    skipped: list[str] = []
    failed: list[str] = []
    unbound: list[str] = []
    for c in cases:
        cls = c["classname"]
        label = "%s#%s" % (cls, c["name"])
        if cls not in sources:
            unbound.append(label)
            continue
        if c["skipped"]:
            skipped.append(label)
        elif c["failed"] or cls in red:
            failed.append(label)
        else:
            clean.append(c)
    return {
        "cases": cases,
        "summary": summary,
        "clean": clean,
        "skipped": sorted(skipped),
        "failed": sorted(failed),
        "unbound": sorted(unbound),
        "classes": sorted({c["classname"] for c in clean}),
    }


# ---------------------------------------------------------------------------
# declared capabilities
# ---------------------------------------------------------------------------


def declared_capabilities(root: Path) -> dict[str, Any]:
    """The qualified scenarios of this tree, as capabilities.

    The corpus is the roster (id, entry point, method, path) and names its own
    provenance; the qualification says which of them the SOURCE actually
    demonstrated. Provenance binding is the corpus gate's job, not this
    floor's -- what is read here is the roster and the verdicts."""
    corpus_p, qual_p = Path(root) / CORPUS, Path(root) / QUALIFICATION
    out: dict[str, Any] = {"capabilities": [], "reason": "", "provenance": "", "corpus_sha256": "", "unqualified": []}
    if not corpus_p.is_file():
        out["reason"] = "no %s in this tree" % CORPUS
        return out
    corpus = _load_json(corpus_p)
    if not isinstance(corpus, dict) or str(corpus.get("schema") or "") != CORPUS_SCHEMA:
        raise Unreadable("%s is not a %s document" % (CORPUS, CORPUS_SCHEMA))
    derived = corpus.get("derived_from")
    out["provenance"] = (
        "derived by %s" % str((derived or {}).get("producer") or "an unnamed producer")
        if isinstance(derived, dict) and not corpus.get("approved_by")
        else "authored by %s" % str(corpus.get("approved_by") or "an unnamed author")
    )
    roster = {}
    for sc in corpus.get("scenarios") or []:
        if isinstance(sc, dict) and str(sc.get("id") or "").strip():
            roster[str(sc["id"])] = {
                "scenario": str(sc["id"]),
                "entry_point": str(sc.get("entry_point") or ""),
                "method": str(sc.get("method") or ""),
                "path": str(sc.get("path") or ""),
            }
    if not roster:
        out["reason"] = "%s declares no scenario" % CORPUS
        return out
    if not qual_p.is_file():
        out["reason"] = "%s declares %d scenario(s) and none is qualified: %s is not in this tree" % (CORPUS, len(roster), QUALIFICATION)
        out["unqualified"] = sorted(roster)
        return out
    qual = _load_json(qual_p)
    if not isinstance(qual, dict) or str(qual.get("schema") or "") != QUALIFICATION_SCHEMA:
        raise Unreadable("%s is not a %s document" % (QUALIFICATION, QUALIFICATION_SCHEMA))
    out["corpus_sha256"] = str(qual.get("corpus_sha256") or "")
    records = qual.get("scenarios") if isinstance(qual.get("scenarios"), dict) else {}
    caps = []
    unqualified = []
    for sid in sorted(roster):
        rec = records.get(sid) if isinstance(records, dict) else None
        capability = str((rec or {}).get("capability") or (rec or {}).get("verdict") or "")
        if capability == "PASS":
            caps.append(dict(roster[sid], capability=capability))
        else:
            unqualified.append("%s (%s)" % (sid, capability or "no qualification record"))
    out["capabilities"] = caps
    out["unqualified"] = unqualified
    if not caps:
        out["reason"] = "%s qualifies no scenario PASS (%d scenario(s): %s)" % (QUALIFICATION, len(roster), ", ".join(unqualified[:6]))
    return out


# ---------------------------------------------------------------------------
# coverage
# ---------------------------------------------------------------------------


def generated_manifest(root: Path, corpus_sha256: str = "") -> dict[str, Any]:
    """The generated-test manifest, or an empty one. ABSENCE IS NOT AN ERROR:
    it means there is no generated coverage yet."""
    p = Path(root) / GENERATED_MANIFEST
    if not p.is_file():
        return {"present": False, "cases": [], "gap": ""}
    doc = _load_json(p)
    if not isinstance(doc, dict) or str(doc.get("schema") or "") != GENERATED_SCHEMA:
        raise Unreadable("%s is not a %s document" % (GENERATED_MANIFEST, GENERATED_SCHEMA))
    cases = [
        {"scenario": str(c.get("scenario") or ""), "class": str(c.get("class") or ""),
         "method": str(c.get("method") or ""), "entry_point": str(c.get("entry_point") or "")}
        for c in (doc.get("cases") or []) if isinstance(c, dict)
    ]
    manifest_sha = str(doc.get("corpus_sha256") or "")
    gap = ""
    if corpus_sha256 and manifest_sha and manifest_sha != corpus_sha256:
        gap = ("%s was generated from corpus %s and this tree qualifies corpus %s; its cases prove nothing about these capabilities"
               % (GENERATED_MANIFEST, manifest_sha[:12], corpus_sha256[:12]))
        cases = []
    return {"present": True, "cases": cases, "gap": gap, "corpus_sha256": manifest_sha}


def names_scenario(scenario: str, classname: str, method: str) -> bool:
    """Does this executed case NAME the scenario? Normalised comparison over
    the simple class name and the method; the local part after the last ``:``
    counts only when it is long enough not to match by accident."""
    blob = _norm("%s#%s" % (str(classname).rsplit(".", 1)[-1], method))
    if not blob:
        return False
    full = _norm(scenario)
    if full and full in blob:
        return True
    local = _norm(str(scenario).rsplit(":", 1)[-1]) if ":" in str(scenario) else ""
    return bool(local and len(local) >= MIN_LOCAL_PART and local in blob)


def coverage(capabilities: list[dict[str, Any]], clean: list[dict[str, Any]], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Per capability: covered by a generated case, by a retained one, or not
    at all. A manifest case counts only when it executed cleanly."""
    executed = {(c["classname"], c["name"]) for c in clean}
    executed_classes = {c["classname"] for c in clean}
    manifest_by_scenario: dict[str, list[dict[str, Any]]] = {}
    for c in manifest.get("cases") or []:
        manifest_by_scenario.setdefault(c["scenario"], []).append(c)
    rows: list[dict[str, Any]] = []
    for cap in capabilities:
        sid = cap["scenario"]
        gen = [
            c for c in manifest_by_scenario.get(sid) or []
            if (c["class"], c["method"]) in executed or (not c["method"] and c["class"] in executed_classes)
        ]
        ret = [c for c in clean if names_scenario(sid, c["classname"], c["name"])]
        rows.append(dict(
            cap,
            covered_by="generated" if gen else ("retained" if ret else ""),
            cases=sorted({"%s#%s" % (c["class"], c["method"]) for c in gen} | {"%s#%s" % (c["classname"], c["name"]) for c in ret}),
            declared_generated=sorted({"%s#%s" % (c["class"], c["method"]) for c in manifest_by_scenario.get(sid) or []}),
        ))
    return rows


# ---------------------------------------------------------------------------
# the floor
# ---------------------------------------------------------------------------


def _fail(msg: str) -> int:
    print("FAIL: AR-2.8 " + msg, file=sys.stderr)
    return 1


def _ar28(root: Path, require_coverage: bool) -> int:
    try:
        sources = product_test_sources(root)
        harness = harness_test_sources(root)
        run = executed_product_cases(root, sources)
        declared = declared_capabilities(root)
        manifest = generated_manifest(root, declared["corpus_sha256"])
    except Unreadable as exc:
        print("FAIL: AR-2.8 unreadable evidence: %s" % exc, file=sys.stderr)
        return 2

    if not sources and not harness:
        return _fail("no *Test.java/*Tests.java/*IT.java under %s — product acceptance is empty"
                     % " or ".join(r.as_posix() for r in test_roots(root)))
    if not sources:
        rc = _fail("probe-only tests (%s) — REFUSE as product acceptance (pair AR-3.6)" % HARNESS_PREFIX.replace("/", "."))
        for p in harness[:20]:
            print("  probe_test: %s" % p, file=sys.stderr)
        return rc

    summary = run["summary"]
    if not run["cases"]:
        where = ", ".join(d.name for d in report_dirs(root))
        if summary and summary["ran"]:
            return _fail(
                "%s says a test phase ran (%d case(s) in %d report(s)) and no per-case report is in this tree (%s). "
                "That summary names failures only, never what passed, so no execution can be bound to a test source: "
                "keep the surefire/failsafe XML, or the %s snapshot, and measure again."
                % (SUREFIRE_JSON, summary["tests"], summary["reports"], where, REPORT_SNAPSHOT.as_posix()))
        return _fail(
            "%d product test source(s) and NO execution record (%s, %s): a test that compiles and never runs is not acceptance."
            % (len(sources), where, SUREFIRE_JSON.as_posix()))

    if not run["clean"]:
        detail = []
        if run["failed"]:
            detail.append("%d failed/errored (%s)" % (len(run["failed"]), ", ".join(run["failed"][:3])))
        if run["skipped"]:
            detail.append("%d skipped (%s) — a skipped case is not a passed case" % (len(run["skipped"]), ", ".join(run["skipped"][:3])))
        if run["unbound"]:
            detail.append("%d executed case(s) belong to no test source of this tree (%s)" % (len(run["unbound"]), ", ".join(run["unbound"][:3])))
        return _fail("no executed product test case is clean and bound to this tree: " + ("; ".join(detail) or "no case named a product test source"))

    caps = declared["capabilities"]
    executed_note = "%d clean case(s) in %d product test class(es): %s" % (
        len(run["clean"]), len(run["classes"]), ", ".join(c.rsplit(".", 1)[-1] for c in run["classes"][:6]))

    if not caps:
        print("OK: AR-2.8 %s" % executed_note)
        print("N/A: AR-2.8 capability coverage — %s (not idle: the floor demands only what this tree's evidence declares)"
              % (declared["reason"] or "no qualified scenario capability"))
        if manifest.get("gap"):
            print("  manifest: %s" % manifest["gap"])
        return 0

    rows = coverage(caps, run["clean"], manifest)
    covered = [r for r in rows if r["covered_by"]]
    uncovered = [r for r in rows if not r["covered_by"]]

    def _report(stream: Any) -> None:
        print("  corpus: %d qualified capability(ies), %s" % (len(caps), declared["provenance"]), file=stream)
        print("  executed: %s" % executed_note, file=stream)
        if manifest.get("gap"):
            print("  manifest: %s" % manifest["gap"], file=stream)
        elif not manifest.get("present"):
            print("  manifest: no %s — no generated coverage (absence is not an error)" % GENERATED_MANIFEST.as_posix(), file=stream)
        for r in rows:
            if r["covered_by"]:
                print("  %s: %s (%s)" % (r["scenario"], r["covered_by"], r["cases"][0]), file=stream)
            else:
                print("  %s: UNCOVERED (%s %s)%s" % (
                    r["scenario"], r["method"] or "?", r["path"] or r["entry_point"] or "?",
                    " — declared generated %s, which did not execute cleanly" % ", ".join(r["declared_generated"]) if r["declared_generated"] else ""),
                    file=stream)

    if not covered:
        rc = _fail(
            "no executed product test covers ANY declared capability: %d uncovered (%s). "
            "The executed suite (%s) proves what it tests and nothing about these capabilities."
            % (len(uncovered), ", ".join(r["scenario"] for r in uncovered), executed_note))
        _report(sys.stderr)
        return rc

    if uncovered and require_coverage:
        rc = _fail("--require-coverage: %d of %d capability(ies) uncovered: %s"
                   % (len(uncovered), len(rows), ", ".join(r["scenario"] for r in uncovered)))
        _report(sys.stderr)
        return rc

    print("OK: AR-2.8 %d of %d declared capability(ies) covered by executed product tests%s"
          % (len(covered), len(rows), "" if require_coverage else " (--require-coverage off)"))
    _report(sys.stdout)
    if uncovered:
        print("GAP: AR-2.8 %d capability(ies) uncovered: %s (not idle: named, and --require-coverage refuses them)"
              % (len(uncovered), ", ".join(r["scenario"] for r in uncovered)))
    if declared["unqualified"]:
        print("N/A: AR-2.8 %d scenario(s) the source did not qualify, so not demanded: %s"
              % (len(declared["unqualified"]), ", ".join(declared["unqualified"][:6])))
    return 0


def _emit_gate_receipt(root: Path, rc: int) -> None:
    hit = (
        Path(__file__).resolve().parents[2]
        / "assert-pinned-gates-ran"
        / "scripts"
        / "script_gate_receipt.py"
    )
    spec = importlib.util.spec_from_file_location("script_gate_receipt", hit)
    if spec is None or spec.loader is None:
        print("FAIL: script_gate_receipt.py missing", file=sys.stderr)
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    argv = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    mod.emit_script_receipt(root, "check-domain-parity", rc, __file__, argv)


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--require-coverage",
        action="store_true",
        help="refuse when ANY declared capability is uncovered (default: refuse only when none is)",
    )
    ap.add_argument(
        "--write-receipt",
        nargs="?",
        const="gates",
        default=None,
        help="Write evidence/receipts/gates/check-domain-parity.json (runner schema)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    rc = _ar28(root, args.require_coverage)
    if args.write_receipt is not None:
        _emit_gate_receipt(root, rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
