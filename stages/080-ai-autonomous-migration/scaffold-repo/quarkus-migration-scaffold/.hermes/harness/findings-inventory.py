#!/usr/bin/env python3
"""M1 spec input bundle: findings inventory with the MAPPINGS join
pre-computed (MTA→spec translation, docs/MTA-TO-SPEC-MAPPING.md R2).

Usage: findings-inventory.py <findings.json> <MAPPINGS.md> [legacy-root] [> inventory.md]

Optional legacy-root enables O-CODEGENDEMAND (deterministic build-codegen-*
findings) and O-INVRECONCILE (RECONCILE closure line). O-TAGDEMAND always
runs from findings.json (tags/insights → tech-<slug> synthetics).

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


def reconcile_counts(data, rules):
    """O-INVRECONCILE arithmetic. Returns (fields_dict, closes: bool).

    findings/source_rulesets = len(mta-findings.json) when it is a list.
    Non-list source cannot close (no tie-back to a countable artifact).
    """
    if not isinstance(data, list):
        return {
            "source_rulesets": 0,
            "skipped_empty": 0,
            "active_rulesets": 0,
            "violation_entries": len(rules),
            "rule_ids": len({rid for rid, _ in rules}),
            "excluded_dup": 0,
            "excluded_total": 0,
        }, False
    source_rulesets = len(data)
    skipped_empty = 0
    active_rulesets = 0
    for rs in data:
        v = (rs.get("violations") or {}) if isinstance(rs, dict) else {}
        if v:
            active_rulesets += 1
        else:
            skipped_empty += 1
    violation_entries = len(rules)
    rule_ids_m = len({rid for rid, _ in rules})
    excluded_dup = violation_entries - rule_ids_m
    level1 = source_rulesets == skipped_empty + active_rulesets
    level2 = excluded_dup >= 0 and (rule_ids_m + excluded_dup == violation_entries)
    return {
        "source_rulesets": source_rulesets,
        "skipped_empty": skipped_empty,
        "active_rulesets": active_rulesets,
        "violation_entries": violation_entries,
        "rule_ids": rule_ids_m,
        "excluded_dup": excluded_dup,
        "excluded_total": skipped_empty + max(excluded_dup, 0),
    }, (level1 and level2)


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: findings-inventory.py <findings.json> <MAPPINGS.md> [legacy-root]",
            file=sys.stderr,
        )
        sys.exit(2)
    findings_path, mappings_path = sys.argv[1], sys.argv[2]
    legacy_root = sys.argv[3] if len(sys.argv) > 3 else None
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

    # O-ADR24FIND: one shared Kantra walk (findings_ir) — inventory is a view.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import findings_ir  # noqa: E402

    rules = list(findings_ir.iter_violation_rules(data))
    rules.sort(key=lambda r: (-len(r[1].get("incidents") or []), r[0]))

    classified = collections.defaultdict(list)
    preserve = []
    # K3: non-mandatory rows kept for the decision table (not silently dropped).
    non_mandatory_rows = []  # (rid, category, effort, sites, desc)
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
            incs = v.get("incidents") or []
            non_mandatory_rows.append(
                (
                    rid,
                    cat,
                    v.get("effort", "?"),
                    len(incs),
                    (v.get("description") or "").strip(),
                )
            )
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

    # K3 — explicit decision table (M2 marks adopt/defer in the roadmap).
    print("## Non-mandatory findings (decide adopt / defer in roadmap)")
    print()
    if non_mandatory_rows:
        print("| rule | category | effort | sites | description |")
        print("|---|---|---|---|---|")
        for rid, cat, effort, sites, desc in sorted(non_mandatory_rows):
            dshort = (desc[:80] + "…") if len(desc) > 80 else desc
            dshort = dshort.replace("|", "/")
            print(f"| {rid} | {cat} | {effort} | {sites} | {dshort} |")
        print()
        print(
            "M2 must mark each rule in the roadmap under "
            "`## Non-mandatory decisions` as `adopt` or `defer (reason)` (K3)."
        )
    else:
        print("- none")
    print()

    # O-CODEGENDEMAND — append synthetic build-codegen-* findings (ANALYZE-side)
    codegen_entries = []
    codegen_ids = []
    if legacy_root:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import codegen_demand  # noqa: WPS433 — sibling harness module

            codegen_entries = codegen_demand.detect(legacy_root)
            codegen_ids = codegen_demand.summary_ids(codegen_entries)
            md = codegen_demand.render_markdown(codegen_entries)
            if md:
                print(md.rstrip())
                print()
            for e in codegen_entries:
                classified["infer"].append(e["finding_id"])
        except Exception as exc:  # noqa: BLE001 — never fail inventory on optional scan
            print(f"WARN: O-CODEGENDEMAND skipped: {exc}", file=sys.stderr)

    # O-TAGDEMAND — tech-<slug> from MTA tags/insights (destination consequence)
    tag_entries = []
    tag_ids = []
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import tag_demand  # noqa: WPS433 — sibling harness module

        tag_entries = tag_demand.detect(findings_path)
        tag_ids = tag_demand.summary_ids(tag_entries)
        md = tag_demand.render_markdown(tag_entries)
        if md:
            print(md.rstrip())
            print()
        for e in tag_entries:
            classified["infer"].append(e["finding_id"])
    except Exception as exc:  # noqa: BLE001 — never fail inventory on optional scan
        print(f"WARN: O-TAGDEMAND skipped: {exc}", file=sys.stderr)

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
    print()

    # O-INVRECONCILE — tie RECONCILE to the source artifact (mta-findings.json).
    fields, closes = reconcile_counts(data, rules)
    reasons = []
    if fields["skipped_empty"]:
        reasons.append(f"skipped-empty-ruleset:{fields['skipped_empty']}")
    if fields["excluded_dup"] > 0:
        reasons.append(f"duplicate-rule-id:{fields['excluded_dup']}")
    elif fields["excluded_dup"] < 0:
        reasons.append(f"NEGATIVE_DUP:{fields['excluded_dup']}")
    if not reasons:
        reasons.append("none:0")
    reason_s = ",".join(reasons)
    print(
        f"RECONCILE findings={fields['source_rulesets']} "
        f"source_rulesets={fields['source_rulesets']} "
        f"skipped_empty={fields['skipped_empty']} "
        f"active_rulesets={fields['active_rulesets']} "
        f"violation_entries={fields['violation_entries']} "
        f"rule_ids={fields['rule_ids']} "
        f"codegen={len(codegen_ids)} tech={len(tag_ids)} "
        f"excluded={fields['excluded_total']} "
        f"reason={reason_s} closes={'yes' if closes else 'no'}"
    )
    if not closes:
        print(
            "RECONCILE-FAIL: source/violation arithmetic does not close "
            f"(rulesets {fields['source_rulesets']}!= "
            f"{fields['skipped_empty']}+{fields['active_rulesets']} "
            f"or violations {fields['violation_entries']}!= "
            f"{fields['rule_ids']}+{fields['excluded_dup']})",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
