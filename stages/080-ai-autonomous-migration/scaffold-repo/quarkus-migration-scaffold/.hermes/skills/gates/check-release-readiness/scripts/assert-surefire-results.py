#!/usr/bin/env python3
"""Refuse M4 when the test evidence is absent, red, skipped, or about a tree
that is not this one -- and say WHAT the evidence shows when it refuses.

Lead:m4-must-read-test-results-not-test-files -- dest-5 M4 discussed
HealthTest 19x and never opened target/surefire-reports (Failures: 1).
Parse XML. Fail closed when no report exists. Prefer the pre-rebuild
snapshot so a later mvn clean cannot hide the result.

Three further refusals, because "the reports are green" is a weaker claim than
it looks (pilot v7):

  * a skipped case is not a passed case. Zero failures over zero executions is
    the same silence as no report at all, and @Disabled reads as green here.
  * at least one executed case must belong to a test source that exists in one
    of this destination's test roots. Reports left by another tree, or by
    sources an ADR has since retired, prove nothing about what ships.
  * a test source in the tree that the reports never name is reported, because
    a test that compiles and never runs is the failure mode this gate exists
    for. Sources with no executable cases (abstract bases, test configuration)
    are named too -- the point is that the set is stated, never assumed.

EVIDENCE-BASED DIAGNOSIS (ADR-015, architect ruling 2026-09-15)
  On v9 this gate refused with "no testsuite element" because it read
  ``failsafe-summary.xml`` -- a PHASE SUMMARY, not a test report -- as a
  malformed report. A summary that records an integration phase with nothing
  to run is not a defect in itself; whether it is one depends on evidence this
  script can read. So the verdict now names the phase, the files it read and
  the counts it found, in four distinguishable states:

TWO TEST ROOTS (ADR-015)
  The tree's test sources do not all live in ``src/test/java``. The generated
  parity suite lives in the root the generated manifest's ``out`` names
  (default ``src/parity-test/java``), which nothing compiles but the
  harness-owned ``m4-parity`` profile. This floor paired phases against
  ``src/test/java`` alone, so a tree whose only tests are the generated suite
  read as a tree with no test source at all: every generated execution was
  unbound and the phase was misdiagnosed as legitimately empty. The roots are
  now the SAME PAIR the product-tests floor measures -- ``test_roots`` /
  ``generated_test_root`` of
  ``check-domain-parity/scripts/check-product-tests.py``, imported from that
  file so the two floors cannot drift apart (that module defines only
  constants and functions at import time; its ``main`` is under
  ``__main__``). If it is ever unimportable, the same manifest read is
  reimplemented here and the verdict SAYS SO on its ``test roots:`` line.
  A generated case's report is bound, counted and named exactly like a
  retained one: the root a source sits in is not evidence about it.

  (a) NO TEST SOURCE for that phase in EITHER root -- surefire owns
      ``*Test.java`` / ``*Tests.java``, failsafe owns ``*IT.java`` -- and no
      report for it.
      The phase is legitimately empty and is reported as such
      ("empty failsafe phase; surefire executed N case(s)"). It is
      INFORMATIONAL, never a refusal on its own: the refusal for an empty
      suite belongs to the case below, which is exactly the condition under
      which the other floor (``check-domain-parity/scripts/check-product-tests.py``,
      AR-2.8) would also count zero executed cases -- no executed, clean case
      bound to a test source of this tree. One empty phase beside a phase that
      executed cases is not that condition.
  (b) SOURCES EXIST for the phase and NO REPORT was produced: the build
      skipped tests (``-DskipTests`` / ``maven.test.skip`` / ``skipITs``) or the
      plugin never ran. REFUSE, naming the sources and the cause the evidence
      shows -- a skip property in ``pom.xml``, a skip marker in a build log,
      the ``failureMessage`` of the phase summary, or
      ``verification/build/surefire.json`` recording a phase that ran and left
      no per-case report. When nothing in the files read names a cause, the
      refusal says so and lists the files it read.
  (c) REPORTS EXIST with failures, errors or skips: REFUSE, naming them per
      case (``class#method``) with the report each came from.
  (d) REPORTS EXIST and all are clean: PASS with the counts, per phase.

  Every claim is bound to the files it was read from: the report directories,
  the XML file count per kind, the test-source roots and their counts.

EXIT CODES
  0  the evidence is clean: at least one executed case, none skipped, none
     failed, at least one bound to a test source of this tree (or neither test
     root holds a source at all, which is stated with both root names). Empty
     phases are printed.
  1  a refusal: no XML to read; a red or skipped case; a phase with sources and
     no report; reports with no executed case; no executed case belonging to
     this tree.
  2  evidence that exists and cannot be read: XML that does not parse, or an
     XML root element that is neither a test suite nor a phase summary.
     Unreadable is never silently green.

Output is on stderr (the runner ``run-m4-pre-verdict.sh`` prints its own line
on stdout).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SNAP = Path("evidence") / "m4-pre-rebuild" / "test-reports"
TEST_ROOT = Path("src") / "test" / "java"
# The generated parity suite's root, when no manifest names another (ADR-015).
GENERATED_TEST_ROOT = Path("src") / "parity-test" / "java"
GENERATED_MANIFEST = Path("evidence") / "tests" / "generated-manifest.json"
SUREFIRE_JSON = Path("verification") / "build" / "surefire.json"
SUREFIRE_SCHEMA = "rhoai3.surefire/v1"
# The product-tests floor owns the roots; this floor must measure the same two.
PRODUCT_TESTS = (
    Path(__file__).resolve().parents[2] / "check-domain-parity" / "scripts" / "check-product-tests.py"
)

# phase name -> (test-source suffixes it owns, live report directory)
PHASES = (
    ("surefire", ("Test.java", "Tests.java"), Path("target") / "surefire-reports"),
    ("failsafe", ("IT.java",), Path("target") / "failsafe-reports"),
)
LIVE = tuple(rel for _, _, rel in PHASES)

# Build-log markers that name a skipped test phase. Text is quoted back with
# the file and line it was read from; nothing is inferred from a marker's
# absence beyond "the files read name no cause".
SKIP_MARKERS = (
    "-DskipTests",
    "-Dmaven.test.skip",
    "-DskipITs",
    "maven.test.skip",
    "Tests are skipped",
    "No tests to run",
    "Skipping execution of surefire",
    "Skipping execution of failsafe",
    "No tests were executed",
)
POM_SKIP = re.compile(r"<(skipTests|skipITs|maven\.test\.skip)>\s*true\s*</\1>", re.I)
LOG_GLOBS = ("*.log", "evidence/*.log", "evidence/*/*.log", "target/*.log")
MAX_LOGS = 20
MAX_LOG_BYTES = 512 * 1024


class Unreadable(ValueError):
    """Evidence that exists and cannot be read: exit 2, never a quiet pass."""


def _fail(msg: str, detail: list[str] | None = None) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    for line in detail or []:
        print("  " + line, file=sys.stderr)
    return 1


def _local(tag: str) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def iter_xml(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*.xml") if p.is_file())


def report_dirs(root: Path) -> list[Path]:
    """The pre-rebuild snapshot when it holds XML, otherwise the live dirs."""
    snap = root / SNAP
    if iter_xml(snap):
        return [snap]
    return [root / rel for rel in LIVE]


# ---------------------------------------------------------------------------
# the tree: which test roots exist, and which test sources each phase owns
# ---------------------------------------------------------------------------


def _product_tests_module():
    """``check-product-tests.py``, loaded for the two functions that decide the
    test roots. Executing it defines constants, classes and functions only --
    its ``main`` runs under ``__main__`` -- so there is no side effect to
    inherit. Returns None when it cannot be loaded; the caller then reads the
    manifest itself and the verdict says which of the two happened."""
    try:
        spec = importlib.util.spec_from_file_location("check_product_tests", PRODUCT_TESTS)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not (hasattr(mod, "test_roots") and hasattr(mod, "generated_test_root")):
            return None
        return mod
    except Exception:  # an unloadable neighbour must not take this gate with it
        return None


_PRODUCT_TESTS = _product_tests_module()
ROOTS_FROM = (
    "roots per check-domain-parity/scripts/check-product-tests.py"
    if _PRODUCT_TESTS is not None
    else "roots reimplemented here: check-domain-parity/scripts/check-product-tests.py "
         "could not be imported, so %s was read by this script" % GENERATED_MANIFEST.as_posix()
)


def generated_test_root(root: Path) -> Path:
    """The root the harness generated its parity cases into, as the manifest's
    ``out`` says (default ``src/parity-test/java``). A manifest that cannot be
    read does not decide the root here."""
    if _PRODUCT_TESTS is not None:
        return Path(_PRODUCT_TESTS.generated_test_root(Path(root)))
    p = Path(root) / GENERATED_MANIFEST
    if not p.is_file():
        return GENERATED_TEST_ROOT
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return GENERATED_TEST_ROOT
    out = str(doc.get("out") or "") if isinstance(doc, dict) else ""
    return Path(out) if out else GENERATED_TEST_ROOT


def test_roots(root: Path) -> list[Path]:
    """The loop's test root and the generated parity root, in that order, with
    no duplicate when a tree declares them the same."""
    if _PRODUCT_TESTS is not None:
        return [Path(r) for r in _PRODUCT_TESTS.test_roots(Path(root))]
    seen: list[Path] = []
    for rel in (TEST_ROOT, generated_test_root(root)):
        if rel not in seen:
            seen.append(rel)
    return seen


def roots_label(root: Path) -> str:
    """Both roots, named, for every line that claims a source is or is not
    there. An absence is about the places it was looked for."""
    return " or ".join(rel.as_posix() for rel in test_roots(root))


def roots_line(root: Path) -> str:
    return "test roots: %s (%s)" % (
        ", ".join(rel.as_posix() for rel in test_roots(root)), ROOTS_FROM)


def _sources(root: Path, suffixes: tuple[str, ...] | None) -> dict[str, str]:
    """{dotted class name: path relative to root} over BOTH test roots. A
    generated source is indexed exactly like a retained one."""
    out: dict[str, str] = {}
    for rel in test_roots(root):
        base = root / rel
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.java")):
            if suffixes is not None and not p.name.endswith(suffixes):
                continue
            out[p.relative_to(base).with_suffix("").as_posix().replace("/", ".")] = _rel(root, p)
    return out


def test_sources(root: Path) -> dict[str, str]:
    return _sources(root, None)


def phase_sources(root: Path, suffixes: tuple[str, ...]) -> dict[str, str]:
    return _sources(root, suffixes)


# ---------------------------------------------------------------------------
# the reports: suites, phase summaries, and what neither of those is
# ---------------------------------------------------------------------------


def read_xml(path: Path) -> dict:
    """One XML file, classified by what it actually is.

    kind ``suite``   -- surefire/failsafe per-case report (``testsuite``).
    kind ``summary`` -- a phase summary (``failsafe-summary``): counts only,
                        no per-case roster.
    Anything else raises Unreadable: an unrecognised root element is evidence
    that cannot be read, not a green.
    """
    try:
        tree = ET.parse(path)
    except (OSError, ET.ParseError) as exc:
        raise Unreadable("%s could not be parsed as XML: %s" % (path, exc)) from exc
    root_el = tree.getroot()
    tag = _local(root_el.tag)
    suites = [el for el in root_el.iter() if _local(el.tag) == "testsuite"]
    if tag == "testsuite":
        suites = [root_el] + [el for el in suites if el is not root_el]
    if suites:
        tests = failures = errors = skipped_attr = 0
        for suite in suites:
            tests += int(suite.attrib.get("tests") or 0)
            failures += int(suite.attrib.get("failures") or 0)
            errors += int(suite.attrib.get("errors") or 0)
            skipped_attr += int(suite.attrib.get("skipped") or 0)
        cases = []
        for tc in root_el.iter():
            if _local(tc.tag) != "testcase":
                continue
            status, message = "executed", ""
            for child in tc:
                name = _local(child.tag)
                if name in ("failure", "error"):
                    status = name
                    message = str(child.get("message") or (child.text or "").strip().split("\n")[0])
                    break
                if name == "skipped":
                    status = "skipped"
                    message = str(child.get("message") or "")
                    break
            cases.append({
                "classname": str(tc.get("classname") or ""),
                "name": str(tc.get("name") or ""),
                "status": status,
                "message": message,
            })
        return {
            "kind": "suite", "path": path, "tests": tests, "failures": failures,
            "errors": errors, "skipped_attr": skipped_attr, "cases": cases,
        }
    if tag.endswith("summary"):
        got = {}
        for child in root_el:
            got[_local(child.tag)] = (child.text or "").strip()
        return {
            "kind": "summary", "path": path, "root_tag": tag,
            "completed": int(got.get("completed") or 0),
            "failures": int(got.get("failures") or 0),
            "errors": int(got.get("errors") or 0),
            "skipped": int(got.get("skipped") or 0),
            "message": got.get("failureMessage") or "",
            "result": str(root_el.get("result") or ""),
        }
    raise Unreadable(
        "%s has root element <%s>, which is neither a test suite nor a phase summary "
        "(a surefire/failsafe report is <testsuite>; a phase summary is <*-summary>)"
        % (path, tag)
    )


def phase_of(root: Path, path: Path) -> str:
    """Which phase a report belongs to, from the directory it was read in.

    Live: target/surefire-reports, target/failsafe-reports. Snapshot:
    evidence/m4-pre-rebuild/test-reports/<surefire|failsafe>/ (written by
    snapshot-m4-test-reports.py)."""
    blob = _rel(root, path).lower()
    if "failsafe" in blob:
        return "failsafe"
    if "surefire" in blob:
        return "surefire"
    return ""


# ---------------------------------------------------------------------------
# what the build says about a phase that produced nothing
# ---------------------------------------------------------------------------


def _read_tail(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return data[-MAX_LOG_BYTES:].decode("utf-8", "replace")


def candidate_logs(root: Path, explicit: list[Path]) -> list[Path]:
    seen: list[Path] = []
    for p in list(explicit) + [q for pat in LOG_GLOBS for q in sorted(root.glob(pat))]:
        if p.is_file() and p not in seen:
            seen.append(p)
        if len(seen) >= MAX_LOGS:
            break
    return seen


def skip_evidence(root: Path, logs: list[Path]) -> tuple[list[str], list[str]]:
    """(causes found, files read). Every cause quotes its file."""
    causes: list[str] = []
    read: list[str] = []

    pom = root / "pom.xml"
    if pom.is_file():
        read.append("pom.xml")
        try:
            for hit in POM_SKIP.finditer(pom.read_text(encoding="utf-8", errors="replace")):
                causes.append("pom.xml declares <%s>true</%s>" % (hit.group(1), hit.group(1)))
        except OSError:
            pass

    sf = root / SUREFIRE_JSON
    if sf.is_file():
        read.append(SUREFIRE_JSON.as_posix())
        try:
            doc = json.loads(sf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            causes.append("%s could not be read: %s" % (SUREFIRE_JSON.as_posix(), exc))
            doc = None
        if isinstance(doc, dict):
            if str(doc.get("schema") or "") != SUREFIRE_SCHEMA:
                causes.append("%s is not a %s document" % (SUREFIRE_JSON.as_posix(), SUREFIRE_SCHEMA))
            elif doc.get("ran") or int(doc.get("tests") or 0) > 0:
                causes.append(
                    "%s records a test phase that RAN (tests=%d, reports=%d) and left no per-case report here"
                    % (SUREFIRE_JSON.as_posix(), int(doc.get("tests") or 0), int(doc.get("reports") or 0))
                )
            else:
                causes.append(
                    "%s records ran=%s tests=%d — the phase did not run"
                    % (SUREFIRE_JSON.as_posix(), bool(doc.get("ran")), int(doc.get("tests") or 0))
                )

    for log in candidate_logs(root, logs):
        read.append(_rel(root, log))
        text = _read_tail(log)
        for number, line in enumerate(text.splitlines(), 1):
            if any(marker in line for marker in SKIP_MARKERS):
                causes.append("%s:%d: %s" % (_rel(root, log), number, line.strip()[:160]))
                break
    return causes, read


# ---------------------------------------------------------------------------
# the diagnosis
# ---------------------------------------------------------------------------


def _diagnose(root: Path, logs: list[Path]) -> int:
    dirs = report_dirs(root)
    where = ", ".join(_rel(root, d) for d in dirs)
    files: list[Path] = []
    for directory in dirs:
        files.extend(iter_xml(directory))

    sources = test_sources(root)
    # Where each phase WOULD have left a report, given what is being read:
    # the snapshot's per-phase folder when the snapshot is in use, otherwise
    # the live directory. A claim about an absent report names the place the
    # absence was observed.
    snapshot_used = len(dirs) == 1 and dirs[0] == root / SNAP
    searched = {
        name: (SNAP / name).as_posix() if snapshot_used else rel.as_posix()
        for name, _, rel in PHASES
    }
    per_phase = {
        name: {
            "sources": phase_sources(root, suffixes),
            "suffixes": ", ".join("*" + s for s in suffixes),
            "suites": [],
            "summaries": [],
            "cases": [],
        }
        for name, suffixes, _ in PHASES
    }
    unclassified: list[dict] = []

    # (b) with nothing at all to read: no XML anywhere is the fail-closed case.
    if not files:
        causes, read = skip_evidence(root, logs)
        detail = [
            "read: %s (no XML); for cause: %s" % (where, ", ".join(read) or "no build log"),
            roots_line(root),
        ]
        detail += ["cause: " + c for c in causes] or ["cause: the files read name none"]
        if sources:
            return _fail(
                "%d test source(s) under %s and no surefire/failsafe XML under %s — fail closed: "
                "a test that compiles and never runs is not evidence"
                % (len(sources), roots_label(root), where),
                detail + ["source: %s" % s for s in sorted(sources.values())[:8]],
            )
        return _fail(
            "no surefire/failsafe XML under %s and no test source under %s — fail closed "
            "(nothing was executed, nothing was read)" % (where, roots_label(root)),
            detail,
        )

    for path in files:
        doc = read_xml(path)  # raises Unreadable -> exit 2
        name = phase_of(root, path)
        bucket = per_phase.get(name)
        if bucket is None:
            unclassified.append(doc)
            continue
        bucket["summaries" if doc["kind"] == "summary" else "suites"].append(doc)
        if doc["kind"] == "suite":
            bucket["cases"].extend(doc["cases"])

    def _cases(status: str) -> list[tuple[str, str, str, str]]:
        out = []
        for name, _, _ in PHASES:
            for doc in per_phase[name]["suites"]:
                for case in doc["cases"]:
                    if case["status"] == status:
                        out.append((name, "%s.%s" % (case["classname"], case["name"]),
                                    _rel(root, doc["path"]), case["message"]))
        for doc in unclassified:
            for case in doc.get("cases") or []:
                if case["status"] == status:
                    out.append(("(unclassified)", "%s.%s" % (case["classname"], case["name"]),
                                _rel(root, doc["path"]), case["message"]))
        return sorted(out)

    suite_docs = [d for name, _, _ in PHASES for d in per_phase[name]["suites"]] + [
        d for d in unclassified if d["kind"] == "suite"
    ]
    tests = sum(d["tests"] for d in suite_docs)
    failures = sum(d["failures"] for d in suite_docs)
    errors = sum(d["errors"] for d in suite_docs)
    red = _cases("failure") + _cases("error")
    skipped = _cases("skipped")
    executed = [
        (case["classname"], case["name"])
        for d in suite_docs for case in d["cases"] if case["status"] == "executed"
    ]

    read_line = "read: %s — %d suite report(s), %d phase summary(ies)" % (
        where, len(suite_docs), sum(1 for name, _, _ in PHASES for _ in per_phase[name]["summaries"]))
    root_line = roots_line(root)
    phase_lines = []
    for name, _, rel in PHASES:
        bucket = per_phase[name]
        phase_lines.append(
            "%s: %d source(s) (%s), %d report(s), %d executed, %d skipped, %d failed/errored"
            % (name, len(bucket["sources"]), bucket["suffixes"], len(bucket["suites"]),
               sum(1 for c in bucket["cases"] if c["status"] == "executed"),
               sum(1 for c in bucket["cases"] if c["status"] == "skipped"),
               sum(1 for c in bucket["cases"] if c["status"] in ("failure", "error")))
        )

    # (c) reports exist and are red, or carry skips: name them per case.
    if failures > 0 or errors > 0 or red:
        detail = [read_line, root_line] + phase_lines
        detail += ["%s %s (%s)%s" % (phase, case, report, ": " + msg if msg else "")
                   for phase, case, report, msg in red[:20]]
        return _fail(
            "surefire/failsafe Failures=%d Errors=%d Tests=%d in %d report(s): %d case(s) red"
            % (failures, errors, tests, len(suite_docs), len(red) or failures + errors),
            detail,
        )
    if skipped:
        detail = [read_line, root_line] + phase_lines
        detail += ["%s %s (%s)%s" % (phase, case, report, ": " + msg if msg else "")
                   for phase, case, report, msg in skipped[:20]]
        return _fail(
            "%d skipped case(s) — a skipped case is not a passed case: %s"
            % (len(skipped), ", ".join(c for _, c, _, _ in skipped[:5])),
            detail,
        )

    # (b) a phase whose sources exist and whose reports do not.
    for name, _, rel in PHASES:
        bucket = per_phase[name]
        if bucket["suites"] or not bucket["sources"]:
            continue
        causes, files_read = skip_evidence(root, logs)
        for summary in bucket["summaries"]:
            causes.append(
                "%s reports completed=%d failures=%d errors=%d skipped=%d%s"
                % (_rel(root, summary["path"]), summary["completed"], summary["failures"],
                   summary["errors"], summary["skipped"],
                   " — %s" % summary["message"] if summary["message"] else "")
            )
            files_read.append(_rel(root, summary["path"]))
        detail = [read_line, root_line] + phase_lines
        detail.append("read for cause: %s" % (", ".join(files_read) or "no build log, no phase summary"))
        detail += ["cause: " + c for c in causes] or [
            "cause: the files read name none — the phase was skipped or its plugin never ran"
        ]
        detail += ["source: %s" % p for p in sorted(bucket["sources"].values())[:8]]
        return _fail(
            "%d %s test source(s) (%s) and no %s report under %s: the phase produced no evidence"
            % (len(bucket["sources"]), name, bucket["suffixes"], name, searched[name]),
            detail,
        )

    # No executed case anywhere: the empty-suite refusal AR-2.8 also makes.
    if not executed:
        detail = [read_line, root_line] + phase_lines
        for name, _, _ in PHASES:
            for summary in per_phase[name]["summaries"]:
                detail.append("%s reports completed=%d%s" % (
                    _rel(root, summary["path"]), summary["completed"],
                    " — %s" % summary["message"] if summary["message"] else ""))
        return _fail(
            "%d report(s) and no executed case — zero failures over zero executions is not evidence"
            % len(suite_docs),
            detail,
        )

    # (a) an empty phase is informational once another phase executed cases.
    empty_notes = []
    for name, _, rel in PHASES:
        bucket = per_phase[name]
        if bucket["suites"] or bucket["sources"]:
            continue
        other = ", ".join(
            "%s executed %d case(s)" % (o, sum(1 for c in per_phase[o]["cases"] if c["status"] == "executed"))
            for o, _, _ in PHASES if o != name
        )
        summary_note = "; ".join(
            "%s reports completed=%d" % (_rel(root, s["path"]), s["completed"])
            for s in bucket["summaries"]
        )
        empty_notes.append(
            "empty %s phase — no %s under %s and no report under %s%s; %s"
            % (name, bucket["suffixes"], roots_label(root), searched[name],
               " (%s)" % summary_note if summary_note else "", other)
        )

    sources_note = sorted(sources)
    if sources_note:
        mine = sorted({c for c, _ in executed if c in sources})
        if not mine:
            detail = [read_line, root_line] + phase_lines + empty_notes
            return _fail(
                "no executed case belongs to a test source in this tree; the reports name %s "
                "while %s holds %s"
                % (", ".join(sorted({c for c, _ in executed})[:3]), roots_label(root),
                   ", ".join(sources_note[:3])),
                detail,
            )
        silent = sorted(set(sources_note) - {c for c, _ in executed})
        print(
            "OK: surefire-results (Failures=0 Errors=0 Skipped=0 Tests=%d reports=%d; executed from this tree: %s%s)"
            % (tests, len(suite_docs), ", ".join(mine),
               ("; no case named for %s" % ", ".join(silent)) if silent else ""),
            file=sys.stderr,
        )
    else:
        print(
            "OK: surefire-results (Failures=0 Errors=0 Skipped=0 Tests=%d reports=%d; "
            "no test source under %s in this tree)"
            % (tests, len(suite_docs), roots_label(root)),
            file=sys.stderr,
        )
    for line in [read_line, root_line] + phase_lines + empty_notes:
        print("  " + line, file=sys.stderr)
    return 0


def check_root(root: Path, logs: list[Path]) -> int:
    try:
        return _diagnose(root, logs)
    except Unreadable as exc:
        print("FAIL: unreadable test evidence: %s" % exc, file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("root", type=Path, help="product / dest root")
    parser.add_argument(
        "--build-log",
        type=Path,
        action="append",
        default=[],
        help="a Maven build log to read when a phase produced no report "
             "(repeatable; root *.log, evidence/ and target/ logs are read anyway)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        return _fail("root is not a directory: " + str(root))
    return check_root(root, list(args.build_log))


if __name__ == "__main__":
    sys.exit(main())
