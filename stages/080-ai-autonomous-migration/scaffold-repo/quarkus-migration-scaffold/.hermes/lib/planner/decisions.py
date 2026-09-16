"""Load and validate `decisions.yaml` (SAD v3): the only human input.

Four things and nothing else:

- ``destination_platform``  the catalog id of the target platform (ADR)
- ``thresholds.max_attempts`` rejected attempts before a cluster becomes
                              a manual card (ADR)
- ``not_applicable``          work-list items an ADR retires (never inferred)
- ``retired_sources``         source files an ADR retires; the bootstrap
                              deletes exactly those (never imports them)
- ``security``                (optional, ADR-014) the source's security switch
                              and the identities the enabled-mode source
                              capture authenticates as, by REFERENCE only
- ``decided_repairs``         (optional, ADR-019) the versioned specimen
                              manifest of repairs accepted ADRs already made,
                              applied by the bootstrap before the loop baseline
                              (path + sha256; planner.decided_repairs)
- ``loop``                    (optional) how the loop forms and measures its
                              work: ``unit_formation: v1`` turns on the unit
                              former, absent keeps today's per-file
                              clustering; ``runtime_feedback: v1`` runs the
                              full scenario comparison once the destination
                              boots, absent leaves it to the parity cards

The planner reads decisions; it never writes or infers them. A required
decision that is null/empty is admission BLOCK ``MISSING_DECISION``; a
cited ADR that is not ``accepted`` is ``ADR_NOT_ACCEPTED``.
"""
from __future__ import annotations

import re
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
    gaps.extend(security_gaps(doc))
    # decided repairs applied at bootstrap (ADR-019): the shape of the decision;
    # whether they were APPLIED is admission's question (planner.decided_repairs)
    from planner.decided_repairs import section_gaps

    gaps.extend(section_gaps(doc, accepted_adrs(doc)))
    return gaps


# ---------------------------------------------------------------------------
# the source's security switch and the identities it is captured with (ADR-014)
# ---------------------------------------------------------------------------
# Who the enabled-mode source capture authenticates as is a DECISION, not a
# command line: an identity typed at a shell is not reviewable, does not
# survive the run and cannot be bound to an ADR. The Operator declares it here
# and the producers read it, so the same run is reproducible from the file.
#
# Nothing here is a credential. The switch is a configuration KEY and the two
# values that name its settings; an identity names the environment VARIABLE
# that holds ``user:password``. decisions.yaml is read, digested and copied
# into evidence, so a value that looks like a credential is refused rather
# than recorded -- and the refusal names the field, never what it holds.
SECURITY_SECTION = "security"
_SWITCH_FIELDS = (
    ("key", "the configuration property the source reads its security switch from"),
    ("disabled_value", "the value of that property that turns the source's security OFF"),
    ("enabled_value", "the value that turns it ON; the enabled-mode capture starts the source with it"),
)
# The policy the source applies to a request NO annotation names. A source
# whose enabled configuration requires authentication for every request
# guards its unannotated routes too, and a derivation that only walks the
# annotations would leave them unprobed -- which reads as "nothing to prove"
# rather than "not measured". Only the Operator can say which it is, so it is
# declared here, in the one file an ADR backs, and the derivation states the
# declaration on every scenario it derives from it.
REQUEST_POLICY_AUTHENTICATED = "authenticated"
REQUEST_POLICIES = (REQUEST_POLICY_AUTHENTICATED,)
# A separately recorded VARIANT of the source baseline: the declared dataset
# with the Operator's statements applied after it, captured on its own and
# followed by a restoration of the baseline. The statements are the
# SPECIMEN's -- opaque SQL to everything here, recorded verbatim because they
# are fixture SQL and not credentials -- and the name becomes a directory.
FIXTURE_SCENARIO_CLASSES = ("auth-allowed", "auth-anonymous", "auth-invalid", "auth-norole")
FIXTURE_INTENTS = ("refuse",)
_FIXTURE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _looks_like_a_value(text: str) -> bool:
    """A reference is the NAME of an environment variable. ``user:password``
    carries the separator, and a name with whitespace was never a variable
    name: either one is a credential pasted where its name belongs."""
    return ":" in text or any(c.isspace() for c in text)


