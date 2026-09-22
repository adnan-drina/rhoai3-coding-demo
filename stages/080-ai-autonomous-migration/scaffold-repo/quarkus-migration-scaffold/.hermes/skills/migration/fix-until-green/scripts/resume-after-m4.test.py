#!/usr/bin/env python3
"""resume-after-m4 selftest: a REFUSE verdict is consumed, not the end of the run.

The measured case is v9's first M4 verdict: REFUSE over a parity receipt that
is FAIL, with floors no card discharges (`check-product-tests` and
`assert-surefire-results` are ADR-015's; `check-empty-security` is ADR-014's)
and receipt rows that `planner.worklist.parity_items` turns into mandatory
obligations. The loop must continue on the obligations and record the
decisions; doing one without the other is either a stalled run or a hidden
floor.

Two readings of the same evidence are covered, because the harness produced
both: a refused read-back as an INCONCLUSIVE row (the comparison could not be
made) and, on the receipt measured on destination v9, the same refusal typed
FAIL. Either way it is ADR-014's and never a card. And the floors the verdict
lists never decide what is repairable: v9's verdict did not name the parity
floor at all while its receipt carried thirteen FAIL rows.

Cases:
  (a) two parity FAILs + two decision floors + a 403 entry point → one mint
      argv under an idempotency key no card on the record already holds, and
      release-blockers.json carrying an ADR-015 floor row and an ADR-014 entry
      point row;
  (b) decision floors only → exit 2, nothing minted, the close card still issued;
  (c) a verdict for another card → refused, nothing touched;
  (c2) a verdict bound to another admission receipt, or to a parity receipt
      that is not the one on disk → refused by name, nothing touched;
  (d) a second run after (a) → refused, already resumed;
  (e) the same fixture under a renamed specimen → the same decisions (the
      classification reads floors and verdicts, never a specimen's names);
  (i) the v9 shape measured on destination v9: a verdict whose failed floors
      are `check-empty-security` and `check-product-tests` and do NOT include
      `compose-parity-receipt`, over a receipt that is FAIL with one CORS
      preflight and twelve refused (403) reads. The obligations come from the
      receipt, so the CORS repair is minted; the refused reads are ADR-014's
      Operator step and are withheld from the mint; and the same receipt
      without the CORS row resumes nothing (exit 2). Renamed specimen: (e).
  (j) v9 t_7740ad21: a CLEAN ACCEPTANCE -- PROVISIONAL_ACCEPT, bound, no
      failed floor, ship false, nothing a card repairs -- CLOSES the run
      instead of refusing: the close row is on the record, issued.json is
      cleared, and a release-blockers.json left by a SUPERSEDED REFUSE is
      rewritten from this verdict, with what is still outstanding named. A
      second close-out refuses; a clean verdict over a dirty tree refuses.
  (f) the whole v9 sequence, in the order it happened: a parity card accepted
      under a SCOPED comparison snapshotted that receipt as the loop's parity
      baseline, the M4 road then composed the FULL receipt, the resume minted
      what it owed, and the first candidate was REVERTED -- whereupon the
      reject path restored the older scoped snapshot and the obligation the
      loop was working on vanished. The close is what makes the comparison it
      closed on the accepted baseline. Renamed specimen: (f2).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "resume-after-m4.py"
ADVANCE = HERE / "advance.py"
GOLDEN = HERE.parents[4]

sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
sys.path.insert(0, str(HERE))

from planner import pipeline, specimens  # noqa: E402
from planner.canonical import load_json, sha256_file, write_canonical  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, LOOP_ISSUED, LOOP_STEPS, WORKLIST  # noqa: E402
from planner.worklist import APP_PROPERTIES, build_worklist, parity_items  # noqa: E402
from planner.paths import STRUCTURE  # noqa: E402
import response_adapters as ra  # noqa: E402

# ADR-019: a CORS obligation is owed the harness adapter; its card's locus is
# the adapter's contract path and its write set adds the configuration
CORS_LOCUS = ra.adapter_path(ra.CORS)

CLOSE_CARD = "t_m4close"
BLOCKERS = Path("verification") / "loop" / "release-blockers.json"
DECISION_FLOORS = ["assert-surefire-results", "check-product-tests"]
# what v9's runner-driven road actually composed: two failed floors, neither of
# them the parity floor, over a parity receipt that was FAIL with thirteen FAIL
# rows. The security floor is ADR-014's, the product-test floor ADR-015's.
V9_FLOORS = ["check-empty-security", "check-product-tests"]
V9_REFUSED_READS = 12
# a contract the admission receipt seals, and the kind of file a harness
# generation rewrites between an M4 verdict and the resume that reads it
CONTRACT = Path(".hermes") / "planning" / "schemas" / "decisions.schema.json"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _slug(ep: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", ep).strip("-").lower()


def _at_m4(tmp: Path, *, base: str = "org.acme.clinic") -> tuple[Path, list]:
    """A destination whose work list is empty, both runtime gates pass, and the
    M4 close card is issued and minted (task_id recorded, as K4 records it)."""
    spec = specimens.specimen("http", base=base)
    root = specimens.build_dest(tmp / "dest", spec, decisions=specimens.admitted_decisions(max_attempts=3))
    # the source declares a CORS policy (ADR-019 renders the adapter's rows from it)
    structure = load_json(root / STRUCTURE)
    for t in structure["types"]:
        if any(str(a.get("fqn") or "").endswith("RestController") for a in t.get("annotations") or []):
            t["annotations"].append({"fqn": "org.springframework.web.bind.annotation.CrossOrigin",
                                     "values": {"exposedHeaders": ["errors"]}})
    write_canonical(root / STRUCTURE, structure)
    specimens.prepare_loop(root)
    specimens.runtime(root, package_rc=0, boot_ready=True)
    specimens.verify(root, errors=[], failures=[], findings={})
    pipeline.admit(root)
    specimens.issue(root)                       # K4 converts → the close card is issued
    issued = load_json(root / LOOP_ISSUED)
    issued["task_id"] = CLOSE_CARD              # what k4_mint records after the real create
    write_canonical(root / LOOP_ISSUED, issued)
    bundle = load_json(root / "evidence" / "planning" / "evidence-bundle.json")
    return root, [str(e["id"]) for e in bundle["entry_points"]]


def _parity(root: Path, eps: list, *, fails: bool, unauthorized: bool) -> None:
    """The parity phase's own output: per-entry-point verdicts plus the receipt
    compose-parity-receipt.py writes, bound to the admission receipt on disk."""
    digest = load_json(root / "evidence" / "planning" / "admission-receipt.json")["receipt_digest"]
    pdir = root / "verification" / "parity"
    pdir.mkdir(parents=True, exist_ok=True)
    rows = []
    if fails:
        # the two v9 mismatches, in their two shapes: a response diff that
        # belongs at the controller, and a CORS preflight header that belongs
        # in application.properties
        for ep, reason in ((eps[0], "status 302 vs 303; body redirect vs redirect"),
                           (eps[1], "header Access-Control-Allow-Origin  vs *")):
            write_canonical(pdir / (_slug(ep) + ".json"), {
                "schema": "rhoai3.parity/v1", "entry_point": ep, "verdict": "FAIL",
                "reason": reason, "receipt_sha256": digest})
            rows.append({"entry_point": ep, "verdict": "FAIL", "reason": reason, "scenarios": []})
    if unauthorized:
        rows.append({"entry_point": eps[2], "verdict": "INCONCLUSIVE",
                     "reason": "status 403 vs 200", "scenarios": []})
    rows.append({"entry_point": eps[3], "verdict": "PASS", "reason": "1 required scenario(s)", "scenarios": []})
    write_canonical(pdir / "receipt.json", {
        "schema": "rhoai3.parity-receipt/v1", "receipt_sha256": digest,
        "producer": "compose-parity-receipt.py", "corpus_sha256": "c" * 64, "corpus_error": "",
        "entry_points": rows, "total": len(rows),
        "not_passed": sum(1 for r in rows if r["verdict"] != "PASS"),
        "cors": {"source_policies": [], "gaps": []},
        "qualification": {"present": True, "derived_corpus": False, "gap": "", "not_passed": [], "stale": []},
        "coverage_gaps": [], "verdict": "FAIL" if fails else "INCONCLUSIVE"})


def _parity_v9(root: Path, eps: list, *, cors: bool = True) -> list:
    """The receipt destination v9 composed: FAIL, with one CORS preflight a card
    repairs and twelve reads the destination REFUSED (403) that no card may.

    Both kinds are typed FAIL here, which is the change this fixture exists
    for: the refused reads used to be INCONCLUSIVE, and a resume that looks for
    401/403 only under that verdict stops seeing them.

    v9's receipt carried thirteen rows because its bundle carried thirteen
    entry points; this bundle carries four. So three of the refused reads are
    entry points this tree has a file for -- the ones whose obligation a mint
    could actually pick up, and therefore the ones withholding has to cover --
    and the rest are refused reads on entry points the bundle names no path
    for, recorded as ADR-014 exactly the same way. Returns the refused entry
    points, in receipt order."""
    digest = load_json(root / "evidence" / "planning" / "admission-receipt.json")["receipt_digest"]
    pdir = root / "verification" / "parity"
    pdir.mkdir(parents=True, exist_ok=True)
    rows = []
    if cors:
        # the preflight: a CORS permission the destination does not grant. It
        # lands in application.properties (kind `config`), never at a controller
        reason = "header Access-Control-Allow-Headers None vs content-type; header Access-Control-Allow-Methods None vs POST"
        write_canonical(pdir / (_slug(eps[1]) + ".json"), {
            "schema": "rhoai3.parity/v1", "entry_point": eps[1], "verdict": "FAIL",
            "reason": reason, "receipt_sha256": digest})
        # the receipt quotes each scenario's diffs under its id; the verdict
        # file beside it carries the diffs alone (compose-parity-receipt.py)
        rows.append({"entry_point": eps[1], "verdict": "FAIL", "reason": "sc:preflight: " + reason, "scenarios": []})
    refused = [e for e in eps if e != eps[1]]
    denied = "status 403 vs 200; body e3b0c44298fc1c14 vs 5f2c1d3ab77e0d41"
    for ep in refused:
        write_canonical(pdir / (_slug(ep) + ".json"), {
            "schema": "rhoai3.parity/v1", "entry_point": ep, "verdict": "FAIL",
            "reason": denied, "receipt_sha256": digest})
        rows.append({"entry_point": ep, "verdict": "FAIL", "reason": "sc:read: " + denied, "scenarios": []})
    for n in range(V9_REFUSED_READS - len(refused)):
        ep = eps[0].replace("#", "#refused%d_" % n, 1)   # this specimen's own names, another operation
        refused.append(ep)
        rows.append({"entry_point": ep, "verdict": "FAIL", "reason": "sc:read: " + denied, "scenarios": []})
    write_canonical(pdir / "receipt.json", {
        "schema": "rhoai3.parity-receipt/v1", "receipt_sha256": digest,
        "producer": "compose-parity-receipt.py", "corpus_sha256": "c" * 64, "corpus_error": "",
        "entry_points": rows, "total": len(rows),
        "not_passed": sum(1 for r in rows if r["verdict"] != "PASS"),
        "cors": {"source_policies": [], "gaps": []},
        "qualification": {"present": True, "derived_corpus": False, "gap": "", "not_passed": [], "stale": []},
        "coverage_gaps": [], "verdict": "FAIL"})
    return refused


def _verdict(root: Path, floors: list, *, card: str = CLOSE_CARD, receipt: str = "", parity: str = "",
             token: str = "REFUSE", reason: str = "", coverage: dict | None = None) -> None:
    """The composed verdict, bound the way compose-m4-verdict's binder binds it:
    the issued close card, the admission receipt that card was minted under, and
    the digest of the parity receipt this verdict judged. The three are what
    `resume-after-m4.py` binds on; a case that passes another value is asking
    whether the resume notices."""
    issued = load_json(root / LOOP_ISSUED)
    write_canonical(root / "evidence" / "verdicts" / "m4-verdict.json", {
        "schema": "rhoai3.m4-verdict/v1", "gate": "M4_VERDICT", "phase": "M4", "ran": True,
        "card_id": card, "verdict": token, "ship": False, "failed_floors": sorted(floors), "reason": reason,
        "receipt_sha256": receipt or str(issued.get("receipt_sha256") or ""),
        "parity_receipt_sha256": parity or sha256_file(root / "verification" / "parity" / "receipt.json"),
        "floors": [{"name": n, "rc": 1, "idle": False} for n in sorted(floors)]
                  + [{"name": "check-runnable-db-config", "rc": 0, "idle": False}],
        "coverage_account": dict(coverage or {"retired": 0, "remaining_gaps": 0})})
    _record_binding(root)


def _record_binding(root: Path) -> None:
    """What bind-m4-verdict.py records when it binds: the digest of the verdict
    file as bound, a copy, the bindings. The resume refuses a verdict without
    it, and one that no longer digests to it."""
    import importlib.util
    binder = GOLDEN / ".hermes" / "skills" / "gates" / "compose-m4-verdict" / "scripts" / "bind-m4-verdict.py"
    spec = importlib.util.spec_from_file_location("bind_m4_verdict", binder)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    vp = root / "evidence" / "verdicts" / "m4-verdict.json"
    mod.write_binding_record(root, vp, load_json(vp))


def _run(root: Path, *args: str) -> tuple[int, str, str]:
    p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--operator", "operator:o", *args],
                       text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def _known_keys(root: Path) -> set:
    """Every idempotency key the loop record and the issued card already hold."""
    steps = load_json(root / LOOP_STEPS) if (root / LOOP_STEPS).is_file() else {}
    keys = {str(s.get("idempotency_key") or "") for s in (steps.get("steps") or [])}
    keys |= {str(r.get("idempotency_key") or "") for r in (steps.get("rejected") or [])}
    if (root / LOOP_ISSUED).is_file():
        keys.add(str(load_json(root / LOOP_ISSUED).get("idempotency_key") or ""))
    return {k for k in keys if k}


def case_both() -> int:
    """(a) parity obligations AND decision floors: the loop continues on what it
    can repair, the decisions are recorded, and (d) a second run refuses."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-both-") as td:
        root, eps = _at_m4(Path(td))
        _parity(root, eps, fails=True, unauthorized=True)
        _verdict(root, DECISION_FLOORS + ["compose-parity-receipt"])
        before = _known_keys(root)
        rc, out, err = _run(root)
        blob = out + err
        if rc != 0:
            return _fail("a verdict with repairable parity obligations must resume: rc=%d %s" % (rc, blob[-800:]))

        # one mint, under a key no card on the record already holds
        if out.count("MINT (dry-run)") != 1:
            return _fail("exactly one mint argv must be printed: %s" % out[-600:])
        m = re.search(r"MINT \(dry-run\) card=(\S+) key=(\S+)", out)
        if not m:
            return _fail("the mint line must name the card and its key: %s" % out[-400:])
        card, key = m.group(1), m.group(2)
        if key in before:
            return _fail("the minted key %s is one the record already holds (%s): a resumed card must be a new card" % (key, sorted(before)))
        if not key.startswith("k4:%s:" % card) or card == "M4_VERIFY":
            return _fail("the resumed card must be an M3 card under a receipt-bound key: %s / %s" % (card, key))
        if "--body" not in out or "**Do**" not in out:
            return _fail("the dry run must print the argv and the card body: %s" % out[-600:])

        # the work list the card comes from is the rebuilt one: the parity
        # verdicts are mandatory obligations now
        wl = load_json(root / WORKLIST)
        if wl["measure"]["parity_mismatches"] != 2:
            return _fail("both parity FAILs must be obligations: %s" % wl["measure"])
        if str(wl.get("head") or "") != card:
            return _fail("the minted card must be the rebuilt work list's head: %s vs %s" % (card, wl.get("head")))

        # the close is on the record, where the live-board comparator reads it
        steps = load_json(root / LOOP_STEPS)
        closes = [r for r in steps.get("rejected") or [] if r.get("kind") == "close"]
        if len(closes) != 1 or closes[0]["card"] != CLOSE_CARD or not closes[0].get("resumed"):
            return _fail("the close card must be recorded once, resumed: %s" % closes)
        if closes[0]["failed_floors"] != sorted(DECISION_FLOORS + ["compose-parity-receipt"]):
            return _fail("the close row must carry the failed floors: %s" % closes[0])
        if (steps.get("attempts") or {}).get("M4_VERIFY"):
            return _fail("closing M4 must not spend an attempt: %s" % steps.get("attempts"))

        # and the decisions are recorded, not hidden
        doc = load_json(root / BLOCKERS)
        if doc["schema"] != "rhoai3.release-blockers/v1" or doc["verdict_card"] != CLOSE_CARD:
            return _fail("the blockers file must name its schema and the verdict card: %s" % doc)
        floors = {r["floor"]: r for r in doc["floors"]}
        if sorted(floors) != sorted(DECISION_FLOORS):
            return _fail("only the decision floors belong in the blockers file: %s" % sorted(floors))
        if any(r["adr"] != "ADR-015" for r in floors.values()):
            return _fail("both ADR-015 floors must name their ADR: %s" % doc["floors"])
        if [r["entry_point"] for r in doc["entry_points"]] != [eps[2]] or doc["entry_points"][0]["adr"] != "ADR-014":
            return _fail("a 403 read-back is the ADR-014 obligation: %s" % doc["entry_points"])
        if doc["owners"] != ["ADR-014", "ADR-015"]:
            return _fail("the blockers file must name every owning decision: %s" % doc["owners"])
        if "BLOCKED: LOOP_RELEASE_FLOOR check-product-tests owned by ADR-015" not in err:
            return _fail("each blocked floor must be named with its ADR on stderr: %s" % err[-600:])
        if "RESUMED" not in out:
            return _fail("the resumed class must be printed too: %s" % out[-400:])

        # (d) a second run is refused: the close is on the record
        rc2, out2, err2 = _run(root)
        if rc2 != 1 or "already resumed for verdict %s" % CLOSE_CARD not in err2:
            return _fail("a second resume must refuse: rc=%d %s" % (rc2, (out2 + err2)[-400:]))
        return 0


