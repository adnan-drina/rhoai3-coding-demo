#!/usr/bin/env python3
"""AR-2.8 inventory-ground vs four-family floor. Not dest."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-product-tests.py"
FIX = HERE.parent / "fixtures" / "product-tests"


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        text=True,
        capture_output=True,
    )


def main() -> int:
    good = run(FIX / "ar28-good")
    if good.returncode != 0:
        print("FAIL: ar28-good must exit 0", file=sys.stderr)
        print(good.stderr, file=sys.stderr)
        return 1

    thin = run(FIX / "ar28-thin-security")
    if thin.returncode != 1 or "boot" not in thin.stderr:
        print("FAIL: ar28-thin-security must exit 1 missing boot", file=sys.stderr)
        print(thin.stderr, file=sys.stderr)
        return 1

    probe = run(FIX / "ar28-probe-only")
    if probe.returncode != 1 or "probe-only" not in probe.stderr:
        print("FAIL: ar28-probe-only must refuse", file=sys.stderr)
        print(probe.stderr, file=sys.stderr)
        return 1

    greet = run(FIX / "ar28-greeting-inventory")
    out = greet.stdout + greet.stderr
    if greet.returncode != 0:
        print("FAIL: greeting inventory + @QuarkusTest must exit 0", file=sys.stderr)
        print(out, file=sys.stderr)
        return 1
    if "N/A: AR-2.8" not in out:
        print("FAIL: greeting inventory must declare N/A families", file=sys.stderr)
        print(out, file=sys.stderr)
        return 1
    if "not idle" not in out:
        print("FAIL: N/A must say not idle", file=sys.stderr)
        print(out, file=sys.stderr)
        return 1

    noboot = run(FIX / "ar28-greeting-inventory-no-boot")
    if noboot.returncode != 1 or "boot" not in noboot.stderr:
        print("FAIL: greeting inventory without boot smoke must exit 1", file=sys.stderr)
        print(noboot.stderr, file=sys.stderr)
        return 1
    if "do not invent /q/health" not in noboot.stderr:
        print("FAIL: missing boot must not tell the worker to invent /q/health", file=sys.stderr)
        print(noboot.stderr, file=sys.stderr)
        return 1

    import importlib.util

    spec = importlib.util.spec_from_file_location("check_product_tests", SCRIPT)
    if spec is None or spec.loader is None:
        print("FAIL: cannot load check-product-tests.py", file=sys.stderr)
        return 1
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    greet_root = FIX / "ar28-greeting-inventory"
    if mod.db_intent(greet_root) is not False:
        print("FAIL: greeting database.needed false must not require db", file=sys.stderr)
        return 1

    print("OK: check-product-tests inventory-ground + four-family floor")

    import json
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "tree"
        shutil.copytree(FIX / "ar28-good", dest)
        wrote = subprocess.run(
            [sys.executable, str(SCRIPT), str(dest), "--write-receipt"],
            text=True,
            capture_output=True,
        )
        rec = dest / "evidence" / "receipts" / "gates" / "check-domain-parity.json"
        if wrote.returncode != 0:
            print("FAIL: ar28-good --write-receipt rc=%s" % wrote.returncode, file=sys.stderr)
            print(wrote.stderr, file=sys.stderr)
            return 1
        if not rec.is_file():
            print("FAIL: --write-receipt did not write %s" % rec, file=sys.stderr)
            return 1
        doc = json.loads(rec.read_text(encoding="utf-8"))
        if doc.get("gate") != "check-domain-parity" or "argv" not in doc:
            print("FAIL: domain receipt schema %s" % doc, file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
