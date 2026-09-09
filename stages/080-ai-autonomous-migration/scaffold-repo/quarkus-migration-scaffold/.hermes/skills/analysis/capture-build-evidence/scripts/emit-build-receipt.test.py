#!/usr/bin/env python3
"""emit-build-receipt selftest: success, failure (planning-only fact), no-freeze refuse."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "emit-build-receipt.py"
WRAPPER = HERE / "capture-build-evidence.sh"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _seed(root: Path, copy: Path, *, compile_rc: int, classpath: str) -> None:
    (root / "evidence" / "producers").mkdir(parents=True, exist_ok=True)
    (root / "evidence" / "producers" / "freeze.json").write_text(json.dumps({"schema": "rhoai3.producer-receipt/v1", "producer": "freeze", "status": "ok", "tool": {"name": "x", "pin_status": "not-applicable"}, "inputs": {}, "outputs": [], "reasons": [], "source_digest": "a" * 64, "analysis_copy": str(copy)}), encoding="utf-8")
    copy.mkdir(parents=True, exist_ok=True)
    (copy / "pom.xml").write_text("<project><properties><maven.compiler.release>17</maven.compiler.release></properties></project>", encoding="utf-8")
    (copy / "src" / "test" / "java").mkdir(parents=True, exist_ok=True)
    raw = root / "evidence" / "build"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "compile.rc").write_text("%d\n" % compile_rc)
    (raw / "compile.log").write_text("[ERROR] cannot find symbol\n[ERROR] BUILD FAILURE\n" if compile_rc else "")
    (raw / "warmup.rc").write_text("0\n")
    (raw / "classpath.rc").write_text("0\n")
    (raw / "classpath.txt").write_text(classpath)
    (raw / "java-version.txt").write_text('openjdk version "21.0.5" 2024-10-15 LTS\n')
    (raw / "mvn-version.txt").write_text("Apache Maven 3.9.10 (abc)\n")
    (raw / "generated-roots.txt").write_text("target/generated-sources/annotations\n")
    (raw / "effective-pom.rc").write_text("0\n")
    (raw / "effective-pom.xml").write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><dependencies><dependency><groupId>org.hsqldb</groupId><artifactId>hsqldb</artifactId><version>2.5.2</version><scope>runtime</scope></dependency></dependencies><dependencyManagement><dependencies><dependency><groupId>com.jayway.jsonpath</groupId><artifactId>json-path</artifactId><version>2.6.0</version></dependency><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-dependencies</artifactId><version>2.6.2</version><type>pom</type><scope>import</scope></dependency></dependencies></dependencyManagement></project>')


def main() -> int:
    src = WRAPPER.read_text(encoding="utf-8")
    if "mvn -q -B -o compile" not in src or "dependency:go-offline" not in src:
        return _fail("wrapper must warm up online and compile offline, separately")
    if "/projects/legacy" in src:
        return _fail("wrapper must not build the read-only legacy mount")
    with tempfile.TemporaryDirectory(prefix="build-ev-") as tmp:
        t = Path(tmp).resolve()
        root, copy = t / "dest", t / "copy"
        root.mkdir()
        _seed(root, copy, compile_rc=0, classpath="/x/a.jar:/x/b.jar")
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--copy", str(copy), "--raw", str(root / "evidence" / "build")], text=True, capture_output=True)
        if p.returncode != 0:
            return _fail("success run: %s" % p.stderr)
        rec = json.loads((root / "evidence" / "producers" / "build.json").read_text())
        if rec["outcome"] != "success" or rec["status"] != "ok" or not rec["classpath_available"] or rec["classpath_entries"] != 2:
            return _fail("success receipt %s" % rec)
        if rec["toolchain"]["java"] != "21.0.5" or rec["toolchain"]["maven"] != "3.9.10" or rec["toolchain"]["pom_release"] != "17":
            return _fail("toolchain %s" % rec["toolchain"])
        if rec["source_roots"] != ["src/main/java", "src/test/java"] or rec["generated_source_roots"] != ["target/generated-sources/annotations"]:
            return _fail("roots %s %s" % (rec["source_roots"], rec["generated_source_roots"]))
        if rec["warmup"]["outcome"] != "success":
            return _fail("warmup must be recorded separately: %s" % rec["warmup"])
        if rec.get("managed_versions") != {"org.hsqldb:hsqldb": "2.5.2", "com.jayway.jsonpath:json-path": "2.6.0"}:
            return _fail("legacy managed versions from the effective pom (imports excluded): %s" % rec.get("managed_versions"))
        first = (root / "evidence" / "producers" / "build.json").read_bytes()
        subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--copy", str(copy), "--raw", str(root / "evidence" / "build")], text=True, capture_output=True)
        if (root / "evidence" / "producers" / "build.json").read_bytes() != first:
            return _fail("rerun not byte-identical")
        _seed(root, copy, compile_rc=1, classpath="")
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--copy", str(copy), "--raw", str(root / "evidence" / "build")], text=True, capture_output=True)
        if p.returncode != 0:
            return _fail("failure is a recorded fact, wrapper exit 0: %s" % p.stderr)
        rec = json.loads((root / "evidence" / "producers" / "build.json").read_text())
        if rec["outcome"] != "failure" or rec["status"] != "failed" or rec["classpath_available"] or not rec["reasons"]:
            return _fail("failure receipt %s" % rec)
        bare = t / "bare"
        bare.mkdir()
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(bare), "--copy", str(copy), "--raw", str(bare)], text=True, capture_output=True)
        if p.returncode != 1 or "BUILD_NO_FREEZE" not in p.stderr:
            return _fail("missing freeze must refuse: %s" % p.stderr)
    print("OK: emit-build-receipt (success; failure recorded as planning-only fact; no-freeze refuse; identical rerun)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
