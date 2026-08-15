#!/usr/bin/env python3
"""Specimen-agnostic helpers for migration gates (Operator E-20260811T150800Z).

Falsifier: coolstore must work unchanged. Specimen literals belong in
fixtures / per-run migration.yaml stamps — never in gate logic constants.
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
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
        # A-6: stamp corruption glues `migration:` onto the preceding comment
        # ("...wrong.migration:"). Treat that as section open even inside #.
        if raw.strip().startswith("#") and raw.rstrip().endswith("migration:"):
            in_migration = True
            in_rewrites = False
            i += 1
            continue
        if not raw.strip() or raw.strip().startswith("#"):
            i += 1
            continue
        # Tolerate non-comment glued forms too.
        if raw == "migration:" or raw.rstrip().endswith("migration:"):
            in_migration = True
            in_rewrites = False
            i += 1
            continue
        if in_migration and raw and not raw.startswith(" ") and not raw.startswith("\t"):
            # left migration section
            in_migration = False
            in_rewrites = False
            continue
        if not in_migration:
            i += 1
            continue
        s = raw.strip()
        if s.startswith("legacyRepoUrl:"):
            mig["legacyRepoUrl"] = s.split(":", 1)[1].strip().strip('"').strip("'")
            in_rewrites = False
        elif s.startswith("legacyBasePackage:"):
            mig["legacyBasePackage"] = s.split(":", 1)[1].strip().strip('"').strip("'")
            in_rewrites = False
        elif s.startswith("legacy_base_package:"):
            mig["legacy_base_package"] = s.split(":", 1)[1].strip().strip('"').strip("'")
            in_rewrites = False
        elif s.startswith("legacyPackage:"):
            # RHDH app-migration skeleton stamp key (alias of legacyBasePackage)
            mig["legacyPackage"] = s.split(":", 1)[1].strip().strip('"').strip("'")
            in_rewrites = False
        elif s.startswith("targetPackage:") or s.startswith("target_package:"):
            mig["targetPackage"] = s.split(":", 1)[1].strip().strip('"').strip("'")
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


def _pkg_to_java_prefix(pkg: str) -> str:
    p = str(pkg).strip().strip(".").replace(".", "/")
    return f"src/main/java/{p}/" if p else ""


def path_rewrites(root: Path) -> list[tuple[str, str]]:
    """Return (dest_prefix, legacy_prefix) pairs for norm_file remaps.

    Sources (first non-empty wins):
      1) migration.yaml migration.path_rewrites: [{from, to}, ...]
         where *from* is dest-tree prefix and *to* is legacy-tree prefix
      2) migration.yaml legacyPackage + targetPackage synthesis (A-6)
      3) Discover from inventory HTTP files vs bodies dual-path (best-effort)
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
        # Synthesize from package stamps when explicit rewrites absent.
        legacy_pkg = (
            mig.get("legacyBasePackage")
            or mig.get("legacy_base_package")
            or mig.get("legacyPackage")
            or ""
        )
        target_pkg = mig.get("targetPackage") or mig.get("target_package") or ""
        dest_p = _pkg_to_java_prefix(str(target_pkg))
        leg_p = _pkg_to_java_prefix(str(legacy_pkg))
        if dest_p and leg_p and dest_p != leg_p:
            return [
                (dest_p, leg_p),
                (
                    dest_p.replace("src/main/java/", "src/test/java/", 1),
                    leg_p.replace("src/main/java/", "src/test/java/", 1),
                ),
            ]

    # Discover: inventory legacy java dirs vs modernized dest dirs in bodies
    inv = None
    for cand in (
        root / "evidence/entry-point-inventory.json",
        root / ".hermes/skills/sdd/check-spec-readiness/fixtures/inventory/entry-point-inventory-petclinic-f11.json",
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
        for path in bodies.glob("*.json"):
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

    rewrites: list[tuple[str, str]] = []

    def lcp(paths: list[str]) -> str:
        if not paths:
            return ""
        s1 = min(paths)
        s2 = max(paths)
        i = 0
        while i < len(s1) and i < len(s2) and s1[i] == s2[i]:
            i += 1
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
            / ".hermes/skills/sdd/check-spec-readiness/fixtures/inventory/entry-point-inventory-petclinic-f11.json"
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
            return [_product_package_prefix(common)]
    return []


# HTTP/lifecycle scanners usually live one package below the product root
# (`…petclinic.rest`). v17 inventory fallback used raw LCP and collapsed to
# `…petclinic.rest.` — too specific for import-prefix scans, so A-6 starved
# even when inventory existed (Lead V18-2 / Deputy E-20260814T141027Z).
_LEAF_PACKAGE_SEGMENTS = frozenset(
    {
        "rest",
        "web",
        "api",
        "controller",
        "controllers",
        "config",
        "configuration",
        "service",
        "services",
        "repository",
        "repositories",
        "endpoint",
        "endpoints",
        "resource",
        "resources",
    }
)


def _product_package_prefix(segments: list[str]) -> str:
    segs = list(segments)
    while len(segs) > 1 and segs[-1].lower() in _LEAF_PACKAGE_SEGMENTS:
        segs.pop()
    return ".".join(segs) + "."



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
        fixture = root / ".hermes/skills/sdd/check-spec-readiness/fixtures/inventory/entry-point-inventory-petclinic-f11.json"
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
        # T-8 closed classes (Architect E-20260814T181701Z)
        "mapping_valid",
        "app_boots",
        # Typed escape when no measurable oracle exists (F5)
        "oracle_unavailable",
    }
)

