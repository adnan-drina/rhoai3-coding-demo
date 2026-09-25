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


def _run(argv: list[str], extra_env: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("HERMES_KANBAN_TASK", None)
    env.pop("HERMES_KANBAN_STOP_REQUEST", None)
    env.update(extra_env or {})
    return subprocess.run(argv, text=True, capture_output=True, env=env)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True).stdout


def _advance(root: Path, cluster: str, card: str, extra_env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return _run([sys.executable, str(ADVANCE), "--root", str(root), "--cluster", cluster, "--card", card, "--no-mint"],
                extra_env)


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
_PARITY_ENABLED_SID = "sc:cors-enabled-preflight-7b1a3d9234cd"
_PARITY_REASON = "header Access-Control-Allow-Origin None vs *; header Access-Control-Expose-Headers None vs errors"


def _parity_records(root: Path, verdict: str, binding: dict | None = None, *,
                    security_mode: str = "disabled", scenario: str | None = None) -> None:
    """What the M4 comparison leaves on disk: one scenario verdict and the
    receipt composed from it (compose-parity-receipt.py's shape).

    ``binding`` is what the records say they are OF. The M4 road leaves none
    (it is the accepted tree under the live seal); the acceptance path leaves
    the candidate binding compose-parity-receipt.py --issued writes.
    ``security_mode`` selects receipt.json vs receipt-enabled.json."""
    from planner.paths import PARITY_DIR
    from planner.worklist import parity_receipt_file

    mode = security_mode if security_mode in ("disabled", "enabled") else "disabled"
    sid = scenario or (_PARITY_ENABLED_SID if mode == "enabled" else _PARITY_SID)
    pdir = root / PARITY_DIR
    sub = "scenarios-enabled" if mode == "enabled" else "scenarios"
    (pdir / sub).mkdir(parents=True, exist_ok=True)
    extra = {"binding": dict(binding)} if binding else {}
    extra["security_mode"] = mode
    write_canonical(pdir / sub / ("sc_cors_enabled.json" if mode == "enabled" else "sc_cors.json"),
                    dict(extra, schema="rhoai3.scenario-parity/v1", entry_point=_PARITY_EP, scenario=sid,
                         verdict=verdict, reason=_PARITY_REASON if verdict != "PASS" else ""))
    write_canonical(root / parity_receipt_file(mode),
                    dict(extra, schema="rhoai3.parity-receipt/v1", verdict=verdict, total=1,
                         not_passed=0 if verdict == "PASS" else 1,
                         entry_points=[{"entry_point": _PARITY_EP, "verdict": verdict,
                                        "reason": "" if verdict == "PASS" else _PARITY_REASON,
                                        "scenarios": [sid], "coverage": {"positive": [sid], "negative": []}}]))


def _write_cors_corpus(root: Path, security_mode: str, scenario: str) -> None:
    rel = ("verification/scenarios-enabled/corpus.json" if security_mode == "enabled"
           else "verification/scenarios/corpus.json")
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    write_canonical(p, {"scenarios": [{"id": scenario, "method": "OPTIONS", "cors_policy": "crossorigin:1",
                                       "scenario_type": "browser-preflight"}]})


def _candidate_binding(root: Path, card: str) -> dict:
    """The binding the acceptance path's own comparison would have recorded:
    the candidate THIS verification measured and the card it was issued for."""
    from planner.paths import ADMISSION_RECEIPT, LOOP_ISSUED, VERIFY_RUN

    return {"mode": "candidate",
            "candidate_sha256": str(load_json(root / VERIFY_RUN).get("candidate_sha256") or ""),
            "issued_receipt_sha256": str((load_json(root / LOOP_ISSUED) if (root / LOOP_ISSUED).is_file() else {}).get("receipt_sha256")
                                         or load_json(root / ADMISSION_RECEIPT).get("receipt_digest") or ""),
            "card": card}


def _parity_run_record(root: Path, binding: dict | None, *, security_mode: str = "disabled") -> None:
    """The runner's own record of the comparison this verification made
    (run-parity.py's _run.json): what it was told to measure. run-verify.sh
    hands it the issued card whenever there is one, so on the acceptance path
    the run is candidate-bound and a receipt it composed would say so."""
    from planner.worklist import parity_run_file

    mode = security_mode if security_mode in ("disabled", "enabled") else "disabled"
    write_canonical(root / parity_run_file(mode),
                    {"schema": "rhoai3.parity-run/v1", "producer": "run-parity.py",
                     "security_mode": mode,
                     "issued": str(root / "verification" / "loop" / "issued.json") if binding else "",
                     "binding": dict(binding) if binding else {"mode": "sealed"},
                     "receipt": {"composed_by_this_run": True, "reason": ""}})


def _parity_verified(root: Path, findings: dict, *, ran: bool = True, verdict: str = "",
                     run_binding: dict | None = None, security_mode: str = "disabled",
                     scenario: str | None = None) -> None:
    """The acceptance pass for a parity card: run-verify.sh copies the receipt
    it started from, runs the comparison, records runtime.parity in run.json and
    re-measures. Here the comparison is simulated; everything else is real."""
    from planner.paths import VERIFY_RUN

    mode = security_mode if security_mode in ("disabled", "enabled") else "disabled"
    sid = scenario or (_PARITY_ENABLED_SID if mode == "enabled" else _PARITY_SID)
    # the acceptance path reaches parity through the packaging and startup
    # gates, and runs them on this candidate (a rejection discarded the last
    # candidate's receipts, so they are not inherited)
    specimens.runtime(root, package_rc=0, boot_ready=True)
    specimens.verify(root, errors=[], failures=[], findings=findings)
    doc = load_json(root / VERIFY_RUN)
    par = {
        "ran": ran, "rc": 0, "scenarios": [sid] if ran else [],
        "receipt_verdict": verdict, "security_mode": mode, "ms": 1}
    if mode == "enabled":
        par["scoped"] = bool(ran)
    doc.setdefault("runtime", {})["parity"] = par
    write_canonical(root / VERIFY_RUN, doc)
    if ran:
        _parity_run_record(root, run_binding, security_mode=mode)


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


def _enabled_mode_acceptance_case() -> int:
    """Disabled PASS + enabled FAIL, then an enabled replay must advance on
    that candidate's enabled receipt -- never the sealed disabled one.

    Missing, stale, wrong-mode or wrong-candidate evidence refuses."""
    from planner.paths import LOOP_ACCEPTED, MTA_FINDINGS, PARITY_DIR, VERIFY_DIR, VERIFY_RUN  # noqa: E402
    from planner.worklist import parity_receipt_file  # noqa: E402
    from _loop_common import snapshot_parity  # noqa: E402

    with tempfile.TemporaryDirectory(prefix="parity-en-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"),
                                    decisions=specimens.admitted_decisions(max_attempts=3))
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
        specimens.runtime(root, package_rc=0, boot_ready=True)
        _write_cors_corpus(root, "disabled", _PARITY_SID)
        _write_cors_corpus(root, "enabled", _PARITY_ENABLED_SID)
        _parity_records(root, "PASS", security_mode="disabled")
        _parity_records(root, "FAIL", security_mode="enabled")
        specimens.verify(root, errors=[], failures=[], findings=findings)
        pipeline.admit(root)
        snapshot_parity(root)
        from planner.worklist import item_ids, obligation_keys  # noqa: E402

        cur = load_json(root / WORKLIST)
        steps = load_json(root / LOOP_STEPS)
        steps["steps"][-1] = dict(steps["steps"][-1], measure=cur["measure"], runtime=cur.get("runtime") or {},
                                  obligation_keys=sorted(obligation_keys(cur)), item_ids=sorted(item_ids(cur)),
                                  candidate_sha256=load_json(root / LOOP_STATE)["candidate_sha256"])
        write_canonical(root / LOOP_STEPS, steps)
        wl = load_json(root / WORKLIST)
        cors = [i for i in wl["items"] if i.get("rule_id") == "PARITY_CORS"]
        if (len(cors) != 1 or cors[0].get("security_mode") != "enabled"
                or cors[0].get("scenario") != _PARITY_ENABLED_SID):
            return _fail("the enabled FAIL is the only CORS obligation: %s"
                         % [{k: i.get(k) for k in ("scenario", "rule_id", "security_mode")} for i in cors])
        cl = [c for c in wl["clusters"] if c["status"] == "open"]
        adapter = ra.adapter_path(ra.CORS)
        if (len(cl) != 1 or cl[0].get("gate") != "parity"
                or (cl[0].get("unit") or {}).get("family_key") != "source-cors-response-adapter/v1:enabled"):
            return _fail("the enabled CORS obligation is its own unit, not mixed with disabled: %s" % cl)
        cluster = cl[0]
        card = specimens.issue(root)
        issued = load_json(root / LOOP_ISSUED)
        if issued.get("security_mode") != "enabled" or card.get("logical_id") != cluster["id"]:
            return _fail("the issued card carries enabled mode: %s" % {k: issued.get(k) for k in ("security_mode", "cluster")})
        installer = HERE.parents[1] / "restore-source-response-shape" / "scripts" / "install-response-adapter.py"

        def install_adapter() -> None:
            ip = _run([sys.executable, str(installer), "--root", str(root), "--adapter", "cors"])
            if ip.returncode != 0:
                raise AssertionError("the capability must install on the issued card: %s%s" % (ip.stdout, ip.stderr))

        def keep_disabled_sealed() -> None:
            _parity_records(root, "PASS", security_mode="disabled")

        def before_enabled() -> None:
            src = root / parity_receipt_file("enabled")
            dst = root / VERIFY_DIR / "parity-before-enabled.json"
            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)

        install_adapter()

        attempts_before = dict(load_json(root / LOOP_STEPS).get("attempts") or {})

        # 0. silent fallback: runner recorded disabled, disabled PASS, enabled missing
        live_en = root / PARITY_DIR / "receipt-enabled.json"
        live_en.unlink(missing_ok=True)
        keep_disabled_sealed()
        _parity_verified(root, findings, ran=True, verdict="PASS", security_mode="disabled")
        p = _advance(root, cluster["id"], "t_en0")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "ACCEPTED" in p.stdout or "VERIFICATION_PENDING" not in blob:
            return _fail("disabled PASS beside missing enabled evidence must refuse acceptance: %s" % blob[-600:])
        if "wrong-security-mode" not in blob and "issuance-scope-missing" not in blob:
            return _fail("wrong-mode PASS must be a typed pending result: %s" % blob[-600:])
        if dict(load_json(root / LOOP_STEPS).get("attempts") or {}) != attempts_before:
            return _fail("wrong-mode PASS must not consume a repair attempt: %s" % load_json(root / LOOP_STEPS).get("attempts"))

        rp = _run([sys.executable, str(SCRIPTS / "restore-pending.py"), "--root", str(root), "--cluster", cluster["id"]])
        if rp.returncode != 0 or "restored" not in rp.stdout:
            return _fail("restore-pending after wrong-mode disabled PASS: %s%s" % (rp.stdout, rp.stderr))

        # 0b. missing issuance scope: no replay, typed pending, no attempt
        keep_disabled_sealed()
        live_en.unlink(missing_ok=True)
        _parity_verified(root, findings, ran=True, verdict="PASS", security_mode="enabled")
        issued_doc = load_json(root / LOOP_ISSUED)
        saved_mode, saved_sids = issued_doc.get("security_mode"), list(issued_doc.get("scenarios") or [])
        saved_eps, saved_scope = list(issued_doc.get("entry_points") or []), list(issued_doc.get("item_scope") or [])
        issued_doc.pop("security_mode", None)
        issued_doc["scenarios"] = []
        issued_doc["entry_points"] = []
        issued_doc["item_scope"] = []
        write_canonical(root / LOOP_ISSUED, issued_doc)
        run_doc = load_json(root / VERIFY_RUN)
        run_doc.setdefault("runtime", {})["parity"] = {
            "ran": False, "pending": "the issued card does not record a security mode or scenario scope",
            "cause": "issuance-scope-missing", "scoped": False, "scenarios": []}
        write_canonical(root / VERIFY_RUN, run_doc)
        attempts_before = dict(load_json(root / LOOP_STEPS).get("attempts") or {})
        p = _advance(root, cluster["id"], "t_en0")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "ACCEPTED" in p.stdout or "VERIFICATION_PENDING" not in blob or "issuance-scope-missing" not in blob:
            return _fail("missing issuance scope must pending without replay: %s" % blob[-600:])
        if dict(load_json(root / LOOP_STEPS).get("attempts") or {}) != attempts_before:
            return _fail("missing issuance scope must not consume a repair attempt")
        issued_doc["security_mode"] = saved_mode
        issued_doc["scenarios"] = saved_sids
        issued_doc["entry_points"] = saved_eps
        issued_doc["item_scope"] = saved_scope
        write_canonical(root / LOOP_ISSUED, issued_doc)
        rp = _run([sys.executable, str(SCRIPTS / "restore-pending.py"), "--root", str(root), "--cluster", cluster["id"]])
        if rp.returncode != 0 or "restored" not in rp.stdout:
            return _fail("restore-pending after missing issuance scope: %s%s" % (rp.stdout, rp.stderr))

        # 1. missing enabled receipt: the sealed disabled PASS is not "now"
        live_en.unlink(missing_ok=True)
        keep_disabled_sealed()
        _parity_verified(root, findings, ran=True, verdict="PASS", security_mode="enabled")
        p = _advance(root, cluster["id"], "t_en0")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "ACCEPTED" in p.stdout or "VERIFICATION_PENDING" not in blob:
            return _fail("missing enabled receipt must refuse acceptance: %s" % blob[-600:])

        rp = _run([sys.executable, str(SCRIPTS / "restore-pending.py"), "--root", str(root), "--cluster", cluster["id"]])
        if rp.returncode != 0 or "restored" not in rp.stdout:
            return _fail("restore-pending after missing enabled receipt: %s%s" % (rp.stdout, rp.stderr))

        # 2. stale enabled FAIL, candidate-bound
        keep_disabled_sealed()
        _parity_records(root, "FAIL", security_mode="enabled")
        before_enabled()
        _parity_verified(root, findings, verdict="FAIL", security_mode="enabled")
        binding = _candidate_binding(root, "t_en0")
        _parity_records(root, "FAIL", binding=binding, security_mode="enabled")
        _parity_run_record(root, binding, security_mode="enabled")
        p = _advance(root, cluster["id"], "t_en0")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "REVERTED" not in blob or "still reported" not in blob:
            return _fail("a stale enabled FAIL must refuse acceptance: %s" % blob[-600:])

        # REVERT restored the accepted reports, including any mandatory MTA
        # findings the baseline still carried; re-measure with the same
        # filtered findings the card was issued under so the enabled CORS
        # unit is the head again.
        _parity_records(root, "PASS", security_mode="disabled")
        _parity_records(root, "FAIL", security_mode="enabled")
        specimens.verify(root, errors=[], failures=[], findings=findings)
        pipeline.admit(root)
        retry = specimens.issue(root)
        cluster = next(c for c in load_json(root / WORKLIST)["clusters"] if c["id"] == retry.get("logical_id"))
        if cluster.get("gate") != "parity":
            return _fail("the reverted enabled card must re-issue a parity cluster: %s" % cluster)
        install_adapter()

        # 3. wrong-mode: disabled receipt candidate-bound PASS, enabled still FAIL
        keep_disabled_sealed()
        _parity_records(root, "FAIL", security_mode="enabled")
        before_enabled()
        _parity_verified(root, findings, verdict="FAIL", security_mode="enabled")
        wrong_disabled = _candidate_binding(root, "t_en1")
        _parity_records(root, "PASS", binding=wrong_disabled, security_mode="disabled")
        _parity_run_record(root, wrong_disabled, security_mode="enabled")
        p = _advance(root, cluster["id"], "t_en1")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "ACCEPTED" in p.stdout:
            return _fail("wrong-mode evidence (disabled PASS, enabled FAIL) must refuse: %s" % blob[-600:])

        if "REVERTED" in blob:
            _parity_records(root, "PASS", security_mode="disabled")
            _parity_records(root, "FAIL", security_mode="enabled")
            specimens.verify(root, errors=[], failures=[], findings=findings)
            pipeline.admit(root)
            retry = specimens.issue(root)
            cluster = next(c for c in load_json(root / WORKLIST)["clusters"] if c["id"] == retry.get("logical_id"))
            if cluster.get("gate") != "parity":
                return _fail("re-issue after wrong-mode revert: %s" % cluster)
            install_adapter()
        else:
            rp = _run([sys.executable, str(SCRIPTS / "restore-pending.py"), "--root", str(root), "--cluster", cluster["id"]])
            if rp.returncode != 0 or "restored" not in rp.stdout:
                return _fail("restore-pending after wrong-mode: %s%s" % (rp.stdout, rp.stderr))

        # 4. wrong-candidate binding on the enabled receipt
        keep_disabled_sealed()
        _parity_records(root, "PASS", security_mode="enabled")
        _parity_verified(root, findings, verdict="PASS", security_mode="enabled")
        _parity_records(root, "PASS", binding=_candidate_binding(root, "t_somebodyelse"), security_mode="enabled")
        before_enabled()
        p = _advance(root, cluster["id"], "t_en1")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "ACCEPTED" in p.stdout or "VERIFICATION_PENDING" not in blob:
            return _fail("wrong-candidate enabled receipt must refuse: %s" % blob[-600:])
        if "t_somebodyelse" not in blob:
            return _fail("the refusal names the card the enabled receipt was composed for: %s" % blob[-600:])

        rp = _run([sys.executable, str(SCRIPTS / "restore-pending.py"), "--root", str(root), "--cluster", cluster["id"]])
        if rp.returncode != 0 or "restored" not in rp.stdout:
            return _fail("restore-pending after wrong-candidate: %s%s" % (rp.stdout, rp.stderr))

        # 5. correctly bound enabled PASS; sealed disabled PASS still on disk
        keep_disabled_sealed()
        _parity_records(root, "PASS", security_mode="enabled")
        _parity_verified(root, findings, verdict="PASS", security_mode="enabled")
        binding = _candidate_binding(root, "t_en1")
        _parity_records(root, "PASS", binding=binding, security_mode="enabled")
        before_enabled()
        _parity_run_record(root, binding, security_mode="enabled")
        if load_json(root / parity_receipt_file("disabled")).get("verdict") != "PASS":
            return _fail("the trap needs the sealed disabled receipt still PASSing")
        if (load_json(root / parity_receipt_file("disabled")).get("binding") or {}).get("mode") == "candidate":
            return _fail("the disabled receipt must stay sealed: %s" % load_json(root / parity_receipt_file("disabled")).get("binding"))
        p = _advance(root, cluster["id"], "t_en1")
        blob = p.stdout + p.stderr
        if p.returncode != 0 or "ACCEPTED" not in p.stdout:
            return _fail("an enabled replay must advance on the enabled receipt: %s" % blob[-800:])
        step = load_json(root / LOOP_STEPS)["steps"][-1]
        if (step.get("parity") or {}).get("binding") != binding:
            return _fail("acceptance recorded the enabled candidate binding, not the disabled seal: %s" % step.get("parity"))
        snap = root / LOOP_ACCEPTED / "parity" / "receipt-enabled.json"
        if not snap.is_file() or load_json(snap).get("verdict") != "PASS":
            return _fail("the accepted snapshot is the enabled receipt: %s" % (load_json(snap) if snap.is_file() else snap))
        disabled_snap = root / LOOP_ACCEPTED / "parity" / "receipt.json"
        if disabled_snap.is_file() and (load_json(disabled_snap).get("binding") or {}).get("mode") == "candidate":
            return _fail("acceptance must not overwrite the disabled snapshot with the enabled candidate")
    return 0