def case_decisions_only() -> int:
    """(b) nothing a card can repair: exit 2, nothing minted, the card stays issued."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-blocked-") as td:
        root, eps = _at_m4(Path(td))
        _parity(root, eps, fails=False, unauthorized=False)
        _verdict(root, DECISION_FLOORS)
        issued_before = (root / LOOP_ISSUED).read_bytes()
        rc, out, err = _run(root)
        if rc != 2:
            return _fail("decision floors alone must exit 2 (blocked), not %d: %s" % (rc, (out + err)[-600:]))
        if "MINT" in out:
            return _fail("a blocked resume must mint nothing: %s" % out[-400:])
        if (root / LOOP_ISSUED).read_bytes() != issued_before:
            return _fail("the close card must stay issued when nothing resumes")
        steps = load_json(root / LOOP_STEPS)
        if [r for r in steps.get("rejected") or [] if r.get("kind") == "close"]:
            return _fail("a blocked resume must not close the card on the record (the Operator can still fix and resume)")
        doc = load_json(root / BLOCKERS)
        if doc["owners"] != ["ADR-015"] or doc["resumed"] is not False:
            return _fail("the blockers file must record the decisions and say nothing resumed: %s" % doc)
        for name in DECISION_FLOORS:
            if "BLOCKED: LOOP_RELEASE_FLOOR %s owned by ADR-015" % name not in err:
                return _fail("%s must be named with its owner: %s" % (name, err[-600:]))
        return 0


def case_wrong_card() -> int:
    """(c) a verdict composed for another card binds to nothing here."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-foreign-") as td:
        root, eps = _at_m4(Path(td))
        _parity(root, eps, fails=True, unauthorized=True)
        _verdict(root, DECISION_FLOORS + ["compose-parity-receipt"], card="t_somebodyelse")
        rc, out, err = _run(root)
        if rc != 1 or "REFUSE: LOOP_RESUME" not in err or "t_somebodyelse" not in err:
            return _fail("a verdict for another card must be refused by name: rc=%d %s" % (rc, (out + err)[-400:]))
        if (root / BLOCKERS).is_file():
            return _fail("a refused resume must write nothing")
        if load_json(root / WORKLIST)["measure"]["parity_mismatches"] is not None:
            return _fail("a refused resume must not rebuild the work list")
        return 0


