#!/usr/bin/env python3
"""O-DELTABASE — honest M5 findings delta (absence ≠ resolved).

Compares migration/mta-findings.json (before) vs mta-findings-after.json.

A rule gone from "after" is NOT automatically RESOLVED:
  - SCAFFOLD-PRESATISFIED — already true on Quarkus destination (omit credit)
  - ABSENT-NOT-LANDED — none of the before-incident basenames exist under
    src/main (or src/test). Empty harvest / scaffold-only tree must score
    0 resolved (quietly wrong > loudly wrong).
  - DEFERRED-BY-DECISION (O-LEDGERFALSE / F-60) — listed in
    migration/deferred-by-decision.txt (one rule id per line); excluded
    from the in-scope denominator (ceiling 17/(28−N)).
  - RESOLVED — at least one incident basename exists under src/ AND the rule
    no longer fires on the after-scan (conversion or cleanup evidence).

Also prints tree metrics so % headlines cannot hide pom/props residual while
src/main java doubled (Poll 39).

Usage: findings-delta.py [before.json] [after.json]
Exit 0 always (report tool); prints machine-readable summary lines.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def load_rules(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for rs in data:
        for rid, v in (rs.get("violations") or {}).items():
            out[rid] = v
    return out


def incident_basenames(v: dict) -> set[str]:
    names: set[str] = set()
    for inc in v.get("incidents") or []:
        uri = unquote(inc.get("uri") or "")
        if uri.startswith("file:"):
            uri = urlparse(uri).path or uri
        base = Path(uri).name
        if base and base != "?":
            names.add(base)
    return names


def basename_in_src(name: str, root: Path) -> bool:
    for rel in ("src/main", "src/test"):
        d = root / rel
        if not d.is_dir():
            continue
        for _ in d.rglob(name):
            return True
    return False


def load_presat(root: Path) -> set[str]:
    out: set[str] = set()
    for base in (
        root / ".hermes/harness/scaffold-presatisfied.txt",
        Path(__file__).resolve().parent / "scaffold-presatisfied.txt",
    ):
        try:
            for ln in base.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    out.add(ln)
            if out:
                break
        except OSError:
            continue
    return out


def count_java(root: Path, rel: str) -> int:
    d = root / rel
    if not d.is_dir():
        return 0
    return sum(1 for _ in d.rglob("*.java"))


def after_sites(after: dict[str, dict]) -> dict[str, int]:
    """Count residual incidents by coarse tree bucket."""
    buckets = {"src/main": 0, "src/test": 0, "pom": 0, "props": 0, "other": 0}
    for v in after.values():
        for inc in v.get("incidents") or []:
            uri = unquote(inc.get("uri") or "").lower()
            if "src/main" in uri:
                buckets["src/main"] += 1
            elif "src/test" in uri:
                buckets["src/test"] += 1
            elif uri.endswith("pom.xml") or "/pom.xml" in uri:
                buckets["pom"] += 1
            elif "application.properties" in uri or uri.endswith(".yaml") or uri.endswith(".yml"):
                buckets["props"] += 1
            else:
                buckets["other"] += 1
    return buckets


def main() -> int:
    root = Path(os.environ.get("FINDINGS_DELTA_ROOT", ".")).resolve()
    before_p = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "migration/mta-findings.json"
    after_p = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "migration/mta-findings-after.json"
    before = load_rules(before_p)
    after = load_rules(after_p)
    if not before:
        print("findings-delta: no before findings — skip")
        return 0
    if not after_p.is_file():
        print("findings-delta: no after findings — skip")
        return 0

    presat = load_presat(root)
    deferred_ids: set[str] = set()
    dpath = root / "migration" / "deferred-by-decision.txt"
    if dpath.is_file():
        for line in dpath.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                deferred_ids.add(line)

    resolved: list[str] = []
    absent: list[str] = []
    deferred: list[str] = []
    scaffold: list[str] = []
    remaining = sorted(set(before) & set(after))
    new_rules = sorted(set(after) - set(before))

    for rid, v in sorted(before.items()):
        if rid in after:
            continue
        if rid in presat:
            scaffold.append(rid)
            continue
        bases = incident_basenames(v)
        landed = any(basename_in_src(b, root) for b in bases) if bases else False
        # Config/pom-only rules: treat pom.xml / properties as landed evidence.
        if not landed and bases:
            for b in bases:
                if b == "pom.xml" and (root / "pom.xml").is_file():
                    landed = True
                    break
                if b.endswith(".properties") and list((root / "src").rglob(b) if (root / "src").is_dir() else []):
                    landed = True
                    break
        if landed:
            resolved.append(rid)
        elif rid in deferred_ids or any(
            rid.startswith(d.rstrip("*")) for d in deferred_ids if d.endswith("*")
        ):
            deferred.append(rid)
        else:
            absent.append(rid)

    java_main = count_java(root, "src/main/java")
    java_test = count_java(root, "src/test/java")
    sites = after_sites(after)
    # Honest floor still counts absent_not_landed. In-scope pct excludes
    # deferred_by_decision from the denominator (F-60 / F-70 N14 arithmetic).
    denom_floor = len(resolved) + len(absent) + len(deferred) + len(remaining)
    rate = (100.0 * len(resolved) / denom_floor) if denom_floor else 0.0
    denom_in = len(resolved) + len(absent) + len(remaining)
    rate_in = (100.0 * len(resolved) / denom_in) if denom_in else 0.0

    print("# Findings delta (O-DELTABASE — absence ≠ resolved)")
    print()
    print(f"METRIC src_main_java={java_main} src_test_java={java_test}")
    print(
        f"METRIC residual_incidents src/main={sites['src/main']} src/test={sites['src/test']} "
        f"pom={sites['pom']} props={sites['props']} other={sites['other']}"
    )
    print(
        f"SUMMARY resolved={len(resolved)} absent_not_landed={len(absent)} "
        f"deferred_by_decision={len(deferred)} "
        f"scaffold_presatisfied={len(scaffold)} remaining={len(remaining)} "
        f"new_after={len(new_rules)} honest_resolve_pct={rate:.1f} "
        f"in_scope_resolve_pct={rate_in:.1f}"
    )
    print()
    print("## RESOLVED (landed evidence + rule absent after)")
    for rid in resolved:
        print(f"- {rid}")
    if not resolved:
        print("- (none)")
    print()
    print("## ABSENT-NOT-LANDED (do NOT credit as resolved — nothing in src/)")
    for rid in absent:
        print(f"- {rid}")
    if not absent:
        print("- (none)")
    print()
    print("## DEFERRED-BY-DECISION (O-LEDGERFALSE — excluded from in-scope denom)")
    for rid in deferred:
        print(f"- {rid}")
    if not deferred:
        print("- (none)")
    print()
    print("## SCAFFOLD-PRESATISFIED (destination already satisfied — no story credit)")
    for rid in scaffold:
        print(f"- {rid}")
    if not scaffold:
        print("- (none)")
    print()
    print("## REMAINING (still in after-scan)")
    for rid in remaining:
        print(f"- {rid}")
    if not remaining:
        print("- (none)")
    if new_rules:
        print()
        print("## NEW IN AFTER (not in before)")
        for rid in new_rules:
            print(f"- {rid}")
    # Machine line for supervisors / instruments
    print()
    print(
        f"DELTABASE:resolved={len(resolved)}:absent={len(absent)}:"
        f"deferred={len(deferred)}:presat={len(scaffold)}:remaining={len(remaining)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