def _mixed_mode_card_refusal_case() -> int:
    """A residual mixed-mode card is refused and must not write the enabled
    receipt into the disabled baseline snapshot."""
    from planner.paths import LOOP_ACCEPTED, MTA_FINDINGS, VERIFY_DIR  # noqa: E402
    from planner.worklist import parity_receipt_file  # noqa: E402
    from _loop_common import snapshot_parity  # noqa: E402

    with tempfile.TemporaryDirectory(prefix="parity-mx-") as td:
        root = specimens.build_dest(Path(td) / "dest", specimens.specimen("http"),
                                    decisions=specimens.admitted_decisions(max_attempts=3))
        from planner.paths import STRUCTURE  # noqa: E402

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
        specimens.runtime(root, package_rc=0, boot_ready=True)
        _write_cors_corpus(root, "disabled", _PARITY_SID)
        _write_cors_corpus(root, "enabled", _PARITY_ENABLED_SID)
        _parity_records(root, "PASS", security_mode="disabled")
        _parity_records(root, "FAIL", security_mode="enabled")
        specimens.verify(root, errors=[], failures=[], findings=findings)
        pipeline.admit(root)
        snapshot_parity(root)
        from planner.worklist import item_ids, obligation_keys  # noqa: E402

        cur = load_json(root / WORKLIST)
        steps = load_json(root / LOOP_STEPS)
        steps["steps"][-1] = dict(steps["steps"][-1], measure=cur["measure"], runtime=cur.get("runtime") or {},
                                  obligation_keys=sorted(obligation_keys(cur)), item_ids=sorted(item_ids(cur)),
                                  candidate_sha256=load_json(root / LOOP_STATE)["candidate_sha256"])
        write_canonical(root / LOOP_STEPS, steps)
        pipeline.admit(root)
        card = specimens.issue(root)
        cluster = next(c for c in load_json(root / WORKLIST)["clusters"] if c["id"] == card.get("logical_id"))
        disabled_snap = root / LOOP_ACCEPTED / "parity" / "receipt.json"
        before = disabled_snap.read_bytes() if disabled_snap.is_file() else b""
        issued = load_json(root / LOOP_ISSUED)
        issued["security_mode"] = "mixed"
        write_canonical(root / LOOP_ISSUED, issued)
        installer = HERE.parents[1] / "restore-source-response-shape" / "scripts" / "install-response-adapter.py"
        ip = _run([sys.executable, str(installer), "--root", str(root), "--adapter", "cors"])
        if ip.returncode != 0:
            return _fail("the capability must install on the issued card: %s%s" % (ip.stdout, ip.stderr))
        _parity_records(root, "PASS", security_mode="disabled")
        _parity_verified(root, findings, ran=True, verdict="PASS", security_mode="enabled")
        run_doc = load_json(root / VERIFY_RUN)
        (run_doc.setdefault("runtime", {}).setdefault("parity", {}))["security_mode"] = "mixed"
        write_canonical(root / VERIFY_RUN, run_doc)
        binding = _candidate_binding(root, "t_mx")
        _parity_records(root, "PASS", binding=binding, security_mode="enabled")
        src = root / parity_receipt_file("enabled")
        dst = root / VERIFY_DIR / "parity-before-enabled.json"
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        p = _advance(root, cluster["id"], "t_mx")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "ACCEPTED" in p.stdout:
            return _fail("a mixed-mode card must refuse acceptance: %s" % blob[-800:])
        if "LOOP_MIXED_SECURITY_MODE" not in blob or "partition" not in blob:
            return _fail("the mixed-card refusal must name partitioning: %s" % blob[-800:])
        if disabled_snap.is_file() and disabled_snap.read_bytes() != before:
            return _fail("mixed acceptance must not overwrite the disabled baseline snapshot")
        if disabled_snap.is_file() and (load_json(disabled_snap).get("binding") or {}).get("mode") == "candidate":
            return _fail("mixed acceptance must not write the enabled candidate into receipt.json")
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
               member_id: str = "", rule: str = "unit/diagnostic-family/v1", symbol: tuple[str, str] = ("type", _UNIT_RETIRED),
               targets: list[dict] | None = None, package: str = "org.springframework.samples.petclinic.rest") -> dict:
    """A sealed v4 unit over these files, and the cluster that carries it.

    Hand-written on purpose: what is under test here is the TRANSACTION -- the
    partition, the checkpoint and what each records -- not the former, which
    worklist.test.py asserts against its own four rules on two worlds."""
    from planner.worklist import batch_scope_digest, batch_scope_path

    scope = {
        "schema": "rhoai3.batch-scope/v4", "kind": "unit", "rule": rule,
        "producer": "worklist.build_unit_scope", "tool": {"model": "jdk-dest-model", "version": "1.2.0"},
        "cluster": "u:testunit", "unit_id": "u:testunit", "family_key": symbol[1],
        "writable_paths": sorted(paths),
        "symbols": [{"kind": symbol[0], "fqn": symbol[1], "path": paths[0]}],
        "target_symbols": (targets if targets is not None
                           else [{"from": _UNIT_RETIRED, "to": _UNIT_TARGET, "catalog_row": dict(_UNIT_CATALOG)}]),
        "members": [{"path": p, "type": "%s.%s" % (package, Path(p).stem),
                     "member_id": member_id, "occurrence": 0, "state": "reported", "identity": ident,
                     "item": iid}
                    for p, ident, iid in zip(paths, identities, item_ids)],
        "evidence": [{"kind": "javac", "ref": "%s names %s" % (p, symbol[1])} for p in paths],
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
    return {"id": "u:testunit", "kind": "compile", "path": paths[0], "label": symbol[1],
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


def _known_before_unknown_case(base: str = "org.acme.clinic") -> int:
    """B7 (v12 t_b33f25fa): a KNOWN regression is decided before any UNKNOWN.

    A unit whose sealed members include one the model cannot type (so the
    scope assessment is inconclusive) and whose candidate ALSO introduces an
    attribution diagnostic the accepted tree did not have -- v12's seven new
    files importing jakarta.enterprise.inject.ApplicationScoped -- is REVERTED
    with the symbol named, not parked as unassessable-scope. Control: the same
    inconclusive member with nothing introduced still pends. Run twice, the
    second time under renamed packages."""
    from planner.paths import MTA_FINDINGS  # noqa: E402
    from planner.worklist import batch_scope_digest

    _ATTR = "compiler.err.cant.resolve.location"

    def sym(name: str) -> str:
        return "cannot find symbol\n  symbol:   class %s\n  location: class R" % name

    with tempfile.TemporaryDirectory(prefix="chk-b7-") as td:
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=8))
        paths = _write_uri_controllers(root, _BUILDER)
        sealed = [paths[0], paths[1]]
        errs = [(p, 3, sym("UriComponentsBuilder"), _ATTR) for p in sealed]
        specimens.prepare_loop(root, errors=list(errs))
        findings = load_json(root / MTA_FINDINGS)
        wl = load_json(root / WORKLIST)
        rows = sorted([i for i in wl["items"] if str(i.get("source")) == "javac" and str(i.get("path")) in sealed],
                      key=lambda i: str(i["path"]))
        cluster = _seal_unit(root, sorted(sealed), [str(r["id"]) for r in rows], [str(r["identity"]) for r in rows])
        # a sealed member the destination model has no type for: a Java file
        # that declares nothing (the model cannot type it), so the unit's
        # assessment is inconclusive whatever the candidate does
        ghost = "src/main/java/%s/support/Pending%sImpl.java" % (base.replace(".", "/"), "Registry")
        (root / ghost).parent.mkdir(parents=True, exist_ok=True)
        (root / ghost).write_text("package %s.support;\n// declared by the unit, not yet written\n" % base, encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "fixture: the ghost member's file")
        scope_p = root / cluster["batch_scope"]["path"]
        scope = load_json(scope_p)
        scope["members"].append({"path": ghost, "type": "%s.support.PendingRegistryImpl" % base, "member_id": "",
                                 "occurrence": 0, "state": "reported", "identity": "ghost", "item": "ghost"})
        scope["writable_paths"] = sorted(set(scope["writable_paths"]) | {ghost})
        scope["digest"] = batch_scope_digest(scope)
        write_canonical(scope_p, scope)
        cluster["batch_scope"]["digest"] = scope["digest"]
        cluster["batch_scope"]["members"] = len(scope["members"])
        cluster["write_set"] = sorted(set(cluster["write_set"]) | {ghost})
        originals = {p: (root / p).read_text(encoding="utf-8") for p in sealed}

        # (1) inconclusive member AND an introduced diagnostic: REVERTED
        _issue_cluster(root, cluster, "t_b7a")
        for p in sealed:
            (root / p).write_text(originals[p].replace(
                "import java.net.URI;\n", "import java.net.URI;\nimport jakarta.enterprise.inject.ApplicationScoped;\n"),
                encoding="utf-8")
        specimens.verify(root, errors=[(p, 4, sym("ApplicationScoped"), _ATTR) for p in sealed],
                         failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_b7a")
        blob = p.stdout + p.stderr
        if "unassessable-scope" in blob or "VERIFICATION_PENDING" in blob:
            return _fail("a known introduced diagnostic is decided before an unassessable member (%s): %s" % (base, blob[-700:]))
        if p.returncode == 0 or "REVERTED" not in blob or "INTRODUCED_COMPILE_DIAGNOSTIC" not in blob or "ApplicationScoped" not in blob:
            return _fail("the candidate is REVERTED naming the introduced symbol (%s): rc=%s %s" % (base, p.returncode, blob[-700:]))
        if any((root / q).read_text(encoding="utf-8") != originals[q] for q in sealed):
            return _fail("the rejected candidate is reverted")
        if (load_json(root / LOOP_STEPS).get("attempts") or {}).get("rk:unit:u:testunit") != 1:
            return _fail("the conclusive regression spends exactly one attempt: %s" % load_json(root / LOOP_STEPS).get("attempts"))

        # (2) control: the same inconclusive member, nothing introduced -- still pends
        pipeline.admit(root)
        _issue_cluster(root, cluster, "t_b7b")
        for p in sealed:
            (root / p).write_text(originals[p].replace("import java.net.URI;\n", "import java.net.URI;\n// progress\n"),
                                  encoding="utf-8")
        specimens.verify(root, errors=list(errs), failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_b7b")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "VERIFICATION_PENDING" not in blob or "unassessable-scope" not in blob:
            return _fail("with nothing introduced an unassessable member still pends (%s): rc=%s %s" % (base, p.returncode, blob[-700:]))
        if (load_json(root / LOOP_STEPS).get("attempts") or {}).get("rk:unit:u:testunit") != 1:
            return _fail("a pending verdict spends no attempt")
    return 0


def _missing_baseline_case() -> int:
    """B7: without the accepted diagnostics snapshot an undecided diagnostic
    is not an absent regression. The candidate pends DIAGNOSTIC_BASELINE_MISSING,
    naming the snapshot, and is never accepted on the fall."""
    from planner.paths import LOOP_ACCEPTED, MTA_FINDINGS  # noqa: E402

    _ATTR = "compiler.err.cant.resolve.location"
    with tempfile.TemporaryDirectory(prefix="chk-b7m-") as td:
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
        paths = _write_uri_controllers(root, _BUILDER)
        owner, pet = paths[0], paths[1]
        specimens.prepare_loop(root, errors=[(owner, 3, "cannot find symbol class UriComponentsBuilder", _ATTR),
                                             (pet, 3, "cannot find symbol class ResponseEntity", _ATTR)])
        findings = load_json(root / MTA_FINDINGS)
        cluster = next(c for c in load_json(root / WORKLIST)["clusters"] if owner in (c.get("write_set") or []))
        snap = root / LOOP_ACCEPTED / VERIFY_DIAGNOSTICS.name
        if not snap.is_file():
            return _fail("fixture: the accepted diagnostics snapshot must exist to be removed: %s" % snap)
        snap.unlink()
        _issue_cluster(root, cluster, "t_b7m")
        f = root / owner
        f.write_text(f.read_text(encoding="utf-8").replace("import java.net.URI;\n", "import java.net.URI;\n// x\n"),
                     encoding="utf-8")
        # Owner's diagnostic gone (the count falls), and a NEW one in Pet
        specimens.verify(root, errors=[(pet, 7, "cannot find symbol class Mystery", _ATTR)], failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_b7m")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "ACCEPTED" in p.stdout:
            return _fail("a missing diagnostics baseline cannot accept on the fall: rc=%s %s" % (p.returncode, blob[-600:]))
        if "DIAGNOSTIC_BASELINE_MISSING" not in blob or VERIFY_DIAGNOSTICS.name not in blob:
            return _fail("the refusal names the missing snapshot: %s" % blob[-600:])
    return 0


def _continuation_case() -> int:
    """B8 (v12 t_b33f25fa, the legacy path where it happened): an ACCEPTED
    step whose admission is then refused because the run's activation is gone
    (pins.json back to not-activated) records the continuation as
    admission-refused, names the refusal, and tells the card to block -- the
    accepted commit stands. Once the activation is back, re-running
    advance.py with the same arguments finishes the continuation (the H9b
    idempotent path) without a second step."""
    from planner.paths import MTA_FINDINGS  # noqa: E402

    _ATTR = "compiler.err.cant.resolve.location"
    with tempfile.TemporaryDirectory(prefix="chk-b8-") as td:
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
        paths = _write_uri_controllers(root, _BUILDER)
        owner, pet = paths[0], paths[1]
        pet_err = (pet, 3, "cannot find symbol class ResponseEntity", _ATTR)
        specimens.prepare_loop(root, errors=[(owner, 3, "cannot find symbol class UriComponentsBuilder", _ATTR), pet_err])
        findings = load_json(root / MTA_FINDINGS)
        cluster = next(c for c in load_json(root / WORKLIST)["clusters"] if owner in (c.get("write_set") or []))
        _issue_cluster(root, cluster, "t_b8")
        f = root / owner
        f.write_text(f.read_text(encoding="utf-8").replace("import java.net.URI;\n", "import java.net.URI;\n// ok\n"),
                     encoding="utf-8")
        specimens.verify(root, errors=[pet_err], failures=[], findings=findings)
        pins_p = root / ".hermes" / "pins.json"
        pins_doc = load_json(pins_p)
        activated = json.loads(json.dumps(pins_doc))
        pins_doc["pins"]["planner"] = {"activation": "not-activated"}   # the v12 loss
        write_canonical(pins_p, pins_doc)
        p = _advance(root, cluster["id"], "t_b8")
        blob = p.stdout + p.stderr
        cont = load_json(root / "verification" / "loop" / "continuation.json")
        if "OK: ACCEPTED" not in p.stdout or p.returncode == 0:
            return _fail("the accepted step stands and the refused admission is not a success: rc=%s %s" % (p.returncode, blob[-600:]))
        if "LOOP_ADMISSION" not in blob or "PLANNER_NOT_ACTIVATED" not in blob or "kanban_block" not in blob:
            return _fail("the refusal names the missing activation and the block terminator: %s" % blob[-600:])
        if cont.get("state") != "admission-refused" or cont.get("predecessor") != "t_b8" or not cont.get("reasons"):
            return _fail("the continuation is recorded as admission-refused for this card: %s" % cont)
        write_canonical(pins_p, activated)
        p = _advance(root, cluster["id"], "t_b8")
        blob = p.stdout + p.stderr
        cont = load_json(root / "verification" / "loop" / "continuation.json")
        if p.returncode != 0 or "ACCEPTED already" not in p.stdout or cont.get("state") != "admitted":
            return _fail("re-running advance.py finishes the continuation once the activation is back: rc=%s %s %s"
                         % (p.returncode, cont, blob[-500:]))
        if sum(1 for s_ in load_json(root / LOOP_STEPS)["steps"] if s_.get("card") == "t_b8") != 1:
            return _fail("finishing the continuation records no second step")
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


def _restore_runner_records_case() -> int:
    """v10 t_27cea939: rejecting a scoped enabled candidate restores the
    accepted receipts and cannot leave that candidate's ``_run-enabled.json``
    to be read as a full-mode comparison. Discarded runner evidence is kept
    aside. A newer scoped receipt must not acquire an older full-mode runner;
    check-mode-parity refuses that pairing."""
    from planner.paths import LOOP_ACCEPTED, LOOP_ISSUED, PARITY_DIR
    from _loop_common import LOOP_DISCARDED, restore_reports, snapshot_parity
    from m4_parity import measure

    artifact = "a" * 64

    def receipt(mode, verdict="FAIL"):
        return {"schema": "rhoai3.parity-receipt/v1", "security_mode": mode, "verdict": verdict,
                "entry_points": [{"entry_point": "ep:x#y():http", "verdict": verdict, "scenarios": ["sc:one"]}]}

    def full_run(mode):
        return {"schema": "rhoai3.parity-run/v1", "ok": True, "security_mode": mode,
                "scenario_filter": [], "artifact": {"sha256": artifact},
                "receipt": {"composed_by_this_run": True}}

    def scoped_run(mode):
        return {"schema": "rhoai3.parity-run/v1", "ok": True, "security_mode": mode,
                "scenario_filter": ["sc:cors-enabled-preflight-7b1a3d9234cd"],
                "artifact": {"sha256": "b" * 64}, "receipt": {"composed_by_this_run": True},
                "binding": {"mode": "candidate", "card": "t_27cea939"}}

    with tempfile.TemporaryDirectory(prefix="restore-run-") as td:
        root = Path(td)
        pdir = root / PARITY_DIR
        pdir.mkdir(parents=True)
        (root / LOOP_ISSUED).parent.mkdir(parents=True, exist_ok=True)
        write_canonical(root / LOOP_ISSUED, {"task_id": "t_27cea939", "cluster": "c:cors"})
        write_canonical(pdir / "receipt.json", receipt("disabled", "INCONCLUSIVE"))
        write_canonical(pdir / "receipt-enabled.json", receipt("enabled", "FAIL"))
        write_canonical(pdir / "_run.json", full_run("disabled"))
        write_canonical(pdir / "_run-enabled.json", full_run("enabled"))
        snapshot_parity(root)
        snap_enabled = (root / LOOP_ACCEPTED / "parity" / "_run-enabled.json").read_bytes()
        if b"scenario_filter" in snap_enabled and b"cors-enabled-preflight" in snap_enabled:
            return _fail("a full-mode snapshot must not store a scoped filter as the baseline runner")
        # discard a scoped enabled candidate: leftover runner beside restored receipts
        write_canonical(pdir / "receipt-enabled.json", dict(receipt("enabled", "INCONCLUSIVE"),
                                                            binding={"mode": "candidate", "card": "t_27cea939"}))
        write_canonical(pdir / "_run-enabled.json", scoped_run("enabled"))
        live_scoped = (pdir / "_run-enabled.json").read_bytes()
        restore_reports(root)
        restored = load_json(pdir / "_run-enabled.json")
        if list(restored.get("scenario_filter") or []) or restored.get("binding", {}).get("card") == "t_27cea939":
            return _fail("restore must not present the discarded scoped runner: %s" % restored)
        if (pdir / "_run-enabled.json").read_bytes() != snap_enabled:
            return _fail("restore puts the accepted full-mode runner back")
        if load_json(pdir / "receipt-enabled.json").get("verdict") != "FAIL":
            return _fail("restore puts the accepted enabled receipt back")
        discarded = list((root / LOOP_DISCARDED).rglob("_run-enabled.json"))
        if len(discarded) != 1 or discarded[0].read_bytes() != live_scoped:
            return _fail("the discarded scoped runner is preserved separately: %s" % discarded)
        measured = measure(root)
        if any("did not compose a full-mode comparison" in e for e in measured.get("errors") or []):
            return _fail("m4_parity must not read a scoped leftover as the restored comparison: %s" % measured)
        if measured.get("rc") not in (0, 1):
            return _fail("the restored baseline is a coherent full-mode comparison: %s" % measured)
        # a newer scoped receipt must never acquire the older full-mode runner
        write_canonical(pdir / "receipt-enabled.json", dict(receipt("enabled", "INCONCLUSIVE"),
                                                            binding={"mode": "candidate", "candidate_sha256": "b" * 64,
                                                                     "card": "t_candidate_b"}))
        snapshot_parity(root)
        snap_enabled = root / LOOP_ACCEPTED / "parity" / "_run-enabled.json"
        if snap_enabled.is_file():
            kept = load_json(snap_enabled)
            if (not list(kept.get("scenario_filter") or [])
                    and (kept.get("artifact") or {}).get("sha256") == artifact):
                return _fail("snapshot_parity must not keep runner A beside candidate B: %s" % kept)
        write_canonical(pdir / "_run-enabled.json", full_run("enabled"))
        measured = measure(root)
        if measured.get("rc") == 0:
            return _fail("check-mode-parity must refuse candidate B proven by runner A: %s" % measured)
        if not any("candidate receipt is paired with a full-mode runner" in e for e in measured.get("errors") or []):
            return _fail("the refusal names the mismatched provenance: %s" % measured)
        # legacy snapshot with no runner: leftover scoped file is removed, not read as full-mode
        (root / LOOP_ACCEPTED / "parity" / "_run-enabled.json").unlink(missing_ok=True)
        (root / LOOP_ACCEPTED / "parity" / "_run.json").unlink(missing_ok=True)
        write_canonical(pdir / "_run-enabled.json", scoped_run("enabled"))
        restore_reports(root)
        if (pdir / "_run-enabled.json").is_file():
            return _fail("a snapshot without a runner cannot keep the discarded scoped record live")
        measured = measure(root)
        if any("did not compose a full-mode comparison" in e for e in measured.get("errors") or []):
            return _fail("absence is not a scoped leftover presented as full-mode: %s" % measured)
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


def _unit_gate_handoff_case(base: str = "p") -> int:
    """v12 t_b33f25fa, and B6: a unit on the PACKAGE gate is accepted at its
    checkpoint only when its issued obligation is gone, every sealed member
    assesses clean, and every failure the gate now reports has POSITIVE
    evidence: the typed reach test says OUTSIDE_SCOPE (never UNKNOWN) and the
    failure is shown independent of the candidate -- an accepted step already
    recorded it, or its file-local expression is unchanged since the accepted
    commit. Each missing condition keeps it pending (None) and, where the
    handoff was the question, says GATE_HANDOFF_UNPROVEN with the cause."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("advance_mod", ADVANCE)
    adv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adv)
    root = Path(tempfile.mkdtemp())
    rel = "src/main/java/%s/RootRestController.java" % base.replace(".", "/")
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    spel_src = 'class RootRestController {\n    @Value("#{servletContext.contextPath}")\n    String path;\n}\n'
    (root / rel).write_text(spel_src, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "accepted")
    accepted = _git(root, "rev-parse", "HEAD").strip()
    prev = {"commit": accepted, "item_ids": []}
    steps = {"steps": [prev]}
    unreached = lambda _r, _s, rel: ("OUTSIDE_SCOPE", "%s declares X, which the unit's sealed symbols do not reach" % rel)
    reached = lambda _r, _s, rel: ("IN_SCOPE", "sealed: %s implements the sealed parent" % rel)
    no_type = lambda _r, _s, rel: ("UNKNOWN", "the model has no type for %s" % rel)
    no_model = lambda _r, _s, rel: ("UNKNOWN", "the destination model is unavailable, so the file's types cannot be named")
    rows = [{"verdict": "ok", "member": "a#b"}] * 3
    issued = {"gate_items": ["rt:package:old"]}
    spel = {"id": "rt:package:new", "gate": "package", "path": rel,
            "cause": "unsupported-spel", "unlocated": False, "set_wide": []}
    cur = {"items": [spel], "measure": {"known": True}}

    def call(**kw):
        a = dict(rows=rows, issued=issued, cur=cur, gate="package", reach=unreached, prev=prev, steps=steps, changed=[])
        a.update(kw)
        why: list = []
        got = adv._unit_gate_handoff(root, {}, a["rows"], a["issued"], a["cur"], a["gate"], reach=a["reach"],
                                     prev=a["prev"], steps=a["steps"], changed=a["changed"], why=why)
        return got, why

    h, _ = call()
    if not h or h["now_reported"][0]["path"] != rel or h["issued"] != ["rt:package:old"] or "closing card" not in h["owed_by"]:
        return _fail("the unit whose gate now stops on an unreached, unchanged obligation must hand off: %s" % h)
    if "unsupported-spel" not in h["reason"] or "RootRestController" not in h["reason"]:
        return _fail("the handoff reason must name the obligation and where it is: %s" % h["reason"])
    ind = h["now_reported"][0]["independence"]
    if ind.get("kind") != "unchanged-expression" or "#{servletContext.contextPath}" not in ind.get("expressions", []):
        return _fail("the handoff records the independence evidence it rests on: %s" % ind)
    if h.get("accepted_commit") != accepted[:12] or h.get("debt") != {"package": "owed", "boot": "owed"}:
        return _fail("the handoff records the accepted commit and the package/boot debt: %s" % h)
    # a pre-existing cause that is NOT file-local may hand off only when an
    # accepted step already recorded that exact obligation
    query = dict(spel, id="rt:package:q", cause="query-invalid")
    h2, _ = call(cur={"items": [query], "measure": {"known": True}},
                 steps={"steps": [dict(prev, item_ids=["rt:package:q"])]})
    if not h2 or h2["now_reported"][0]["independence"].get("kind") != "baseline-named":
        return _fail("a pre-existing unrelated cause an accepted step recorded can continue: %s" % h2)
    changed_expr = spel_src.replace("#{servletContext.contextPath}", "#{request.contextPath}")
    for why_name, kw, token in (
        ("reach is UNKNOWN: the model has no type (B6)", dict(reach=no_type), "reach UNKNOWN"),
        ("reach is UNKNOWN: the model is unavailable (B6)", dict(reach=no_model), "reach UNKNOWN"),
        ("a failure in an untouched file whose cause is not file-local and no step recorded (B6)",
         dict(cur={"items": [query], "measure": {"known": True}}), "independence UNKNOWN"),
        ("the file the gate names is one the candidate changed", dict(changed=[rel]), "independence UNKNOWN"),
        ("the measure is not known", dict(cur={"items": [spel], "measure": {"known": False}}), "not known"),
        ("the new failure is unlocated", dict(cur={"items": [dict(spel, unlocated=True)], "measure": {"known": True}}), "unlocated"),
        ("the new failure is set-wide", dict(cur={"items": [dict(spel, set_wide=["repositories"])], "measure": {"known": True}}), "set-wide"),
        ("the new failure is in a file the unit reaches", dict(reach=reached), "reach IN_SCOPE"),
    ):
        got, why = call(**kw)
        if got is not None:
            return _fail("%s: the unit must stay pending, got a handoff %s" % (why_name, got))
        if not why or "GATE_HANDOFF_UNPROVEN" not in why[0] or token not in why[0]:
            return _fail("%s: the refusal names GATE_HANDOFF_UNPROVEN and its cause: %s" % (why_name, why))
    # the file-local expression changed between the accepted tree and the candidate
    (root / rel).write_text(changed_expr, encoding="utf-8")
    got, why = call()
    (root / rel).write_text(spel_src, encoding="utf-8")
    if got is not None or not why or "independence UNKNOWN" not in why[0]:
        return _fail("a changed file-local expression is not independent of the candidate: %s %s" % (got, why))
    for why_name, kw in (
        ("the issued obligation is still reported", dict(cur={"items": [spel, dict(spel, id="rt:package:old")], "measure": {"known": True}})),
        ("a sealed member is inconclusive", dict(rows=rows + [{"verdict": "inconclusive", "member": "c#d"}])),
        ("a sealed member violates", dict(rows=rows + [{"verdict": "violates", "member": "c#d"}])),
        ("the gate is not package", dict(gate="boot")),
        ("the gate reports nothing", dict(cur={"items": [], "measure": {"known": True}})),
        ("nothing was issued on the gate", dict(issued={"gate_items": []})),
    ):
        got, _ = call(**kw)
        if got is not None:
            return _fail("%s: the unit must stay pending, got a handoff %s" % (why_name, got))
    shutil.rmtree(root, ignore_errors=True)
    return 0


def _adapter_owned_retirement_advance_case(base: str = "org.springframework.samples.petclinic.rest") -> int:
    """V16-1 (v16 t_7074fcda), end to end through the transaction.

    A leaf unit over two controllers retiring @CrossOrigin -- class-level on
    one, method-level on the other, both with arguments -- whose files also
    carry an unrelated diagnostic another card owns, so the compiler can only
    attribute them partially. The candidate that removes the annotations and
    their import is ACCEPTED through the existing parsed-symbol-absence proof
    (no shortcut: the step records the proof assess_unit gave); one that
    leaves a method-level annotation is not. Run twice, the second time under
    renamed packages."""
    from planner.paths import MTA_FINDINGS  # noqa: E402
    from planner.worklist import adapter_owned_annotations, assess_unit

    _ATTR = "compiler.err.cant.resolve.location"
    owned = "org.springframework.web.bind.annotation.CrossOrigin"
    row = adapter_owned_annotations(GOLDEN)[owned]

    def sym(name: str) -> str:
        return "cannot find symbol\n  symbol:   class %s\n  location: class R" % name

    src = "src/main/java/%s/" % base.replace(".", "/")
    imp = "import %s;\n" % owned

    def ctl(name: str, *, head: str = "", cls: str = "", meth: str = "") -> str:
        return ("package %s;\n%s%spublic class %s {\n    %spublic String list() { return \"\"; }\n"
                "    public PendingType pending() { return null; }\n}\n" % (base, head, cls, name, meth))

    with tempfile.TemporaryDirectory(prefix="chk-owned-") as td:
        spec = specimens.specimen("http")
        root = specimens.build_dest(Path(td) / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=8))
        owner, pet = src + "OwnerRestController.java", src + "PetRestController.java"
        originals = {owner: ctl("OwnerRestController", head=imp, cls='@CrossOrigin(exposedHeaders = "errors, content-type")\n'),
                     pet: ctl("PetRestController", head=imp, meth='@CrossOrigin(origins = "http://client.example", maxAge = 1800) ')}
        for rel, text in originals.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        sealed = sorted(originals)
        unrelated = [(p, 6, sym("PendingType"), _ATTR) for p in sealed]
        specimens.prepare_loop(root, errors=[(p, 4, sym("CrossOrigin"), _ATTR) for p in sealed] + unrelated)
        findings = load_json(root / MTA_FINDINGS)
        wl = load_json(root / WORKLIST)
        rows = sorted([i for i in wl["items"] if str(i.get("source")) == "javac" and "CrossOrigin" in str(i.get("message"))],
                      key=lambda i: str(i["path"]))
        if [r["path"] for r in rows] != sealed:
            return _fail("the fixture needs one CrossOrigin diagnostic per controller: %s" % rows)
        retire = [{"from": owned, "to": "", "retire": True, "action": row["action"],
                   "catalog_row": {"catalog": "compat-mapping.json", "block": "adapter_owned_annotations", "key": owned,
                                   "kind": "annotation", "adapter": row["adapter"], "contract": row["contract"]}}]
        cluster = _seal_unit(root, sealed, [str(r["id"]) for r in rows], [str(r["identity"]) for r in rows],
                             member_id="list", rule="unit/package-leaf/v1", symbol=("annotation", owned), targets=retire,
                             package=base)

        # (1) a method-level annotation left behind: the sealed diagnostic is
        # still reported, and the member still names the retired symbol
        _issue_cluster(root, cluster, "t_own1")
        (root / owner).write_text(ctl("OwnerRestController"), encoding="utf-8")
        specimens.verify(root, errors=[(pet, 4, sym("CrossOrigin"), _ATTR)] + unrelated, failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_own1")
        blob = p.stdout + p.stderr
        if p.returncode == 0 or "ACCEPTED" in blob:
            return _fail("a candidate that leaves a @CrossOrigin is not accepted (%s): rc=%s %s" % (base, p.returncode, blob[-700:]))
        for rel, text in originals.items():
            (root / rel).write_text(text, encoding="utf-8")

        # (2) the retirement: annotations and import gone, handlers and routes
        # kept, the unrelated diagnostic still standing
        pipeline.admit(root)
        _issue_cluster(root, cluster, "t_own2")
        for rel, name in ((owner, "OwnerRestController"), (pet, "PetRestController")):
            (root / rel).write_text(ctl(name), encoding="utf-8")
        scope = load_json(root / cluster["batch_scope"]["path"])
        proofs = {r.get("proof") for r in assess_unit(root, scope)}
        if proofs != {"parsed-symbol-absence"}:
            return _fail("the retirement is decided by the existing parsed-symbol-absence proof (%s): %s" % (base, proofs))
        specimens.verify(root, errors=list(unrelated), failures=[], findings=findings)
        p = _advance(root, cluster["id"], "t_own2")
        blob = p.stdout + p.stderr
        if p.returncode != 0 or "ACCEPTED" not in blob:
            return _fail("the retirement is accepted despite the unrelated partial attribution (%s): rc=%s %s" % (base, p.returncode, blob[-700:]))
        step = (load_json(root / LOOP_STEPS)["steps"] or [{}])[-1]
        if (step.get("unit") or {}).get("unit_id") != "u:testunit" or step.get("explained_regressions"):
            return _fail("the step records the unit and tolerated nothing (%s): %s" % (base, step.get("unit")))
        after = {str(i.get("identity") or "") for i in load_json(root / WORKLIST)["items"] if str(i.get("source")) == "javac"}
        if len(after) != len(unrelated):
            return _fail("the unrelated diagnostics stay obligations of their own (%s): %s" % (base, sorted(after)))
    return 0


def _scope_aware_pending_case(base: str = "org.acme.inventory") -> int:
    """V16-2 (v16 t_d3f89ded): what the package gate names NOW, against the
    card's scope. A location outside the write set is not independence: a bean
    the card added makes an unchanged consumer's injection point ambiguous, and
    the error names the consumer. So:

    * a card-added bean causing an ambiguity at an outside consumer gets no
      handoff, and the pending verdict says the candidate may have caused it;
    * a failure an accepted step already recorded (proven pre-existing) may
      hand off, with package/boot debt and -- for a unit that owes CDI beans --
      the bean obligations on the record and the wiring marked unverified;
    * a failure with no location has an UNKNOWN cause and stays pending;
    * no pending message ever asks for an edit outside the write set.
    Run twice, the second time under renamed packages."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("advance_scope", ADVANCE)
    adv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adv)
    src = "src/main/java/%s/" % base.replace(".", "/")
    delegate, consumer = src + "repository/ItemRepositoryImpl.java", src + "service/StockService.java"
    card_file = src + "web/RootController.java"
    ambiguity = ("Build step io.quarkus.arc.deployment.ArcProcessor#validate threw an exception: "
                 "jakarta.enterprise.inject.AmbiguousResolutionException: Ambiguous dependencies for type "
                 "%s.repository.ItemRepository and qualifiers [@Default]\n - injection target: %s.service.StockService#items\n"
                 " - available beans:\n  - CLASS bean [types=[...], target=%s.springdatajpa.SpringDataItemRepository_91a5Impl]\n"
                 "  - CLASS bean [types=[...], target=%s.repository.ItemRepositoryImpl]" % (base, base, base, base))
    amb = {"id": "rt:package:amb", "gate": "package", "path": consumer, "cause": "ambiguous-injection",
           "unlocated": False, "set_wide": [], "message": ambiguity}
    unit_issued = {"items": ["rt:package:frag"], "gate_items": ["rt:package:frag"], "write_set": [delegate]}
    card_issued = {"items": ["rt:package:spel"], "gate_items": ["rt:package:spel"], "write_set": [card_file]}
    forbidden = ("in the same candidate", "repair it in this candidate", "repair the members it now names")

    def unedited(text: str) -> bool:
        return not any(f in text for f in forbidden) and "must not edit" in text

    root = Path(tempfile.mkdtemp())
    _git(root, "init", "-q")
    (root / "README").write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "accepted")
    prev = {"commit": _git(root, "rev-parse", "HEAD").strip(), "item_ids": []}
    unreached = lambda _r, _s, rel: ("OUTSIDE_SCOPE", "%s is not reached by the unit's sealed symbols" % rel)
    beans = [{"parent": "%s.repository.ItemRepository" % base, "type": "%s.repository.ItemRepositoryImpl" % base,
              "path": delegate, "contract": "spring-data-fragment-impl/v1",
              "cdi": {"scope": "jakarta.enterprise.context.ApplicationScoped", "typed": "jakarta.enterprise.inject.Typed",
                      "types": ["%s.repository.ItemRepositoryImpl" % base]}}]
    scope_doc = {"implementation_obligations": beans}
    rows = [{"verdict": "ok", "member": "a#b"}]

    # (1) the card ADDED the bean the ambiguity names; the consumer is untouched
    why: list = []
    h = adv._unit_gate_handoff(root, scope_doc, rows, unit_issued, {"items": [amb], "measure": {"known": True}}, "package",
                               reach=unreached, prev=prev, steps={"steps": [prev]}, changed=[delegate], why=why)
    if h is not None or not why or "independence UNKNOWN" not in why[0]:
        return _fail("a card-added bean's outside ambiguity gets no independent handoff (%s): %s %s" % (base, h, why))
    g = adv._gate_scope_guidance(unit_issued, {"items": [amb]}, "package", [delegate])
    if (not g or g["cause"] != "outside-scope-prerequisite" or g["record"]["caused_by_candidate"] != [delegate]
            or "may have caused it and no handoff is possible" not in g["reason"] or consumer not in g["reason"]):
        return _fail("the pending verdict names the outside consumer and the bean this candidate changed (%s): %s" % (base, g))
    if not unedited(g["reason"]):
        return _fail("the pending message never asks for an edit outside the write set (%s): %s" % (base, g["reason"]))
    # the v16 shape: the bean came from an EARLIER accepted card, this card
    # (RootController) changed nothing the error names -- still no handoff,
    # and the prerequisite is the Operator's, beside the pending card
    g = adv._gate_scope_guidance(card_issued, {"items": [amb]}, "package", [card_file])
    if (not g or g["cause"] != "outside-scope-prerequisite" or g["record"]["caused_by_candidate"]
            or "operator-step.py beside this pending card" not in g["reason"] or "write set: %s" % card_file not in g["reason"]
            or [f["path"] for f in g["record"]["failures"]] != [consumer]):
        return _fail("an outside failure the candidate did not name is an Operator prerequisite (%s): %s" % (base, g))
    if not unedited(g["reason"]) or delegate not in g["record"]["failures"][0]["beans_named"]:
        return _fail("the record names the beans, the message no edit (%s): %s" % (base, g))

    # (2) a PROVEN pre-existing failure: an accepted step recorded it
    spel = {"id": "rt:package:spel", "gate": "package", "path": card_file, "cause": "unsupported-spel",
            "unlocated": False, "set_wide": []}
    h = adv._unit_gate_handoff(root, scope_doc, rows, unit_issued, {"items": [spel], "measure": {"known": True}}, "package",
                               reach=unreached, prev=prev, steps={"steps": [dict(prev, item_ids=["rt:package:spel"])]},
                               changed=[delegate], why=[])
    if not h or h["now_reported"][0]["independence"]["kind"] != "baseline-named" or h["debt"] != {"package": "owed", "boot": "owed"}:
        return _fail("a proven pre-existing failure hands off with package/boot debt (%s): %s" % (base, h))
    if ([b["type"] for b in h.get("bean_obligations") or []] != [beans[0]["type"]]
            or not str(h.get("bean_wiring") or "").startswith("unverified") or "NOT verified" not in h["reason"]):
        return _fail("the handoff keeps the bean obligations traceable and never claims the wiring (%s): %s" % (base, h))
    h = adv._unit_gate_handoff(root, {}, rows, unit_issued, {"items": [spel], "measure": {"known": True}}, "package",
                               reach=unreached, prev=prev, steps={"steps": [dict(prev, item_ids=["rt:package:spel"])]},
                               changed=[delegate], why=[])
    if not h or "bean_obligations" in h or "NOT verified" in h["reason"]:
        return _fail("a unit that owes no bean records none (%s): %s" % (base, h))

    # (3) UNKNOWN: the gate failed where nothing locates it
    lost = {"id": "rt:package:lost", "gate": "package", "path": "", "cause": "unclassified", "unlocated": True, "set_wide": []}
    why = []
    h = adv._unit_gate_handoff(root, scope_doc, rows, unit_issued, {"items": [lost], "measure": {"known": True}}, "package",
                               reach=unreached, prev=prev, steps={"steps": [prev]}, changed=[delegate], why=why)
    g = adv._gate_scope_guidance(card_issued, {"items": [lost]}, "package", [card_file])
    if h is not None or not g or g["cause"] != "unclassified-gate-failure" or "UNKNOWN" not in g["reason"]:
        return _fail("an unlocated failure stays pending with an unknown cause (%s): %s %s" % (base, h, g))
    if not unedited(g["reason"]):
        return _fail("and asks for no edit (%s): %s" % (base, g["reason"]))

    # (4) the only failure named is INSIDE the write set: that one IS the
    # candidate's to repair, and only it is named
    inside = dict(spel, id="rt:package:inside", path=card_file, cause="query-invalid")
    g = adv._gate_scope_guidance(card_issued, {"items": [inside]}, "package", [card_file])
    if not g or g["cause"] or card_file not in g["reason"] or "repair it in this candidate" not in g["reason"]:
        return _fail("a failure inside the write set is the candidate's own remaining work (%s): %s" % (base, g))
    if adv._gate_scope_guidance(card_issued, {"items": [spel]}, "package", [card_file]) is not None:
        return _fail("the issued obligation still reported is not a NEW failure to guide on")
    if adv._gate_scope_guidance(card_issued, {"items": [amb]}, "", [card_file]) is not None:
        return _fail("only a package or boot card is guided this way")
    shutil.rmtree(root, ignore_errors=True)
    return 0


def _cdi_wiring_acceptance_case(base: str = "org.acme.inventory") -> int:
    """V16-4 acceptance rule: compilation cannot establish bean correctness.
    A candidate that changes CDI wiring -- here, a delegate gaining
    @Typed(ItemRepositoryImpl.class), and a bean added -- and whose package gate
    did not pass on THIS candidate is accepted only as unverified wiring with
    package and boot owed. Packaging that passed on this candidate proves it,
    packaging of another tree does not, and a change that touches no wiring
    records nothing. Real git, real compiler models of both trees."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("advance_wiring", ADVANCE)
    adv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adv)
    from planner.paths import VERIFY_PACKAGE

    src = "src/main/java/%s/" % base.replace(".", "/")
    impl = src + "repository/ItemRepositoryImpl.java"
    extra = src + "service/Audit.java"
    stubs = {
        "src/main/java/jakarta/enterprise/context/ApplicationScoped.java":
            "package jakarta.enterprise.context;\npublic @interface ApplicationScoped { }\n",
        "src/main/java/jakarta/enterprise/inject/Typed.java":
            "package jakarta.enterprise.inject;\npublic @interface Typed { Class<?>[] value() default {}; }\n",
        src + "repository/ItemRepository.java":
            "package %s.repository;\npublic interface ItemRepository { int count(); }\n" % base,
    }
    body = ("package %s.repository;\n%s@jakarta.enterprise.context.ApplicationScoped\n%spublic class ItemRepositoryImpl "
            "implements ItemRepository {\n    public int count() { return %d; }\n}\n")
    root = Path(tempfile.mkdtemp())
    (root / ".hermes").mkdir()
    (root / ".hermes" / "pins.json").write_text('{"pins":{"quarkus_platform":{"java_release":21}}}', encoding="utf-8")
    for rel, text in {**stubs, impl: body % (base, "", "", 0)}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "accepted")
    accepted = _git(root, "rev-parse", "HEAD").strip()

    # a body change is not wiring
    (root / impl).write_text(body % (base, "", "", 1), encoding="utf-8")
    if adv._cdi_wiring_record(root, accepted, [impl], "cand-0"):
        return _fail("a change that touches no CDI wiring records nothing (%s)" % base)
    # the delegate restricted, a bean added: wiring changed
    (root / impl).write_text(body % (base, "", "@jakarta.enterprise.inject.Typed(ItemRepositoryImpl.class)\n", 1), encoding="utf-8")
    (root / extra).parent.mkdir(parents=True, exist_ok=True)
    (root / extra).write_text("package %s.service;\n@jakarta.enterprise.context.ApplicationScoped\npublic class Audit { }\n" % base,
                              encoding="utf-8")
    rec = adv._cdi_wiring_record(root, accepted, [impl, extra], "cand-1")
    kinds = {r["type"].rsplit(".", 1)[-1]: r["change"] for r in rec.get("changed") or []}
    if kinds != {"ItemRepositoryImpl": "changed", "Audit": "added"} or rec.get("verified") is not False:
        return _fail("a wiring change with no packaging is recorded unverified (%s): %s" % (base, rec))
    if rec.get("debt") != {"package": "owed", "boot": "owed"} or "did not run" not in rec.get("packaging", ""):
        return _fail("with package and boot owed, and why (%s): %s" % (base, rec))
    typed_after = next(r for r in rec["changed"] if r["type"].endswith("ItemRepositoryImpl"))["after"]
    if not any("jakarta.enterprise.inject.Typed(value=%s.repository.ItemRepositoryImpl)" % base in a for a in typed_after):
        return _fail("the record names the restriction the compiler resolved (%s): %s" % (base, typed_after))
    # packaging of ANOTHER tree proves nothing about this one
    (root / VERIFY_PACKAGE).parent.mkdir(parents=True, exist_ok=True)
    write_canonical(root / VERIFY_PACKAGE, {"ran": True, "rc": 0, "candidate_sha256": "other", "profile": "prod"})
    if adv._cdi_wiring_record(root, accepted, [impl, extra], "cand-1").get("verified") is not False:
        return _fail("a package receipt of another candidate does not verify this wiring (%s)" % base)
    write_canonical(root / VERIFY_PACKAGE, {"ran": True, "rc": 1, "candidate_sha256": "cand-1", "profile": "prod",
                                            "failed_goal": "quarkus-maven-plugin:build"})
    failed = adv._cdi_wiring_record(root, accepted, [impl, extra], "cand-1")
    if failed.get("verified") is not False or "packaging failed on this candidate" not in failed.get("packaging", ""):
        return _fail("a failed package on this candidate verifies nothing (%s): %s" % (base, failed))
    # packaging under the decided profile PASSED on this candidate: proven
    write_canonical(root / VERIFY_PACKAGE, {"ran": True, "rc": 0, "candidate_sha256": "cand-1", "profile": "prod"})
    if adv._cdi_wiring_record(root, accepted, [impl, extra], "cand-1"):
        return _fail("packaging that passed on this candidate leaves no wiring debt (%s)" % base)
    shutil.rmtree(root, ignore_errors=True)
    return 0


def _stop_request_case() -> int:
    """V16-3: the stop request belongs to the dispatcher-spawned worker of THIS
    card. No variable (an older runtime, a manual or Operator run) or another
    card's id: none, and kanban_block stays the terminator."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("advance_stop", ADVANCE)
    adv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adv)
    saved = {k: os.environ.get(k) for k in ("HERMES_KANBAN_STOP_REQUEST", "HERMES_KANBAN_TASK")}
    try:
        for env, card, want in (({}, "t_a", None),
                                ({"HERMES_KANBAN_STOP_REQUEST": "/b/stop-requests/t_a.run2.json"}, "t_a", None),
                                ({"HERMES_KANBAN_STOP_REQUEST": "/b/stop-requests/t_a.run2.json", "HERMES_KANBAN_TASK": "t_b"}, "t_a", None),
                                ({"HERMES_KANBAN_STOP_REQUEST": "/b/stop-requests/t_a.run2.json", "HERMES_KANBAN_TASK": "t_a"}, "",
                                 None),
                                ({"HERMES_KANBAN_STOP_REQUEST": "/b/stop-requests/t_a.run2.json", "HERMES_KANBAN_TASK": "t_a"}, "t_a",
                                 Path("/b/stop-requests/t_a.run2.json"))):
            for k in saved:
                os.environ.pop(k, None)
            os.environ.update(env)
            if adv._stop_request_path(card) != want:
                return _fail("the stop request is raised only for this card's own run: %s %s -> %s" % (env, card, adv._stop_request_path(card)))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return 0