def case_edited_after_binding() -> int:
    """(c3) v9 t_caf2ad51: a bound verdict revised by hand after binding.

    The composer's output is the verdict. bind-m4-verdict.py records the
    digest of the file it bound; a verdict that no longer digests to it was
    edited afterwards and is not consumed -- the refusal names the fields."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-edited-") as td:
        root, eps = _at_m4(Path(td))
        _parity(root, eps, fails=True, unauthorized=True)
        _verdict(root, DECISION_FLOORS + ["compose-parity-receipt"])
        vp = root / "evidence" / "verdicts" / "m4-verdict.json"
        doc = load_json(vp)
        doc["failed_floors"] = sorted(DECISION_FLOORS)  # the parity floor dropped by hand
        write_canonical(vp, doc)
        rc, out, err = _run(root)
        if rc != 1 or "REFUSE: LOOP_RESUME" not in err or "edited after binding" not in err or "failed_floors" not in err:
            return _fail("a verdict edited after binding must be refused naming the field: rc=%d %s" % (rc, (out + err)[-500:]))
        if (root / BLOCKERS).is_file():
            return _fail("a refused resume must write nothing")
        # and with no record at all: bound by hand is not bound
        _verdict(root, DECISION_FLOORS + ["compose-parity-receipt"])
        (root / "evidence" / "verdicts" / "m4-verdict.bound.json").unlink()
        rc, out, err = _run(root)
        if rc != 1 or "no binding record" not in err:
            return _fail("a verdict with no binding record must be refused: rc=%d %s" % (rc, (out + err)[-500:]))
        return 0


def case_wrong_receipt_bindings() -> int:
    """(c2) the card binds, the evidence does not.

    `card_id` alone says only WHO answered. A verdict composed under another
    admission receipt was measured on another tree, and one whose
    `parity_receipt_sha256` is not the receipt on disk judged parity evidence
    this tree no longer holds -- the parity phase ran again after it. Both are
    refused by name, and both leave the tree untouched."""
    for label, kwargs, needle in (
        ("another admission receipt", {"receipt": "e" * 64}, "was composed under admission receipt"),
        ("a parity receipt that moved", {"parity": "f" * 64}, "judged parity receipt"),
        ("no admission receipt at all", {"receipt": " "}, "names no receipt_sha256"),
        ("no parity receipt digest", {"parity": " "}, "names no parity_receipt_sha256"),
    ):
        with tempfile.TemporaryDirectory(prefix="resume-m4-binding-") as td:
            root, eps = _at_m4(Path(td))
            _parity(root, eps, fails=True, unauthorized=True)
            _verdict(root, DECISION_FLOORS + ["compose-parity-receipt"], **kwargs)
            rc, out, err = _run(root)
            if rc != 1 or "REFUSE: LOOP_RESUME" not in err or needle not in err:
                return _fail("a verdict bound to %s must be refused by name: rc=%d %s" % (label, rc, (out + err)[-500:]))
            if (root / BLOCKERS).is_file():
                return _fail("a refused resume must write nothing (%s)" % label)
            if load_json(root / WORKLIST)["measure"]["parity_mismatches"] is not None:
                return _fail("a refused resume must not rebuild the work list (%s)" % label)
    return 0


def case_renamed_specimen() -> int:
    """(e) the same case under another specimen: the same decisions.

    The classification reads floor names, verdict tokens and diff shapes. If it
    read a specimen's packages or files, this fixture would decide differently.
    """
    with tempfile.TemporaryDirectory(prefix="resume-m4-renamed-") as td:
        root, eps = _at_m4(Path(td), base="com.example.store")
        _parity(root, eps, fails=True, unauthorized=True)
        _verdict(root, DECISION_FLOORS + ["compose-parity-receipt"])
        rc, out, err = _run(root)
        if rc != 0:
            return _fail("the renamed specimen must resume the same way: rc=%d %s" % (rc, (out + err)[-800:]))
        doc = load_json(root / BLOCKERS)
        if doc["owners"] != ["ADR-014", "ADR-015"] or sorted(r["floor"] for r in doc["floors"]) != sorted(DECISION_FLOORS):
            return _fail("the same floors must be owned by the same decisions under another specimen: %s" % doc)
        if [r["entry_point"] for r in doc["entry_points"]] != [eps[2]]:
            return _fail("the ADR-014 row must name this specimen's own entry point: %s" % doc["entry_points"])
        wl = load_json(root / WORKLIST)
        if wl["measure"]["parity_mismatches"] != 2 or "com/example/store" not in json.dumps(wl["clusters"]):
            return _fail("the obligations must land on this specimen's own files: %s" % wl["measure"])
        return 0


def _v9_blockers(doc: dict, refused: list) -> str:
    """What the blockers file must say about a v9-shaped receipt, whatever the
    specimen is called: every refused read is an ADR-014 entry point, the
    security floor is ADR-014's and the product-test floor ADR-015's, and each
    floor is recorded once however many rows explain it."""
    got = [r["entry_point"] for r in doc["entry_points"]]
    if sorted(got) != sorted(refused) or len(got) != V9_REFUSED_READS:
        return "every refused read must be recorded as an entry point (%d): %s" % (V9_REFUSED_READS, got)
    if any(r["adr"] != "ADR-014" or r["verdict"] != "FAIL" for r in doc["entry_points"]):
        return "a FAIL row the destination refused is ADR-014's, not a card's: %s" % doc["entry_points"][:2]
    floors = {r["floor"]: r for r in doc["floors"]}
    if sorted(floors) != sorted(V9_FLOORS):
        return "the verdict's own failed floors are the floor rows: %s" % sorted(floors)
    if floors["check-empty-security"]["adr"] != "ADR-014" or floors["check-product-tests"]["adr"] != "ADR-015":
        return "each floor must name the decision that owns it: %s" % doc["floors"]
    if floors["check-empty-security"].get("explained_by") != V9_REFUSED_READS:
        return "the security floor is recorded once, counting the rows that explain it: %s" % floors["check-empty-security"]
    if doc["owners"] != ["ADR-014", "ADR-015"]:
        return "the blockers file must name every owning decision: %s" % doc["owners"]
    return ""


def case_v9_receipt_shape() -> int:
    """(i) the measured v9 shape: the obligations are the RECEIPT's, and a
    request the destination refused is never a card.

    The verdict names `check-empty-security` and `check-product-tests` and does
    not name the parity floor at all, so a resume that reads its floor list for
    repairs finds none -- while the receipt beside it is FAIL with a CORS
    preflight a card repairs and twelve refused reads it must not. Exactly one
    card is minted, and it is the CORS one: the refused reads are withheld to
    ADR-014's Operator step and recorded."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-v9-") as td:
        root, eps = _at_m4(Path(td))
        refused = _parity_v9(root, eps)
        _verdict(root, V9_FLOORS)
        rc, out, err = _run(root)
        blob = out + err
        if rc != 0:
            return _fail("a receipt with a repairable obligation must resume even when no floor names parity: rc=%d %s" % (rc, blob[-900:]))
        if out.count("MINT (dry-run)") != 1:
            return _fail("exactly one card must be minted: %s" % out[-600:])

        # the minted card is the CORS repair: the owed adapter and its configuration (ADR-019)
        wl = load_json(root / WORKLIST)
        head = [c for c in wl["clusters"] if c["id"] == wl["head"]]
        if len(head) != 1 or head[0]["path"] != CORS_LOCUS or APP_PROPERTIES not in head[0]["write_set"]:
            return _fail("the CORS obligation is the only one a card may carry here, and it is application config: %s" % head)
        if wl["measure"]["parity_mismatches"] != 1 + len([e for e in refused if e in eps]):
            return _fail("the work list still counts every parity mismatch it measured: %s" % wl["measure"])

        doc = load_json(root / BLOCKERS)
        why = _v9_blockers(doc, refused)
        if why:
            return _fail(why)
        if len(doc["parity_obligations"]) != 1 or doc["resumed"] is not True:
            return _fail("exactly the CORS obligation resumes: %s" % doc)
        if len(doc["withheld_obligations"]) != len([e for e in refused if e in eps]):
            return _fail("every refused read that HAS a locus in this tree must be withheld by name: %s" % doc["withheld_obligations"])
        if set(doc["withheld_obligations"]) & set(doc["parity_obligations"]):
            return _fail("a withheld obligation must not also be minted: %s" % doc)
        if "BLOCKED: LOOP_RELEASE_FLOOR check-empty-security owned by ADR-014" not in err:
            return _fail("the security floor must be named with ADR-014 on stderr: %s" % err[-800:])
        if "BLOCKED: LOOP_RELEASE_FLOOR check-product-tests owned by ADR-015" not in err:
            return _fail("the product-test floor must be named with ADR-015 on stderr: %s" % err[-800:])
        if "RESUMED" not in out:
            return _fail("the resumed class must be printed too: %s" % out[-400:])
        return 0