def security_gaps(doc: dict[str, Any]) -> list[dict[str, str]]:
    """Why the declared ``security`` section may not be used; [] when it holds
    or when it is absent.

    Absent is not a gap: a specimen may have no security switch, and the
    enabled-mode M1 steps then record that as the reason they did nothing.
    Present and half-declared IS a gap, because the capture would otherwise
    start the source with a switch nobody named."""
    sec = doc.get(SECURITY_SECTION)
    if sec is None:
        return []
    gaps: list[dict[str, str]] = []

    def gap(cls: str, subject: str, detail: str) -> None:
        gaps.append({"class": cls, "subject": subject, "detail": detail})

    if not isinstance(sec, dict):
        gap("MISSING_DECISION", SECURITY_SECTION, "security must be a mapping of switch, identities and invalid_credential_ref")
        return gaps
    if not _adr_ok(doc, sec.get("adr")):
        gap("ADR_NOT_ACCEPTED", SECURITY_SECTION, "security cites %r which is not an accepted ADR" % sec.get("adr"))
    switch = sec.get("switch")
    if not isinstance(switch, dict):
        gap("MISSING_DECISION", "security.switch", "name the source's own security switch: key, disabled_value, enabled_value")
    else:
        for field, why in _SWITCH_FIELDS:
            if not str(switch.get(field) or "").strip():
                gap("MISSING_DECISION", "security.switch.%s" % field, why)
        if str(switch.get("disabled_value") or "") == str(switch.get("enabled_value") or "") and switch.get("enabled_value"):
            gap("MISSING_DECISION", "security.switch.enabled_value",
                "the two settings of the switch are the same value; they are two behaviours and must be two values")
    rows = sec.get("identities")
    if not isinstance(rows, list):
        gap("MISSING_DECISION", "security.identities",
            "declare the seeded identities the enabled-mode capture authenticates as, each by credential_ref")
        rows = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        where = "security.identities[%d]" % i
        if not isinstance(row, dict):
            gap("MISSING_DECISION", where, "an identity must be a mapping of name, credential_ref and roles")
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            gap("MISSING_DECISION", "%s.name" % where, "name the seeded identity as the source's own seed spells it")
        elif name in seen:
            gap("MISSING_DECISION", "%s.name" % where, "identity %r is declared twice" % name)
        else:
            seen.add(name)
        # the RAW value is what is judged: a name never carries whitespace, so
        # trimming first would accept one that was pasted from somewhere else
        ref = str(row.get("credential_ref") or "")
        if not ref.strip():
            gap("MISSING_DECISION", "%s.credential_ref" % where,
                "identity %s names no credential_ref; the capture cannot authenticate as it, and a credential is never written here"
                % (name or "(unnamed)"))
        elif _looks_like_a_value(ref):
            gap("SECURITY_LITERAL_CREDENTIAL", "%s.credential_ref" % where,
                "credential_ref of identity %s looks like a value, not the NAME of an environment variable; credentials are "
                "referenced, never recorded here" % (name or "(unnamed)"))
        roles = row.get("roles")
        if roles is not None and (not isinstance(roles, list) or not all(str(r).strip() for r in roles)):
            gap("MISSING_DECISION", "%s.roles" % where, "roles is the list of roles the seed gives this identity")
    invalid = sec.get("invalid_credential_ref")
    if invalid is not None and str(invalid) and _looks_like_a_value(str(invalid)):
        gap("SECURITY_LITERAL_CREDENTIAL", "security.invalid_credential_ref",
            "invalid_credential_ref looks like a value, not the NAME of an environment variable")
    policy = sec.get("request_policy")
    if policy is not None and str(policy).strip() and str(policy).strip() not in REQUEST_POLICIES:
        gap("MISSING_DECISION", "security.request_policy",
            "request_policy %r is not one of %s; it says what the source's enabled configuration requires of a request no "
            "annotation names, and a value nothing implements would leave those routes unprobed"
            % (policy, ", ".join(REQUEST_POLICIES)))
    gaps.extend(_fixture_gaps(sec))
    return gaps


