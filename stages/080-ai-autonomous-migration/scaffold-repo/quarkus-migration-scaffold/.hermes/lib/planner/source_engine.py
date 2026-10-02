"""Which database engine the frozen source is captured on, and which seed it reads (D-1, ADR-027 draft; v31).

v31 captured the source on its own default in-memory HSQLDB while the destination ran on PostgreSQL: unordered rows came
back in primary-key order on one and heap order on the other, and the provider messages differed -- differences no
source code made. Decision D-1 (2026-10-02): when the frozen source ships a configuration profile for the destination's
engine, capture the source on THAT engine.

``datasource.source_capture_engine`` (decisions.yaml):
  declared     (default until the server-engine capture path is qualified) the engine the source's own selected
               profiles run on, recorded as ``source_baseline_db_kind`` (ADR-017)
  destination  the destination's ``db_kind``, with the source's profile for it -- only when the frozen source ships one
               (``src/main/resources/application-<engine>.properties|yml|yaml``); otherwise the declared engine, with
               the reason named (engine artifacts remain possible)

One rule for the seed as well: the selected engine's ``db/<engine>/populateDB.sql``, then the default, then any --
used by the scenario derivation and the destination baseline alike, so the corpus and the reset never disagree.
Nothing here knows a specimen.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

RESOURCES = Path("src") / "main" / "resources"
SEED_BASENAME = "populateDB.sql"
DEFAULT_ENGINE = "hsqldb"
MODES = ("declared", "destination")
PROFILE_SUFFIXES = (".properties", ".yml", ".yaml")


def source_profile_for(copy: Path | None, engine: str) -> str:
    """The source's own profile file for ``engine`` (relative), or ''."""
    if copy is None or not engine:
        return ""
    for suf in PROFILE_SUFFIXES:
        rel = RESOURCES / ("application-%s%s" % (engine, suf))
        if (Path(copy) / rel).is_file():
            return rel.as_posix()
    return ""


def capture_engine(datasource: dict[str, Any] | None, copy: Path | None = None) -> dict[str, Any]:
    """{"engine", "mode", "profile", "profile_file", "why"} for the source capture."""
    ds = datasource or {}
    declared = str(ds.get("source_baseline_db_kind") or "")
    dest = str(ds.get("db_kind") or "")
    mode = str(ds.get("source_capture_engine") or "declared")
    if mode not in MODES:
        mode = "declared"
    if mode == "destination" and dest:
        pf = source_profile_for(copy, dest)
        if pf:
            return {"engine": dest, "mode": mode, "profile": dest, "profile_file": pf,
                    "why": "captured on the destination's engine through the source's own %s profile (%s)" % (dest, pf)}
        return {"engine": declared, "mode": "declared", "profile": "", "profile_file": "",
                "why": ("the frozen source ships no profile for the destination engine %s: captured on its declared "
                        "engine %s; engine artifacts (unordered rows, provider messages) remain possible" % (dest, declared or "?"))}
    return {"engine": declared, "mode": "declared", "profile": "", "profile_file": "",
            "why": "captured on the source's declared engine %s (ADR-017)" % (declared or "?")}


def seed(base: Path, engine: str) -> tuple[Path | None, str]:
    """(the seed file, the engine directory it was read from): the selected engine, then the default, then any."""
    db = Path(base) / RESOURCES / "db"
    if not db.is_dir():
        return None, ""
    for name in [engine, DEFAULT_ENGINE] + sorted(d.name for d in db.iterdir() if d.is_dir()):
        if name and (db / name / SEED_BASENAME).is_file():
            return db / name / SEED_BASENAME, name
    return None, ""


# ---- D-1 increment 2: the server-engine capture plan --------------------------------------------------------------
# The source is captured in a schema of ITS OWN on the run's own parity database (the same instance, ownership check
# and credentials the destination's reset uses -- ADR-022), reloaded from the frozen source's own per-engine scripts
# before every start. The process is still restarted per scenario: identifier pools and caches live in it.

