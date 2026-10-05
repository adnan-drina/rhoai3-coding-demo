#!/usr/bin/env python3
"""S-010 Class A — scaffold must declare test toolchain (assertj + rest-assured).

Exit 0 when pom.xml includes both test-scoped deps (or BOM-imported GAVs)
and assertj-core@version matches .hermes/pins.json assertj_core.

Exit 1 (REFUSE) when either is missing, assertj has no version, or the
version does not match the pin. RH quarkus-bom dest-cited 0 assertj hits
(Architect 125110ZA option B) — do not invent a version, and do not accept
an unpinned @version.

Usage:
  python3 check-test-toolchain.py .
  python3 check-test-toolchain.py /projects/modernized
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

REQUIRED = (
    # The JUnit 5 runner @QuarkusTest resolves against. Absent it, the
    # annotations do not compile and the failure lands on whichever story first
    # writes a test, not on the story that authored the pom (dest-6
    # us1_greeting; Operator E-20260825T200914ZO).
    ("io.quarkus", "quarkus-junit5"),
    ("io.rest-assured", "rest-assured"),
    ("org.assertj", "assertj-core"),
)


def has_dep(pom: str, group: str, artifact: str) -> bool:
    # Naive but durable for our scaffold poms: adjacent groupId/artifactId.
    pattern = (
        rf"<groupId>\s*{re.escape(group)}\s*</groupId>\s*"
        rf"<artifactId>\s*{re.escape(artifact)}\s*</artifactId>"
    )
    return re.search(pattern, pom, re.S) is not None


def pom_prop(pom: str, key: str) -> str:
    m = re.search(
        rf"<{re.escape(key)}>\s*([^<]+)\s*</{re.escape(key)}>",
        pom,
    )
    return m.group(1).strip() if m else ""


def resolve_version_token(raw: str, pom: str) -> str:
    token = (raw or "").strip()
    m = re.fullmatch(r"\$\{([^}]+)\}", token)
    if m:
        return pom_prop(pom, m.group(1))
    return token


def assertj_version(pom: str) -> str | None:
    """Return the resolved <version> or None if the dep block is absent.

    Empty string means the dep is present but has no version element.
    """
    m = re.search(
        r"<groupId>\s*org\.assertj\s*</groupId>\s*"
        r"<artifactId>\s*assertj-core\s*</artifactId>\s*"
        r".*?</dependency>",
        pom,
        re.S,
    )
    if not m:
        return None
    vm = re.search(r"<version>\s*([^<]+)\s*</version>", m.group(0))
    if not vm:
        return ""
    return resolve_version_token(vm.group(1), pom)


def assertj_pin(root: Path) -> str:
    path = root / ".hermes" / "pins.json"
    if not path.is_file():
        raise FileNotFoundError(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    pins = data.get("pins") if isinstance(data, dict) else None
    if not isinstance(pins, dict):
        raise ValueError("pins.json missing pins object")
    row = pins.get("assertj_core") or {}
    ver = str(row.get("version") or "").strip()
    if not ver:
        raise ValueError("assertj_core version missing in .hermes/pins.json")
    return ver


def _emit_gate_receipt(root: Path, rc: int) -> None:
    hit = (
        Path(__file__).resolve().parents[2]
        / "assert-pinned-gates-ran"
        / "scripts"
        / "script_gate_receipt.py"
    )
    spec = importlib.util.spec_from_file_location("script_gate_receipt", hit)
    if spec is None or spec.loader is None:
        print("FAIL: script_gate_receipt.py missing", file=sys.stderr)
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    argv = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    mod.emit_script_receipt(root, "check-release-readiness", rc, __file__, argv)


def _toolchain(root: Path) -> int:
    pom_path = root / "pom.xml"
    if not pom_path.is_file():
        print(f"FAIL: no pom.xml under {root}", file=sys.stderr)
        return 1
    pom = pom_path.read_text(encoding="utf-8", errors="replace")
    missing = [f"{g}:{a}" for g, a in REQUIRED if not has_dep(pom, g, a)]
    if missing:
        print(
            "FAIL: S-010 Class A test toolchain missing from pom.xml: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "  harness must ship assertj-core + rest-assured (test scope); "
            "see .hermes/skills/migration/manage-quarkus-extensions/references/test-toolchain.md",
            file=sys.stderr,
        )
        return 1
    try:
        pin = assertj_pin(root)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: cannot load assertj_core pin: {exc}", file=sys.stderr)
        return 1
    got = assertj_version(pom)
    if got is None:
        print("FAIL: org.assertj:assertj-core block unreadable", file=sys.stderr)
        return 1
    if not got:
        print(
            "FAIL: org.assertj:assertj-core present but missing <version> "
            "(RH quarkus-bom dest-cited 0 assertj hits; pin from "
            ".hermes/pins.json assertj_core)",
            file=sys.stderr,
        )
        return 1
    if got != pin:
        print(
            f"FAIL: pom assertj-core version {got!r} != pins.json {pin!r} "
            "(do not invent a GAV; Architect 125110ZA)",
            file=sys.stderr,
        )
        return 1
    print(
        "OK: test toolchain present "
        "(quarkus-junit5 + rest-assured + assertj-core pin)"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--write-receipt",
        nargs="?",
        const="gates",
        default=None,
        help="Write evidence/receipts/gates/check-release-readiness.json (runner schema)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    rc = _toolchain(root)
    if args.write_receipt is not None:
        _emit_gate_receipt(root, rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
