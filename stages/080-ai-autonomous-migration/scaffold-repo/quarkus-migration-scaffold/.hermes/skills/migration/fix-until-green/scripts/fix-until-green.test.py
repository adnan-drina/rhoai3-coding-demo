#!/usr/bin/env python3
"""fix-until-green loop selftest (end to end on the http specimen; simulated tool outputs; real git).

Transaction: issued card → candidate identity → scope → measure → commit / revert.
Counterexamples kept from the 2026-09-09 review: invented cluster, post-verification
edit, out-of-scope (test) edit, staged edit, rejected reports, missing/failed tool
runs, line movement, unresolved test scope, deferral stops the loop.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE
GOLDEN = HERE.parents[4]
VERIFY = HERE / "verify.py"
ADVANCE = HERE / "advance.py"
REWIND = HERE / "rewind.py"
OPERATOR_STEP = HERE / "operator-step.py"
BRIEF = HERE / "brief.py"
BOOTSTRAP = GOLDEN / ".hermes" / "skills" / "migration" / "bootstrap-destination" / "scripts" / "bootstrap-destination.py"
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
sys.path.insert(0, str(GOLDEN / ".hermes" / "kernel"))
from k4_convert import convert_admitted  # noqa: E402
sys.path.insert(0, str(HERE))
from _loop_common import profile_keys_lost  # noqa: E402
from planner import pipeline, specimens  # noqa: E402
from planner.worklist import build_worklist  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, LOOP_DEFERRED, LOOP_ISSUED, LOOP_PENDING_FILES, LOOP_STATE, LOOP_STEPS, VERIFY_DIAGNOSTICS, VERIFY_RUN, WORKLIST  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("HERMES_KANBAN_TASK", None)
    return subprocess.run(argv, text=True, capture_output=True, env=env)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True).stdout


def _advance(root: Path, cluster: str, card: str) -> subprocess.CompletedProcess[str]:
    return _run([sys.executable, str(ADVANCE), "--root", str(root), "--cluster", cluster, "--card", card, "--no-mint"])


def _head(root: Path) -> dict:
    wl = load_json(root / WORKLIST)
    return next(c for c in wl["clusters"] if c["id"] == wl["head"])


def _profile_keys_cases() -> int:
    old = "# db\nquarkus.datasource.jdbc.url=jdbc:hsqldb:mem:x\nquarkus.datasource.username=sa\nspring.jpa.database=HSQL\nspring.datasource.password=pw\n"
    m = {"spring.datasource.password": "quarkus.datasource.password"}
    # deletion with nothing landed: every behavior-carrying key is lost; the unmapped Spring key is not
    lost = profile_keys_lost("hsqldb", old, "", "spring.profiles.active=hsqldb\n", m)
    if lost != ["quarkus.datasource.jdbc.url", "quarkus.datasource.username", "spring.datasource.password"]:
        return _fail("deleting a profile file must report its behavior-carrying keys as lost: %s" % lost)
    # the documented merge: %profile.key in application.properties (mapped name accepted)
    main = "%hsqldb.quarkus.datasource.jdbc.url=jdbc:hsqldb:mem:x\n%hsqldb.quarkus.datasource.username=sa\n%hsqldb.quarkus.datasource.password=pw\n"
    if profile_keys_lost("hsqldb", old, "", main, m):
        return _fail("keys landed as %profile.key (mapped) must not count as lost")
    # a bare key in application.properties also counts; keys kept in the file are not lost
    if profile_keys_lost("hsqldb", old, "quarkus.datasource.username=sa\n", "quarkus.datasource.jdbc.url=x\nquarkus.datasource.password=pw\n", m):
        return _fail("bare landing and kept keys must not count as lost")
    return 0


def _attempt_budget_case() -> int:
    """A cleared deferral raises the budget; it never deletes the attempts."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _loop_common import attempt_budget  # noqa: E402

    steps = {"attempts": {"c:x": 3}, "rejected": [{"cluster": "c:x", "card": "t_1"}], "deferral_clearances": []}
    if attempt_budget(steps, "c:x", 3) != 3:
        return _fail("with no clearance the budget is the decided limit")
    steps["deferral_clearances"].append({"cluster": "c:x", "attempts": 3, "cards": ["t_1"]})
    if attempt_budget(steps, "c:x", 3) != 6:
        return _fail("a clearance at 3 spent attempts must allow 3 more, not reset the counter")
    steps["deferral_clearances"].append({"cluster": "c:x", "attempts": 6, "cards": ["t_1"]})
    if attempt_budget(steps, "c:x", 3) != 9:
        return _fail("a second clearance moves the budget again: %d" % attempt_budget(steps, "c:x", 3))
    if attempt_budget(steps, "c:other", 3) != 3:
        return _fail("a clearance belongs to its own cluster")
    if steps["attempts"]["c:x"] != 3 or steps["rejected"][0]["card"] != "t_1":
        return _fail("the history must be untouched by the budget question")
    return 0


def _pending_classify_case() -> int:
    from _loop_common import classify_inconclusive  # noqa: E402

    if classify_inconclusive({"blocked": ["build unresolvable: missing version"]}, {}) != "environment":
        return _fail("unresolvable Maven is environment, not a product reject")
    if classify_inconclusive({"blocked": ["no surefire report was produced; tests unknown"]}, {}) != "harness":
        return _fail("missing Surefire is harness")
    if classify_inconclusive({"blocked": ["mystery"]}, {"mode": "diagnostic"}) != "harness":
        return _fail("diagnostic mode is harness")
    if classify_inconclusive({"blocked": ["something the classifier does not know"]}, {}) != "unresolved":
        return _fail("unknown blocked text stays unresolved")
    return 0


