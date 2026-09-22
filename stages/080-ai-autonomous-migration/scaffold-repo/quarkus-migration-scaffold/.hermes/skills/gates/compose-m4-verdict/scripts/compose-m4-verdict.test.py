#!/usr/bin/env python3
"""Operator 143706ZO: M4 producer + failed_floors schema. Not dest."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
GOLDEN = SKILL.parents[3]
SCHEMA = HERE / "assert-m4-verdict-schema.py"
SYNC = HERE / "assert-m4-verdict-schema-sync.py"
BINDER = HERE / "bind-m4-verdict.py"
CARD = "t_49c0ad27"          # v9's second M4 card: the one that wrote no card_id
RECEIPT = "a" * 64           # the admission receipt it was minted under
DEST8 = (
    GOLDEN
    / ".hermes"
    / "skills"
    / "gates"
    / "check-release-readiness"
    / "fixtures"
    / "complete-around"
    / "dest-8-m4-verdict.json"
)


def _binder_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("bind_m4_verdict", BINDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def record(root: Path, vp: Path) -> dict:
    """What bind-m4-verdict.py records for a verdict it bound: the digest of
    the file, a copy, the bindings. A case that writes a bound verdict by hand
    records it this way, so what it measures is the binding, not the record."""
    doc = json.loads(vp.read_text(encoding="utf-8"))
    return _binder_module().write_binding_record(root, vp, doc)


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        text=True,
        capture_output=True,
    )


def tree(root: Path) -> str:
    """A destination at M4: the close card is issued and minted, and the parity
    phase left its receipt. The two artifacts the verdict's bindings name.

    Returns the parity receipt's digest -- what a bound verdict must carry."""
    issued = root / "verification" / "loop" / "issued.json"
    issued.parent.mkdir(parents=True, exist_ok=True)
    issued.write_text(
        json.dumps({"schema": "rhoai3.loop-issued/v1", "cluster": "M4_VERIFY", "kind": "close",
                    "attempt": 1, "idempotency_key": "k4:M4_VERIFY:1:" + RECEIPT[:16],
                    "receipt_sha256": RECEIPT, "task_id": CARD}) + "\n",
        encoding="utf-8",
    )
    receipt = root / "verification" / "parity" / "receipt.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        json.dumps({"schema": "rhoai3.parity-receipt/v1", "receipt_sha256": RECEIPT,
                    "entry_points": [], "verdict": "FAIL"}) + "\n",
        encoding="utf-8",
    )
    return hashlib.sha256(receipt.read_bytes()).hexdigest()


def verdict_path(root: Path, doc: dict, *, bind: str | None = "") -> Path:
    """Write the verdict where the lint derives its root from (two directories
    above it). `bind` fills the three bindings unless the case overrides one."""
    doc = dict(doc)
    if bind is not None:
        doc.setdefault("card_id", CARD)
        doc.setdefault("receipt_sha256", RECEIPT)
        doc.setdefault("parity_receipt_sha256", bind)
    p = root / "evidence" / "verdicts" / "m4-verdict.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc) + "\n", encoding="utf-8")
    return p


MEASURED = {
    "gate": "M4_VERDICT", "phase": "M4", "ran": True, "verdict": "REFUSE", "ship": False,
    "failed_floors": ["check-empty-security", "check-product-tests"],
    "coverage_account": {"retired": 0, "remaining_gaps": 0},
    "floors": [{"name": "check-empty-security", "rc": 1, "idle": False},
               {"name": "check-product-tests", "rc": 1, "idle": False},
               {"name": "check-runnable-db-config", "rc": 0, "idle": False}],
}


