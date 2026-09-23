#!/usr/bin/env python3
"""paved-road-m5 selftest: kind rules, generated audit, delivery contract tests."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
LIB = HERE.parents[3] / "lib"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from paved_road import load_steps, sync_audit, validate_steps_doc  # noqa: E402


def main() -> int:
    rc, msg = sync_audit(SKILL)
    if rc != 0:
        return _fail(msg)
    doc = load_steps(SKILL / "steps.json")
    ids = [s["id"] for s in doc["steps"]]
    if ids[0] != "start-m5-delivery":
        return _fail("M5 must start with eligibility-checked mint: %s" % ids)
    prod = next(s for s in doc["steps"] if s.get("producer"))
    if prod.get("native") != "compose-m5-verdict.py":
        return _fail("compose-m5-verdict.py must be the producer: %s" % prod)
    errors = validate_steps_doc(doc, path=SKILL / "steps.json")
    if errors:
        return _fail("\n".join(errors))
    proc = subprocess.run([sys.executable, str(LIB / "m5_delivery.test.py")], cwd=str(LIB), text=True, capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return _fail("m5_delivery.test.py rc=%s" % proc.returncode)
    print("OK: paved-road-m5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
