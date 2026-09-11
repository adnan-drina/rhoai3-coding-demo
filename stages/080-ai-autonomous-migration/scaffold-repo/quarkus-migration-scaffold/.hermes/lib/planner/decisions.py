"""Load and validate `decisions.yaml` (SAD v3): the only human input.

Four things and nothing else:

- ``destination_platform``  the catalog id of the target platform (ADR)
- ``thresholds.max_attempts`` rejected attempts before a cluster becomes
                              a manual card (ADR)
- ``not_applicable``          work-list items an ADR retires (never inferred)
- ``retired_sources``         source files an ADR retires; the bootstrap
                              deletes exactly those (never imports them)

The planner reads decisions; it never writes or infers them. A required
decision that is null/empty is admission BLOCK ``MISSING_DECISION``; a
cited ADR that is not ``accepted`` is ``ADR_NOT_ACCEPTED``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from planner.canonical import load_json
from planner.paths import CATALOGS_DIR, DECISIONS, SCHEMAS_DIR
from planner.schema_lite import load_schema, validate
from planner.yamlite import YamlLiteError, load_yaml

DEFAULT_MAX_ATTEMPTS = 3


class DecisionsError(ValueError):
    pass


def load_decisions(root: Path) -> dict[str, Any]:
    root = Path(root)
    path = root / DECISIONS
    if not path.is_file():
        raise DecisionsError("missing %s (copy .hermes/planning/decisions.example.yaml)" % DECISIONS)
    try:
        doc = load_yaml(path)
    except YamlLiteError as exc:
        raise DecisionsError("%s: %s" % (DECISIONS, exc)) from exc
    if not isinstance(doc, dict):
        raise DecisionsError("%s: root must be a mapping" % DECISIONS)
    errors = validate(doc, load_schema(root / SCHEMAS_DIR / "decisions.schema.json"))
    if errors:
        raise DecisionsError("%s: %s" % (DECISIONS, "; ".join(errors)))
    return doc


def accepted_adrs(doc: dict[str, Any]) -> set[str]:
    return {str(a.get("id")) for a in (doc.get("adrs") or []) if isinstance(a, dict) and str(a.get("status")) == "accepted"}


def _adr_ok(doc: dict[str, Any], adr: Any) -> bool:
    return isinstance(adr, str) and adr in accepted_adrs(doc)


def known_platforms(root: Path) -> dict[str, Any]:
    doc = load_json(Path(root) / CATALOGS_DIR / "destination-platforms.json")
    return doc.get("platforms") or {}


def missing_decisions(doc: dict[str, Any], root: Path) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []

    def gap(cls: str, subject: str, detail: str) -> None:
        gaps.append({"class": cls, "subject": subject, "detail": detail})

    plat = doc.get("destination_platform") or {}
    pid = plat.get("id")
    if not pid:
        gap("MISSING_DECISION", "destination_platform.id", "name a platform from .hermes/planning/catalogs/destination-platforms.json")
    else:
        if pid not in known_platforms(root):
            gap("PLATFORM_UNKNOWN", "destination_platform.id", "%r is not in destination-platforms.json" % pid)
        if not _adr_ok(doc, plat.get("adr")):
            gap("ADR_NOT_ACCEPTED", "destination_platform", "platform cites %r which is not an accepted ADR" % plat.get("adr"))
    th = doc.get("thresholds") or {}
    if th.get("max_attempts") is None:
        gap("MISSING_DECISION", "thresholds.max_attempts", "set the rejected-attempt threshold after which a cluster becomes a manual card")
    elif not _adr_ok(doc, th.get("adr")):
        gap("ADR_NOT_ACCEPTED", "thresholds", "thresholds cite %r which is not an accepted ADR" % th.get("adr"))
    for i, row in enumerate(doc.get("not_applicable") or []):
        if not _adr_ok(doc, row.get("adr")):
            gap("ADR_NOT_ACCEPTED", "not_applicable[%d]" % i, "entry cites %r which is not an accepted ADR" % row.get("adr"))
    for i, row in enumerate(doc.get("retired_sources") or []):
        if not _adr_ok(doc, row.get("adr")):
            gap("ADR_NOT_ACCEPTED", "retired_sources[%d]" % i, "entry cites %r which is not an accepted ADR" % row.get("adr"))
    # The datasource is an architectural input, not something a worker discovers
    # at runtime: an undecided or half-decided one keeps admission INCONCLUSIVE,
    # so no card is minted against it (pilot v7 reached an empty work list with
    # no default datasource configured and could not be built at all).
    ds = doc.get("datasource")
    if not isinstance(ds, dict) or not ds.get("db_kind"):
        gap("MISSING_DECISION", "datasource", "name the destination's effective database: db_kind, version, matching JDBC extension, profile, isolated instance, credential references, reset procedure, schema and seed ownership")
    else:
        if not _adr_ok(doc, ds.get("adr")):
            gap("ADR_NOT_ACCEPTED", "datasource", "datasource cites %r which is not an accepted ADR" % ds.get("adr"))
        for field, why in DATASOURCE_FIELDS:
            if not str(ds.get(field) or "").strip():
                gap("MISSING_DECISION", "datasource.%s" % field, why)
        kinds = known_db_kinds(root)
        kind = str(ds.get("db_kind") or "")
        if kind and kind not in kinds:
            gap("DATASOURCE_UNSUPPORTED", "datasource.db_kind", "%r has no row in compat-mapping.json datasources.db_kinds; the destination platform documents no JDBC extension for it (the frozen source engine may have none, which is why source_baseline_db_kind is recorded separately)" % kind)
        elif kind and str(ds.get("jdbc_extension") or "") != str(kinds[kind].get("extension") or ""):
            gap("DATASOURCE_EXTENSION_MISMATCH", "datasource.jdbc_extension", "%s is documented for db_kind %s, the decision names %r" % (kinds[kind].get("extension"), kind, ds.get("jdbc_extension")))
        for field in ("jdbc_url_env", "username_env", "password_env"):
            value = str(ds.get(field) or "")
            if value and (":" in value or "/" in value or value != value.strip()):
                gap("DATASOURCE_LITERAL_SECRET", "datasource.%s" % field, "%r looks like a value, not the NAME of an environment variable; credentials are referenced, never recorded here" % value)
        if str(ds.get("schema_owner") or "") == "source-assets" and not (str(ds.get("schema_sql") or "").strip() and str(ds.get("seed_sql") or "").strip()):
            gap("MISSING_DECISION", "datasource.schema_sql", "schema_owner source-assets must name the schema and seed files the source provides")
    return gaps


DATASOURCE_FIELDS = (
    ("db_kind", "quarkus.datasource.db-kind for the destination"),
    ("db_version", "the approved database version"),
    ("jdbc_extension", "groupId:artifactId of the matching Quarkus JDBC extension"),
    ("profile", "the build and run profile this configuration is selected under"),
    ("instance", "the isolated test instance this run uses"),
    ("jdbc_url_env", "the environment variable holding the JDBC URL (never a literal URL)"),
    ("username_env", "the environment variable holding the user"),
    ("password_env", "the environment variable holding the password"),
    ("reset_procedure", "how the instance returns to its initial state between scenario runs"),
    ("schema_owner", "who owns schema and seed (source assets, destination ORM, or a named migration tool)"),
    ("hibernate_generation", "quarkus.hibernate-orm.database.generation"),
    ("source_baseline_db_kind", "the engine the frozen source ran on, kept so its baseline is not rewritten"),
)


def datasource(doc: dict[str, Any]) -> dict[str, Any]:
    """The decided effective datasource, or {} when it is not decided."""
    ds = doc.get("datasource")
    if not isinstance(ds, dict) or not ds.get("db_kind") or not _adr_ok(doc, ds.get("adr")):
        return {}
    return dict(ds)


def build_profiles(doc: dict[str, Any]) -> dict[str, Any]:
    """The decided build profiles, or {} when they are not decided.

    A profile is not decoration: the legacy chose which implementation exists
    with spring.profiles.active, and the platform resolves @IfBuildProfile at
    build time. A destination that activates none of the profiles its own
    sources are gated on has no implementations at all, which is what stalled
    pilot v7 at the packaging gate."""
    bp = doc.get("build_profiles")
    if not isinstance(bp, dict) or not _adr_ok(doc, bp.get("adr")):
        return {}
    if not bp.get("active") and not bp.get("retire_gates"):
        return {}
    return dict(bp)


def retired_profile_gates(doc: dict[str, Any]) -> list[dict[str, str]]:
    """The profile conditions an accepted ADR retires, one row per condition.

    A blanket "retire the gates" is not a decision anyone can review: it
    absorbs whatever the tree contains on the day it runs. An enumeration can
    be read, diffed, and refused when the tree moved under it."""
    bp = doc.get("build_profiles")
    if not isinstance(bp, dict) or not _adr_ok(doc, bp.get("adr")):
        return []
    out: list[dict[str, str]] = []
    for row in bp.get("retire") or []:
        if not isinstance(row, dict):
            continue
        if not (row.get("path") and row.get("type") and row.get("annotation") and row.get("profile")):
            continue
        out.append({
            "path": str(row["path"]).replace("\\", "/").lstrip("/"),
            "type": str(row["type"]),
            "member": str(row.get("member") or ""),
            "annotation": str(row["annotation"]).lstrip("@").rsplit(".", 1)[-1],
            "profile": str(row["profile"]),
            "reason": str(row.get("reason") or ""),
            "adr": str(bp.get("adr") or ""),
        })
    return out


def retirement_inventory_sha256(doc: dict[str, Any]) -> str:
    bp = doc.get("build_profiles")
    return str(bp.get("inventory_sha256") or "") if isinstance(bp, dict) else ""


def known_db_kinds(root: Path) -> dict[str, Any]:
    doc = load_json(Path(root) / CATALOGS_DIR / "compat-mapping.json")
    return (doc.get("datasources") or {}).get("db_kinds") or {}


def retired_sources(doc: dict[str, Any]) -> dict[str, str]:
    """relative source path → ADR for files an accepted ADR retires."""
    out: dict[str, str] = {}
    for row in doc.get("retired_sources") or []:
        if isinstance(row, dict) and row.get("path") and _adr_ok(doc, row.get("adr")):
            out[str(row["path"]).replace("\\", "/").lstrip("/")] = str(row["adr"])
    return out


def max_attempts(doc: dict[str, Any]) -> int:
    th = doc.get("thresholds") or {}
    try:
        return int(th.get("max_attempts") or DEFAULT_MAX_ATTEMPTS)
    except (TypeError, ValueError):
        return DEFAULT_MAX_ATTEMPTS


def not_applicable_ids(doc: dict[str, Any]) -> dict[str, str]:
    """work-list item id → ADR for items an accepted ADR retires."""
    out: dict[str, str] = {}
    for row in doc.get("not_applicable") or []:
        if isinstance(row, dict) and row.get("item_id") and _adr_ok(doc, row.get("adr")):
            out[str(row["item_id"])] = str(row["adr"])
    return out


def waivers(doc: dict[str, Any]) -> list[dict[str, str]]:
    """not_applicable rows an accepted ADR backs, by obligation (rule_id [+ path])
    or by item id. A content-hash item id changes when the fix re-words the
    incident; the obligation form (rule on a file) is the stable one."""
    out: list[dict[str, str]] = []
    for row in doc.get("not_applicable") or []:
        if not isinstance(row, dict) or not _adr_ok(doc, row.get("adr")):
            continue
        if not (row.get("item_id") or row.get("rule_id")):
            continue
        out.append({"item_id": str(row.get("item_id") or ""), "rule_id": str(row.get("rule_id") or ""),
                    "path": str(row.get("path") or "").replace("\\", "/").lstrip("/"), "adr": str(row["adr"]), "reason": str(row.get("reason") or "")})
    return out


def superseded_rules(doc: dict[str, Any], root: Path) -> dict[str, dict[str, str]]:
    """rule id → {requires_present, reason} the decided platform supersedes (catalog fact, never inferred)."""
    plat = (doc.get("destination_platform") or {}).get("id")
    if not plat:
        return {}
    try:
        rows = (known_platforms(root).get(str(plat)) or {}).get("superseded_rules") or {}
    except (OSError, ValueError):
        return {}
    return {k: {"requires_present": str(v.get("requires_present") or ""), "reason": str(v.get("reason") or "")} for k, v in rows.items() if k != "note" and isinstance(v, dict)}
