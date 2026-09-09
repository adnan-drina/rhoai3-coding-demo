#!/usr/bin/env python3
"""inventory-legacy-surface selftest.

- normalize-structure.py: raw JDK-model JSON → canonical structure + compat views; identical rerun
- partial mode (broken build) still yields evidence
- unpinned extractor → receipt status unpinned, exit 1, no structure written
- launcher refuses without a pin and on a JDK feature mismatch
- the real extractor (JDK compiler API, no classpath) runs on a Spring fixture and the
  catalog-derived entry points are the expected HTTP + scheduled set
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
NORMALIZE = HERE / "normalize-structure.py"
PAIR = HERE / "assert-frozen-root-pair.py"
LAUNCHER = HERE / "run-jdk-model-extract.sh"
EXTRACTOR = HERE / "jdk-model" / "JdkModelExtract.java"
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
from planner import specimens  # noqa: E402
from planner.canonical import load_json  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(argv: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, cwd=cwd, env=env)


def _java_fixture(root: Path) -> None:
    base = root / "src" / "main" / "java" / "org" / "acme"
    (base / "owner").mkdir(parents=True)
    (base / "owner" / "OwnerController.java").write_text(
        "package org.acme.owner;\n"
        "import org.springframework.web.bind.annotation.*;\n"
        "@RestController\n@RequestMapping(\"/api/owners\")\n"
        "public class OwnerController {\n"
        "  @GetMapping(\"/list\") public String list() { return \"x\"; }\n"
        "  @PostMapping public String create() { return \"y\"; }\n"
        "}\n",
        encoding="utf-8",
    )
    (base / "jobs").mkdir(parents=True)
    (base / "jobs" / "SyncJob.java").write_text(
        "package org.acme.jobs;\nimport org.springframework.scheduling.annotation.Scheduled;\n"
        "public class SyncJob {\n  @Scheduled(cron = \"0 * * * * *\") public void run() {}\n}\n",
        encoding="utf-8",
    )
    (root / "pom.xml").write_text("<project/>\n", encoding="utf-8")


def main() -> int:
    src = LAUNCHER.read_text(encoding="utf-8")
    for needle in ("STRUCTURE_UNPINNED", "STRUCTURE_JDK_MISMATCH", "pins.json", "--refuse unpinned", "--classpath", "structure_extractor"):
        if needle not in src:
            return _fail("launcher must carry %r" % needle)
    if "/projects/legacy" in src or "mvn " in src or "dependency:get" in src:
        return _fail("launcher must not scan the read-only mount or fetch an artifact")
    java = EXTRACTOR.read_text(encoding="utf-8")
    for needle in ("JavacTask", "javax.lang.model", "rhoai3.structure/v1", "should-stop.ifError=FLOW"):
        if needle not in java:
            return _fail("extractor must be the JDK compiler API and emit rhoai3.structure/v1 (%r)" % needle)
    third_party = ("import " + "spoon", "import org." + "eclipse", "import com.github." + "javaparser", "Pattern." + "compile")
    if any(x in java for x in third_party):
        return _fail("extractor must have no third-party dependency and no regex")

    with tempfile.TemporaryDirectory(prefix="inv-") as tmp:
        t = Path(tmp).resolve()
        spec = specimens.specimen("http")
        root = specimens.build_dest(t / "dest", spec, decisions=specimens.full_decisions())
        raw = t / "raw.json"
        raw.write_text(json.dumps({"schema": "rhoai3.structure/v1", "producer": {"tool": "jdk-model", "version": "", "runtime": "fixture", "mode": "full"}, "source_digest": "", "mode": "full", "types": list(reversed(spec["types"]))}), encoding="utf-8")
        p = _run([sys.executable, str(NORMALIZE), "--root", str(root), "--raw", str(raw), "--tool-version", "X.Y", "--tool-sha256", "a" * 64])
        if p.returncode != 0:
            return _fail("normalize: %s%s" % (p.stdout, p.stderr))
        structure = load_json(root / "evidence" / "structure" / "structure.json")
        freeze = load_json(root / "evidence" / "producers" / "freeze.json")
        if structure["source_digest"] != freeze["source_digest"]:
            return _fail("source_digest not stamped from freeze receipt")
        fqns = [x["fqn"] for x in structure["types"]]
        if fqns != sorted(fqns):
            return _fail("types not sorted")
        first = (root / "evidence" / "structure" / "structure.json").read_bytes()
        epi = load_json(root / "evidence" / "entry-point-inventory.json")
        if epi["counts"]["total"] != 4 or epi["counts"]["http"] != 4 or not epi["execution_evidence"]["provenance"].startswith("jdk-model:"):
            return _fail("entry-point inventory compat view: %s" % epi["counts"])
        paths = {e["http_method"] + " " + e["http_path"] for e in epi["entry_points"]}
        if "GET /api/owners" not in paths or "POST /api/owners" not in paths or "GET /api/pets" not in paths:
            return _fail("http paths not joined: %s" % paths)
        ti = load_json(root / "evidence" / "type-inventory.json")
        dests = {r["dest_file"] for r in ti["types"]}
        if "src/main/java/org/acme/clinic/owner/OwnerController.java" not in dests or "src/main/java/org/acme/clinic/common/Money.java" not in dests:
            return _fail("type inventory dest twins (compat path keeps packages): %s" % sorted(dests)[:5])
        if any("legacy/OldReportWriter" in d for d in dests):
            return _fail("unreached type must not be in the reach-based type inventory")
        rec = load_json(root / "evidence" / "producers" / "jdk-model.json")
        if rec["status"] != "ok" or rec["tool"]["artifact_sha256"] != "a" * 64 or rec["mode"] != "full" or rec["tool"]["name"] != "jdk-model":
            return _fail("jdk-model receipt %s" % rec)
        raw.write_text(json.dumps({"schema": "rhoai3.structure/v1", "producer": {"tool": "jdk-model", "version": "", "runtime": "fixture", "mode": "full"}, "source_digest": "", "mode": "full", "types": list(spec["types"])}), encoding="utf-8")
        _run([sys.executable, str(NORMALIZE), "--root", str(root), "--raw", str(raw), "--tool-version", "X.Y", "--tool-sha256", "a" * 64])
        if (root / "evidence" / "structure" / "structure.json").read_bytes() != first:
            return _fail("shuffled raw order must produce identical structure.json")
        pair = _run([sys.executable, str(PAIR), str(root)])
        if pair.returncode != 0:
            return _fail("frozen-root pair must pass: %s" % pair.stderr)

        # partial mode: broken build still yields evidence
        raw.write_text(json.dumps({"schema": "rhoai3.structure/v1", "producer": {"tool": "jdk-model", "version": "", "runtime": "fixture", "mode": "partial"}, "source_digest": "", "mode": "partial", "types": [dict(x, resolution="partial") for x in spec["types"]]}), encoding="utf-8")
        p = _run([sys.executable, str(NORMALIZE), "--root", str(root), "--raw", str(raw), "--tool-version", "X.Y"])
        if p.returncode != 0:
            return _fail("partial mode must still produce evidence: %s" % p.stderr)
        if load_json(root / "evidence" / "producers" / "jdk-model.json")["mode"] != "partial":
            return _fail("partial mode not recorded")

        # unpinned → fail closed
        p = _run([sys.executable, str(NORMALIZE), "--root", str(root), "--refuse", "unpinned", "--reason", "no pin"])
        if p.returncode != 1:
            return _fail("unpinned refuse must exit 1")
        if load_json(root / "evidence" / "producers" / "jdk-model.json")["status"] != "unpinned":
            return _fail("unpinned receipt not recorded")

        # launcher refuses without a structure_extractor pin (the fixture pins it, so unpin here)
        pins_path = root / ".hermes" / "pins.json"
        pins_doc = json.loads(pins_path.read_text(encoding="utf-8"))
        pins_doc["pins"].pop("structure_extractor")
        pins_path.write_text(json.dumps(pins_doc), encoding="utf-8")
        p = _run(["bash", str(LAUNCHER), "--root", str(root)])
        if p.returncode != 1 or "STRUCTURE_UNPINNED" not in p.stderr:
            return _fail("launcher without a pin must refuse STRUCTURE_UNPINNED: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        if load_json(root / "evidence" / "producers" / "jdk-model.json")["status"] != "unpinned":
            return _fail("unpinned launcher must record the receipt")

        # the real extractor on a Spring fixture, no classpath (partial mode), through the launcher
        jroot = t / "java"
        _java_fixture(jroot)
        jdest = t / "jdest"
        (jdest / ".hermes").mkdir(parents=True)
        shutil.copytree(GOLDEN / ".hermes" / "planning", jdest / ".hermes" / "planning")
        golden_pins = json.loads((GOLDEN / ".hermes" / "pins.json").read_text(encoding="utf-8"))
        retired_pin = "sp" + "oon"
        if golden_pins["pins"].get("structure_extractor", {}).get("version") != "jdk-21" or retired_pin in golden_pins["pins"]:
            return _fail("golden pins must pin structure_extractor to the toolchain JDK and carry no third-party extractor pin")
        (jdest / ".hermes" / "pins.json").write_text(json.dumps(golden_pins), encoding="utf-8")
        (jdest / "evidence" / "producers").mkdir(parents=True)
        (jdest / "evidence" / "producers" / "freeze.json").write_text(json.dumps({"schema": "rhoai3.producer-receipt/v1", "producer": "freeze", "status": "ok", "tool": {"name": "freeze-migration-input", "version": "1.0.0", "pin_status": "not-applicable"}, "inputs": {"source_root": str(jroot)}, "outputs": [], "reasons": [], "analysis_copy": str(jroot), "source_digest": "f" * 64}), encoding="utf-8")
        (jdest / "migration.yaml").write_text("migration:\n  legacyBasePackage: org.acme\n", encoding="utf-8")
        feature = _run(["java", "-XshowSettings:properties", "-version"]).stderr
        running = next((l.split("=")[1].strip() for l in feature.splitlines() if "java.specification.version" in l), "")
        if running != "21":
            # JDK mismatch must refuse, never run the extractor on the wrong toolchain
            p = _run(["bash", str(LAUNCHER), "--root", str(jdest)])
            if p.returncode != 1 or "STRUCTURE_JDK_MISMATCH" not in p.stderr:
                return _fail("JDK %r != pinned jdk-21 must refuse: %s" % (running, p.stderr[-200:]))
            print("OK: inventory-legacy-surface (normalize; compat views; partial mode; unpinned refuse; launcher refuse; JDK mismatch refuse on jdk-%s — extractor run skipped)" % running)
            return 0
        p = _run(["bash", str(LAUNCHER), "--root", str(jdest)])
        if p.returncode != 0:
            return _fail("launcher on the Java fixture: rc=%s %s %s" % (p.returncode, p.stdout[-300:], p.stderr[-600:]))
        structure = load_json(jdest / "evidence" / "structure" / "structure.json")
        if structure["producer"]["tool"] != "jdk-model" or structure["mode"] != "partial" or structure["producer"]["version"] != "jdk-21":
            return _fail("extractor provenance: %s" % structure["producer"])
        names = {x["fqn"]: x for x in structure["types"]}
        ctl = names.get("org.acme.owner.OwnerController")
        if ctl is None or {a["fqn"] for a in ctl["annotations"]} != {"org.springframework.web.bind.annotation.RestController", "org.springframework.web.bind.annotation.RequestMapping"}:
            return _fail("wildcard-imported annotations must resolve through the CU imports: %s" % (ctl and ctl["annotations"]))
        epi = load_json(jdest / "evidence" / "entry-point-inventory.json")
        got = {(e["http_method"], e["http_path"]) for e in epi["entry_points"] if e["kind"] == "http"}
        if got != {("GET", "/api/owners/list"), ("POST", "/api/owners")}:
            return _fail("extractor http set %s" % got)
        if epi["counts"]["non_http"] != 1:
            return _fail("extractor must see the @Scheduled seed: %s" % epi["counts"])
        rec = load_json(jdest / "evidence" / "producers" / "jdk-model.json")
        if rec["status"] != "ok" or rec["tool"]["pin_status"] != "pinned" or rec["tool"]["version"] != "jdk-21" or len(rec["tool"]["artifact_sha256"] or "") != 64 or "21" not in rec["tool"]["runtime"]:
            return _fail("jdk-model receipt provenance: %s" % rec["tool"])
        # JDK mismatch refusal: pin another release
        golden_pins["pins"]["structure_extractor"]["version"] = "jdk-17"
        (jdest / ".hermes" / "pins.json").write_text(json.dumps(golden_pins), encoding="utf-8")
        p = _run(["bash", str(LAUNCHER), "--root", str(jdest)])
        if p.returncode != 1 or "STRUCTURE_JDK_MISMATCH" not in p.stderr or load_json(jdest / "evidence" / "producers" / "jdk-model.json")["status"] != "unpinned":
            return _fail("JDK mismatch must refuse fail-closed: %s" % p.stderr[-200:])
    print("OK: inventory-legacy-surface (normalize; compat views; partial mode; unpinned refuse; launcher refuse; real JDK extractor on a Spring fixture; JDK mismatch refuse)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
