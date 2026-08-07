#!/usr/bin/env python3
"""O-HARVESTREADY — shared harvest compile-readiness signals (migration-general).

Architecture
------------
Harvest / rewrite work places Target ``.java`` on disk (O-HARVESTSTALL
preseed or worker). Readiness has two layers:

**Content (acceptance):** Spring residue must be cleared before tip
(O-SPRINGRESIDUE) via approved transforms (O-FIDELITYDAO / O-FIDELITYSORT).

**Classpath (compile):** implied Quarkus capabilities not yet on pom:

  org.springframework.* → spring-clean transforms          (O-HARVESTSPRING)
  jakarta.validation.*  → quarkus-hibernate-validator      (O-VALDEPADD)
  @Mapper / mapstruct   → mapstruct deps + jakarta-cdi     (O-MAPPRESEED)
  @Entity / hibernate   → jdbc + profiled db-kind          (O-DSKIND)

Shared signal detection + pom authorization live here;
``ensure-harvest-ready.py`` applies ensurers; ``task-stage-paths`` /
``exec-scope`` use ``needs_pom_stage`` so OWNSTAGE can tip pom dirt.

Do not add a new ensure script + supervisor ``if`` without registering it
in ``ensure-harvest-ready.py`` ENSURERS and extending ``collect_signals``.

Scaffold/create Targets (``package-info.java``, ``.gitkeep``) are **not**
harvest readiness — they use peer pipeline ``ensure-scaffold-ready.py``
(O-SCAFFOLDREADY). ``needs_pom_stage`` must never authorize pom for
scaffold-only Owns (focused scan must not inherit full-tree pom JPA).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

SIGNAL_SPRING = "spring"
SIGNAL_VALIDATION = "validation"
SIGNAL_MAPSTRUCT = "mapstruct"
SIGNAL_JPA = "jpa"

_ALL = frozenset(
    {SIGNAL_SPRING, SIGNAL_VALIDATION, SIGNAL_MAPSTRUCT, SIGNAL_JPA}
)


def _read_java(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def signals_from_text(text: str) -> set[str]:
    out: set[str] = set()
    if re.search(r"\borg\.springframework\b", text) or "PropertyComparator" in text:
        out.add(SIGNAL_SPRING)
    if re.search(r"\bjakarta\.validation\b", text):
        out.add(SIGNAL_VALIDATION)
    if "import org.mapstruct" in text or re.search(r"@Mapper\b", text):
        out.add(SIGNAL_MAPSTRUCT)
    if re.search(r"@Entity\b", text) or re.search(r"\bjakarta\.persistence\b", text):
        out.add(SIGNAL_JPA)
    return out


def collect_signals(
    root: Path, focus_paths: Iterable[str] | None = None
) -> frozenset[str]:
    """Scan focus .java paths, else all under ``src/``."""
    found: set[str] = set()
    paths: list[Path] = []
    if focus_paths is not None:
        for rel in focus_paths:
            if not str(rel).endswith(".java"):
                continue
            fp = root / rel if not Path(rel).is_absolute() else Path(rel)
            if fp.is_file():
                paths.append(fp)
    else:
        src = root / "src"
        if src.is_dir():
            paths.extend(src.rglob("*.java"))
    for fp in paths:
        found |= signals_from_text(_read_java(fp))
        if found >= _ALL:
            break
    # Full-tree scan only: pom hibernate-orm implies jpa for ensure-dskind.
    # Never when focusing OWNSTAGE paths — that falsely attached pom.xml to
    # package-info-only tasks (Wave5 T-008 OWNSTAGE 2 path-ops, empty tip).
    if focus_paths is None:
        pom = root / "pom.xml"
        if pom.is_file() and SIGNAL_JPA not in found:
            try:
                ptxt = pom.read_text(encoding="utf-8", errors="replace")
            except OSError:
                ptxt = ""
            if re.search(r"<artifactId>\s*quarkus-hibernate-orm", ptxt):
                found.add(SIGNAL_JPA)
    return frozenset(found)


def _scaffold_only(owned: list[str]) -> bool:
    """True when owned src paths are only package-info / .gitkeep (no entities)."""
    srcish = [
        p
        for p in owned
        if p.startswith("src/") and p != "pom.xml" and not p.startswith("k8s/")
    ]
    if not srcish:
        return False
    return all(
        p.endswith("package-info.java") or p.endswith(".gitkeep") for p in srcish
    )


def needs_pom_stage(root: Path, owned_paths: Iterable[str]) -> bool:
    """True when owned Targets imply a harvest-ready pom ensure.

    OWNSTAGE allowlists otherwise omit ``pom.xml`` → ensurer dirt stays
    unstaged while the .java tips alone → next compile RED / MiniMax.
    Scaffold-only tasks (package-info / .gitkeep) never authorize pom.
    """
    owned = [p for p in owned_paths if p]
    if "pom.xml" in owned:
        return True
    if _scaffold_only(owned):
        return False
    sigs = collect_signals(root, owned)
    return bool(sigs & {SIGNAL_VALIDATION, SIGNAL_MAPSTRUCT, SIGNAL_JPA})
