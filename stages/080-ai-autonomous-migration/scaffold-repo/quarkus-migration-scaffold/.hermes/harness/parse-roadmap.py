#!/usr/bin/env python3
"""Outer-loop roadmap parser (improvement B2): emits one shell-safe line
per story for the supervisor to iterate.

Usage: parse-roadmap.py <roadmap.md>
Output per story:  <sid>|<deploy>|<findings-or-none>|<scope-files>
(fields pipe-separated; findings comma-separated; scope space-separated)
"""
import re
import sys


def package_paths():
    """(legacy-path, target-path) slash-forms from migration.yaml. The roadmap
    names classes by their LEGACY path (com/redhat/coolstore/...), but src/main
    only ever holds TARGET-package files (com/demo/...). The scope this parser
    emits is compared against src/main by the supervisor's scope sensor, so it
    must be translated to the target path — otherwise every legitimate harvest
    reads as out-of-scope and gets reverted (V5 run-4: S02 ShoppingCart)."""
    leg, tgt = "com.redhat.coolstore", "com.demo"
    try:
        y = open("migration.yaml", encoding="utf-8").read()
        ml = re.search(r"legacyPackage:\s*([\w.]+)", y)
        mt = re.search(r"targetPackage:\s*([\w.]+)", y)
        if ml:
            leg = ml.group(1)
        if mt:
            tgt = mt.group(1)
    except OSError:
        pass
    return leg.replace(".", "/"), tgt.replace(".", "/")


def main():
    text = open(sys.argv[1], encoding="utf-8").read()
    legp, tgtp = package_paths()
    heads = re.findall(r"^##\s+(S\d{2,})\s*:", text, re.M)
    parts = re.split(r"^##\s+(S\d{2,})\s*:.*$", text, flags=re.M)
    bodies = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}

    def field(sid, name):
        m = re.search(rf"^-\s*{name}:\s*(.+)$", bodies.get(sid, ""), re.M)
        return m.group(1).strip() if m else ""

    for sid in heads:
        deploy = "true" if field(sid, "deploy").lower() == "true" else "false"
        findings = ",".join(
            f for f in re.split(r"[,\s]+", field(sid, "findings"))
            if f and f != "-" and re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+", f))
        scope = " ".join(
            s.strip().rstrip(",").replace(legp, tgtp)
            for s in field(sid, "scope").split(",") if s.strip())
        print(f"{sid}|{deploy}|{findings or 'none'}|{scope}")


if __name__ == "__main__":
    sys.exit(main())
