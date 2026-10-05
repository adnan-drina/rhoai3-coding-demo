#!/usr/bin/env python3
"""diagnose selftest: an investigation is bounded, writes nothing, and
discharges nothing."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _loop_common import ensure_hermes_lib  # noqa: E402

ensure_hermes_lib()

FAILURE = "rt:package:583bde63a"
WORKLIST = {
    "schema": "rhoai3.worklist/v1",
    "unlocatable": [{"id": FAILURE, "kind": "unlocatable", "gate": "package",
                     "cause": "unsupported-spel",
                     "detail": "SpEL expressions are not supported when using @Value"}],
}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(root: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(HERE / "diagnose.py"), "--root", str(root), *args],
                       capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


CLOSE = ("--close", "--conclusion", "DECISION_REQUIRED",
         "--investigated", "grepped the tree for the offending value and read the extension docs",
         "--finding", "the SpEL @Value lives in RootRestController and the platform implements none",
         "--proposed-action", "an ADR choosing a replacement for the servlet context path")


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _git(root, "init", "-q")
        _git(root, "config", "user.email", "t@t")
        _git(root, "config", "user.name", "t")
        (root / "evidence/planning").mkdir(parents=True)
        (root / "evidence/planning/worklist.json").write_text(json.dumps(WORKLIST))
        (root / "src/main/java").mkdir(parents=True)
        (root / "src/main/java/A.java").write_text("class A {}\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "base")

        rc, out = _run(root, "--list")
        if rc != 0 or FAILURE not in out or "0/2" not in out:
            return _fail("--list must name the failure and what has been spent: %s" % out)
        rc, out = _run(root, "--failure", "rt:nope", "--open")
        if rc == 0:
            return _fail("an unknown failure must refuse")
        rc, out = _run(root, "--failure", FAILURE, *CLOSE)
        if rc == 0 or "no attempt is open" not in out:
            return _fail("closing without an open attempt must refuse: %s" % out)

        rc, out = _run(root, "--failure", FAILURE, "--open")
        if rc != 0 or "attempt 1 of 2" not in out:
            return _fail("the first attempt must open: %s" % out)
        rc, out = _run(root, "--failure", FAILURE, "--open")
        if rc == 0 or "already open" not in out:
            return _fail("two attempts must not be open at once: %s" % out)
        rc, out = _run(root, "--failure", FAILURE, "--close", "--conclusion", "SOLVED",
                       "--investigated", "x" * 20, "--finding", "y" * 20, "--proposed-action", "z" * 20)
        if rc == 0 or "--conclusion must be one of" not in out:
            return _fail("the conclusion vocabulary is closed: %s" % out)
        rc, out = _run(root, "--failure", FAILURE, "--close", "--conclusion", "LOCATED",
                       "--investigated", "looked at the thing", "--finding", "short", "--proposed-action", "z" * 20)
        if rc == 0:
            return _fail("an empty finding must refuse")

        # an investigation that edited the product cannot close
        (root / "src/main/java/A.java").write_text("class A { int x; }\n")
        rc, out = _run(root, "--failure", FAILURE, *CLOSE)
        if rc == 0 or "an investigation reads" not in out:
            return _fail("editing the product during an investigation must refuse: %s" % out)
        rec = json.loads((root / "evidence/diagnosis/rt-package-583bde63a/1.json").read_text())
        if not any(e.get("event") == "refused" for e in rec["events"]):
            return _fail("the refusal must be on the record")
        _git(root, "checkout", "--", "src/main/java/A.java")

        rc, out = _run(root, "--failure", FAILURE, *CLOSE)
        if rc != 0 or "DECISION_REQUIRED" not in out or "nothing was discharged" not in out:
            return _fail("a clean close must record the conclusion and discharge nothing: %s" % out)
        rec = json.loads((root / "evidence/diagnosis/rt-package-583bde63a/1.json").read_text())
        kinds = [e["event"] for e in rec["events"]]
        if kinds != ["open", "refused", "close"]:
            return _fail("the record is append-only: %s" % kinds)
        close = rec["events"][-1]
        if close["discharges"] != [] or close["identity"]["failure"] != FAILURE:
            return _fail("a conclusion discharges nothing and names its failure")

        # the deadline makes the conclusion, not the investigator
        rec["events"][0]["deadline_epoch"] = int(time.time()) - 1
        p2 = root / "evidence/diagnosis/rt-package-583bde63a/2.json"
        p2.write_text(json.dumps({"schema": "rhoai3.diagnosis-attempt/v1", "attempt": 2,
                                  "events": [dict(rec["events"][0], attempt=2)]}))
        rc, out = _run(root, "--failure", FAILURE, *CLOSE)
        if rc != 0 or "INCONCLUSIVE" not in out:
            return _fail("a close past the deadline is INCONCLUSIVE whatever it found: %s" % out)
        if "no attempts left" not in out:
            return _fail("the last attempt must say the failure now needs a decision: %s" % out)

        rc, out = _run(root, "--failure", FAILURE, "--open")
        if rc == 0 or "a third is not a longer look" not in out:
            return _fail("a third attempt must refuse: %s" % out)

    print("OK: diagnose (bounded at two attempts of ten minutes; a closed conclusion vocabulary; an edit to the "
          "product during an investigation refuses and is recorded; the deadline decides INCONCLUSIVE; the record "
          "is append-only; nothing is ever discharged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
