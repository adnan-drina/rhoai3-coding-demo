#!/usr/bin/env python3
"""prepare-initial-analysis selftest: stale build outputs cannot move the initial plan.

Real producer, real files:

1. an orphan class in target/classes HIDES a real compile error from the JDK
   diagnostics producer (the reproduction); --exclude-output-classes shows it.
2. --phase before removes target/ (orphan classes, stale generated Java) on
   the initial analysis and REFUSES once a baseline or an issued card exists,
   leaving every file in place.
3. --phase after refuses (VERIFY_INITIAL_STALE_OUTPUT) a generated root holding
   a file older than the verification, or target/classes on the classpath,
   and records the provenance of a regenerated root.
4. two independent preparations of the same source, each polluted with
   different stale outputs, and a warm replay give the same v1 obligations.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HERMES = HERE.parents[3]
sys.path.insert(0, str(HERMES / "lib"))
from planner.worklist import IDENTITY_V1, compile_items  # noqa: E402

SCRIPT = HERE / "prepare-initial-analysis.py"
TOOL = HERE / "jdk-diagnostics" / "JdkDiagnostics.java"
EXPORTS = ["--add-exports", "jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED",
           "--add-exports", "jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED"]


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


_CLASSES: list[Path] = []


def producer(root: Path, out: Path, *extra: str) -> dict:
    if not _CLASSES:
        c = Path(tempfile.mkdtemp(prefix="pia-diag-"))
        subprocess.run(["javac", "-d", str(c), str(TOOL)], check=True, capture_output=True)
        _CLASSES.append(c)
    subprocess.run(["java"] + EXPORTS + ["-cp", str(_CLASSES[0]), "JdkDiagnostics", "--source", str(root), "--out", str(out),
                    "--release", "21", *extra], check=True, capture_output=True, timeout=120)
    return json.loads(out.read_text(encoding="utf-8"))


def tree(base: Path, *, junk: str) -> Path:
    """Source referencing a.Gone (deleted) and a generated a.gen.Dto; target/
    polluted with an orphan Gone.class and a stale generated file."""
    root = base / junk
    (root / "src/main/java/a").mkdir(parents=True)
    (root / "src/main/java/a/A.java").write_text("package a;\npublic class A { Gone g; a.gen.Dto d; }\n", encoding="utf-8")
    gone = base / ("gone-" + junk)
    (gone / "a").mkdir(parents=True)
    (gone / "a/Gone.java").write_text("package a;\npublic class Gone {}\n", encoding="utf-8")
    (root / "target/classes").mkdir(parents=True)
    subprocess.run(["javac", "-d", str(root / "target/classes"), str(gone / "a/Gone.java")], check=True, capture_output=True)
    stale = root / "target/generated-sources/openapi/a/gen"
    stale.mkdir(parents=True)
    (stale / "Dto.java").write_text("package a.gen;\npublic class Dto { /* %s */ }\n" % junk, encoding="utf-8")
    (stale / ("Orphan%s.java" % junk.capitalize())).write_text("package a.gen;\npublic class Orphan%s {}\n" % junk.capitalize(), encoding="utf-8")
    old = time.time() - 3600
    for p in stale.iterdir():
        os.utime(p, (old, old))
    return root


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args], text=True, capture_output=True)


def regenerate(root: Path) -> None:
    """What the warm-up's generate-sources does from the pinned spec: here, one DTO."""
    d = root / "target/generated-sources/openapi/a/gen"
    d.mkdir(parents=True, exist_ok=True)
    (d / "Dto.java").write_text("package a.gen;\npublic class Dto {}\n", encoding="utf-8")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="pia-"))
    try:
        # 1. the reproduction and the producer option
        a = tree(tmp, junk="one")
        hidden = producer(a, tmp / "hidden.json")
        if any("Gone" in d["message"] for d in hidden["diagnostics"]) or not hidden.get("output_classes_on_classpath"):
            return _fail("reproduction lost: the orphan Gone.class no longer hides the missing type")
        shown = producer(a, tmp / "shown.json", "--exclude-output-classes")
        if not any("Gone" in d["message"] and d["kind"] == "ERROR" for d in shown["diagnostics"]) or shown.get("output_classes_on_classpath"):
            return _fail("--exclude-output-classes must report the missing type and say target/classes was not read")
        if not shown.get("generated_roots") or shown["generated_roots"][0]["root"] != "target/generated-sources/openapi":
            return _fail("the producer must record the generated roots it read")

        # 2. before: refusal after a baseline leaves everything in place
        (a / "verification/loop").mkdir(parents=True)
        (a / "verification/loop/steps.json").write_text(json.dumps({"steps": [{"n": 0}]}), encoding="utf-8")
        p = run(a, "--phase", "before")
        if p.returncode != 2 or "VERIFY_INITIAL_AFTER_BASELINE" not in p.stderr or not (a / "target/classes/a/Gone.class").is_file():
            return _fail("after the baseline the boundary must refuse and delete nothing: %s" % p.stderr)
        (a / "verification/loop/steps.json").unlink()
        (a / "verification/loop/issued.json").write_text("{}", encoding="utf-8")
        p = run(a, "--phase", "before")
        if p.returncode != 2 or not (a / "target").is_dir():
            return _fail("with a card issued the boundary must refuse and delete nothing")
        (a / "verification/loop/issued.json").unlink()
        p = run(a, "--phase", "before")
        if p.returncode != 0 or (a / "target").exists():
            return _fail("the initial analysis must remove target/: %s" % p.stderr)
        rec = json.loads(p.stdout)
        if rec["removed_target"]["classes"] != 1 or rec["removed_target"]["generated"] != 2 or not rec["clean"]:
            return _fail("the record must count the removed orphan class and stale generated files: %s" % rec)
        if not (a / "src/main/java/a/A.java").is_file():
            return _fail("product files are never touched")

        # 3. after: stale generated root / output classes refuse; regenerated passes
        b = tree(tmp, junk="two")
        since = int(time.time() * 1000)
        stale_doc = producer(b, tmp / "b-stale.json", "--exclude-output-classes")
        p = run(b, "--phase", "after", "--diagnostics", str(tmp / "b-stale.json"), "--since-ms", str(since))
        if p.returncode != 1 or "VERIFY_INITIAL_STALE_OUTPUT" not in p.stderr:
            return _fail("a generated root older than the verification must refuse: %s" % p.stderr)
        del stale_doc
        producer(b, tmp / "b-classes.json")
        shutil.rmtree(b / "target/generated-sources")
        regenerate(b)
        producer(b, tmp / "b-classes.json")
        p = run(b, "--phase", "after", "--diagnostics", str(tmp / "b-classes.json"), "--since-ms", str(since))
        if p.returncode != 1 or "target/classes" not in p.stderr:
            return _fail("target/classes on the initial analysis classpath must refuse")

        # 4. two independent clean preparations and a warm replay agree
        ids = []
        for root in (a, b):
            if root.joinpath("target").exists():
                if run(root, "--phase", "before").returncode != 0:
                    return _fail("preparation of %s failed" % root.name)
            since = int(time.time() * 1000)
            regenerate(root)
            doc = producer(root, root.parent / ("%s-clean.json" % root.name), "--exclude-output-classes")
            p = run(root, "--phase", "after", "--diagnostics", str(root.parent / ("%s-clean.json" % root.name)), "--since-ms", str(since))
            if p.returncode != 0:
                return _fail("a regenerated root must pass the provenance check: %s" % p.stderr)
            prov = json.loads(p.stdout)
            if not prov["generated_roots"] or not prov["generated_roots"][0]["regenerated"]:
                return _fail("the provenance of the regenerated root must be recorded")
            ids.append(sorted(i["id"] for i in compile_items(doc, identity=IDENTITY_V1)))
        warm = producer(a, tmp / "warm.json", "--exclude-output-classes")
        ids.append(sorted(i["id"] for i in compile_items(warm, identity=IDENTITY_V1)))
        if not ids[0] or ids[0] != ids[1] or ids[0] != ids[2]:
            return _fail("independent clean preparations and a warm replay disagree: %s" % ids)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK: prepare-initial-analysis (an orphan class hides an error until target/classes is excluded; the "
          "initial boundary removes stale outputs and refuses after a baseline or an issued card; a stale generated "
          "root or output classes refuse; two polluted clean preparations and a warm replay give identical obligations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
