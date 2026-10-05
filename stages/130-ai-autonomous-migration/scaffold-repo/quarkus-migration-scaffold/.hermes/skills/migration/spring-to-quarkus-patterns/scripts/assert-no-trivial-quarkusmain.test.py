#!/usr/bin/env python3
"""W6: dest @QuarkusMain + trivial legacy main REFUSE. Not dest."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
BIN = HERE / "assert-no-trivial-quarkusmain.py"
FIX = SKILL / "fixtures" / "cases"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BIN), *args],
        text=True,
        capture_output=True,
    )


def main() -> int:
    md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    if "assert-no-trivial-quarkusmain.py" not in md:
        print("FAIL: SKILL.md must name assert-no-trivial-quarkusmain.py", file=sys.stderr)
        return 1
    if "@QuarkusMain" not in md:
        print("FAIL: SKILL.md must name @QuarkusMain", file=sys.stderr)
        return 1

    refuse = FIX / "trivial-boot-main-refuses-quarkusmain"
    proc = run(str(refuse / "dest"), "--legacy", str(refuse / "legacy"))
    blob = proc.stdout + proc.stderr
    if proc.returncode != 1:
        print("FAIL: trivial dest @QuarkusMain must REFUSE: %s" % blob, file=sys.stderr)
        return 1
    if "TRIVIAL_QUARKUSMAIN" not in blob or "Application.java" not in blob:
        print("FAIL: refuse detail missing: %s" % blob, file=sys.stderr)
        return 1

    ok = FIX / "custom-startup-permits-quarkusmain"
    proc = run(str(ok / "dest"), "--legacy", str(ok / "legacy"))
    if proc.returncode != 0:
        print(
            "FAIL: CommandLineRunner legacy must PASS: %s%s"
            % (proc.stdout, proc.stderr),
            file=sys.stderr,
        )
        return 1

    idle = FIX / "trivial-boot-main-plain-class-idles"
    proc = run(str(idle / "dest"), "--legacy", str(idle / "legacy"))
    blob = proc.stdout + proc.stderr
    if proc.returncode != 0 or "idle" not in blob:
        print("FAIL: no dest @QuarkusMain must idle: %s" % blob, file=sys.stderr)
        return 1

    print("OK: assert-no-trivial-quarkusmain (refuse trivial / pass custom / idle)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