CAPTURE_SCHEMA = "source_oracle"
# How an engine's JDBC URL selects a schema. An engine missing here is not captured on (the reason is named).
SCHEMA_URL_PARAM = {"postgresql": "currentSchema"}
# Engines a source profile can be named for; a profile so named that the source ships is an ENGINE profile.
ENGINE_NAMES = ("postgresql", "postgres", "mysql", "mariadb", "mssql", "sqlserver", "oracle", "db2", "hsqldb", "h2", "derby")
SCHEMA_LOCATIONS_KEY = "spring.sql.init.schema-locations"
PROFILES_KEY = "spring.profiles.active"
# Spring Boot binds these environment names to spring.datasource.* and spring.profiles.active with a higher
# precedence than the source's own properties files; values travel by environment, never argv or evidence.
SPRING_ENV = {"profiles": "SPRING_PROFILES_ACTIVE", "url": "SPRING_DATASOURCE_URL",
              "user": "SPRING_DATASOURCE_USERNAME", "password": "SPRING_DATASOURCE_PASSWORD"}


def _properties(path: Path) -> dict[str, str]:
    """key -> value of a .properties file (uncommented lines only)."""
    out: dict[str, str] = {}
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        s = line.strip()
        if not s or s[0] in "#!":
            continue
        for sep in ("=", ":"):
            if sep in s:
                k, v = s.split(sep, 1)
                out.setdefault(k.strip(), v.strip())
                break
    return out


def _yaml_key(path: Path, dotted: str) -> str:
    """A scalar at a dotted key of a simple YAML file, or ''."""
    try:
        import yaml  # noqa: PLC0415
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return ""
    for part in dotted.split("."):
        if not isinstance(doc, dict) or part not in doc:
            return ""
        doc = doc[part]
    if isinstance(doc, list):
        return ",".join(str(x) for x in doc)
    return "" if isinstance(doc, dict) or doc is None else str(doc)


def config_value(copy: Path, key: str, profile: str = "") -> str:
    """The value of ``key`` in the source's own application[-profile] configuration, or ''."""
    stem = "application-%s" % profile if profile else "application"
    for suf in PROFILE_SUFFIXES:
        p = Path(copy) / RESOURCES / (stem + suf)
        if p.is_file():
            v = _properties(p).get(key, "") if suf == ".properties" else _yaml_key(p, key)
            if v:
                return v
    return ""


def capture_profiles(copy: Path, engine: str) -> list[str]:
    """The source's own active profiles with its ENGINE profile replaced by ``engine``'s (order kept)."""
    active = [p.strip() for p in config_value(copy, PROFILES_KEY).split(",") if p.strip()]
    kept = [p for p in active if not (p.lower() in ENGINE_NAMES and source_profile_for(copy, p))]
    return [engine] + [p for p in kept if p != engine]


def schema_script(copy: Path, engine: str) -> tuple[Path | None, str]:
    """(the source's own schema script for ``engine``, how it was found): the engine profile's declared
    ``spring.sql.init.schema-locations`` (classpath: resolved under src/main/resources) first; otherwise the one
    script beside the engine's seed that creates tables. Ambiguity or absence -> (None, why)."""
    declared = config_value(copy, SCHEMA_LOCATIONS_KEY, engine)
    for loc in [x.strip() for x in declared.split(",") if x.strip()]:
        rel = loc.split(":", 1)[1] if ":" in loc else loc
        rel = rel.lstrip("*").lstrip("/")
        p = Path(copy) / RESOURCES / rel
        if p.is_file():
            return p, "declared by the %s profile (%s)" % (engine, SCHEMA_LOCATIONS_KEY)
    d = Path(copy) / RESOURCES / "db" / engine
    if not d.is_dir():
        return None, "the frozen source has no db/%s directory" % engine
    hits = []
    for f in sorted(d.glob("*.sql")):
        if f.name == SEED_BASENAME:
            continue
        try:
            if "create table" in f.read_text(encoding="utf-8", errors="replace").lower():
                hits.append(f)
        except OSError:
            continue
    if len(hits) == 1:
        return hits[0], "the one table-creating script in db/%s" % engine
    if not hits:
        return None, "no table-creating script in db/%s" % engine
    return None, "%d table-creating scripts in db/%s (%s); which one the source applies is not decidable" % (
        len(hits), engine, ", ".join(h.name for h in hits))


