#!/usr/bin/env python3
"""Emit evidence/findings-handoff.json (rhoai3.findings-handoff/v1).

Seam artifact: identity + rule/locus index + digests. NO codeSnip / raw blobs.
Evidence store remains evidence/mta-findings.json.

AD-H §16.7 / AR-4.1: inventory digest REQUIRED (refuse emit without inventory).
AD-H §16.7 / AR-4.2: each rule carries bounded description + disposition.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.findings-handoff/v1"
HANDOFF_MAX_BYTES = 65536
DESC_MAX = 240
DISPOSITIONS = frozenset({"apply", "false_positive", "needs_review", "opaque_exception"})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def loci_from_incidents(incidents: list) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, int | None]] = set()
    for inc in incidents:
        if not isinstance(inc, dict):
            continue
        path = str(inc.get("uri") or inc.get("file") or inc.get("path") or "")
        if not path or path == "(absent-from-tool)":
            continue
        line = inc.get("lineNumber")
        if line in (None, ""):
            line_i: int | None = None
        else:
            try:
                line_i = int(line)
            except (TypeError, ValueError):
                line_i = None
        key = (path, line_i)
        if key in seen:
            continue
        seen.add(key)
        entry: dict = {"path": path}
        if line_i is not None:
            entry["line"] = line_i
        out.append(entry)
        if len(out) >= 40:
            break
    return out


def bounded_description(v: dict, rid: str) -> str:
    for key in ("description", "title", "message", "ruleDescription", "hint"):
        raw = v.get(key)
        if isinstance(raw, str) and raw.strip():
            text = " ".join(raw.split())
            if len(text) > DESC_MAX:
                text = text[: DESC_MAX - 1] + "…"
            # never carry snip-like payloads
            if "codeSnip" in text or "code_snip" in text:
                continue
            return text
    # Opaque ID without semantic text → typed exception disposition path
    return f"opaque:{rid}"


def disposition_of(v: dict, description: str) -> str:
    explicit = str(v.get("disposition") or "").strip().lower()
    if explicit in DISPOSITIONS:
        return explicit
    if description.startswith("opaque:"):
        return "opaque_exception"
    cat = str(v.get("category") or "").lower()
    if "false" in cat and "positive" in cat:
        return "false_positive"
    return "apply"


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    evidence = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "evidence" / "mta-findings.json"
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else root / "evidence" / "findings-handoff.json"
    inventory = root / "evidence" / "entry-point-inventory.json"

    if not evidence.is_file():
        print(f"emit-findings-handoff: missing evidence {evidence}", file=sys.stderr)
        return 2
    # AR-4.1 — inventory before handoff or force re-emit
    if not inventory.is_file():
        print(
            "emit-findings-handoff: AR-4.1 missing evidence/entry-point-inventory.json "
            "— run inventory-entry-points before emit (refuse)",
            file=sys.stderr,
        )
        return 2

    doc = json.loads(evidence.read_text(encoding="utf-8"))
    violations = doc.get("violations") if isinstance(doc, dict) else None
    if not isinstance(violations, dict):
        print("emit-findings-handoff: evidence lacks violations{}", file=sys.stderr)
        return 2

    inv = json.loads(inventory.read_text(encoding="utf-8"))
    inv_count = int((inv.get("counts") or {}).get("total") or len(inv.get("entry_points") or []))

    rules = []
    by_category: dict[str, int] = {}
    for rid, v in sorted(violations.items(), key=lambda kv: str(kv[0])):
        if not isinstance(v, dict):
            continue
        incidents = v.get("incidents") if isinstance(v.get("incidents"), list) else []
        cat = str(v.get("category") or "uncategorized")
        by_category[cat] = by_category.get(cat, 0) + 1
        desc = bounded_description(v, str(v.get("ruleID") or rid))
        rule = {
            "rule_id": str(v.get("ruleID") or rid),
            "category": cat,
            "incident_count": len(incidents),
            "loci": loci_from_incidents(incidents),
            "description": desc,
            "disposition": disposition_of(v, desc),
        }
        effort = v.get("effort")
        if effort is not None and effort != "":
            rule["effort"] = effort
        blob = json.dumps(rule)
        if "codeSnip" in blob or "code_snip" in blob:
            print("emit-findings-handoff: internal error — snip leaked", file=sys.stderr)
            return 3
        rules.append(rule)

    try:
        evid_rel = str(evidence.relative_to(root))
    except ValueError:
        evid_rel = str(evidence)

    handoff = {
        "schema": SCHEMA,
        "emitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence": {
            "path": evid_rel,
            "sha256": sha256_file(evidence),
        },
        "inventory": {
            "path": str(inventory.relative_to(root)),
            "sha256": sha256_file(inventory),
            "endpoint_count": inv_count,
        },
        "rules": rules,
        "totals": {
            "violations": len(rules),
            "by_category": by_category,
            "inventory_endpoints": inv_count,
        },
        "ack_obligation": (
            "M2 PLAN must partition from findings-handoff.json rules/loci + inventory digests; "
            "must not load mta-findings.json codeSnip/raw exhaust into the planner context. "
            "Selective evidence reads allowed only by locus path after digest check. "
            "Opaque rule IDs require disposition=opaque_exception or consistent re-classify — "
            "never invent semantics (AR-4.2)."
        ),
    }

    raw = json.dumps(handoff, indent=2) + "\n"
    if len(raw.encode("utf-8")) > HANDOFF_MAX_BYTES:
        for r in handoff["rules"]:
            r["loci"] = r["loci"][:5]
        raw = json.dumps(handoff, indent=2) + "\n"
    if len(raw.encode("utf-8")) > HANDOFF_MAX_BYTES:
        for r in handoff["rules"]:
            r["loci"] = []
        raw = json.dumps(handoff, indent=2) + "\n"
    size = len(raw.encode("utf-8"))
    if size > HANDOFF_MAX_BYTES:
        print(
            f"emit-findings-handoff: handoff {size}B exceeds cap {HANDOFF_MAX_BYTES}",
            file=sys.stderr,
        )
        return 4

    evid_size = evidence.stat().st_size
    # Ratio lint targets snip-bloated evidence stores; skip tiny fixtures (<8KiB).
    if evid_size >= 8192 and size / evid_size >= 0.25:
        print(
            f"emit-findings-handoff: ratio {size}/{evid_size} >= 0.25 (fail lint)",
            file=sys.stderr,
        )
        return 5

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(raw, encoding="utf-8")
    print(
        f"OK: findings-handoff → {out} ({size}B, {len(rules)} rules, "
        f"inventory_endpoints={inv_count})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
