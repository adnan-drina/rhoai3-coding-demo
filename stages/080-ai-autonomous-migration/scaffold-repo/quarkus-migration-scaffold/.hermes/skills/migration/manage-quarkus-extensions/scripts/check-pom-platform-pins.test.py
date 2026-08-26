#!/usr/bin/env python3
"""Operator 125006ZO §5: dest-8 invented plugin versions must REFUSE. Not dest.

§5a (measured 2026-08-26 before this land): check-pom-platform-pins.py against
a dest-8-shaped pom (compiler 3.13.0 / surefire 3.5.2) AND a copy mutated to
compiler 3.11.0 both returned 0 — plugin coverage was zero.

§5b: pin from RHBQ 3.27 Maven chapter (3.11.0 / 3.1.2), not dest-8 recall.
After this land dest-8 invented versions REFUSE; official properties PASS.
The §5a mutation target 3.11.0 is the official compiler pin, so the refuse
case is dest-8 3.13.0/3.5.2, not 3.11.0.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-pom-platform-pins.py"
GOLDEN_PINS = next(
    p / "pins.json"
    for p in HERE.parents
    if p.name == ".hermes" and (p / "pins.json").is_file()
)


def _pom(compiler: str, surefire: str, *, platform: dict[str, str]) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>demo</groupId>
  <artifactId>demo</artifactId>
  <version>1.0</version>
  <properties>
    <compiler-plugin.version>{compiler}</compiler-plugin.version>
    <surefire-plugin.version>{surefire}</surefire-plugin.version>
    <quarkus.platform.group-id>{platform["group_id"]}</quarkus.platform.group-id>
    <quarkus.platform.artifact-id>{platform["bom_artifact_id"]}</quarkus.platform.artifact-id>
    <quarkus.platform.version>{platform["version"]}</quarkus.platform.version>
  </properties>
</project>
"""


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        text=True,
        capture_output=True,
    )


def main() -> int:
    if not GOLDEN_PINS.is_file():
        print("FAIL: missing golden pins.json", file=sys.stderr)
        return 1
    pins = json.loads(GOLDEN_PINS.read_text(encoding="utf-8"))
    qp = pins["pins"]["quarkus_platform"]
    want_c = pins["pins"]["compiler_plugin"]["version"]
    want_s = pins["pins"]["surefire_plugin"]["version"]
    if want_c != "3.11.0" or want_s != "3.1.2":
        print(
            "FAIL: pins must be RHBQ-doc 3.11.0/3.1.2, got "
            f"{want_c!r}/{want_s!r}",
            file=sys.stderr,
        )
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        hermes = root / ".hermes"
        hermes.mkdir()
        shutil.copy(GOLDEN_PINS, hermes / "pins.json")

        (root / "pom.xml").write_text(
            _pom("3.13.0", "3.5.2", platform=qp), encoding="utf-8"
        )
        dest8 = run(root)
        blob = dest8.stdout + dest8.stderr
        if dest8.returncode != 1:
            print(
                "FAIL: dest-8 invented 3.13.0/3.5.2 must exit 1: %s" % blob,
                file=sys.stderr,
            )
            return 1
        if "compiler-plugin.version" not in blob:
            print(
                "FAIL: dest-8 refuse must name compiler-plugin.version: %s" % blob,
                file=sys.stderr,
            )
            return 1

        (root / "pom.xml").write_text(
            _pom(want_c, "3.5.2", platform=qp), encoding="utf-8"
        )
        mixed = run(root)
        blob = mixed.stdout + mixed.stderr
        if mixed.returncode != 1 or "surefire-plugin.version" not in blob:
            print(
                "FAIL: official compiler + dest-8 surefire 3.5.2 must REFUSE: %s"
                % blob,
                file=sys.stderr,
            )
            return 1

        (root / "pom.xml").write_text(
            _pom(want_c, want_s, platform=qp), encoding="utf-8"
        )
        good = run(root)
        if good.returncode != 0:
            print(
                "FAIL: RHBQ-doc plugin pins must exit 0: %s%s"
                % (good.stdout, good.stderr),
                file=sys.stderr,
            )
            return 1

    print("OK: check-pom-platform-pins plugin coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