def case_v9_without_the_repairable_row() -> int:
    """(i2) the control: the same receipt with the CORS row removed.

    Everything left is a request the destination refused, so nothing a card may
    carry remains and the resume blocks -- the close card stays issued, the
    record stays empty, and the blockers file says the same thing it said
    when a card WAS available."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-v9-blocked-") as td:
        root, eps = _at_m4(Path(td))
        refused = _parity_v9(root, eps, cors=False)
        _verdict(root, V9_FLOORS)
        issued_before = (root / LOOP_ISSUED).read_bytes()
        rc, out, err = _run(root)
        if rc != 2:
            return _fail("a receipt whose every mismatch is ADR-014's must block, not mint: rc=%d %s" % (rc, (out + err)[-900:]))
        if "MINT" in out:
            return _fail("a blocked resume must mint nothing: %s" % out[-400:])
        if (root / LOOP_ISSUED).read_bytes() != issued_before:
            return _fail("the close card must stay issued when nothing resumes")
        if [r for r in load_json(root / LOOP_STEPS).get("rejected") or [] if r.get("kind") == "close"]:
            return _fail("a blocked resume must not close the card on the record")
        doc = load_json(root / BLOCKERS)
        why = _v9_blockers(doc, refused)
        if why:
            return _fail(why)
        if doc["resumed"] is not False or doc["parity_obligations"]:
            return _fail("nothing resumed, and the file must say so: %s" % doc)
        if len(doc["withheld_obligations"]) != len([e for e in refused if e in eps]):
            return _fail("the withheld obligations are still named: %s" % doc["withheld_obligations"])
        return 0


def case_v9_renamed_specimen() -> int:
    """(i3) the v9 shape under another specimen: the same decisions.

    Nothing in the classification may read a specimen's packages or files: it
    reads the receipt's diff shapes and the verdict's floor names."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-v9-renamed-") as td:
        root, eps = _at_m4(Path(td), base="com.example.store")
        refused = _parity_v9(root, eps)
        _verdict(root, V9_FLOORS)
        rc, out, err = _run(root)
        if rc != 0 or out.count("MINT (dry-run)") != 1:
            return _fail("the renamed specimen must decide the same way: rc=%d %s" % (rc, (out + err)[-900:]))
        doc = load_json(root / BLOCKERS)
        why = _v9_blockers(doc, refused)
        if why:
            return _fail(why)
        wl = load_json(root / WORKLIST)
        head = [c for c in wl["clusters"] if c["id"] == wl["head"]]
        if len(head) != 1 or head[0]["path"] != CORS_LOCUS or APP_PROPERTIES not in head[0]["write_set"] or len(doc["parity_obligations"]) != 1:
            return _fail("the same one obligation must be minted under another specimen: %s / %s" % (head, doc["parity_obligations"]))
        return 0


