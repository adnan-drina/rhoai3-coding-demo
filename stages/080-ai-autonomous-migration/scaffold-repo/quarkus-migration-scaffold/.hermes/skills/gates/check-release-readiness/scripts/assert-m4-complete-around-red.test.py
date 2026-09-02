#!/usr/bin/env python3
"""dest-8 m4-verdict.json + AR-2.8 rc 1 must refuse. Not dest."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "assert-m4-complete-around-red.py"
FIXTURE = HERE.parent / "fixtures" / "complete-around" / "dest-8-m4-verdict.json"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
    )


def main() -> int:
    if not FIXTURE.is_file():
        print("FAIL: missing dest-8 fixture " + str(FIXTURE), file=sys.stderr)
        return 1
    proc = run("--verdict", str(FIXTURE), "--floor-rc", "1")
    if proc.returncode != 1:
        print("FAIL: dest-8 fixture + floor-rc 1 must exit 1", file=sys.stderr)
        print(proc.stdout + proc.stderr, file=sys.stderr)
        return 1
    err = proc.stderr
    if "complete-around-red" not in err:
        print("FAIL: dest-8 must name complete-around-red", file=sys.stderr)
        print(err, file=sys.stderr)
        return 1
    if "idle" not in err.lower():
        print("FAIL: dest-8 idle-for-failed-floor must fire", file=sys.stderr)
        print(err, file=sys.stderr)
        return 1

    proc = run("--verdict", str(FIXTURE), "--floor-rc", "0")
    if proc.returncode != 0:
        print("FAIL: floor-rc 0 must not refuse ACCEPT", file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        honest = Path(tmp) / "refuse.json"
        honest.write_text(
            json.dumps(
                {
                    "verdict": "REFUSE",
                    "ship": False,
                    "reason": "AR-2.8 missing product-test families: boot",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        proc = run("--verdict", str(honest), "--floor-rc", "1")
        if proc.returncode != 0:
            print("FAIL: honest REFUSE + floor-rc 1 must pass", file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return 1

        idle_key_false = Path(tmp) / "idle-key-false.json"
        idle_key_false.write_text(
            json.dumps(
                {
                    "verdict": "REFUSE",
                    "ship": False,
                    "failed_floors": ["check-product-tests"],
                    "floors": [
                        {
                            "name": "check-runnable-db-config",
                            "idle": False,
                            "rc": 0,
                        },
                        {
                            "name": "check-product-tests",
                            "idle": False,
                            "rc": 1,
                        },
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        proc = run("--verdict", str(idle_key_false), "--floor-rc", "1")
        if proc.returncode != 0:
            print(
                "FAIL: idle:false values must not trip on the key name",
                file=sys.stderr,
            )
            print(proc.stderr, file=sys.stderr)
            return 1

        idle_ok = Path(tmp) / "idle-ok.json"
        idle_ok.write_text(
            json.dumps(
                {
                    "verdict": "PROVISIONAL_ACCEPT",
                    "ship": False,
                    "reason": "AR-2.1 completion floor idle (no DB intent)",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        proc = run(
            "--verdict",
            str(idle_ok),
            "--floor-rc",
            "0",
            "--floor-name",
            "check-runnable-db-config",
        )
        if proc.returncode != 0:
            print("FAIL: genuine idle + floor-rc 0 must pass", file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return 1

    print("OK: assert-m4-complete-around-red dest-8 fixture + idle-key false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