def _si1_case() -> int:
    """SI-1/v2: a member the SOURCE wrote with must still write.

    The rule the architect asked for, replacing a name-prefix veto that missed
    a fully-qualified @Query, borrowed @Modifying from a neighbour, and flagged
    a read called updatedPetById."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _loop_common import state_change_violations  # noqa: E402

    writes = {"save", "delete"}
    cases = {
        "fully-qualified @Query on a write": ('@org.springframework.data.jpa.repository.Query("SELECT u FROM User u")\n    void save(User u);', 1, 0),
        "a @Query carrying no statement": ("@Query\n    void save(User u);", 1, 0),
        "@Modifying on the PRECEDING member is not borrowed": ('@Modifying\n    @Query("UPDATE Pet p SET p.n = ?1")\n    void updateName(String n);\n\n    @Query("UPDATE User u SET u.id = u.id")\n    void save(User u);', 1, 0),
        "a documented modifying delete": ('@Modifying\n    @Query("DELETE FROM Pet p WHERE p.id = ?1")\n    void delete(Pet p);', 0, 0),
        "annotation order does not change the verdict": ('@Query("DELETE FROM Pet p WHERE p.id = ?1")\n    @Modifying\n    void delete(Pet p);', 0, 0),
        "a multi-line query argument": ('@Modifying\n    @Query(\n        "DELETE FROM Pet p WHERE p.id = ?1"\n    )\n    void delete(Pet p);', 0, 0),
        "a read whose name begins like a write": ('@Query("SELECT p FROM Pet p")\n    Pet updatedPetById(int id);', 0, 0),
        "an inherited write declares nothing": ("public interface R extends CrudRepository<User,Integer> { }", 0, 0),
        "an argument the rule cannot read": ("@Query(QUERIES.SAVE)\n    void save(User u);", 0, 1),
    }
    for name, (src, want_bad, want_unknown) in cases.items():
        bad, unknown = state_change_violations(src, writes)
        if len(bad) != want_bad or len(unknown) != want_unknown:
            return _fail("%s: %d violation(s) and %d inconclusive, wanted %d and %d" % (name, len(bad), len(unknown), want_bad, want_unknown))
    bad, _ = state_change_violations('@Query("SELECT u FROM User u")\n    void save(User u);', writes)
    if bad[0]["rule"] != "SI-1/v2" or "state change" not in bad[0]["detail"]:
        return _fail("the finding must name its rule and its contract: %s" % bad[0])
    return 0


_URI_MSG = "unreported exception java.net.URISyntaxException; must be caught or declared to be thrown"
_URI_CODE = "compiler.err.unreported.exception.need.to.catch.or.throw"
_URI_CONTROLLERS = ("OwnerRestController", "PetRestController", "PetTypeRestController",
                    "SpecialtyRestController", "VetRestController", "VisitRestController")


_FAMILY_CTL = (
    "package org.springframework.samples.petclinic.rest;\n"
    "import java.net.URI;\n"
    "public class %s {\n"
    "    static class Headers { void setLocation(URI u) { } }\n"
    "    static class Builder { URI build(int id) { return URI.create(\"/x/\" + id); } }\n"
    "    void add%s(int id, Builder b) {\n"
    "        Headers h = new Headers();\n"
    "        h.setLocation(%s);\n"
    "    }\n"
    "}\n"
)
_BUILDER = "b.build(id)"
_CTOR = 'new URI("/api/x/" + id)'
_REST = "src/main/java/org/springframework/samples/petclinic/rest/"


def _write_uri_controllers(root: Path, form: str) -> list[str]:
    paths: list[str] = []
    for name in _URI_CONTROLLERS:
        f = root / _REST / ("%s.java" % name)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(_FAMILY_CTL % (name, name.replace("RestController", ""), form), encoding="utf-8")
        paths.append(_REST + "%s.java" % name)
    return paths


def _issue_cluster(root: Path, cluster: dict, card: str) -> None:
    """What k4_convert records, for a named cluster (the head may be another)."""
    from planner.budget import budget

    wl = load_json(root / WORKLIST)
    ids = set(cluster.get("items") or [])
    steps = load_json(root / LOOP_STEPS)
    write_canonical(root / LOOP_ISSUED, {
        "schema": "rhoai3.loop-issued/v1", "cluster": cluster["id"], "kind": cluster.get("kind") or "compile", "attempt": 1,
        "idempotency_key": "k4:%s:test" % card, "receipt_sha256": "", "write_set": list(cluster.get("write_set") or []),
        "gate": str(cluster.get("gate") or ""), "items": list(cluster.get("items") or []), "gate_items": [],
        "batch_scope": dict(cluster.get("batch_scope") or {}), "retry_key": str(cluster.get("retry_key") or cluster["id"]),
        "budget": budget(steps, cluster["id"], str(cluster.get("retry_key") or cluster["id"]), 3),
        "item_identities": {str(i["id"]): str(i["identity"]) for i in wl["items"] if str(i["id"]) in ids and i.get("identity")},
        "task_id": card,
    })


def _checked_veto_case() -> int:
    """t_cef8a0f6: the compile count fell and the candidate had introduced an
    unhandled checked exception. The fall does not admit it."""
    from planner.paths import MTA_FINDINGS  # noqa: E402

    with tempfile.TemporaryDirectory(prefix="chk-veto-") as td:
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
        owner = _write_uri_controllers(root, _BUILDER)[0]
        specimens.prepare_loop(root, errors=[(owner, 3, "cannot find symbol", "compiler.err.cant.resolve.location")])
        findings = load_json(root / MTA_FINDINGS)
        cluster = next(c for c in load_json(root / WORKLIST)["clusters"] if owner in (c.get("write_set") or []))
        _issue_cluster(root, cluster, "t_veto")
        f = root / owner
        f.write_text(f.read_text(encoding="utf-8").replace(_BUILDER, _CTOR), encoding="utf-8")
        specimens.verify(root, errors=[], failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_veto")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "introduced 1 unhandled checked exception" not in blob or "REVERTED" not in blob:
            return _fail("an introduced unhandled checked exception vetoes a falling count: %s" % blob[-600:])
        if "made 0 call(s) named URI" not in blob and "had no such site" not in blob:
            return _fail("the veto names its proof: %s" % blob[-400:])
        if _CTOR in f.read_text(encoding="utf-8"):
            return _fail("the vetoed candidate is reverted")
        if not (load_json(root / LOOP_STEPS).get("attempts") or {}):
            return _fail("a veto is a genuine rejection and spends an attempt")
    return 0


def _checked_family_advance_case() -> int:
    """v8 end to end: the family one step introduced, CONTINUE in the same card,
    a stalled continuation rejects, an exposure outside the family is typed."""
    from planner.paths import MTA_FINDINGS  # noqa: E402
    from planner.worklist import item_ids, obligation_keys  # noqa: E402

    with tempfile.TemporaryDirectory(prefix="chk-adv-") as td:
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
        paths = _write_uri_controllers(root, _BUILDER)
        owner, pet = paths[0], paths[1]
        legacy = _REST + "LegacyController.java"
        (root / legacy).write_text(_FAMILY_CTL % ("LegacyController", "Legacy", _CTOR), encoding="utf-8")
        owner_err, pet_err, legacy_err = ((owner, 8, _URI_MSG, _URI_CODE), (pet, 8, _URI_MSG, _URI_CODE), (legacy, 8, _URI_MSG, _URI_CODE))
        specimens.prepare_loop(root, errors=[legacy_err])
        findings = load_json(root / MTA_FINDINGS)
        # the introducing step, as the loop records an accepted one
        _write_uri_controllers(root, _CTOR)
        _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "the transformation")
        specimens.verify(root, errors=[owner_err], failures=[], findings=findings)
        cur = load_json(root / WORKLIST)
        steps = load_json(root / LOOP_STEPS)
        steps["steps"].append(dict(steps["steps"][-1], cluster="c:intro", card="t_intro", verdict="accepted",
                                   commit=_git(root, "rev-parse", "HEAD").strip(), measure=cur["measure"],
                                   obligation_keys=sorted(obligation_keys(cur)), item_ids=sorted(item_ids(cur)),
                                   candidate_sha256=load_json(root / LOOP_STATE)["candidate_sha256"]))
        write_canonical(root / LOOP_STEPS, steps)
        specimens.verify(root, errors=[owner_err], failures=[], findings=findings)
        pipeline.admit(root)
        wl = load_json(root / WORKLIST)
        family = [c for c in wl["clusters"] if (c.get("batch_scope") or {}).get("rule") == "checked-exception-family/v1"]
        if len(family) != 1 or set(family[0]["write_set"]) != set(paths) or len(family[0]["items"]) != 1:
            return _fail("the family writes the six sites the step introduced, not the legacy one, with one measured item: %s" % family)
        cluster = family[0]
        if not str(cluster.get("retry_key") or "").startswith("rk:compile:checked-family:"):
            return _fail("family retry_key: %s" % cluster.get("retry_key"))
        _issue_cluster(root, cluster, "t_fam")
        if not all(v.startswith("chk:") for v in load_json(root / LOOP_ISSUED)["item_identities"].values()):
            return _fail("the issued failure carries its line-free identity")
        p = _run([sys.executable, str(BRIEF), "--root", str(root), "--cluster", cluster["id"]])
        brief = json.loads(p.stdout) if p.returncode == 0 else {}
        if "request-aware URI builder" not in json.dumps(brief.get("batch_scope") or {}) or (brief.get("budget") or {}).get("limit") != 3:
            return _fail("the family brief carries the family's note and the one budget: %s%s" % (p.stdout[-400:], p.stderr[-300:]))

        # Owner repaired, Pet exposed: the same card continues
        f = root / owner
        f.write_text(f.read_text(encoding="utf-8").replace(_CTOR, _BUILDER), encoding="utf-8")
        specimens.verify(root, errors=[pet_err], failures=[], findings=findings)
        before = dict(load_json(root / LOOP_STEPS).get("attempts") or {})
        p = _advance(root, cluster["id"], "t_fam")
        blob = p.stdout + p.stderr
        if p.returncode != 3 or "CONTINUE" not in blob or "THIS card" not in blob:
            return _fail("Owner gone, Pet reported inside the family: CONTINUE (exit 3): rc=%s %s" % (p.returncode, blob[-500:]))
        if dict(load_json(root / LOOP_STEPS).get("attempts") or {}) != before or _CTOR in f.read_text(encoding="utf-8"):
            return _fail("a continuation spends nothing and keeps the candidate on the tree")
        if len(load_json(root / LOOP_ISSUED).get("continuations") or []) != 1:
            return _fail("the continuation is recorded on the issued card")

        # verified again without moving: that is a rejection, not a continuation
        specimens.verify(root, errors=[pet_err], failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_fam")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "did not move" not in blob or "REVERTED" not in blob:
            return _fail("a continuation that did not move is rejected: %s" % blob[-500:])
        steps = load_json(root / LOOP_STEPS)
        if (steps.get("attempts") or {}).get(cluster["retry_key"]) != 1 or _CTOR not in f.read_text(encoding="utf-8"):
            return _fail("the rejection counts against the family and reverts the candidate: %s" % steps.get("attempts"))
        rejected = (steps.get("rejected") or [])[-1]
        if "do not remint" not in rejected.get("legal_next", "") or (rejected.get("budget") or {}).get("spent") != 1:
            return _fail("the reject record carries the family's legal next and the budget: %s" % rejected)

        # Owner repaired, and the compiler now names a site no step of this family made
        specimens.verify(root, errors=[owner_err], failures=[], findings=findings)
        pipeline.admit(root)
        _issue_cluster(root, next(c for c in load_json(root / WORKLIST)["clusters"] if c["id"] == cluster["id"]), "t_fam2")
        f.write_text(f.read_text(encoding="utf-8").replace(_CTOR, _BUILDER), encoding="utf-8")
        specimens.verify(root, errors=[legacy_err], failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_fam2")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "VERIFICATION_PENDING" not in blob or "exposed-outside-scope" not in blob:
            return _fail("an exposure outside the family is a typed diagnosis: %s" % blob[-500:])
        if (load_json(root / LOOP_STEPS).get("attempts") or {}).get(cluster["retry_key"]) != 1:
            return _fail("a typed diagnosis spends no attempt")
    return 0


def _disposition_case() -> int:
    """A deferral whose cause was a harness defect is cleared by a disposition,
    not a product change: no commit, no step, the history kept -- and the ONE
    budget answer sees the clearance whichever identity it is asked with."""
    from planner.budget import budget

    with tempfile.TemporaryDirectory(prefix="disp-") as td:
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
        specimens.prepare_loop(root)
        steps = load_json(root / LOOP_STEPS)
        steps["attempts"] = {"rk:compile:checked-family:abc": 3}
        steps["retry_keys"] = {"c:fam": "rk:compile:checked-family:abc"}
        steps["rejected"] = [{"cluster": "c:fam", "card": "t_%d" % n, "retry_key": "rk:compile:checked-family:abc", "reason": "r"} for n in (1, 2, 3)]
        write_canonical(root / LOOP_STEPS, steps)
        write_canonical(root / LOOP_DEFERRED, {"schema": "rhoai3.loop-deferred/v1", "clusters": ["c:fam"], "reasons": {"c:fam": "3 of 3"}})
        if budget(steps, "c:fam", "rk:compile:checked-family:abc", 3)["left"] != 0:
            return _fail("a deferred family has no budget left before its clearance")
        n_steps, log = len(steps["steps"]), _git(root, "log", "--oneline")
        p = _run([sys.executable, str(HERE / "operator-step.py"), "--root", str(root), "--operator", "operator:o", "--reason", "harness fixed",
                  "--clear-deferred", "c:fam", "--disposition-only", "--no-mint"])
        if p.returncode != 0 or "DISPOSITION" not in p.stdout:
            return _fail("a metadata-only disposition on a verified, clean tree records: %s%s" % (p.stdout[-300:], p.stderr[-300:]))
        steps = load_json(root / LOOP_STEPS)
        row = (steps.get("deferral_clearances") or [{}])[-1]
        if load_json(root / LOOP_DEFERRED)["clusters"] or len(steps["steps"]) != n_steps or _git(root, "log", "--oneline") != log:
            return _fail("the deferral is lifted with no commit and no step")
        if row.get("kind") != "metadata-only" or row.get("retry_key") != "rk:compile:checked-family:abc" or row.get("attempts") != 3:
            return _fail("the disposition names the cluster, its retry key and what that key spent: %s" % row)
        if [r["card"] for r in steps["rejected"]] != ["t_1", "t_2", "t_3"]:
            return _fail("the rejected rows are never dropped")
        for ident in ("c:fam", "rk:compile:checked-family:abc"):
            b = budget(steps, "c:fam", ident if ident.startswith("rk:") else "", 3)
            if b["limit"] != 6 or b["left"] != 3:
                return _fail("the clearance raises the budget for every caller, asked by %s: %s" % (ident, b))
    return 0


def main() -> int:
    if _checked_veto_case() or _checked_family_advance_case() or _disposition_case():
        return 1
    if _si1_case():
        return 1
    if _pending_classify_case():
        return 1
    if _attempt_budget_case():
        return 1
    if _profile_keys_cases():
        return 1
    with tempfile.TemporaryDirectory(prefix="fug-") as tmp:
        t = Path(tmp).resolve()
        spec = specimens.specimen("http")
        base = spec["base"].replace(".", "/")
        root = specimens.build_dest(t / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=2))
        pipeline.assemble_bundle(root)
        _git(root, "init", "-q")
        _git(root, "add", "-A")
        _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "scaffold")
        p = _run([sys.executable, str(BOOTSTRAP), "--root", str(root)])
        if p.returncode != 0:
            return _fail("bootstrap: %s%s" % (p.stdout, p.stderr))
        findings = load_json(root / "evidence" / "mta-findings.json")
        owner = "src/main/java/%s/owner/OwnerController.java" % base
        pet = "src/main/java/%s/pet/PetController.java" % base
        errors = [(owner, 3, "cannot find symbol ResponseEntity"), (pet, 5, "cannot find symbol")]

        # --- measurement contract before the baseline ---
        # tests did not run → unknown; mvn test failed without a recorded failure → unknown
        p = specimens.verify(root, errors=[], failures=[], findings=findings)
        wl = load_json(root / WORKLIST)
        if not wl["measure"]["known"]:
            return _fail("clean tests with rc 0 must be known: %s" % wl["measure"])
        # an absent MTA scan is zero obligations in the bundle, not in the code: unknown
        bundle_p = root / "evidence/planning/evidence-bundle.json"
        bundle_doc = load_json(bundle_p)
        saved_bundle = bundle_p.read_bytes()
        bundle_doc["producers"]["mta"]["status"] = "missing"
        bundle_doc["obligations"] = []
        write_canonical(bundle_p, bundle_doc)
        specimens.verify(root, errors=[], failures=[])
        wl = load_json(root / WORKLIST)
        if wl["measure"]["known"] or wl["measure"]["mandatory_incidents"] is not None or "MTA producer status" not in " ".join(wl["measure"]["blocked"]):
            return _fail("a missing MTA producer must leave obligations unknown: %s" % wl["measure"])
        bundle_p.write_bytes(saved_bundle)
        st = specimens.write_verified_state(root, errors=[], failures=[], findings=findings)
        args = [a for a in st["args"] if not a.startswith("--surefire") and not a.endswith("surefire.json")]
        _run([sys.executable, str(VERIFY), "--root", str(root)] + [a for i, a in enumerate(args) if not (args[i - 1] == "--test-rc" if i else False) and a != "--test-rc"])
        wl = load_json(root / WORKLIST)
        if wl["measure"]["known"] or wl["measure"]["failing_tests"] is not None:
            return _fail("tests that did not run must be unknown: %s" % wl["measure"])
        specimens.verify(root, errors=[], failures=[], findings=findings, test_rc=1)
        wl = load_json(root / WORKLIST)
        if wl["measure"]["known"] or "no failing test recorded" not in " ".join(wl["measure"]["blocked"]):
            return _fail("mvn test rc 1 without a recorded failure must be unknown: %s" % wl["measure"])
        empty = t / "empty-surefire"
        empty.mkdir()
        _run([sys.executable, str(VERIFY), "--root", str(root), "--diagnostics", str(root / "verification/loop/sim/diagnostics.json"), "--surefire-dir", str(empty), "--test-rc", "0", "--findings", str(root / "verification/loop/sim/findings.json")])
        wl = load_json(root / WORKLIST)
        if wl["measure"]["known"] or wl["measure"]["tuple"][2] is not None:
            return _fail("an empty surefire directory must never be green: %s" % wl["measure"])

        # --- baseline (two compile errors; tests skipped because compilation fails) ---
        p = specimens.verify(root, errors=errors, failures=[], findings=findings)
        if p.returncode != 0:
            return _fail("verify: %s%s" % (p.stdout, p.stderr))
        wl = load_json(root / WORKLIST)
        m = wl["measure"]
        if not m["known"] or m["tuple"] != [5, 2, 0] or m["parity_mismatches"] is not None:
            return _fail("initial measure %s" % m)
        if wl["clusters"][0]["kind"] != "build" or wl["clusters"][0]["path"] != "pom.xml":
            return _fail("build cluster must come first: %s" % wl["clusters"][0])
        # a tree edited after verification cannot become the baseline
        (root / "pom.xml").write_text((root / "pom.xml").read_text(encoding="utf-8") + "\n<!-- late -->\n", encoding="utf-8")
        p = _run([sys.executable, str(ADVANCE), "--root", str(root), "--baseline", "--no-mint"])
        if p.returncode != 2 or "LOOP_CANDIDATE_CHANGED" not in p.stderr:
            return _fail("baseline after a late edit must refuse: %s" % p.stderr)
        specimens.verify(root, errors=errors, failures=[], findings=findings)
        p = _run([sys.executable, str(ADVANCE), "--root", str(root), "--baseline", "--no-mint"])
        if p.returncode != 0:
            return _fail("baseline: %s%s" % (p.stdout, p.stderr))
        if _git(root, "status", "--porcelain").strip():
            return _fail("baseline must commit the bootstrapped tree")
        baseline_head = _git(root, "rev-parse", "HEAD").strip()
        rec = pipeline.admit(root)
        if rec["status"] != "ADMITTED":
            return _fail("admission after baseline: %s" % rec["reasons"][:4])

        # --- issued card ---
        head = specimens.issue(root)
        issued = load_json(root / LOOP_ISSUED)
        if head["kind"] != "build" or issued["cluster"] != head["logical_id"] or issued["write_set"] != ["pom.xml"] or issued["attempt"] != 1:
            return _fail("issued card %s" % issued)
        p = _run([sys.executable, str(BRIEF), "--root", str(root)])
        if p.returncode != 0 or "pom.xml" not in p.stdout:
            return _fail("brief: %s" % p.stderr)
        brief = json.loads(p.stdout)
        if brief.get("previous_attempts") != [] or brief.get("attempts_left") != 2:
            return _fail("a first attempt has no previous attempts and the full budget: %s / %s" % (brief.get("previous_attempts"), brief.get("attempts_left")))
        if brief.get("write_set") != ["pom.xml"] or "one item at a time" not in brief.get("procedure", ""):
            return _fail("brief must name the write set and the patch-per-item procedure: %s" % {k: brief.get(k) for k in ("write_set", "procedure")})
        pom_items = [i for i in brief["items"] if i.get("source") == "mta" and i.get("path") == "pom.xml"]
        if not pom_items or any("advice" not in i or "element" not in i for i in pom_items):
            return _fail("every pom incident in the brief carries the rule advice and the element at its line: %s" % pom_items[:1])
        if any(i["element"].get("kind") not in ("dependency", "plugin", "extension", "project") for i in pom_items):
            return _fail("element kinds: %s" % [i["element"] for i in pom_items])
        pom_before = (root / "pom.xml").read_text(encoding="utf-8")

        # diagnostic mode cannot promote or reject; the candidate stays for an acceptance pass
        (root / "pom.xml").write_text(pom_before + "\n<!-- diag -->\n", encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=findings)
        run_doc = load_json(root / VERIFY_RUN) if (root / VERIFY_RUN).is_file() else {"schema": "rhoai3.verify-run/v1"}
        run_doc["mode"] = "diagnostic"
        write_canonical(root / VERIFY_RUN, run_doc)
        p = _advance(root, head["logical_id"], "t_diag")
        if p.returncode != 1 or "LOOP_DIAGNOSTIC_NOT_ACCEPTANCE" not in p.stderr:
            return _fail("diagnostic mode must refuse advance: %s" % p.stderr[-300:])
        if (root / "pom.xml").read_text(encoding="utf-8") == pom_before:
            return _fail("diagnostic refuse must leave the candidate on disk")
        if load_json(root / LOOP_STEPS)["attempts"].get(head["logical_id"]):
            return _fail("diagnostic refuse must not count an attempt")
        (root / "pom.xml").write_text(pom_before, encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=findings)

        # legacy baseline: strip the recorded obligation_keys; every later accept/revert below must re-key the
        # baseline from the accepted rescan findings instead of comparing content-hash ids against rule|file keys
        st = load_json(root / "verification/loop/steps.json")
        if st["steps"][0].pop("obligation_keys", None) is None:
            return _fail("the baseline step must record obligation_keys")
        write_canonical(root / "verification/loop/steps.json", st)
        # --- review counterexample 1: invented cluster + post-verification edit ---
        f2 = json.loads(json.dumps(findings))
        f2["violations"].pop("javaee-pom-to-quarkus-00003")
        (root / "pom.xml").write_text(pom_before + "\n<!-- step -->\n", encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=f2)  # decreasing measure
        (root / "src/test/java/Bad.java").write_text("this is not java\n", encoding="utf-8")  # edit AFTER verification
        p = _advance(root, "c:never-issued", "t_x")
        if p.returncode != 1 or "LOOP_CANDIDATE_CHANGED" not in p.stderr:
            return _fail("post-verification edit must refuse: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        if _git(root, "rev-parse", "HEAD").strip() != baseline_head or (root / "src/test/java/Bad.java").exists() or (root / "pom.xml").read_text(encoding="utf-8") != pom_before:
            return _fail("refusal must leave the accepted baseline and working tree unchanged")
        specimens.issue(root)
        (root / "pom.xml").write_text(pom_before + "\n<!-- step -->\n", encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=f2)
        p = _advance(root, "c:never-issued", "t_x")
        if p.returncode != 1 or "LOOP_NOT_ISSUED" not in p.stderr or (root / "pom.xml").read_text(encoding="utf-8") != pom_before:
            return _fail("an unissued cluster must refuse and discard: %s" % p.stderr[-300:])

        # --- review counterexample 4/1: an edit outside the write set (a test) is rejected and reverted ---
        specimens.issue(root)
        (root / "pom.xml").write_text(pom_before + "\n<!-- step -->\n", encoding="utf-8")
        test_file = root / "src/test/java" / base / "owner/OwnerControllerTest.java"
        test_before = test_file.read_text(encoding="utf-8")
        test_file.write_text(test_before + "// weakened\n", encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=f2)
        p = _advance(root, head["logical_id"], "t_c1")
        if p.returncode != 1 or "outside the write set" not in p.stderr or test_file.read_text(encoding="utf-8") != test_before or (root / "pom.xml").read_text(encoding="utf-8") != pom_before:
            return _fail("out-of-scope edit must reject and revert everything: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        steps = load_json(root / LOOP_STEPS)
        if steps["attempts"].get(head["logical_id"]) != 1:
            return _fail("scope violation counts an attempt: %s" % steps["attempts"])
        # the rejected candidate's reports are gone: the work list is the accepted one again
        wl = load_json(root / WORKLIST)
        if wl["measure"]["tuple"] != [5, 2, 0]:
            return _fail("rejected reports must not survive: %s" % wl["measure"])

        # --- step 1 accepted (attempt 2 after the scope rejection) ---
        card1 = specimens.issue(root)
        if card1["attempt"] != 2:
            return _fail("retry must carry attempt 2: %s" % card1["attempt"])
        (root / "pom.xml").write_text(pom_before + "\n<!-- step -->\n", encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=f2)
        p = _advance(root, head["logical_id"], "t_c1")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout or _git(root, "status", "--porcelain").strip():
            return _fail("accept: %s%s" % (p.stdout, p.stderr))
        steps = load_json(root / LOOP_STEPS)
        if steps["steps"][-1]["cluster"] != head["logical_id"] or steps["steps"][-1]["attempt"] != 2 or (root / LOOP_ISSUED).exists():
            return _fail("accepted step record: %s" % steps["steps"][-1])
        wl2 = load_json(root / WORKLIST)
        if wl2["measure"]["tuple"] != [4, 2, 0] or wl2["head"] == head["logical_id"]:
            return _fail("work list not advanced: %s head=%s" % (wl2["measure"], wl2["head"]))
        cl2 = _head(root)
        if cl2["kind"] != "compile":
            return _fail("after build, compile clusters come first: %s" % cl2)
        target = root / cl2["path"]
        original = target.read_text(encoding="utf-8")

        # --- review counterexample 2: a STAGED no-progress edit is reverted from index and tree ---
        key_c2 = specimens.issue(root)["idempotency_key"]
        target.write_text(original + "// staged, no progress\n", encoding="utf-8")
        _git(root, "add", "--", cl2["path"])
        specimens.verify(root, errors=errors, failures=[], findings=f2)
        p = _advance(root, cl2["id"], "t_c2")
        if p.returncode != 1 or "REVERTED" not in p.stderr:
            return _fail("no-progress step must revert: rc=%s %s" % (p.returncode, p.stderr[-200:]))
        if target.read_text(encoding="utf-8") != original or _git(root, "diff", "--cached", "--name-only").strip():
            return _fail("revert must restore the file in the working tree AND the index")
        if load_json(root / LOOP_STEPS)["attempts"].get(cl2["id"]) != 1:
            return _fail("rejection must count an attempt")
        p = _run([sys.executable, str(BRIEF), "--root", str(root), "--cluster", cl2["id"]])
        b2 = json.loads(p.stdout)
        reason = b2["previous_attempts"][0]["reason"]
        if len(b2.get("previous_attempts") or []) != 1 or b2.get("attempts_left") != 1:
            return _fail("the retry's brief must carry the refused attempt and the remaining budget: %s" % {k: b2.get(k) for k in ("previous_attempts", "attempts_left")})
        if "did not decrease" not in reason and "still reported" not in reason:
            return _fail("the retry brief must name why the previous attempt was refused: %s" % reason)

        # --- review counterexample 7: line movement is not a new obligation ---
        specimens.issue(root)
        target.write_text("// one more line at the top\n" + original, encoding="utf-8")
        f3 = json.loads(json.dumps(f2))
        for v in f3["violations"].values():
            for inc in v.get("incidents", []):
                if inc["uri"].endswith(cl2["path"]):
                    inc["lineNumber"] = int(inc["lineNumber"]) + 1
        one_less = [e for e in errors if e[0] != cl2["path"]]
        specimens.verify(root, errors=one_less, failures=[], findings=f3)
        p = _advance(root, cl2["id"], "t_c3")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout:
            return _fail("a shifted incident must not veto progress: %s%s" % (p.stdout, p.stderr))
        accepted_head = _git(root, "rev-parse", "HEAD").strip()

        # --- unknown measure retains the candidate (VERIFICATION_PENDING); known no-progress still defers ---
        cl3 = _head(root)
        t3 = root / cl3["path"]
        orig3 = t3.read_text(encoding="utf-8")
        specimens.issue(root)
        t3.write_text(orig3 + "// unresolvable\n", encoding="utf-8")
        specimens.verify(root, errors=one_less, failures=[], findings=f3, unresolvable="'dependencies.dependency.version' for io.quarkus:x is missing")
        p = _advance(root, cl3["id"], "t_pending")
        if p.returncode != 1 or "VERIFICATION_PENDING" not in p.stderr:
            return _fail("an unresolvable candidate must be pending, not a counted revert: %s" % p.stderr[-300:])
        if load_json(root / LOOP_STEPS)["attempts"].get(cl3["id"]):
            return _fail("pending must not count an attempt: %s" % load_json(root / LOOP_STEPS)["attempts"])
        if t3.read_text(encoding="utf-8") != orig3:
            return _fail("pending must restore the accepted tree")
        if convert_admitted(root)[0] is not None:
            return _fail("K4 must mint nothing while a candidate is VERIFICATION_PENDING")
        stored = root / LOOP_PENDING_FILES / cl3["id"].replace(":", "_").replace("/", "_") / cl3["path"]
        if not stored.is_file() or "// unresolvable" not in stored.read_text(encoding="utf-8"):
            return _fail("pending must retain the candidate files: %s" % stored)
        p = _advance(root, cl3["id"], "t_pending")
        if p.returncode != 1 or "LOOP_PENDING_NOT_RESTORED" not in p.stderr:
            return _fail("advance on the accepted tree while pending must refuse without counting: %s" % p.stderr[-300:])
        if load_json(root / LOOP_STEPS)["attempts"].get(cl3["id"]):
            return _fail("LOOP_PENDING_NOT_RESTORED must not count an attempt")
        p = _run([sys.executable, str(HERE / "restore-pending.py"), "--root", str(root), "--cluster", cl3["id"]])
        if p.returncode != 0 or t3.read_text(encoding="utf-8") != orig3 + "// unresolvable\n":
            return _fail("restore-pending must put the candidate back: %s%s" % (p.stdout, p.stderr))
        specimens.verify(root, errors=one_less, failures=[], findings=f3)
        p = _advance(root, cl3["id"], "t_pending")
        if p.returncode != 1 or "REVERTED" not in p.stderr:
            return _fail("a restored candidate that still does not progress must revert: %s" % p.stderr[-300:])
        if load_json(root / LOOP_STEPS)["attempts"].get(cl3["id"]) != 1:
            return _fail("the known no-progress after pending is attempt 1: %s" % load_json(root / LOOP_STEPS)["attempts"])
        specimens.issue(root)
        t3.write_text(orig3 + "// attempt 2\n", encoding="utf-8")
        specimens.verify(root, errors=one_less, failures=[], findings=f3)
        p = _advance(root, cl3["id"], "t_c5")
        if p.returncode != 1:
            return _fail("no-progress attempt 2 must fail: %s" % p.stdout)
        if "DEFERRED" not in p.stderr or "STOPS" not in p.stderr:
            return _fail("threshold must defer and stop: %s" % p.stderr[-300:])
        if t3.read_text(encoding="utf-8") != orig3 or _git(root, "rev-parse", "HEAD").strip() != accepted_head:
            return _fail("deferral must leave the baseline intact")
        rec = load_json(root / ADMISSION_RECEIPT)
        if rec["status"] != "INCONCLUSIVE" or not any(b["class"] == "MANUAL_CLUSTER" for b in rec["blocks"]):
            return _fail("a deferred cluster must stop admission: %s" % rec["reasons"][:3])
        if convert_admitted(root)[0] is not None:
            return _fail("K4 must mint nothing while a cluster is deferred")
        # --- the Operator rewinds to the step before t_c3: the tree, the budget and the deferral go back; the record grows ---
        steps_before = load_json(root / LOOP_STEPS)
        n = len(steps_before["steps"])
        sim = root / "verification" / "loop" / "rewind-sim.py"
        sim.write_text("import sys, json\nsys.path.insert(0, %r)\nfrom planner import specimens\nr = specimens.verify(%r, errors=json.loads(%r), failures=[], findings=json.loads(%r))\nsys.exit(r.returncode)\n"
                       % (str(GOLDEN / ".hermes" / "lib"), str(root), json.dumps(errors), json.dumps(f2)), encoding="utf-8")
        rew = [sys.executable, str(REWIND), "--root", str(root), "--operator", "adnan.drina", "--reason", "measure defect", "--no-mint", "--verify-cmd", "%s %s" % (sys.executable, sim)]
        p = _run(rew + ["--to-step", "99"])
        if p.returncode != 1 or "LOOP_REWIND" not in p.stderr or "steps:" not in p.stderr:
            return _fail("rewind to an unrecorded step must refuse and print the step table: %s" % p.stderr[-200:])
        p = _run(rew + ["--to-step", "0", "--to-card", "t_c1"])
        if p.returncode != 1 or "exactly one" not in p.stderr:
            return _fail("two targets must refuse: %s" % p.stderr[-200:])
        p = _run(rew + ["--before-card", "t_nobody"])
        if p.returncode != 1 or "accepted no recorded step" not in p.stderr:
            return _fail("an unknown card must refuse: %s" % p.stderr[-200:])
        # --before-card t_c3 == --to-step n-2 (undo the step t_c3 accepted)
        p = _run(rew + ["--before-card", "t_c3"])
        if p.returncode != 0 or "REWOUND" not in p.stdout:
            return _fail("rewind: %s%s" % (p.stdout[-400:], p.stderr[-400:]))
        if target.read_text(encoding="utf-8") != original or _git(root, "status", "--porcelain").strip():
            return _fail("rewind must restore the product tree at the step and commit it")
        steps = load_json(root / LOOP_STEPS)
        if len(steps["steps"]) != n - 1 or steps["attempts"] or len(steps["rewinds"]) != 1 or steps["rewinds"][0]["moved_steps"] != ["t_c3"]:
            return _fail("rewind record: %s" % {k: steps[k] for k in ("attempts", "rewinds")})
        if not all(r.get("rewound") for r in steps["rejected"]) or "t_c3" not in [r["card"] for r in steps["rejected"]]:
            return _fail("rewound steps and old rejections stay on the record as closed cards: %s" % [(r["card"], r.get("rewound")) for r in steps["rejected"]])
        if load_json(root / LOOP_DEFERRED)["clusters"] or load_json(root / ADMISSION_RECEIPT)["status"] != "ADMITTED":
            return _fail("rewind must clear the deferral and re-seal admission")
        if _head(root)["id"] != cl2["id"]:
            return _fail("after the rewind the earlier cluster is the head again: %s" % _head(root)["id"])
        again = specimens.issue(root)
        if again["attempt"] != 1 or again["idempotency_key"] == key_c2:
            return _fail("a new epoch must not hand back the old attempt-1 card: %s vs %s" % (again["idempotency_key"], key_c2))
        target.write_text("// one more line at the top\n" + original, encoding="utf-8")
        specimens.verify(root, errors=one_less, failures=[], findings=f3)
        p = _advance(root, cl2["id"], "t_c3b")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout:
            return _fail("re-landing the rewound step: %s%s" % (p.stdout, p.stderr))
        # --- an Operator step: a decided change (ADR retirement) recorded as a loop step, not card work ---
        victim = next(p for p in sorted((root / "src" / "main" / "java").rglob("*.java")) if p.name != target.name)
        vrel = str(victim.relative_to(root))
        op_sim = root / "verification" / "loop" / "op-sim.py"
        op_sim.write_text("import sys, json\nsys.path.insert(0, %r)\nfrom planner import specimens\nr = specimens.verify(%r, errors=json.loads(%r), failures=[], findings=json.loads(%r))\nsys.exit(r.returncode)\n"
                          % (str(GOLDEN / ".hermes" / "lib"), str(root), json.dumps([e for e in one_less if e[0] != vrel]), json.dumps(f3)), encoding="utf-8")
        opcmd = [sys.executable, str(OPERATOR_STEP), "--root", str(root), "--operator", "adnan.drina", "--reason", "retired by test", "--adr", "ADR-009", "--no-mint", "--verify-cmd", "%s %s" % (sys.executable, op_sim)]
        p = _run(opcmd)
        if p.returncode != 1 or "nothing changed" not in p.stderr:
            return _fail("an operator step with a clean tree must refuse: %s" % p.stderr[-200:])
        victim.unlink()
        n_before = len(load_json(root / LOOP_STEPS)["steps"])
        p = _run(opcmd)
        if p.returncode != 0 or "OPERATOR STEP" not in p.stdout:
            return _fail("operator step: %s%s" % (p.stdout[-300:], p.stderr[-300:]))
        st = load_json(root / LOOP_STEPS)["steps"][-1]
        if len(load_json(root / LOOP_STEPS)["steps"]) != n_before + 1 or st.get("verdict") != "operator" or st.get("adr") != "ADR-009" or st.get("changed") != [vrel] or not st.get("obligation_keys") or not st["measure"]["known"]:
            return _fail("the operator step must be recorded with verdict, adr, changed paths, keys and a known measure: %s" % {k: st.get(k) for k in ("verdict", "adr", "changed")})
        if _git(root, "status", "--porcelain").strip() or _git(root, "log", "-1", "--format=%s").strip().find("operator step by adnan.drina (ADR-009)") < 0:
            return _fail("the operator step must commit exactly the change with provenance: %s" % _git(root, "log", "-1", "--format=%s"))
        if load_json(root / ADMISSION_RECEIPT)["status"] != "ADMITTED":
            return _fail("admission must be re-sealed after an operator step")
        # --- the measure definition changed under an issued card (harness fix): rewind to the LAST step with --remeasure, closing the orphaned card ---
        specimens.issue(root)
        n = len(load_json(root / LOOP_STEPS)["steps"])
        sim2 = root / "verification" / "loop" / "rewind-sim2.py"
        f5 = json.loads(json.dumps(f3))
        drop = next(k for k, v in f5["violations"].items() if v.get("category") == "mandatory")
        f5["violations"].pop(drop)  # one fewer obligation: as if a rule were superseded
        sim2.write_text("import sys, json\nsys.path.insert(0, %r)\nfrom planner import specimens\nr = specimens.verify(%r, errors=json.loads(%r), failures=[], findings=json.loads(%r))\nsys.exit(r.returncode)\n"
                        % (str(GOLDEN / ".hermes" / "lib"), str(root), json.dumps(one_less), json.dumps(f5)), encoding="utf-8")
        rew2 = [sys.executable, str(REWIND), "--root", str(root), "--operator", "adnan.drina", "--reason", "rule superseded", "--no-mint", "--verify-cmd", "%s %s" % (sys.executable, sim2), "--to-step", str(n - 1)]
        p = _run(rew2)
        if p.returncode != 1 or "issued card is open" not in p.stderr:
            return _fail("an open issued card must refuse without --close-card: %s" % p.stderr[-200:])
        p = _run(rew2 + ["--close-card", "t_orphan"])
        if p.returncode != 1 or "--remeasure" not in p.stderr:
            return _fail("a changed measure must refuse without --remeasure: %s" % p.stderr[-300:])
        p = _run(rew2 + ["--close-card", "t_orphan", "--remeasure"])
        if p.returncode != 0 or "REWOUND" not in p.stdout:
            return _fail("remeasure rewind: %s%s" % (p.stdout[-300:], p.stderr[-300:]))
        steps = load_json(root / LOOP_STEPS)
        last = steps["steps"][-1]
        if len(steps["steps"]) != n or not last.get("remeasured") or last["remeasured"]["after"] != last["measure"]["tuple"] or (root / LOOP_ISSUED).exists():
            return _fail("remeasure must keep the step, record before/after and drop the issued card: %s" % {k: last.get(k) for k in ("remeasured",)})
        if not any(r["card"] == "t_orphan" and r.get("rewound") for r in steps["rejected"]) or steps["rewinds"][-1]["closed_cards"] != ["t_orphan"]:
            return _fail("the orphaned card must be on the record as closed: %s" % steps["rewinds"][-1])
        if load_json(root / ADMISSION_RECEIPT)["status"] != "ADMITTED":
            return _fail("after a remeasure rewind admission must be re-sealed")
        # the deferred cluster is open again with a fresh budget; the fix lands
        specimens.issue(root)
        t3.write_text(orig3 + "// human fix\n", encoding="utf-8")
        f4 = json.loads(json.dumps(f3))
        f4["violations"] = {k: v for k, v in f4["violations"].items() if v.get("category") != "mandatory"}
        specimens.verify(root, errors=[], failures=[], findings=f4)
        p = _advance(root, cl3["id"], "t_c6")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout:
            return _fail("human fix step: %s%s" % (p.stdout, p.stderr))
        rec = load_json(root / ADMISSION_RECEIPT)
        if rec["status"] != "ADMITTED" or not rec["loop_complete"] or rec["measure"]["tuple"] != [0, 0, 0]:
            return _fail("green state must be ADMITTED + loop_complete: %s %s" % (rec["status"], rec["reasons"][:3]))

        # --- the transition out of the repair loop: packaging, then startup ---
        # An empty list means the tree compiles and its tests pass. Until the
        # packaged application has been built and started against the decided
        # database, both gates are UNKNOWN and the closing card is not minted.
        wl = load_json(root / WORKLIST)
        if (wl.get("runtime") or {}).get("ready") or not any("packaging is unknown" in r for r in wl["runtime"]["reasons"]):
            return _fail("with no packaging receipt the runtime must be unknown: %s" % wl.get("runtime"))
        try:
            specimens.issue(root)
            return _fail("M4 must not mint while packaging and startup are unknown")
        except RuntimeError:
            pass

        # packaging fails on a plugin: one build obligation, at pom.xml, with its gate
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal org.jacoco:jacoco-maven-plugin:0.8.7:report", log="Unsupported class file major version 65")
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        wl = load_json(root / WORKLIST)
        rt_items = [i for i in wl["items"] if i["source"] == "runtime"]
        if len(rt_items) != 1 or rt_items[0]["gate"] != "package" or rt_items[0]["obligation"] != "build-configuration" or rt_items[0]["path"] != "pom.xml":
            return _fail("a packaging failure must be one build obligation carrying its gate: %s" % rt_items)
        cl = [c for c in wl["clusters"] if c["status"] == "open"][0]
        if cl.get("gate") != "package":
            return _fail("the cluster must carry the gate it repairs: %s" % cl)
        # a failure that NAMES a type in this tree lands on that type, not on
        # pom.xml (measured live: SpringDataJPAProcessor named VetRepository)
        named = sorted(root.glob("src/main/java/**/*.java"))[0].relative_to(root).as_posix()
        fqn = named[len("src/main/java/"):-len(".java")].replace("/", ".")
        specimens.runtime(root, package_rc=1, boot_ready=None,
                          detail="Failed to execute goal quarkus-maven-plugin:build",
                          log="Build step io.quarkus.spring.data.deployment.SpringDataJPAProcessor#build threw an exception: No implementation of interface %s was found" % fqn)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        named_items = [i for i in load_json(root / WORKLIST)["items"] if i["source"] == "runtime"]
        if len(named_items) != 1 or named_items[0]["path"] != named or named_items[0]["kind"] != "compile":
            return _fail("an augmentation failure must land on the type it names: %s (wanted %s)" % (named_items, named))
        # back to the plugin failure for the acceptance case below
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal org.jacoco:jacoco-maven-plugin:0.8.7:report", log="Unsupported class file major version 65")
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        wl = load_json(root / WORKLIST)
        cl = [c for c in wl["clusters"] if c["status"] == "open"][0]
        rec_pkg = load_json(root / ADMISSION_RECEIPT)
        if rec_pkg["status"] != "ADMITTED":
            return _fail("a packaging obligation must still admit: %s %s" % (rec_pkg["status"], rec_pkg.get("reasons")))
        issued = specimens.issue(root)
        if issued["logical_id"] != cl["id"]:
            return _fail("the packaging obligation must be the card: %s" % issued["logical_id"])

        # the repair leaves the compile/test tuple untouched. Acceptance is
        # phase-aware: the step is accepted because its own gate now passes.
        pom_p = root / "pom.xml"
        pom_p.write_text(pom_p.read_text(encoding="utf-8").replace("</project>", "  <!-- coverage plugin pinned for the toolchain -->\n</project>"), encoding="utf-8")
        specimens.runtime(root, package_rc=0, boot_ready=None)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        p = _advance(root, cl["id"], "t_pkg")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout or "discharges" not in p.stdout:
            return _fail("a packaging repair with an unchanged measure must be accepted when the gate passes: %s%s" % (p.stdout, p.stderr))

        # --- two independent packaging defects, one repaired ---
        # The gate holds one obligation per place it fails. Repairing the one
        # this card was issued for is progress even while the gate still fails
        # somewhere else; a rewording at the same place is not.
        srcs = sorted(root.glob("src/main/java/**/*.java"))
        one, two = srcs[0].relative_to(root).as_posix(), srcs[1].relative_to(root).as_posix()
        fqn = lambda rel: rel[len("src/main/java/"):-len(".java")].replace("/", ".")
        two_defects = ("Build step io.quarkus.spring.data.deployment.SpringDataJPAProcessor#build threw an exception: "
                       "No implementation of interface %s was found, and none of %s either" % (fqn(one), fqn(two)))
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build", log=two_defects)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        wl = load_json(root / WORKLIST)
        first = [i for i in wl["items"] if i["source"] == "runtime"]
        if len(first) != 1 or first[0]["path"] != one:
            return _fail("the gate reports the place it is failing now: %s" % first)
        cl2 = [c for c in wl["clusters"] if c["status"] == "open"][0]
        issued2 = specimens.issue(root)
        if issued2["logical_id"] != cl2["id"]:
            return _fail("the packaging obligation must be the card")

        # a) the same cause at the same place, differently worded: NOT progress
        (root / one).write_text((root / one).read_text(encoding="utf-8") + "// touched\n", encoding="utf-8")
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build",
                          log="[error] after 2 rounds: Build step X#build threw an exception: No implementation of interface %s was found" % fqn(one))
        specimens.verify(root, errors=[], failures=[], findings=f4)
        p = _advance(root, cl2["id"], "t_pkg2")
        if p.returncode == 0 or "still reported" not in (p.stdout + p.stderr):
            return _fail("a reworded failure at the same place must not count as progress: %s%s" % (p.stdout, p.stderr))

        # the rejection restored the accepted tree AND its receipts; the next
        # verification measures that tree again and re-derives the same
        # obligation, which is what the loop really does after a revert
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build", log=two_defects)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        # a2) a DIFFERENT cause at the same place IS a different obligation:
        #     a file can need a second repair once its first is done
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build",
                          log="Build step X#build threw an exception: io.quarkus.spring.data.deployment.UnableToParseMethodException: Method 'findAll' of %s" % fqn(one))
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        second = [i for i in load_json(root / WORKLIST)["items"] if i["source"] == "runtime"]
        if len(second) != 1 or second[0]["cause"] != "underivable-query-method" or second[0]["path"] != one:
            return _fail("a second cause at the same file must be its own obligation: %s" % second)
        # back to the first cause for the acceptance case below
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build", log=two_defects)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)

        # b) that place repaired, another still failing: progress
        specimens.issue(root)
        (root / one).write_text((root / one).read_text(encoding="utf-8") + "// repaired\n", encoding="utf-8")
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build",
                          log="Build step SpringDataJPAProcessor#build threw an exception: No implementation of interface %s was found" % fqn(two))
        specimens.verify(root, errors=[], failures=[], findings=f4)
        attempts_before = dict((load_json(root / LOOP_STEPS).get("attempts") or {}))
        p = _advance(root, cl2["id"], "t_pkg3")
        # a failing gate cannot discharge an obligation: the repair is RETAINED,
        # not accepted, and no attempt is spent
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "VERIFICATION_PENDING" not in blob or "not proof it was repaired" not in blob:
            return _fail("an unproven gate repair must be retained, not accepted: %s" % blob[:400])
        steps_now = load_json(root / LOOP_STEPS)
        if (steps_now.get("attempts") or {}) != attempts_before:
            return _fail("retaining a candidate must not spend an attempt: %s → %s" % (attempts_before, steps_now.get("attempts")))
        if not [r for r in (steps_now.get("pending") or []) if r.get("cluster") == cl2["id"] and r.get("cause") == "unproven-repair"]:
            return _fail("the retained candidate must be recorded with its cause: %s" % steps_now.get("pending"))

        # and the way out is the one the record names: restore the candidate,
        # repair what the gate now reports, and let the gate passing discharge
        # the whole batch at once
        rp = subprocess.run([sys.executable, str(SCRIPTS / "restore-pending.py"), "--root", str(root), "--cluster", cl2["id"]],
                            text=True, capture_output=True)
        if rp.returncode != 0 or "restored" not in rp.stdout:
            return _fail("restore-pending must put the retained candidate back: %s%s" % (rp.stdout, rp.stderr))
        specimens.runtime(root, package_rc=0, boot_ready=None)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        p = _advance(root, cl2["id"], "t_pkg3b")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout:
            return _fail("the gate passing must discharge the retained batch: %s%s" % (p.stdout, p.stderr))
        last = load_json(root / LOOP_STEPS)["steps"][-1]
        if not last.get("discharged"):
            return _fail("the accepted step must record which obligations it discharged: %s" % last.get("discharged"))

        # settle: the gate passes again for the rest of the walk
        specimens.runtime(root, package_rc=0, boot_ready=None)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)

        # startup still unknown: the closing card stays unminted
        try:
            specimens.issue(root)
            return _fail("M4 must not mint while startup is unknown")
        except RuntimeError:
            pass
        # an environment blocker is not a repair card
        specimens.runtime(root, package_rc=0, boot_ready=False, blocker="environment: Connection refused", detail="database unreachable")
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        wl = load_json(root / WORKLIST)
        if [i for i in wl["items"] if i["source"] == "runtime"]:
            return _fail("an environment blocker must not become a repair obligation: %s" % wl["items"])
        if not any("blocked by the environment" in r for r in wl["measure"]["blocked"]):
            return _fail("an environment blocker must be recorded as blocked: %s" % wl["measure"])
        # both gates passing on the SAME artifact: now M4 mints
        specimens.runtime(root, package_rc=0, boot_ready=True)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        wl = load_json(root / WORKLIST)
        if not wl["runtime"]["ready"]:
            return _fail("packaging + startup on one artifact must be ready: %s" % wl["runtime"])
        m4 = specimens.issue(root)
        if m4["logical_id"] != "M4_VERIFY" or m4["title"] != "M4 VERIFY":
            return _fail("an empty list with both gates passing must mint M4 VERIFY: %s" % m4["logical_id"])

        # --- review counterexample 4: an unresolved failing test never yields a test write set ---
        specimens.verify(root, errors=[], failures=[("x.NoSuchTest", "t")], findings=f4)
        wl = load_json(root / WORKLIST)
        bad = [c for c in wl["clusters"] if any(w.startswith("src/test/") for w in c["write_set"])]
        if bad:
            return _fail("tests are never in a write set: %s" % bad)
        if not wl["blocked_clusters"]:
            return _fail("an unresolvable test failure must be a typed blocker")
        rec = pipeline.admit(root)
        if not any(b["class"] == "SCOPE_UNDERIVED" for b in rec["blocks"]):
            return _fail("blocked cluster must block admission: %s" % rec["reasons"][:3])
        # a resolvable failing test scopes its production twin
        specimens.verify(root, errors=[], failures=[("org.acme.clinic.owner.OwnerControllerTest", "t")], findings=f4)
        wl = load_json(root / WORKLIST)
        tc = next(c for c in wl["clusters"] if c["kind"] == "test")
        if tc["write_set"] != ["src/main/java/%s/owner/OwnerController.java" % base]:
            return _fail("failing test must scope its production twin: %s" % tc["write_set"])
        # rescan that did not run after the baseline → incidents unknown
        st = specimens.write_verified_state(root, errors=[], failures=[], findings=None)
        _run([sys.executable, str(VERIFY), "--root", str(root)] + st["args"])
        wl = load_json(root / WORKLIST)
        if wl["measure"]["known"] or "rescan did not run" not in " ".join(wl["measure"]["blocked"]):
            return _fail("a skipped rescan must make incidents unknown: %s" % wl["measure"])
        # tampered work list → advance refuses
        specimens.verify(root, errors=[], failures=[], findings=f4)
        doc = load_json(root / WORKLIST)
        doc["head"] = "c:tampered"
        write_canonical(root / WORKLIST, doc)
        p = _advance(root, "c:tampered", "t_z")
        if p.returncode != 2 or "LOOP_STALE_STATE" not in p.stderr:
            return _fail("tampered work list must refuse advance: %s" % p.stderr)
    print("OK: fix-until-green (checked-exception veto: a falling count does not admit an introduced unhandled exception; family bound to its introducing step: Owner→Pet CONTINUE in the same card without an attempt, a stalled continuation rejects, an exposure outside the family is a typed diagnosis; a harness-caused deferral is cleared by a metadata-only disposition and the one budget sees it; measurement contract: unrun tests / empty reports / failed runner / skipped rescan are unknown; baseline; issued card; diagnostic cannot advance; post-verify edit + unissued cluster refused with baseline intact; out-of-scope test edit rejected + reverted + reports discarded; accept commits; staged no-progress reverted from index; line shift is not a new obligation; unresolvable candidate is VERIFICATION_PENDING (no attempt); known no-progress defers; Operator rewind restores tree+budget in a new epoch; green → packaging → startup → M4 (unknown gates never mint; an environment blocker is not a card; a gate repair is accepted phase-aware); unresolved test = typed blocker; tampered list refused)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
