#!/usr/bin/env python3
"""Measure which artifacts the pinned Quarkus BOM manages → evidence/build/bom-managed.json.

A minimal probe pom under .derived/bom-probe/ imports exactly the BOM from
.hermes/pins.json (quarkus_platform) and Maven's own `help:effective-pom`
writes the expanded dependencyManagement as XML. The bootstrap consumes the
resulting group:artifact set: a version-less dependency the BOM manages
stays version-less; one it does not manage is pinned to the version the
legacy build resolved (build receipt managed_versions) or blocks.

Network once (the BOM and the help plugin); the tree's own .mvn/maven.config
(-s .mvn/settings.xml, Red Hat GA repository) is copied next to the probe.
Never invents: no BOM, no probe file, and the bootstrap blocks.

Usage: probe-bom-managed.py --root <dest>
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.canonical import load_json, sha256_file, write_canonical  # noqa: E402
from planner.paths import BOM_MANAGED, PINS  # noqa: E402

NS = "http://maven.apache.org/POM/4.0.0"
PROBE_POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>rhoai3.probe</groupId>
  <artifactId>bom-probe</artifactId>
  <version>0</version>
  <packaging>pom</packaging>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>%(group_id)s</groupId>
        <artifactId>%(artifact_id)s</artifactId>
        <version>%(version)s</version>
        <type>pom</type>
        <scope>import</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>
</project>
"""


def managed_from_effective_pom(path: Path) -> list[str]:
    root = ET.parse(path).getroot()
    projects = [root] if root.tag == "{%s}project" % NS else root.findall("{%s}project" % NS)
    out: set[str] = set()
    for proj in projects:
        for dep in proj.findall("{%s}dependencyManagement/{%s}dependencies/{%s}dependency" % (NS, NS, NS)):
            g = (dep.findtext("{%s}groupId" % NS) or "").strip()
            a = (dep.findtext("{%s}artifactId" % NS) or "").strip()
            if g and a:
                out.add("%s:%s" % (g, a))
    return sorted(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    pins = load_json(root / PINS).get("pins") or {}
    platform = pins.get("quarkus_platform") or {}
    bom = {"group_id": str(platform.get("group_id") or ""), "artifact_id": str(platform.get("bom_artifact_id") or ""), "version": str(platform.get("version") or "")}
    if not all(bom.values()):
        print("FAIL: BOM_PROBE_UNPINNED pins.quarkus_platform is incomplete", file=sys.stderr)
        return 1
    probe = root / ".derived" / "bom-probe"
    shutil.rmtree(probe, ignore_errors=True)
    probe.mkdir(parents=True)
    (probe / "pom.xml").write_text(PROBE_POM % bom, encoding="utf-8")
    if (root / ".mvn").is_dir():
        shutil.copytree(root / ".mvn", probe / ".mvn")
    env = dict(os.environ)
    java_home = env.get("JAVA_HOME_21") or env.get("JAVA_HOME")
    if java_home:
        env["JAVA_HOME"] = java_home
        env["PATH"] = str(Path(java_home) / "bin") + os.pathsep + env.get("PATH", "")
    effective = probe / "effective-pom.xml"
    log = probe / "mvn.log"
    with log.open("w", encoding="utf-8") as fh:
        rc = subprocess.run(["mvn", "-q", "-B", "help:effective-pom", "-Doutput=%s" % effective], cwd=str(probe), env=env, stdout=fh, stderr=subprocess.STDOUT).returncode
    if rc != 0 or not effective.is_file():
        tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-6:]
        print("FAIL: BOM_PROBE_FAILED mvn help:effective-pom rc=%s: %s" % (rc, " | ".join(tail)[:600]), file=sys.stderr)
        return 1
    managed = managed_from_effective_pom(effective)
    if not managed:
        print("FAIL: BOM_PROBE_EMPTY the effective pom manages nothing (wrong BOM coordinates?)", file=sys.stderr)
        return 1
    doc = {"schema": "rhoai3.bom-managed/v1", "bom": bom, "managed": managed, "count": len(managed), "effective_pom_sha256": sha256_file(effective), "tool": "mvn help:effective-pom"}
    write_canonical(root / BOM_MANAGED, doc)
    print("OK: bom-managed %d artifacts from %s:%s:%s → %s" % (len(managed), bom["group_id"], bom["artifact_id"], bom["version"], BOM_MANAGED))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
