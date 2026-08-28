#!/usr/bin/env python3
"""Specimen-agnostic remainder (oracles / operand / refs). Concern modules:
inventory_io, path_maps, supersede, http_join. Re-exports those names.

Specimen-agnostic helpers for migration gates (Operator E-20260811T150800Z).

Falsifier: coolstore must work unchanged. Specimen literals belong in
fixtures / per-run migration.yaml stamps — never in gate logic constants.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any

from inventory_io import (
    load_json,
    load_migration_yaml,
    resolve_inventory_path,
    resolve_partition_path,
    inventory_http_expected,
)
from path_maps import (
    dest_path_as_written,
    intra_package_maps,
    path_rewrites,
    rewrite_across,
    dest_hole_leaves,
    resolve_java_source,
    legacy_java_prefixes,
)
from supersede import (
    collect_supersedes,
    type_inventory_invented_writes,
    type_inventory_supersede_gaps,
    type_inventory_uncovered,
)
from http_join import (
    endpoint_tokens,
    row_tokens,
    story_claims_http,
)

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
# T-8 AMEND (Architect E-20260816T115106Z): operand_class is a *set* used for
# B-16 skill attachment and class-legal *names*; the exit *cmd* comes from
# phase acceptance criteria. Do not drop the field. Do not stamp a default
# `mvn -q test` on every card.
# F5a (Deputy E-20260813T221456Z): oracle_unavailable is NOT legal for
# rest/api/src_code/bootstrap/persistence — those always have a measurable oracle.
# Escape remains for build/config/test/infra/observability classes that genuinely
# lack one.
ORACLE_UNAVAILABLE_FORBIDDEN_CLASSES: frozenset[str] = frozenset(
    {"rest", "api", "src_code", "bootstrap", "persistence"}
)
# Native user-story phases (v20). Oracle source is acceptance criteria, not
# a class-map preferred stamp. Unknown tokens that are *not* in this set
# still fail-closed (do not inherit the full vocab).
AC_SOURCED_OPERAND_CLASSES: frozenset[str] = frozenset({"user_story", "story"})
FOUNDATION_OPERAND_CLASSES: frozenset[str] = frozenset(
    {"build_config", "config", "pom"}
)
# B-16 — attach by class, not a uniform M3 bundle. Union across the set.
# W5: rest/us declare + own config/SQL; only pom/bootstrap apply the union.
OPERAND_CLASS_SKILLS: dict[str, tuple[str, ...]] = {
    "rest": ("spring-to-quarkus-patterns",),
    "api": ("spring-to-quarkus-patterns",),
    "src_code": ("spring-to-quarkus-patterns",),
    "persistence": ("form-entity-persistence",),
    "build_config": ("manage-quarkus-extensions", "reference-rh-quarkus-pom"),
    "pom": ("manage-quarkus-extensions", "reference-rh-quarkus-pom"),
    "config": ("configure-quarkus-profiles",),
    "bootstrap": ("author-destination-pom",),
    "test": (),
    "infra": (),
    "observability": (),
    "user_story": (),
    "story": (),
}
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

# Fallback cmds when a *single* known class has no acceptance_criteria and
# the write-set already contains the proving test. OBJECT a default
# `mvn -q test` on cards that do not name a proving test (T-8 AMEND).
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

DEFAULT_TEST_CMD = "mvn -q test"
MAVEN_AC_GOALS = frozenset({"test", "verify", "test-compile"})
ALWAYS_OK_CMD_TOKENS = frozenset({"true", ":", "true.exe"})


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


def _cmd_token0(parts: list[str]) -> str:
    return parts[0].rsplit("/", 1)[-1]


def semantic_exit_cmd_ok(check: str, cmd: str) -> bool:
    """True when cmd is a Maven vehicle that can fail for this card's AC.

    Keep the Maven vehicle (Operator course-correction 2026-08-16).
    build_resolves must end with ` compile`. Other checks accept `test`,
    `verify`, and `test-compile` (v19 Issue 6). curl / scripts / `./…` are
    not card exits — live acceptance is M4/M5 gate scripts; an HTTP AC is a
    @QuarkusTest in this write-set (B-1). Vacuous `true` / technique prose
    / slash-OR gloss refuse (SR-13).
    """
    s = (cmd or "").strip()
    if not s or " / " in s:
        return False
    try:
        parts = shlex.split(s)
    except ValueError:
        return False
    if not parts:
        return False
    if _cmd_token0(parts) in ALWAYS_OK_CMD_TOKENS:
        return False
    ok, mvn_parts = semantic_exit_cmd_is_maven(s)
    if not ok or not mvn_parts:
        return False
    if check == "build_resolves":
        return s.endswith(" compile")
    return mvn_parts[-1] in MAVEN_AC_GOALS


def _canon_operand_class(token: str) -> str:
    return str(token or "").strip().lower().replace("-", "_")


def parse_operand_classes(raw: Any) -> list[str]:
    """Accept a string, list, or the str(list) accident. Preserve order."""
    items: list[str] = []
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = ast.literal_eval(s)
            except (SyntaxError, ValueError):
                parsed = None
            if isinstance(parsed, (list, tuple, set, frozenset)):
                return parse_operand_classes(list(parsed))
        if "," in s:
            items = [x.strip() for x in s.split(",")]
        else:
            items = [s]
    elif isinstance(raw, (list, tuple, set, frozenset)):
        for x in raw:
            items.extend(parse_operand_classes(x))
    else:
        items = [str(raw).strip()]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        c = _canon_operand_class(item)
        if not c or c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def operand_classes_of(body: dict) -> list[str]:
    """operand_class as a set (list for stable order). Defaults to src_code."""
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    if isinstance(ident, dict) and "operand_class" in ident:
        raw = ident.get("operand_class")
    else:
        raw = body.get("operand_class")
    parsed = parse_operand_classes(raw)
    return parsed or ["src_code"]


def stamp_operand_class(classes: list[str]) -> str | list[str]:
    """Single class stays a string (compat); multiple become a list."""
    cleaned = parse_operand_classes(classes)
    if not cleaned:
        return "src_code"
    if len(cleaned) == 1:
        return cleaned[0]
    return cleaned


def skills_for_operand_classes(classes: list[str] | tuple[str, ...] | str) -> list[str]:
    """B-16 attach set — union of per-class skills, order-stable."""
    out: list[str] = []
    seen: set[str] = set()
    for oc in parse_operand_classes(classes):
        for skill in OPERAND_CLASS_SKILLS.get(oc, ()):
            if skill not in seen:
                seen.add(skill)
                out.append(skill)
    return out


POM_ATTACH_SKILLS = frozenset(
    {"manage-quarkus-extensions", "reference-rh-quarkus-pom"}
)


def _owns_pom_write_set(paths: list[str] | tuple[str, ...] | None) -> bool:
    """True when this story is the A-5 pom.xml writer."""
    for raw in paths or []:
        n = str(raw).strip().lstrip("./")
        if n == "pom.xml" or n.endswith("/pom.xml"):
            return True
    return False


def filter_attach_skills_for_write_set(
    skills: list[str], files_writable: list[str] | tuple[str, ...] | None
) -> list[str]:
    """Drop pom skills unless pom.xml is in the story write-set (Architect 113519Z)."""
    if _owns_pom_write_set(files_writable):
        return list(skills)
    return [s for s in skills if s not in POM_ATTACH_SKILLS]


def known_operand_classes(classes: list[str]) -> list[str]:
    return [c for c in classes if c in OPERAND_CLASS_SEMANTIC_EXITS]


def ac_sourced_operand_classes(classes: list[str]) -> list[str]:
    return [c for c in classes if c in AC_SOURCED_OPERAND_CLASSES]


def unknown_operand_classes(classes: list[str]) -> list[str]:
    return [
        c
        for c in classes
        if c not in OPERAND_CLASS_SEMANTIC_EXITS
        and c not in AC_SOURCED_OPERAND_CLASSES
    ]


def _normalize_operand_class(body: dict) -> str:
    """Compat scalar: first class. Prefer operand_classes_of for T-8 AMEND."""
    classes = operand_classes_of(body)
    return classes[0] if classes else "src_code"


def required_semantic_exits_for(body: dict) -> frozenset[str]:
    """Union of class-legal names. Unknown-only → empty (fail-closed)."""
    union: set[str] = set()
    known = 0
    for oc in operand_classes_of(body):
        allowed = OPERAND_CLASS_SEMANTIC_EXITS.get(oc)
        if allowed:
            union |= set(allowed)
            known += 1
    if known == 0:
        return frozenset()
    return frozenset(union)


def preferred_semantic_exit_for(operand_class: str) -> str | None:
    """One class-legal stamp for a *single* known class. None ⇒ unknown / AC."""
    oc = _canon_operand_class(operand_class)
    allowed = OPERAND_CLASS_SEMANTIC_EXITS.get(oc)
    if not allowed:
        return None
    pref = PREFERRED_SEMANTIC_EXIT.get(oc)
    if pref and pref in allowed:
        return pref
    measurable = sorted(allowed - {"oracle_unavailable"})
    return measurable[0] if measurable else None


class _OracleUnmappedError(ValueError):
    """Mint/assembler leftover type. `exit_for` was superseded by
    `preferred_semantic_exit_for` (KEEP check-semantic-exits / park assemble).
    """

    code = "ORACLE_UNMAPPED"


def is_oracle_unavailable(exit_item: dict) -> bool:
    if not isinstance(exit_item, dict):
        return False
    check = str(exit_item.get("check") or "").strip()
    if check != "oracle_unavailable":
        return False
    reason = exit_item.get("reason") or exit_item.get("why") or exit_item.get("detail")
    return isinstance(reason, str) and bool(reason.strip())


def _oracle_unavailable_allowed_for_class(operand_class: str) -> bool:
    """F5a — escape forbidden for rest/api/src_code."""
    oc = _canon_operand_class(operand_class)
    return oc not in ORACLE_UNAVAILABLE_FORBIDDEN_CLASSES


def oracle_unavailable_allowed_for_body(body: dict) -> bool:
    """Escape allowed only when *every* class in the set permits it."""
    return all(
        _oracle_unavailable_allowed_for_class(c) for c in operand_classes_of(body)
    )


def oracle_unavailable_routes_to_lead(
    exit_item: dict, *, operand_class: str = ""
) -> bool:
    """F5b — true only when escape is class-legal + reasoned (Lead debt signal).

    Callers must also mint-cap and write evidence/receipts/oracle-unavailable.json.
    """
    if not is_oracle_unavailable(exit_item):
        return False
    if operand_class and not _oracle_unavailable_allowed_for_class(operand_class):
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
        oc = _normalize_operand_class(body)
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


def _resolve_ref_file(root: Path, path_s: str) -> Path | None:
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
        got = _resolve_ref_file(root, path_s)
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
_GENERATOR_PLUGIN = "openapi-generator-maven-plugin"
REQUIRED_EXTENSIONS_REL = "evidence/required-extensions.json"
_SPEC_NAMES = ("api-docs.yml", "api-docs.yaml", "openapi.yml", "openapi.yaml", "openapi.json")


def _body_scope_paths(body: dict) -> list[str]:
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
    return any(p.rstrip("/").endswith("pom.xml") for p in _body_scope_paths(body))


def _declared_extensions_for_paths(paths: list[str]) -> list[str]:
    """T-3 path heuristic → sorted unique artifactIds. Empty = none.

    Dest layouts use entity/ and resource/ (not only repository/jpa and /rest/).
    /repository/jdbc/ stays [] (JdbcTemplate often needs no extension).
    """
    found: set[str] = set()
    for raw in paths:
        p = (raw or "").replace("\\", "/").lower()
        base = p.rsplit("/", 1)[-1]
        if "/repository/jdbc/" in p or "/jdbc/" in p:
            continue
        if (
            "/rest/" in p
            or "/resource/" in p
            or base.endswith("restcontroller.java")
            or base.endswith("resource.java")
        ):
            found.update(_REST_EXTENSIONS)
        if (
            "/repository/jpa/" in p
            or "/springdatajpa/" in p
            or "/entity/" in p
            or "/repository/" in p
            or "entity" in base
        ):
            found.update(_JPA_EXTENSIONS)
        if base in _SPEC_NAMES or (
            base.endswith((".yml", ".yaml", ".json"))
            and any(tok in base for tok in ("api-docs", "openapi", "swagger"))
        ):
            found.add(_GENERATOR_PLUGIN)
    return sorted(found)


def load_required_extension_entries(root: Path | None) -> list[dict[str, str]]:
    """Read M1 entries[{artifactId, kind}]. Missing file → []."""
    if root is None:
        return []
    p = Path(root) / REQUIRED_EXTENSIONS_REL
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    raw = data.get("entries")
    out: list[dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            aid = str(item.get("artifactId") or "").strip()
            kind = str(item.get("kind") or "").strip().lower()
            if not aid or ":" in aid or "/" in aid:
                continue
            if aid.startswith("quarkus-spring-"):
                continue
            if kind not in {"extension", "plugin"}:
                kind = (
                    "plugin"
                    if aid == "openapi-generator-maven-plugin"
                    else "extension"
                )
            out.append({"artifactId": aid, "kind": kind})
    return sorted(out, key=lambda r: r["artifactId"])


def _load_required_extensions(root: Path | None) -> list[str]:
    """ArtifactIds from M1 required-extensions.json. Missing file → []."""
    return [r["artifactId"] for r in load_required_extension_entries(root)]


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


def stamp_dd3_extensions(bodies: list[dict], *, root: Path | None = None) -> None:
    """Stamp declared on every body; apply on the sole pom.xml writer.

    The pom writer also declares M1 required-extensions.json (when present)
    so check-kanban-body apply == sibling union still holds. Raises
    ValueError unless exactly one writer. Non-writers must not carry
    extensions_apply (key absent, not []).
    """
    if not bodies:
        raise ValueError("stamp_dd3_extensions: no bodies")
    m1 = _load_required_extensions(root)
    declared_lists: list[list[str]] = []
    for body in bodies:
        ident = body.setdefault("identity", {})
        if not isinstance(ident, dict):
            raise ValueError("stamp_dd3_extensions: identity must be an object")
        declared = _declared_extensions_for_paths(_body_scope_paths(body))
        if writes_pom_xml(body) and m1:
            declared = extensions_union([declared, m1])
        ident["extensions_declared"] = declared
        ident.pop("extensions_apply", None)
        declared_lists.append(list(ident["extensions_declared"]))
    writers = [b for b in bodies if writes_pom_xml(b)]
    if len(writers) != 1:
        sids = []
        details = []
        for b in bodies:
            ident = b.get("identity") if isinstance(b.get("identity"), dict) else {}
            sid = str(ident.get("story_id") or b.get("task_id") or "?")
            if writes_pom_xml(b):
                sids.append(sid)
            fw = _body_scope_paths(b)
            pom_hits = [
                p
                for p in fw
                if str(p).replace("\\", "/").rstrip("/").endswith("pom.xml")
            ]
            details.append(f"{sid}: files_writable pom={pom_hits or 'none'}")
        raise ValueError(
            f"stamp_dd3_extensions: need exactly 1 pom.xml writer, "
            f"got {len(writers)} {sids}. "
            "Surface=typed bodies files_writable (writes_pom_xml). "
            + "; ".join(details)
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
_TEST_SOURCE_SUFFIXES = {".java", ".kt", ".scala"}


def _paths_from_story_field(val: object) -> list[str]:
    out: list[str] = []
    if not isinstance(val, list):
        return out
    for item in val:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            for k in ("dest", "dst", "legacy", "src", "source", "path", "file"):
                if item.get(k):
                    out.append(str(item[k]).strip())
                    break
    return out


def story_declared_writeset(story: dict) -> list[str]:
    """Single declared dest frame on a partition story.

    First non-empty of files_writable, files, files_in_scope. Do not
    union keys — that mixes frames (entity/ + model/) and hides extras.
    """
    if not isinstance(story, dict):
        return []
    for key in ("files_writable", "files", "files_in_scope", "legacy_files", "scope_files"):
        paths = _paths_from_story_field(story.get(key))
        if paths:
            return paths
    return []


_HEALTH_AC = re.compile(
    r"(?i)/q/health|healthtest|smallrye-health|quarkus-smallrye-health"
    r"|\bhealth_probe\b"
)
_POM_AC = re.compile(r"(?i)\bpom\.xml\b|quarkus:add-extension|\badd-extension\b")


def acceptance_unsatisfiable_files(story: dict) -> list[str]:
    """Files this story's acceptance needs that files_writable does not grant.

    dest-5 T020: HealthTest + /q/health with pom.xml outside the write-set
    (Lead:partition-must-grant-scope-its-acceptance-needs). Health and
    add-extension imply pom.xml. ``proves`` paths must be in the write-set.
    """
    if not isinstance(story, dict):
        return []
    writable = {
        dest_path_as_written(p) for p in story_declared_writeset(story) if p
    }
    writable_names = {Path(p).name for p in writable}
    blob_parts: list[str] = []
    proves: list[str] = []
    for key in (
        "acceptance_criteria",
        "acceptance",
        "ac",
        "exit_criteria",
        "done_when",
    ):
        raw = story.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            blob_parts.append(raw)
            continue
        blob_parts.append(json.dumps(raw, default=str))
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                for p in item.get("proves") or []:
                    if str(p).strip():
                        proves.append(str(p).strip())
                blob_parts.append(
                    " ".join(
                        str(item.get(k) or "")
                        for k in ("cmd", "assert", "expect", "check")
                    )
                )
    blob = "\n".join(blob_parts)
    missing: list[str] = []
    if _HEALTH_AC.search(blob) or _POM_AC.search(blob):
        if "pom.xml" not in writable and "pom.xml" not in writable_names:
            missing.append("pom.xml")
    for p in proves:
        rel = dest_path_as_written(p)
        name = Path(rel).name
        if rel not in writable and name not in writable_names:
            missing.append(rel)
    # Stable unique
    seen: set[str] = set()
    out: list[str] = []
    for item in missing:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def partition_story_writeset(root: Path, story_id: str) -> tuple[str, set[str]]:
    """Look up partition.stories[id] declared write-set.

    Returns (status, files) where status is:
      absent — no partition.json / invalid
      missing_story — partition present, story_id not in stories[]
      ok — story found (files may be empty)
    """
    path, _looked = resolve_partition_path(root)
    if path is None:
        return "absent", set()
    data = load_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("stories"), list):
        return "absent", set()
    sid = str(story_id or "").strip()
    if not sid:
        return "missing_story", set()
    for story in data["stories"]:
        if not isinstance(story, dict):
            continue
        if str(story.get("story_id") or "").strip() != sid:
            continue
        files = {dest_path_as_written(p) for p in story_declared_writeset(story) if p}
        return "ok", files
    return "missing_story", set()


def _files_writable_rels(body: dict) -> set[str]:
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


_TEST_ANNOTATION_RE = re.compile(
    r"@(?:org\.junit\.(?:jupiter\.api\.)?)?"
    r"(?:Test|ParameterizedTest|RepeatedTest|TestFactory|TestTemplate)\b"
)


def _java_has_executable_test(text: str) -> bool:
    """True when the source contains a JUnit/TestNG executable test annotation."""
    return bool(_TEST_ANNOTATION_RE.search(text or ""))


def proves_to_fqcn(rel: str) -> str | None:
    n = _rel_posix(rel)
    m = re.search(r"(?:^|/)src/test/java/(.+)\.(java|kt)$", n)
    if not m:
        return None
    return m.group(1).replace("/", ".")


def _surefire_has_class(root: Path, fqcn: str) -> bool:
    reports = Path(root) / "target" / "surefire-reports"
    if not reports.is_dir():
        return False
    xml = reports / f"TEST-{fqcn}.xml"
    if xml.is_file() and xml.stat().st_size > 0:
        return True
    needle = f'classname="{fqcn}"'
    for path in reports.glob("TEST-*.xml"):
        try:
            if needle in path.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            continue
    return False


def _body_has_test_shaped_cmd(body: dict) -> bool:
    for item in (body or {}).get("exit_criteria") or (body or {}).get("done_when") or []:
        if not isinstance(item, dict):
            continue
        cmd = item.get("cmd")
        if not (isinstance(cmd, str) and cmd.strip()):
            continue
        ok, parts = semantic_exit_cmd_is_maven(cmd)
        if ok and parts and parts[-1] in {"test", "verify"}:
            return True
    return False


def proves_executable_errors(
    root: Path, body: dict, *, stage: str = "mint"
) -> list[str]:
    """B-1: each proves path contains an executable @Test.

    mint: missing dest file is OK (the story may add it). An existing file
    with methods but no @Test refuses.
    complete: file must exist, contain @Test, and (when a test-shaped Maven
    cmd ran) appear in target/surefire-reports.
    """
    errs: list[str] = []
    root = Path(root)
    exits = (body or {}).get("exit_criteria") or (body or {}).get("done_when") or []
    if not isinstance(exits, list):
        return errs
    need_surefire = stage == "complete" and _body_has_test_shaped_cmd(body)
    for item in exits:
        if not isinstance(item, dict):
            continue
        check = str(item.get("check") or "").strip()
        proves, perr = proving_test_rels(item)
        if perr or not proves:
            continue
        for rel in proves:
            dest = root / rel
            if not dest.is_file():
                if stage == "complete":
                    errs.append(
                        f"exit {check!r} proves {rel!r} missing on dest "
                        "(B-1 executable test refuse)"
                    )
                continue
            try:
                text = dest.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                errs.append(
                    f"exit {check!r} proves {rel!r} unreadable ({exc}) "
                    "(B-1 executable test refuse)"
                )
                continue
            if not _java_has_executable_test(text):
                errs.append(
                    f"exit {check!r} proves {rel!r} has no @Test "
                    "(B-1: a file with methods but no executable test fails the card)"
                )
                continue
            if need_surefire:
                fqcn = proves_to_fqcn(rel)
                if not fqcn or not _surefire_has_class(root, fqcn):
                    errs.append(
                        f"exit {check!r} proves {rel!r} did not appear in "
                        "target/surefire-reports (B-1 surefire refuse)"
                    )
    return errs


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
    """SR-13 / L2a: cmd must be able to fail *for this card's AC*.

    Static (no mvn on PATH — golden must not require it):
      * first token `true` / `:` → always succeeds → refuse
      * `mvn … test` must name `proves` test source(s) that sit in
        **this** `files_writable`. An unrelated dest `src/test` file must
        not satisfy the oracle (Deputy E-20260815T014500Z).
      * `mvn … compile` / `test-compile` are not test-shaped for L2a
        proves. `mvn … test` and `mvn … verify` must name `proves`.
        curl / scripts are not card exits (Operator 2026-08-16).
      * surefire `failIfNoTests=true` is not a mint recipe (L4).

    Provenance over mint-time Maven invocation.
    """
    errs: list[str] = []
    writable = _files_writable_rels(body)
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
            errs.append(
                f"exit {check!r} cmd {cmd!r} is not a Maven vehicle "
                "(SR-13: curl/scripts are not card exits; an HTTP AC is a "
                "@QuarkusTest in this write-set)"
            )
            continue
        if mvn_parts[-1] not in {"test", "verify"}:
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
    errs.extend(proves_executable_errors(root, body, stage="mint"))
    return errs
