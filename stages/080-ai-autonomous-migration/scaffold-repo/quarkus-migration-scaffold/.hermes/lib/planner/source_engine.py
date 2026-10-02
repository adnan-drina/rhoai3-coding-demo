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
