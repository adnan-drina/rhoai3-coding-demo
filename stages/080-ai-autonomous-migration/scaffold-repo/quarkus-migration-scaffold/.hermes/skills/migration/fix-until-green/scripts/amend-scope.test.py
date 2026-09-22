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
    # a fragment parent nothing implements, and the repository that extends it:
    # the unit that OWES a file nobody has written yet
    "src/main/java/p/VetHistory.java":
        "package p;\nimport java.util.List;\npublic interface VetHistory {\n"
        "    List<Vet> lookupByCustomClause(String clause);\n}\n",
    "src/main/java/p/VetStore.java":
        "package p;\npublic interface VetStore extends VetHistory {\n}\n",
}

# The sealed unit that owes an implementation: the obligation names the parent,
# the type and the file the naming contract fixes for it. Nothing else can make
# a path that does not exist admissible.
OWED_SCOPE = {
    "schema": "rhoai3.batch-scope/v4",
    "kind": "unit",
    "rule": "unit/declaration-closure/v1",
    "cluster": "u:owed01",
    "unit_id": "u:owed01",
    "family_key": "spring-data-fragment-implementations:p.VetHistory",
    "writable_paths": ["src/main/java/p/VetHistory.java"],
    "symbols": [{"kind": "member", "fqn": "p.VetHistory", "signature": "lookupByCustomClause(java.lang.String)",
                 "path": "src/main/java/p/VetHistory.java"}],
    "target_symbols": [],
    "members": [{"path": "src/main/java/p/VetHistory.java", "type": "p.VetHistory",
                 "member_id": "lookupByCustomClause", "state": "declares",
                 "signature": "lookupByCustomClause(java.lang.String)"},
                {"path": "src/main/java/p/VetStore.java", "type": "p.VetStore", "state": "implements",
                 "parent": "p.VetHistory"}],
    "implementation_obligations": [{
        "parent": "p.VetHistory", "parent_path": "src/main/java/p/VetHistory.java",
        "type": "p.VetHistoryImpl", "path": "src/main/java/p/VetHistoryImpl.java",
        "members": ["lookupByCustomClause(java.lang.String)"],
        "contract": "spring-data-fragment-impl/v1", "source": "the fragment naming contract",
    }],
    "measured": ["rt:boot:setwide"],
}

