#!/usr/bin/env python3
"""M2 gate: deterministic roadmap/brief check (redesign §2).

Usage: roadmap-lint.py <roadmap.md> [findings-inventory.md] [legacy-dir]

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
  fabrication — (needs legacy-dir) every annotation/method the brief QUOTES
               as legacy code in its 'In scope' section must actually exist
               in the legacy source. Catches SEQUENCING inventing a contract
               that is not in the tree (V5 run-4: S02 fabricated a JPA layer,
               S03 fabricated the ShoppingCartService API). plan-lint cannot
               catch it — the plan is well-formed, just false.
"""
import glob
import os
import re
import sys

problems = []


def lint(cls, detail):
    problems.append(f"LINT:{cls}: {detail}")


_JKW = {"if", "for", "while", "switch", "catch", "return", "new", "throws",
        "throw", "public", "private", "protected", "class", "interface",
        "void", "import", "package", "extends", "implements", "super", "this",
        "instanceof", "else", "do", "try", "finally", "synchronized", "assert"}


def brief_fidelity(sid, btext, legacy_dir):
    """Every annotation/method the brief QUOTES as legacy code (in 'In scope')
    must exist in the legacy source. Comments and target-arrows (// →) are
    stripped before extracting claims, so target hints are exempt — only the
    'this is the legacy code' quotes are checked."""
    m = re.search(r"^##\s+In scope\s*$(.*?)(?:^##\s|\Z)", btext, re.M | re.S)
    if not m:
        return
    section = m.group(1)
    # pair each cited `<path>.java` with the fenced block that follows it
    items = re.split(r"^\s*-\s+`([^`]+\.java)`", section, flags=re.M)
    for i in range(1, len(items) - 1, 2):
        block_file = items[i].strip()
        fence = re.search(r"```[a-zA-Z]*\n(.*?)```", items[i + 1], re.S)
        if not fence:
            continue
        legpath = os.path.join(legacy_dir, block_file)
        if not os.path.isfile(legpath):
            continue  # cannot verify (target path / later-story class) — skip
        legsrc = open(legpath, encoding="utf-8", errors="replace").read()
        # strip comments and target arrows before reading the legacy CLAIMS
        claims = "\n".join(re.split(r"//|→|-->|->", ln)[0]
                           for ln in fence.group(1).splitlines())
        cls_name = os.path.basename(block_file)
        for ann in sorted(set(re.findall(r"@(\w+)", claims))):
            if not re.search(rf"@{ann}\b", legsrc):
                lint("fabrication",
                     f"{sid}: brief cites @{ann} on {cls_name} but it is "
                     f"absent from the legacy source (invented annotation)")
        for meth in sorted(set(re.findall(r"\b([a-z]\w*)\s*\(", claims))):
            if meth in _JKW:
                continue
            if not re.search(rf"\b{re.escape(meth)}\s*\(", legsrc):
                lint("fabrication",
                     f"{sid}: brief cites method '{meth}(' on {cls_name} but "
                     f"it is absent from the legacy source (invented method)")


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

    # numbering must be contiguous from S01 (dry-run catch: a session
    # left S01,S03 after renumbering mid-flight and the lint passed)
    expect = [f"S{i:02d}" for i in range(1, len(ids) + 1)]
    if ids != expect:
        lint("stories", f"story numbering not contiguous: {ids} (want {expect})")

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
            if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+", fid):
                lint("stories", f"{sid}: findings field contains non-rule-id token '{fid[:40]}' — ids only, no prose")
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
    legacy_dir = sys.argv[3] if len(sys.argv) > 3 and os.path.isdir(sys.argv[3]) else None
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
        if legacy_dir:
            brief_fidelity(sid, btext, legacy_dir)

    print("\n".join(problems) if problems else
          f"ROADMAP OK: {len(ids)} stories, {len(owned)} findings owned, "
          f"deploy milestones: {[s for s, f in deploy_flags if f]}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
