#!/usr/bin/env python3
"""Emit evidence/required-extensions.json from M1 findings (V35-EXTENSIONS).

Emission, not new analysis. M1 rules already name Quarkus targets; legacy
pom artifactIds are the other source. Rewrite quoted quarkus-spring-* /
Spring Boot starters through T-3 (spring-dep-to-extension.md). Never emit
quarkus-spring-* compatibility extensions.

JDBC driver kind comes from the LEGACY datasource URL (jdbc:<kind>: mapped
through the same md table). Dest application.properties does not exist at
M1 — do not read dest db-kind.

Usage:
  python3 emit-required-extensions.py <root>
  python3 emit-required-extensions.py <root> --handoff PATH --legacy-pom PATH --out PATH
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_MAP = (
    _SCRIPTS.parent.parent.parent
    / "migration"
    / "manage-quarkus-extensions"
    / "scripts"
)
if str(_MAP) not in sys.path:
    sys.path.insert(0, str(_MAP))

from spring_dep_map import (  # noqa: E402
    JDBC_GLOB,
    entries_for,
    expand_jdbc_glob,
    native_for_artifact,
    scan_legacy_jdbc_keys,
)

SCHEMA = "rhoai3.required-extensions/v2"
HANDOFF_REL = Path("evidence") / "findings-handoff.json"
OUT_REL = Path("evidence") / "required-extensions.json"
INVENTORY_REL = Path("evidence") / "type-inventory.json"

QUARKUS_AID_RE = re.compile(r"quarkus-[a-z0-9-]+", re.I)
SPRING_QUOTE_RE = re.compile(r"['\"](spring-[a-z0-9-]+)['\"]", re.I)
ARTIFACT_RE = re.compile(r"<artifactId>\s*([^<]+?)\s*</artifactId>", re.I)

LEGACY_POM_CANDIDATES = (
    Path("/projects/.derived/legacy-at-3/pom.xml"),
    Path("evidence/derived/legacy-at-3/pom.xml"),
)
LEGACY_ROOT_CANDIDATES = (
    Path("/projects/.derived/legacy-at-3"),
    Path("evidence/derived/legacy-at-3"),
    Path("/projects/legacy"),
)


def _apply_rule(rule: dict) -> set[str]:
    disp = str(rule.get("disposition") or "apply").strip().lower()
    if disp != "apply":
        return set()
    rid = str(rule.get("rule_id") or "")
    desc = str(rule.get("description") or "")
    text = f"{rid} {desc}".lower()
    out: set[str] = set()
    for m in QUARKUS_AID_RE.findall(desc):
        out.update(native_for_artifact(m))
    for m in SPRING_QUOTE_RE.findall(desc):
        out.update(native_for_artifact(m))
    if "jpa" in rid.lower() or "hibernate-orm" in text:
        out.add("quarkus-hibernate-orm")
    if "persistence" in rid.lower() and "to-quarkus" in rid.lower():
        out.add("quarkus-hibernate-orm")
        out.update(native_for_artifact("spring-boot-starter-jdbc"))
    if "validat" in rid.lower() or "validat" in desc.lower():
        out.add("quarkus-hibernate-validator")
    if "springboot-cache" in rid.lower() or "spring-cache" in text:
        out.add("quarkus-cache")
    if re.search(r"springboot-.*web|resteasy|jax-rs", rid.lower()):
        out.update(["quarkus-rest", "quarkus-rest-jackson"])
    if any(tok in text for tok in ("openapi", "swagger", "springfox")):
        out.add("openapi-generator-maven-plugin")
        out.add("quarkus-smallrye-openapi")
    out = {x for x in out if x and not x.startswith("quarkus-spring-")}
    return out


def from_handoff(handoff: dict) -> tuple[list[str], list[str]]:
    found: set[str] = set()
    from_rules: list[str] = []
    for rule in handoff.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        got = _apply_rule(rule)
        if got:
            rid = str(rule.get("rule_id") or "")
            if rid and rid not in from_rules:
                from_rules.append(rid)
            found.update(got)
    return sorted(found), from_rules[:40]


def from_legacy_pom(text: str) -> list[str]:
    found: set[str] = set()
    for m in ARTIFACT_RE.findall(text or ""):
        found.update(native_for_artifact(m.strip()))
    return sorted(x for x in found if x and not x.startswith("quarkus-spring-"))


def generated_present(root: Path) -> bool:
    inv = root / INVENTORY_REL
    if not inv.is_file():
        return False
    try:
        data = json.loads(inv.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    rows = data if isinstance(data, list) else (data or {}).get("types") or []
    if not isinstance(rows, list):
        return False
    for rec in rows:
        if isinstance(rec, dict) and (
            rec.get("generated") is True or str(rec.get("provider") or "") == "generated"
        ):
            return True
    return False


def resolve_legacy_pom(root: Path, explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.is_file() else None
    for cand in LEGACY_POM_CANDIDATES:
        p = cand if cand.is_absolute() else (root / cand)
        if p.is_file():
            return p
    return None


def resolve_legacy_root(root: Path, pom: Path | None) -> Path | None:
    if pom is not None and pom.is_file():
        parent = pom.parent
        if parent.is_dir():
            return parent
    for cand in LEGACY_ROOT_CANDIDATES:
        p = cand if cand.is_absolute() else (root / cand)
        if p.is_dir():
            return p
    return None


def emit(
    root: Path,
    *,
    handoff_path: Path,
    legacy_pom: Path | None,
    out_path: Path,
) -> int:
    if not handoff_path.is_file():
        print(f"FAIL: missing findings-handoff {handoff_path}", file=sys.stderr)
        return 1
    try:
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: handoff {handoff_path}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(handoff, dict):
        print(f"FAIL: handoff {handoff_path} is not an object", file=sys.stderr)
        return 1
    from_rules, rule_ids = from_handoff(handoff)
    from_pom: list[str] = []
    pom_rel = ""
    if legacy_pom is not None and legacy_pom.is_file():
        from_pom = from_legacy_pom(legacy_pom.read_text(encoding="utf-8", errors="ignore"))
        try:
            pom_rel = str(legacy_pom.relative_to(root))
        except ValueError:
            pom_rel = str(legacy_pom)
    found = set(from_rules) | set(from_pom)
    if generated_present(root):
        found.add("openapi-generator-maven-plugin")
    jdbc_from = ""
    if JDBC_GLOB in found or any(
        x.startswith("quarkus-jdbc-") for x in found
    ) or "quarkus-agroal" in found:
        keys = scan_legacy_jdbc_keys(resolve_legacy_root(root, legacy_pom))
        expanded, jdbc_from = expand_jdbc_glob(found, keys)
        if JDBC_GLOB in found and jdbc_from in {"", "MISSING"}:
            print(
                "REFUSE: JDBC_KIND legacy datasource URL missing "
                "(cannot expand quarkus-jdbc-* from dest db-kind; M1 is too early)",
                file=sys.stderr,
            )
            return 1
        found = expanded
    entries = entries_for(sorted(found))
    doc = {
        "schema": SCHEMA,
        "entries": entries,
        "from_rules": rule_ids,
        "legacy_pom": pom_rel,
        "jdbc_kind_from": jdbc_from,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"OK: required-extensions {len(entries)} -> {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--handoff", default="")
    ap.add_argument("--legacy-pom", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    handoff = Path(args.handoff) if args.handoff else root / HANDOFF_REL
    if args.handoff and not handoff.is_file():
        handoff = root / args.handoff
    out = Path(args.out) if args.out else root / OUT_REL
    if args.out and not out.is_absolute():
        out = root / args.out if not Path(args.out).is_absolute() else Path(args.out)
    explicit = Path(args.legacy_pom) if args.legacy_pom else None
    if explicit is not None and not explicit.is_file():
        alt = root / args.legacy_pom
        explicit = alt if alt.is_file() else explicit
    legacy = resolve_legacy_pom(root, explicit)
    return emit(root, handoff_path=handoff, legacy_pom=legacy, out_path=out)


if __name__ == "__main__":
    raise SystemExit(main())