def _fixture_gaps(sec: dict[str, Any]) -> list[dict[str, str]]:
    """Why the declared ``security.fixtures`` may not be used; [] when they
    hold or when none are declared.

    Every field is checked as what it IS: the name becomes a directory, the
    statements are opaque SQL this loader never parses (only that there is at
    least one, and that each is a non-empty string), the scenario class names
    a class of derived scenario, and dataset_config_key is the configuration
    KEY the source reads its dataset location from."""
    gaps: list[dict[str, str]] = []

    def gap(cls: str, subject: str, detail: str) -> None:
        gaps.append({"class": cls, "subject": subject, "detail": detail})

    rows = sec.get("fixtures")
    if rows is None:
        return gaps
    if not isinstance(rows, list):
        gap("MISSING_DECISION", "security.fixtures",
            "fixtures is the list of separately recorded variants of the source baseline, each with a name, the statements "
            "it applies after the declared dataset, the scenario class it varies and the configuration key the dataset "
            "location is passed through")
        return gaps
    seen: set[str] = set()
    for i, row in enumerate(rows):
        where = "security.fixtures[%d]" % i
        if not isinstance(row, dict):
            gap("MISSING_DECISION", where, "a fixture is a mapping of name, statements, scenarios and dataset_config_key")
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            gap("MISSING_DECISION", "%s.name" % where, "name the variant; its name is the directory its captures live in")
        elif not _FIXTURE_NAME.match(name):
            gap("MISSING_DECISION", "%s.name" % where,
                "fixture name %r is not a name a directory can carry (a-z, 0-9 and -, starting with a letter or digit)" % name)
        elif name in seen:
            gap("MISSING_DECISION", "%s.name" % where, "fixture %r is declared twice" % name)
        else:
            seen.add(name)
        statements = row.get("statements")
        if not isinstance(statements, list) or not statements:
            gap("MISSING_DECISION", "%s.statements" % where,
                "declare the statements this variant applies AFTER the declared dataset; they are the specimen's own SQL and "
                "nothing here interprets them")
        elif not all(isinstance(s, str) and s.strip() for s in statements):
            gap("MISSING_DECISION", "%s.statements" % where, "every statement is a non-empty string")
        scenarios = str(row.get("scenarios") or "").strip()
        if not scenarios:
            gap("MISSING_DECISION", "%s.scenarios" % where,
                "name the class of derived scenario this variant is recorded for (%s)" % ", ".join(FIXTURE_SCENARIO_CLASSES))
        elif scenarios not in FIXTURE_SCENARIO_CLASSES:
            gap("MISSING_DECISION", "%s.scenarios" % where,
                "scenarios %r is not one of %s" % (scenarios, ", ".join(FIXTURE_SCENARIO_CLASSES)))
        key = str(row.get("dataset_config_key") or "")
        if not key.strip():
            gap("MISSING_DECISION", "%s.dataset_config_key" % where,
                "name the configuration property the source reads its dataset location from; the variant capture starts the "
                "source with it pointed at the variant dataset")
        elif _looks_like_a_value(key):
            gap("MISSING_DECISION", "%s.dataset_config_key" % where,
                "dataset_config_key is a configuration property NAME, and this one carries a separator or whitespace")
        intent = row.get("intent")
        if intent is not None and str(intent).strip() and str(intent).strip() not in FIXTURE_INTENTS:
            gap("MISSING_DECISION", "%s.intent" % where,
                "intent %r is not one of %s; an intent nobody declared means the variant expects whatever the source "
                "answers, which is the honest default" % (intent, ", ".join(FIXTURE_INTENTS)))
    return gaps


