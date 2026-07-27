#!/usr/bin/env python3
"""M2 gate: deterministic roadmap/brief check (redesign §2).

Usage: roadmap-lint.py <roadmap.md> [findings-inventory.md]

Checks (exit 0 = accepted; findings printed as 'LINT:<class>: ...'):
  stories    — parseable S<NN> headings, unique, with required fields
  coverage   — every mandatory finding id (minus recipe-executed and
               non-mandatory, read from the inventory summary) owned by
               exactly one story
  order      — depends: reference only EARLIER stories; no cycles by
               construction
  deploy     — at least one deploy story; the LAST story deploys
  briefs     — migration/briefs/S<NN>-*.md exists per story and carries
               the template's required sections
  substance  — every story's scope names at least one code/test path
               (no ceremonial stories)
"""
import glob
import os
import re
import sys

problems = []


def lint(cls, detail):
    problems.append(f"LINT:{cls}: {detail}")


BRIEF_SECTIONS = ["Goal & position", "In scope", "Out of scope",
                  "Decided target shapes", "Contracts", "Done-criteria"]


def main():
    text = open(sys.argv[1], encoding="utf-8").read()
    heads = re.findall(r"^##\s+(S\d{2,})\s*:\s*(.+)$", text, re.M)
    if not heads:
        lint("stories", "no parseable story headings (want '## S01: title')")
        print("\n".join(problems))
        return 1

    ids = [h[0] for h in heads]
    for sid in set(ids):
        if ids.count(sid) > 1:
            lint("stories", f"{sid}: story id used more than once")

    parts = re.split(r"^##\s+(S\d{2,})\s*:.*$", text, flags=re.M)
    bodies = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}

    def field(sid, name):
        m = re.search(rf"^-\s*{name}:\s*(.+)$", bodies.get(sid, ""), re.M)
        return m.group(1).strip() if m else None

    owned = {}
    deploy_flags = []
    for pos, sid in enumerate(ids):
        for name in ("scope", "findings", "depends", "deploy", "done", "rationale"):
            if field(sid, name) is None:
                lint("stories", f"{sid}: missing field '{name}'")
        scope = field(sid, "scope") or ""
        if not re.search(r"(src/|\.java|\.properties|pom\.xml|k8s/)", scope):
            lint("substance", f"{sid}: scope names no code/test path — ceremonial story")
        for fid in re.split(r"[,\s]+", field(sid, "findings") or ""):
            if not fid or fid == "-":
                continue
            if fid in owned:
                lint("coverage", f"finding {fid} owned by both {owned[fid]} and {sid}")
            owned[fid] = sid
        dep = field(sid, "depends") or "-"
        if dep != "-":
            for d in re.split(r"[,\s]+", dep):
                if d and d not in ids[:pos]:
                    lint("order", f"{sid}: depends on '{d}' which is not an earlier story")
        deploy_flags.append((sid, (field(sid, "deploy") or "").lower() == "true"))

    if not any(f for _, f in deploy_flags):
        lint("deploy", "no story is marked deploy: true")
    elif not deploy_flags[-1][1]:
        lint("deploy", f"last story {deploy_flags[-1][0]} must deploy")

    # coverage vs the inventory's mandatory (recipe/rewrite/infer/OPEN) sets;
    # recipe-executed and non-mandatory ids are exempt
    if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
        inv = open(sys.argv[2], encoding="utf-8").read()
        must, exempt = set(), set()
        for m in re.finditer(r"^-\s*(rewrite|infer|OPEN DESIGN):\s*\d+\s*—\s*(.+)$", inv, re.M):
            must |= {i.strip() for i in m.group(2).split(",")}
        for m in re.finditer(r"^-\s*(recipe|non-mandatory):\s*\d+\s*—\s*(.+)$", inv, re.M):
            exempt |= {i.strip() for i in m.group(2).split(",")}
        for fid in sorted(must - set(owned)):
            lint("coverage", f"mandatory finding {fid} owned by no story")
        for fid in sorted(set(owned) & exempt):
            lint("coverage", f"{fid} is {'recipe-executed' if fid not in must else 'exempt'} — no story should own it (owned by {owned[fid]})")

    # briefs exist and are complete
    base = os.path.dirname(os.path.abspath(sys.argv[1]))
    for sid in ids:
        matches = glob.glob(os.path.join(base, "briefs", f"{sid}-*.md"))
        if not matches:
            lint("briefs", f"{sid}: no brief file migration/briefs/{sid}-*.md")
            continue
        btext = open(matches[0], encoding="utf-8").read()
        for sec in BRIEF_SECTIONS:
            if sec.lower() not in btext.lower():
                lint("briefs", f"{sid}: brief missing section '{sec}'")
        if "```" not in btext:
            lint("briefs", f"{sid}: brief has no code excerpt (In scope must quote legacy lines)")

    print("\n".join(problems) if problems else
          f"ROADMAP OK: {len(ids)} stories, {len(owned)} findings owned, "
          f"deploy milestones: {[s for s, f in deploy_flags if f]}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