def bindings() -> int:
    """v9's second M4 card: an honest REFUSE bound to nothing.

    The floors it measured are the same in every case below -- only the binding
    moves, so what the lint is measuring is the binding and not the shape."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        parity = tree(root)

        vp0 = verdict_path(root, MEASURED, bind=parity)
        proc = run(SCHEMA, str(vp0))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "no binding record" not in blob:
            print("FAIL: bindings typed by hand with no record must REFUSE naming the record: %s" % blob, file=sys.stderr)
            return 1
        record(root, vp0)
        proc = run(SCHEMA, str(vp0))
        if proc.returncode != 0:
            print("FAIL: a bound verdict must PASS: %s%s" % (proc.stdout, proc.stderr), file=sys.stderr)
            return 1
        for needle in (CARD, RECEIPT[:12], parity[:12]):
            if needle not in proc.stdout:
                print("FAIL: the OK line must report the binding it checked (%s): %s" % (needle, proc.stdout), file=sys.stderr)
                return 1

        # (1) v9 itself: no card_id at all. The card completed and the resume
        # could not attribute the measurement to a run.
        no_card = {k: v for k, v in MEASURED.items()}
        proc = run(SCHEMA, str(verdict_path(root, dict(no_card, receipt_sha256=RECEIPT,
                                                       parity_receipt_sha256=parity), bind=None)))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "M4_VERDICT_BINDING" not in blob or "card_id" not in blob:
            print("FAIL: a verdict with no card_id must REFUSE by name: %s" % blob, file=sys.stderr)
            return 1

        # (2) the first card's id carried over to the second card's verdict
        proc = run(SCHEMA, str(verdict_path(root, dict(MEASURED, card_id="t_32c82390"), bind=parity)))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "is not the issued close card" not in blob or CARD not in blob:
            print("FAIL: a verdict for another card must REFUSE naming both cards: %s" % blob, file=sys.stderr)
            return 1

        # (3) another tree: the card was minted under a different admission receipt
        proc = run(SCHEMA, str(verdict_path(root, dict(MEASURED, receipt_sha256="b" * 64), bind=parity)))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "is not the admission receipt" not in blob:
            print("FAIL: a foreign admission receipt must REFUSE: %s" % blob, file=sys.stderr)
            return 1

        # (4) evidence this tree does not hold: the parity receipt moved
        proc = run(SCHEMA, str(verdict_path(root, dict(MEASURED, parity_receipt_sha256="c" * 64), bind=parity)))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "is not the digest of verification/parity/receipt.json" not in blob:
            print("FAIL: a stale parity receipt digest must REFUSE: %s" % blob, file=sys.stderr)
            return 1

        # (5) the binder writes what a worker must not: it fills the three from
        # issued.json and the receipt, and the lint then agrees
        vp = verdict_path(root, MEASURED, bind=None)
        # case (1) recorded a hand binding in this root; a fresh record is what
        # this case measures, so that one is removed rather than superseded
        (root / "evidence" / "verdicts" / "m4-verdict.bound.json").unlink()
        proc = run(BINDER, "--root", str(root))
        if proc.returncode != 0:
            print("FAIL: bind-m4-verdict must bind an unbound verdict: %s%s" % (proc.stdout, proc.stderr), file=sys.stderr)
            return 1
        bound = json.loads(vp.read_text(encoding="utf-8"))
        if bound.get("card_id") != CARD or bound.get("receipt_sha256") != RECEIPT or bound.get("parity_receipt_sha256") != parity:
            print("FAIL: the binder must write all three bindings: %s" % bound, file=sys.stderr)
            return 1
        if bound.get("failed_floors") != MEASURED["failed_floors"] or bound.get("floors") != MEASURED["floors"]:
            print("FAIL: the binder must not touch what the floors measured: %s" % bound, file=sys.stderr)
            return 1
        proc = run(SCHEMA, str(vp))
        if proc.returncode != 0:
            print("FAIL: the lint must accept what the binder bound: %s%s" % (proc.stdout, proc.stderr), file=sys.stderr)
            return 1
        rec_p = root / "evidence" / "verdicts" / "m4-verdict.bound.json"
        rec = json.loads(rec_p.read_text(encoding="utf-8"))
        if rec.get("schema") != "rhoai3.m4-verdict-binding/v1" or rec.get("verdict_sha256") != hashlib.sha256(vp.read_bytes()).hexdigest() \
                or rec.get("card_id") != CARD or rec.get("verdict", {}).get("failed_floors") != MEASURED["failed_floors"] or rec.get("superseded") != []:
            print("FAIL: the binder must record the verdict as bound (digest, copy, bindings): %s" % rec, file=sys.stderr)
            return 1
        proc = run(BINDER, "--root", str(root))
        if proc.returncode != 0 or "already bound" not in proc.stdout:
            print("FAIL: re-binding an unchanged bound verdict is a no-op: %s%s" % (proc.stdout, proc.stderr), file=sys.stderr)
            return 1

        # (5b) v9 t_caf2ad51: the bound verdict revised by hand -- failed_floors
        # changed, card_id blanked. The binder, the lint and the resume all
        # refuse it naming the fields that differ; it is never re-bound.
        revised = dict(bound, failed_floors=["check-empty-security", "check-product-tests", "assert-mta-rescan"],
                       verdict="REFUSE", card_id="")
        revised["floors"] = list(MEASURED["floors"]) + [{"name": "assert-mta-rescan", "rc": 1, "idle": False}]
        vp.write_text(json.dumps(revised) + "\n", encoding="utf-8")
        proc = run(SCHEMA, str(vp))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "card_id" not in blob:
            print("FAIL: the revised verdict must REFUSE on its blanked binding: %s" % blob, file=sys.stderr)
            return 1
        proc = run(BINDER, "--root", str(root))
        if proc.returncode != 0:
            # a verdict without bindings is a composition: binding it supersedes the record
            print("FAIL: an unbound composition binds, superseding the record: %s%s" % (proc.stdout, proc.stderr), file=sys.stderr)
            return 1
        rec = json.loads(rec_p.read_text(encoding="utf-8"))
        if len(rec.get("superseded") or []) != 1 or rec["superseded"][0].get("verdict", {}).get("failed_floors") != MEASURED["failed_floors"] \
                or "superseding" not in proc.stdout:
            print("FAIL: the superseded binding must stay on the record with its verdict copy: %s" % rec, file=sys.stderr)
            return 1
        # Now edit the BOUND verdict in place, keeping its bindings and a
        # SHAPE the lint accepts -- a floor dropped from both lists, which is
        # what a hand revision looks like. Only the binding record can catch
        # this one, and it must.
        bound2 = json.loads(vp.read_text(encoding="utf-8"))
        edited = dict(bound2,
                      failed_floors=[f for f in bound2["failed_floors"] if f != "assert-mta-rescan"],
                      floors=[f for f in bound2["floors"] if f.get("name") != "assert-mta-rescan"])
        vp.write_text(json.dumps(edited) + "\n", encoding="utf-8")
        proc = run(SCHEMA, str(vp))
        if "M4_VERDICT_SCHEMA" in (proc.stdout + proc.stderr):
            print("FAIL: the edited verdict must be shape-valid, so the record is what catches it: %s%s"
                  % (proc.stdout, proc.stderr), file=sys.stderr)
            return 1
        proc = run(BINDER, "--root", str(root))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "edited after binding" not in blob or "failed_floors" not in blob or "floors" not in blob:
            print("FAIL: the binder must refuse a bound verdict edited after binding, naming the fields: %s" % blob, file=sys.stderr)
            return 1
        proc = run(SCHEMA, str(vp))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "edited after binding" not in blob or "failed_floors" not in blob:
            print("FAIL: the lint must refuse a bound verdict edited after binding: %s" % blob, file=sys.stderr)
            return 1
        rec2 = json.loads(rec_p.read_text(encoding="utf-8"))
        if rec2 != rec:
            print("FAIL: a refused re-bind must not touch the record", file=sys.stderr)
            return 1

    # (6) no issued card at all: nothing to bind to, and the lint says so
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        proc = run(SCHEMA, str(verdict_path(root, MEASURED, bind="d" * 64)))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "verification/loop/issued.json" not in blob:
            print("FAIL: a tree with no issued card must REFUSE naming it: %s" % blob, file=sys.stderr)
            return 1
        proc = run(BINDER, "--root", str(root))
        if proc.returncode != 1 or "no issued card" not in (proc.stdout + proc.stderr):
            print("FAIL: the binder must refuse with no issued card: %s%s" % (proc.stdout, proc.stderr), file=sys.stderr)
            return 1
    return 0


def main() -> int:
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    if "--skill compose-m4-verdict" not in skill_md:
        print("FAIL: SKILL.md must pin --skill compose-m4-verdict", file=sys.stderr)
        return 1
    if "failed_floors" not in skill_md:
        print("FAIL: SKILL.md must name failed_floors", file=sys.stderr)
        return 1
    if "evidence/receipts/gates/" not in skill_md:
        print("FAIL: SKILL.md must consume evidence/receipts/gates/", file=sys.stderr)
        return 1
    if "idle" not in skill_md.lower():
        print("FAIL: SKILL.md must fold failed-floor-as-idle", file=sys.stderr)
        return 1
    # The binding is the tool's job, and the SKILL is where the worker is told
    # so -- both the binder and the values a hand-authored verdict must copy.
    for needle in ("bind-m4-verdict.py", "card_id", "receipt_sha256", "parity_receipt_sha256", "m4-verdict.bound.json",
                   "verification/loop/issued.json"):
        if needle not in skill_md:
            print("FAIL: SKILL.md must name %s in the authoring step" % needle, file=sys.stderr)
            return 1
    if not BINDER.is_file():
        print("FAIL: the SKILL names a binder that is not in scripts/", file=sys.stderr)
        return 1

    ready = (
        GOLDEN
        / ".hermes"
        / "skills"
        / "gates"
        / "check-release-readiness"
        / "SKILL.md"
    )
    ready_txt = ready.read_text(encoding="utf-8")
    if "compose-m4-verdict" not in ready_txt:
        print(
            "FAIL: check-release-readiness must name compose-m4-verdict as producer",
            file=sys.stderr,
        )
        return 1

    agents = GOLDEN / "AGENTS.md"
    if "compose-m4-verdict" not in agents.read_text(encoding="utf-8"):
        print("FAIL: AGENTS.md skill router must name compose-m4-verdict", file=sys.stderr)
        return 1

    proc = run(SYNC)
    if proc.returncode != 0:
        print("FAIL: schema sync: %s%s" % (proc.stdout, proc.stderr), file=sys.stderr)
        return 1

    if not DEST8.is_file():
        print("FAIL: missing dest-8 verdict fixture", file=sys.stderr)
        return 1
    proc = run(SCHEMA, str(DEST8))
    blob = proc.stdout + proc.stderr
    if proc.returncode != 1 or "failed_floors" not in blob:
        print("FAIL: dest-8 verdict must REFUSE missing failed_floors: %s" % blob, file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        parity = tree(root)
        honest = {
            "gate": "M4_VERDICT",
            "phase": "M4",
            "ran": True,
            "verdict": "REFUSE",
            "ship": False,
            "failed_floors": ["check-product-tests"],
            "coverage_account": {"retired": 0, "remaining_gaps": 0},
            "floors": [{"name": "check-product-tests", "rc": 1, "idle": False}],
            "reason": ("AR-2.8 no executed product test covers ANY declared "
                       "capability: 2 uncovered (sc-001, sc-002)"),
        }
        vp_honest = verdict_path(root, honest, bind=parity)
        record(root, vp_honest)
        proc = run(SCHEMA, str(vp_honest))
        if proc.returncode != 0:
            print(
                "FAIL: honest REFUSE + failed_floors + bindings must PASS: %s%s"
                % (proc.stdout, proc.stderr),
                file=sys.stderr,
            )
            return 1

        idle_fail = {
            "gate": "M4_VERDICT",
            "phase": "M4",
            "ran": True,
            "verdict": "PROVISIONAL_ACCEPT",
            "ship": False,
            "failed_floors": [],
            "coverage_account": {"retired": 0, "remaining_gaps": 0},
            "floors": [{"name": "check-product-tests", "rc": 1, "idle": True}],
            "reason": "AR-2.8 completion floor idle",
        }
        proc = run(SCHEMA, str(verdict_path(root, idle_fail, bind=parity)))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "FAILED_FLOOR_AS_IDLE" not in blob:
            print("FAIL: idle-for-failed-floor must REFUSE: %s" % blob, file=sys.stderr)
            return 1

        accept_fail = {
            "gate": "M4_VERDICT",
            "phase": "M4",
            "ran": True,
            "verdict": "PROVISIONAL_ACCEPT",
            "ship": False,
            "failed_floors": ["check-product-tests"],
            "coverage_account": {"retired": 0, "remaining_gaps": 0},
            "floors": [{"name": "check-product-tests", "rc": 1, "idle": False}],
        }
        proc = run(SCHEMA, str(verdict_path(root, accept_fail, bind=parity)))
        blob = proc.stdout + proc.stderr
        if proc.returncode != 1 or "ACCEPT_WITH_FAILED_FLOOR" not in blob:
            print("FAIL: ACCEPT + failed_floors must REFUSE: %s" % blob, file=sys.stderr)
            return 1

        genuine = {
            "gate": "M4_VERDICT",
            "phase": "M4",
            "ran": True,
            "verdict": "PROVISIONAL_ACCEPT",
            "ship": False,
            "failed_floors": [],
            "coverage_account": {"retired": 0, "remaining_gaps": 0},
            "floors": [
                {"name": "check-runnable-db-config", "rc": 0, "idle": True},
                {"name": "check-product-tests", "rc": 0, "idle": False},
            ],
            "reason": "AR-2.1 completion floor idle (no DB intent)",
        }
        vp_genuine = verdict_path(root, genuine, bind=parity)
        record(root, vp_genuine)
        proc = run(SCHEMA, str(vp_genuine))
        if proc.returncode != 0:
            print(
                "FAIL: genuine idle + rc 0 must PASS: %s%s"
                % (proc.stdout, proc.stderr),
                file=sys.stderr,
            )
            return 1

    # a verdict with no coverage account refuses: what an ADR retired must be
    # accounted for in M4 evidence, not left to a reader to notice
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        parity = tree(root)
        doc = {"gate": "M4_VERDICT", "phase": "M4", "ran": True, "verdict": "REFUSE", "ship": False,
               "failed_floors": [], "floors": [{"name": "check-product-tests", "rc": 0, "idle": False}]}
        proc = run(SCHEMA, str(verdict_path(root, doc, bind=parity)))
        if proc.returncode != 1 or "coverage_account" not in (proc.stdout + proc.stderr):
            print("FAIL: a verdict with no coverage_account must REFUSE: %s%s" % (proc.stdout, proc.stderr), file=sys.stderr)
            return 1
        doc["coverage_account"] = {"retired": "5", "remaining_gaps": 0}
        proc = run(SCHEMA, str(verdict_path(root, doc, bind=parity)))
        if proc.returncode != 1 or "must be int" not in (proc.stdout + proc.stderr):
            print("FAIL: coverage_account counts must be ints: %s%s" % (proc.stdout, proc.stderr), file=sys.stderr)
            return 1

    rc = bindings()
    if rc:
        return rc
    print("OK: compose-m4-verdict producer + failed_floors + coverage_account schema + card/receipt bindings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