OWED_WORKLIST = {
    "schema": "rhoai3.worklist/v1",
    "items": [{"id": "rt:boot:setwide", "source": "runtime", "gate": "boot", "kind": "config",
               "cause": "missing-implementation", "set_wide": "spring-data-fragment-implementations",
               "category": "mandatory", "path": "", "line": 0,
               "rule_id": "RUNTIME_APPLICATION_CONFIGURATION",
               "message": "No implementation of interface p.VetHistory was found"}],
    "clusters": [],
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


def _owed_case(root: Path) -> int:
    """A path the unit is OWED is authorized BEFORE it exists, from the seal's
    own obligation and naming contract — and from nothing else.

    This is the defect the architect reproduced: a card whose whole purpose is
    to write an adapter could not put that adapter in its write set, because
    the model has no type for a file nobody has written. The promise the path
    was authorized on is checked once the file exists."""
    from planner.worklist import UNIT_MAX_FILES

    scope = dict(OWED_SCOPE)
    scope["digest"] = batch_scope_digest(scope)
    sp = root / "evidence/planning/batch-scope/u-owed01" / ("%s.json" % scope["digest"][:32])
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(scope))
    wl = root / "evidence/planning/worklist.json"
    wl.parent.mkdir(parents=True, exist_ok=True)
    wl.write_text(json.dumps(OWED_WORKLIST))
    issued = root / "verification/loop/issued.json"
    owed = "src/main/java/p/VetHistoryImpl.java"

    def reset(write_set: list | None = None) -> None:
        issued.write_text(json.dumps({
            "schema": "rhoai3.loop-issued/v1", "cluster": "u:owed01", "attempt": 2,
            "write_set": list(write_set or scope["writable_paths"]),
            "retry_key": "rk:unit:u:owed01", "budget": {"spent": 2, "max": 3},
            "idempotency_key": "k4:t_owed:1",
            "batch_scope": {"path": sp.relative_to(root).as_posix(), "digest": scope["digest"]},
        }))

    reset()
    # a new path the seal does NOT name is still refused: an obligation is what
    # authorizes a file that does not exist, never a request for one
    rc, out = _run(root, "--path", "src/main/java/p/Invented.java", "--reason", "I would like to write this adapter",
                   "--evidence", "model:p.VetHistory", cluster="u:owed01")
    if rc == 0 or "records no implementation obligation" not in out:
        return _fail("a new path nobody owes must refuse: %s" % out)
    # and the owed path is authorized before it exists
    rc, out = _run(root, "--path", owed, "--reason", "the fragment parent is owed a concrete implementation",
                   "--evidence", "runtime:rt:boot:setwide", cluster="u:owed01")
    if rc != 0 or "SCOPE REVISED" not in out:
        return _fail("the path the unit owes must be authorized before creation: %s" % out)
    doc = json.loads(issued.read_text())
    if owed not in (doc.get("write_set") or []):
        return _fail("and become writable: %s" % doc.get("write_set"))
    amd = (doc.get("amendments") or [{}])[-1]
    if amd.get("granted_before_sha256") != "" or (amd.get("creates") or {}).get("parent") != "p.VetHistory":
        return _fail("the record says the file did not exist and what it must become: %s" % amd)
    if "obligation" not in (amd.get("locus") or "") and "owed" not in (amd.get("locus") or ""):
        return _fail("and why that authorized it: %s" % amd)
    # the BUDGET and the identity do not move: a revision is not a new problem
    if doc.get("retry_key") != "rk:unit:u:owed01" or doc.get("budget") != {"spent": 2, "max": 3}:
        return _fail("a revision keeps the unit's retry budget: %s" % {k: doc.get(k) for k in ("retry_key", "budget")})
    if doc.get("idempotency_key") != "k4:t_owed:1" or (doc.get("revisions") or [{}])[0].get("unit_id") != "u:owed01":
        return _fail("and its identity: %s" % {k: doc.get(k) for k in ("idempotency_key", "revisions")})
    if json.loads(sp.read_text()) != scope:
        return _fail("the sealed inventory is not rewritten by a revision")

    # AFTER creation the promise is a fact or it is not. An adapter that does
    # not implement the parent is named as such.
    (root / owed).write_text("package p;\npublic class VetHistoryImpl {\n}\n")
    rc, out = _run(root, "--path", owed, "--reason", "the fragment parent is owed a concrete implementation",
                   "--evidence", "runtime:rt:boot:setwide", cluster="u:owed01")
    if rc != 0 or "does not implement p.VetHistory" not in out:
        return _fail("an adapter that does not implement the parent is reported: %s" % out)
    (root / owed).write_text("package p;\nimport java.util.List;\n"
                             "public class VetHistoryImpl implements VetHistory {\n"
                             "    public List<Vet> lookupByCustomClause(String clause) { return List.of(); }\n}\n")
    rc, out = _run(root, "--path", owed, "--reason", "the fragment parent is owed a concrete implementation",
                   "--evidence", "runtime:rt:boot:setwide", cluster="u:owed01")
    if rc != 0 or "implements p.VetHistory" not in out:
        return _fail("and one that does is verified from the model: %s" % out)

    # the file bound governs an owed path exactly as it governs any other
    (root / owed).unlink()
    reset(write_set=["src/main/java/p/Filler%d.java" % i for i in range(UNIT_MAX_FILES)])
    rc, out = _run(root, "--path", owed, "--reason", "the fragment parent is owed a concrete implementation",
                   "--evidence", "runtime:rt:boot:setwide", cluster="u:owed01")
    if rc == 0 or "UNIT_OVERSIZE" not in out or "max %d" % UNIT_MAX_FILES not in out:
        return _fail("an owed path past the file bound refuses by name: %s" % out)
    return 0


