#!/usr/bin/env python3
"""Control: identity cannot close W4; mismatched inventory root REFUSE."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKER = HERE / "assert-harvest-referent-pair.py"
ENTRY = HERE / "inventory-entry-points.py"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True)


def _write_tree(tmp: Path, harvest: Path, mode: str, inv_root: Path) -> Path:
    dest = tmp / "dest"
    (dest / "evidence" / "derived").mkdir(parents=True)
    harvest.mkdir(parents=True, exist_ok=True)
    (harvest / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
    (harvest / "src" / "main" / "java" / "App.java").write_text(
        "class App {}\n", encoding="utf-8"
    )
    man = {
        "schema": "legacy-at-3/v2",
        "mode": mode,
        "harvest_referent": str(harvest.resolve()),
        "sha256": "deadbeef",
        "spring_boot_version_source": "2.6.2",
        "spring_boot_version_derived": "3.2.0",
        "jdk_version_source": "11",
        "jdk_version_derived": "17",
    }
    (dest / "evidence" / "derived" / "legacy-at-3.json").write_text(
        json.dumps(man, indent=2) + "\n", encoding="utf-8"
    )
    inv = {
        "schema": "rhoai3.entry-point-inventory/v1",
        "root": str(inv_root.resolve()),
        "counts": {"total": 0},
        "entry_points": [],
    }
    (dest / "evidence" / "entry-point-inventory.json").write_text(
        json.dumps(inv, indent=2) + "\n", encoding="utf-8"
    )
    return dest


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="w4-harvest-pair-") as raw:
        tmp = Path(raw)
        harvest = tmp / "harvest"
        other = tmp / "other"
        other.mkdir()

        dest_ok = _write_tree(tmp / "id-ok", harvest, "identity", harvest)
        got = _run([sys.executable, str(CHECKER), str(dest_ok)])
        if got.returncode != 0:
            return _fail("identity matching roots must PASS: %s" % got.stderr)
        boot2 = _run(
            [
                sys.executable,
                str(CHECKER),
                str(dest_ok),
                "--require-boot2-derivation",
            ]
        )
        if boot2.returncode != 2:
            return _fail(
                "identity --require-boot2-derivation want 2 got %s: %s"
                % (boot2.returncode, boot2.stderr)
            )
        if "cannot close W4-boot2-pair" not in (boot2.stderr or ""):
            return _fail("identity boot2 skip must name W4: %s" % boot2.stderr)

        dest_bad = _write_tree(tmp / "id-bad", harvest, "identity", other)
        bad = _run([sys.executable, str(CHECKER), str(dest_bad)])
        if bad.returncode != 1:
            return _fail(
                "mismatched roots want 1 got %s: %s" % (bad.returncode, bad.stderr)
            )

        dest_der = _write_tree(tmp / "der-ok", harvest, "derived", harvest)
        der = _run(
            [
                sys.executable,
                str(CHECKER),
                str(dest_der),
                "--require-boot2-derivation",
            ]
        )
        if der.returncode != 0:
            return _fail("derived matching roots must PASS boot2: %s" % der.stderr)

        guess = _run([sys.executable, str(ENTRY)])
        if guess.returncode != 2:
            return _fail(
                "inventory-entry-points with no args must REFUSE guess, got %s: %s"
                % (guess.returncode, guess.stderr)
            )
        if "do not guess /projects/legacy" not in (guess.stderr or ""):
            return _fail("no-args REFUSE must name /projects/legacy: %s" % guess.stderr)

        man = dest_ok / "evidence" / "derived" / "legacy-at-3.json"
        out = tmp / "inv-from-manifest.json"
        from_man = _run(
            [
                sys.executable,
                str(ENTRY),
                "--from-manifest",
                str(man),
                "-o",
                str(out),
            ]
        )
        if from_man.returncode != 0:
            return _fail("--from-manifest must scan harvest: %s" % from_man.stderr)
        wrote = json.loads(out.read_text(encoding="utf-8"))
        if Path(wrote["root"]).resolve() != harvest.resolve():
            return _fail(
                "--from-manifest wrote root %s want %s"
                % (wrote.get("root"), harvest)
            )

    print("OK: harvest-referent pair selftest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
