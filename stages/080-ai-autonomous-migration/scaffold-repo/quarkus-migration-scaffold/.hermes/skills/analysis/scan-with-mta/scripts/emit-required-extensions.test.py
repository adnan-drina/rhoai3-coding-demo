#!/usr/bin/env python3
"""Operator 114924ZO: identity-mode empty legacy_pom must REFUSE. Not dest."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "emit-required-extensions.py"

HANDOFF = {
    "rules": [
        {
            "rule_id": "springboot-web-to-quarkus-00000",
            "description": "Rewrite Spring Web to quarkus-rest",
            "disposition": "apply",
        }
    ]
}

IDENTITY = {
    "schema": "legacy-at-3/v2",
    "mode": "identity",
    "legacy_src": "/projects/legacy",
}


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        text=True,
        capture_output=True,
    )


def write_handoff(root: Path) -> None:
    ev = root / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "findings-handoff.json").write_text(
        json.dumps(HANDOFF) + "\n", encoding="utf-8"
    )


def write_manifest(root: Path, harvest: str) -> None:
    derived = root / "evidence" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    doc = dict(IDENTITY)
    doc["harvest_referent"] = harvest
    (derived / "legacy-at-3.json").write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )


def write_pom(path: Path, artifact: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>legacy</groupId>
  <artifactId>legacy</artifactId>
  <version>1.0</version>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>{artifact}</artifactId>
    </dependency>
  </dependencies>
</project>
""",
        encoding="utf-8",
    )


def main() -> int:
    src = SCRIPT.read_text(encoding="utf-8")
    if "/projects/legacy/pom.xml" in src or "LEGACY_POM_CANDIDATES" in src:
        print(
            "FAIL: must not restore hardcoded /projects/legacy pom candidates",
            file=sys.stderr,
        )
        return 1

    import importlib.util

    spec = importlib.util.spec_from_file_location("emit_req", SCRIPT)
    if spec is None or spec.loader is None:
        print("FAIL: cannot load emit-required-extensions.py", file=sys.stderr)
        return 1
    ere = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ere)
    none = ere.database_object("", [])
    if none.get("needed") is not False:
        print("FAIL: empty jdbc_kind_from database.needed must be false: %s" % none, file=sys.stderr)
        return 1
    pg = ere.database_object(
        "jdbc:postgresql://localhost/x", ["spring-boot-starter-data-jpa"]
    )
    if pg.get("needed") is not True or pg.get("kind") != "postgresql":
        print("FAIL: postgres harvest database object: %s" % pg, file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_handoff(root)
        empty_dir = root / "legacy-empty"
        empty_dir.mkdir()
        write_manifest(root, str(empty_dir))
        miss = run(root)
        blob = miss.stdout + miss.stderr
        if miss.returncode != 1 or "LEGACY_POM_UNRESOLVED" not in blob:
            print(
                "FAIL: identity harvest_referent without pom must REFUSE: %s"
                % blob,
                file=sys.stderr,
            )
            return 1

        trap = root / "evidence" / "derived" / "legacy-at-3" / "pom.xml"
        write_pom(trap, "spring-boot-starter-validation")
        harvest = root / "legacy-at-3-harvest"
        write_pom(harvest / "pom.xml", "spring-boot-starter-cache")
        write_manifest(root, str(harvest))
        ok = run(root)
        blob = ok.stdout + ok.stderr
        if ok.returncode != 0:
            print("FAIL: harvest_referent pom must emit: %s" % blob, file=sys.stderr)
            return 1
        doc = json.loads(
            (root / "evidence" / "required-extensions.json").read_text(
                encoding="utf-8"
            )
        )
        if not doc.get("legacy_pom"):
            print("FAIL: legacy_pom must be non-empty: %s" % doc, file=sys.stderr)
            return 1
        aids = {e["artifactId"] for e in doc.get("entries") or []}
        if "quarkus-cache" not in aids:
            print(
                "FAIL: pom-only spring-boot-starter-cache must appear: %s" % doc,
                file=sys.stderr,
            )
            return 1
        if "quarkus-hibernate-validator" in aids:
            print(
                "FAIL: trap derived-dir pom must not win over harvest_referent: %s"
                % doc,
                file=sys.stderr,
            )
            return 1
        if "quarkus-cache" not in (doc.get("from_pom") or []):
            print("FAIL: from_pom must name the pom-only target: %s" % doc, file=sys.stderr)
            return 1
        db = doc.get("database")
        if not isinstance(db, dict) or db.get("needed") is not False:
            print("FAIL: cache-only harvest database.needed must be false: %s" % doc, file=sys.stderr)
            return 1
        if db.get("kind"):
            print("FAIL: no-database harvest must not name a kind: %s" % db, file=sys.stderr)
            return 1

        no_manifest = Path(tmp) / "no-manifest"
        no_manifest.mkdir()
        write_handoff(no_manifest)
        miss2 = run(no_manifest)
        blob = miss2.stdout + miss2.stderr
        if miss2.returncode != 1 or "LEGACY_POM_UNRESOLVED" not in blob:
            print(
                "FAIL: missing harvest_referent manifest must REFUSE: %s" % blob,
                file=sys.stderr,
            )
            return 1

    print("OK: emit-required-extensions harvest_referent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