def _owed_adapter_case(root: Path) -> int:
    """ADR-019: a harness adapter the seal OWES (contract path, type, template
    digest) is authorized before it exists, on a parity obligation the work
    list carries; once written, the file must declare the contract's type."""
    import response_adapters as ra

    owed = ra.adapter_path(ra.CORS)
    scope = {
        "schema": "rhoai3.batch-scope/v4", "kind": "unit", "rule": "unit/owed-adapter/v1",
        "cluster": "u:adapt01", "unit_id": "u:adapt01", "family_key": "source-cors-response-adapter/v1",
        "writable_paths": ["src/main/resources/application.properties"],
        "symbols": [{"kind": "property", "fqn": "rhoai3.source-cors", "path": "src/main/resources/application.properties"}],
        "target_symbols": [],
        "members": [{"path": "src/main/resources/application.properties", "type": "", "member_id": "", "occurrence": 0,
                     "state": "declares-property"}],
        "implementation_obligations": [dict(ra.contract(ra.CORS), parent="", parent_path="", members=[],
                                            verify="template", adapter=ra.CORS, properties=[])],
        "measured": ["parity:abc"],
    }
    scope["digest"] = batch_scope_digest(scope)
    sp = root / "evidence/planning/batch-scope/u-adapt01" / ("%s.json" % scope["digest"][:32])
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(scope))
    (root / "evidence/planning/worklist.json").write_text(json.dumps({"schema": "rhoai3.worklist/v1", "clusters": [], "items": [
        {"id": "parity:abc", "source": "parity", "gate": "parity", "kind": "config", "rule_id": "PARITY_CORS",
         "path": owed, "category": "mandatory", "line": 0, "owed": ra.contract(ra.CORS)}]}))
    issued = root / "verification/loop/issued.json"
    issued.write_text(json.dumps({
        "schema": "rhoai3.loop-issued/v1", "cluster": "u:adapt01", "attempt": 1,
        "write_set": list(scope["writable_paths"]),
        "batch_scope": {"path": sp.relative_to(root).as_posix(), "digest": scope["digest"]},
    }))
    other = ra.adapter_path(ra.MEDIA_TYPE)
    rc, out = _run(root, "--path", other, "--reason", "the media type adapter would help here too",
                   "--evidence", "parity:parity:abc", cluster="u:adapt01")
    if rc == 0 or "records no implementation obligation" not in out:
        return _fail("a CORS seal never authorizes the media-type adapter: %s" % out)
    rc, out = _run(root, "--path", owed, "--reason", "the CORS obligation is owed the source-preserving adapter",
                   "--evidence", "parity:parity:nope", cluster="u:adapt01")
    if rc == 0 or "no parity obligation" not in out:
        return _fail("a parity id the work list does not carry is no evidence: %s" % out)
    rc, out = _run(root, "--path", owed, "--reason", "the CORS obligation is owed the source-preserving adapter",
                   "--evidence", "parity:parity:abc", cluster="u:adapt01")
    if rc != 0 or "SCOPE REVISED" not in out:
        return _fail("the owed adapter path is authorized before it exists: %s" % out)
    amd = (json.loads(issued.read_text()).get("amendments") or [{}])[-1]
    if (amd.get("creates") or {}).get("template_sha256") != ra.template_sha256(ra.CORS) or "template" not in amd.get("locus", ""):
        return _fail("the record names the template the file must be: %s" % amd)
    (root / owed).parent.mkdir(parents=True, exist_ok=True)
    (root / owed).write_text("package io.rhoai3.migration.response;\npublic class SomethingElse {\n}\n")
    rc, out = _run(root, "--path", owed, "--reason", "the CORS obligation is owed the source-preserving adapter",
                   "--evidence", "parity:parity:abc", cluster="u:adapt01")
    if "instead" not in out:
        return _fail("a file that declares another type than the contract's is named: %s" % out)
    (root / owed).write_text("package io.rhoai3.migration.response;\npublic class SourceCorsResponseAdapter {\n}\n")
    rc, out = _run(root, "--path", owed, "--reason", "the CORS obligation is owed the source-preserving adapter",
                   "--evidence", "parity:parity:abc", cluster="u:adapt01")
    if rc != 0 or "the adapter its obligation names" not in out:
        return _fail("the contract's type at the contract's path is verified from the model: %s" % out)
    (root / owed).unlink()
    return 0


