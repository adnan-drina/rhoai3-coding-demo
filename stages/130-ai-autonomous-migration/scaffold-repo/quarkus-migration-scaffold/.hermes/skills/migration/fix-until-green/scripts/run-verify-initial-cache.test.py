#!/usr/bin/env python3
"""The initial M2 analysis never reuses a warm-up (round 3).

The warm-up stamp's key covers the build inputs, the toolchain and the
generator specs, not the resolved dependency graph; the approved bound is that
the INITIAL analysis always rebuilds. Executed, not grepped: run-verify.sh
itself runs three times on a disposable destination with `mvn` stubbed on PATH
(the stub records every invocation and answers every goal):

  1. a routine verification with no stamp warms up and writes the stamp;
  2. a routine verification with the matching stamp SKIPS the warm-up
     (routine behaviour unchanged: cache "reused");
  3. an --initial verification with the SAME matching stamp present runs the
     warm-up again (the stub sees dependency:go-offline), records
     warmup.cache = "not-reused-initial-analysis", skipped false, initial true.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
SCRIPT = HERE / "run-verify.sh"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


STUB = """#!/usr/bin/env bash
echo "$*" >> "%(log)s"
for a in "$@"; do
  case "$a" in
    -Dmdep.outputFile=*) f="${a#-Dmdep.outputFile=}"; mkdir -p "$(dirname "$f")"; : > "$f" ;;
  esac
done
exit 0
"""


def run(root: Path, env: dict, *args: str) -> tuple[int, dict, str]:
    p = subprocess.run(["bash", str(SCRIPT), "--root", str(root), "--mode", "diagnostic", *args],
                       capture_output=True, text=True, env=env, timeout=600)
    rj = root / "verification/build/run.json"
    return p.returncode, (json.loads(rj.read_text()) if rj.is_file() else {}), p.stdout + p.stderr


def main() -> int:
    if not shutil.which("javac") or not shutil.which("java"):
        print("SKIP run-verify-initial-cache: no JDK (not run)")
        return 0
    with tempfile.TemporaryDirectory(prefix="rv-initial-") as td:
        td = Path(td)
        root = td / "dest"
        (root / ".hermes").mkdir(parents=True)
        for name in ("lib", "planning", "skills", "kernel"):
            os.symlink(GOLDEN / ".hermes" / name, root / ".hermes" / name)
        (root / ".hermes/pins.json").write_text('{"pins":{"quarkus_platform":{"java_release":21}}}', encoding="utf-8")
        (root / "pom.xml").write_text("<project><modelVersion>4.0.0</modelVersion></project>\n", encoding="utf-8")
        (root / "src/main/java/p").mkdir(parents=True)
        (root / "src/main/java/p/A.java").write_text("package p;\npublic class A { }\n", encoding="utf-8")
        bindir, log = td / "bin", td / "mvn.log"
        bindir.mkdir()
        (bindir / "mvn").write_text(STUB % {"log": log}, encoding="utf-8")
        (bindir / "mvn").chmod((bindir / "mvn").stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH="%s:%s" % (bindir, os.environ.get("PATH", "")))

        def warmups() -> int:
            return sum(1 for ln in (log.read_text().splitlines() if log.is_file() else []) if "dependency:go-offline" in ln)

        rc, doc, out = run(root, env)
        if not doc or (doc.get("warmup") or {}).get("cache") != "rebuilt" or warmups() != 1:
            return _fail("1. a first routine verification warms up and writes the stamp: rc=%s %s %s" % (rc, doc.get("warmup"), out[-400:]))
        if not (root / "verification/build/warmup.stamp").is_file():
            return _fail("1. the successful warm-up writes the stamp")
        rc, doc, out = run(root, env)
        if (doc.get("warmup") or {}).get("cache") != "reused" or not doc["warmup"].get("skipped") or warmups() != 1:
            return _fail("2. routine verification still reuses a matching stamp: %s" % doc.get("warmup"))
        stamp_before = (root / "verification/build/warmup.stamp").read_text()
        rc, doc, out = run(root, env, "--initial")
        w = doc.get("warmup") or {}
        if w.get("cache") != "not-reused-initial-analysis" or w.get("skipped") or not w.get("initial") or warmups() != 2:
            return _fail("3. the initial analysis rebuilds although the matching stamp was there: rc=%s %s (go-offline x%d) %s"
                         % (rc, w, warmups(), out[-400:]))
        if not stamp_before:
            return _fail("the control needs a matching stamp before the initial analysis")
    print("OK: run-verify initial cache (routine verification reuses a matching warm-up stamp; the INITIAL analysis "
          "discards it and warms up again -- executed with a stubbed mvn, recorded as warmup.cache "
          "not-reused-initial-analysis)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
