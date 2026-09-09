#!/usr/bin/env python3
"""admit-migration-plan selftest (v3): ADMITTED/INCONCLUSIVE/COMPAT_FAIL, seals, activation, pins, CLI exits."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
ADMIT = HERE / "admit-migration-plan.py"
VERIFY = HERE / "verify-admission-receipt.py"
ACTIVATED = HERE / "assert-planner-activated.py"
BOOTSTRAP = GOLDEN / ".hermes" / "skills" / "migration" / "bootstrap-destination" / "scripts" / "bootstrap-destination.py"
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
sys.path.insert(0, str(GOLDEN / ".hermes" / "kernel"))
from k4_convert import convert_admitted  # noqa: E402
from planner import pipeline, specimens  # noqa: E402
from planner.admission import receipt_digest  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.paths import ADMISSION_RECEIPT, EVIDENCE_BUNDLE, SCHEMAS_DIR, WORKLIST  # noqa: E402
from planner.schema_lite import load_schema, validate  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True)


def _prepare(root: Path) -> None:
    specimens.prepare_loop(root)


def _blocks(rec: dict) -> set[str]:
    return {b["class"] for b in rec.get("blocks") or []}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="admit-") as tmp:
        t = Path(tmp).resolve()
        root = specimens.build_dest(t / "ok", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        _prepare(root)
        p = _run([sys.executable, str(ADMIT), "--root", str(root)])
        if p.returncode != 0 or "ADMITTED" not in p.stdout:
            return _fail("admit: %s%s" % (p.stdout, p.stderr))
        rec = load_json(root / ADMISSION_RECEIPT)
        if validate(rec, load_schema(root / SCHEMAS_DIR / "admission-receipt.schema.json")):
            return _fail("receipt schema")
        seals = rec["seals"]
        for key in ("evidence_bundle", "worklist", "bootstrap", "pins"):
            if len(seals[key]) != 64:
                return _fail("seal %s" % key)
        if not seals["decisions_yaml"] or not any(k.endswith("decisions.schema.json") for k in seals["contracts"]) or not any("mta-rules" in k for k in seals["contracts"]) or not any(k.endswith("compat-mapping.json") for k in seals["contracts"]):
            return _fail("receipt must seal decisions.yaml, schemas, catalogs (incl. compat-mapping), and MTA rules")
        first = (root / ADMISSION_RECEIPT).read_bytes()
        _run([sys.executable, str(ADMIT), "--root", str(root)])
        if (root / ADMISSION_RECEIPT).read_bytes() != first:
            return _fail("receipt not byte-identical on rerun")
        if _run([sys.executable, str(VERIFY), "--root", str(root)]).returncode != 0:
            return _fail("verify must pass on an intact ADMITTED receipt")
        # decisions.yaml changed after admission → verify refuses
        (root / "decisions.yaml").write_text((root / "decisions.yaml").read_text() + "\n# touched\n", encoding="utf-8")
        p = _run([sys.executable, str(VERIFY), "--root", str(root)])
        if p.returncode != 1 or "decisions.yaml" not in p.stderr:
            return _fail("changed decisions must refuse verify: %s" % p.stderr)
        _run([sys.executable, str(ADMIT), "--root", str(root)])
        # hand-edited work list → seal mismatch → COMPAT_FAIL or refuse
        wl = load_json(root / WORKLIST)
        wl["schema"] = "rhoai3.worklist/v0"
        write_canonical(root / WORKLIST, wl)
        p = _run([sys.executable, str(ADMIT), "--root", str(root)])
        rec = load_json(root / ADMISSION_RECEIPT)
        if p.returncode != 2 or rec["status"] != "COMPAT_FAIL":
            return _fail("hand-edited work list must be COMPAT_FAIL: rc=%s %s" % (p.returncode, rec["reasons"][:2]))
        pipeline.plan(root)
        # INCONCLUSIVE path: missing decisions → exit 1 with blocks; verify refuses; --any-status accepts
        inc = specimens.build_dest(t / "inc", specimens.specimen("http"), decisions=specimens.full_decisions(max_attempts=None))
        _prepare(inc)
        p = _run([sys.executable, str(ADMIT), "--root", str(inc)])
        if p.returncode != 1 or "INCONCLUSIVE" not in p.stderr or "MISSING_DECISION" not in p.stderr:
            return _fail("inconclusive: rc=%s %s" % (p.returncode, p.stderr[-300:]))
        if _run([sys.executable, str(VERIFY), "--root", str(inc)]).returncode != 1:
            return _fail("verify must refuse a non-ADMITTED receipt")
        if _run([sys.executable, str(VERIFY), "--root", str(inc), "--any-status"]).returncode != 0:
            return _fail("verify --any-status accepts intact INCONCLUSIVE")
        # negatives that each keep admission INCONCLUSIVE
        for label, kw, cls in (
            ("kantra", {"mta_admissible": False}, "MTA_PROVENANCE"),
            ("canary", {"drop_canary": True}, "CANARY_MISSING"),
            ("extractor", {"structure_status": "unpinned"}, "STRUCTURE_MISSING"),
            ("platform", {"decisions": specimens.full_decisions(platform="wildfly-99")}, "PLATFORM_UNKNOWN"),
            ("adr", {"decisions": specimens.full_decisions(adrs=[{"id": "ADR-001", "status": "proposed"}, {"id": "ADR-002", "status": "accepted"}, {"id": "ADR-003", "status": "accepted"}])}, "ADR_NOT_ACCEPTED"),
            ("mta-version", {"pins_override": {"mta_cli": {"version": "8.1"}}}, "TOOL_PIN_MISMATCH"),
            ("extractor-unpinned", {"pins_override": {"structure_extractor": {"status": "unpinned"}}}, "TOOL_UNPINNED"),
        ):
            kw = dict(kw)
            dec = kw.pop("decisions", specimens.admitted_decisions())
            d = specimens.build_dest(t / label, specimens.specimen("http"), decisions=dec, **kw)
            _prepare(d)
            rec_d = pipeline.admit(d)
            if rec_d["status"] != "INCONCLUSIVE" or cls not in _blocks(rec_d):
                return _fail("%s must BLOCK %s: %s %s" % (label, cls, rec_d["status"], sorted(_blocks(rec_d))))
            if convert_admitted(d)[0] is not None:
                return _fail("%s: K4 must emit nothing" % label)
        # activation: golden not-activated; fixture not-activated never admits; forged receipt refused by K4; pilot seal bundle-bound
        golden_pins = load_json(GOLDEN / ".hermes" / "pins.json")["pins"]
        if str((golden_pins.get("planner") or {}).get("activation")) != "not-activated":
            return _fail("golden pins.json must ship not-activated")
        na = specimens.build_dest(t / "na", specimens.specimen("http"), decisions=specimens.admitted_decisions(), activation="not-activated")
        _prepare(na)
        p = _run([sys.executable, str(ACTIVATED), "--root", str(na)])
        if p.returncode != 1 or "PLANNER_NOT_ACTIVATED" not in p.stderr:
            return _fail("not-activated gate must refuse: %s" % p.stderr)
        rec_na = pipeline.admit(na)
        if rec_na["status"] != "INCONCLUSIVE" or "PLANNER_NOT_ACTIVATED" not in _blocks(rec_na) or rec_na["activation"]["mode"] != "not-activated":
            return _fail("not-activated pins must never ADMIT: %s" % sorted(_blocks(rec_na)))
        forged = dict(rec_na, status="ADMITTED", reasons=[], blocks=[])
        forged["receipt_digest"] = receipt_digest(forged)
        write_canonical(na / ADMISSION_RECEIPT, forged)
        conv, issues = convert_admitted(na)
        if conv is not None or not any("PLANNER_NOT_ACTIVATED" in str(i[1]) for i in issues):
            return _fail("forged ADMITTED receipt under not-activated pins must be refused by K4: %s" % issues)
        bundle_sha = digest(load_json(na / EVIDENCE_BUNDLE))
        pins = load_json(na / ".hermes" / "pins.json")
        pins["pins"]["planner"] = {"activation": "pilot", "pilot": {"run_id": "pilot-1", "authorized_by": "Operator GO test", "evidence_bundle_sha256": "1" * 64}}
        (na / ".hermes" / "pins.json").write_text(json.dumps(pins), encoding="utf-8")
        if "PLANNER_PILOT_SEAL" not in _blocks(pipeline.admit(na)):
            return _fail("pilot seal for another bundle must refuse")
        pins["pins"]["planner"]["pilot"]["evidence_bundle_sha256"] = bundle_sha
        (na / ".hermes" / "pins.json").write_text(json.dumps(pins), encoding="utf-8")
        rec_p = pipeline.admit(na)
        if rec_p["status"] != "ADMITTED" or rec_p["activation"]["mode"] != "pilot":
            return _fail("pilot seal bound to this bundle must ADMIT: %s %s" % (rec_p["status"], rec_p["reasons"][:3]))
        if _run([sys.executable, str(ACTIVATED), "--root", str(na)]).returncode != 0:
            return _fail("gate must pass under a matching pilot seal")
        # pins changed after admission → verify refuses
        pins["pins"]["planner"]["note"] = "touched"
        (na / ".hermes" / "pins.json").write_text(json.dumps(pins), encoding="utf-8")
        p = _run([sys.executable, str(VERIFY), "--root", str(na)])
        if p.returncode != 1 or "pins" not in p.stderr:
            return _fail("changed pins must refuse verify: %s" % p.stderr)
    print("OK: admit-migration-plan (ADMITTED sealed + identical; decisions/pins drift refused; edited work list COMPAT_FAIL; INCONCLUSIVE exit 1; provenance/canary/extractor/platform/ADR/pin negatives; not-activated never admits + forged receipt refused; pilot seal bundle-bound)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
