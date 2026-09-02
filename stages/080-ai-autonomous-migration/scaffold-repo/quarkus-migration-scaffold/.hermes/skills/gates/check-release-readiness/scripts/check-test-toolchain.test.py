#!/usr/bin/env python3
"""Architect 125110ZA: assertj@version must match pins, not any literal. Not dest."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-test-toolchain.py"
GOLDEN_PINS = next(
    p / "pins.json"
    for p in HERE.parents
    if p.name == ".hermes" and (p / "pins.json").is_file()
)

TOOLCHAIN = """\
  <dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-junit5</artifactId>
    <scope>test</scope>
  </dependency>
  <dependency>
    <groupId>io.rest-assured</groupId>
    <artifactId>rest-assured</artifactId>
    <scope>test</scope>
  </dependency>
"""


def _pom(assertj_block: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>demo</groupId>
  <artifactId>demo</artifactId>
  <version>1.0</version>
  <dependencies>
{TOOLCHAIN}
{assertj_block}
  </dependencies>
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
    pin = json.loads(GOLDEN_PINS.read_text(encoding="utf-8"))["pins"][
        "assertj_core"
    ]["version"]
    if pin == "3.27.3":
        print("FAIL: assertj pin must not echo the Quarkus platform number", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        hermes = root / ".hermes"
        hermes.mkdir()
        shutil.copy(GOLDEN_PINS, hermes / "pins.json")

        (root / "pom.xml").write_text(
            _pom(
                """  <dependency>
    <groupId>org.assertj</groupId>
    <artifactId>assertj-core</artifactId>
    <scope>test</scope>
  </dependency>"""
            ),
            encoding="utf-8",
        )
        missing = run(root)
        blob = missing.stdout + missing.stderr
        if missing.returncode != 1 or "missing <version>" not in blob:
            print("FAIL: unversioned assertj must REFUSE: %s" % blob, file=sys.stderr)
            return 1

        (root / "pom.xml").write_text(
            _pom(
                """  <dependency>
    <groupId>org.assertj</groupId>
    <artifactId>assertj-core</artifactId>
    <version>3.27.3</version>
    <scope>test</scope>
  </dependency>"""
            ),
            encoding="utf-8",
        )
        echo = run(root)
        blob = echo.stdout + echo.stderr
        if echo.returncode != 1 or "3.27.3" not in blob:
            print(
                "FAIL: platform-echo 3.27.3 must REFUSE: %s" % blob,
                file=sys.stderr,
            )
            return 1

        (root / "pom.xml").write_text(
            _pom(
                f"""  <dependency>
    <groupId>org.assertj</groupId>
    <artifactId>assertj-core</artifactId>
    <version>{pin}</version>
    <scope>test</scope>
  </dependency>"""
            ),
            encoding="utf-8",
        )
        good = run(root)
        if good.returncode != 0:
            print(
                "FAIL: pinned assertj must exit 0: %s%s"
                % (good.stdout, good.stderr),
                file=sys.stderr,
            )
            return 1

        wrote = subprocess.run(
            [sys.executable, str(SCRIPT), str(root), "--write-receipt"],
            text=True,
            capture_output=True,
        )
        rec = root / "evidence" / "receipts" / "gates" / "check-release-readiness.json"
        if wrote.returncode != 0 or not rec.is_file():
            print(
                "FAIL: --write-receipt rc=%s rec=%s %s%s"
                % (wrote.returncode, rec.is_file(), wrote.stdout, wrote.stderr),
                file=sys.stderr,
            )
            return 1

    print("OK: check-test-toolchain assertj pin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
