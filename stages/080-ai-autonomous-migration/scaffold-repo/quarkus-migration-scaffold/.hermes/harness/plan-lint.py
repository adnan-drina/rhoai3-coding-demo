#!/usr/bin/env python3
"""Deterministic Phase B plan lint (improvement plan B2).

Usage: plan-lint.py <tasks.md> [mta-findings.json]

Checks (exit 0 = plan accepted, 1 = revision required; findings printed
one per line as 'LINT:<class>: <detail>'):
  ids        — every task heading parseable (any #-depth, T-style id)
  order      — rewrite-class tasks precede infer-class tasks
  design     — every infer task carries design content (a target/file
               mapping or signature line), per the design-in-packet rule
  ui-surface — the plan covers or explicitly waives the legacy UI
  findings   — every mandatory finding rule id appears in some task
               (requires the findings JSON)
"""
import json
import re
import sys

problems = []


def lint(cls, detail):
    problems.append(f"LINT:{cls}: {detail}")


def main():
    tasks_path = sys.argv[1]
    text = open(tasks_path).read()

    heads = re.findall(r"^(#{2,6})\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M)
    if not heads:
        lint("ids", "no parseable task headings (want '#### T-001: title')")
        print("\n".join(problems))
        return 1

    # split body per task
    bodies = {}
    parts = re.split(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:.*$", text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        bodies[parts[i]] = parts[i + 1]

    classes = {}
    for _, tid, _ in heads:
        body = bodies.get(tid, "")
        m = re.search(r"\*\*Class\*\*:?\s*`?(\w+)`?|^Class:\s*(\w+)", body, re.M)
        classes[tid] = (m.group(1) or m.group(2)).lower() if m else "unknown"
        if classes[tid] == "unknown":
            lint("ids", f"{tid}: no Class marker (rewrite|infer)")

    # order: no rewrite after the first infer
    seen_infer = False
    for _, tid, _ in heads:
        if classes.get(tid) == "infer":
            seen_infer = True
        elif classes.get(tid) == "rewrite" and seen_infer:
            lint("order", f"{tid}: rewrite task after infer tasks began")

    # design-in-packet: infer bodies need concrete target content
    design_signal = re.compile(
        r"(→|->)\s*src/|src/(main|test)/java|@\w+|\bsignature|\bPath\(|"
        r"class\s+\w+|record\s+\w+|Target\s*(file|shape|design)", re.I)
    for _, tid, _ in heads:
        if classes.get(tid) == "infer" and not design_signal.search(bodies.get(tid, "")):
            lint("design", f"{tid}: infer task without decided design "
                           "(no file mappings/signatures/annotations in body)")

    # ui surface covered or waived
    if not re.search(r"\b(ui|frontend|index\s*page|web\s*surface)\b", text, re.I):
        lint("ui-surface", "plan neither covers nor waives the legacy UI surface")

    # N2: every preserve: item in migration.yaml must appear in the plan
    try:
        my = open("migration.yaml").read()
        import re as _re
        pres = _re.findall(r"^\s*-\s*([A-Za-z0-9_./:-]+)", my[my.index("preserve:"):], _re.M) if "preserve:" in my else []
        for item in pres:
            if item not in text:
                lint("preserve", f"preserved integration '{item}' mapped to no task")
    except FileNotFoundError:
        pass

    # findings coverage
    if len(sys.argv) > 2:
        d = json.load(open(sys.argv[2]))
        mandatory = set()
        for rs in d:
            for rid, v in (rs.get("violations") or {}).items():
                if (v.get("category") or "mandatory") == "mandatory":
                    mandatory.add(rid)
        missing = {r for r in mandatory if r not in text}
        for r in sorted(missing):
            lint("findings", f"mandatory finding {r} mapped to no task")

    print("\n".join(problems) if problems else
          f"PLAN OK: {len(heads)} tasks, classes {dict((c, list(classes.values()).count(c)) for c in set(classes.values()))}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
