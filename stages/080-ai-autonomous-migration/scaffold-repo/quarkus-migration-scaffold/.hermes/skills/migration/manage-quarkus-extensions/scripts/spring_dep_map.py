#!/usr/bin/env python3
"""Parse spring-dep-to-extension.md — the only Spring→Quarkus map.

M1 emit and workers share this table. Do not keep a parallel dict in
emit-required-extensions.py.

Usage:
  python3 spring_dep_map.py                 # print map size
  python3 spring_dep_map.py --check         # fail if table unreadable
"""
from __future__ import annotations

import argparse
import re
import sys
from functools import lru_cache
from pathlib import Path

PLUGIN_AIDS = frozenset({"openapi-generator-maven-plugin"})
JDBC_GLOB = "quarkus-jdbc-*"
JDBC_URL_RE = re.compile(r"jdbc:([a-zA-Z0-9]+):")
CODE_RE = re.compile(r"`([^`]+)`")
NONE_RE = re.compile(r"^\s*none\s*$", re.I)

_TABLE_MD = (
    Path(__file__).resolve().parent.parent
    / "references"
    / "spring-dep-to-extension.md"
)


def kind_of(artifact_id: str) -> str:
    a = (artifact_id or "").strip()
    if a in PLUGIN_AIDS:
        return "plugin"
    return "extension"


def _parse_table(text: str) -> dict[str, tuple[str, ...]]:
    rows: dict[str, tuple[str, ...]] = {}
    in_table = False
    for line in text.splitlines():
        if not line.startswith("|"):
            if in_table:
                break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        if set(cells[0]) <= {"-", ":"} or cells[0].lower().startswith("legacy"):
            in_table = True
            continue
        in_table = True
        keys = CODE_RE.findall(cells[0])
        if not keys:
            continue
        raw_tgt = cells[1]
        if NONE_RE.match(raw_tgt) or raw_tgt.lower() == "none":
            targets: tuple[str, ...] = ()
        else:
            targets = tuple(
                t
                for t in CODE_RE.findall(raw_tgt)
                if t and not t.startswith("quarkus-spring-")
            )
        for key in keys:
            k = key.strip().lower()
            if k:
                rows[k] = targets
    return rows


@lru_cache(maxsize=1)
def load_map(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    p = path or _TABLE_MD
    text = p.read_text(encoding="utf-8")
    rows = _parse_table(text)
    if not rows:
        raise RuntimeError(f"empty Spring→Quarkus table {p}")
    return rows


def native_for_artifact(
    aid: str, mapping: dict[str, tuple[str, ...]] | None = None
) -> list[str]:
    a = (aid or "").strip().lower()
    if not a:
        return []
    table = mapping if mapping is not None else load_map()
    if a.startswith("quarkus-spring-"):
        return native_for_artifact(a[len("quarkus-") :], table)
    if a.startswith("quarkus-") or a in PLUGIN_AIDS:
        return [a]
    if a in table:
        return list(table[a])
    return []


def jdbc_urls_in_text(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for m in JDBC_URL_RE.finditer(text or ""):
        kind = m.group(1).strip().lower()
        key = f"jdbc:{kind}"
        if key not in seen:
            seen.add(key)
            found.append(key)
    return found


def scan_legacy_jdbc_keys(legacy_root: Path | None) -> list[str]:
    """JDBC URL kinds from the active Spring profile, not rglob order.

    `spring.profiles.active` is the native declaration. Profile-specific
    `application-{profile}.properties` (and `%profile.` keys in the base
    file) win. Filesystem order is only the fallback when no active
    profile is declared.
    """
    if legacy_root is None or not legacy_root.is_dir():
        return []

    def unique(keys: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for key in keys:
            if key not in seen:
                seen.add(key)
                out.append(key)
        return out

    def urls_from(path: Path) -> list[str]:
        try:
            return jdbc_urls_in_text(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            return []

    app_props: list[Path] = [
        p for p in legacy_root.rglob("application.properties") if p.is_file()
    ]
    active: list[str] = []
    base_text = ""
    for path in app_props:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = re.search(r"(?m)^spring\.profiles\.active\s*=\s*(.+)$", text)
        if m:
            active = [p.strip() for p in m.group(1).split(",") if p.strip()]
            base_text = text
            break

    if active:
        profile_keys: list[str] = []
        for profile in active:
            for path in legacy_root.rglob(f"application-{profile}.properties"):
                if path.is_file():
                    profile_keys.extend(urls_from(path))
            if base_text:
                for m in re.finditer(
                    rf"(?m)^%{re.escape(profile)}\.[^\n]*jdbc:([a-zA-Z0-9]+):",
                    base_text,
                ):
                    key = f"jdbc:{m.group(1).strip().lower()}"
                    profile_keys.append(key)
        return unique(profile_keys)

    found: list[str] = []
    seen: set[str] = set()
    for path in legacy_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".properties", ".yml", ".yaml", ".xml", ".env"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for key in jdbc_urls_in_text(text):
            if key not in seen:
                seen.add(key)
                found.append(key)
    return found


def expand_jdbc_glob(
    artifacts: set[str],
    jdbc_keys: list[str],
    mapping: dict[str, tuple[str, ...]] | None = None,
) -> tuple[set[str], str]:
    """Replace quarkus-jdbc-* with concrete drivers from jdbc:* table rows.

    Returns (artifacts, source_key). source_key empty if glob was not present.
    """
    table = mapping if mapping is not None else load_map()
    if JDBC_GLOB not in artifacts:
        return set(artifacts), ""
    out = {x for x in artifacts if x != JDBC_GLOB}
    drivers: list[str] = []
    source = ""
    for key in jdbc_keys:
        for tgt in table.get(key, ()):
            if tgt.startswith("quarkus-jdbc-") and tgt != JDBC_GLOB:
                if tgt not in drivers:
                    drivers.append(tgt)
                if not source:
                    source = key
    if not drivers:
        return out, source or "MISSING"
    out.update(drivers)
    return out, source


def entries_for(artifacts: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for aid in artifacts:
        a = (aid or "").strip()
        if not a or a in seen or a == JDBC_GLOB:
            continue
        if a.startswith("quarkus-spring-"):
            continue
        seen.add(a)
        out.append({"artifactId": a, "kind": kind_of(a)})
    return sorted(out, key=lambda r: r["artifactId"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    try:
        table = load_map()
    except (OSError, RuntimeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if "spring-boot-starter-jdbc" not in table:
        print("FAIL: table missing spring-boot-starter-jdbc", file=sys.stderr)
        return 1
    jdbc_tgts = table["spring-boot-starter-jdbc"]
    if "quarkus-agroal" not in jdbc_tgts or JDBC_GLOB not in jdbc_tgts:
        print(f"FAIL: jdbc starter maps to {jdbc_tgts}", file=sys.stderr)
        return 1
    if table.get("jdbc:hsqldb") != ("quarkus-jdbc-h2",):
        print(f"FAIL: jdbc:hsqldb row {table.get('jdbc:hsqldb')}", file=sys.stderr)
        return 1
    print(f"OK: spring-dep-to-extension.md n={len(table)}")
    return 0 if args.check or True else 0


if __name__ == "__main__":
    raise SystemExit(main())