def _parity_body_case(root: Path) -> int:
    """H1b (v9 t_a755c0a1): a body difference produced outside the controller.
    A parity card with no sealed inventory reaches the producing file on its
    OWN parity obligation's evidence -- the planner's hinted locus, or a type
    its controller reaches -- and on nothing else."""
    files = {"src/main/java/p/web/OwnerCtl.java": "package p.web;\nimport p.Holder;\npublic class OwnerCtl {\n    public Holder get() { return null; }\n}\n",
             "src/main/java/p/Holder.java": "package p;\npublic class Holder {\n    public Pet pet;\n}\n"}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "parity fixture")
    ctl = "src/main/java/p/web/OwnerCtl.java"
    item = {"id": "parity:body1", "source": "parity", "gate": "parity", "kind": "parity", "rule_id": "PARITY",
            "path": ctl, "detail": "sc:read-owner: body aa vs bb",
            "advice": {"body_diff": {"summary": "order of pet.visits", "order_only": True, "locus_hints": []}}}
    wl = root / "evidence/planning/worklist.json"
    wl.write_text(json.dumps({"schema": "rhoai3.worklist/v1", "clusters": [], "items": [
        item, {"id": "parity:other", "source": "parity", "path": ctl, "detail": "body x vs y"}]}))
    issued = root / "verification/loop/issued.json"
    issued.write_text(json.dumps({"schema": "rhoai3.loop-issued/v1", "cluster": "c:par", "attempt": 1, "gate": "parity",
                                  "items": ["parity:body1"], "write_set": [ctl]}))
    reason = "the visits order is produced by the model getter"
    rc, out = _run(root, "--path", "src/main/java/p/Pet.java", "--reason", reason, cluster="c:par")
    if rc == 0 or "no sealed scope" not in out:
        return _fail("without parity evidence a parity card has nothing to amend: %s" % out)
    rc, out = _run(root, "--path", "src/main/java/p/Pet.java", "--reason", reason, "--evidence", "parity:parity:other", cluster="c:par")
    if rc == 0 or "not an obligation this card was issued" not in out:
        return _fail("another card's parity obligation is no evidence: %s" % out)
    rc, out = _run(root, "--path", "src/main/java/p/SecurityConfig.java", "--reason", reason, "--evidence", "parity:parity:body1", cluster="c:par")
    if rc == 0 or "does not reach" not in out:
        return _fail("a file the controller does not reach is refused: %s" % out)
    rc, out = _run(root, "--path", "src/main/java/p/Pet.java", "--reason", reason, "--evidence", "parity:parity:body1", cluster="c:par")
    if rc != 0 or "reaches p.Pet in 2 step" not in out:
        return _fail("the model file the controller reaches is authorized on parity evidence: %s" % out)
    doc = json.loads(issued.read_text())
    if "src/main/java/p/Pet.java" not in doc["write_set"] or doc["amendments"][-1]["evidence"]["kind"] != "parity":
        return _fail("the amendment is recorded with its parity evidence: %s" % doc)
    item["advice"]["body_diff"]["locus_hints"] = [{"path": "src/main/java/p/SecurityConfig.java", "member": "getX"}]
    wl.write_text(json.dumps({"schema": "rhoai3.worklist/v1", "clusters": [], "items": [item]}))
    rc, out = _run(root, "--path", "src/main/java/p/SecurityConfig.java", "--reason", reason, "--evidence", "parity:parity:body1", cluster="c:par")
    if rc != 0 or "hinted producer" not in out:
        return _fail("the planner's hinted locus is authorized: %s" % out)
    rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", reason, "--evidence", "parity:parity:body1", cluster="c:par")
    if rc == 0 or "limit 2" not in out:
        return _fail("a parity card is bounded like any card: %s" % out)
    # H11 (v9 t_0527c69b): the CONFIG locus. A navigation obligation's advice
    # names application.properties (quarkus.swagger-ui.*); the card reaches it
    # on that evidence -- and only on it: the same file for an obligation whose
    # advice names no property there is refused with the exact shape, and
    # pom.xml stays its own cluster
    props = "src/main/resources/application.properties"
    (root / props).parent.mkdir(parents=True, exist_ok=True)
    (root / props).write_text("quarkus.http.port=8080\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "props")
    nav_item = {"id": "parity:nav1", "source": "parity", "gate": "parity", "kind": "parity", "rule_id": "PARITY",
                "cause": "redirect-target-dead", "path": ctl, "detail": "ep: redirect target http://d/swagger-ui/index.html is dead (404)",
                "advice": {"config_locus": props, "navigation": [], "exit": ["THE FIX IS CONFIGURATION"],
                           "locus_hints": [{"path": props, "member": "quarkus.swagger-ui.always-include", "why": "the configuration locus"}]}}
    wl.write_text(json.dumps({"schema": "rhoai3.worklist/v1", "clusters": [], "items": [item, nav_item]}))
    issued.write_text(json.dumps({"schema": "rhoai3.loop-issued/v1", "cluster": "c:nav", "attempt": 1, "gate": "parity",
                                  "items": ["parity:nav1"], "write_set": [ctl]}))
    rc, out = _run(root, "--path", props, "--reason", "quarkus.swagger-ui.always-include=true puts the UI in the package",
                   "--evidence", "parity:parity:nav1", cluster="c:nav")
    if rc != 0 or "configuration locus" not in out or "never a handler" not in out:
        return _fail("the config file the navigation advice names is authorized on parity evidence: %s" % out)
    if props not in json.loads(issued.read_text())["write_set"]:
        return _fail("the amendment lands application.properties in the write set")
    rc, out = _run(root, "--path", "pom.xml", "--reason", "quarkus.swagger-ui.always-include=true puts the UI in the package",
                   "--evidence", "parity:parity:nav1", cluster="c:nav")
    if rc == 0 or "not a path a parity card may reach" not in out:
        return _fail("the build file is not the config locus: %s" % out)
    # the same file for an obligation whose advice names no property there: refused, with the exact shape
    issued.write_text(json.dumps({"schema": "rhoai3.loop-issued/v1", "cluster": "c:par", "attempt": 1, "gate": "parity",
                                  "items": ["parity:body1"], "write_set": [ctl]}))
    rc, out = _run(root, "--path", props, "--reason", "a property might help somewhere", "--evidence", "parity:parity:body1", cluster="c:par")
    if (rc == 0 or "REFUSE: SCOPE_AMENDMENT" not in out or "bears no relation to what this card measures" not in out
            or "advice names no property that lives there" not in out):
        return _fail("the config file is refused by name when the obligation's advice does not name it: %s" % out)
    return 0


def _parity_server_error_case(root: Path) -> int:
    """H5a (v9 c:67bfc8d7483e): a 5xx is thrown in the service or persistence
    layer behind the controller's interface. ONE rule for every parity item:
    the repository IMPLEMENTATION is reached through the interface the
    controller calls (an implementor is reached in the same step as its
    interface), and the file a server_error's product frame names is the
    hinted producer. A file the operation does not reach is still refused."""
    files = {"src/main/java/p/web/LedgerCtl.java": "package p.web;\nimport p.svc.LedgerService;\npublic class LedgerCtl {\n    LedgerService svc;\n    public void delete(int id) { svc.delete(id); }\n}\n",
             "src/main/java/p/svc/LedgerService.java": "package p.svc;\npublic interface LedgerService {\n    void delete(int id);\n}\n",
             "src/main/java/p/svc/LedgerServiceImpl.java": "package p.svc;\nimport p.repo.LedgerRepo;\npublic class LedgerServiceImpl implements LedgerService {\n    LedgerRepo repo;\n    public void delete(int id) { repo.delete(id); }\n}\n",
             "src/main/java/p/repo/LedgerRepo.java": "package p.repo;\npublic interface LedgerRepo {\n    void delete(int id);\n}\n",
             "src/main/java/p/repo/LedgerRepoImpl.java": "package p.repo;\npublic class LedgerRepoImpl implements LedgerRepo {\n    public void delete(int id) { throw new IllegalStateException(\"hql\"); }\n}\n"}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "server error fixture")
    ctl, repo_impl, svc_impl = "src/main/java/p/web/LedgerCtl.java", "src/main/java/p/repo/LedgerRepoImpl.java", "src/main/java/p/svc/LedgerServiceImpl.java"
    item = {"id": "parity:err1", "source": "parity", "gate": "parity", "kind": "parity", "rule_id": "PARITY",
            "path": ctl, "detail": "sc:delete-1: status 500 vs 204",
            "advice": {"server_error": {"status": 500, "expected_status": 204, "exception": "java.lang.IllegalStateException", "locus_hints": []}}}
    wl = root / "evidence/planning/worklist.json"
    issued = root / "verification/loop/issued.json"

    def reset() -> None:
        wl.write_text(json.dumps({"schema": "rhoai3.worklist/v1", "clusters": [], "items": [item]}))
        issued.write_text(json.dumps({"schema": "rhoai3.loop-issued/v1", "cluster": "c:err", "attempt": 1, "gate": "parity",
                                      "items": ["parity:err1"], "write_set": [ctl]}))

    reason = "the delete throws in the repository implementation"
    reset()
    # no body difference, no hint: the repository IMPLEMENTATION is reached through the interfaces the controller calls
    rc, out = _run(root, "--path", repo_impl, "--reason", reason, "--evidence", "parity:parity:err1", cluster="c:err")
    if rc != 0 or "reaches p.repo.LedgerRepoImpl in 2 step(s) as an implementor of p.repo.LedgerRepo" not in out:
        return _fail("a 5xx parity item reaches the persistence implementation behind the service interface: %s" % out)
    doc = json.loads(issued.read_text())
    if repo_impl not in doc["write_set"] or doc["amendments"][-1]["evidence"] != {"kind": "parity", "ref": "parity:err1", "tool_named": True}:
        return _fail("the amendment is recorded on the parity evidence: %s" % doc)
    rc, out = _run(root, "--path", "src/main/java/p/SecurityConfig.java", "--reason", reason, "--evidence", "parity:parity:err1", cluster="c:err")
    if rc == 0 or "does not reach" not in out or "implementors included" not in out:
        return _fail("a file the operation does not reach is refused, implementors included: %s" % out)
    # the runner's product frame is the hinted producer, whatever the reach says
    reset()
    item["advice"]["server_error"]["locus_hints"] = [{"path": svc_impl, "type": "p.svc.LedgerServiceImpl", "member": "delete", "line": 5}]
    reset()
    rc, out = _run(root, "--path", svc_impl, "--reason", reason, "--evidence", "parity:parity:err1", cluster="c:err")
    if rc != 0 or "is where parity:err1's server error is thrown (p.svc.LedgerServiceImpl.delete line 5)" not in out:
        return _fail("the server error's product frame is the hinted producer: %s" % out)
    # a runtime obligation's evidence kind is not a parity card's route; bounds stay the card's
    rc, out = _run(root, "--path", repo_impl, "--reason", reason, "--evidence", "parity:parity:err1", cluster="c:err")
    rc, out = _run(root, "--path", "src/main/java/p/Vet.java", "--reason", reason, "--evidence", "parity:parity:err1", cluster="c:err")
    if rc == 0 or "limit 2" not in out:
        return _fail("a parity card is bounded like any card: %s" % out)
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
        if _owed_case(root):
            return 1
        if _owed_adapter_case(root):
            return 1
        if _parity_body_case(root):
            return 1
        if _parity_server_error_case(root):
            return 1

    print("OK: amend-scope (tests, the build file, unknown paths, unreasoned asks and files the failure does not reach "
          "all refuse; a reference the repair itself introduced authorizes nothing and an inventory with no sealed reachability refuses outright; a file that is already edited cannot be authorized after the fact; a justified amendment widens "
          "the issued write set on the record, naming what it authorized, without rewriting the seal; a broken seal refuses). "
          "UNIT REVISIONS: prose alone, an unknown evidence kind, a stale javac identity and a model relation about a "
          "symbol the unit never sealed all refuse; evidence is not a locus, and a test source and the build file stay "
          "refused for any unit and any evidence; a tool-named identity at a file that implements the sealed "
          "declaration, and a model relation at a file that calls the sealed member, are accepted and recorded as "
          "revisions[] carrying the evidence and the locus, with the inventory, the unit_id and the budget untouched; "
          "four revisions and no more, and never past the size rule that formed the unit (UNIT_OVERSIZE). AN OWED PATH: "
          "a file that does not exist yet is authorized only when the seal records an implementation obligation "
          "and its naming contract, an invented one refuses, and the record says the file did not exist and what "
          "it must become; the unit's retry budget, idempotency key and sealed inventory do not move; once the "
          "file exists the promised relationship is verified from the model (an adapter that does not implement "
          "the parent is named as such); and the file bound still governs it. AN OWED ADAPTER (ADR-019): its contract "
          "path is authorized before it exists on a parity obligation the work list carries, never the other "
          "adapter's path, and once written it must declare the contract's type. H5a: a 5xx parity item reaches the "
          "persistence implementation behind the service interface the controller calls (implementors count as one "
          "step) and the product frame the runner recorded is the hinted producer; a file the operation does not "
          "reach stays refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
