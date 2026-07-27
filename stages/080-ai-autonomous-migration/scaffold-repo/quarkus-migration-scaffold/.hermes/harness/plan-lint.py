#!/usr/bin/env python3
"""Deterministic Phase B plan lint (improvement plan B2).

Usage: plan-lint.py <tasks.md> [mta-findings.json] [--findings-scope id1,id2]

--findings-scope (M3 story scoping, redesign §3): restrict the
mandatory-findings coverage check to the listed rule ids — the story's
assigned findings from the roadmap. All other checks stay global.

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
    args = sys.argv[1:]
    scope = None
    if "--findings-scope" in args:
        i = args.index("--findings-scope")
        scope = {s.strip() for s in args[i + 1].split(",") if s.strip()}
        del args[i:i + 2]
    tasks_path = args[0]
    text = open(tasks_path).read()

    heads = re.findall(r"^(#{2,6})\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M)
    if not heads:
        lint("ids", "no parseable task headings (want '#### T-001: title')")
        print("\n".join(problems))
        return 1

    # id uniqueness — duplicate ids corrupt the supervisor's commit checks
    seen = set()
    for _, tid, _ in heads:
        if tid in seen:
            lint("dup-ids", f"{tid}: task id used more than once")
        seen.add(tid)

    # split body per task
    bodies = {}
    parts = re.split(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:.*$", text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        bodies[parts[i]] = parts[i + 1]

    classes = {}
    for _, tid, _ in heads:
        body = bodies.get(tid, "")
        # Accept any line that ties Class/Type to rewrite|infer — models
        # express the marker in several shapes (**Class**:, Type: `Class:
        # rewrite`, Class - infer). Substance over syntax.
        m = re.search(r"^[^\n]*(?:Class|Type)[^\n]*?\b(rewrite|infer)\b", body, re.M | re.I)
        classes[tid] = m.group(1).lower() if m else "unknown"
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

    # Package identity: the destination's package root is a project
    # constant (AGENTS.md); plans that target legacy packages replicate
    # the monolith's identity into the migrated service.
    # Fire only on TARGET-position references: a migration plan must name
    # the legacy package as the SOURCE (from→to lines, staging paths are
    # fine); the defect is placing migrated code there (run #2) — i.e. a
    # destination path or Target line carrying the legacy root.
    for line in text.splitlines():
        if "migration/staging/" in line:
            continue
        if re.search(r"(?:Target|→|->)\s*[^\n]*src/(?:main|test)/java/com/redhat/coolstore", line) \
                or re.search(r"^\*\*Target\*\*.*com[./]redhat[./]coolstore", line):
            lint("package", f"legacy package in TARGET position: {line.strip()[:80]} — project root is com.demo (AGENTS.md)")
    # Task substance (T-029 class, M3 dry-run catch: 'waiver' and
    # 'coverage' tasks with no code path): every task body must name a
    # concrete artifact it changes.
    substance = re.compile(r"src/(?:main|test)/|pom\.xml|k8s/|application\.properties|migration\.yaml|migration/staging/")
    for _, tid, _ in heads:
        if not substance.search(bodies.get(tid, "")):
            lint("substance", f"{tid}: task body names no code/config path it changes — ceremonial task (waivers belong in spec prose, not tasks)")

    # N2: every preserve: item in migration.yaml must appear in the plan
    try:
        my = open("migration.yaml").read()
        import re as _re
        pres = _re.findall(r"^\s*-\s*([A-Za-z0-9_./:-]+)", my[my.index("preserve:"):], _re.M) if "preserve:" in my else []
        for item in pres:
            if item not in text:
                lint("preserve", f"preserved integration '{item}' mapped to no task")
        # Ship acceptance is part of the contract (cart run #2: the stamped
        # acceptance.path had no endpoint anywhere in the plan, discovered
        # only at ship time). The path must be mapped to a task.
        m = _re.search(r"^acceptance:\s*\n\s*path:\s*(\S+)", my, _re.M)
        if m and m.group(1) not in text:
            lint("acceptance", f"acceptance path '{m.group(1)}' (migration.yaml) mapped to no task — the app must serve it")
    except FileNotFoundError:
        pass

    # findings coverage — a mandatory rule is covered by a task OR by a
    # recipe execution recorded in migration/recipe-log.md (R3: recipe-
    # executed rewrites need no plan task).
    if len(args) > 1:
        d = json.load(open(args[1]))
        mandatory = set()
        for rs in d:
            for rid, v in (rs.get("violations") or {}).items():
                if (v.get("category") or "mandatory") == "mandatory":
                    mandatory.add(rid)
        if scope is not None:
            mandatory &= scope
        try:
            recipe_log = open("migration/recipe-log.md").read()
        except OSError:
            recipe_log = ""
        missing = {r for r in mandatory if r not in text and r not in recipe_log}
        for r in sorted(missing):
            lint("findings", f"mandatory finding {r} mapped to no task (and not recipe-executed)")

    print("\n".join(problems) if problems else
          f"PLAN OK: {len(heads)} tasks, classes {dict((c, list(classes.values()).count(c)) for c in set(classes.values()))}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
