"""Admission receipt (SAD v3 §7): seal and verdict over the evidence bundle,
the work list, the bootstrap receipt, `decisions.yaml`, the contracts
(schemas, catalogs, MTA rules) and the tool pins.

Admission means "the loop may run the next step from this exact state".

- ``ADMITTED``      every fail-closed boundary holds: mandatory tools pinned
                    and matching their receipts, MTA analysis admissible with
                    the canary fired, activation/pilot seal covers this
                    bundle, required decisions present, the measure is
                    fully known, and the work list is either non-empty or
                    empty with nothing deferred (→ M4).
- ``INCONCLUSIVE``  a boundary is open; nothing mints.
- ``COMPAT_FAIL``   an artifact fails its schema or the digest chain is
                    broken; the planner itself is at fault.

The receipt digest is the SHA-256 of the canonical receipt without its own
``receipt_digest``. K4 binds every idempotency key and every K1 body to it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from planner.canonical import digest, is_sha256, load_json, sha256_file
from planner.decisions import missing_decisions
from planner.paths import ADMISSION_RECEIPT, BOOTSTRAP_RECEIPT, DECISIONS, EVIDENCE_BUNDLE, LOOP_STEPS, SCHEMAS_DIR, WORKLIST, contract_files
from planner.pins import activation_gaps, activation_record, digestable_pins, load_pins, pin_gaps
from planner.schema_lite import load_schema, validate

SCHEMA = "rhoai3.admission-receipt/v2"
ADMITTED = "ADMITTED"
INCONCLUSIVE = "INCONCLUSIVE"
COMPAT_FAIL = "COMPAT_FAIL"
ARTIFACT_SCHEMAS = {"evidence-bundle": "evidence-bundle.schema.json", "worklist": "worklist.schema.json"}


def installed_skills(root: Path) -> set[str]:
    base = Path(root) / ".hermes" / "skills"
    return {p.parent.name for p in base.rglob("SKILL.md")}


def receipt_digest(receipt: dict[str, Any]) -> str:
    return digest({k: v for k, v in receipt.items() if k != "receipt_digest"})


def blocks_for(root: Path, bundle: dict[str, Any], worklist: dict[str, Any], decisions: dict[str, Any] | None, pins: dict[str, Any], bundle_digest: str) -> list[dict[str, str]]:
    """Every open fail-closed boundary as {class, subject, detail}."""
    out: list[dict[str, str]] = []

    def block(cls: str, subject: str, detail: str) -> None:
        out.append({"class": cls, "subject": subject, "detail": detail})

    if decisions is None:
        block("MISSING_DECISION", "decisions.yaml", "decisions.yaml missing or invalid (copy .hermes/planning/decisions.example.yaml)")
    else:
        for gap in missing_decisions(decisions, root):
            block(gap["class"], gap["subject"], gap["detail"])
    for g in activation_gaps(pins, bundle_digest):
        block("PLANNER_NOT_ACTIVATED" if "NOT_ACTIVATED" in g else "PLANNER_PILOT_SEAL", "pins.planner", g)
    for g in pin_gaps(pins, bundle.get("producers") or {}):
        block(g["class"], g["subject"], g["detail"])
    if not (bundle.get("structure") or {}).get("available"):
        block("STRUCTURE_MISSING", "jdk-model", "no admitted structural evidence (JDK-model producer status %s)" % ((bundle.get("producers") or {}).get("jdk-model") or {}).get("status", "missing"))
    mta = bundle.get("mta") or {}
    if str(mta.get("status")) != "ok":
        block("MTA_MISSING", "mta", "MTA producer status is %r" % mta.get("status"))
    else:
        if not mta.get("admissible"):
            block("MTA_PROVENANCE", "mta", "analysis was not produced by the pinned MTA CLI 8.2 artifact (%s); kantra is provisional" % (mta.get("provenance") or "unknown"))
        if not (mta.get("canary") or {}).get("fired"):
            block("CANARY_MISSING", "mta", "canary rule %r did not fire; the effective ruleset is unproven" % (mta.get("canary") or {}).get("rule_id"))
        inc = mta.get("incidents") or {}
        if inc.get("raw") != inc.get("normalized"):
            block("INCIDENTS_NOT_CONSERVED", "mta", "MTA reported %s incident(s); normalization carries %s" % (inc.get("raw"), inc.get("normalized")))
    if (bundle.get("structure") or {}).get("available") and not bundle.get("entry_points"):
        block("ZERO_ENTRY_POINTS", "entry-points", "no entry point found; an empty oracle set is not a silent success")
    bs = root / BOOTSTRAP_RECEIPT
    if not bs.is_file():
        block("BOOTSTRAP_MISSING", "bootstrap", "bootstrap-destination did not run; the destination tree has no deterministic baseline")
    else:
        b = load_json(bs)
        for bb in b.get("blocks") or []:
            block("BOOTSTRAP_BLOCKED", str(bb.get("subject")), str(bb.get("detail")))
        if str(b.get("status")) not in ("ok", "blocked") or str((b.get("inputs") or {}).get("evidence_bundle_sha256")) != bundle_digest:
            block("BOOTSTRAP_STALE", "bootstrap", "bootstrap receipt is %s / bound to bundle %s, current bundle %s" % (b.get("status"), str((b.get("inputs") or {}).get("evidence_bundle_sha256"))[:12], bundle_digest[:12]))
    m = worklist.get("measure") or {}
    if not m.get("known"):
        block("MEASURE_UNKNOWN", "worklist", "compile/tests/parity not all verified (run-verify.sh); the loop never advances on an unknown measure")
    if worklist.get("evidence_bundle_sha256") != bundle_digest:
        block("WORKLIST_STALE", "worklist", "work list was built from another bundle")
    # Pilot rule: the loop STOPS on a deferred (human-owned) cluster and on a
    # cluster with no derivable production scope; nothing mints until a human
    # clears it (decisions.not_applicable by ADR, or the fix lands by hand).
    for cid in worklist.get("deferred") or []:
        block("MANUAL_CLUSTER", cid, "cluster deferred after the attempt threshold; a human owns it (kanban_block kind=needs_input); the loop does not continue past it")
    for cid in worklist.get("blocked_clusters") or []:
        block("SCOPE_UNDERIVED", cid, "no production write scope can be derived for this cluster (tests are never writable); a human or ADR must own it")
    return out


def compose_receipt(root: Path) -> dict[str, Any]:
    root = Path(root)
    bundle = load_json(root / EVIDENCE_BUNDLE)
    worklist = load_json(root / WORKLIST)
    bundle_digest = digest(bundle)
    worklist_digest = digest(worklist)
    reasons: list[str] = []
    status = ADMITTED
    compat: list[str] = []
    for key, doc in (("evidence-bundle", bundle), ("worklist", worklist)):
        schema = load_schema(root / SCHEMAS_DIR / ARTIFACT_SCHEMAS[key])
        compat.extend("%s: %s" % (key, e) for e in validate(doc, schema))
    if compat:
        status = COMPAT_FAIL
        reasons.extend(compat)
    pins = load_pins(root)
    try:
        from planner.decisions import load_decisions

        decisions: dict[str, Any] | None = load_decisions(root)
    except ValueError:
        decisions = None
    blocks = blocks_for(root, bundle, worklist, decisions, pins, bundle_digest) if status != COMPAT_FAIL else []
    if blocks:
        status = INCONCLUSIVE
        reasons.extend("%s: %s" % (b["class"], b["detail"]) for b in blocks)
    decisions_path = root / DECISIONS
    bs = root / BOOTSTRAP_RECEIPT
    seals = {
        "evidence_bundle": bundle_digest,
        "worklist": worklist_digest,
        "bootstrap": sha256_file(bs) if bs.is_file() else "",
        "decisions_yaml": sha256_file(decisions_path) if decisions_path.is_file() else "",
        "contracts": {str(p.relative_to(root)): sha256_file(p) for p in contract_files(root)},
        "pins": digest(digestable_pins(pins)),
    }
    m = worklist.get("measure") or {}
    receipt = {
        "schema": SCHEMA,
        "status": status,
        "planning_only": str((bundle.get("build") or {}).get("outcome")) != "success",
        "reasons": reasons,
        "blocks": blocks,
        "seals": seals,
        "activation": activation_record(pins),
        "measure": m,
        "head": worklist.get("head") or "",
        "counts": {
            "items": len(worklist.get("items") or []),
            "clusters": len(worklist.get("clusters") or []),
            "open_clusters": sum(1 for c in (worklist.get("clusters") or []) if c.get("status") == "open"),
            "deferred": len(worklist.get("deferred") or []),
            "entry_points": len(bundle.get("entry_points") or []),
            "open_blocks": len(blocks),
        },
        "loop_complete": bool(m.get("known")) and not worklist.get("head") and not worklist.get("deferred") and not worklist.get("blocked_clusters") and all(v == 0 for v in (m.get("tuple") or [1])),
    }
    steps_p = root / LOOP_STEPS
    epoch = len((load_json(steps_p) or {}).get("rewinds") or []) if steps_p.is_file() else 0
    if epoch:
        # an Operator rewind (fix-until-green/scripts/rewind.py) re-seals the
        # same plan for a new epoch; the digest — and with it every K4 card
        # key — must differ from the rewound epoch's, or K4 hands back a card
        # that epoch already closed (pilot v6, 2026-09-10)
        receipt["loop_epoch"] = epoch
    receipt["receipt_digest"] = receipt_digest(receipt)
    return receipt


def verify_receipt(root: Path, *, require_admitted: bool = True) -> tuple[dict[str, Any] | None, list[str]]:
    """Prove the receipt on disk still seals what is on disk."""
    root = Path(root)
    gaps: list[str] = []
    path = root / ADMISSION_RECEIPT
    if not path.is_file():
        return None, ["missing %s" % ADMISSION_RECEIPT]
    receipt = load_json(path)
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        return None, ["%s: not a v2 admission receipt" % ADMISSION_RECEIPT]
    if receipt.get("receipt_digest") != receipt_digest(receipt):
        gaps.append("receipt_digest does not match the receipt body")
    seals = receipt.get("seals") or {}
    for key, rel, seal_key in (("evidence-bundle", EVIDENCE_BUNDLE, "evidence_bundle"), ("worklist", WORKLIST, "worklist")):
        p = root / rel
        if not p.is_file():
            gaps.append("missing %s" % rel)
            continue
        got = digest(load_json(p))
        if got != seals.get(seal_key):
            gaps.append("%s digest %s != sealed %s" % (key, got[:12], str(seals.get(seal_key))[:12]))
    bs = root / BOOTSTRAP_RECEIPT
    if (sha256_file(bs) if bs.is_file() else "") != seals.get("bootstrap", ""):
        gaps.append("bootstrap receipt changed after admission")
    dec = root / DECISIONS
    if dec.is_file():
        if sha256_file(dec) != seals.get("decisions_yaml"):
            gaps.append("decisions.yaml changed after admission")
    elif seals.get("decisions_yaml"):
        gaps.append("decisions.yaml missing")
    for rel, sha in sorted((seals.get("contracts") or {}).items()):
        p = root / rel
        if not p.is_file() or sha256_file(p) != sha:
            gaps.append("contract %s changed after admission" % rel)
    pins = load_pins(root)
    if digest(digestable_pins(pins)) != seals.get("pins"):
        gaps.append("tool pins changed after admission")
    if require_admitted:
        if receipt.get("status") != ADMITTED:
            gaps.append("receipt status is %s, not ADMITTED" % receipt.get("status"))
        gaps.extend(activation_gaps(pins, str(seals.get("evidence_bundle") or "")))
        bp = root / EVIDENCE_BUNDLE
        if bp.is_file():
            gaps.extend("%s: %s" % (g["class"], g["detail"]) for g in pin_gaps(pins, (load_json(bp) or {}).get("producers") or {}))
    return receipt, gaps


def artifact_digests_on_disk(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, rel in (("evidence-bundle", EVIDENCE_BUNDLE), ("worklist", WORKLIST)):
        p = Path(root) / rel
        if p.is_file():
            out[key] = digest(load_json(p))
    return out
