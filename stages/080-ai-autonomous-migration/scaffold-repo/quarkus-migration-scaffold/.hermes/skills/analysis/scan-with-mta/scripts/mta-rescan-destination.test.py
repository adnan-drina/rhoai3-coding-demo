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
   scratch copy either.
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
import json, os, sys
from pathlib import Path
a = sys.argv[1:]
if a[:1] != ["analyze"]:
    print("mta-cli 8.2.1"); raise SystemExit(0)
inp = Path(a[a.index("--input") + 1]); out = Path(a[a.index("--json-output") + 1])
if os.environ.get("FAKE_FAIL"):
    raise SystemExit(3)
# what JDT/m2e does to the tree it analyzes
(inp / ".project").write_text("<projectDescription/>\n")
(inp / ".settings").mkdir(exist_ok=True)
(inp / ".settings" / "org.eclipse.m2e.core.prefs").write_text("version=1\n")
(inp / ".classpath").write_text("<classpath/>\n")
incidents = []
for f in sorted(inp.rglob("*.java")):
    first = f.read_text().splitlines()[0]
    incidents.append({"uri": "file://%s" % f, "lineNumber": 1, "message": "uses %s" % first})
if os.environ.get("FAKE_TOUCH"):
    orig = Path(os.environ["FAKE_TOUCH"])
    orig.write_text(orig.read_text() + "// changed during the scan\n")
out.write_text(json.dumps([{"name": "rs", "violations": {"fake-rule-00001": {"category": "mandatory", "incidents": incidents}},
                            "unmatched": [], "skipped": [], "errors": {}}]))
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
        (root / "migration.yaml").write_text("analysis:\n  targets:\n    - quarkus\n")
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
    print("OK: mta-rescan-destination (the analyzer reads a disposable copy of the candidate, uncommitted repair included; "
          "its IDE metadata never reaches the candidate, whose digest stays HEAD's; incidents are destination-relative with "
          "scratch-independent identities; a candidate changed during the scan is refused as stale; scratch always removed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
