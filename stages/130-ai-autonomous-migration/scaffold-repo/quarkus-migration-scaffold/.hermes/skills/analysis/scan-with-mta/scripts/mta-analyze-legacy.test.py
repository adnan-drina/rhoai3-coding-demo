#!/usr/bin/env python3
"""mta-analyze-legacy.sh (M1) judges the analyzer's exit like the rescan does.

The fake analyzer of mta-rescan-destination.test.py (the pinned 8.2.1 shape:
`--json-output` is a boolean, findings in <output>/output.json, the optional
dependency-JSON marshal defect) analyzes a frozen copy of a one-file legacy
source:

1. a clean exit: findings and an ok receipt with exit_status 0, basis
   clean-exit, and the analyze argv recorded (written after the analyzer's
   --overwrite emptied the output directory);
2. the known 8.2.1 defect: accepted; the receipt and the findings keep exit
   status 1 and the exception's id and reason;
3. the defect plus another error, or a truncated output.json: M1 fails, the
   receipt is status failed with the refusal, and no findings remain, not
   even an earlier run's.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
ANALYZE = HERE / "mta-analyze-legacy.sh"
FREEZE = GOLDEN / ".hermes/skills/analysis/freeze-migration-input/scripts/freeze-migration-input.py"
_spec = importlib.util.spec_from_file_location("rescan_test", HERE / "mta-rescan-destination.test.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
FAKE = _mod.FAKE
EXC = "MTA-8.2.1-DEPENDENCIES-JSON-MARSHAL"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="m1-analyze-") as td:
        t = Path(td).resolve()
        legacy = t / "legacy"
        (legacy / "src/main/java/org/acme").mkdir(parents=True)
        (legacy / "src/main/java/org/acme/A.java").write_text("class A {}\n")
        (legacy / "pom.xml").write_text("<project/>\n")
        root = t / "dest"
        (root / ".hermes").mkdir(parents=True)
        shutil.copy2(GOLDEN / ".hermes/pins.json", root / ".hermes/pins.json")
        shutil.copytree(GOLDEN / ".hermes/planning/mta-rules", root / ".hermes/planning/mta-rules")
        (root / "migration.yaml").write_text("analysis:\n  custom_rules: .hermes/planning/mta-rules\n"
                                             "  canary_rule_id: rhoai3-canary-00001\n  targets:\n    - quarkus\n")
        p = subprocess.run([sys.executable, str(FREEZE), "--source", str(legacy), "--root", str(root),
                            "--copy-to", str(root / ".derived/frozen-input")], capture_output=True, text=True)
        if p.returncode != 0:
            return _fail("freeze: %s" % p.stderr[-400:])
        home = t / "home"
        (home / ".local/bin").mkdir(parents=True)
        (home / ".local/bin/kantra-assert-exec").write_text("#!/bin/sh\nexit 0\n")
        (home / ".local/bin/kantra-assert-exec").chmod(0o755)
        cli_home = t / "mta-cli"
        cli_home.mkdir()
        (cli_home / "mta-cli").write_text(FAKE)
        (cli_home / "mta-cli").chmod(0o755)
        receipt = root / "evidence/producers/mta.json"
        findings = root / "evidence/mta-findings.json"

        def analyze(**env) -> subprocess.CompletedProcess:
            e = dict(os.environ, HUMAN_HOME=str(home), MTA_CLI_HOME=str(cli_home), MTA_RUN_CWD=str(t / "run"),
                     KANTRA_HOME=str(t / "no-kantra"), JVM_MAX_MEM="1G", PYTHONDONTWRITEBYTECODE="1", **env)
            e.pop("JAVA_HOME_21", None)
            return subprocess.run(["bash", str(ANALYZE), "--root", str(root)], capture_output=True, text=True, env=e)

        # 1. clean exit
        p = analyze()
        rec = json.loads(receipt.read_text()) if receipt.is_file() else {}
        if not findings.is_file() or rec.get("status") != "ok" or rec.get("exit_status") != 0 \
                or (rec.get("analyzer_exit") or {}).get("basis") != "clean-exit":
            return _fail("a clean exit yields findings and an ok receipt: rc=%s %s %s" % (p.returncode, rec.get("analyzer_exit"), p.stderr[-600:]))
        argv = rec.get("argv") or []
        if "--json-output" not in argv or argv[argv.index("--json-output") + 1] != "--overwrite":
            return _fail("the receipt records the argv, --json-output without a value: %s" % argv)
        # 2. the known defect: accepted, exit status and exception recorded
        p = analyze(FAKE_MODE="defect")
        rec = json.loads(receipt.read_text()) if receipt.is_file() else {}
        exc = (rec.get("analyzer_exit") or {}).get("compatibility_exception") or {}
        ev = (json.loads(findings.read_text()).get("execution_evidence") or {}) if findings.is_file() else {}
        if rec.get("status") != "ok" or rec.get("exit_status") != 1 or exc.get("id") != EXC or exc.get("analyzer_exit_status") != 1:
            return _fail("the known defect is accepted with exit 1 recorded in the receipt: %s %s" % (rec.get("analyzer_exit"), p.stderr[-600:]))
        if ev.get("analyzer_exit_status") != 1 or (ev.get("compatibility_exception") or {}).get("id") != EXC:
            return _fail("the findings' execution evidence records the exception: %s" % ev)
        # 3. anything else fails M1, with a failed receipt and no findings
        for mode, why in (("defect+other", "another error"), ("truncated", "does not parse")):
            p = analyze(FAKE_MODE=mode)
            rec = json.loads(receipt.read_text()) if receipt.is_file() else {}
            ax = rec.get("analyzer_exit") or {}
            if p.returncode == 0 or rec.get("status") != "failed" or rec.get("exit_status") != 1 \
                    or ax.get("accepted") is not False or why not in str(ax.get("refusal")):
                return _fail("%s must fail M1 with a failed receipt: rc=%s %s" % (mode, p.returncode, ax))
            if findings.exists():
                return _fail("%s must leave no findings (an earlier run's included)" % mode)
    print("OK: mta-analyze-legacy (M1 passes --json-output as a boolean and judges the analyzer's exit: clean exit "
          "recorded; the known 8.2.1 dependency-JSON defect accepted with exit 1 and its reason in receipt and findings; "
          "another error or a truncated output.json fails M1 with a failed receipt and no findings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
