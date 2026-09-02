#!/usr/bin/env python3
"""Wrap raw --json-output into the preserved mta-findings envelope.

If the file already has our schema, validate-only path is a no-op rewrite.
Raw Konveyor JSON is typically a list of RuleSet objects (violations /
unmatched / skipped / errors) or { violations: { ruleID: {…}}} —
we normalize to the envelope in governance/schemas/mta-findings.md.

WC-2: keep unmatched / skipped / errors. They are written to
rules-coverage.json (sidecar) plus envelope.rules_coverage.totals.
The static HTML report path is recorded when present (we do not pass
--skip-static-report).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _id_list(val) -> list[str]:
    if isinstance(val, list):
        out: list[str] = []
        for x in val:
            if isinstance(x, str) and x:
                out.append(x)
            elif isinstance(x, dict):
                rid = x.get("ruleID") or x.get("rule") or x.get("id")
                if rid:
                    out.append(str(rid))
        return out
    if isinstance(val, dict):
        return [str(k) for k in val if k]
    return []


def _error_map(val) -> dict[str, str]:
    if isinstance(val, dict):
        return {str(k): str(v) for k, v in val.items() if k}
    if isinstance(val, list):
        return {str(x): "" for x in val if x}
    return {}


def _raw_tool_keys(raw) -> list[str]:
    if isinstance(raw, dict):
        return sorted(raw.keys())
    if isinstance(raw, list):
        keys: set[str] = set()
        for item in raw:
            if isinstance(item, dict):
                keys.update(item.keys())
        return ["rulesets-list"] + sorted(keys)
    return []


def _collect_ruleset_coverage(item: dict) -> dict:
    viol = item.get("violations") if isinstance(item.get("violations"), dict) else {}
    return {
        "name": str(item.get("name") or ""),
        "fired": sorted(str(k) for k in viol.keys() if k),
        "unmatched": _id_list(item.get("unmatched")),
        "skipped": _id_list(item.get("skipped")),
        "errors": _error_map(item.get("errors")),
    }


def _coverage_from_raw(raw) -> list[dict]:
    if isinstance(raw, list):
        return [_collect_ruleset_coverage(item) for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        # Single RuleSet-shaped object, or a violations-only export.
        if any(k in raw for k in ("unmatched", "skipped", "errors", "name")):
            return [_collect_ruleset_coverage(raw)]
        viol = raw.get("violations") if isinstance(raw.get("violations"), dict) else {}
        if viol:
            return [
                {
                    "name": str(raw.get("name") or ""),
                    "fired": sorted(str(k) for k in viol.keys() if k),
                    "unmatched": _id_list(raw.get("unmatched")),
                    "skipped": _id_list(raw.get("skipped")),
                    "errors": _error_map(raw.get("errors")),
                }
            ]
    return []


def _totals(rulesets: list[dict]) -> dict:
    fired: set[str] = set()
    unmatched: set[str] = set()
    skipped: set[str] = set()
    errors: set[str] = set()
    for rs in rulesets:
        fired.update(rs.get("fired") or [])
        unmatched.update(rs.get("unmatched") or [])
        skipped.update(rs.get("skipped") or [])
        errors.update((rs.get("errors") or {}).keys())
    return {
        "rulesets": len(rulesets),
        "fired": len(fired),
        "unmatched": len(unmatched),
        "skipped": len(skipped),
        "errors": len(errors),
    }


def _default_coverage_path(findings: Path) -> Path:
    if findings.name == "mta-findings.json":
        return findings.parent / "mta" / "rules-coverage.json"
    return findings.with_name("rules-coverage.json")


def _default_static_report(findings: Path) -> Path:
    if findings.name == "mta-findings.json":
        return findings.parent / "mta" / "static-report" / "index.html"
    return findings.parent / "static-report" / "index.html"


def _merge_violations(raw) -> dict:
    violations: dict = {}
    if isinstance(raw, dict) and isinstance(raw.get("violations"), dict):
        violations = dict(raw["violations"])
        return violations
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            nested = item.get("violations")
            if isinstance(nested, dict) and nested:
                for rid, v in nested.items():
                    if not isinstance(v, dict):
                        continue
                    if rid in violations and isinstance(violations[rid].get("incidents"), list):
                        extras = v.get("incidents") or []
                        if isinstance(extras, list):
                            violations[rid]["incidents"].extend(extras)
                    else:
                        violations[rid] = v
            elif item.get("ruleID"):
                violations[item["ruleID"]] = item
        return violations
    if isinstance(raw, dict):
        for key in ("violations", "rules", "output"):
            if isinstance(raw.get(key), dict) and raw[key]:
                sample = next(iter(raw[key].values()), None)
                if isinstance(sample, dict) and (
                    "incidents" in sample or "category" in sample or "ruleID" in sample
                ):
                    return dict(raw[key])
    return violations


def _preserve_incidents(violations: dict) -> None:
    for rid, v in list(violations.items()):
        if not isinstance(v, dict):
            continue
        v.setdefault("ruleID", rid)
        incidents = v.get("incidents") or []
        if not isinstance(incidents, list):
            incidents = []
        for inc in incidents:
            if isinstance(inc, dict):
                if not inc.get("codeSnip"):
                    inc["codeSnip"] = "(absent-from-tool)"
                if inc.get("lineNumber") in (None, ""):
                    inc["lineNumber"] = 0
                if not inc.get("uri"):
                    inc["uri"] = "(absent-from-tool)"
                if not inc.get("message"):
                    inc["message"] = "(absent-from-tool)"
        v["incidents"] = incidents


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "evidence/mta-findings.json")
    meta_cli = sys.argv[2] if len(sys.argv) > 2 else "unknown"
    rule_set = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else []
    input_digest = sys.argv[4] if len(sys.argv) > 4 else ""
    coverage_arg = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else ""
    static_arg = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] else ""

    if not path.is_file():
        print(f"normalize-mta-findings: missing {path}", file=sys.stderr)
        return 2
    raw = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(raw, dict) and raw.get("schema") == "rhoai3.mta-findings/v1-provisional":
        print(f"OK: already normalized {path}")
        return 0

    violations = _merge_violations(raw)
    _preserve_incidents(violations)

    rulesets = _coverage_from_raw(raw)
    totals = _totals(rulesets)
    coverage_path = Path(coverage_arg) if coverage_arg else _default_coverage_path(path)
    static_path = Path(static_arg) if static_arg else _default_static_report(path)
    static_present = static_path.is_file()

    coverage_doc = {
        "schema": "rhoai3.mta-rules-coverage/v1",
        "normalized_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "totals": totals,
        "static_report": str(static_path) if static_present else None,
        "static_report_present": static_present,
        "rulesets": rulesets,
    }
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.write_text(json.dumps(coverage_doc, indent=2) + "\n", encoding="utf-8")

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
        "raw_tool_keys": _raw_tool_keys(raw),
        "rules_coverage": {
            "path": str(coverage_path),
            "totals": totals,
            "static_report": str(static_path) if static_present else None,
            "static_report_present": static_present,
        },
    }
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(
        f"OK: normalized {path} ({len(violations)} violation rules); "
        f"coverage {coverage_path} "
        f"fired={totals['fired']} unmatched={totals['unmatched']} "
        f"skipped={totals['skipped']} errors={totals['errors']} "
        f"static_report={'yes' if static_present else 'missing'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
