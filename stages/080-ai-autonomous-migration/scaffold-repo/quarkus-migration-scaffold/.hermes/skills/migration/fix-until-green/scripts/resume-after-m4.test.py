#!/usr/bin/env python3
"""resume-after-m4 selftest: a REFUSE verdict is consumed, not the end of the run.

The measured case is v9's first M4 verdict: REFUSE with `check-product-tests`
and `assert-surefire-results` (ADR-015: a decision plus a harness capability,
neither of them a card) and `compose-parity-receipt` (FAIL: parity mismatches
that `planner.worklist.parity_items` turns into mandatory obligations, beside
INCONCLUSIVE entry points whose read-back answered 403 -- ADR-014). The loop
must continue on the obligations and record the decisions; doing one without
the other is either a stalled run or a hidden floor.

Cases:
  (a) two parity FAILs + two decision floors + a 403 entry point → one mint
      argv under an idempotency key no card on the record already holds, and
      release-blockers.json carrying an ADR-015 floor row and an ADR-014 entry
      point row;
  (b) decision floors only → exit 2, nothing minted, the close card still issued;
  (c) a verdict for another card → refused, nothing touched;
  (d) a second run after (a) → refused, already resumed;
  (e) the same fixture under a renamed specimen → the same decisions (the
      classification reads floors and verdicts, never a specimen's names).
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
GOLDEN = HERE.parents[4]

sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
sys.path.insert(0, str(HERE))

from planner import pipeline, specimens  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import LOOP_ISSUED, LOOP_STEPS, WORKLIST  # noqa: E402

CLOSE_CARD = "t_m4close"
BLOCKERS = Path("verification") / "loop" / "release-blockers.json"
DECISION_FLOORS = ["assert-surefire-results", "check-product-tests"]


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


def _verdict(root: Path, floors: list, *, card: str = CLOSE_CARD) -> None:
    write_canonical(root / "evidence" / "verdicts" / "m4-verdict.json", {
        "schema": "rhoai3.m4-verdict/v1", "gate": "M4_VERDICT", "phase": "M4", "ran": True,
        "card_id": card, "verdict": "REFUSE", "ship": False, "failed_floors": sorted(floors),
        "floors": [{"name": n, "rc": 1, "idle": False} for n in sorted(floors)]
                  + [{"name": "check-runnable-db-config", "rc": 0, "idle": False}],
        "coverage_account": {"retired": 0, "remaining_gaps": 0}})


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


def main() -> int:
    for case in (case_both, case_decisions_only, case_wrong_card, case_renamed_specimen):
        rc = case()
        if rc:
            return rc
    print("OK: resume-after-m4 (a REFUSE verdict resumes the loop on its parity obligations and records the release "
          "floors it cannot repair: ADR-015 product tests / surefire and ADR-014 unauthorized read-backs; decision "
          "floors alone are exit 2 with nothing minted and the close card still issued; a verdict for another card is "
          "refused and writes nothing; a second resume refuses on the recorded close; a renamed specimen decides the same)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
