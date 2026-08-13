#!/usr/bin/env python3
"""M2 domain gate: findings-handoff.json (Architect E-20260809T072752Z + §16.7).

Exit semantics (Deputy E-20260811T113300Z — contract, not judgment):
  0 = pass
  1 = FAIL → typed BLOCK (product/gate residue)
  2 = missing script / unusable harness path (lint defect — do not invent)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "rhoai3.findings-handoff/v1"
HANDOFF_MAX_BYTES = 65536
FORBIDDEN_KEYS = {"codesnip", "code_snip", "raw", "analysis.log", "output.json"}
DISPOSITIONS = frozenset({"apply", "false_positive", "needs_review", "opaque_exception"})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_forbidden(obj, path="$") -> list[str]:
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in FORBIDDEN_KEYS or "codesnip" in lk:
                hits.append(f"{path}.{k}")
            hits.extend(walk_forbidden(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(walk_forbidden(v, f"{path}[{i}]"))
    return hits


def ep_key(ep: dict) -> str:
    f = str(ep.get("file") or ep.get("path") or "")
    line = ep.get("line")
    return f"{f}:{line}" if line is not None else f


def check_partition_conservation(root: Path, inv: dict) -> int:
    """AR-4.1 — if story partition present, union must equal inventory endpoints."""
    part_p = root / "evidence" / "story-endpoint-partition.json"
    if not part_p.is_file():
        return 0
    part = json.loads(part_p.read_text(encoding="utf-8"))
    stories = part.get("stories") if isinstance(part, dict) else None
    if not isinstance(stories, dict):
        print("FAIL: AR-4.1 story-endpoint-partition.stories missing", file=sys.stderr)
        return 1
    inv_eps = {ep_key(e) for e in (inv.get("entry_points") or []) if isinstance(e, dict)}
    union: set[str] = set()
    dup = 0
    for sid, eps in stories.items():
        if not isinstance(eps, list):
            print(f"FAIL: AR-4.1 stories[{sid}] not a list", file=sys.stderr)
            return 1
        for ep in eps:
            if isinstance(ep, str):
                k = ep
            elif isinstance(ep, dict):
                k = ep_key(ep)
            else:
                continue
            if k in union:
                dup += 1
            union.add(k)
    if union != inv_eps:
        missing = sorted(inv_eps - union)[:8]
        extra = sorted(union - inv_eps)[:8]
        print(
            f"FAIL: AR-4.1 partition conservation "
            f"(union={len(union)} inventory={len(inv_eps)} "
            f"missing_sample={missing} extra_sample={extra})",
            file=sys.stderr,
        )
        return 1
    if dup:
        print(f"FAIL: AR-4.1 partition has {dup} duplicate endpoint assignment(s)", file=sys.stderr)
        return 1
    print(f"OK: AR-4.1 partition conservation ({len(union)} endpoints)")
    return 0


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    handoff_p = root / "evidence" / "findings-handoff.json"
    evidence_p = root / "evidence" / "mta-findings.json"
    inventory_p = root / "evidence" / "entry-point-inventory.json"

    if not handoff_p.is_file():
        print("FAIL: missing evidence/findings-handoff.json (typed blocked)", file=sys.stderr)
        return 1
    if not evidence_p.is_file():
        print("FAIL: missing evidence/mta-findings.json evidence store", file=sys.stderr)
        return 1
    if not inventory_p.is_file():
        print("FAIL: AR-4.1 missing evidence/entry-point-inventory.json", file=sys.stderr)
        return 1

    raw = handoff_p.read_bytes()
    if len(raw) > HANDOFF_MAX_BYTES:
        print(f"FAIL: handoff size {len(raw)} > {HANDOFF_MAX_BYTES}", file=sys.stderr)
        return 1
    evid_size = evidence_p.stat().st_size
    if evid_size >= 8192 and len(raw) / evid_size >= 0.25:
        print(
            f"FAIL: handoff/evidence ratio {len(raw)}/{evid_size} >= 0.25",
            file=sys.stderr,
        )
        return 1

    handoff = json.loads(raw.decode("utf-8"))
    if handoff.get("schema") != SCHEMA:
        print(f"FAIL: schema want {SCHEMA} got {handoff.get('schema')}", file=sys.stderr)
        return 1

    hits = walk_forbidden(handoff)
    if hits:
        print(f"FAIL: forbidden fields in handoff: {hits[:8]}", file=sys.stderr)
        return 1

    ev = handoff.get("evidence") or {}
    if not isinstance(ev, dict) or not ev.get("path") or not ev.get("sha256"):
        print("FAIL: evidence.path/sha256 required", file=sys.stderr)
        return 1
    digest = sha256_file(evidence_p)
    if digest != ev.get("sha256"):
        print(
            f"FAIL: BODY_REF_DIGEST evidence sha256 mismatch (file={digest} handoff={ev.get('sha256')})",
            file=sys.stderr,
        )
        return 1

    # AR-4.1 inventory digest
    inv_h = handoff.get("inventory")
    if not isinstance(inv_h, dict) or not inv_h.get("path") or not inv_h.get("sha256"):
        print("FAIL: AR-4.1 handoff.inventory.path/sha256 required", file=sys.stderr)
        return 1
    inv_digest = sha256_file(inventory_p)
    if inv_digest != inv_h.get("sha256"):
        print(
            f"FAIL: AR-4.1 inventory sha256 mismatch "
            f"(file={inv_digest} handoff={inv_h.get('sha256')})",
            file=sys.stderr,
        )
        return 1
    inv = json.loads(inventory_p.read_text(encoding="utf-8"))
    inv_count = int((inv.get("counts") or {}).get("total") or len(inv.get("entry_points") or []))
    stamped = inv_h.get("endpoint_count")
    if stamped is not None and int(stamped) != inv_count:
        print(
            f"FAIL: AR-4.1 inventory.endpoint_count {stamped} != inventory total {inv_count}",
            file=sys.stderr,
        )
        return 1

    evidence = json.loads(evidence_p.read_text(encoding="utf-8"))
    viol = evidence.get("violations") if isinstance(evidence, dict) else None
    if not isinstance(viol, dict):
        print("FAIL: evidence store has no violations{}", file=sys.stderr)
        return 1
    evid_ids = {str(v.get("ruleID") or rid) for rid, v in viol.items() if isinstance(v, dict)}
    rules = handoff.get("rules")
    if not isinstance(rules, list) or not rules:
        print("FAIL: handoff.rules empty", file=sys.stderr)
        return 1
    for r in rules:
        rid = str(r.get("rule_id") or "")
        if rid not in evid_ids:
            print(f"FAIL: handoff rule_id {rid!r} not in evidence store", file=sys.stderr)
            return 1
        # AR-4.2 semantics
        desc = r.get("description")
        disp = r.get("disposition")
        if not isinstance(desc, str) or not desc.strip():
            print(f"FAIL: AR-4.2 rule {rid!r} missing description", file=sys.stderr)
            return 1
        if disp not in DISPOSITIONS:
            print(
                f"FAIL: AR-4.2 rule {rid!r} disposition {disp!r} not in {sorted(DISPOSITIONS)}",
                file=sys.stderr,
            )
            return 1
        if desc.startswith("opaque:") and disp not in {"opaque_exception", "needs_review"}:
            print(
                f"FAIL: AR-4.2 opaque rule {rid!r} must use opaque_exception/needs_review "
                f"(got {disp!r}) — no planner invention",
                file=sys.stderr,
            )
            return 1

    if not handoff.get("ack_obligation"):
        print("FAIL: ack_obligation missing", file=sys.stderr)
        return 1

    if check_partition_conservation(root, inv):
        return 1

    print(
        f"OK: findings-handoff gate ({len(raw)}B, {len(rules)} rules, "
        f"inventory={inv_count}, digest={digest[:12]}…)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
