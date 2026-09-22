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
import shutil
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


def _seal_gaps(root: Path) -> list[str]:
    """Why the admission receipt no longer seals what is on disk."""
    from planner.admission import verify_receipt

    return verify_receipt(root, require_admitted=True)[1]


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
        # H9b: advance.py again on the REVERTED card is idempotent -- the
        # rejection comes back by name, exit 1, no second attempt is spent
        spent = dict(load_json(root / LOOP_STEPS).get("attempts") or {})
        p = _advance(root, cluster["id"], "t_veto")
        blob = p.stdout + p.stderr
        if p.returncode != 1 or "REVERTED already" not in blob or "call kanban_complete" not in blob or "unhandled checked exception" not in blob:
            return _fail("advance.py on a reverted card answers REVERTED already, exit 1: %s" % blob[-400:])
        if (load_json(root / LOOP_STEPS).get("attempts") or {}) != spent:
            return _fail("the idempotent answer spends no attempt")
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


_PARITY_EP = "ep:org.acme.OwnerRestController#getOwners():http"
_PARITY_SID = "sc:cors-actual-owners"
_PARITY_REASON = "header Access-Control-Allow-Origin None vs *; header Access-Control-Expose-Headers None vs errors"


def _parity_records(root: Path, verdict: str, binding: dict | None = None) -> None:
    """What the M4 comparison leaves on disk: one scenario verdict and the
    receipt composed from it (compose-parity-receipt.py's shape).

    ``binding`` is what the records say they are OF. The M4 road leaves none
    (it is the accepted tree under the live seal); the acceptance path leaves
    the candidate binding compose-parity-receipt.py --issued writes."""
    from planner.paths import PARITY_DIR

    pdir = root / PARITY_DIR
    (pdir / "scenarios").mkdir(parents=True, exist_ok=True)
    extra = {"binding": dict(binding)} if binding else {}
    write_canonical(pdir / "scenarios" / "sc_cors.json",
                    dict(extra, schema="rhoai3.scenario-parity/v1", entry_point=_PARITY_EP, scenario=_PARITY_SID,
                         verdict=verdict, reason=_PARITY_REASON if verdict != "PASS" else ""))
    write_canonical(pdir / "receipt.json",
                    dict(extra, schema="rhoai3.parity-receipt/v1", verdict=verdict, total=1,
                         not_passed=0 if verdict == "PASS" else 1,
                         entry_points=[{"entry_point": _PARITY_EP, "verdict": verdict,
                                        "reason": "" if verdict == "PASS" else _PARITY_REASON,
                                        "scenarios": [_PARITY_SID], "coverage": {"positive": [_PARITY_SID], "negative": []}}]))


def _candidate_binding(root: Path, card: str) -> dict:
    """The binding the acceptance path's own comparison would have recorded:
    the candidate THIS verification measured and the card it was issued for."""
    from planner.paths import ADMISSION_RECEIPT, LOOP_ISSUED, VERIFY_RUN

    return {"mode": "candidate",
            "candidate_sha256": str(load_json(root / VERIFY_RUN).get("candidate_sha256") or ""),
            "issued_receipt_sha256": str((load_json(root / LOOP_ISSUED) if (root / LOOP_ISSUED).is_file() else {}).get("receipt_sha256")
                                         or load_json(root / ADMISSION_RECEIPT).get("receipt_digest") or ""),
            "card": card}


def _parity_run_record(root: Path, binding: dict | None) -> None:
    """The runner's own record of the comparison this verification made
    (run-parity.py's _run.json): what it was told to measure. run-verify.sh
    hands it the issued card whenever there is one, so on the acceptance path
    the run is candidate-bound and a receipt it composed would say so."""
    from planner.paths import PARITY_DIR

    write_canonical(root / PARITY_DIR / "_run.json",
                    {"schema": "rhoai3.parity-run/v1", "producer": "run-parity.py",
                     "issued": str(root / "verification" / "loop" / "issued.json") if binding else "",
                     "binding": dict(binding) if binding else {"mode": "sealed"},
                     "receipt": {"composed_by_this_run": True, "reason": ""}})


def _parity_verified(root: Path, findings: dict, *, ran: bool = True, verdict: str = "",
                     run_binding: dict | None = None) -> None:
    """The acceptance pass for a parity card: run-verify.sh copies the receipt
    it started from, runs the comparison, records runtime.parity in run.json and
    re-measures. Here the comparison is simulated; everything else is real."""
    from planner.paths import VERIFY_RUN

    # the acceptance path reaches parity through the packaging and startup
    # gates, and runs them on this candidate (a rejection discarded the last
    # candidate's receipts, so they are not inherited)
    specimens.runtime(root, package_rc=0, boot_ready=True)
    specimens.verify(root, errors=[], failures=[], findings=findings)
    doc = load_json(root / VERIFY_RUN)
    doc.setdefault("runtime", {})["parity"] = {
        "ran": ran, "rc": 0, "scenarios": [_PARITY_SID] if ran else [],
        "receipt_verdict": verdict, "ms": 1}
    write_canonical(root / VERIFY_RUN, doc)
    if ran:
        _parity_run_record(root, run_binding)


