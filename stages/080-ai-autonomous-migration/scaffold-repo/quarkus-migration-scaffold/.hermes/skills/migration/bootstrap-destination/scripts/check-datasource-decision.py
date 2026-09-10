#!/usr/bin/env python3
"""Refuse a destination whose effective datasource is not the decided one (M2).

The decision lives in decisions.yaml (`datasource`, under an accepted ADR) and
is rendered by bootstrap-destination. This checker measures the rendered tree
against the decision, at M2, before any worker reaches runtime verification:

  * the unprefixed keys the platform resolves at build time must be present and
    equal to the decision (a %profile-prefixed key alone is not a configured
    datasource -- that is exactly how pilot v7 reached an empty work list and
    then failed augmentation with "Datasource <default> is not configured");
  * the JDBC extension documented for the decided db_kind must be in the pom,
    and no OTHER db-kind extension may be there, because with two drivers and
    no db-kind the platform cannot choose;
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


def _refuse(findings: list[str]) -> int:
    for f in findings:
        print("  - %s" % f, file=sys.stderr)
    print("REFUSE: DATASOURCE_DECISION (%d finding(s))" % len(findings), file=sys.stderr)
    return 1


def effective_properties(root: Path) -> dict[str, str]:
    p = root / "src" / "main" / "resources" / "application.properties"
    out: dict[str, str] = {}
    if not p.is_file():
        return out
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s or s.startswith(("#", "!")) or "=" not in s or s.startswith("%"):
            continue
        key, _, value = s.partition("=")
        out[key.strip()] = value.strip()
    return out


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
    props = effective_properties(root)
    want = {
        "quarkus.datasource.db-kind": kind,
        "quarkus.datasource.jdbc.url": "${%s}" % ds["jdbc_url_env"],
        "quarkus.datasource.username": "${%s}" % ds["username_env"],
        "quarkus.datasource.password": "${%s}" % ds["password_env"],
        "quarkus.hibernate-orm.database.generation": str(ds["hibernate_generation"]),
    }
    for key, value in want.items():
        got = props.get(key)
        if got is None:
            out.append("%s is not set in src/main/resources/application.properties; a profile-prefixed key is not a configured datasource" % key)
        elif got != value:
            out.append("%s is %r, the decision says %r" % (key, got, value))
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
        out.append("pom.xml also carries %s; with more than one JDBC extension and no decided db-kind the platform cannot choose, so remove what this run does not use" % ", ".join(others))
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