# Backward-compatible alias used by older call sites / docs.
ENDPOINTISH = SEMANTIC_EXIT_VOCAB

# operand_class → legal semantic exit checks (at least one required unless
# oracle_unavailable with reason). Unknown classes fail-closed (empty set) —
# they must not inherit the full vocab (Architect E-20260814T181701Z).
# F5a (Deputy E-20260813T221456Z): oracle_unavailable is NOT legal for
# rest/api/src_code/bootstrap/persistence — those always have a measurable oracle.
# Escape remains for build/config/test/infra/observability classes that genuinely
# lack one.
ORACLE_UNAVAILABLE_FORBIDDEN_CLASSES: frozenset[str] = frozenset(
    {"rest", "api", "src_code", "bootstrap", "persistence"}
)
# F5b: mint-wide fail-closed when escape count exceeds this (of ~13 stories).
ORACLE_UNAVAILABLE_MINT_CAP: int = 2

OPERAND_CLASS_SEMANTIC_EXITS: dict[str, frozenset[str]] = {
    "build_config": frozenset({"build_resolves", "oracle_unavailable"}),
    "build-config": frozenset({"build_resolves", "oracle_unavailable"}),
    "config": frozenset({"config_profile_load", "oracle_unavailable"}),
    "pom": frozenset({"build_resolves", "oracle_unavailable"}),
    "bootstrap": frozenset({"app_boots"}),
    "persistence": frozenset({"mapping_valid"}),
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

# Singleton preferred stamp for the deterministic assembler (one name per class).
# rest/api: concern-table first named HTTP check. src_code has no singleton.
PREFERRED_SEMANTIC_EXIT: dict[str, str] = {
    "build_config": "build_resolves",
    "build-config": "build_resolves",
    "config": "config_profile_load",
    "pom": "build_resolves",
    "bootstrap": "app_boots",
    "persistence": "mapping_valid",
    "test": "test_suite_runs",
    "infra": "health_probe",
    "observability": "log_output",
    "rest": "http_semantics",
    "api": "http_semantics",
}

# Assembler `exit_criteria[].cmd` values. evaluate-exit-criteria.py runs `cmd`
# via subprocess shell=True unless the string ends with " compile" (Class A
# scoped-compile intercept). Stamp Maven invocations, not concern-oracle-table
# technique prose (Architect E-20260814T204807Z). Prose belongs in `assert`.
PREFERRED_SEMANTIC_EXIT_CMD: dict[str, str] = {
    "build_resolves": "mvn -q compile",
    "config_profile_load": "mvn -q test",
    "mapping_valid": "mvn -q test",
    "app_boots": "mvn -q test",
    "http_semantics": "mvn -q test",
    "test_suite_runs": "mvn -q test",
    "health_probe": "mvn -q test",
    "log_output": "mvn -q test",
}


def semantic_exit_cmd_is_maven(cmd: str) -> tuple[bool, list[str]]:
    """SR-13 AMEND: shlex first token is `mvn`, not shutil.which.

    Mint-time golden/validate may lack mvn on PATH. Executability of the
    field is 'this is a Maven invocation', not 'this host can run it now'.
    ` / ` is concern-table OR prose; shell=True would treat `/` as a path.
    """
    s = (cmd or "").strip()
    if not s or " / " in s:
        return False, []
    try:
        parts = shlex.split(s)
    except ValueError:
        return False, []
    if not parts:
        return False, []
    token = parts[0].rsplit("/", 1)[-1]
    return token == "mvn", parts


def semantic_exit_cmd_ok(check: str, cmd: str) -> bool:
    """True when cmd is a class-legal Maven vehicle (Architect E-204807Z).

    build_resolves must end with ` compile` (scoped-compile intercept).
    Other cmd-bearing semantic checks use `mvn … test` (not compile — DD6).
    """
    ok, parts = semantic_exit_cmd_is_maven(cmd)
    if not ok:
        return False
    if check == "build_resolves":
        return cmd.strip().endswith(" compile")
    return parts[-1] == "test"


def build_resolves_cmd_is_executable(cmd: str) -> bool:
    """Compat wrapper — prefer semantic_exit_cmd_ok(check, cmd)."""
    return semantic_exit_cmd_ok("build_resolves", cmd)


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
    # Unknown class: empty set — mint lint fail-closed (Architect E-20260814T181701Z).
    # Do not widen to full vocab (that licensed http_semantics on JPA/bootstrap).
    return frozenset()


def preferred_semantic_exit_for(operand_class: str) -> str | None:
    """One class-legal stamp for the assembler. None ⇒ unknown class (refuse)."""
    oc = str(operand_class or "").strip().lower()
    allowed = OPERAND_CLASS_SEMANTIC_EXITS.get(oc)
    if not allowed:
        return None
    pref = PREFERRED_SEMANTIC_EXIT.get(oc)
    if pref and pref in allowed:
        return pref
    measurable = sorted(allowed - {"oracle_unavailable"})
    return measurable[0] if measurable else None


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


# Architect E-20260814T212425Z — refs path-sha oracle (SR-13).
# sha256(resolve(path)) must equal the stamped digest. Missing file fail-closed.
# Typed `pending` is fail-closed except creation-time ack keys (Operator artifact
# does not exist at mint). AMEND: not every pending ref is refused — only
# digest-bearing harvest refs (legacy_locus and any non-ack hex/pending slot).
REF_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
REF_PENDING = "pending"
REF_PENDING_ALLOWED_KEYS = frozenset({"brief_identity_ack", "m1_findings_ack"})


def resolve_ref_file(root: Path, path_s: str) -> Path | None:
    """Return the file `path_s` names, or None if unresolvable."""
    s = (path_s or "").strip()
    if not s:
        return None
    p = Path(s)
    try:
        if p.is_absolute():
            return p if p.is_file() else None
        cand = Path(root) / s
        if cand.is_file():
            return cand.resolve()
    except OSError:
        return None
    return None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refs_path_sha_errors(
    root: Path,
    refs: list,
    *,
    pending_allowed: frozenset[str] | None = None,
) -> list[str]:
    """Errors when a ref digest does not match the file at `path`.

    `pending` on non-ack keys is fail-closed. Hex digest with a missing file
    is fail-closed (do not defer — that licensed dest-relative locus stamps).
    """
    allowed = (
        pending_allowed if pending_allowed is not None else REF_PENDING_ALLOWED_KEYS
    )
    errs: list[str] = []
    if not isinstance(refs, list):
        return ["refs must be a list"]
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        key = str(ref.get("key") or "")
        path_s = str(ref.get("path") or "").strip()
        exp = str(ref.get("sha256") or "").strip().lower()
        if not exp:
            continue
        if exp == REF_PENDING:
            if key not in allowed:
                errs.append(
                    f"key={key} sha256=pending fail-closed "
                    f"(pending only for {sorted(allowed)})"
                )
            continue
        if not REF_SHA256_HEX.match(exp):
            continue
        if not path_s:
            errs.append(f"key={key} path missing (cannot verify sha256)")
            continue
        got = resolve_ref_file(root, path_s)
        if got is None:
            errs.append(
                f"key={key} path={path_s} unresolvable "
                "(path-sha oracle fail-closed)"
            )
            continue
        actual = sha256_file(got)
        if actual != exp:
            errs.append(
                f"key={key} path={path_s} expected={exp} actual={actual} "
                f"resolved={got}"
            )
    return errs


# Architect E-20260814T205052Z — DD3 declare/apply/own.
# identity.extensions_declared: every M3 body, string[] artifactIds (empty = none).
# identity.extensions_apply: only the sole pom.xml writer; sorted unique union.
# Path heuristic is T-3 (spring-dep-to-extension.md). Do not invent GAVs or
# jdbc drivers. /repository/jdbc/ → [] (JdbcTemplate often needs no extension).
_REST_EXTENSIONS = ("quarkus-rest", "quarkus-rest-jackson")
_JPA_EXTENSIONS = ("quarkus-hibernate-orm",)


def body_scope_paths(body: dict) -> list[str]:
    """Dest-relative or absolute paths from writable/in-scope fields."""
    out: list[str] = []
    for key in ("files_writable", "write_set", "files_in_scope", "filesInScope"):
        raw = body.get(key) if isinstance(body, dict) else None
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.replace("\\", "/").strip())
            elif isinstance(item, dict):
                for k in ("legacy", "src", "source", "path", "file", "dest", "dst"):
                    if item.get(k):
                        out.append(str(item[k]).replace("\\", "/").strip())
    return out


