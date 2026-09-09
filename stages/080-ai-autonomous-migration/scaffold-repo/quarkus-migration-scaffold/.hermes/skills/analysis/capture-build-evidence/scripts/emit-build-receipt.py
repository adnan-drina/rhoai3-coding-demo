#!/usr/bin/env python3
"""Turn raw Maven outputs under evidence/build/ into evidence/producers/build.json.

Deterministic: reads rc files, classpath, pom, and version banners. The
receipt records facts; a failed compile is `outcome: failure`, still exit 0.
"""
from __future__ import annotations

import argparse
import re
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
from planner.paths import producer_receipt  # noqa: E402

JAVA_RE = re.compile(r'version "([^"]+)"')  # `java -version` banner (no structured form)
MVN_RE = re.compile(r"Apache Maven ([0-9][^ ]*)")  # `mvn -v` banner


def _q(tag: str) -> str:
    return tag


def _parse(path: Path) -> "ET.Element | None":
    """Parse and strip the POM namespace so lookups are by local name."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _pom_facts(pom_path: Path) -> dict:
    """release / java.version / sourceDirectory from the pom as XML (no text matching)."""
    out = {"release": "", "java_version": "", "source_dir": ""}
    if not pom_path.is_file():
        return out
    root = _parse(pom_path)
    if root is None:
        return out
    props = root.find(_q("properties"))
    if props is not None:
        for key in ("maven.compiler.release", "maven.compiler.source", "maven.compiler.target"):
            el = props.find(_q(key))
            if el is not None and (el.text or "").strip():
                out["release"] = (el.text or "").strip()
                break
        el = props.find(_q("java.version"))
        if el is not None:
            out["java_version"] = (el.text or "").strip()
    sd = root.find(_q("build") + "/" + _q("sourceDirectory"))
    if sd is not None:
        out["source_dir"] = (sd.text or "").strip()
    return out


def managed_versions(effective_pom: Path) -> dict[str, str]:
    """group:artifact → version as the legacy build resolved it (dependencies
    first, then the parent's dependencyManagement). Structured XML from
    `mvn help:effective-pom`; multi-module output (<projects>) is walked."""
    if not effective_pom.is_file():
        return {}
    root = _parse(effective_pom)
    if root is None:
        return {}
    projects = [root] if root.tag == _q("project") else root.findall(_q("project"))
    out: dict[str, str] = {}
    for proj in projects:
        for sel in (_q("dependencies") + "/" + _q("dependency"), _q("dependencyManagement") + "/" + _q("dependencies") + "/" + _q("dependency")):
            for dep in proj.findall(sel):
                g = (dep.findtext(_q("groupId")) or "").strip()
                a = (dep.findtext(_q("artifactId")) or "").strip()
                v = (dep.findtext(_q("version")) or "").strip()
                if g and a and v and (dep.findtext(_q("type")) or "jar").strip() != "pom":
                    out.setdefault("%s:%s" % (g, a), v)
    return out


def _rc(raw: Path, name: str) -> int | None:
    p = raw / (name + ".rc")
    if not p.is_file():
        return None
    try:
        return int(p.read_text(encoding="utf-8").strip() or "1")
    except ValueError:
        return 1


def _text(raw: Path, name: str) -> str:
    p = raw / name
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def build_receipt(root: Path, copy: Path, raw: Path) -> dict:
    freeze = load_json(producer_receipt(root, "freeze"))
    facts = _pom_facts(copy / "pom.xml")
    compile_rc = _rc(raw, "compile")
    eff_rc = _rc(raw, "effective-pom")
    managed = managed_versions(raw / "effective-pom.xml") if eff_rc == 0 else {}
    warm_rc = _rc(raw, "warmup")
    cp_rc = _rc(raw, "classpath")
    classpath = _text(raw, "classpath.txt").strip()
    java_m = JAVA_RE.search(_text(raw, "java-version.txt"))
    mvn_m = MVN_RE.search(_text(raw, "mvn-version.txt"))
    source_roots = [facts["source_dir"].replace("${basedir}/", "") if facts["source_dir"] else "src/main/java"]
    if (copy / "src" / "test" / "java").is_dir():
        source_roots.append("src/test/java")
    gen_roots = [ln.strip() for ln in _text(raw, "generated-roots.txt").splitlines() if ln.strip()]
    outcome = "not-attempted" if compile_rc is None else ("success" if compile_rc == 0 else "failure")
    reasons: list[str] = []
    if outcome == "failure":
        tail = _text(raw, "compile.log").strip().splitlines()[-5:]
        reasons.append("offline compile rc=%s: %s" % (compile_rc, " | ".join(tail)[:400]))
    if warm_rc not in (None, 0):
        reasons.append("dependency warm-up rc=%s" % warm_rc)
    if eff_rc not in (None, 0):
        reasons.append("effective pom rc=%s (legacy dependency versions unavailable to the bootstrap)" % eff_rc)
    outputs = []
    for name in ("compile.log", "warmup.log", "classpath.txt", "java-version.txt", "mvn-version.txt", "generated-roots.txt", "effective-pom.xml"):
        p = raw / name
        if p.is_file():
            outputs.append({"path": str(p.relative_to(root)) if p.is_relative_to(root) else str(p), "sha256": sha256_file(p)})
    return {
        "schema": "rhoai3.producer-receipt/v1",
        "producer": "build",
        "status": "ok" if outcome == "success" else ("failed" if outcome == "failure" else "skipped"),
        "tool": {"name": "maven", "version": mvn_m.group(1) if mvn_m else None, "pin_status": "not-applicable"},
        "inputs": {"analysis_copy": str(copy), "source_digest": str(freeze.get("source_digest") or "")},
        "outputs": outputs,
        "reasons": reasons,
        "outcome": outcome,
        "classpath_available": bool(classpath) and cp_rc == 0,
        "classpath_entries": len([c for c in classpath.split(":") if c]) if classpath else 0,
        "source_roots": sorted(set(source_roots)),
        "generated_source_roots": sorted(set(gen_roots)),
        "toolchain": {
            "java": java_m.group(1) if java_m else "",
            "maven": mvn_m.group(1) if mvn_m else "",
            "pom_release": facts["release"] or facts["java_version"],
        },
        "warmup": {"attempted": warm_rc is not None, "outcome": "success" if warm_rc == 0 else ("failure" if warm_rc is not None else "not-attempted")},
        "managed_versions": managed,
        "observations": {"compile_rc": compile_rc, "warmup_rc": warm_rc, "classpath_rc": cp_rc, "effective_pom_rc": eff_rc},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--copy", required=True)
    ap.add_argument("--raw", required=True)
    args = ap.parse_args(argv)
    root, copy, raw = Path(args.root).resolve(), Path(args.copy).resolve(), Path(args.raw).resolve()
    if not producer_receipt(root, "freeze").is_file():
        print("FAIL: BUILD_NO_FREEZE missing freeze receipt", file=sys.stderr)
        return 1
    receipt = build_receipt(root, copy, raw)
    write_canonical(producer_receipt(root, "build"), receipt)
    print("OK: build receipt outcome=%s classpath=%s warmup=%s" % (receipt["outcome"], receipt["classpath_available"], receipt["warmup"]["outcome"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