def case_v9_head_is_a_decision() -> int:
    """(i4) the mint takes the work list's HEAD, and nothing chooses it.

    So withholding an obligation from a count is not enough: when the head
    cluster is made of nothing but requests the destination refused, the next
    card WOULD be the security decision, and the resume must block instead --
    even though another entry point's mismatch is repairable and waiting
    behind it. The invariant is asserted against the head this tree actually
    forms, so a reordering in the planner changes the expected branch rather
    than breaking the case."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-v9-head-") as td:
        root, eps = _at_m4(Path(td))
        digest = load_json(root / ADMISSION_RECEIPT)["receipt_digest"]
        pdir = root / "verification" / "parity"
        pdir.mkdir(parents=True, exist_ok=True)
        denied = "status 403 vs 200; body e3b0c44298fc1c14 vs 5f2c1d3ab77e0d41"
        repairable = "status 500 vs 200; body 7d1a vs 5f2c"
        rows = []
        for ep, reason in [(e, denied) for e in eps[:-1]] + [(eps[-1], repairable)]:
            write_canonical(pdir / (_slug(ep) + ".json"), {
                "schema": "rhoai3.parity/v1", "entry_point": ep, "verdict": "FAIL",
                "reason": reason, "receipt_sha256": digest})
            rows.append({"entry_point": ep, "verdict": "FAIL", "reason": "sc:read: " + reason, "scenarios": []})
        write_canonical(pdir / "receipt.json", {
            "schema": "rhoai3.parity-receipt/v1", "receipt_sha256": digest,
            "producer": "compose-parity-receipt.py", "corpus_sha256": "c" * 64, "corpus_error": "",
            "entry_points": rows, "total": len(rows), "not_passed": len(rows),
            "cors": {"source_policies": [], "gaps": []},
            "qualification": {"present": True, "derived_corpus": False, "gap": "", "not_passed": [], "stale": []},
            "coverage_gaps": [], "verdict": "FAIL"})
        _verdict(root, V9_FLOORS)
        preview = build_worklist(root, write=False)      # writes nothing; the head the mint would take
        head = [c for c in preview["clusters"] if c["id"] == preview["head"]]
        if len(head) != 1:
            return _fail("the fixture must form a head cluster: %s" % preview.get("head"))
        bundle = load_json(root / "evidence" / "planning" / "evidence-bundle.json")
        held = {str(i["id"]) for i in parity_items(root, bundle) if str(i.get("entry_point") or "") in set(eps[:-1])}
        if not held or len(held) >= len(parity_items(root, bundle)):
            return _fail("the fixture must refuse some entry points and leave one repairable: %s" % sorted(held))
        head_items = {str(x) for x in head[0]["items"]}
        rc, out, err = _run(root)
        doc = load_json(root / BLOCKERS)
        if head_items <= held:
            if rc != 2 or "MINT" in out:
                return _fail("a head made only of refused requests must block: rc=%d %s" % (rc, (out + err)[-700:]))
            if "the head cluster carries only requests the destination refused" not in err:
                return _fail("the blocked head must say why it is not a card: %s" % err[-700:])
            if not head_items <= set(doc["withheld_obligations"]):
                return _fail("the head's obligations are the withheld ones: %s vs %s" % (sorted(head_items), doc["withheld_obligations"]))
            if doc["resumed"] is not False:
                return _fail("nothing resumed, and the file must say so: %s" % doc)
        else:
            if rc != 0 or out.count("MINT (dry-run)") != 1:
                return _fail("a head a card may carry must still mint: rc=%d %s" % (rc, (out + err)[-700:]))
            if head_items & set(doc["withheld_obligations"]):
                return _fail("the minted head must carry no withheld obligation: %s" % doc["withheld_obligations"])
        return 0


# --- (j) the clean acceptance: the run's success path ------------------------

# what v9's SUPERSEDED REFUSE left on disk, and the run report kept reading as
# current after the next verdict cleared it
SUPERSEDED_FLOOR = "assert-mta-rescan"


def _stale_blockers(root: Path) -> None:
    """release-blockers.json as a previous, now superseded, REFUSE verdict left
    it: a release floor the CURRENT verdict measured rc 0."""
    write_canonical(root / BLOCKERS, {
        "schema": "rhoai3.release-blockers/v1", "at": "2026-09-21T00:00:00Z", "operator": "operator:earlier",
        "verdict_card": "t_supersededcard", "verdict": "REFUSE", "verdict_file": "evidence/verdicts/m4-verdict.json",
        "failed_floors": [SUPERSEDED_FLOOR], "receipt_sha256": "0" * 64, "corpus_sha256": "0" * 64,
        "floors": [{"floor": SUPERSEDED_FLOOR, "class": "decision", "adr": "", "owner": "Operator",
                    "detail": "release floor %s is not a card" % SUPERSEDED_FLOOR}],
        "entry_points": [], "owners": [], "resumed": False,
        "parity_obligations": [], "withheld_obligations": []})


def _parity_clean(root: Path, eps: list) -> None:
    """The receipt v9's clean M4 composed: no FAIL row anywhere, so no
    obligation a card can carry -- and still not a PASS, because entry points
    nothing compared are INCONCLUSIVE and the coverage account has gaps.

    That combination is exactly what had no terminator: nothing to repair,
    nothing a decision owns, and a run that must not stay open."""
    digest = load_json(root / ADMISSION_RECEIPT)["receipt_digest"]
    pdir = root / "verification" / "parity"
    pdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for ep in eps[:2]:
        write_canonical(pdir / (_slug(ep) + ".json"), {
            "schema": "rhoai3.parity/v1", "entry_point": ep, "verdict": "PASS",
            "reason": "", "receipt_sha256": digest})
        rows.append({"entry_point": ep, "verdict": "PASS", "reason": "compared", "scenarios": [],
                     "coverage_kind": "oracle", "covered_by": {"oracle": True, "scenarios": []}})
    for ep in eps[2:]:
        rows.append({"entry_point": ep, "verdict": "INCONCLUSIVE", "scenarios": [],
                     "reason": "no parity record: no read-oracle replay on disk, and no scenario in this corpus binds this entry point",
                     "coverage_kind": "none", "covered_by": {"oracle": False, "scenarios": []}})
    write_canonical(pdir / "receipt.json", {
        "schema": "rhoai3.parity-receipt/v1", "receipt_sha256": digest,
        "producer": "compose-parity-receipt.py", "corpus_sha256": "c" * 64, "corpus_error": "",
        "entry_points": rows, "total": len(rows),
        "not_passed": sum(1 for r in rows if r["verdict"] != "PASS"),
        "coverage_summary": {"entry_points": len(rows), "by_oracle": 2, "by_scenario": 0,
                             "uncovered": len(rows) - 2},
        "cors": {"source_policies": [], "gaps": []},
        "qualification": {"present": True, "derived_corpus": False, "gap": "", "not_passed": [], "stale": []},
        "coverage_gaps": [], "verdict": "INCONCLUSIVE"})


CLEAN_COVERAGE = {"retired": 41, "remaining_gaps": 41}
CLEAN_REASON = ("the parity receipt is INCONCLUSIVE: 20 of 34 entry points were not compared (a non-idempotent "
                "method or a wildcard path with no captured single-request oracle)")


def case_clean_acceptance_closes() -> int:
    """(j) v9 t_7740ad21: PROVISIONAL_ACCEPT, bound, no failed floor, ship
    false, and nothing a card repairs — the run CLOSES.

    Before H16 this refused ("there is nothing to resume"), and the run was
    left with an issued card the board had already closed and a blockers file
    from a superseded REFUSE that the run report read as current. The close-out
    has to answer both, and to say what is still outstanding: a closed run with
    coverage gaps is not a shipped run."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-clean-") as td:
        root, eps = _at_m4(Path(td))
        _parity_clean(root, eps)
        _stale_blockers(root)
        _verdict(root, [], token="PROVISIONAL_ACCEPT", reason=CLEAN_REASON, coverage=CLEAN_COVERAGE)
        rc, out, err = _run(root)
        blob = out + err
        if rc != 0:
            return _fail("a clean acceptance must close the run, not refuse: rc=%d %s" % (rc, blob[-900:]))
        if "MINT" in out:
            return _fail("a closed run mints nothing: %s" % out[-400:])
        if "CLOSED %s" % CLOSE_CARD not in out:
            return _fail("the terminal line must name the state and the card: %s" % out[-600:])

        # the issued card is cleared: the loop no longer believes a card is open
        if (root / LOOP_ISSUED).is_file():
            return _fail("the close-out must clear the issued card; %s is still on disk" % LOOP_ISSUED)

        # the close is on the record, with the verdict and its bindings
        steps = load_json(root / LOOP_STEPS)
        closes = [r for r in steps.get("rejected") or [] if r.get("kind") == "close"]
        if len(closes) != 1:
            return _fail("the close must be recorded exactly once: %s" % closes)
        row = closes[0]
        if row["card"] != CLOSE_CARD or row["verdict"] != "PROVISIONAL_ACCEPT" or not row.get("closed") or row.get("resumed"):
            return _fail("the close row must say the run was CLOSED on this verdict, not resumed: %s" % row)
        if row["failed_floors"] != [] or row["parity_obligations"] or row["withheld_obligations"]:
            return _fail("a clean close names no failed floor and no obligation: %s" % row)
        if row["receipt_sha256"] != load_json(root / ADMISSION_RECEIPT)["receipt_digest"]:
            return _fail("the close row must bind to the admission receipt that seals this tree: %s" % row)
        if row["parity_receipt_sha256"] != sha256_file(root / "verification" / "parity" / "receipt.json"):
            return _fail("the close row must bind to the parity receipt the verdict judged: %s" % row)
        if (steps.get("attempts") or {}).get("M4_VERIFY"):
            return _fail("closing M4 must not spend an attempt: %s" % steps.get("attempts"))

        # the blockers file is rewritten FROM THIS VERDICT: the superseded
        # floor is gone, and the file says which verdict cleared it and when
        doc = load_json(root / BLOCKERS)
        if doc["verdict_card"] != CLOSE_CARD or doc["verdict"] != "PROVISIONAL_ACCEPT":
            return _fail("the blockers file must be this verdict's: %s" % doc)
        if doc["floors"] or doc["entry_points"] or doc["owners"] or doc["failed_floors"]:
            return _fail("a verdict that names no blocker leaves an EMPTY record, not a superseded one: %s" % doc)
        if SUPERSEDED_FLOOR in json.dumps(doc):
            return _fail("a floor the current verdict cleared must not survive in the record: %s" % doc)
        cleared = doc.get("cleared_by") or {}
        if cleared.get("verdict") != "PROVISIONAL_ACCEPT" or cleared.get("card") != CLOSE_CARD or not cleared.get("at"):
            return _fail("the empty record must name the verdict that cleared it and when: %s" % cleared)
        if doc.get("closed") is not True or doc.get("resumed") is not False:
            return _fail("the record must say the run closed and nothing resumed: %s" % doc)

        # and what is still outstanding stays visible: closed is not shipped
        kinds = {r["kind"] for r in doc.get("outstanding") or []}
        for want in ("parity-receipt", "coverage-account", "verdict-reason", "not-shipped"):
            if want not in kinds:
                return _fail("the close-out must name what remains before ship (%s): %s" % (want, doc.get("outstanding")))
        text = json.dumps(doc["outstanding"])
        if "41" not in text or "INCONCLUSIVE" not in text or "not compared" not in text:
            return _fail("the outstanding items must be read from the verdict's own reason and account: %s" % text)
        if "closed is not shipped" not in out:
            return _fail("the terminal line must distinguish closed from shipped: %s" % out[-600:])

        # the comparison the close was made on is the accepted parity baseline
        snap = root / "verification" / "loop" / "accepted" / "parity" / "receipt.json"
        src = root / "verification" / "loop" / "accepted" / "parity-source.json"
        if not snap.is_file() or not src.is_file() or load_json(src).get("card") != CLOSE_CARD:
            return _fail("the close must snapshot the comparison it closed on: %s" % (load_json(src) if src.is_file() else "absent"))

        # a second close-out refuses: the close is on the record
        rc2, out2, err2 = _run(root)
        if rc2 != 1 or "already closed for verdict %s" % CLOSE_CARD not in err2:
            return _fail("a second close-out must refuse: rc=%d %s" % (rc2, (out2 + err2)[-400:]))
        return 0