def writes_pom_xml(body: dict) -> bool:
    """True when this body claims pom.xml on a write/scope path."""
    return any(p.rstrip("/").endswith("pom.xml") for p in body_scope_paths(body))


def declared_extensions_for_paths(paths: list[str]) -> list[str]:
    """T-3 path heuristic → sorted unique artifactIds. Empty = none."""
    found: set[str] = set()
    for raw in paths:
        p = (raw or "").replace("\\", "/").lower()
        base = p.rsplit("/", 1)[-1]
        if "/rest/" in p or base.endswith("restcontroller.java"):
            found.update(_REST_EXTENSIONS)
        if "/repository/jpa/" in p or "/springdatajpa/" in p:
            found.update(_JPA_EXTENSIONS)
    return sorted(found)


def parse_extensions_declared(identity: dict) -> tuple[list[str] | None, str | None]:
    """Return (artifactIds, None) or (None, error). Missing key is an error."""
    if not isinstance(identity, dict) or "extensions_declared" not in identity:
        return None, "identity.extensions_declared missing (fail-closed)"
    raw = identity["extensions_declared"]
    if not isinstance(raw, list):
        return None, "identity.extensions_declared must be string[]"
    out: list[str] = []
    for i, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            return None, f"identity.extensions_declared[{i}] must be a non-empty string"
        s = item.strip()
        if ":" in s or "/" in s:
            return None, (
                f"identity.extensions_declared[{i}]={s!r} is not an artifactId "
                "(no GAV / path)"
            )
        out.append(s)
    return out, None


