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
    # a declaration closure: the surface others are bound to, one implementer
    # and one caller. A unit seals the surface; the other two are what a
    # revision may reach, and only on evidence.
    "src/main/java/p/ClinicService.java":
        "package p;\npublic interface ClinicService {\n    Vet lookup(int id);\n}\n",
    "src/main/java/p/ClinicServiceImpl.java":
        "package p;\npublic class ClinicServiceImpl implements ClinicService {\n"
        "    public Vet lookup(int id) { return null; }\n}\n",
    "src/main/java/p/Caller.java":
        "package p;\npublic class Caller {\n    ClinicService s;\n    public Vet go() { return s.lookup(1); }\n}\n",
}

# The sealed v4 unit: the declaration surface, its symbols, its members. The
# inventory is what a revision is checked against, never the tree as the
# candidate has left it.
UNIT_SCOPE = {
    "schema": "rhoai3.batch-scope/v4",
    "kind": "unit",
    "rule": "unit/declaration-closure/v1",
    "cluster": "u:abc123",
    "unit_id": "u:abc123",
    "family_key": "p.ClinicService",
    "writable_paths": ["src/main/java/p/ClinicService.java"],
    "symbols": [{"kind": "member", "fqn": "p.ClinicService", "signature": "lookup(int)",
                 "path": "src/main/java/p/ClinicService.java"}],
    "target_symbols": [],
    "members": [{"path": "src/main/java/p/ClinicService.java", "type": "p.ClinicService",
                 "member_id": "lookup", "state": "declares", "signature": "lookup(int)"}],
    "measured": ["err:1"],
}

