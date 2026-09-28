#!/usr/bin/env python3
"""emit-build-receipt selftest: success, failure (planning-only fact), no-freeze
refuse, a failed classpath extraction named after a successful compile, and the
wrapper's warm-up covering every goal its offline pass measures (fake Maven)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "emit-build-receipt.py"
WRAPPER = HERE / "capture-build-evidence.sh"

# A Maven whose offline resolution holds only what the SAME goal fetched
# online: go-offline fetches nothing another goal needs (measured 2026-09-09),
# and compile does not fetch test scope (v21 2026-09-27, byte-buddy-agent).
FAKE_MVN = r'''#!/usr/bin/env python3
import json, os, sys
state = os.environ["FAKE_MVN_STATE"]
args = sys.argv[1:]
if "-v" in args:
    print("Apache Maven 3.9.10 (fake)"); sys.exit(0)
warm = set(json.load(open(state))) if os.path.exists(state) else set()
goals = [a for a in args if not a.startswith("-")]
props = dict(a[2:].split("=", 1) for a in args if a.startswith("-D") and "=" in a)
for g in goals:
    if "-o" in args and g not in warm:
        print("[ERROR] dependency for goal %s has not been downloaded from it before." % g); sys.exit(1)
    warm.add(g)
    if g == "compile":
        os.makedirs("target/generated-sources/annotations", exist_ok=True)
    if g == "dependency:build-classpath" and props.get("mdep.outputFile"):
        open(props["mdep.outputFile"], "w").write("/repo/a.jar:/repo/b.jar")
    if g == "help:effective-pom" and props.get("output"):
        open(props["output"], "w").write("<project/>")
json.dump(sorted(warm), open(state, "w"))
'''


def _run_wrapper(t: Path, wrapper: Path, name: str) -> dict:
    root, copy, bin_dir = t / name / "dest", t / name / "copy", t / name / "bin"
    root.mkdir(parents=True)
    _seed(root, copy, compile_rc=0, classpath="")
    bin_dir.mkdir()
    (bin_dir / "mvn").write_text(FAKE_MVN, encoding="utf-8")
    (bin_dir / "mvn").chmod(0o755)
    env = dict(os.environ, PATH="%s:%s" % (bin_dir, os.environ.get("PATH", "")), FAKE_MVN_STATE=str(t / name / "m2.json"),
               JAVA_HOME="", JAVA_HOME_21="")
    p = subprocess.run(["bash", str(wrapper), "--root", str(root)], text=True, capture_output=True, env=env)
    if p.returncode != 0:
        raise AssertionError("%s wrapper rc=%d: %s" % (name, p.returncode, p.stderr[-400:]))
    return json.loads((root / "evidence" / "producers" / "build.json").read_text())


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
        # the compile succeeded, the offline classpath did not: the receipt
        # keeps the successful outcome and NAMES the missing classpath
        _seed(root, copy, compile_rc=0, classpath="")
        (root / "evidence" / "build" / "classpath.rc").write_text("1\n")
        (root / "evidence" / "build" / "classpath.log").write_text(
            "[ERROR] Failed to execute goal on project x: Could not resolve dependencies\n"
            "[ERROR] dependency: g:test-only:jar:1.0 (test)\n")
        p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--copy", str(copy), "--raw", str(root / "evidence" / "build")], text=True, capture_output=True)
        rec = json.loads((root / "evidence" / "producers" / "build.json").read_text())
        why = [r for r in rec["reasons"] if r.startswith("offline classpath extraction rc=1")]
        if p.returncode != 0 or rec["outcome"] != "success" or rec["classpath_available"] or not why or "g:test-only" not in why[0]:
            return _fail("a failed classpath after a successful compile must be named, not silent: %s" % rec["reasons"])
        # the wrapper's warm-up covers every goal the offline pass measures
        rec = _run_wrapper(t, WRAPPER, "wrapper")
        if not rec["classpath_available"] or rec["classpath_entries"] != 2 or rec["reasons"]:
            return _fail("warm-up must fetch what the offline classpath resolves: %s %s" % (rec["classpath_available"], rec["reasons"]))
        # mutation: the pre-fix warm-up (go-offline + compile only) is caught
        pre = t / "pre-fix"
        pre.mkdir()
        src = WRAPPER.read_text(encoding="utf-8")
        cut = src.replace(' \\\n    && mvn -q -B dependency:build-classpath "-Dmdep.outputFile=${RAW}/warmup-classpath.txt"', "")
        if cut == src:
            return _fail("mutation did not apply; the warm-up line changed shape")
        (pre / "capture-build-evidence.sh").write_text(cut, encoding="utf-8")
        (pre / "emit-build-receipt.py").symlink_to(SCRIPT)
        rec = _run_wrapper(t, pre / "capture-build-evidence.sh", "mutant")
        if rec["classpath_available"] or not any(r.startswith("offline classpath extraction rc=1") for r in rec["reasons"]):
            return _fail("the pre-fix warm-up must leave the classpath unavailable AND named: %s" % rec)
    print("OK: emit-build-receipt (success; failure recorded as planning-only fact; no-freeze refuse; identical rerun; "
          "failed classpath named; warm-up covers the measured classpath goal, pre-fix mutant caught)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