def extensions_union(declared_lists: list[list[str]]) -> list[str]:
    found: set[str] = set()
    for lst in declared_lists:
        found.update(lst)
    return sorted(found)


def stamp_dd3_extensions(bodies: list[dict]) -> None:
    """Stamp declared on every body; apply on the sole pom.xml writer.

    Raises ValueError unless exactly one writer. Non-writers must not carry
    extensions_apply (key absent, not []).
    """
    if not bodies:
        raise ValueError("stamp_dd3_extensions: no bodies")
    declared_lists: list[list[str]] = []
    for body in bodies:
        ident = body.setdefault("identity", {})
        if not isinstance(ident, dict):
            raise ValueError("stamp_dd3_extensions: identity must be an object")
        ident["extensions_declared"] = declared_extensions_for_paths(
            body_scope_paths(body)
        )
        ident.pop("extensions_apply", None)
        declared_lists.append(list(ident["extensions_declared"]))
    writers = [b for b in bodies if writes_pom_xml(b)]
    if len(writers) != 1:
        sids = []
        for b in writers:
            ident = b.get("identity") if isinstance(b.get("identity"), dict) else {}
            sids.append(str(ident.get("story_id") or b.get("task_id") or "?"))
        raise ValueError(
            f"stamp_dd3_extensions: need exactly 1 pom.xml writer, "
            f"got {len(writers)} {sids}"
        )
    writers[0]["identity"]["extensions_apply"] = extensions_union(declared_lists)


