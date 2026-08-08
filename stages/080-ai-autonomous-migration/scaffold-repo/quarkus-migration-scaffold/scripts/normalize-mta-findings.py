#!/usr/bin/env python3
"""Wrap raw --json-output into the preserved mta-findings envelope.

If the file already has our schema, validate-only path is a no-op rewrite.
Raw Konveyor JSON is typically { violations: { ruleID: {…}}} or a list —
we normalize to the envelope in migration/schemas/mta-findings.md.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "migration/mta-findings.json")
    meta_cli = sys.argv[2] if len(sys.argv) > 2 else "unknown"
    rule_set = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else []
    input_digest = sys.argv[4] if len(sys.argv) > 4 else ""

    if not path.is_file():
        print(f"normalize-mta-findings: missing {path}", file=sys.stderr)
        return 2
    raw = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(raw, dict) and raw.get("schema") == "rhoai3.mta-findings/v1-provisional":
        print(f"OK: already normalized {path}")
        return 0

    violations = {}
    if isinstance(raw, dict) and isinstance(raw.get("violations"), dict):
        violations = raw["violations"]
    elif isinstance(raw, list):
        # unlikely list-of-rules shape
        for item in raw:
            if isinstance(item, dict) and item.get("ruleID"):
                violations[item["ruleID"]] = item
    elif isinstance(raw, dict):
        # some exports nest under analysis/output
        for key in ("violations", "rules", "output"):
            if isinstance(raw.get(key), dict) and raw[key]:
                # if values look like violations
                sample = next(iter(raw[key].values()), None)
                if isinstance(sample, dict) and (
                    "incidents" in sample or "category" in sample or "ruleID" in sample
                ):
                    violations = raw[key]
                    break

    # Ensure ruleID on each violation; preserve codeSnip (AD-003 / W2 §11.5).
    for rid, v in list(violations.items()):
        if not isinstance(v, dict):
            continue
        v.setdefault("ruleID", rid)
        incidents = v.get("incidents") or []
        if not isinstance(incidents, list):
            incidents = []
        for inc in incidents:
            if isinstance(inc, dict) and not inc.get("codeSnip"):
                inc["codeSnip"] = "(absent-from-tool)"
        v["incidents"] = incidents

    out = {
        "schema": "rhoai3.mta-findings/v1-provisional",
        "normalized_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "execution_evidence": {
            "analyzer_ran": True,
            "cli": meta_cli,
            "rule_set": rule_set,
            "input_digest": input_digest,
        },
        "violations": violations,
        "raw_tool_keys": sorted(raw.keys()) if isinstance(raw, dict) else [],
    }
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"OK: normalized {path} ({len(violations)} violation rules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
