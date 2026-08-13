#!/usr/bin/env python3
"""Specimen-agnostic helpers for migration gates (Operator E-20260811T150800Z).

Falsifier: coolstore must work unchanged. Specimen literals belong in
fixtures / per-run migration.yaml stamps — never in gate logic constants.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

def _parse_migration_yaml_lite(text: str) -> dict:
    """Minimal migration.yaml reader (no PyYAML dep). Supports legacyBasePackage
    and path_rewrites list used by portability stamps."""
    out: dict = {"migration": {}}
    mig = out["migration"]
    lines = text.splitlines()
    i = 0
    in_migration = False
    in_rewrites = False
    current: dict | None = None
    while i < len(lines):
        ln = lines[i]
        raw = ln.rstrip()
        if not raw.strip() or raw.strip().startswith("#"):
            i += 1
            continue
        if raw == "migration:":
            in_migration = True
            in_rewrites = False
            i += 1
            continue
        if in_migration and raw and not raw.startswith(" ") and not raw.startswith("	"):
            # left migration section
            in_migration = False
            in_rewrites = False
            continue
        if not in_migration:
            i += 1
            continue
        s = raw.strip()
        if s.startswith("legacyBasePackage:"):
            mig["legacyBasePackage"] = s.split(":", 1)[1].strip().strip('"').strip("'")
            in_rewrites = False
        elif s.startswith("legacy_base_package:"):
            mig["legacy_base_package"] = s.split(":", 1)[1].strip().strip('"').strip("'")
            in_rewrites = False
        elif s.startswith("legacyPackage:"):
            # RHDH app-migration skeleton stamp key (alias of legacyBasePackage)
            mig["legacyPackage"] = s.split(":", 1)[1].strip().strip('"').strip("'")
            in_rewrites = False
        elif s.startswith("path_rewrites:") or s.startswith("packageRemap:"):
            key = "path_rewrites" if s.startswith("path_rewrites") else "packageRemap"
            mig[key] = []
            in_rewrites = True
            current = None
        elif in_rewrites and s.startswith("- "):
            current = {}
            mig.setdefault("path_rewrites", mig.get("packageRemap") or [])
            # normalize to path_rewrites
            if "path_rewrites" not in mig:
                mig["path_rewrites"] = []
            if "packageRemap" in mig and mig["packageRemap"] is not mig.get("path_rewrites"):
                mig["path_rewrites"] = mig["packageRemap"]
            mig["path_rewrites"].append(current)
            rest = s[2:].strip()
            if rest and ":" in rest:
                k, v = rest.split(":", 1)
                current[k.strip()] = v.strip().strip('"').strip("'")
        elif in_rewrites and current is not None and ":" in s and s[0] not in "-":
            k, v = s.split(":", 1)
            current[k.strip()] = v.strip().strip('"').strip("'")
        else:
            in_rewrites = False
        i += 1
    return out


def load_json(path: Path) -> dict | list | None:
    if not path.is_file():
        return None
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_migration_yaml(root: Path) -> dict[str, Any]:
    path = root / "migration.yaml"
    if not path.is_file():
        return {}
    try:
        return _parse_migration_yaml_lite(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def path_rewrites(root: Path) -> list[tuple[str, str]]:
    """Return (dest_prefix, legacy_prefix) pairs for norm_file remaps.

    Sources (first non-empty wins):
      1) migration.yaml migration.path_rewrites: [{from, to}, ...]
         where *from* is dest-tree prefix and *to* is legacy-tree prefix
      2) Discover from inventory HTTP files vs bodies dual-path (best-effort)
    """
    mig = load_migration_yaml(root).get("migration") or {}
    if isinstance(mig, dict):
        raw = mig.get("path_rewrites") or mig.get("packageRemap") or []
        out: list[tuple[str, str]] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                frm = str(item.get("from") or item.get("dest") or "").replace("\\", "/")
                to = str(item.get("to") or item.get("legacy") or "").replace("\\", "/")
                if frm and to:
                    out.append((frm.rstrip("/") + "/", to.rstrip("/") + "/"))
        if out:
            return out

    # Discover: inventory legacy java dirs vs modernized dest dirs in bodies
    inv = None
    for cand in (
        root / "evidence/entry-point-inventory.json",
        root / "governance/fixtures/inventory/entry-point-inventory-petclinic-f11.json",
    ):
        inv = load_json(cand)
        if isinstance(inv, dict):
            break
    legacy_pkgs: set[str] = set()
    if isinstance(inv, dict):
        for ep in inv.get("entry_points") or []:
            if not isinstance(ep, dict):
                continue
            f = str(ep.get("file") or "").replace("\\", "/")
            m = re.match(r"(src/(?:main|test)/java/.+)/[^/]+\.java$", f)
            if m:
                # package directory (drop class file); keep up to parent of class
                legacy_pkgs.add(m.group(1).rsplit("/", 1)[0] + "/")

    dest_pkgs: set[str] = set()
    bodies = root / "evidence/bodies"
    if bodies.is_dir():
        for path in bodies.glob("m3-*.json"):
            if path.name.endswith(".sha256.json"):
                continue
            data = load_json(path)
            if not isinstance(data, dict):
                continue
            for item in data.get("files_writable") or []:
                if not isinstance(item, str):
                    continue
                p = item.replace("\\", "/")
                if "/modernized/" in p:
                    p = p.split("/modernized/", 1)[1]
                m = re.match(r"(src/(?:main|test)/java/.+)/[^/]+\.java$", p)
                if m:
                    dest_pkgs.add(m.group(1).rsplit("/", 1)[0] + "/")

    # Pair by java/(main|test) + depth-1 package root swap when unique
    rewrites: list[tuple[str, str]] = []
    # Prefer remapping dest base → legacy base when both have single java root
    def java_roots(pkgs: set[str]) -> set[str]:
        roots: set[str] = set()
        for p in pkgs:
            m = re.match(r"(src/(?:main|test)/java/[^/]+(?:/[^/]+){0,3})/", p)
            if m:
                # take up to 3 segments after java/ as base package guess
                parts = m.group(1).split("/")
                # src/main/java/a/b/c → keep a/b/c if present
                if len(parts) >= 4:
                    roots.add("/".join(parts[: min(7, len(parts))]) + "/")
        return roots

    # Simpler: if exactly one dest root under com/ and one legacy under org/, pair them
    dest_bases = sorted(
        {re.sub(r"(src/(?:main|test)/java/)(.+?)/$", r"\1\2/", p) for p in dest_pkgs}
    )
    leg_bases = sorted(legacy_pkgs)
    # Collapse to package-root (strip trailing entity folder noise) — use
    # longest common prefix within each set
    def lcp(paths: list[str]) -> str:
        if not paths:
            return ""
        s1 = min(paths)
        s2 = max(paths)
        i = 0
        while i < len(s1) and i < len(s2) and s1[i] == s2[i]:
            i += 1
        # trim to last /
        pref = s1[:i]
        if "/" in pref:
            pref = pref[: pref.rfind("/") + 1]
        return pref

    droot = lcp(sorted(dest_pkgs))
    lroot = lcp(sorted(legacy_pkgs))
    if (
        droot.startswith("src/main/java/")
        and lroot.startswith("src/main/java/")
        and droot != lroot
    ):
        rewrites.append((droot, lroot))
        rewrites.append(
            (
                droot.replace("src/main/java/", "src/test/java/", 1),
                lroot.replace("src/main/java/", "src/test/java/", 1),
            )
        )
    return rewrites


def legacy_java_prefixes(
    root: Path, *, allow_specimen_fixture: bool = False
) -> list[str]:
    """Import prefixes like 'com.example.app.' for deps stamp.

    Order: migration.yaml stamp → live evidence inventory → (opt-in) fixture.
    Never silently fall back to a demo fixture on the golden tip
    (Deputy E-20260813T184217Z).
    """
    mig = load_migration_yaml(root).get("migration") or {}
    if isinstance(mig, dict):
        base = (
            mig.get("legacyBasePackage")
            or mig.get("legacy_base_package")
            or mig.get("legacyPackage")
        )
        if base:
            b = str(base).strip().rstrip(".") + "."
            return [b]
    # Derive from inventory file paths (live evidence only by default)
    cands = [root / "evidence/entry-point-inventory.json"]
    if allow_specimen_fixture:
        cands.append(
            root
            / "governance/fixtures/inventory/entry-point-inventory-petclinic-f11.json"
        )
    for cand in cands:
        inv = load_json(cand)
        if not isinstance(inv, dict):
            continue
        pkgs: list[str] = []
        for ep in inv.get("entry_points") or []:
            if not isinstance(ep, dict):
                continue
            f = str(ep.get("file") or "").replace("\\", "/")
            m = re.match(r"src/(?:main|test)/java/(.+)/[^/]+\.java$", f)
            if m:
                pkgs.append(m.group(1).replace("/", "."))
        if not pkgs:
            continue
        # longest common package prefix
        parts = [p.split(".") for p in pkgs]
        common: list[str] = []
        for segs in zip(*parts):
            if len(set(segs)) == 1:
                common.append(segs[0])
            else:
                break
        if common:
            return [".".join(common) + "."]
    return []


def resolve_inventory_path(root: Path, explicit: str = "", *, allow_specimen_fixture: bool = False) -> Path | None:
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = root / p
        return p if p.is_file() else None
    primary = root / "evidence/entry-point-inventory.json"
    if primary.is_file():
        return primary
    if allow_specimen_fixture:
        fixture = root / "governance/fixtures/inventory/entry-point-inventory-petclinic-f11.json"
        if fixture.is_file():
            return fixture
    return None


def inventory_http_expected(inventory: dict) -> int:
    """Denominator = runtime inventory HTTP count (never a specimen constant)."""
    eps = inventory.get("entry_points") or []
    if not isinstance(eps, list):
        return 0
    return sum(1 for e in eps if isinstance(e, dict) and e.get("kind") == "http")


# ---------------------------------------------------------------------------
# Shared exit vocabulary (Deputy E-20260813T220250Z F1/F4/F5)
# One definition for surgical-scopes + semantic-exits. Specimen literals
# (e.g. owner_pet_visit_create) must NOT appear here — R-SK.5.
# ---------------------------------------------------------------------------

# Unified compile-shaped checks (union of prior surgical + semantic sets).
COMPILE_ONLY = frozenset(
    {
        "compile",
        "mvn_compile",
        "mvn_test_compile",
        "quarkus_compile",
        "residue",
        "spring_residue",
        "skills",
        "claim_accuracy",
        "scope",
    }
)

# Legal non-compile semantic exit check names (closed set, specimen-agnostic).
SEMANTIC_EXIT_VOCAB = frozenset(
    {
        # REST / persistence
        "endpoint_contract",
        "route_contract",
        "http_status",
        "http_semantics",
        "route_auth",
        "create_fk",
        "hql_entity_path",
        "delete_cascade_it",
        "exception_mapping",
        "tx_rmw",
        "concurrency",
        "security_authz",
        # Non-REST story classes (F1 — honest terms for build/config/test/infra/obs)
        "build_resolves",
        "config_profile_load",
        "test_suite_runs",
        "log_output",
        "cache_hit",
        "health_probe",
        # Typed escape when no measurable oracle exists (F5)
        "oracle_unavailable",
    }
)

# Backward-compatible alias used by older call sites / docs.
ENDPOINTISH = SEMANTIC_EXIT_VOCAB

# operand_class → preferred semantic exit checks (at least one required unless
# oracle_unavailable with reason). Unknown classes fall back to ENDPOINTISH ∩ REST-ish.
# F5a (Deputy E-20260813T221456Z): oracle_unavailable is NOT legal for
# rest/api/src_code — those always have a measurable oracle. Escape remains
# for build/config/test/infra/observability classes that genuinely lack one.
ORACLE_UNAVAILABLE_FORBIDDEN_CLASSES: frozenset[str] = frozenset(
    {"rest", "api", "src_code"}
)
# F5b: mint-wide fail-closed when escape count exceeds this (of ~13 stories).
ORACLE_UNAVAILABLE_MINT_CAP: int = 2

OPERAND_CLASS_SEMANTIC_EXITS: dict[str, frozenset[str]] = {
    "build_config": frozenset({"build_resolves", "oracle_unavailable"}),
    "build-config": frozenset({"build_resolves", "oracle_unavailable"}),
    "config": frozenset({"config_profile_load", "oracle_unavailable"}),
    "pom": frozenset({"build_resolves", "oracle_unavailable"}),
    "test": frozenset({"test_suite_runs", "oracle_unavailable"}),
    "infra": frozenset({"cache_hit", "health_probe", "oracle_unavailable"}),
    "observability": frozenset({"log_output", "health_probe", "oracle_unavailable"}),
    "rest": frozenset(
        {
            "endpoint_contract",
            "route_contract",
            "http_status",
            "http_semantics",
            "route_auth",
            "create_fk",
            "exception_mapping",
            "security_authz",
        }
    ),
    "api": frozenset(
        {
            "endpoint_contract",
            "route_contract",
            "http_semantics",
        }
    ),
    # src_code: full vocab minus the universal escape (F5a)
    "src_code": frozenset(SEMANTIC_EXIT_VOCAB - {"oracle_unavailable"}),
}


def normalize_operand_class(body: dict) -> str:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    raw = str(
        ident.get("operand_class") or body.get("operand_class") or "src_code"
    ).strip().lower()
    return raw or "src_code"


def required_semantic_exits_for(body: dict) -> frozenset[str]:
    oc = normalize_operand_class(body)
    if oc in OPERAND_CLASS_SEMANTIC_EXITS:
        return OPERAND_CLASS_SEMANTIC_EXITS[oc]
    # aliases
    if oc in {"build_config", "build-config", "config", "pom"}:
        return OPERAND_CLASS_SEMANTIC_EXITS["build_config"]
    # Unknown class: full vocab without universal escape (F5a posture)
    return frozenset(SEMANTIC_EXIT_VOCAB - {"oracle_unavailable"})


def is_compile_only_check(name: str) -> bool:
    return str(name or "").strip() in COMPILE_ONLY


def is_oracle_unavailable(exit_item: dict) -> bool:
    if not isinstance(exit_item, dict):
        return False
    check = str(exit_item.get("check") or "").strip()
    if check != "oracle_unavailable":
        return False
    reason = exit_item.get("reason") or exit_item.get("why") or exit_item.get("detail")
    return isinstance(reason, str) and bool(reason.strip())


def oracle_unavailable_allowed_for_class(operand_class: str) -> bool:
    """F5a — escape forbidden for rest/api/src_code."""
    oc = str(operand_class or "").strip().lower()
    return oc not in ORACLE_UNAVAILABLE_FORBIDDEN_CLASSES


def oracle_unavailable_routes_to_lead(
    exit_item: dict, *, operand_class: str = ""
) -> bool:
    """F5b — true only when escape is class-legal + reasoned (Lead debt signal).

    Callers must also mint-cap and write evidence/receipts/oracle-unavailable.json.
    """
    if not is_oracle_unavailable(exit_item):
        return False
    if operand_class and not oracle_unavailable_allowed_for_class(operand_class):
        return False
    return True


def collect_oracle_unavailable(
    bodies: list[tuple[str, dict]],
) -> list[dict]:
    """Return [{story_id, operand_class, reason, label}, ...] for Lead triage."""
    out: list[dict] = []
    for label, body in bodies:
        if not isinstance(body, dict):
            continue
        ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
        sid = str(ident.get("story_id") or body.get("story_id") or "").strip()
        oc = normalize_operand_class(body)
        exits = body.get("exit_criteria") or body.get("done_when") or []
        if not isinstance(exits, list):
            continue
        for x in exits:
            if not isinstance(x, dict):
                continue
            if not is_oracle_unavailable(x):
                continue
            reason = x.get("reason") or x.get("why") or x.get("detail") or ""
            out.append(
                {
                    "story_id": sid,
                    "operand_class": oc,
                    "reason": str(reason).strip(),
                    "label": label,
                    "routes_to_lead": oracle_unavailable_routes_to_lead(
                        x, operand_class=oc
                    ),
                }
            )
    return out


def write_oracle_unavailable_receipt(
    root: Path, entries: list[dict], *, cap: int = ORACLE_UNAVAILABLE_MINT_CAP
) -> Path:
    """Persist Lead-visible debt list (F5b)."""
    from datetime import datetime, timezone

    receipt_dir = root / "evidence" / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / "oracle-unavailable.json"
    payload = {
        "schema": "rhoai3.oracle-unavailable-receipt/v1",
        "cap": cap,
        "count": len(entries),
        "over_cap": len(entries) > cap,
        "entries": entries,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": [
            "Deputy E-20260813T221456Z F5b — escape is debt, not a pass",
            "routes_to_lead requires class-legal + non-empty reason",
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