# ---------------------------------------------------------------------------
# L2 mint oracles — SR-13 discriminating exit + Hermes task_id identity
# Operator E-20260815T010500Z / Lead L2 entry gate.
# shlex+mvn is necessary (semantic_exit_cmd_ok) and not sufficient: `true`
# and a test-shaped cmd with no named proving test in this write-set both
# satisfy the shape lint while asserting nothing about this story. An
# unrelated dest src/test file must not flip the oracle (L2a /
# E-20260815T014500Z). Provenance over mint-time Maven invocation.
# ---------------------------------------------------------------------------

CARD_TASK_ID_RE = re.compile(r"^t_[0-9a-f]{8,}$")
ALWAYS_OK_CMD_TOKENS = frozenset({"true", ":", "true.exe"})
_TEST_SOURCE_SUFFIXES = {".java", ".kt", ".scala"}


def _rel_posix(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def files_writable_rels(body: dict) -> set[str]:
    """Dest-relative write-set only (not files_in_scope)."""
    out: set[str] = set()
    if not isinstance(body, dict):
        return out
    for key in ("files_writable", "write_set"):
        raw = body.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.add(_rel_posix(item))
            elif isinstance(item, dict):
                for k in ("dest", "dst", "path", "file"):
                    if item.get(k):
                        out.add(_rel_posix(str(item[k])))
                        break
    return out


def _path_excluded(rel: str, writable: set[str]) -> bool:
    rel = _rel_posix(rel)
    if rel in writable:
        return True
    for w in writable:
        ww = _rel_posix(w)
        if not ww:
            continue
        if ww.endswith("/"):
            if rel.startswith(ww):
                return True
        elif rel.startswith(ww + "/"):
            return True
    return False


def is_test_source_rel(rel: str) -> bool:
    n = _rel_posix(rel)
    if Path(n).suffix.lower() not in _TEST_SOURCE_SUFFIXES:
        return False
    return n.startswith("src/test/") or "/src/test/" in n


def proving_test_rels(exit_item: dict) -> tuple[list[str], str | None]:
    """Named tests that prove this exit (L2a). Missing key → empty, not error."""
    if not isinstance(exit_item, dict) or "proves" not in exit_item:
        return [], None
    raw = exit_item.get("proves")
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        return [], "proves must be a string or list of dest-relative test paths"
    out: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            return [], "proves entries must be non-empty strings"
        out.append(_rel_posix(item))
    return out, None


def minted_task_id_errors(
    body: dict, *, expect_task_id: str | None = None
) -> list[str]:
    """Refuse story-slug task_id. Equality is post-bind only.

    Assembler stamps task_id=story_id before create. Do not require t_* in
    check-kanban-body pre-create — that would break mint. After bind,
    body.task_id must equal the Hermes card id.
    """
    tid = str((body or {}).get("task_id") or "").strip()
    if expect_task_id:
        exp = str(expect_task_id).strip()
        if tid != exp:
            return [f"task_id={tid!r} != card {exp!r}"]
        if not CARD_TASK_ID_RE.fullmatch(tid):
            return [f"task_id={tid!r} is not a Hermes card id (t_<hex>)"]
        return []
    if not CARD_TASK_ID_RE.fullmatch(tid):
        return [
            f"task_id={tid!r} is not a Hermes card id (t_<hex>) "
            "(do not widen to story-N)"
        ]
    return []


def exit_cmd_discriminating_errors(root: Path, body: dict) -> list[str]:
    """SR-13 / L2a: cmd must be able to fail *for this story*.

    Static (no mvn on PATH — golden must not require it):
      * first token `true` / `:` → always succeeds → refuse
      * `mvn … test` must name `proves` test source(s) that sit in
        **this** `files_writable`. An unrelated dest `src/test` file must
        not satisfy the oracle (Deputy E-20260815T014500Z).
      * `mvn … compile` is not test-shaped; remaining pom / no pom as before.
      * surefire `failIfNoTests=true` is not a mint recipe (L4).

    Provenance over mint-time Maven invocation.
    """
    errs: list[str] = []
    writable = files_writable_rels(body)
    exits = (body or {}).get("exit_criteria") or (body or {}).get("done_when") or []
    if not isinstance(exits, list):
        return ["exit_criteria must be a list"]
    for x in exits:
        if not isinstance(x, dict):
            continue
        check = str(x.get("check") or "").strip()
        if is_oracle_unavailable(x):
            continue
        cmd = x.get("cmd")
        if not (isinstance(cmd, str) and cmd.strip()):
            continue
        s = cmd.strip()
        try:
            parts = shlex.split(s)
        except ValueError:
            errs.append(
                f"exit {check!r} cmd {cmd!r} unparseable "
                "(SR-13 discriminating-exit refuse)"
            )
            continue
        if not parts:
            continue
        token0 = parts[0].rsplit("/", 1)[-1]
        if token0 in ALWAYS_OK_CMD_TOKENS:
            errs.append(
                f"exit {check!r} cmd {cmd!r} always succeeds "
                "(SR-13 discriminating-exit refuse)"
            )
            continue
        ok, mvn_parts = semantic_exit_cmd_is_maven(s)
        if not ok or not mvn_parts:
            continue
        if mvn_parts[-1] != "test":
            continue
        proves, perr = proving_test_rels(x)
        if perr:
            errs.append(
                f"exit {check!r} cmd {cmd!r} {perr} "
                "(L2a per-story test provenance refuse)"
            )
            continue
        if not proves:
            errs.append(
                f"exit {check!r} cmd {cmd!r} names no proving test "
                "(L2a: a test-shaped exit must name the test in this "
                "files_writable; an unrelated src/test file cannot satisfy SR-13)"
            )
            continue
        for rel in proves:
            if not is_test_source_rel(rel):
                errs.append(
                    f"exit {check!r} proves {rel!r} is not a test source "
                    "(L2a per-story test provenance refuse)"
                )
                continue
            if not _path_excluded(rel, writable):
                errs.append(
                    f"exit {check!r} proves {rel!r} is not in this "
                    "files_writable (L2a per-story test provenance refuse)"
                )
    return errs