def security(doc: dict[str, Any]) -> dict[str, Any]:
    """The decided security switch and identities, or {} when they are not
    decided (absent, or declared in a shape the loader refuses).

    Callers get a normalised shape: ``{"switch": {...}, "identities":
    [{"name", "credential_ref", "roles": [...]}], "invalid_credential_ref",
    "request_policy", "fixtures": [{"name", "statements", "scenarios",
    "dataset_config_key", "intent"}], "adr"}``. Roles, the statements and the
    declared intent are the only values; everything else is a key or a name."""
    sec = doc.get(SECURITY_SECTION)
    if not isinstance(sec, dict) or security_gaps(doc):
        return {}
    switch = sec.get("switch") or {}
    return {
        "adr": str(sec.get("adr") or ""),
        "switch": {field: str(switch.get(field) or "") for field, _why in _SWITCH_FIELDS},
        "identities": [{"name": str(r.get("name") or ""), "credential_ref": str(r.get("credential_ref") or ""),
                        "roles": [str(x) for x in (r.get("roles") or [])]}
                       for r in (sec.get("identities") or []) if isinstance(r, dict)],
        "invalid_credential_ref": str(sec.get("invalid_credential_ref") or ""),
        "request_policy": str(sec.get("request_policy") or "").strip(),
        "fixtures": [{"name": str(r.get("name") or "").strip(),
                      "statements": [str(s) for s in (r.get("statements") or [])],
                      "scenarios": str(r.get("scenarios") or "").strip(),
                      "dataset_config_key": str(r.get("dataset_config_key") or "").strip(),
                      "intent": str(r.get("intent") or "").strip()}
                     for r in (sec.get("fixtures") or []) if isinstance(r, dict)],
    }


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


# ---------------------------------------------------------------------------
# how the loop forms its work (design of 2026-09-15 §5.1)
# ---------------------------------------------------------------------------
# A mode, not a threshold: it changes which CARDS exist, so it is a decision
# and it is sealed on the admission receipt with the rest of this file. Absent
# is a decision too -- it means today's per-file clustering, which is what
# keeps a run that is already under way byte-for-byte unchanged.
LOOP_SECTION = "loop"
UNIT_FORMATION_V1 = "v1"
UNIT_FORMATION_OFF = "off"
# Whether the loop feeds RUNTIME behaviour back into its own work list. v1 runs
# the full scenario comparison once the destination boots, so a behavioural
# failure enters the next work-list rebuild as a parity obligation immediately
# instead of waiting for M4. Absent is off, which is the v9 behaviour: the
# comparison runs only for a card whose obligation is already a parity
# mismatch.
RUNTIME_FEEDBACK_V1 = "v1"
RUNTIME_FEEDBACK_OFF = "off"


def loop_modes(doc: dict[str, Any]) -> dict[str, str]:
    """The decided loop modes, normalised. Unknown or absent values fall back
    to the mode that changes nothing, never to the new one."""
    section = doc.get(LOOP_SECTION)
    section = section if isinstance(section, dict) else {}
    formation = str(section.get("unit_formation") or "").strip()
    feedback = str(section.get("runtime_feedback") or "").strip()
    return {"unit_formation": UNIT_FORMATION_V1 if formation == UNIT_FORMATION_V1 else UNIT_FORMATION_OFF,
            "runtime_feedback": RUNTIME_FEEDBACK_V1 if feedback == RUNTIME_FEEDBACK_V1 else RUNTIME_FEEDBACK_OFF}


def unit_formation(doc: dict[str, Any]) -> str:
    """decisions.loop.unit_formation: "v1" or "off"."""
    return loop_modes(doc)["unit_formation"]


def runtime_feedback(doc: dict[str, Any]) -> str:
    """decisions.loop.runtime_feedback: "v1" or "off"."""
    return loop_modes(doc)["runtime_feedback"]


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