def case_clean_acceptance_dirty_tree() -> int:
    """(j2) the control: the same clean verdict over a tree a worker still holds.

    A close-out writes to the tree (the record, the baseline snapshot, the
    blockers file), so every refusal that guarded the resume guards it too. The
    stale blockers file is left exactly as it was: a refused run changes
    nothing, including a record it would otherwise have corrected."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-clean-dirty-") as td:
        root, eps = _at_m4(Path(td))
        _parity_clean(root, eps)
        _stale_blockers(root)
        stale = (root / BLOCKERS).read_bytes()
        _verdict(root, [], token="PROVISIONAL_ACCEPT", reason=CLEAN_REASON, coverage=CLEAN_COVERAGE)
        issued_before = (root / LOOP_ISSUED).read_bytes()
        src = sorted((root / "src").rglob("*.java"))
        if not src:
            return _fail("the fixture must carry a product source to change")
        src[0].write_text(src[0].read_text(encoding="utf-8") + "\n// a worker's edit\n", encoding="utf-8")
        rc, out, err = _run(root)
        if rc != 1 or "the product tree is not clean" not in err:
            return _fail("a clean verdict over a dirty tree must still refuse: rc=%d %s" % (rc, (out + err)[-600:]))
        if (root / BLOCKERS).read_bytes() != stale:
            return _fail("a refused close-out must rewrite nothing, not even a superseded record")
        if (root / LOOP_ISSUED).read_bytes() != issued_before:
            return _fail("a refused close-out must leave the issued card alone")
        if [r for r in load_json(root / LOOP_STEPS).get("rejected") or [] if r.get("kind") == "close"]:
            return _fail("a refused close-out must record no close")

        # and the same clean verdict for ANOTHER card binds to nothing here
        with tempfile.TemporaryDirectory(prefix="resume-m4-clean-foreign-") as td2:
            root2, eps2 = _at_m4(Path(td2))
            _parity_clean(root2, eps2)
            _verdict(root2, [], token="PROVISIONAL_ACCEPT", card="t_somebodyelse", coverage=CLEAN_COVERAGE)
            rc2, out2, err2 = _run(root2)
            if rc2 != 1 or "t_somebodyelse" not in err2:
                return _fail("a clean verdict for another card must be refused by name: rc=%d %s" % (rc2, (out2 + err2)[-400:]))
            if (root2 / BLOCKERS).is_file():
                return _fail("a refused close-out must write nothing")
        return 0


def case_accept_vocabulary_is_the_roads() -> int:
    """(j3) the accepting tokens are READ from the road, never invented here.

    compose-m4-verdict's lint owns the vocabulary (`ACCEPT_TOKENS`) and refuses
    any of them beside a failed floor. If the road adds or renames one, this
    equality fails rather than the close-out silently refusing a verdict the
    road accepts."""
    import importlib.util

    def _load(path: Path, name: str):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    lint = _load(GOLDEN / ".hermes" / "skills" / "gates" / "compose-m4-verdict" / "scripts" / "assert-m4-verdict-schema.py",
                 "assert_m4_verdict_schema")
    resume = _load(SCRIPT, "resume_after_m4")
    if set(resume.ACCEPT_TOKENS) != set(lint.ACCEPT_TOKENS):
        return _fail("the close-out must treat exactly the road's accepting tokens: %s vs %s"
                     % (sorted(resume.ACCEPT_TOKENS), sorted(lint.ACCEPT_TOKENS)))
    if (GOLDEN / resume.M4_VERDICT_LINT).resolve() != (GOLDEN / ".hermes" / "skills" / "gates" / "compose-m4-verdict"
                                                       / "scripts" / "assert-m4-verdict-schema.py").resolve():
        return _fail("the recorded source of the vocabulary must be the lint that owns it: %s" % resume.M4_VERDICT_LINT)
    return 0


def _install_harness_generation(root: Path) -> None:
    """What a harness install does to a sealed contract: the file's bytes move.

    Nothing about the destination's product tree, its evidence or its work list
    changes -- only a file the admission receipt happens to seal."""
    p = root / CONTRACT
    p.write_text(p.read_text(encoding="utf-8").rstrip("\n") + "\n\n", encoding="utf-8")


def case_contract_reseal() -> int:
    """(f) v9: the harness generation installed between the M4 verdict and this
    resume changed a sealed contract, and nothing else moved.

    The verdict is still the verdict of the issued close card on this tree --
    `card_id` binds it to the card, the parity receipt's digest to the seal it
    was measured under. Only the seal moved, so the resume re-takes it, records
    what moved and between which two receipts, and continues."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-reseal-") as td:
        root, eps = _at_m4(Path(td))
        _parity(root, eps, fails=True, unauthorized=True)
        _verdict(root, DECISION_FLOORS + ["compose-parity-receipt"])
        sealed = load_json(root / ADMISSION_RECEIPT)["receipt_digest"]
        _install_harness_generation(root)
        rc, out, err = _run(root)
        if rc != 0:
            return _fail("a changed contract must be re-sealed, not refused: rc=%d %s" % (rc, (out + err)[-900:]))
        if "RESEAL" not in out or CONTRACT.as_posix() not in out:
            return _fail("the re-seal must name the contract that moved: %s" % out[-500:])
        if load_json(root / ADMISSION_RECEIPT)["receipt_digest"] == sealed:
            return _fail("admission must actually be re-sealed, not merely tolerated")
        doc = load_json(root / BLOCKERS)
        got = doc.get("contract_reseal") or {}
        if got.get("changed") != [CONTRACT.as_posix()]:
            return _fail("release-blockers.json must name the contract that moved: %s" % got)
        if got.get("old_receipt") != sealed or not got.get("new_receipt") or got["new_receipt"] == sealed:
            return _fail("it must record both seals: the one the verdict was measured under and the one taken here: %s" % got)
        closes = [r for r in load_json(root / LOOP_STEPS).get("rejected") or [] if r.get("kind") == "close"]
        if len(closes) != 1 or closes[0].get("contract_reseal") != got:
            return _fail("the close row must carry the same record: %s" % closes)
        if closes[0]["receipt_sha256"] != got["new_receipt"]:
            return _fail("the close row must bind to the seal this run took, not the one it superseded: %s" % closes[0]["receipt_sha256"])
        # and the loop actually moved: the parity obligations are cards now
        if out.count("MINT (dry-run)") != 1 or load_json(root / WORKLIST)["measure"]["parity_mismatches"] != 2:
            return _fail("the resume must continue on the parity obligations: %s" % out[-500:])
        return 0


