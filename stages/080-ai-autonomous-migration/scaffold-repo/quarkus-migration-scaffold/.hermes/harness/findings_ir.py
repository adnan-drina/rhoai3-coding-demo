#!/usr/bin/env python3
"""ADR-24 Findings Control Plane — single Kantra → IR loader (O-ADR24FIND).

Canonical artifact: migration/findings.json

Kantra live shape (ruleset list):
  [ {name, skipped…}, {name, violations: {ruleId: {incidents:[{uri,lineNumber,…}]}}} ]

Only this module may parse that nesting for identity. findings-inventory.md and
model.json findings[] are views / consumers of the IR — never a second walk.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

IR_REL = Path("migration/findings.json")
KANTRA_REL = Path("migration/mta-findings.json")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def uri_to_legacy_path(uri: str) -> str:
    """Normalize Kantra incident uri → repo-relative legacy path (no basename)."""
    u = (uri or "").strip()
    if not u or u == "?":
        return ""
    u = u.replace("file://", "")
    # file:///projects/legacy/src/... or /projects/legacy/src/...
    for marker in (
        "/projects/legacy/",
        "/projects/modernized/",
        "projects/legacy/",
        "projects/modernized/",
    ):
        if marker in u:
            u = u.split(marker, 1)[1]
            break
    u = u.lstrip("/")
    if u.startswith("src/") or u in ("pom.xml",) or u.startswith("src/"):
        return u
    # already relative under legacy root
    if "/src/" in u:
        return u[u.index("src/") :]
    return u


def infer_kind(legacy_path: str) -> str:
    p = legacy_path or ""
    if p.endswith(".java"):
        return "java"
    if p.endswith("pom.xml") or p == "pom.xml":
        return "pom"
    if p.endswith((".properties", ".yml", ".yaml", ".xml")):
        return "resources"
    if p:
        return "resources"
    return "unknown"


def load_kantra(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def iter_violation_rules(data: Any) -> list[tuple[str, dict]]:
    """Yield (rule_id, violation_dict) from live Kantra ruleset list or flat shapes."""
    rules: list[tuple[str, dict]] = []
    if isinstance(data, list):
        for rs in data:
            if not isinstance(rs, dict):
                continue
            viol = rs.get("violations") or {}
            if isinstance(viol, dict):
                for rid, v in viol.items():
                    if isinstance(v, dict):
                        rules.append((str(rid), v))
        return rules
    if isinstance(data, dict):
        viol = data.get("violations") or data.get("issues") or {}
        if isinstance(viol, dict):
            for rid, v in viol.items():
                if isinstance(v, dict):
                    rules.append((str(rid), v))
    return rules


def build_ir(
    kantra_path: Path,
    *,
    data: Any = None,
) -> dict[str, Any]:
    """Build typed findings IR from Kantra JSON bytes/path."""
    raw = kantra_path.read_bytes() if kantra_path.is_file() else b""
    if data is None:
        if not raw:
            data = []
        else:
            data = json.loads(raw.decode("utf-8", errors="replace"))
    source_sha = sha256_bytes(raw) if raw else ""
    rules_out: list[dict[str, Any]] = []
    n_incidents = 0
    for rid, v in sorted(iter_violation_rules(data), key=lambda x: x[0]):
        incs_out: list[dict[str, Any]] = []
        for inc in v.get("incidents") or []:
            if not isinstance(inc, dict):
                continue
            uri = str(inc.get("uri") or "")
            lp = uri_to_legacy_path(uri)
            incs_out.append(
                {
                    "uri": uri,
                    "legacy_path": lp,
                    "line": inc.get("lineNumber"),
                    "message": (inc.get("message") or "")[:400],
                }
            )
            n_incidents += 1
        kinds = {infer_kind(i["legacy_path"]) for i in incs_out if i.get("legacy_path")}
        kind = "java" if "java" in kinds else (next(iter(kinds)) if kinds else "unknown")
        rules_out.append(
            {
                "id": rid,
                "kind": kind,
                "category": v.get("category") or "mandatory",
                "description": (v.get("description") or "").strip(),
                "effort": v.get("effort"),
                "incidents": incs_out,
            }
        )
    ir = {
        "schema": "adr24-findings-ir/v1",
        "provenance": {
            "source_path": str(KANTRA_REL),
            "source_sha256": source_sha,
            "producer": "findings_ir",
            "generated_at": _utc(),
            "ruleset_rows": len(data) if isinstance(data, list) else 1,
            "active_rulesets": sum(
                1
                for rs in (data if isinstance(data, list) else [data])
                if isinstance(rs, dict) and (rs.get("violations") or {})
            ),
        },
        "rules": rules_out,
        "stats": {
            "rule_count": len(rules_out),
            "incident_count": n_incidents,
        },
    }
    ir["provenance"]["ir_sha256"] = sha256_bytes(
        json.dumps(
            {"rules": rules_out, "stats": ir["stats"]},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return ir


def save_ir(root: Path, ir: dict[str, Any]) -> Path:
    path = root / IR_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ir, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return path


def load_ir(root: Path) -> dict[str, Any]:
    path = root / IR_REL
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_ir(root: Path, kantra_path: Optional[Path] = None) -> dict[str, Any]:
    """Load IR if present and source hash matches; else rebuild from Kantra."""
    kantra = kantra_path or (root / KANTRA_REL)
    ir_path = root / IR_REL
    if ir_path.is_file() and kantra.is_file():
        try:
            ir = load_ir(root)
            src = (ir.get("provenance") or {}).get("source_sha256") or ""
            if src and src == sha256_file(kantra):
                return ir
        except (json.JSONDecodeError, OSError):
            pass
    if not kantra.is_file():
        ir = {
            "schema": "adr24-findings-ir/v1",
            "provenance": {
                "source_path": str(KANTRA_REL),
                "source_sha256": "",
                "producer": "findings_ir",
                "generated_at": _utc(),
                "ir_sha256": "",
                "ruleset_rows": 0,
                "active_rulesets": 0,
            },
            "rules": [],
            "stats": {"rule_count": 0, "incident_count": 0},
        }
        save_ir(root, ir)
        return ir
    ir = build_ir(kantra)
    save_ir(root, ir)
    return ir


def path_exact_match(incident_path: str, unit_legacy_path: str) -> bool:
    """Identity join: exact relative path only (F-basename / O-ADR24BASENAME)."""
    a = (incident_path or "").strip().lstrip("./")
    b = (unit_legacy_path or "").strip().lstrip("./")
    if not a or not b:
        return False
    return a == b


def bind_findings_to_units(
    ir: dict[str, Any], units: list[dict]
) -> tuple[list[dict], list[dict], list[str]]:
    """Attach finding ids to units by exact legacy_path.

    Returns (findings_index, units_with_findings_field_updated, unbound_paths).
    """
    by_legacy: dict[str, list[str]] = {}
    for u in units:
        lp = (u.get("legacy_path") or "").strip().lstrip("./")
        if lp:
            by_legacy.setdefault(lp, []).append(u["key"])

    finding_index: dict[str, dict] = {}
    unit_findings: dict[str, list[str]] = {u["key"]: [] for u in units}
    unbound: list[str] = []

    for rule in ir.get("rules") or []:
        rid = rule["id"]
        bound_keys: set[str] = set()
        for inc in rule.get("incidents") or []:
            lp = (inc.get("legacy_path") or "").strip().lstrip("./")
            if not lp:
                unbound.append(f"{rid}:<empty-path>")
                continue
            keys = by_legacy.get(lp) or []
            if not keys:
                unbound.append(f"{rid}:{lp}")
                continue
            for k in keys:
                bound_keys.add(k)
                if rid not in unit_findings[k]:
                    unit_findings[k].append(rid)
        finding_index[rid] = {
            "id": rid,
            "kind": rule.get("kind") or "java",
            "category": rule.get("category"),
            "units": sorted(bound_keys),
            "incident_count": len(rule.get("incidents") or []),
            "evidence_ref": f"findings.json#{rid}",
        }

    for u in units:
        u["findings"] = sorted(unit_findings.get(u["key"]) or [])

    findings = sorted(finding_index.values(), key=lambda r: r["id"])
    return findings, units, sorted(set(unbound))


def lint_bind_closed(ir: dict[str, Any], findings: list[dict]) -> list[str]:
    """F-bind: IR incidents > 0 ⇒ model findings > 0."""
    n_inc = int((ir.get("stats") or {}).get("incident_count") or 0)
    if n_inc > 0 and not findings:
        return [
            f"O-ADR24FINDBIND RED: IR has {n_inc} incidents but model.findings is empty"
        ]
    return []


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="ADR-24 findings IR")
    ap.add_argument("--root", default=".")
    ap.add_argument("--kantra", default="")
    ap.add_argument("cmd", choices=["emit", "show"])
    args = ap.parse_args()
    root = Path(args.root).resolve()
    kantra = Path(args.kantra) if args.kantra else root / KANTRA_REL
    if args.cmd == "emit":
        ir = build_ir(kantra)
        save_ir(root, ir)
        print(
            f"O-ADR24FIND IR: rules={ir['stats']['rule_count']} "
            f"incidents={ir['stats']['incident_count']} → {IR_REL}"
        )
        return 0
    ir = ensure_ir(root, kantra)
    print(json.dumps(ir["stats"], indent=2))
    print("source", (ir.get("provenance") or {}).get("source_sha256", "")[:16])
    print("ir", (ir.get("provenance") or {}).get("ir_sha256", "")[:16])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
