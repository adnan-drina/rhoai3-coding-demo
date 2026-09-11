#!/usr/bin/env python3
"""Refuse a destination whose effective datasource is not the decided one (M2).

The decision lives in decisions.yaml (`datasource`, under an accepted ADR) and
is rendered by bootstrap-destination. This checker measures the rendered tree
against the decision, at M2, before any worker reaches runtime verification:

  * the values the platform would resolve FOR THE SELECTED PROFILE must equal
    the decision. A %profile-prefixed key overrides the unprefixed one when
    that profile is active, so both are read and the override wins; and a
    key for a DIFFERENT profile that would point at another database is
    reported, because nothing stops that profile being selected at run time.
    An unprefixed key must still be present: the platform resolves the
    datasource at build time, and pilot v7 reached an empty work list with
    only %hsqldb.* keys and then failed augmentation with "Datasource
    <default> is not configured";
  * the JDBC extension documented for the decided db_kind must be in the pom,
    and no OTHER db-kind extension may be there. Not because the platform
    could not choose -- db-kind is set, so it can -- but because a driver the
    decision never selected has no reason to be in the build, and the
    bootstrap is what must not leave it behind;
  * credentials must be environment references, never literals in the tree;
  * when the decision says the source assets own schema and seed, those files
    must exist in the destination.

It does not prove the configuration works. Packaging and boot verification do
that, and neither replaces the other.

Exit 0 PASS, 1 REFUSE, 2 usage."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: DATASOURCE .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.canonical import load_json  # noqa: E402
from planner.decisions import DecisionsError, datasource, load_decisions, missing_decisions  # noqa: E402
from planner.paths import CATALOGS_DIR, DECISIONS  # noqa: E402


def _all_profile_keys(root: Path) -> list[str]:
    p = root / "src" / "main" / "resources" / "application.properties"
    if not p.is_file():
        return []
    out = []
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if s.startswith("%") and "=" in s and not s.startswith(("#", "!")):
            out.append(s.partition("=")[0].strip())
    return out


def _refuse(findings: list[str]) -> int:
    for f in findings:
        print("  - %s" % f, file=sys.stderr)
    print("REFUSE: DATASOURCE_DECISION (%d finding(s))" % len(findings), file=sys.stderr)
    return 1


def effective_properties(root: Path, profile: str) -> tuple[dict[str, str], dict[str, str]]:
    """(effective values for the selected profile, where each came from).

    A %profile-prefixed key is NOT inert: when that profile is active the
    platform prefers it over the unprefixed one
    (https://quarkus.io/version/3.27/guides/config-reference/#profiles). This
    checker used to ignore prefixed keys entirely, so a
    %prod.quarkus.datasource.jdbc.url pointing at another database produced
    zero findings while being exactly what the destination would use."""
    p = root / "src" / "main" / "resources" / "application.properties"
    base: dict[str, str] = {}
    override: dict[str, str] = {}
    if not p.is_file():
        return {}, {}
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s or s.startswith(("#", "!")) or "=" not in s:
            continue
        key, _, value = s.partition("=")
        key, value = key.strip(), value.strip()
        if key.startswith("%"):
            profiles, _, rest = key[1:].partition(".")
            if profile and profile in [x.strip() for x in profiles.split(",")]:
                override[rest] = value
            continue
        base[key] = value
    effective = dict(base)
    source = {k: "application.properties" for k in base}
    for key, value in override.items():
        effective[key] = value
        source[key] = "%%%s.%s" % (profile, key)
    # the caller needs to know which keys exist unprefixed: the platform
    # resolves the datasource at build time, so a value that exists only under
    # a profile is not a configured datasource even when its value is right
    source["__unprefixed__"] = ",".join(sorted(base))
    return effective, source


def check(root: Path) -> list[str]:
    out: list[str] = []
    try:
        doc = load_decisions(root)
    except DecisionsError as exc:
        return ["%s: %s" % (DECISIONS, exc)]
    gaps = [g for g in missing_decisions(doc, root) if str(g["subject"]).startswith("datasource")]
    if gaps:
        return ["%s %s: %s" % (g["class"], g["subject"], g["detail"]) for g in gaps]
    ds = datasource(doc)
    if not ds:
        return ["decisions.yaml datasource is not decided under an accepted ADR"]
    catalog = load_json(root / CATALOGS_DIR / "compat-mapping.json")
    kinds = (catalog.get("datasources") or {}).get("db_kinds") or {}
    kind = str(ds["db_kind"])
    profile = str(ds.get("profile") or "")
    props, came_from = effective_properties(root, profile)
    want = {
        "quarkus.datasource.db-kind": kind,
        "quarkus.datasource.jdbc.url": "${%s}" % ds["jdbc_url_env"],
        "quarkus.datasource.username": "${%s}" % ds["username_env"],
        "quarkus.datasource.password": "${%s}" % ds["password_env"],
        "quarkus.hibernate-orm.database.generation": str(ds["hibernate_generation"]),
    }
    unprefixed = set((came_from.get("__unprefixed__") or "").split(",")) - {""}
    for key, value in want.items():
        got = props.get(key)
        if key not in unprefixed:
            out.append("%s is not set unprefixed in src/main/resources/application.properties; the platform resolves the datasource at build time, so a profile-prefixed key alone is not a configured datasource" % key)
        if got is None:
            continue
        elif got != value:
            out.append("%s is %r under the %s profile (from %s), the decision says %r"
                       % (key, got, profile or "default", came_from.get(key, "application.properties"), value))
    for key in ("quarkus.datasource.jdbc.url", "quarkus.datasource.username", "quarkus.datasource.password"):
        got = props.get(key) or ""
        if got and not re.fullmatch(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", got):
            out.append("%s must be an environment reference, not the literal %r" % (key, got))
    pom = (root / "pom.xml").read_text(encoding="utf-8", errors="replace") if (root / "pom.xml").is_file() else ""
    wanted_ext = str((kinds.get(kind) or {}).get("extension") or "")
    if wanted_ext and wanted_ext.split(":", 1)[1] not in pom:
        out.append("%s (the extension documented for db_kind %s) is not in pom.xml" % (wanted_ext, kind))
    others = sorted({str(row.get("extension") or "").split(":", 1)[1] for k, row in kinds.items()
                     if k != kind and str(row.get("extension") or "").split(":", 1)[1] in pom})
    if others:
        # The reason is DECISION DRIFT, not ambiguity: db-kind is set, so the
        # platform can choose perfectly well. What it cannot do is explain why
        # a driver the decision never selected is in the build. Saying "the
        # platform cannot choose" while db-kind sits in the same file sent the
        # v8 M2 worker looking for a problem that was not there.
        out.append("pom.xml also carries %s; decisions.yaml selects db_kind %s, so a driver this run never uses is "
                   "decision drift and the bootstrap must not leave it behind" % (", ".join(others), kind))
    # a profile the decision did not select may still be selected at run time
    other = sorted({k.split(".", 1)[0][1:] for k in _all_profile_keys(root) if k.split(".", 1)[0][1:] != profile})
    conflicting = []
    for name in other:
        alt, _ = effective_properties(root, name)
        for key, value in want.items():
            if alt.get(key) not in (None, value):
                conflicting.append("%%%s.%s=%s" % (name, key, alt.get(key)))
    if conflicting:
        out.append("another profile would configure a different database: %s; the decision selects %r, so remove what this run does not use or record the other profile as a decision"
                   % (", ".join(sorted(conflicting)[:4]), profile))
    if str(ds.get("schema_owner")) == "source-assets":
        for field in ("schema_sql", "seed_sql"):
            rel = str(ds.get(field) or "")
            if rel and not (root / rel).is_file():
                out.append("datasource.%s names %s, which the destination does not have" % (field, rel))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    findings = check(root)
    if findings:
        return _refuse(findings)
    ds = datasource(load_decisions(root))
    print("PASS: datasource decision rendered (db_kind %s %s, profile %s, instance %s; credentials by reference; schema owned by %s)"
          % (ds["db_kind"], ds["db_version"], ds["profile"], ds["instance"], ds["schema_owner"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