def _parity_card_case() -> int:
    """v9 card t_77cae2b2 end to end: the worker wrote the CORS properties the
    brief asked for, the acceptance pass was green, and advance.py answered
    "measure [0, 0, 0] did not decrease from [0, 0, 0]" -- because the parity
    obligation was never re-measured. Here the comparison is part of the
    acceptance path, and it is the comparison that decides."""
    from planner.paths import MTA_FINDINGS, VERIFY_DIR  # noqa: E402

    with tempfile.TemporaryDirectory(prefix="parity-adv-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"),
                                    decisions=specimens.admitted_decisions(max_attempts=3))
        # ADR-019: the source declares a CORS policy, so the CORS obligation is
        # owed the harness adapter, rendered from THIS policy
        from planner.paths import STRUCTURE  # noqa: E402
        import response_adapters as ra  # noqa: E402

        structure = load_json(root / STRUCTURE)
        for t in structure["types"]:
            if t["fqn"].endswith(".OwnerController"):
                t["annotations"].append({"fqn": "org.springframework.web.bind.annotation.CrossOrigin",
                                         "values": {"exposedHeaders": ["errors"]}})
        write_canonical(root / STRUCTURE, structure)
        specimens.prepare_loop(root)
        findings = json.loads(json.dumps(load_json(root / MTA_FINDINGS)))
        findings["violations"] = {k: v for k, v in (findings.get("violations") or {}).items()
                                  if v.get("category") != "mandatory"}
        # green, packaged and started: M4 ran, and the comparison FAILED
        specimens.runtime(root, package_rc=0, boot_ready=True)
        _parity_records(root, "FAIL")
        specimens.verify(root, errors=[], failures=[], findings=findings)
        pipeline.admit(root)
        # the accepted state the M4 road left: the tuple is green and parity is
        # the only thing outstanding, which is what makes the tuple useless as a
        # measure of this card
        from planner.worklist import item_ids, obligation_keys  # noqa: E402

        cur = load_json(root / WORKLIST)
        steps = load_json(root / LOOP_STEPS)
        steps["steps"][-1] = dict(steps["steps"][-1], measure=cur["measure"], runtime=cur.get("runtime") or {},
                                  obligation_keys=sorted(obligation_keys(cur)), item_ids=sorted(item_ids(cur)),
                                  candidate_sha256=load_json(root / LOOP_STATE)["candidate_sha256"])
        write_canonical(root / LOOP_STEPS, steps)
        wl = load_json(root / WORKLIST)
        if wl["measure"]["tuple"] != [0, 0, 0] or wl["measure"]["parity_mismatches"] != 1:
            return _fail("a parity mismatch sits beside the tuple, not inside it: %s" % wl["measure"])
        cl = [c for c in wl["clusters"] if c["status"] == "open"]
        adapter = ra.adapter_path(ra.CORS)
        if (len(cl) != 1 or cl[0].get("gate") != "parity"
                or cl[0]["write_set"] != sorted([adapter, "src/main/resources/application.properties"])
                or (cl[0].get("unit") or {}).get("rule") != "unit/owed-adapter/v1"):
            return _fail("the parity obligation must be one card carrying its gate and its owed adapter: %s" % cl)
        cluster = cl[0]
        card = specimens.issue(root)
        issued = load_json(root / LOOP_ISSUED)
        if card.get("logical_id") != cluster["id"] or issued.get("gate") != "parity" or issued.get("gate_items") != cluster["items"]:
            return _fail("K4 must mint the parity cluster and carry gate=parity and what the gate held onto the issued card: %s | %s"
                         % (card.get("logical_id"), {k: issued.get(k) for k in ("gate", "gate_items", "items")}))
        p = _run([sys.executable, str(BRIEF), "--root", str(root), "--cluster", cluster["id"]])
        brief = json.loads(p.stdout) if p.returncode == 0 else {}
        if _PARITY_SID not in json.dumps((brief.get("parity") or {})) or "PASS" not in json.dumps(brief.get("parity") or {}):
            return _fail("the parity brief must name the scenarios and what discharges them: %s%s" % (p.stdout[-400:], p.stderr[-300:]))

        props = root / "src/main/resources/application.properties"
        installer = HERE.parents[1] / "restore-source-response-shape" / "scripts" / "install-response-adapter.py"

        def install_adapter() -> None:
            ip = _run([sys.executable, str(installer), "--root", str(root), "--adapter", "cors"])
            if ip.returncode != 0:
                raise AssertionError("the capability must install on the issued card: %s%s" % (ip.stdout, ip.stderr))

        # 1. the comparison did not run: nothing was measured about the
        #    obligation, so the candidate is retained and no attempt is spent
        install_adapter()
        _parity_verified(root, findings, ran=False)
        p = _advance(root, cluster["id"], "t_par0")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "VERIFICATION_PENDING" not in blob or "not a measurement" not in blob:
            return _fail("a parity card whose comparison did not run must be retained, not judged: %s" % blob[-600:])
        if (load_json(root / LOOP_STEPS).get("attempts") or {}):
            return _fail("retaining a candidate must not spend an attempt: %s" % load_json(root / LOOP_STEPS).get("attempts"))

        # 2. the comparison ran and still reports the obligation: REVERTED
        rp = _run([sys.executable, str(SCRIPTS / "restore-pending.py"), "--root", str(root), "--cluster", cluster["id"]])
        if rp.returncode != 0 or "restored" not in rp.stdout:
            return _fail("restore-pending must put the retained candidate back: %s%s" % (rp.stdout, rp.stderr))
        shutil.copyfile(root / "verification" / "parity" / "receipt.json", root / VERIFY_DIR / "parity-before.json")
        _parity_records(root, "FAIL")
        _parity_verified(root, findings, verdict="FAIL")
        p = _advance(root, cluster["id"], "t_par1")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "REVERTED" not in blob or "still reported" not in blob:
            return _fail("an obligation the comparison still reports must be reverted: %s" % blob[-600:])
        if "rhoai3:source-cors" in props.read_text(encoding="utf-8") or (root / adapter).exists():
            return _fail("a rejected parity candidate must be reverted from the tree, the new adapter file included")

        # 3. the same repair, and this time the comparison comes back PASS.
        #    The rejection discarded the candidate's reports, so the accepted
        #    tree is measured again -- and the obligation is back, unrepaired.
        _parity_verified(root, findings, verdict="FAIL")
        pipeline.admit(root)
        retry = specimens.issue(root)
        if retry.get("logical_id") != cluster["id"]:
            return _fail("the reverted parity card must be re-issued: %s" % retry.get("logical_id"))
        install_adapter()
        shutil.copyfile(root / "verification" / "parity" / "receipt.json", root / VERIFY_DIR / "parity-before.json")
        _parity_records(root, "PASS")
        _parity_verified(root, findings, verdict="PASS")
        # The acceptance verify REBUILT the work list on this candidate, so the
        # live seal's worklist digest is the accepted tree's: a comparison that
        # asked the seal to match could not have measured anything here. That is
        # v9 card t_222c582a, where the CORS repair was right, every scenario
        # came back "receipt not authoritative: worklist digest ... != sealed
        # ...", and the card -- like every parity card -- was REVERTED.
        if not any("worklist digest" in g for g in _seal_gaps(root)):
            return _fail("the control needs the seal to be stale after the candidate's re-measure: %s" % _seal_gaps(root))

        # ... so the comparison binds its verdicts to the CANDIDATE and the
        # ISSUED card instead. One composed for another card is not this
        # card's measurement: nothing is judged from it and no attempt is spent
        _parity_records(root, "PASS", binding=_candidate_binding(root, "t_somebodyelse"))
        spent = dict(load_json(root / LOOP_STEPS).get("attempts") or {})
        p = _advance(root, cluster["id"], "t_par2")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "VERIFICATION_PENDING" not in blob or "not a measurement" not in blob:
            return _fail("a parity receipt composed for another card must not judge this one: %s" % blob[-600:])
        if "t_somebodyelse" not in blob or (load_json(root / LOOP_STEPS).get("attempts") or {}) != spent:
            return _fail("the refusal names the card the receipt was composed for, and spends no attempt: %s" % blob[-600:])

        # ... and the mirror of it, which is a FALSE GREEN rather than a
        # refusal: the comparison ran bound to THIS card, so a receipt it
        # composed would say so -- and the one on disk says nothing at all. It
        # is the receipt the last run left when this run's composer REFUSED to
        # compose (the composer writes nothing when it refuses), it still says
        # PASS, and it is a measurement of the accepted tree, not of this
        # candidate. Nothing is judged from it and no attempt is spent.
        rp = _run([sys.executable, str(SCRIPTS / "restore-pending.py"), "--root", str(root), "--cluster", cluster["id"]])
        if rp.returncode != 0 or "restored" not in rp.stdout:
            return _fail("restore-pending must put the retained candidate back: %s%s" % (rp.stdout, rp.stderr))
        _parity_records(root, "PASS")
        _parity_verified(root, findings, verdict="PASS")
        _parity_run_record(root, _candidate_binding(root, "t_par2"))
        spent = dict(load_json(root / LOOP_STEPS).get("attempts") or {})
        p = _advance(root, cluster["id"], "t_par2")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "ACCEPTED" in p.stdout or "VERIFICATION_PENDING" not in blob or "not a measurement" not in blob:
            return _fail("a receipt left by a composer that refused must not be read as this card's PASS: %s" % blob[-600:])
        if "left by an earlier run" not in blob or (load_json(root / LOOP_STEPS).get("attempts") or {}) != spent:
            return _fail("the refusal must say the receipt is not this verification's, and spend no attempt: %s" % blob[-600:])

        rp = _run([sys.executable, str(SCRIPTS / "restore-pending.py"), "--root", str(root), "--cluster", cluster["id"]])
        if rp.returncode != 0 or "restored" not in rp.stdout:
            return _fail("restore-pending must put the retained candidate back: %s%s" % (rp.stdout, rp.stderr))
        # H10 (v9 t_56adcd76): a MID-CARD verification never re-seals admission
        # -- the receipt is byte-identical across the whole acceptance pass --
        # and even when another process re-sealed it after the mint, the
        # comparison binds to the receipt the card was MINTED under
        # (issued.json), and the card is ACCEPTED on its own evidence.
        from planner.paths import ADMISSION_RECEIPT as _ADM  # noqa: E402
        adm_before = (root / _ADM).read_bytes()
        _parity_records(root, "PASS")
        _parity_verified(root, findings, verdict="PASS")
        if (root / _ADM).read_bytes() != adm_before:
            return _fail("a mid-card verification must leave admission-receipt.json byte-identical")
        binding = _candidate_binding(root, "t_par2")
        _parity_records(root, "PASS", binding=binding)
        _parity_run_record(root, binding)
        # ... another writer re-seals admission mid-card (the v9 shape: a
        # different receipt_digest on disk than the one issued.json names)
        adm_doc = load_json(root / _ADM)
        adm_doc["receipt_digest"] = "3277" + "0" * 60
        write_canonical(root / _ADM, adm_doc)
        sys.path.insert(0, str(HERE.parents[2] / "gates" / "capture-source-oracles" / "scripts"))
        from _scenarios import candidate_binding as _cb  # noqa: E402
        notes: list = []
        made, gaps = _cb(root, issued_path=root / LOOP_ISSUED, notes=notes)
        if gaps or made.get("issued_receipt_sha256") != binding["issued_receipt_sha256"] or not any("minted under" in n for n in notes):
            return _fail("the candidate binding is to the ISSUED receipt, and the on-disk mismatch is a note, not a refusal: %s %s %s" % (made, gaps, notes))
        p = _advance(root, cluster["id"], "t_par2")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout or "discharges" not in p.stdout:
            return _fail("a parity repair the comparison confirms must be accepted with the tuple unchanged, whatever "
                         "admission-receipt.json says now: %s%s" % (p.stdout[-600:], p.stderr[-600:]))
        step = load_json(root / LOOP_STEPS)["steps"][-1]
        if step.get("gate") != "parity" or (step.get("parity") or {}).get("verdict") != "PASS":
            return _fail("the accepted step must record the gate and the receipt it was accepted on: %s" % step)
        if (step.get("parity") or {}).get("binding") != binding:
            return _fail("the accepted step must record what that receipt was a measurement OF: %s" % step.get("parity"))
        if step.get("measure", {}).get("tuple") != [0, 0, 0]:
            return _fail("a parity repair does not move the tuple: %s" % step.get("measure"))
        snap = root / "verification" / "loop" / "accepted" / "parity" / "receipt.json"
        if not snap.is_file() or load_json(snap)["verdict"] != "PASS":
            return _fail("the accepted state's parity receipt must be snapshotted like the other reports: %s" % snap)
        # H9b (v9 t_2da2458b): advance.py again on the ACCEPTED card -- the
        # killed-terminal case -- is idempotent: the verdict comes back, no
        # step, no commit, no attempt is added, exit 0; and its progress lines
        # name the phases
        before_steps, before_head = load_json(root / LOOP_STEPS), _git(root, "rev-parse", "HEAD").strip()
        p = _advance(root, cluster["id"], "t_par2")
        if (p.returncode != 0 or "OK: ACCEPTED already (step %d, commit %s)" % (len(before_steps["steps"]) - 1, step["commit"][:12]) not in p.stdout
                or "call kanban_complete" not in p.stdout):
            return _fail("advance.py on an accepted card answers ACCEPTED already, exit 0: %s%s" % (p.stdout[-400:], p.stderr[-400:]))
        if load_json(root / LOOP_STEPS) != before_steps or _git(root, "rev-parse", "HEAD").strip() != before_head:
            return _fail("the idempotent answer records nothing and commits nothing")
        if "advance: state loaded" not in p.stderr or "advance: re-sealing admission" not in p.stderr:
            return _fail("advance.py prints its phases: %s" % p.stderr[-400:])
        p = _advance(root, cluster["id"], "t_par2")
        if p.returncode != 0 or "ACCEPTED already" not in p.stdout:
            return _fail("and again: %s" % (p.stdout[-200:] + p.stderr[-200:]))
    return 0


