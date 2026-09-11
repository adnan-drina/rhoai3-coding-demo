#!/usr/bin/env python3
"""amend-scope selftest: a card widens its write set only on the record, and
only so far."""
from __future__ import annotations

import json
import shutil
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
    "schema": "rhoai3.batch-scope/v3",
    "rule": "spring-data-repository-contract/v1",
    "cluster": "c:abc",
    "repository": "src/main/java/p/VetRepository.java",
    "members": [{"member": "findByLastName", "signature": "findByLastName(java.lang.String)"}],
    # what the repository reached WHEN THE CARD WAS SEALED
    "reaches": ["java.util.List<p.Vet>", "java.lang.String"],
    "measured": ["rt:package:1"],
}

SOURCES = {
    # the repository the card is issued for, and the entity its queries reach
    "src/main/java/p/VetRepository.java":
        "package p;\nimport java.util.List;\npublic interface VetRepository {\n"
        "    List<Vet> findByLastName(String lastName);\n}\n",
    "src/main/java/p/Vet.java": "package p;\npublic class Vet { public String lastName; }\n",
    # a file with no bearing on the failure at all
    "src/main/java/p/SecurityConfig.java": "package p;\npublic class SecurityConfig { boolean enabled = true; }\n",
    "src/main/java/p/Pet.java": "package p;\npublic class Pet {}\n",
    "src/main/java/p/Owner.java": "package p;\npublic class Owner {}\n",
    "src/test/java/p/VetTest.java": "package p;\npublic class VetTest {}\n",
}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(root: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(HERE / "amend-scope.py"), "--root", str(root),
                        "--cluster", "c:abc", *args], capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def main() -> int:
    if not shutil.which("javac"):
        print("SKIP: amend-scope selftest needs a JDK on PATH")
        return 0
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _git(root, "init", "-q")
        _git(root, "config", "user.email", "t@t")
        _git(root, "config", "user.name", "t")
        scope = dict(SCOPE)
        scope["digest"] = batch_scope_digest(scope)
        sp = root / "evidence/planning/batch-scope/c-abc" / ("%s.json" % scope["digest"][:32])
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(scope))
        (root / ".hermes").mkdir(parents=True, exist_ok=True)
        (root / ".hermes/pins.json").write_text('{"pins":{"quarkus_platform":{"java_release":21}}}')
        for rel, text in SOURCES.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text)
        (root / "pom.xml").write_text("<project/>\n")
        issued = root / "verification/loop/issued.json"
        issued.parent.mkdir(parents=True, exist_ok=True)

        def reset(digest: str = "") -> None:
            issued.write_text(json.dumps({
                "schema": "rhoai3.loop-issued/v1", "cluster": "c:abc", "attempt": 1,
                "write_set": ["src/main/java/p/VetRepository.java"],
                "batch_scope": {"path": sp.relative_to(root).as_posix(),
                                "digest": digest or scope["digest"]},
            }))

        reset()
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "base")

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

        # a file the failure does not reach is a planning answer, however
        # well the ask is worded
        rc, out = _run(root, "--path", "src/main/java/p/SecurityConfig.java",
                       "--reason", "This unrelated security file would be useful to edit")
        if rc == 0 or "bears no relation" not in out:
            return _fail("an unrelated file must refuse however long the reason: %s" % out)

        # authority is granted BEFORE the change, never after it
        (root / "src/main/java/p/Vet.java").write_text("package p;\npublic class Vet { public String lastName; public int id; }\n")
        rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", "findByLastName needs Vet.lastName")
        if rc == 0 or "already been edited" not in out:
            return _fail("a file that is already edited cannot be authorized retrospectively: %s" % out)
        _git(root, "checkout", "--", "src/main/java/p/Vet.java")

        rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", "findByLastName needs Vet.lastName")
        if rc != 0:
            return _fail("a justified amendment of a file the repository reaches must pass: %s" % out)
        doc = json.loads(issued.read_text())
        if doc["write_set"] != ["src/main/java/p/Vet.java", "src/main/java/p/VetRepository.java"]:
            return _fail("the amended path must become writable: %s" % doc["write_set"])
        a = (doc.get("amendments") or [{}])[0]
        if a.get("path") != "src/main/java/p/Vet.java" or not a.get("reason") or not a.get("granted_before_sha256"):
            return _fail("the amendment must record its reason and the state it authorized: %s" % a)
        if a.get("dirty_at_grant") is not False or not a.get("locus"):
            return _fail("the amendment must record that the file was clean and why it is in scope: %s" % a)
        if json.loads(sp.read_text()) != scope:
            return _fail("the sealed inventory must not be rewritten by an amendment")
        rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", "findByLastName needs Vet.lastName")
        if rc != 0 or "already writable" not in out:
            return _fail("re-amending the same path is a no-op, not a second amendment")

        # a relationship the CANDIDATE introduced grants nothing: the worker
        # adds a reference to SecurityConfig inside the writable repository and
        # asks again
        (root / "src/main/java/p/VetRepository.java").write_text(
            "package p;\nimport java.util.List;\npublic interface VetRepository {\n"
            "    List<Vet> findByLastName(String lastName);\n"
            "    SecurityConfig config();\n}\n")
        rc, out = _run(root, "--path", "src/main/java/p/SecurityConfig.java",
                       "--reason", "the repository now mentions SecurityConfig directly")
        if rc == 0 or "did not reach" not in out:
            return _fail("a reference the repair itself wrote must not authorize anything: %s" % out)
        _git(root, "checkout", "--", "src/main/java/p/VetRepository.java")

        # an inventory with no sealed reachability cannot show anything is in
        # scope, and says so rather than falling back to the current tree
        no_reach = {k: v for k, v in scope.items() if k not in ("reaches", "digest")}
        no_reach["schema"] = "rhoai3.batch-scope/v2"
        no_reach["digest"] = batch_scope_digest(no_reach)
        old_sp = sp
        sp2 = root / "evidence/planning/batch-scope/c-abc" / ("%s.json" % no_reach["digest"][:32])
        sp2.write_text(json.dumps(no_reach))
        issued.write_text(json.dumps({
            "schema": "rhoai3.loop-issued/v1", "cluster": "c:abc", "attempt": 1,
            "write_set": ["src/main/java/p/VetRepository.java"],
            "batch_scope": {"path": sp2.relative_to(root).as_posix(), "digest": no_reach["digest"]},
        }))
        rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", "findByLastName needs Vet.lastName")
        if rc == 0 or "sealed reachability" not in out:
            return _fail("an inventory without sealed reachability must refuse, not fall back: %s" % out)
        sp = old_sp

        # a broken seal refuses before anything else is considered
        reset(digest="deadbeef" * 8)
        rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", "findByLastName needs Vet.lastName")
        if rc == 0 or "not the one sealed" not in out:
            return _fail("a broken seal must refuse the amendment: %s" % out)

    print("OK: amend-scope (tests, the build file, unknown paths, unreasoned asks and files the failure does not reach "
          "all refuse; a reference the repair itself introduced authorizes nothing and an inventory with no sealed reachability refuses outright; a file that is already edited cannot be authorized after the fact; a justified amendment widens "
          "the issued write set on the record, naming what it authorized, without rewriting the seal; a broken seal refuses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