def with_schema(url: str, engine: str, schema: str) -> str:
    """``url`` selecting ``schema`` through the engine's own URL parameter (an existing one is replaced)."""
    param = SCHEMA_URL_PARAM[engine]
    base, _, query = str(url).partition("?")
    kept = [q for q in query.split("&") if q and q.split("=", 1)[0] != param]
    return base + "?" + "&".join(kept + ["%s=%s" % (param, schema)])


def server_capture(datasource: dict[str, Any] | None, copy: Path, environ: dict[str, str]) -> dict[str, Any]:
    """The plan for capturing the frozen source on the destination's server engine, or {"refused": why}.

    {"engine", "profiles", "schema", "schema_sql", "seed_sql", "found", "env_names", "env"}: ``env`` holds the
    values to start the source with (credentials among them) and is NEVER recorded; ``env_names`` is."""
    plan = capture_engine(datasource, copy)
    if plan["mode"] != "destination":
        return {"refused": plan["why"]}
    engine = plan["engine"]
    if engine not in SCHEMA_URL_PARAM:
        return {"refused": "capture on %s is not supported (no schema selection known for it)" % engine}
    pom = Path(copy) / "pom.xml"
    try:
        spring_boot = "spring-boot" in pom.read_text(encoding="utf-8", errors="replace")
    except OSError:
        spring_boot = False
    if not spring_boot:
        return {"refused": "the frozen source is not a Spring Boot build; its datasource cannot be bound by environment"}
    schema_p, found = schema_script(copy, engine)
    if schema_p is None:
        return {"refused": found}
    seed_p, seed_engine = seed(copy, engine)
    if seed_p is None or seed_engine != engine:
        return {"refused": "the frozen source ships no %s seed for %s" % (SEED_BASENAME, engine)}
    ds = datasource or {}
    names = {"url": str(ds.get("jdbc_url_env") or ""), "user": str(ds.get("username_env") or ""),
             "password": str(ds.get("password_env") or "")}
    missing = sorted(n for n in names.values() if not n or not environ.get(n))
    if missing or not all(names.values()):
        return {"refused": "the run's datasource credentials are not in this environment (%s)" % (", ".join(missing) or "unnamed")}
    url = str(environ[names["url"]])
    if not url.startswith("jdbc:%s:" % engine):
        return {"refused": "%s is not a %s JDBC URL" % (names["url"], engine)}
    profiles = capture_profiles(copy, engine)
    env = {SPRING_ENV["profiles"]: ",".join(profiles), SPRING_ENV["url"]: with_schema(url, engine, CAPTURE_SCHEMA),
           SPRING_ENV["user"]: str(environ[names["user"]]), SPRING_ENV["password"]: str(environ[names["password"]])}
    return {"engine": engine, "profiles": profiles, "schema": CAPTURE_SCHEMA,
            "schema_sql": schema_p.relative_to(copy).as_posix(), "seed_sql": seed_p.relative_to(copy).as_posix(),
            "found": found, "profile_file": plan["profile_file"], "why": plan["why"],
            "env_names": sorted(env), "datasource_env": names, "env": env}


_SEQ_RESTART_RE = __import__("re").compile(
    r"\bALTER\s+SEQUENCE\s+(?:IF\s+EXISTS\s+)?\"?([A-Za-z_][A-Za-z0-9_]*)\"?\s+(?:RESTART|START)\s+(?:WITH\s+)?(\d+)",
    __import__("re").IGNORECASE)


def sequence_starts(schema_text: str) -> dict[str, int]:
    """sequence name -> the value it is (re)started at, from a schema's ``ALTER SEQUENCE ... RESTART WITH n``.

    A serial column's sequence is named ``<table>_<column>_seq`` by PostgreSQL (``serial_sequence``); the value is
    the identity the engine generates NEXT, whatever the seed inserted explicitly (explicit ids do not advance it)."""
    return {m.group(1).lower(): int(m.group(2)) for m in _SEQ_RESTART_RE.finditer(str(schema_text or ""))}


def serial_sequence(table: str, column: str) -> str:
    return ("%s_%s_seq" % (table, column)).lower()