def case_product_change_refuses() -> int:
    """(g) the control: a changed contract AND a product change since the seal.

    The receipt is not authoritative for a second reason, and that reason is a
    file somebody edited. Nothing is re-sealed and nothing is recorded."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-product-") as td:
        root, eps = _at_m4(Path(td))
        _parity(root, eps, fails=True, unauthorized=True)
        _verdict(root, DECISION_FLOORS + ["compose-parity-receipt"])
        sealed = load_json(root / ADMISSION_RECEIPT)["receipt_digest"]
        _install_harness_generation(root)
        src = sorted((root / "src").rglob("*.java"))
        if not src:
            return _fail("the fixture must carry a product source to change")
        src[0].write_text(src[0].read_text(encoding="utf-8") + "\n// a worker's edit\n", encoding="utf-8")
        rc, out, err = _run(root)
        if rc != 1 or "the product tree is not clean" not in err:
            return _fail("a product change since the seal must still refuse: rc=%d %s" % (rc, (out + err)[-600:]))
        if load_json(root / ADMISSION_RECEIPT)["receipt_digest"] != sealed:
            return _fail("a refused resume must re-seal nothing")
        if (root / BLOCKERS).is_file() or [r for r in load_json(root / LOOP_STEPS).get("rejected") or [] if r.get("kind") == "close"]:
            return _fail("a refused resume must write nothing")
        return 0


def case_worklist_rebuilt_refuses() -> int:
    """(h) the second control: a changed contract AND a work list rebuilt with
    an obligation the seal never covered.

    `verify_receipt` names the work list as well as the contract, so the gaps
    are not contracts alone and the chain is broken for a reason no re-seal
    answers: the plan on disk is not the plan the verdict was measured under."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-worklist-") as td:
        root, eps = _at_m4(Path(td))
        _parity(root, eps, fails=True, unauthorized=True)
        _verdict(root, DECISION_FLOORS + ["compose-parity-receipt"])
        sealed = load_json(root / ADMISSION_RECEIPT)["receipt_digest"]
        rebuilt = build_worklist(root)          # the parity FAILs are obligations now
        if rebuilt["measure"]["parity_mismatches"] != 2:
            return _fail("the fixture must rebuild the work list with new obligations: %s" % rebuilt["measure"])
        _install_harness_generation(root)
        rc, out, err = _run(root)
        if rc != 1 or "not authoritative" not in err:
            return _fail("a work list the seal never covered must still refuse: rc=%d %s" % (rc, (out + err)[-600:]))
        if "worklist digest" not in err:
            return _fail("the refusal must name the gap that is not a contract: %s" % err[-600:])
        if load_json(root / ADMISSION_RECEIPT)["receipt_digest"] != sealed:
            return _fail("a refused resume must re-seal nothing")
        if (root / BLOCKERS).is_file():
            return _fail("a refused resume must write nothing")
        return 0


def _scoped_acceptance_snapshot(root: Path, eps: list, scoped: str) -> None:
    """What the last ACCEPTED parity step left as the loop's baseline.

    The acceptance path re-runs the comparison SCOPED to the issued card's own
    scenarios, and `compose-parity-receipt.py` then composes over every record
    on disk: the row it just re-measured, and for every other entry point the
    record the last full run left. So the receipt carries all the rows -- and
    the ones it did not re-run are as old as the records behind them. That is
    the receipt `advance.py`'s `snapshot_reports` copies into
    verification/loop/accepted/parity/ when the step is accepted."""
    from _loop_common import snapshot_reports

    digest = load_json(root / ADMISSION_RECEIPT)["receipt_digest"]
    pdir = root / "verification" / "parity"
    pdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for ep in eps:
        write_canonical(pdir / (_slug(ep) + ".json"), {
            "schema": "rhoai3.parity/v1", "entry_point": ep, "verdict": "PASS",
            "reason": "", "receipt_sha256": digest})
        rows.append({"entry_point": ep, "verdict": "PASS",
                     "reason": "re-measured for the issued card" if ep == scoped else "the last full run's record",
                     "scenarios": []})
    write_canonical(pdir / "receipt.json", {
        "schema": "rhoai3.parity-receipt/v1", "receipt_sha256": digest,
        "producer": "compose-parity-receipt.py", "corpus_sha256": "c" * 64, "corpus_error": "",
        "binding": {"mode": "candidate", "card": "t_scoped", "candidate_sha256": "a" * 64,
                    "issued_receipt_sha256": digest},
        "entry_points": rows, "total": len(rows), "not_passed": 0,
        "cors": {"source_policies": [], "gaps": []},
        "qualification": {"present": True, "derived_corpus": False, "gap": "", "not_passed": [], "stale": []},
        "coverage_gaps": [], "verdict": "PASS"})
    snapshot_reports(root)


