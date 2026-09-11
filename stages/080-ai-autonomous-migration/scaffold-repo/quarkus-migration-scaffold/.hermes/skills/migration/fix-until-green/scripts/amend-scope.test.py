#!/usr/bin/env python3
"""amend-scope selftest: a card widens its write set only on the record, and
only so far."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _loop_common import ensure_hermes_lib  # noqa: E402

ensure_hermes_lib()
from planner.worklist import batch_scope_digest  # noqa: E402

SCOPE = {
    "schema": "rhoai3.batch-scope/v1",
    "rule": "spring-data-repository-contract/v1",
    "cluster": "c:abc",
    "repository": "src/main/java/p/VetRepository.java",
    "members": [{"member": "findByLastName", "signatures": ["findByLastName(String)"], "ambiguous": False, "source_refs": []}],
    "measured": ["rt:package:1"],
}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(root: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(HERE / "amend-scope.py"), "--root", str(root),
                        "--cluster", "c:abc", *args], capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        scope = dict(SCOPE)
        scope["digest"] = batch_scope_digest(scope)
        sp = root / "evidence/planning/batch-scope/c-abc.json"
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(scope))
        for rel in ("src/main/java/p/VetRepository.java", "src/main/java/p/Vet.java",
                    "src/main/java/p/Pet.java", "src/main/java/p/Owner.java",
                    "src/test/java/p/VetTest.java", "pom.xml"):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text("x")
        issued = root / "verification/loop/issued.json"
        issued.parent.mkdir(parents=True, exist_ok=True)

        def reset(digest: str = "") -> None:
            issued.write_text(json.dumps({
                "schema": "rhoai3.loop-issued/v1", "cluster": "c:abc", "attempt": 1,
                "write_set": ["src/main/java/p/VetRepository.java"],
                "batch_scope": {"path": "evidence/planning/batch-scope/c-abc.json",
                                "digest": digest or scope["digest"]},
            }))

        reset()
        rc, out = _run(root, "--path", "src/test/java/p/VetTest.java", "--reason", "the test needs a new name")
        if rc == 0 or "test source is never writable" not in out:
            return _fail("a test source is never amendable: %s" % out)
        rc, out = _run(root, "--path", "pom.xml", "--reason", "a dependency is missing here")
        if rc == 0:
            return _fail("the build file is never an amendment: %s" % out)
        rc, out = _run(root, "--path", "src/main/java/p/Nope.java", "--reason", "it would be useful to me")
        if rc == 0:
            return _fail("a path that is not a file of the tree must refuse")
        rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", "short")
        if rc == 0 or "--reason" not in out:
            return _fail("an amendment without a stated reason must refuse")

        rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", "findByLastName needs Vet.lastName")
        if rc != 0:
            return _fail("a justified amendment of a main source must pass: %s" % out)
        doc = json.loads(issued.read_text())
        if doc["write_set"] != ["src/main/java/p/Vet.java", "src/main/java/p/VetRepository.java"]:
            return _fail("the amended path must become writable: %s" % doc["write_set"])
        if [a["path"] for a in doc["amendments"]] != ["src/main/java/p/Vet.java"] or not doc["amendments"][0]["reason"]:
            return _fail("the amendment must be on the record with its reason: %s" % doc.get("amendments"))
        if json.loads(sp.read_text()) != scope:
            return _fail("the sealed inventory must not be rewritten by an amendment")
        rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", "findByLastName needs Vet.lastName")
        if rc != 0 or "already writable" not in out:
            return _fail("re-amending the same path is a no-op, not a second amendment")

        rc, _ = _run(root, "--path", "src/main/java/p/Pet.java", "--reason", "the return type moved to Pet")
        if rc != 0:
            return _fail("the second amendment is within the limit")
        rc, out = _run(root, "--path", "src/main/java/p/Owner.java", "--reason", "and this one too, honestly")
        if rc == 0 or "limit" not in out:
            return _fail("a third amendment must refuse and say the cluster is wrong: %s" % out)

        # a card whose seal does not match the inventory cannot amend anything
        reset(digest="0" * 64)
        rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", "findByLastName needs Vet.lastName")
        if rc == 0 or "not the one sealed" not in out:
            return _fail("a broken seal must refuse the amendment: %s" % out)

    print("OK: amend-scope (tests, the build file, unknown paths and unreasoned asks refuse; a justified main-source "
          "amendment widens the issued write set on the record without rewriting the seal; bounded at two; a broken seal refuses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