def _introduced_attribution_case() -> int:
    """v9 t_3903f495: the right repair with the wrong import swapped 13
    attribution diagnostics for 13 of the same shape, and equal counts parked
    the card as exposed-outside-scope. An attribution diagnostic the accepted
    tree did not report was introduced: REVERTED, the symbols named, an
    attempt spent. Controls: a FLOW code newly reported outside any family is
    still the typed diagnosis; an attribution diagnostic the accepted tree
    already had (in another file) is not introduced."""
    from planner.paths import MTA_FINDINGS  # noqa: E402

    _ATTR = "compiler.err.cant.resolve.location"
    with tempfile.TemporaryDirectory(prefix="chk-attr-") as td:
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
        paths = _write_uri_controllers(root, _BUILDER)
        owner, pet = paths[0], paths[1]
        owner_err = (owner, 3, "cannot find symbol class UriComponentsBuilder", _ATTR)
        pet_err = (pet, 3, "cannot find symbol class ResponseEntity", _ATTR)
        # the accepted tree reports one attribution diagnostic in each of two files
        specimens.prepare_loop(root, errors=[owner_err, pet_err])
        findings = load_json(root / MTA_FINDINGS)
        wl = load_json(root / WORKLIST)
        cluster = next(c for c in wl["clusters"] if owner in (c.get("write_set") or []))
        if pet in (cluster.get("write_set") or []):
            return _fail("the control needs Owner and Pet in separate clusters: %s" % cluster)
        f = root / owner
        original = f.read_text(encoding="utf-8")

        def _edit(marker: str) -> None:
            f.write_text(original.replace("import java.net.URI;\n", "import java.net.URI;\n// %s\n" % marker), encoding="utf-8")

        # the candidate "repairs" Owner and javac reports a DIFFERENT symbol there: same count
        _issue_cluster(root, cluster, "t_attr")
        _edit("jakarta.ws.rs.Context for jakarta.ws.rs.core.Context")
        specimens.verify(root, errors=[(owner, 4, "cannot find symbol class Context", _ATTR), pet_err], failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_attr")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "REVERTED" not in blob or "introduced 1 compile diagnostic" not in blob or "Context" not in blob:
            return _fail("an introduced attribution diagnostic is rejected, not parked: rc=%s %s" % (p.returncode, blob[-600:]))
        if "VERIFICATION_PENDING" in blob or "exposed-outside-scope" in blob:
            return _fail("the rejection is a verdict, not a typed diagnosis: %s" % blob[-400:])
        steps = load_json(root / LOOP_STEPS)
        key = str(cluster.get("retry_key") or cluster["id"])
        if (steps.get("attempts") or {}).get(key) != 1 or f.read_text(encoding="utf-8") != original:
            return _fail("the rejection spends an attempt and reverts the candidate: %s" % steps.get("attempts"))
        rejected = (steps.get("rejected") or [])[-1]
        if "write set" not in rejected.get("legal_next", "") or "introduced 1 compile diagnostic" not in rejected.get("reason", ""):
            return _fail("the rejected row tells the retry to fix the named symbols inside the write set: %s" % rejected)

        # control 1: a FLOW code newly reported outside any sealed family is still the typed diagnosis
        pipeline.admit(root)
        _issue_cluster(root, next(c for c in load_json(root / WORKLIST)["clusters"] if c["id"] == cluster["id"]), "t_attr2")
        _edit("a flow-class report")
        specimens.verify(root, errors=[(owner, 8, _URI_MSG, _URI_CODE), pet_err], failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_attr2")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "VERIFICATION_PENDING" not in blob or "exposed-outside-scope" not in blob or "introduced" in blob:
            return _fail("a flow-class diagnostic the compiler reports one at a time is exposed, not introduced: rc=%s %s" % (p.returncode, blob[-600:]))
        if (load_json(root / LOOP_STEPS).get("attempts") or {}).get(key) != 1:
            return _fail("the typed diagnosis spends no attempt")

        # control 2: Owner's diagnostic gone, Pet's still reported -- the accepted tree already had it
        p = _run([sys.executable, str(HERE / "restore-pending.py"), "--root", str(root), "--cluster", cluster["id"]])
        if p.returncode != 0:
            return _fail("restore-pending: %s%s" % (p.stdout, p.stderr))
        _edit("the right import")
        specimens.verify(root, errors=[pet_err], failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_attr2")
        blob = p.stdout + p.stderr
        if "introduced" in blob:
            return _fail("a diagnostic the accepted tree already had in another file is not introduced: %s" % blob[-500:])
        if p.returncode != 0 or "ACCEPTED" not in p.stdout:
            return _fail("Owner repaired with Pet's accepted diagnostic still standing is accepted: rc=%s %s" % (p.returncode, blob[-500:]))
    return 0


_UNIT_RETIRED = "org.springframework.web.util.UriComponentsBuilder"
_UNIT_TARGET = "jakarta.ws.rs.core.UriBuilder"
_UNIT_CATALOG = {"catalog": "compat-mapping.json", "block": "symbol_renames", "key": _UNIT_RETIRED,
                 "kind": "type", "source": "https://quarkus.io/version/3.27/guides/rest"}


def _seal_unit(root: Path, paths: list[str], item_ids: list[str], identities: list[str], *,
               member_id: str = "") -> dict:
    """A sealed v4 unit over these files, and the cluster that carries it.

    Hand-written on purpose: what is under test here is the TRANSACTION -- the
    partition, the checkpoint and what each records -- not the former, which
    worklist.test.py asserts against its own four rules on two worlds."""
    from planner.worklist import batch_scope_digest, batch_scope_path

    scope = {
        "schema": "rhoai3.batch-scope/v4", "kind": "unit", "rule": "unit/diagnostic-family/v1",
        "producer": "worklist.build_unit_scope", "tool": {"model": "jdk-dest-model", "version": "1.2.0"},
        "cluster": "u:testunit", "unit_id": "u:testunit", "family_key": _UNIT_RETIRED,
        "writable_paths": sorted(paths),
        "symbols": [{"kind": "type", "fqn": _UNIT_RETIRED, "path": paths[0]}],
        "target_symbols": [{"from": _UNIT_RETIRED, "to": _UNIT_TARGET, "catalog_row": dict(_UNIT_CATALOG)}],
        "members": [{"path": p, "type": "org.springframework.samples.petclinic.rest.%s" % Path(p).stem,
                     "member_id": member_id, "occurrence": 0, "state": "reported", "identity": ident,
                     "item": iid}
                    for p, ident, iid in zip(paths, identities, item_ids)],
        "evidence": [{"kind": "javac", "ref": "%s names %s" % (p, _UNIT_RETIRED)} for p in paths],
        "completion": [{"check": "identities-gone", "tool": "javac", "identities": sorted(identities),
                        "detail": "every sealed identity is gone"},
                       {"check": "unit-assessment", "tool": "worklist.assess_unit", "detail": "no member violates"}],
        "bounds": {"files": len(paths), "sites": len(paths), "symbols": 1,
                   "max_files": 20, "max_sites": 160, "max_symbols": 8},
        "measured": sorted(item_ids), "inputs": {"candidate_sha256": ""},
    }
    scope["digest"] = batch_scope_digest(scope)
    sp = batch_scope_path(scope)
    write_canonical(root / sp, scope)
    return {"id": "u:testunit", "kind": "compile", "path": paths[0], "label": _UNIT_RETIRED,
            "write_set": sorted(paths), "items": sorted(item_ids), "retry_key": "rk:unit:u:testunit",
            "batch_scope": {"path": sp.as_posix(), "digest": scope["digest"], "rule": scope["rule"],
                            "kind": "unit", "unit_id": "u:testunit", "members": len(paths)}}


def _unit_checkpoint_case() -> int:
    """The checkpoint, end to end through the transaction.

    A coordinated repair across two files is ACCEPTED with the compile count
    unchanged when what remains is a diagnostic the unit's DOCUMENTED target
    explains; the same shape with an invented replacement (v9 t_3903f495, the
    right repair with the wrong import) is explained by nothing and REVERTS;
    the compiler naming another member of the same unit CONTINUES the card;
    one naming something outside it does not; and a member repaired by
    deleting it still violates."""
    from planner.paths import MTA_FINDINGS  # noqa: E402

    _ATTR = "compiler.err.cant.resolve.location"

    def sym(name: str) -> str:
        # javac's own wording: the TOKEN is what compile_token reads, and the
        # whole partition turns on resolving it rather than matching prose
        return "cannot find symbol\n  symbol:   class %s\n  location: class R" % name

    with tempfile.TemporaryDirectory(prefix="chk-unit-") as td:
        spec = specimens.specimen("http")
        # six verdicts are asserted in one tree, and what is under test is the
        # verdict, never the budget (the budget has its own case)
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=8))
        paths = _write_uri_controllers(root, _BUILDER)
        owner, pet, third = paths[0], paths[1], paths[2]
        sealed = [owner, pet]
        # the catalogued target has to EXIST for an import of it to bind: the
        # whole predicate under test is "the token resolves, through this
        # file's imports, to a qualified identity", and a type the compiler
        # cannot see resolves to nothing. A stub in the baseline tree is the
        # platform's presence, as dest_model's own selftest stubs it.
        stub = root / "src/main/java" / (_UNIT_TARGET.replace(".", "/") + ".java")
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text("package %s;\npublic interface %s { }\n"
                        % (_UNIT_TARGET.rsplit(".", 1)[0], _UNIT_TARGET.rsplit(".", 1)[-1]), encoding="utf-8")
        errs = [(p, 3, sym("UriComponentsBuilder"), _ATTR) for p in sealed]
        specimens.prepare_loop(root, errors=list(errs))
        findings = load_json(root / MTA_FINDINGS)
        wl = load_json(root / WORKLIST)
        rows = sorted([i for i in wl["items"] if str(i.get("source")) == "javac" and str(i.get("path")) in sealed],
                      key=lambda i: str(i["path"]))
        if len(rows) != 2:
            return _fail("the fixture needs one diagnostic per sealed file: %s" % [(r.get("path"), r.get("id")) for r in rows])
        cluster = _seal_unit(root, sorted(sealed), [str(r["id"]) for r in rows], [str(r["identity"]) for r in rows])
        originals = {p: (root / p).read_text(encoding="utf-8") for p in paths}

        def edit(rel: str, marker: str) -> None:
            (root / rel).write_text(originals[rel].replace("import java.net.URI;\n",
                                                           "import java.net.URI;\n// %s\n" % marker), encoding="utf-8")

        def edit_import(rel: str, fqn: str) -> None:
            """The repair as a repair: the file IMPORTS what it moved to, so
            the model binds the diagnostic's token to a qualified identity.
            Nothing else can make a token resolve, which is the point."""
            (root / rel).write_text(originals[rel].replace("import java.net.URI;\n",
                                                           "import java.net.URI;\nimport %s;\n" % fqn), encoding="utf-8")

        def restore() -> None:
            for rel, text in originals.items():
                (root / rel).write_text(text, encoding="utf-8")

        # (1) THE COUNTEREXAMPLE FIRST, so no later pass can be read as luck.
        # Both sealed diagnostics are gone and the candidate has invented a
        # replacement the catalogue never wrote down. The count is unchanged.
        _issue_cluster(root, cluster, "t_unit1")
        for p in sealed:
            edit(p, "jakarta.ws.rs.Context for jakarta.ws.rs.core.Context")
        specimens.verify(root, errors=[(p, 9, sym("Context"), _ATTR) for p in sealed],
                         failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_unit1")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "REVERTED" not in blob or "introduced 2 compile diagnostic" not in blob:
            return _fail("an invented replacement is explained by nothing and still REVERTS: rc=%s %s" % (p.returncode, blob[-700:]))
        if "Context" not in blob:
            return _fail("and the rejection names the symbols: %s" % blob[-400:])
        if (root / owner).read_text(encoding="utf-8") != originals[owner]:
            return _fail("the rejected candidate is reverted")

        # (1b) THE SECOND COUNTEREXAMPLE: the diagnostic names UriBuilder, the
        # simple name of the catalogued target — and nothing in the file
        # imports it. An unbound token resolves to no type at all, so it is a
        # SPELLING, and a spelling is not the catalogued identity. Explained by
        # nothing, REVERTED, exactly as the invented import above.
        pipeline.admit(root)
        _issue_cluster(root, cluster, "t_unit1b")
        for q in sealed:
            edit(q, "the right shape with nothing bound")
        specimens.verify(root, errors=[(q, 9, sym("UriBuilder"), _ATTR) for q in sealed],
                         failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_unit1b")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "REVERTED" not in blob or "introduced 2 compile diagnostic" not in blob:
            return _fail("an unresolved lookalike is not the catalogued target: rc=%s %s" % (p.returncode, blob[-700:]))
        if (root / owner).read_text(encoding="utf-8") != originals[owner]:
            return _fail("and the candidate that spelled it is reverted")

        # (2) THE SAME SHAPE with the DOCUMENTED target, RESOLVED: the file
        # imports jakarta.ws.rs.core.UriBuilder, so the token binds to the
        # qualified identity the catalogue wrote down. The unit traded its two
        # sealed diagnostics for two about that replacement, with the catalogue
        # row that documents it. The count did not fall and the step is
        # ACCEPTED at its checkpoint.
        pipeline.admit(root)
        _issue_cluster(root, cluster, "t_unit2")
        for q in sealed:
            edit_import(q, _UNIT_TARGET)
        specimens.verify(root, errors=[(q, 9, sym("UriBuilder"), _ATTR) for q in sealed],
                         failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_unit2")
        blob = p.stdout + p.stderr
        if p.returncode != 0 or "ACCEPTED" not in blob:
            return _fail("a discharged unit is accepted with the count unchanged: rc=%s %s" % (p.returncode, blob[-700:]))
        if "explained_regressions" not in blob:
            return _fail("and it says what it tolerated and why: %s" % blob[-500:])
        step = (load_json(root / LOOP_STEPS)["steps"] or [{}])[-1]
        if (step.get("unit") or {}).get("unit_id") != "u:testunit":
            return _fail("the accepted step records the unit it discharged: %s" % step.get("unit"))
        rec = step.get("explained_regressions") or []
        if len(rec) != 2 or {r["boundary"] for r in rec} != {"target"}:
            return _fail("every tolerated diagnostic is recorded with its boundary: %s" % rec)
        if {r["catalog_row"].get("key") for r in rec} != {_UNIT_RETIRED}:
            return _fail("and with the catalogue row that documented it: %s" % rec)
        # what the checkpoint TOLERATED is not what it forgave: every explained
        # diagnostic is still an obligation on the rebuilt work list, so the
        # next card is minted for it
        after = load_json(root / WORKLIST)
        carried = {str(i.get("identity") or "") for i in after["items"] if str(i.get("source")) == "javac"}
        missing = sorted(r["identity"] for r in rec if r["identity"] not in carried)
        if missing:
            return _fail("an explained regression is retained as an obligation, never discharged: %s" % missing)
        for q in sealed:
            originals[q] = (root / q).read_text(encoding="utf-8")

        # (3) CONTINUE: the compiler names another member of the same unit. A
        # flow code carries no symbol token, so nothing explains it -- and it is
        # at a file the unit seals, which is the unit's own remaining work. The
        # count does not fall: the other file's diagnostic is still standing.
        pipeline.admit(root)

        def javac_rows(where: list[str]) -> list[dict]:
            doc = load_json(root / WORKLIST)
            return sorted([i for i in doc["items"] if str(i.get("source")) == "javac" and str(i.get("path")) in where],
                          key=lambda i: str(i["path"]))

        now = javac_rows(sealed)
        both = _seal_unit(root, sorted(sealed), [str(r["id"]) for r in now], [str(r["identity"]) for r in now])
        spent = (load_json(root / LOOP_STEPS).get("attempts") or {}).get("rk:unit:u:testunit", 0)
        _issue_cluster(root, both, "t_unit3")
        for q in sealed:
            edit(q, "another site of the same unit")
        specimens.verify(root, errors=[(q, 8, _URI_MSG, _URI_CODE) for q in sealed], failures=[], findings=findings)
        p = _advance(root, both["id"], "t_unit3")
        blob = p.stdout + p.stderr
        if p.returncode != 3 or "CONTINUE" not in blob or "another member of the same unit" not in blob:
            return _fail("the next member of the unit continues the card: rc=%s %s" % (p.returncode, blob[-700:]))
        if (load_json(root / LOOP_STEPS).get("attempts") or {}).get("rk:unit:u:testunit", 0) != spent:
            return _fail("a continuation spends no attempt against the unit's budget")

        # (4) OUTSIDE the unit: the same kind of diagnostic at a file the unit
        # does not seal is not its remaining work, and is not accepted.
        restore()
        _issue_cluster(root, both, "t_unit4")
        for q in sealed:
            edit(q, "a repair with a side effect elsewhere")
        specimens.verify(root, errors=[(owner, 8, _URI_MSG, _URI_CODE), (third, 8, _URI_MSG, _URI_CODE)],
                         failures=[], findings=findings)
        p = _advance(root, both["id"], "t_unit4")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "VERIFICATION_PENDING" not in blob or "exposed-outside-scope" not in blob:
            return _fail("a diagnostic outside the sealed symbols is never accepted: rc=%s %s" % (p.returncode, blob[-700:]))

        # (5) REPAIR BY DELETION: a sealed member answered by removing the
        # operation violates, whatever the measure does -- here the measure
        # falls to nothing at all and the card is still REVERTED.
        restore()
        specimens.verify(root, errors=[(q, 9, sym("UriBuilder"), _ATTR) for q in sealed], failures=[], findings=findings)
        pipeline.admit(root)
        now = javac_rows([owner])
        gone = _seal_unit(root, [owner], [str(now[0]["id"])], [str(now[0]["identity"])], member_id="addOwner")
        _issue_cluster(root, gone, "t_unit5")
        (root / owner).write_text(originals[owner].split("    void add")[0] + "}\n", encoding="utf-8")
        specimens.verify(root, errors=[(pet, 9, sym("UriBuilder"), _ATTR)], failures=[], findings=findings)
        p = _advance(root, gone["id"], "t_unit5")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "REVERTED" not in blob or "violate" not in blob:
            return _fail("a member repaired by deleting it violates: rc=%s %s" % (p.returncode, blob[-700:]))
        if "addOwner" not in blob:
            return _fail("and the refusal names the member that went: %s" % blob[-400:])
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


_SET_WIDE_ERRORS = (
    "[ERROR] \t[error]: Build step io.quarkus.spring.data.deployment.SpringDataJPAProcessor#build threw an exception: "
    "java.lang.IllegalArgumentException: No implementation of interface "
    "org.springframework.samples.petclinic.repository.%s was found\n"
    "[ERROR] \tat io.quarkus.spring.data.deployment.generate.FragmentMethodsUtil.getImplementationDotName(FragmentMethodsUtil.java:38)"
)


def _harness_owned_root_case() -> int:
    """v9 (after the ADR-014 step): the mint issued an M3 incident card whose
    write set was a GENERATED parity test (20 MTA incidents on its origin
    mapping). The generated roots are the harness's (ADR-015/ADR-019): an
    incident there is accounted as a finding for the generator's owner and is
    never an obligation, and no write set may name such a path. The roots come
    from the generator's own declaration, including a root its manifest records."""
    sys.path.insert(0, str(HERE.parents[2] / "gates" / "generate-product-tests" / "scripts"))
    import parity_pom  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="owned-root-") as td:
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
        specimens.prepare_loop(root)
        gen = "%s/org/acme/generated/AccountParityTest.java" % parity_pom.DEFAULT_OUT
        extra = "src/it-generated/java/org/acme/generated/BParityTest.java"
        product = "src/main/java/org/acme/clinic/owner/OwnerController.java"
        for rel in (gen, extra, product):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text("package x;\nclass A {}\n", encoding="utf-8")
        man = root / parity_pom.GENERATED_MANIFEST
        man.parent.mkdir(parents=True, exist_ok=True)
        man.write_text(json.dumps({"schema": "rhoai3.generated-tests/v1", "out": "src/it-generated/java",
                                   "files": [{"path": extra, "sha256": "0" * 64}]}), encoding="utf-8")

        def inc(rel: str, n: int) -> dict:
            return {"uri": "file://%s/%s" % (root, rel), "lineNumber": n, "message": "hardcoded address %d" % n}

        findings = {"schema": "rhoai3.mta-findings/v1-provisional", "violations": {
            "localhost-http-00001": {"category": "mandatory", "incidents": [inc(gen, 10), inc(gen, 11), inc(extra, 3)]},
            "hardcoded-ip-address": {"category": "mandatory", "incidents": [inc(product, 7)]},
        }}
        specimens.verify(root, errors=[], failures=[], findings=findings)
        wl = build_worklist(root)
        owned = wl.get("harness_owned") or {}
        paths = sorted({f["path"] for f in owned.get("findings") or []})
        if paths != sorted([gen, extra]) or any(f.get("owner") != "generate-product-tests" or f.get("applicable_to_workers") is not False
                                                for f in owned.get("findings") or []):
            return _fail("findings in generated roots are accounted to the generator's owner: %s" % owned)
        if parity_pom.DEFAULT_OUT not in owned.get("roots", []) or "src/it-generated/java" not in owned.get("roots", []):
            return _fail("the roots come from the generator's declaration and its manifest: %s" % owned.get("roots"))
        bad = [c for c in wl["clusters"] if any(w.startswith((parity_pom.DEFAULT_OUT, "src/it-generated/")) for w in c.get("write_set") or [])]
        if bad:
            return _fail("no cluster may be issued a generated path: %s" % [(c["id"], c["write_set"]) for c in bad])
        if any(str(i.get("path") or "").startswith((parity_pom.DEFAULT_OUT, "src/it-generated/")) for i in wl["items"]):
            return _fail("a generated-root finding is never an obligation: %s" % [i["path"] for i in wl["items"]])
        if not any(i.get("path") == product for i in wl["items"]):
            return _fail("the product incident is still an obligation: %s" % [i["path"] for i in wl["items"]])
        if wl["measure"]["tuple"][0] != 1:
            return _fail("the incident slot counts only worker obligations: %s" % wl["measure"])
    return 0


def _parity_baseline_refresh_case() -> int:
    """F2 (v9 step 2410082): an Operator step that CHANGES the product may not
    freeze the parity receipt of the tree before it. The accepted baseline is
    UNMEASURED (reason and prior digest kept), the live records are set aside,
    a revert cannot bring the stale obligation back, and only a sealed,
    whole, current-admission, same-artifact comparison of the accepted tree
    is snapshotted by refresh-accepted-parity.py."""
    from planner.paths import MTA_FINDINGS, PARITY_DIR  # noqa: E402
    from _loop_common import restore_reports  # noqa: E402

    from planner.paths import STRUCTURE  # noqa: E402

    refresh = HERE / "refresh-accepted-parity.py"
    with tempfile.TemporaryDirectory(prefix="parity-refresh-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"),
                                    decisions=specimens.admitted_decisions(max_attempts=3))
        structure = load_json(root / STRUCTURE)
        for t in structure["types"]:
            if t["fqn"].endswith(".OwnerController"):
                t["annotations"].append({"fqn": "org.springframework.web.bind.annotation.CrossOrigin", "values": {}})
        write_canonical(root / STRUCTURE, structure)
        specimens.prepare_loop(root)
        findings = json.loads(json.dumps(load_json(root / MTA_FINDINGS)))
        findings["violations"] = {k: v for k, v in (findings.get("violations") or {}).items() if v.get("category") != "mandatory"}
        specimens.runtime(root, package_rc=0, boot_ready=True)
        _parity_records(root, "FAIL")
        specimens.verify(root, errors=[], failures=[], findings=findings)
        pipeline.admit(root)
        stale_sha = load_json(root / PARITY_DIR / "receipt.json")
        if not load_json(root / WORKLIST)["measure"]["parity_mismatches"]:
            return _fail("the fixture starts with a parity obligation")
        # the Operator step changes the product; its re-measure runs no comparison
        sim = root / "verification" / "loop" / "op-sim-parity.py"
        sim.write_text("import sys, json\nsys.path.insert(0, %r)\nfrom planner import specimens\nr = specimens.verify(%r, errors=[], failures=[], findings=json.loads(%r))\nsys.exit(r.returncode)\n"
                       % (str(GOLDEN / ".hermes" / "lib"), str(root), json.dumps(findings)), encoding="utf-8")
        victim = next(p for p in sorted((root / "src" / "main" / "java").rglob("*.java")))
        victim.write_text(victim.read_text(encoding="utf-8") + "\n// operator change\n", encoding="utf-8")
        p = _run([sys.executable, str(OPERATOR_STEP), "--root", str(root), "--operator", "adnan.drina", "--reason", "decided repair",
                  "--adr", "ADR-019", "--no-mint", "--verify-cmd", "%s %s" % (sys.executable, sim)])
        if p.returncode != 0:
            return _fail("operator step: %s%s" % (p.stdout[-300:], p.stderr[-300:]))
        snap = load_json(root / "verification" / "loop" / "accepted" / "parity" / "receipt.json")
        if snap.get("verdict") != "UNMEASURED" or "no parity comparison" not in snap["unmeasured"]["reason"]:
            return _fail("the step's baseline is UNMEASURED with its reason: %s" % snap)
        if snap["unmeasured"]["prior"].get("verdict") != stale_sha.get("verdict") or not snap["unmeasured"]["prior"].get("file_sha256"):
            return _fail("the replaced receipt is kept as history: %s" % snap["unmeasured"])
        if list((root / PARITY_DIR / "scenarios").glob("*.json")) or not list((root / "verification" / "loop" / "parity-set-aside").rglob("*.json")):
            return _fail("the other tree's records are set aside, not left live and not deleted")
        wl = build_worklist(root)
        if wl["measure"]["parity_mismatches"] is not None or not (wl["sources"]["parity"] or {}).get("unmeasured"):
            return _fail("an UNMEASURED baseline is unknown parity, not zero and not the stale FAIL: %s" % wl["sources"]["parity"])
        # a later revert restores the UNMEASURED baseline, never the stale FAIL
        _parity_records(root, "FAIL")
        restore_reports(root)
        if load_json(root / PARITY_DIR / "receipt.json").get("verdict") != "UNMEASURED" or list((root / PARITY_DIR / "scenarios").glob("*.json")):
            return _fail("a revert over an UNMEASURED baseline brings back no other tree's verdicts")

        def sealed(binding_extra: dict | None = None, *, admission: str = "", artifact: str = "", scoped: list | None = None, verdict: str = "FAIL") -> None:
            rec = load_json(root / "evidence" / "planning" / "admission-receipt.json")["receipt_digest"]
            _parity_records(root, verdict)
            r = load_json(root / PARITY_DIR / "receipt.json")
            r["receipt_sha256"] = admission or rec
            if binding_extra:
                r["binding"] = binding_extra
            write_canonical(root / PARITY_DIR / "receipt.json", r)
            write_canonical(root / PARITY_DIR / "_run.json", {
                "schema": "rhoai3.parity-run/v1", "producer": "run-parity.py", "receipt_sha256": admission or rec,
                "binding": {"mode": "sealed"}, "scenario_filter": list(scoped or []), "security_mode": "disabled",
                "artifact": {"sha256": artifact or load_json(root / "verification" / "build" / "package.json")["artifact_sha256"]},
                "receipt": {"composed_by_this_run": True}})

        base = [sys.executable, str(refresh), "--root", str(root), "--operator", "adnan.drina", "--reason", "sealed run on the accepted tree", "--no-mint"]
        for label, kw, needle in (("another admission", {"admission": "f" * 64}, "admission receipt"),
                                  ("another artifact", {"artifact": "e" * 64}, "artifact"),
                                  ("a scoped run", {"scoped": ["sc:x"]}, "scoped"),
                                  ("a candidate receipt", {"binding_extra": {"mode": "candidate"}}, "candidate-bound")):
            sealed(**kw)
            p = _run(base)
            if p.returncode != 1 or needle not in p.stderr:
                return _fail("refresh refuses %s: %s" % (label, p.stderr[-300:]))
            if load_json(root / "verification" / "loop" / "accepted" / "parity" / "receipt.json").get("verdict") != "UNMEASURED":
                return _fail("a refused refresh changes nothing (%s)" % label)
        sealed()
        p = _run(base)
        if p.returncode != 0 or "LOOP_PARITY_REFRESH" not in p.stdout:
            return _fail("a sealed comparison of the accepted tree refreshes the baseline: %s%s" % (p.stdout[-300:], p.stderr[-300:]))
        snap = load_json(root / "verification" / "loop" / "accepted" / "parity" / "receipt.json")
        steps = load_json(root / LOOP_STEPS)
        if snap.get("verdict") != "FAIL" or not steps.get("parity_refreshes") or "parity_refreshed" not in steps["steps"][-1]:
            return _fail("the refresh is snapshotted and recorded: %s %s" % (snap.get("verdict"), steps.get("parity_refreshes")))
        if steps["parity_refreshes"][-1]["replaces"]["verdict"] != "UNMEASURED":
            return _fail("the refresh records what it replaced: %s" % steps["parity_refreshes"][-1])
        if not load_json(root / WORKLIST)["measure"]["parity_mismatches"] or load_json(root / ADMISSION_RECEIPT)["status"] != "ADMITTED":
            return _fail("the rebuilt work list carries this tree's parity obligations and admission is re-sealed")
        if not (root / steps["parity_refreshes"][-1]["archive"] / "parity" / "receipt.json").is_file():
            return _fail("the refreshed baseline is archived by refresh number: %s" % steps["parity_refreshes"][-1])
        # a rewind to the REFRESHED step keeps that tree measured (v9 step 27),
        # from the archive, and -- for a refresh recorded before archives -- from
        # the accepted snapshot while it is still that refresh's receipt
        last = len(steps["steps"]) - 1
        rew = [sys.executable, str(REWIND), "--root", str(root), "--operator", "adnan.drina", "--reason", "back to the refreshed step",
               "--to-step", str(last), "--remeasure", "--no-mint", "--verify-cmd", "%s %s" % (sys.executable, sim)]
        for label in ("archive", "legacy snapshot"):
            _parity_records(root, "PASS")  # whatever a later card left live
            p = _run(rew)
            if p.returncode != 0 or "is restored" not in p.stdout:
                return _fail("rewind to the refreshed step (%s): %s%s" % (label, p.stdout[-300:], p.stderr[-300:]))
            snap = load_json(root / "verification" / "loop" / "accepted" / "parity" / "receipt.json")
            live = load_json(root / PARITY_DIR / "receipt.json")
            if snap.get("verdict") != "FAIL" or live.get("verdict") != "FAIL":
                return _fail("the refreshed baseline stands after the rewind (%s): %s / %s" % (label, snap.get("verdict"), live.get("verdict")))
            shutil.rmtree(root / "verification" / "loop" / "parity-refreshes", ignore_errors=True)
        # control: once the accepted snapshot is no longer that refresh's receipt, the tree is UNMEASURED
        _parity_records(root, "PASS")
        from _loop_common import snapshot_parity  # noqa: E402
        snapshot_parity(root)
        p = _run(rew)
        snap = load_json(root / "verification" / "loop" / "accepted" / "parity" / "receipt.json")
        if p.returncode != 0 or snap.get("verdict") != "UNMEASURED" or "no longer its receipt" not in snap["unmeasured"]["reason"]:
            return _fail("without that refresh's receipt the rewound tree is UNMEASURED, saying why: %s %s" % (snap, p.stderr[-200:]))
    return 0


def _set_wide_blocker_case() -> int:
    """A packaging failure about a SET reaches the work list as ONE typed
    blocker, never as a card for the repository it happened to name."""
    from planner.worklist import build_worklist  # noqa: E402

    with tempfile.TemporaryDirectory(prefix="set-wide-e2e-") as td:
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
        base = root / "src/main/java/org/springframework/samples/petclinic/repository"
        base.mkdir(parents=True, exist_ok=True)
        for name in ("OwnerRepository", "VisitRepository"):
            (base / ("%s.java" % name)).write_text(
                "package org.springframework.samples.petclinic.repository;\npublic interface %s {}\n" % name, encoding="utf-8")
        specimens.prepare_loop(root)
        seen = set()
        for name in ("OwnerRepository", "VisitRepository"):
            specimens.runtime(root, package_rc=1, detail="mvn verify exited 1 at quarkus-maven-plugin:build",
                              log=_SET_WIDE_ERRORS % name)
            wl = build_worklist(root)
            pkg_clusters = [c for c in wl["clusters"] if str(c.get("gate") or "") == "package"]
            if pkg_clusters:
                return _fail("a set-wide cause must mint nothing: %s" % [c["write_set"] for c in pkg_clusters])
            rows = [u for u in wl.get("unlocatable") or [] if u.get("scope") == "spring-data-fragment-implementations"]
            if len(rows) != 1:
                return _fail("exactly one typed blocker: %s" % (wl.get("unlocatable") or []))
            if not any(name in o for o in rows[0].get("observed") or []):
                return _fail("the blocker keeps what the message named: %s" % rows[0])
            if not any("SET-WIDE" in b for b in wl["measure"].get("blocked") or []):
                return _fail("the measure must say why nothing can be minted: %s" % wl["measure"].get("blocked"))
            seen.add(rows[0]["id"])
        if len(seen) != 1:
            return _fail("the blocker identity must not follow the reported name: %s" % sorted(seen))
    return 0


def _scratch_in_tree_case(base: str = "org.acme.clinic") -> int:
    """v9 t_46556d5e: the worker ran javap to diagnose its own repair, javap
    extracted .class files under io/quarkus/ at the destination ROOT, and the
    files landed after the verification. `is_product_path` is an exempt list
    (not evidence/, verification/, .hermes/, .derived/, target/, .git/), so
    that scratch counted as product: the candidate digest moved, advance.py
    read it as a post-verification product edit, and a repair it had already
    measured was REVERTED with an attempt spent on tool output.

    A change to something this migration OWNS after verification still
    invalidates the measured candidate. Untracked files outside its product do
    not: they are nobody's repair and no evidence against one, so they are not
    a verdict either -- a typed refusal, no attempt, the candidate left where
    it is. Removing them and running advance.py again gives the verdict the
    verification earned."""
    from planner.paths import MTA_FINDINGS  # noqa: E402

    with tempfile.TemporaryDirectory(prefix="scratch-adv-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http", base=base),
                                    decisions=specimens.admitted_decisions(max_attempts=3))
        owner = "src/main/java/%s/owner/OwnerController.java" % base.replace(".", "/")
        errors = [(owner, 3, "cannot find symbol ResponseEntity")]
        specimens.prepare_loop(root, errors=errors)
        findings = load_json(root / MTA_FINDINGS)
        head = specimens.issue(root)
        cluster = head["logical_id"]
        issued = load_json(root / LOOP_ISSUED)
        target = root / str((issued.get("write_set") or ["pom.xml"])[0])
        before = target.read_text(encoding="utf-8")

        # the repair the card asked for: one mandatory obligation on that file
        # is gone from the rescan, and the file changed
        repaired = json.loads(json.dumps(findings))
        rule = next(k for k, v in (repaired.get("violations") or {}).items()
                    if v.get("category") == "mandatory"
                    and all(str(i.get("uri") or "").endswith("/" + target.name) for i in (v.get("incidents") or [])))
        repaired["violations"].pop(rule)
        target.write_text(before + "\n<!-- repaired -->\n", encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=repaired)
        spent = dict(load_json(root / LOOP_STEPS).get("attempts") or {})
        head_commit = _git(root, "rev-parse", "HEAD").strip()

        # javap leaves its extracted classes at the tree root, AFTER the verify
        scratch = root / "io" / "quarkus" / "runtime" / "Quarkus.class"
        scratch.parent.mkdir(parents=True, exist_ok=True)
        scratch.write_bytes(b"\xca\xfe\xba\xbe extracted by javap\n")
        p = _advance(root, cluster, "t_scratch")
        blob = p.stdout + p.stderr
        if p.returncode != 1 or "LOOP_SCRATCH_IN_TREE" not in blob:
            return _fail("tool output left in the tree must not be a verdict: rc=%s %s" % (p.returncode, blob[-600:]))
        if "io/quarkus/runtime/Quarkus.class" not in blob:
            return _fail("the refusal must name the files it is refusing over: %s" % blob[-400:])
        if (load_json(root / LOOP_STEPS).get("attempts") or {}) != spent:
            return _fail("a refusal over scratch must spend no attempt: %s" % load_json(root / LOOP_STEPS).get("attempts"))
        if target.read_text(encoding="utf-8") == before or not scratch.is_file():
            return _fail("the refusal must leave the candidate and the scratch exactly where they are")
        if _git(root, "rev-parse", "HEAD").strip() != head_commit:
            return _fail("a refusal promotes nothing")

        # a PRODUCT path touched after the verification is still the revert it
        # always was: the control that keeps the refusal from swallowing it
        target.write_text(before + "\n<!-- repaired -->\n<!-- late -->\n", encoding="utf-8")
        p = _advance(root, cluster, "t_scratch")
        blob = p.stdout + p.stderr
        if p.returncode != 1 or "LOOP_CANDIDATE_CHANGED" not in blob or "REVERTED" not in blob:
            return _fail("a product edit after verification must still revert, scratch or no scratch: %s" % blob[-600:])

        # the worker removes the scratch, re-measures its own repair and
        # advances again: the normal verdict
        import shutil as _shutil

        _shutil.rmtree(root / "io")
        specimens.issue(root)
        target.write_text(before + "\n<!-- repaired -->\n", encoding="utf-8")
        specimens.verify(root, errors=errors, failures=[], findings=repaired)
        p = _advance(root, cluster, "t_scratch2")
        if p.returncode != 0 or "ACCEPTED" not in p.stdout:
            return _fail("with the scratch removed the candidate must get the verdict it earned: %s%s"
                         % (p.stdout[-400:], p.stderr[-600:]))
        return 0


def main() -> int:
    if _checked_veto_case() or _checked_family_advance_case() or _introduced_attribution_case() or _disposition_case() or _set_wide_blocker_case() or _harness_owned_root_case() or _parity_baseline_refresh_case() or _parity_card_case():
        return 1
    if _scratch_in_tree_case() or _scratch_in_tree_case("com.example.store"):
        return 1
    if _unit_checkpoint_case():
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
        # A failure that NAMES a type of this tree lands on that type rather
        # than on pom.xml -- for a cause that is really ABOUT that type. The
        # Spring Data fragment cause is not: it names one member of a set that
        # is failing as a set, and which member it names changes between runs
        # (six builds of one unchanged v8 tree named six repositories,
        # 2026-09-12). It is a typed blocker, and it mints nothing.
        named = sorted(root.glob("src/main/java/**/*.java"))[0].relative_to(root).as_posix()
        fqn = named[len("src/main/java/"):-len(".java")].replace("/", ".")
        specimens.runtime(root, package_rc=1, boot_ready=None,
                          detail="Failed to execute goal quarkus-maven-plugin:build",
                          log="Build step io.quarkus.spring.data.deployment.SpringDataJPAProcessor#build threw an exception: No implementation of interface %s was found" % fqn)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        wl_set = load_json(root / WORKLIST)
        if [i for i in wl_set["items"] if i["source"] == "runtime"] or [c for c in wl_set["clusters"] if c.get("gate") == "package"]:
            return _fail("a set-wide cause must mint nothing: %s" % [i.get("path") for i in wl_set["items"] if i["source"] == "runtime"])
        blocker = [u for u in wl_set.get("unlocatable") or [] if u.get("scope") == "spring-data-fragment-implementations"]
        if len(blocker) != 1 or named not in (blocker[0].get("observed") or []):
            return _fail("the set-wide failure is one typed blocker keeping what it named: %s" % (wl_set.get("unlocatable") or []))
        # control: a cause that IS about that type still lands on it
        specimens.runtime(root, package_rc=1, boot_ready=None,
                          detail="Failed to execute goal quarkus-maven-plugin:build",
                          log="Build step X#build threw an exception: io.quarkus.spring.data.deployment.UnableToParseMethodException on %s" % fqn)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        named_items = [i for i in load_json(root / WORKLIST)["items"] if i["source"] == "runtime"]
        if len(named_items) != 1 or named_items[0]["path"] != named or named_items[0]["kind"] != "compile":
            return _fail("an augmentation failure about a type must land on it: %s (wanted %s)" % (named_items, named))
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
        # The vehicle is a per-FILE cause. The Spring Data fragment cause is
        # set-wide and cannot carry a per-place obligation at all.
        two_defects = ("Build step X#build threw an exception: io.quarkus.spring.data.deployment.UnableToParseMethodException: "
                       "on %s (and later %s)" % (fqn(one), fqn(two)))
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
                          log="[error] after 2 rounds: Build step X#build threw an exception: io.quarkus.spring.data.deployment.UnableToParseMethodException reported at %s" % fqn(one))
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
                          log="Build step X#build threw an exception: void was not part of the Quarkus index, from %s" % fqn(one))
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)
        second = [i for i in load_json(root / WORKLIST)["items"] if i["source"] == "runtime"]
        if len(second) != 1 or second[0]["cause"] != "unindexed-type" or second[0]["path"] != one:
            return _fail("a second cause at the same file must be its own obligation: %s" % second)
        # back to the first cause for the acceptance case below
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build", log=two_defects)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        pipeline.admit(root)

        # b) that place repaired, another still failing: progress
        specimens.issue(root)
        (root / one).write_text((root / one).read_text(encoding="utf-8") + "// repaired\n", encoding="utf-8")
        specimens.runtime(root, package_rc=1, boot_ready=None, detail="Failed to execute goal quarkus-maven-plugin:build",
                          log="Build step X#build threw an exception: io.quarkus.spring.data.deployment.UnableToParseMethodException reported at %s" % fqn(two))
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
        # a skipped destination rescan must not copy the last incident slot
        # even when findings.json still exists: MTA analyses source, not
        # bytecode (v9 incidents 4→0 while 233 compile errors remained)
        specimens.verify(root, errors=[], failures=[], findings=f4)
        run_p = root / "verification" / "build" / "run.json"
        run = load_json(run_p)
        run["rescan"] = {"ran": False, "reused": True, "skipped": True, "rc": 0, "ms": 0}
        write_canonical(run_p, run)
        from planner.worklist import build_worklist
        wl = build_worklist(root)
        if wl["measure"]["known"]:
            return _fail("a skipped destination rescan must not copy the last incident slot: %s" % wl["measure"])
        kind = ((wl.get("sources") or {}).get("incidents") or {}).get("kind")
        if kind == "destination-rescan-reused":
            return _fail("reuse-as-known kind must not exist: %s" % kind)
        # tampered work list → advance refuses
        specimens.verify(root, errors=[], failures=[], findings=f4)
        doc = load_json(root / WORKLIST)
        doc["head"] = "c:tampered"
        write_canonical(root / WORKLIST, doc)
        p = _advance(root, "c:tampered", "t_z")
        if p.returncode != 2 or "LOOP_STALE_STATE" not in p.stderr:
            return _fail("tampered work list must refuse advance: %s" % p.stderr)
    print("OK: fix-until-green (checked-exception veto: a falling count does not admit an introduced unhandled exception; family bound to its introducing step: Owner→Pet CONTINUE in the same card without an attempt, a stalled continuation rejects, an exposure outside the family is a typed diagnosis; an introduced attribution diagnostic is rejected, not parked (javac reports every one of them at once; a flow code newly reported stays exposed; one the accepted tree already had is not introduced); a harness-caused deferral is cleared by a metadata-only disposition and the one budget sees it; a set-wide packaging cause reaches the work list as one typed blocker with no card, under permuted reported names; measurement contract: unrun tests / empty reports / failed runner / skipped rescan are unknown; baseline; issued card; diagnostic cannot advance; post-verify edit + unissued cluster refused with baseline intact; out-of-scope test edit rejected + reverted + reports discarded; accept commits; staged no-progress reverted from index; line shift is not a new obligation; unresolvable candidate is VERIFICATION_PENDING (no attempt); known no-progress defers; Operator rewind restores tree+budget in a new epoch; green → packaging → startup → M4 (unknown gates never mint; an environment blocker is not a card; a gate repair is accepted phase-aware); unresolved test = typed blocker; tampered list refused; PARITY CARD (v9 t_77cae2b2): the obligation carries gate=parity onto the issued card, the brief names its scenarios and what discharges them, a comparison that did not run retains the candidate without an attempt, one that still reports the obligation reverts it, a receipt composed for another card is not this card's measurement, a receipt that carries NO binding after a comparison bound to this card is the one a refusing composer left (VERIFICATION_PENDING, no attempt, never ACCEPTED), and the repair is ACCEPTED on the re-composed candidate-bound receipt with the tuple unchanged at [0,0,0], the receipt snapshotted with the accepted reports); SCRATCH IN THE TREE (v9 t_46556d5e): untracked files outside this migration's product that appear after the verification (javap's extracted .class files at the root) are a typed refusal naming them -- no attempt, the candidate untouched -- while a product path touched after the verification still REVERTS, and the same candidate is ACCEPTED once the scratch is removed, under a renamed specimen too); UNIT CHECKPOINT: the attribution veto is PARTITIONED for a unit card -- a candidate that invented a replacement the catalogue never wrote down still REVERTS with the symbols named (v9 t_3903f495), while one whose remaining diagnostics name the DOCUMENTED target is ACCEPTED with the compile count unchanged and records each tolerated diagnostic with its boundary and its catalogue row; an unresolved lookalike (UriBuilder with nothing importing it) is not the catalogued target either, and the accepted case is the one whose file IMPORTS it; every tolerated diagnostic is still an obligation on the rebuilt work list; the compiler naming another member of the same unit CONTINUES the card without spending an attempt, one naming a file the unit does not seal is a typed diagnosis, and a sealed member answered by deleting it violates however far the measure fell)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