def _reverted_candidate(root: Path, cluster: str) -> tuple[int, str]:
    """The v9 revert, run for real: a candidate verified, the tree touched after
    the verification, `advance.py` REVERTS it -- and its reject path calls
    `restore_reports`, which puts the ACCEPTED parity snapshot back."""
    props = root / APP_PROPERTIES
    props.parent.mkdir(parents=True, exist_ok=True)
    before = props.read_text(encoding="utf-8") if props.is_file() else ""
    props.write_text(before + "\nquarkus.http.cors=true\n", encoding="utf-8")
    specimens.verify(root, errors=[], failures=[], findings={})
    props.write_text(before + "\nquarkus.http.cors=true\n# touched after the verification\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(ADVANCE), "--root", str(root), "--cluster", cluster,
                        "--card", "t_reverted", "--no-mint"], text=True, capture_output=True)
    return p.returncode, p.stdout + p.stderr


def _reverted_baseline_case(base: str) -> int:
    """Measured on destination v9, in this order: a parity card was ACCEPTED
    under a comparison SCOPED to one scenario, so the receipt that step
    snapshotted as the accepted baseline is that scoped run's; the M4 road then
    composed a FULL receipt (thirteen FAIL rows, the CORS preflight among
    them); `resume-after-m4.py` closed the M4 card and minted the obligations
    that receipt owed; and the very first candidate was REVERTED for an edit
    after its verification. `advance.py`'s reject path calls `restore_reports`,
    which restored the SCOPED snapshot over the full receipt -- and the rebuilt
    work list then had no parity obligation at all: open_clusters 0,
    parity_mismatches 0, no card, nothing minted. The obligation the loop was
    working on did not fail; it vanished, because a rejected candidate's revert
    restored a baseline older than the receipt its card was issued from.

    The baseline a card is issued against is the receipt the close was made
    on, so the close is what has to record it."""
    with tempfile.TemporaryDirectory(prefix="resume-m4-baseline-") as td:
        root, eps = _at_m4(Path(td), base=base)
        _scoped_acceptance_snapshot(root, eps, eps[0])
        refused = _parity_v9(root, eps)                      # the M4 road: FAIL, CORS + refused reads
        _verdict(root, V9_FLOORS)
        m4_receipt = sha256_file(root / "verification" / "parity" / "receipt.json")
        rc, out, err = _run(root)
        if rc != 0 or out.count("MINT (dry-run)") != 1:
            return _fail("the fixture must resume and mint the CORS obligation: rc=%d %s" % (rc, (out + err)[-800:]))
        wl = load_json(root / WORKLIST)
        owed = int(wl["measure"]["parity_mismatches"] or 0)
        cluster = str(wl.get("head") or "")
        if owed < 1 or not cluster:
            return _fail("the fixture must leave an open parity obligation to lose: %s / %s" % (wl["measure"], cluster))

        # the close made the M4 comparison the accepted baseline, which is what
        # `advance.py` hands progress() as the "before" of every card it minted
        snap = root / "verification" / "loop" / "accepted" / "parity" / "receipt.json"
        if not snap.is_file() or sha256_file(snap) != m4_receipt:
            return _fail("the close must snapshot the receipt it closed on as the accepted parity baseline: %s"
                         % (sha256_file(snap)[:12] if snap.is_file() else "absent"))
        src = load_json(root / "verification" / "loop" / "accepted" / "parity-source.json")
        if (src.get("binding") or {}).get("mode") != "sealed" or src.get("card") != CLOSE_CARD:
            return _fail("the baseline must record whose comparison it is (sealed, the M4 card): %s" % src)
        for ep in refused[:1] + [eps[1]]:
            if not (root / "verification" / "parity" / (_slug(ep) + ".json")).is_file():
                continue
            kept = root / "verification" / "loop" / "accepted" / "parity" / (_slug(ep) + ".json")
            if not kept.is_file() or load_json(kept)["verdict"] != "FAIL":
                return _fail("the per-verdict records the receipt was composed from must be snapshotted too: %s" % kept)

        rc, blob = _reverted_candidate(root, cluster)
        if rc != 1 or "REVERTED" not in blob:
            return _fail("the fixture needs the candidate REVERTED for an edit after its verification: rc=%d %s"
                         % (rc, blob[-600:]))
        live = load_json(root / "verification" / "parity" / "receipt.json")
        if live.get("verdict") != "FAIL" or sha256_file(root / "verification" / "parity" / "receipt.json") != m4_receipt:
            return _fail("a rejected candidate must not restore a parity baseline older than the receipt its card was "
                         "issued from: the receipt on disk is now %s with %d row(s)"
                         % (live.get("verdict"), len(live.get("entry_points") or [])))
        after = build_worklist(root)
        if int(after["measure"]["parity_mismatches"] or 0) != owed:
            return _fail("the obligations the reverted card was minted for must survive the revert: %s were owed, %s are "
                         "reported" % (owed, after["measure"]["parity_mismatches"]))
        if not [c for c in after["clusters"] if c["status"] == "open"]:
            return _fail("a revert that leaves no open cluster has lost the work, not judged it")
        return 0


def case_reverted_candidate_keeps_the_m4_baseline() -> int:
    """(f) the v9 sequence: accepted scoped snapshot → M4 full receipt → resume
    mints → candidate reverted → the full receipt and its obligations survive."""
    return _reverted_baseline_case("org.acme.clinic")


def case_reverted_baseline_renamed_specimen() -> int:
    """(f2) the same, under another specimen: a baseline is a receipt and a
    card id, never a specimen's names."""
    return _reverted_baseline_case("com.example.store")


def main() -> int:
    for case in (case_both, case_decisions_only, case_wrong_card, case_wrong_receipt_bindings, case_edited_after_binding,
                 case_renamed_specimen, case_contract_reseal, case_product_change_refuses,
                 case_worklist_rebuilt_refuses, case_v9_receipt_shape,
                 case_v9_without_the_repairable_row, case_v9_head_is_a_decision,
                 case_v9_renamed_specimen, case_reverted_candidate_keeps_the_m4_baseline,
                 case_reverted_baseline_renamed_specimen, case_clean_acceptance_closes,
                 case_clean_acceptance_dirty_tree, case_accept_vocabulary_is_the_roads):
        rc = case()
        if rc:
            return rc
    print("OK: resume-after-m4 (a REFUSE verdict resumes the loop on its parity obligations and records the release "
          "floors it cannot repair: ADR-015 product tests / surefire and ADR-014 unauthorized read-backs; decision "
          "floors alone are exit 2 with nothing minted and the close card still issued; a verdict for another card is "
          "refused and writes nothing, as is one bound to another admission receipt or to a parity receipt this tree "
          "no longer holds, or one edited after it was bound (the bound verdict is the verdict); a second resume refuses on the recorded close; a renamed specimen decides the "
          "same; a sealed contract a harness install moved is re-sealed with the two receipts recorded, while a "
          "product change or a rebuilt work list still refuses and re-seals nothing; and on v9's own shape -- a "
          "verdict naming check-empty-security and check-product-tests and NOT the parity floor, over a FAIL receipt "
          "with one CORS preflight and twelve refused reads -- the CORS card is minted from the receipt, the refused "
          "reads are withheld to ADR-014 and recorded, and the same receipt without the CORS row blocks at exit 2; and the close makes the comparison it closed on the ACCEPTED parity baseline, so a candidate REVERTED off the card it minted restores THAT receipt and not the older scoped one an earlier accepted step left -- the obligations survive the revert, under a renamed specimen too; and a CLEAN ACCEPTANCE -- an accepting token the road defines, no failed floor, nothing a card repairs and no floor a decision owns -- CLOSES the run instead of refusing: the close row goes on the record with its bindings, issued.json is cleared, a superseded REFUSE's release-blockers.json is rewritten as an empty record naming the verdict that cleared it and what is still outstanding, a second close-out refuses, and a dirty tree or a foreign card refuses and rewrites nothing)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
