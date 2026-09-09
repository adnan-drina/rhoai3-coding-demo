#!/usr/bin/env python3
"""freeze-migration-input selftest: identical reruns, verified copy, refusals."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "freeze-migration-input.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True)


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="freeze-") as tmp:
        t = Path(tmp).resolve()
        src = t / "legacy"
        (src / "src" / "main" / "java" / "a").mkdir(parents=True)
        (src / "src" / "main" / "java" / "a" / "A.java").write_text("class A {}\n", encoding="utf-8")
        (src / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        (src / "target").mkdir()
        (src / "target" / "junk.class").write_bytes(b"\x00")
        (src / ".git").mkdir()
        (src / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
        root = t / "dest"
        root.mkdir()
        copy = t / "dest" / ".derived" / "frozen-input"
        p1 = _run("--source", str(src), "--root", str(root), "--copy-to", str(copy))
        if p1.returncode != 0:
            return _fail("first run: %s%s" % (p1.stdout, p1.stderr))
        m1 = (root / "evidence" / "frozen" / "source-manifest.json").read_bytes()
        doc = json.loads(m1)
        paths = [f["path"] for f in doc["files"]]
        if paths != ["pom.xml", "src/main/java/a/A.java"]:
            return _fail("manifest paths %s (target/.git must be skipped)" % paths)
        if len(doc["digest"]) != 64:
            return _fail("digest not sha256")
        if not (copy / "src" / "main" / "java" / "a" / "A.java").is_file():
            return _fail("copy missing")
        rec = json.loads((root / "evidence" / "producers" / "freeze.json").read_text())
        if rec["status"] != "ok" or rec["source_digest"] != doc["digest"] or rec["analysis_copy"] != str(copy):
            return _fail("receipt %s" % rec)
        p2 = _run("--source", str(src), "--root", str(root), "--copy-to", str(copy))
        if p2.returncode != 0:
            return _fail("rerun: %s" % p2.stderr)
        if (root / "evidence" / "frozen" / "source-manifest.json").read_bytes() != m1:
            return _fail("rerun is not byte-identical")
        (src / "src" / "main" / "java" / "a" / "A.java").write_text("class A { int x; }\n", encoding="utf-8")
        p3 = _run("--source", str(src), "--root", str(root))
        if json.loads((root / "evidence" / "frozen" / "source-manifest.json").read_text())["digest"] == doc["digest"]:
            return _fail("changed source must change the digest")
        empty = t / "empty"
        empty.mkdir()
        p4 = _run("--source", str(empty), "--root", str(root))
        if p4.returncode != 1 or "FREEZE_EMPTY" not in p4.stderr:
            return _fail("empty source must refuse: %s" % p4.stderr)
        nojava = t / "nojava"
        nojava.mkdir()
        (nojava / "README").write_text("x\n", encoding="utf-8")
        p5 = _run("--source", str(nojava), "--root", str(root))
        if p5.returncode != 1 or "FREEZE_NO_JAVA" not in p5.stderr:
            return _fail("no-java source must refuse: %s" % p5.stderr)
        inside = _run("--source", str(src), "--root", str(root), "--copy-to", str(src / "copy"))
        if inside.returncode != 1 or "FREEZE_COPY_INSIDE_SOURCE" not in inside.stderr:
            return _fail("copy inside source must refuse: %s" % inside.stderr)
    print("OK: freeze-migration-input (identical rerun; verified copy; empty/no-java/inside refuse)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
