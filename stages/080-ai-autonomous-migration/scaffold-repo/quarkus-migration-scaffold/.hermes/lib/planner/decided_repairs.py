"""Decided repairs applied at bootstrap (ADR-019 §2 and §3): what admission,
the loop baseline and the run report read.

A decided repair is a repair an accepted ADR already made, carried into a
fresh run as a TRANSFORMATION instead of a mid-run Operator step: the
specimen's versioned manifest (named and digest-pinned by ``decisions.yaml``
``decided_repairs``) enumerates the transformations, the bootstrap producer
applies them before the first loop baseline, and every application leaves a
row in ``evidence/producers/decided-repairs.json``. The engine lives with its
producer (``bootstrap-destination/scripts/_decided_repairs.py``); this module
only READS the decision and the receipt, so admission and the baseline can
refuse without importing the producer.

The run is then classified ``autonomous_execution_with_predecided_repairs``:
autonomous EXECUTION, with decided repair knowledge in its preparation. Both
facts are recorded; neither hides the other.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from planner.canonical import load_json, sha256_file
from planner.paths import BOOTSTRAP_RECEIPT, DECIDED_REPAIRS_RECEIPT, LOOP_STEPS

SECTION = "decided_repairs"
CLASSIFICATION = "autonomous_execution_with_predecided_repairs"
RECEIPT_SCHEMA = "rhoai3.decided-repairs-receipt/v1"
MANIFEST_SCHEMA = "rhoai3.decided-repairs-manifest/v1"


def section(doc: dict[str, Any] | None) -> dict[str, Any]:
    """The decisions.yaml ``decided_repairs`` block, or {} when none is decided."""
    sec = (doc or {}).get(SECTION)
    return sec if isinstance(sec, dict) and sec.get("manifest") else {}


def section_gaps(doc: dict[str, Any], accepted: set[str]) -> list[dict[str, str]]:
    """Shape of the decision itself (decisions.missing_decisions calls this)."""
    sec = (doc or {}).get(SECTION)
    if sec in (None, {}):
        return []
    out: list[dict[str, str]] = []
    if not isinstance(sec, dict):
        return [{"class": "MISSING_DECISION", "subject": SECTION, "detail": "decided_repairs must be a mapping"}]
    if str(sec.get("adr") or "") not in accepted:
        out.append({"class": "ADR_NOT_ACCEPTED", "subject": SECTION, "detail": "decided_repairs cites %r which is not an accepted ADR" % sec.get("adr")})
    for field in ("manifest", "manifest_sha256"):
        if not str(sec.get(field) or "").strip():
            out.append({"class": "MISSING_DECISION", "subject": "%s.%s" % (SECTION, field),
                        "detail": "a decided repair set is named by its manifest path AND pinned by that manifest's sha256"})
    for adr in sec.get("applies") or []:
        if str(adr) not in accepted:
            out.append({"class": "ADR_NOT_ACCEPTED", "subject": "%s.applies" % SECTION, "detail": "decided_repairs applies %r which is not an accepted ADR" % adr})
    return out


def _baseline_recorded(root: Path) -> bool:
    p = Path(root) / LOOP_STEPS
    if not p.is_file():
        return False
    try:
        return bool((load_json(p) or {}).get("steps"))
    except ValueError:
        return False


def receipt_gaps(root: Path, doc: dict[str, Any] | None, *, for_baseline: bool = False) -> list[dict[str, str]]:
    """Every reason the decided repairs are not demonstrably applied.

    ``for_baseline`` is the question the loop asks before it records step 0;
    admission asks the same question afterwards. The one difference: a run
    whose bootstrap PREDATES this capability (its bootstrap receipt carries no
    ``decided_repairs`` key) and whose baseline is already recorded took these
    repairs as Operator steps, which the intervention accounting already sees
    -- blocking it now would stall a run for a rule it could not have met."""
    root = Path(root)
    sec = section(doc)
    if not sec:
        return []
    out: list[dict[str, str]] = []

    def gap(cls: str, subject: str, detail: str) -> None:
        out.append({"class": cls, "subject": subject, "detail": detail})

    manifest = root / str(sec["manifest"])
    if not manifest.is_file():
        gap("DECIDED_REPAIRS_MANIFEST", str(sec["manifest"]), "the decided repair manifest named by decisions.yaml is absent")
    elif sha256_file(manifest) != str(sec.get("manifest_sha256") or ""):
        gap("DECIDED_REPAIRS_MANIFEST", str(sec["manifest"]),
            "the manifest's sha256 %s is not the one decisions.yaml pins (%s)" % (sha256_file(manifest)[:12], str(sec.get("manifest_sha256") or "")[:12]))
    bs_p = root / BOOTSTRAP_RECEIPT
    bs = load_json(bs_p) if bs_p.is_file() else {}
    if "decided_repairs" not in bs:
        if not for_baseline and _baseline_recorded(root) and bs:
            return out
        gap("DECIDED_REPAIRS_MISSING", str(DECIDED_REPAIRS_RECEIPT),
            "decisions.yaml decides repairs for bootstrap but the bootstrap that produced this tree did not apply them; re-run bootstrap-destination before the loop baseline")
        return out
    rp = root / DECIDED_REPAIRS_RECEIPT
    if not rp.is_file():
        gap("DECIDED_REPAIRS_MISSING", str(DECIDED_REPAIRS_RECEIPT), "the decided repair receipt is absent")
        return out
    rec = load_json(rp)
    if rec.get("schema") != RECEIPT_SCHEMA:
        gap("DECIDED_REPAIRS_MISSING", str(DECIDED_REPAIRS_RECEIPT), "not a %s document" % RECEIPT_SCHEMA)
        return out
    bound = (bs.get("decided_repairs") or {}).get("receipt_sha256")
    if bound != sha256_file(rp):
        gap("DECIDED_REPAIRS_STALE", str(DECIDED_REPAIRS_RECEIPT), "the receipt changed after the bootstrap receipt bound it")
    if str((rec.get("decision") or {}).get("manifest_sha256") or "") != str(sec.get("manifest_sha256") or ""):
        gap("DECIDED_REPAIRS_STALE", str(DECIDED_REPAIRS_RECEIPT),
            "the receipt applied manifest %s, decisions.yaml now pins %s; re-run bootstrap-destination"
            % (str((rec.get("decision") or {}).get("manifest_sha256") or "")[:12], str(sec.get("manifest_sha256") or "")[:12]))
    for row in rec.get("rows") or []:
        if row.get("status") == "refused":
            ref = row.get("refusal") or {}
            gap("DECIDED_REPAIR_REFUSED", str(row.get("id")), "%s: %s" % (ref.get("class"), ref.get("detail")))
    if manifest.is_file():
        try:
            want = [str(t.get("id")) for t in (load_json(manifest).get("transformations") or [])]
        except ValueError:
            want = []
        have = {str(r.get("id")) for r in rec.get("rows") or []}
        missing = [t for t in want if t not in have]
        if missing:
            gap("DECIDED_REPAIRS_INCOMPLETE", str(DECIDED_REPAIRS_RECEIPT), "no receipt row for %s" % ", ".join(missing[:5]))
    # a refusal that belongs to no single row (the effective build
    # configuration, the manifest itself) is still a refusal
    reported = {o["subject"] for o in out}
    for blk in rec.get("blocks") or []:
        if str(blk.get("subject")) not in reported:
            gap("DECIDED_REPAIR_REFUSED", str(blk.get("subject")), "%s: %s" % (blk.get("class"), blk.get("detail")))
    if rec.get("status") != "ok" and not out:
        gap("DECIDED_REPAIR_REFUSED", str(DECIDED_REPAIRS_RECEIPT), "the receipt status is %r" % rec.get("status"))
    return out


def summary(root: Path, doc: dict[str, Any] | None) -> dict[str, Any]:
    """What admission records about the run's pre-decided repairs."""
    root = Path(root)
    sec = section(doc)
    if not sec:
        return {"declared": False, "classification": None}
    rp = root / DECIDED_REPAIRS_RECEIPT
    out: dict[str, Any] = {
        "declared": True,
        "classification": CLASSIFICATION,
        "adr": str(sec.get("adr") or ""),
        "applies": [str(a) for a in (sec.get("applies") or [])],
        "manifest": str(sec.get("manifest") or ""),
        "manifest_sha256": str(sec.get("manifest_sha256") or ""),
        "receipt": str(DECIDED_REPAIRS_RECEIPT),
        "receipt_sha256": sha256_file(rp) if rp.is_file() else "",
    }
    if rp.is_file():
        rec = load_json(rp)
        rows = rec.get("rows") or []
        out["counts"] = {s: sum(1 for r in rows if r.get("status") == s) for s in ("applied", "already-applied", "refused")}
        out["inventory"] = len(rec.get("inventory") or [])
    else:
        bs_p = root / BOOTSTRAP_RECEIPT
        if bs_p.is_file() and "decided_repairs" not in load_json(bs_p):
            out["applied_at_bootstrap"] = False
            out["note"] = "this run was bootstrapped before decided repairs existed; the repairs entered it as Operator steps"
    return out
