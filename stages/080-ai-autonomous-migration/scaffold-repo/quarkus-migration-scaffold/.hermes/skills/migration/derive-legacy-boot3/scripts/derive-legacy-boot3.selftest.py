#!/usr/bin/env python3
"""Identity must not freeze a phantom derived_root. Not dest."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DERIVE = HERE / "derive-legacy-boot3.sh"
CHECK = HERE / "check-manifest.sh"


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def _run(argv: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, env=env)


def _pom(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<project>
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.0</version>
  </parent>
  <groupId>demo</groupId>
  <artifactId>legacy</artifactId>
  <version>1.0</version>
  <properties>
    <java.version>17</java.version>
  </properties>
</project>
""",
        encoding="utf-8",
    )


def _gradle(path: Path) -> None:
    path.write_text(
        """plugins {
  id 'org.springframework.boot' version '4.0.7'
}
sourceCompatibility = '21'
""",
        encoding="utf-8",
    )


def _identity_doc(harvest: Path, *, derived_root: str | None = None) -> dict:
    doc = {
        "schema": "legacy-at-3/v2",
        "mode": "identity",
        "legacy_src": str(harvest),
        "harvest_referent": str(harvest),
        "sha256": "abc",
        "spring_boot_version_source": "3.2.0",
        "spring_boot_version_derived": "3.2.0",
        "jdk_version_source": "17",
        "jdk_version_derived": "17",
    }
    if derived_root is not None:
        doc["derived_root"] = derived_root
    return doc


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="derive-identity-"))
    try:
        harvest = tmp / "legacy"
        harvest.mkdir()
        _pom(harvest / "pom.xml")
        (harvest / "README").write_text("x\n", encoding="utf-8")
        dest = tmp / "modernized"
        dest.mkdir()
        env = os.environ.copy()
        env["MODERNIZED_ROOT"] = str(dest)
        env["LEGACY_SRC"] = str(harvest)
        proc = _run(["bash", str(DERIVE)], env=env)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 0:
            return _fail("identity derive must PASS: %s" % blob)
        man_path = dest / "evidence" / "derived" / "legacy-at-3.json"
        if not man_path.is_file():
            return _fail("missing manifest: %s" % blob)
        doc = json.loads(man_path.read_text(encoding="utf-8"))
        if doc.get("mode") != "identity":
            return _fail("mode: %s" % doc)
        if "derived_root" in doc and doc["derived_root"]:
            return _fail("identity must omit derived_root: %s" % doc)
        if Path(doc["harvest_referent"]).resolve() != harvest.resolve():
            return _fail("harvest_referent: %s" % doc)
        phantom = dest / ".derived" / "legacy-at-3"
        if phantom.exists():
            return _fail("identity must not create %s" % phantom)
        proc = _run(["bash", str(CHECK), "--root", str(dest)])
        if proc.returncode != 0:
            return _fail("check-manifest identity must PASS: %s%s" % (proc.stdout, proc.stderr))

        dest10 = tmp / "dest10"
        (dest10 / "evidence" / "derived").mkdir(parents=True)
        harvest.mkdir(exist_ok=True)
        (dest10 / "evidence" / "derived" / "legacy-at-3.json").write_text(
            json.dumps(
                _identity_doc(
                    harvest,
                    derived_root="/projects/modernized/.derived/legacy-at-3",
                ),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        proc = _run(["bash", str(CHECK), "--root", str(dest10)])
        blob = proc.stdout + proc.stderr
        if proc.returncode == 0:
            return _fail("dest-10 phantom derived_root must REFUSE: %s" % blob)
        if "derived_root" not in blob:
            return _fail("phantom refuse must name derived_root: %s" % blob)

        gdest = tmp / "gradle-ws"
        gdest.mkdir()
        gleg = tmp / "gradle-legacy"
        gleg.mkdir()
        _gradle(gleg / "build.gradle")
        (gleg / "src.txt").write_text("x\n", encoding="utf-8")
        env["MODERNIZED_ROOT"] = str(gdest)
        env["LEGACY_SRC"] = str(gleg)
        proc = _run(["bash", str(DERIVE)], env=env)
        blob = proc.stdout + proc.stderr
        if proc.returncode != 0:
            return _fail("gradle identity derive must PASS: %s" % blob)
        gdoc = json.loads(
            (gdest / "evidence" / "derived" / "legacy-at-3.json").read_text(
                encoding="utf-8"
            )
        )
        if gdoc.get("spring_boot_version_source") != "4.0.7":
            return _fail("gradle boot version: %s" % gdoc)
        if "derived_root" in gdoc and gdoc["derived_root"]:
            return _fail("gradle identity derived_root: %s" % gdoc)
        if "legacy@3.x" in str(gdoc.get("note") or "") and "derived" in str(
            gdoc.get("note") or ""
        ).lower() and "no derived_root" not in str(gdoc.get("note") or ""):
            return _fail("identity note still frames a derived at-3 tree: %s" % gdoc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK: derive-legacy-boot3 identity omits derived_root")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