def main() -> int:
    if _checked_veto_case() or _checked_family_advance_case() or _introduced_attribution_case() or _disposition_case() or _set_wide_blocker_case() or _harness_owned_root_case() or _parity_baseline_refresh_case() or _restore_runner_records_case() or _parity_card_case() or _enabled_mode_acceptance_case() or _mixed_mode_card_refusal_case():
        return 1
    if _scratch_in_tree_case() or _scratch_in_tree_case("com.example.store"):
        return 1
    if _known_before_unknown_case() or _known_before_unknown_case("com.example.store") or _missing_baseline_case() or _continuation_case():
        return 1
    if _adapter_owned_retirement_advance_case() or _adapter_owned_retirement_advance_case("com.example.store.web"):
        return 1
    if _scope_aware_pending_case() or _scope_aware_pending_case("com.example.depot"):
        return 1
    if _cdi_wiring_acceptance_case() or _cdi_wiring_acceptance_case("com.example.depot"):
        return 1
    if _unit_checkpoint_case() or _unit_gate_handoff_case() or _unit_gate_handoff_case("com.example.store.web"):
        return 1
    if _si1_case():
        return 1
    if _pending_classify_case():
        return 1
    if _stop_request_case():
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
        # V16-3 (runtime 0011): the dispatcher-spawned worker of THIS card is
        # given the run's stop-request path; the pending verdict raises it
        stop = t / "board" / "stop-requests" / "t_pkg3.run1.json"
        p = _advance(root, cl2["id"], "t_pkg3", {"HERMES_KANBAN_STOP_REQUEST": str(stop), "HERMES_KANBAN_TASK": "t_pkg3"})
        # a failing gate cannot discharge an obligation: the repair is RETAINED,
        # not accepted, and no attempt is spent
        blob = p.stdout + p.stderr
        req = json.loads(stop.read_text(encoding="utf-8")) if stop.is_file() else {}
        pend = [r for r in (load_json(root / LOOP_STEPS).get("pending") or []) if r.get("cluster") == cl2["id"]]
        if (req.get("kind") != "needs_input" or req.get("task") != "t_pkg3" or not pend
                or not str(req.get("reason") or "").startswith("VERIFICATION_PENDING %s cause=outside-scope-prerequisite card=t_pkg3: " % cl2["id"])
                or "candidate retained (sha256 %s) under verification/loop/pending-files/%s" % (pend[-1]["candidate_sha256"][:16], cl2["id"].replace(":", "_")) not in req["reason"]
                or not req["reason"].endswith("after the prerequisite: restore-pending.py, run-verify.sh --mode acceptance, advance.py")):
            return _fail("a pending verdict raises the run's stop request once the pending row is persisted: %s %s" % (req, blob[-400:]))
        if "The runtime blocks this card" not in blob or "Terminator: kanban_block" in blob:
            return _fail("with the stop request raised the worker is not told to block again: %s" % blob[-400:])
        if [x.name for x in stop.parent.iterdir()] != [stop.name]:
            return _fail("the request is written atomically, no temporary file left: %s" % list(stop.parent.iterdir()))
        if p.returncode == 0 or "VERIFICATION_PENDING" not in blob or "not proof it was repaired" not in blob:
            return _fail("an unproven gate repair must be retained, not accepted: %s" % blob[:400])
        # V16-2 (v16 t_d3f89ded): the gate now fails at `two`, which is outside
        # this card's write set. The pending verdict names that path, the
        # card's scope and the Operator prerequisite -- and never tells the
        # worker to repair it in this candidate.
        if ("GATE_FAILURE_OUTSIDE_SCOPE" not in blob or two not in blob or "write set: %s" % one not in blob
                or "Required Operator prerequisite" not in blob or "operator-step.py" not in blob):
            return _fail("the pending verdict names the outside path, the scope and the Operator prerequisite: %s" % blob[-900:])
        if "in the same candidate" in blob or "repair the members it now names" in blob or "must not edit those files" not in blob:
            return _fail("the pending message never asks for an edit outside the write set: %s" % blob[-900:])
        steps_now = load_json(root / LOOP_STEPS)
        if (steps_now.get("attempts") or {}) != attempts_before:
            return _fail("retaining a candidate must not spend an attempt: %s → %s" % (attempts_before, steps_now.get("attempts")))
        held = [r for r in (steps_now.get("pending") or []) if r.get("cluster") == cl2["id"]]
        if not held or held[-1].get("cause") != "outside-scope-prerequisite":
            return _fail("the retained candidate must be recorded with its cause: %s" % steps_now.get("pending"))
        rec = held[-1].get("outside_scope") or {}
        if [f["path"] for f in rec.get("failures") or []] != [two] or rec.get("scope") != [one] or not rec.get("prerequisite"):
            return _fail("the record carries the outside paths, the scope and the prerequisite: %s" % rec)

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
    print("OK: fix-until-green (checked-exception veto: a falling count does not admit an introduced unhandled exception; family bound to its introducing step: Owner→Pet CONTINUE in the same card without an attempt, a stalled continuation rejects, an exposure outside the family is a typed diagnosis; an introduced attribution diagnostic is rejected, not parked (javac reports every one of them at once; a flow code newly reported stays exposed; one the accepted tree already had is not introduced); a harness-caused deferral is cleared by a metadata-only disposition and the one budget sees it; a set-wide packaging cause reaches the work list as one typed blocker with no card, under permuted reported names; measurement contract: unrun tests / empty reports / failed runner / skipped rescan are unknown; baseline; issued card; diagnostic cannot advance; post-verify edit + unissued cluster refused with baseline intact; out-of-scope test edit rejected + reverted + reports discarded; accept commits; staged no-progress reverted from index; line shift is not a new obligation; unresolvable candidate is VERIFICATION_PENDING (no attempt); known no-progress defers; Operator rewind restores tree+budget in a new epoch; green → packaging → startup → M4 (unknown gates never mint; an environment blocker is not a card; a gate repair is accepted phase-aware); unresolved test = typed blocker; tampered list refused; PARITY CARD (v9 t_77cae2b2): the obligation carries gate=parity onto the issued card, the brief names its scenarios and what discharges them, a comparison that did not run retains the candidate without an attempt, one that still reports the obligation reverts it, a receipt composed for another card is not this card's measurement, a receipt that carries NO binding after a comparison bound to this card is the one a refusing composer left (VERIFICATION_PENDING, no attempt, never ACCEPTED), and the repair is ACCEPTED on the re-composed candidate-bound receipt with the tuple unchanged at [0,0,0], the receipt snapshotted with the accepted reports); SCRATCH IN THE TREE (v9 t_46556d5e): untracked files outside this migration's product that appear after the verification (javap's extracted .class files at the root) are a typed refusal naming them -- no attempt, the candidate untouched -- while a product path touched after the verification still REVERTS, and the same candidate is ACCEPTED once the scratch is removed, under a renamed specimen too); UNIT CHECKPOINT: the attribution veto is PARTITIONED for a unit card -- a candidate that invented a replacement the catalogue never wrote down still REVERTS with the symbols named (v9 t_3903f495), while one whose remaining diagnostics name the DOCUMENTED target is ACCEPTED with the compile count unchanged and records each tolerated diagnostic with its boundary and its catalogue row; an unresolved lookalike (UriBuilder with nothing importing it) is not the catalogued target either, and the accepted case is the one whose file IMPORTS it; every tolerated diagnostic is still an obligation on the rebuilt work list; the compiler naming another member of the same unit CONTINUES the card without spending an attempt, one naming a file the unit does not seal is a typed diagnosis, and a sealed member answered by deleting it violates however far the measure fell; a unit on the package gate whose issued obligation is gone, whose members all assess clean and whose gate now stops ONLY on located obligations it does not reach is handed off at its checkpoint (proof owed by the closing card), and any missing condition keeps it pending)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
