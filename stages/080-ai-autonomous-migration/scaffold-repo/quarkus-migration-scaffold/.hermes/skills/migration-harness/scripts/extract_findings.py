#!/usr/bin/env python3
"""Summarize migration/mta-findings.json without loading it into context.

Usage: extract_findings.py [findings.json] [--rule RULE_ID]
Default file: /projects/modernized/migration/mta-findings.json
With --rule, prints each incident (uri, line, message) for that rule.
"""
import json, sys

path = "/projects/modernized/migration/mta-findings.json"
rule_filter = None
args = sys.argv[1:]
if "--rule" in args:
    i = args.index("--rule"); rule_filter = args[i+1]; del args[i:i+2]
if args: path = args[0]

d = json.load(open(path))
rows = []
for rs in d:
    for rid, v in (rs.get("violations") or {}).items():
        incidents = v.get("incidents") or []
        rows.append((rid, v.get("description", ""), incidents))

if rule_filter:
    for rid, desc, incidents in rows:
        if rid == rule_filter:
            print(f"{rid} — {desc}")
            for inc in incidents:
                print(f"  {inc.get('uri','?')}:{inc.get('lineNumber','?')}  {str(inc.get('message',''))[:100]}")
else:
    rows.sort(key=lambda r: -len(r[2]))
    print(f"{len(rows)} violations, {sum(len(r[2]) for r in rows)} incidents")
    for rid, desc, incidents in rows:
        print(f"{len(incidents):4d}  {rid}  {desc[:70]}")
