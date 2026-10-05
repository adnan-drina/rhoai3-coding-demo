#!/usr/bin/env python3
"""mta-rescan-destination.sh analyzes a disposable copy of the candidate.

A fake analyzer behaves like the pinned MTA Java provider (JDT/m2e): it
writes .project, .settings/ and .classpath into the tree it is given, and
reports one incident per Java file by absolute file URI, quoting the file's
first line so the test can tell which bytes it read. Against a real git
destination (the golden's planner library):

1. the candidate's bytes, git status and product digest are unchanged by the
   scan (the analyzer's IDE metadata stays in the copy), so the product digest
   still equals HEAD's and issuance needs no forced commit;
2. an UNCOMMITTED repair is what the analyzer reads, and the findings bind to
   that candidate's digest, not to HEAD's;
3. incidents name destination-relative files, and the obligation identities
   (worklist.incidents_from_findings) do not depend on the scratch directory;
4. a candidate that changes while it is analyzed is refused
   MTA_RESCAN_STALE_INPUT, its findings kept only as .stale, the scratch copy
   removed and the report left for diagnosis; a failed analyzer leaves no
   scratch copy either;
5. the fake takes `--json-output` as the pinned 8.2.1 boolean (a value after it
   is refused), and the analyzer's exit is judged (judge-analyzer-exit.py): a
   clean exit is recorded as such; the known 8.2.1 dependency-JSON marshal
   defect after a completed analysis is accepted with its nonzero exit and
   reason recorded; the defect plus another error, a stale, missing or
   truncated output.json, output.json disagreeing with output.yaml, or another
   CLI version is refused with no findings (incidents UNKNOWN).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HERMES = HERE.parents[3]
RESCAN = HERE / "mta-rescan-destination.sh"
sys.path.insert(0, str(HERMES / "lib"))
from planner.canonical import product_tree_sha256  # noqa: E402
from planner.outcome_checks import commit_product_tree  # noqa: E402
from planner.worklist import incidents_from_findings  # noqa: E402

FAKE = r'''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
a = sys.argv[1:]
if a[:1] != ["analyze"]:
    print(os.environ.get("FAKE_VERSION", "version: 8.2.1")); raise SystemExit(0)
# the pinned 8.2.1 flag is a boolean: a value after it is a stray argument
j = a.index("--json-output")
if j + 1 < len(a) and not a[j + 1].startswith("--"):
    print("Error: unexpected argument %s" % a[j + 1], file=sys.stderr); raise SystemExit(2)
inp = Path(a[a.index("--input") + 1]); rep = Path(a[a.index("--output") + 1])
mode = os.environ.get("FAKE_MODE", "")
if os.environ.get("FAKE_FAIL"):
    raise SystemExit(3)
# what JDT/m2e does to the tree it analyzes
(inp / ".project").write_text("<projectDescription/>\n")
(inp / ".settings").mkdir(exist_ok=True)
(inp / ".settings" / "org.eclipse.m2e.core.prefs").write_text("version=1\n")
(inp / ".classpath").write_text("<classpath/>\n")
incidents, canary = [], []
for f in sorted(inp.rglob("*.java")):
    first = f.read_text().splitlines()[0]
    incidents.append({"uri": "file://%s" % f, "lineNumber": 1, "message": "uses %s" % first})
    canary.append({"uri": "file://%s" % f, "lineNumber": 1, "message": "rhoai3 canary fired"})
if os.environ.get("FAKE_TOUCH"):
    orig = Path(os.environ["FAKE_TOUCH"])
    orig.write_text(orig.read_text() + "// changed during the scan\n")
rep.mkdir(parents=True, exist_ok=True)
doc = [{"name": "rs", "violations": {"fake-rule-00001": {"category": "mandatory", "incidents": incidents}},
        "insights": {"rhoai3-canary-00001": {"category": "optional", "incidents": canary}},
        "unmatched": [], "skipped": [], "errors": {}}]
def yaml_incidents(items):
    return "".join("      - uri: %s\n        message: %s\n        lineNumber: 1\n" % (i["uri"], i["message"]) for i in items)
extra = incidents[:1] if mode == "inconsistent" else []
(rep / "output.yaml").write_text("- name: rs\n  violations:\n    fake-rule-00001:\n      category: mandatory\n      incidents:\n"
                                 + yaml_incidents(incidents + extra)
                                 + "  insights:\n    rhoai3-canary-00001:\n      category: optional\n      incidents:\n"
                                 + yaml_incidents(canary))
(rep / "analysis.log").write_text('time="t" level=error msg="skipping rule for unavailable provider" provider=nodejs\n'
                                  'time="t" level=info msg="finished running analysis" rulesets="[]"\n')
(rep / "dependencies.yaml").write_text("- provider: java\n  dependencies: []\n")
text = json.dumps(doc)
if mode == "truncated":
    text = text[: len(text) // 2]
if mode != "missing":
    (rep / "output.json").write_text(text)
if mode == "stale":
    os.utime(rep / "output.json", (time.time() - 86400, time.time() - 86400))
if mode != "incomplete":
    print("Analysis complete!")
if mode:
    # what the pinned 8.2.1 prints converting dependencies.yaml with nested baseDep.extras
    print('time="t" level=error msg="failed to marshal dependencies file to json" error="json: unsupported type: map[interface {}]interface {}"', file=sys.stderr)
    if mode == "defect+other":
        print('time="t" level=error msg="failed to generate static report" error="exit status 1"', file=sys.stderr)
    print("Error: json: unsupported type: map[interface {}]interface {}", file=sys.stderr)
    raise SystemExit(1)
'''


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def git(root: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="rescan-copy-") as td:
        t = Path(td)
        root = t / "modernized"
        (root / "src/main/java/org/acme").mkdir(parents=True)
        (root / "src/main/java/org/acme/A.java").write_text("class A {}\n")
        (root / "pom.xml").write_text("<project/>\n")
        (root / "migration.yaml").write_text("analysis:\n  canary_rule_id: rhoai3-canary-00001\n  targets:\n    - quarkus\n")
        (root / ".gitignore").write_text(".project\n.settings/\n.classpath\nverification/\n.hermes/\n")
        (root / "evidence/mta").mkdir(parents=True)   # M1 leaves this read-only on a real destination
        (root / "evidence/mta/output.json").write_text("{}")
        (root / ".hermes").mkdir()
        os.symlink(HERMES / "lib", root / ".hermes" / "lib")
        git(root, "init", "-q")
        git(root, "add", "-A")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "candidate")
        (root / "evidence/mta/output.json").chmod(0o444)
        (root / "evidence/mta").chmod(0o555)
        home = t / "home"
        (home / ".local/bin").mkdir(parents=True)
        (home / ".local/bin/kantra-assert-exec").write_text("#!/bin/sh\nexit 0\n")
        (home / ".local/bin/kantra-assert-exec").chmod(0o755)
        cli_home = t / "mta-cli"
        cli_home.mkdir()
        (cli_home / "mta-cli").write_text(FAKE)
        (cli_home / "mta-cli").chmod(0o755)

        def rescan(run_cwd: str, **env) -> subprocess.CompletedProcess:
            e = dict(os.environ, HUMAN_HOME=str(home), MTA_CLI_HOME=str(cli_home), MTA_RUN_CWD=str(t / run_cwd),
                     KANTRA_HOME=str(t / "no-kantra"), PYTHONDONTWRITEBYTECODE="1", **env)
            e.pop("JAVA_HOME_21", None)
            return subprocess.run(["bash", str(RESCAN), str(root)], capture_output=True, text=True, env=e)

        def findings() -> dict:
            return json.loads((root / "verification/mta-rescan/findings.json").read_text())

        # 1. the analyzer's IDE metadata never reaches the candidate
        before = product_tree_sha256(root)
        p = rescan("run-a")
        if p.returncode != 0:
            return _fail("the rescan must succeed: %s" % (p.stdout + p.stderr)[-600:])
        leaked = [n for n in (".project", ".settings", ".classpath") if (root / n).exists()]
        if leaked or git(root, "status", "--porcelain", "--ignored", "--", "src", "pom.xml", ".project", ".settings", ".classpath"):
            return _fail("the candidate was changed by the analyzer: %s" % (leaked or git(root, "status", "--porcelain", "--ignored")))
        if product_tree_sha256(root) != before or before != commit_product_tree(root, git(root, "rev-parse", "HEAD")):
            return _fail("the product digest must stay the candidate's and equal HEAD's after a rescan")
        if list((t / "run-a").glob("destination-input.*")):
            return _fail("the scratch copy must be removed after the scan, read-only directories included")
        # 3. destination-relative incidents, identities independent of the scratch directory
        doc_a = findings()
        uris = [i["uri"] for v in doc_a["violations"].values() for i in v["incidents"]]
        if not uris or any(not u.startswith("file://%s/" % root) for u in uris):
            return _fail("incidents must name the destination's files, not the scratch copy: %s" % uris)
        ids_a = sorted(i["id"] for i in incidents_from_findings(doc_a, [str(root)], ""))
        paths_a = sorted(i.get("path") for i in incidents_from_findings(doc_a, [str(root)], ""))
        if paths_a != ["src/main/java/org/acme/A.java"]:
            return _fail("the obligation must be destination-relative: %s" % paths_a)
        p = rescan("another-scratch-name")
        ids_b = sorted(i["id"] for i in incidents_from_findings(findings(), [str(root)], ""))
        if p.returncode != 0 or ids_a != ids_b:
            return _fail("obligation identities must not depend on the scratch directory: %s vs %s" % (ids_a, ids_b))
        # 2. an uncommitted repair is analyzed and the findings bind to it
        (root / "src/main/java/org/acme/A.java").write_text("class A { /* repaired */ }\n")
        cand = product_tree_sha256(root)
        head_tree = commit_product_tree(root, git(root, "rev-parse", "HEAD"))
        p = rescan("run-c")
        doc = findings()
        ev = doc.get("execution_evidence") or {}
        msgs = [i["message"] for v in doc["violations"].values() for i in v["incidents"]]
        if p.returncode != 0 or ev.get("tree_sha256") != cand or cand == head_tree:
            return _fail("the findings must bind to the uncommitted candidate: %s vs %s (HEAD %s)" % (ev.get("tree_sha256"), cand, head_tree))
        if msgs != ["uses class A { /* repaired */ }"]:
            return _fail("the analyzer must read the uncommitted repair: %s" % msgs)
        # 4a. a candidate that changes during the scan is a stale input
        p = rescan("run-d", FAKE_TOUCH=str(root / "src/main/java/org/acme/A.java"))
        out = root / "verification/mta-rescan"
        if p.returncode == 0 or "MTA_RESCAN_STALE_INPUT" not in p.stderr:
            return _fail("a candidate changed during the scan must be refused: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        if (out / "findings.json").exists() or not (out / "findings.json.stale").exists() or not (out / "report").is_dir():
            return _fail("stale findings are kept only as .stale, with the report: %s" % sorted(x.name for x in out.iterdir()))
        if list((t / "run-d").glob("destination-input.*")):
            return _fail("a refused scan must still remove its scratch copy")
        # 4b. a failed analyzer leaves no scratch copy either
        p = rescan("run-e", FAKE_FAIL="1")
        if p.returncode == 0 or list((t / "run-e").glob("destination-input.*")):
            return _fail("a failed analyzer must fail and clean its scratch copy: rc=%s" % p.returncode)
        if (out / "findings.json").exists() or "MTA_ANALYZER_FAILED" not in p.stderr:
            return _fail("a failed analyzer must leave no findings (incidents UNKNOWN): %s" % p.stderr[-300:])
        # 5. the analyzer's exit status is judged (--json-output is a boolean on 8.2.1; the fake refuses a value)
        p = rescan("run-f")
        ev = findings().get("execution_evidence") or {}
        if p.returncode != 0 or ev.get("analyzer_exit_status") != 0 or ev.get("analyzer_exit_basis") != "clean-exit" \
                or ev.get("compatibility_exception") is not None:
            return _fail("a clean exit is recorded as such: rc=%s %s" % (p.returncode, ev))
        # 5a. the one known 8.2.1 defect: accepted, its nonzero exit and reason recorded, findings intact
        p = rescan("run-g", FAKE_MODE="defect")
        if p.returncode != 0:
            return _fail("the known 8.2.1 dependency-JSON marshal defect after a completed analysis is accepted: %s"
                         % (p.stdout + p.stderr)[-600:])
        doc = findings()
        ev = doc.get("execution_evidence") or {}
        exc = ev.get("compatibility_exception") or {}
        if ev.get("analyzer_exit_status") != 1 or exc.get("id") != "MTA-8.2.1-DEPENDENCIES-JSON-MARSHAL" \
                or exc.get("analyzer_exit_status") != 1 or exc.get("cli_version") != "8.2.1" or "dependencies.yaml" not in exc.get("reason", ""):
            return _fail("the exception must be recorded with the analyzer's nonzero exit preserved: %s" % ev)
        if not any(v.get("incidents") for v in doc["violations"].values()) or ev.get("tree_sha256") != product_tree_sha256(root):
            return _fail("accepted findings must carry the incidents and bind to the candidate: %s" % ev)
        # 5b. every other nonzero exit means incidents UNKNOWN: the rescan fails and writes no findings
        refusals = {
            "run-h": ({"FAKE_MODE": "defect+other"}, "another error besides the known marshal failure"),
            "run-i": ({"FAKE_MODE": "stale"}, "predates this invocation"),
            "run-j": ({"FAKE_MODE": "missing"}, "wrote no output.json"),
            "run-k": ({"FAKE_MODE": "truncated"}, "does not parse"),
            "run-l": ({"FAKE_MODE": "inconsistent"}, "output.json and output.yaml disagree"),
            "run-m": ({"FAKE_MODE": "defect", "FAKE_VERSION": "version: 8.2.2"}, "bound to 8.2.1 only"),
            "run-n": ({"FAKE_MODE": "incomplete"}, "does not report 'Analysis complete!'"),
        }
        for run, (env, why) in refusals.items():
            p = rescan(run, **env)
            verdict = out / "analyzer-verdict.json"
            if p.returncode == 0 or "MTA_ANALYZER_FAILED" not in p.stderr or why not in p.stderr:
                return _fail("%s must be refused (%s): rc=%s %s" % (env, why, p.returncode, p.stderr[-400:]))
            if (out / "findings.json").exists() or not verdict.is_file() or json.loads(verdict.read_text()).get("accepted") is not False:
                return _fail("%s must leave no findings and a refusing verdict" % env)
            if list((t / run).glob("destination-input.*")):
                return _fail("%s must still remove its scratch copy" % env)
        # 5c. an output.json present before the analyzer ran is never this invocation's
        rep = t / "prior" / "report"
        rep.mkdir(parents=True)
        (rep / "output.json").write_text("[]")
        (t / "prior" / "started").write_text("")
        p = subprocess.run([sys.executable, str(HERE / "judge-analyzer-exit.py"), "--rc", "1", "--report-dir", str(rep),
                            "--console", str(t / "prior" / "console"), "--started", str(t / "prior" / "started"),
                            "--cli-version", "version: 8.2.1", "--input-root", str(t), "--canary-id", "x", "--output-existed"],
                           capture_output=True, text=True)
        if p.returncode == 0 or "existed before this invocation" not in p.stderr:
            return _fail("a pre-existing output.json must be refused: %s" % p.stderr)
        # the M1 analyzer invocation uses the same boolean flag and the same judgement
        m1 = (HERE / "mta-analyze-legacy.sh").read_text()
        if '--json-output "' in m1 or "judge-analyzer-exit.py" not in m1:
            return _fail("mta-analyze-legacy.sh must pass --json-output as a boolean and judge the analyzer's exit")
    print("OK: mta-rescan-destination (the analyzer reads a disposable copy of the candidate, uncommitted repair included; "
          "its IDE metadata never reaches the candidate, whose digest stays HEAD's; incidents are destination-relative with "
          "scratch-independent identities; a candidate changed during the scan is refused as stale; scratch always removed; "
          "--json-output is a boolean; the known 8.2.1 dependency-JSON marshal defect is accepted with its exit recorded, and "
          "another error, a stale/missing/truncated output.json, YAML/JSON disagreement or another version is refused)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
