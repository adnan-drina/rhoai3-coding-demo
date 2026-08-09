#!/usr/bin/env python3
"""M2 domain gate: findings-handoff.json consumer contract (Architect E-20260809T072752Z)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "rhoai3.findings-handoff/v1"
HANDOFF_MAX_BYTES = 65536
FORBIDDEN_KEYS = {"codesnip", "code_snip", "raw", "analysis.log", "output.json"}


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


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    handoff_p = root / "migration" / "findings-handoff.json"
    evidence_p = root / "migration" / "mta-findings.json"

    if not handoff_p.is_file():
        print("FAIL: missing migration/findings-handoff.json (typed blocked)", file=sys.stderr)
        return 1
    if not evidence_p.is_file():
        print("FAIL: missing migration/mta-findings.json evidence store", file=sys.stderr)
        return 1

    raw = handoff_p.read_bytes()
    if len(raw) > HANDOFF_MAX_BYTES:
        print(f"FAIL: handoff size {len(raw)} > {HANDOFF_MAX_BYTES}", file=sys.stderr)
        return 1
    evid_size = evidence_p.stat().st_size
    if evid_size > 0 and len(raw) / evid_size >= 0.25:
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

    if not handoff.get("ack_obligation"):
        print("FAIL: ack_obligation missing", file=sys.stderr)
        return 1

    print(
        f"OK: findings-handoff gate ({len(raw)}B, {len(rules)} rules, digest={digest[:12]}…)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
