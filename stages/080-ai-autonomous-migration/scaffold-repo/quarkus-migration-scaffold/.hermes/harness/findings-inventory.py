#!/usr/bin/env python3
"""M1 spec input bundle: findings inventory with the MAPPINGS join
pre-computed (MTA→spec translation, docs/MTA-TO-SPEC-MAPPING.md R2).

Usage: findings-inventory.py <findings.json> <MAPPINGS.md> [> inventory.md]

Per mandatory rule: description, class from the MAPPINGS rule-join table
(recipe / rewrite / infer / OPEN DESIGN), decided target, incident sites
grouped by file. Config-surface rules are additionally listed as
preserve-candidates for confirmation against migration.yaml. M3
spends its judgment on the behavioral contract and the OPEN DESIGN
rows — everything else here is a lookup, not a derivation.
"""
import collections
import json
import os
import re
import sys

PRESERVE_HINT = re.compile(
    r"propert|config|env|endpoint|datasource|actuator|url|credential", re.I)


def parse_joins(mappings_path):
    """Rows of the 'Windup rule joins' table: (prefix, class, target)."""
    text = open(mappings_path, encoding="utf-8").read()
    m = re.search(r"## Windup rule joins.*?\n(\|.*?)(?:\n##|\Z)", text, re.S)
    joins = []
    if not m:
        return joins
    for line in m.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] in ("rule id prefix", "---") or set(cells[0]) <= {"-"}:
            continue
        joins.append((cells[0], cells[1], cells[2]))
    # longest prefix wins on overlap (e.g. -01 vs bare prefix)
    joins.sort(key=lambda j: -len(j[0]))
    return joins


def main():
    findings_path, mappings_path = sys.argv[1], sys.argv[2]
    data = json.load(open(findings_path))
    joins = parse_joins(mappings_path)
    # Scaffold-baseline annotation (V3 S01 lesson: pom-convention rules
    # kept firing on the destination and read as a falsified claim):
    # rules that also fire on the PRISTINE scaffold are residual-expected
    # — annotated, never exempted.
    baseline = set()
    try:
        for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scaffold-baseline.txt")):
            line = line.strip()
            if line and not line.startswith("#"):
                baseline.add(line)
    except OSError:
        pass

    rules = []  # (rid, violation)
    for rs in data:
        for rid, v in (rs.get("violations") or {}).items():
            rules.append((rid, v))
    rules.sort(key=lambda r: (-len(r[1].get("incidents") or []), r[0]))

    classified = collections.defaultdict(list)
    preserve = []
    print("# Findings inventory (M1 spec input bundle)")
    print()
    print(f"Rules: {len(rules)}; incidents: "
          f"{sum(len(v.get('incidents') or []) for _, v in rules)}. "
          f"Join source: MAPPINGS.md rule-join table ({len(joins)} rows).")
    print()
    for rid, v in rules:
        cat = v.get("category") or "mandatory"
        if cat != "mandatory":
            classified["non-mandatory"].append(rid)
            continue
        cls, target = "OPEN DESIGN", "no MAPPINGS join — decide the shape in the plan"
        for prefix, jcls, jtarget in joins:
            if rid.startswith(prefix):
                cls, target = jcls, jtarget
                break
        bucket = cls.split(":", 1)[0]
        classified[bucket].append(rid)
        desc = (v.get("description") or "").strip()
        if rid in baseline:
            desc += " [ALSO FIRES ON PRISTINE SCAFFOLD — residual expected after migration; verify by substance at delta time]"
        if PRESERVE_HINT.search(rid + " " + desc):
            preserve.append((rid, desc))
        print(f"## {rid} [{bucket}]")
        print()
        print(f"- {desc}")
        print(f"- Decided target: {target}")
        by_file = collections.defaultdict(list)
        for inc in v.get("incidents") or []:
            uri = (inc.get("uri") or "?").replace("file:///", "/")
            by_file[uri].append(str(inc.get("lineNumber", "?")))
        for uri, lines in sorted(by_file.items()):
            print(f"- {uri}: line {', '.join(lines)}")
        print()

    print("## Summary by class")
    print()
    for bucket in ("recipe", "rewrite", "infer", "OPEN DESIGN", "non-mandatory"):
        ids = classified.get(bucket, [])
        if ids:
            print(f"- {bucket}: {len(ids)} — {', '.join(sorted(ids))}")
    print()
    print("## Preserve-candidate surfaces (confirm against migration.yaml preserve:)")
    print()
    if preserve:
        for rid, desc in preserve:
            print(f"- {rid}: {desc[:100]}")
    else:
        print("- none detected")


if __name__ == "__main__":
    main()