UNIT_WORKLIST = {
    "schema": "rhoai3.worklist/v1",
    "items": [{"id": "err:1", "source": "javac", "kind": "compile", "category": "mandatory",
               "identity": "diag:impl|cant.resolve|aaaa",
               "path": "src/main/java/p/ClinicServiceImpl.java", "line": 3,
               "rule_id": "compiler.err.cant.resolve.location",
               "message": "cannot find symbol\n  symbol:   class Vet\n  location: class p.ClinicServiceImpl"}],
    "clusters": [],
}


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(root: Path, *args: str, cluster: str = "c:abc") -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(HERE / "amend-scope.py"), "--root", str(root),
                        "--cluster", cluster, *args], capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def _unit_case(root: Path) -> int:
    """A UNIT's scope is revised on EVIDENCE, bounded by the rule that formed
    it, and recorded as a revision beside the amendment."""
    from planner.worklist import UNIT_MAX_FILES

    scope = dict(UNIT_SCOPE)
    scope["digest"] = batch_scope_digest(scope)
    sp = root / "evidence/planning/batch-scope/u-abc123" / ("%s.json" % scope["digest"][:32])
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(scope))
    wl = root / "evidence/planning/worklist.json"
    wl.parent.mkdir(parents=True, exist_ok=True)
    wl.write_text(json.dumps(UNIT_WORKLIST))
    issued = root / "verification/loop/issued.json"

    def reset(write_set: list | None = None) -> None:
        issued.write_text(json.dumps({
            "schema": "rhoai3.loop-issued/v1", "cluster": "u:abc123", "attempt": 1,
            "write_set": list(write_set or scope["writable_paths"]),
            "retry_key": "rk:unit:u:abc123",
            "batch_scope": {"path": sp.relative_to(root).as_posix(), "digest": scope["digest"]},
        }))

    impl = "src/main/java/p/ClinicServiceImpl.java"
    caller = "src/main/java/p/Caller.java"

    reset()
    # prose alone stops being sufficient for a unit
    rc, out = _run(root, "--path", impl, "--reason", "the implementer must move with the surface", cluster="u:abc123")
    if rc == 0 or "revised on evidence" not in out:
        return _fail("a unit revision with no evidence must refuse: %s" % out)
    # an evidence kind nobody states is not evidence
    rc, out = _run(root, "--path", impl, "--reason", "the implementer must move with the surface",
                   "--evidence", "vibes:it feels right", cluster="u:abc123")
    if rc == 0 or "must be <kind>:<ref>" not in out:
        return _fail("an unknown evidence kind must refuse: %s" % out)
    # a STALE identity is justified by nothing: nobody reports it any more
    rc, out = _run(root, "--path", impl, "--reason", "the implementer must move with the surface",
                   "--evidence", "javac:diag:gone|x|y", cluster="u:abc123")
    if rc == 0 or "justified by nothing" not in out:
        return _fail("an identity the work list does not carry must refuse: %s" % out)
    # a symbol the unit never sealed is not a relation about this card
    rc, out = _run(root, "--path", impl, "--reason", "the implementer must move with the surface",
                   "--evidence", "model:p.SecurityConfig", cluster="u:abc123")
    if rc == 0 or "not a symbol this unit sealed" not in out:
        return _fail("the model may only be cited about what the card sealed: %s" % out)
    # a file the sealed symbols do not reach refuses however good the evidence
    rc, out = _run(root, "--path", "src/main/java/p/SecurityConfig.java",
                   "--reason", "this unrelated security file would help", "--evidence", "model:p.ClinicService",
                   cluster="u:abc123")
    if rc == 0 or "sealed symbols do not reach" not in out:
        return _fail("evidence is not a locus: %s" % out)
    # a test source and the build file are refused on a unit card too
    rc, out = _run(root, "--path", "src/test/java/p/VetTest.java", "--reason", "the test names the old surface",
                   "--evidence", "model:p.ClinicService", cluster="u:abc123")
    if rc == 0 or "test source is never writable" not in out:
        return _fail("a test source is never writable, for any unit, for any evidence: %s" % out)
    rc, out = _run(root, "--path", "pom.xml", "--reason", "the extension is missing",
                   "--evidence", "model:p.ClinicService", cluster="u:abc123")
    if rc == 0:
        return _fail("the dependency gap is the next card, never a wider unit: %s" % out)

    # a TOOL-NAMED javac identity the current work list carries, at a file that
    # implements the sealed declaration: accepted, and recorded as a revision
    rc, out = _run(root, "--path", impl, "--reason", "the implementer must move with the surface",
                   "--evidence", "javac:diag:impl|cant.resolve|aaaa", cluster="u:abc123")
    if rc != 0 or "SCOPE REVISED" not in out:
        return _fail("a tool-named revision of a file the unit reaches must pass: %s" % out)
    doc = json.loads(issued.read_text())
    if impl not in (doc.get("write_set") or []):
        return _fail("the revised path must become writable: %s" % doc.get("write_set"))
    rev = (doc.get("revisions") or [{}])[0]
    if rev.get("path") != impl or (rev.get("evidence") or {}).get("ref") != "diag:impl|cant.resolve|aaaa":
        return _fail("the revision must record the evidence it cites: %s" % rev)
    if not rev.get("locus") or "implements" not in rev["locus"]:
        return _fail("and why the file is in the unit's scope: %s" % rev)
    if rev.get("unit_id") != "u:abc123":
        return _fail("the revision belongs to the unit, so the budget does not move: %s" % rev)
    amd = (doc.get("amendments") or [{}])[0]
    if not amd.get("granted_before_sha256") or amd.get("dirty_at_grant") is not False:
        return _fail("a revision is still an amendment: authority before the file moves: %s" % amd)
    if json.loads(sp.read_text()) != scope:
        return _fail("the sealed inventory must not be rewritten by a revision")

    # a CALLER of the sealed member reaches it too, on a model relation
    rc, out = _run(root, "--path", caller, "--reason", "the caller is bound to the sealed signature",
                   "--evidence", "model:p.ClinicService#lookup", cluster="u:abc123")
    if rc != 0 or "SCOPE REVISED" not in out:
        return _fail("a caller of a sealed member is inside the unit: %s" % out)

    # FOUR revisions, and no more: the fifth is a planning answer
    reset(write_set=scope["writable_paths"] + [impl, caller])
    doc = json.loads(issued.read_text())
    doc["amendments"] = [{"path": "x%d" % i} for i in range(4)]
    issued.write_text(json.dumps(doc))
    rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", "one more collaborator",
                   "--evidence", "model:p.ClinicService", cluster="u:abc123")
    if rc == 0 or "already been amended 4 time(s) (limit 4)" not in out:
        return _fail("a unit is revised four times and no more: %s" % out)

    # and never past the size rule that FORMED it: an amendment may not build
    # by hand the card the former declined to mint
    reset(write_set=["src/main/java/p/Filler%d.java" % i for i in range(UNIT_MAX_FILES)])
    rc, out = _run(root, "--path", impl, "--reason", "the implementer must move with the surface",
                   "--evidence", "model:p.ClinicService", cluster="u:abc123")
    if rc == 0 or "UNIT_OVERSIZE" not in out:
        return _fail("a revision past the former's own bound must refuse by name: %s" % out)
    return 0


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

        if _unit_case(root):
            return 1

    print("OK: amend-scope (tests, the build file, unknown paths, unreasoned asks and files the failure does not reach "
          "all refuse; a reference the repair itself introduced authorizes nothing and an inventory with no sealed reachability refuses outright; a file that is already edited cannot be authorized after the fact; a justified amendment widens "
          "the issued write set on the record, naming what it authorized, without rewriting the seal; a broken seal refuses). "
          "UNIT REVISIONS: prose alone, an unknown evidence kind, a stale javac identity and a model relation about a "
          "symbol the unit never sealed all refuse; evidence is not a locus, and a test source and the build file stay "
          "refused for any unit and any evidence; a tool-named identity at a file that implements the sealed "
          "declaration, and a model relation at a file that calls the sealed member, are accepted and recorded as "
          "revisions[] carrying the evidence and the locus, with the inventory, the unit_id and the budget untouched; "
          "four revisions and no more, and never past the size rule that formed the unit (UNIT_OVERSIZE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
