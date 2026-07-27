#!/usr/bin/env python3
"""Single source for SonarQube new-code evidence (audit consolidation:
this logic previously existed 3x across sensors.sh and supervisor.sh).

Usage: sonar-report.py <host> <projectKey> [--out FILE] [--coverage]

Prints the new-code violation count on stdout (last line, integer).
Violation details (rule (count): file:line, ...), DUPLICATION lines and
— with --coverage — COVERAGE lines are written to FILE (default stderr).
Never raises: network failures degrade to count 0 with a note.
"""
import collections
import json
import sys
import urllib.request


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=30) as r:
        return json.load(r)


def main():
    base, key = sys.argv[1], sys.argv[2]
    out = sys.stderr
    if "--out" in sys.argv:
        out = open(sys.argv[sys.argv.index("--out") + 1], "w")
    want_cov = "--coverage" in sys.argv

    total = 0
    try:
        issues = get(base, f"/api/issues/search?componentKeys={key}&resolved=false&inNewCodePeriod=true&ps=100")
        total = issues.get("total", 0)
        by = collections.defaultdict(list)
        for i in issues.get("issues", []):
            by[i["rule"]].append(f"{i['component'].split(':')[-1]}:{i.get('line', '?')}")
        for rule in sorted(by):
            print(f"{rule} ({len(by[rule])}): " + ", ".join(by[rule][:10]), file=out)
    except Exception as e:
        print(f"(violation fetch failed: {e})", file=out)

    try:
        dup = get(base, f"/api/measures/component_tree?component={key}&metricKeys=new_duplicated_lines&qualifiers=FIL&ps=50")
        for c in dup.get("components", []):
            m = {x["metric"]: (x.get("period") or {}).get("value") or x.get("value") for x in c.get("measures", [])}
            dl = float(m.get("new_duplicated_lines") or 0)
            if dl > 0:
                print(f"DUPLICATION {c['path']}: {int(dl)} duplicated new lines", file=out)
    except Exception:
        pass

    if want_cov:
        try:
            cov = get(base, f"/api/measures/component?component={key}&metricKeys=new_coverage")
            val = None
            for x in cov.get("component", {}).get("measures", []):
                val = (x.get("period") or {}).get("value") or x.get("value")
            if val is not None and float(val) < 80:
                print(f"COVERAGE new_coverage={val}% (gate requires >= 80%) — see SHIPPING.md gate-correction (coverage).", file=out)
                tree = get(base, f"/api/measures/component_tree?component={key}&metricKeys=new_coverage,new_uncovered_lines&qualifiers=FIL&ps=100")
                rows = []
                for c in tree.get("components", []):
                    m = {x["metric"]: (x.get("period") or {}).get("value") or x.get("value") for x in c.get("measures", [])}
                    if m.get("new_coverage") is not None:
                        rows.append((float(m["new_coverage"]), c["path"], m.get("new_uncovered_lines") or "?"))
                for pct, path, unc in sorted(rows)[:10]:
                    print(f"COVERAGE {path}: {pct}% new-code coverage, {unc} uncovered new lines", file=out)
        except Exception:
            pass

    if out is not sys.stderr:
        out.close()
    print(total)


if __name__ == "__main__":
    main()
