#!/usr/bin/env python3
"""M1 rubric: deterministic structure/evidence check for
migration/architecture-profile.md (judgment quality is reviewed by a
human/retro; this gate only makes sure the judgment is inspectable).

Usage: profile-rubric.py <architecture-profile.md> [<legacy-src-dir>]
When the legacy source dir is given, §7 class-role classification is
cross-checked deterministically (every CDI/JAX-RS class must be REDESIGN).
Exit 0 = pass; findings printed one per line as 'RUBRIC:<class>: ...'.
"""
import os
import re
import sys

REQUIRED = [
    "Purpose & domain",
    "Components & relationships",
    "Integration surfaces",
    "Behavioral contract sources",
    "Modernization surface",
    "Domain boundaries",
    "Class roles",
]

# a class carrying one of these is a REDESIGN class (owns runtime behavior)
REDESIGN_ANNO = re.compile(
    r"@(Service|Component|RestController|Repository|Path|ApplicationScoped"
    r"|Singleton|RequestScoped|RegisterRestClient)\b")

# a citation is a source path with optional :line, a finding rule id, or
# a test class reference
CITE = re.compile(
    r"(src/(?:main|test)/\S+|/projects/legacy/\S+|"
    r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+-\d+|"      # windup rule ids
    r"\b[A-Z]\w+Test\b)")

problems = []


def main():
    text = open(sys.argv[1], encoding="utf-8").read()
    # split into sections by heading
    parts = re.split(r"^#{2,3}\s+(?:\d+\.\s*)?(.+)$", text, flags=re.M)
    sections = {}
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i].strip()] = parts[i + 1]

    for name in REQUIRED:
        body = next((b for t, b in sections.items() if name.lower() in t.lower()), None)
        if body is None:
            problems.append(f"RUBRIC:missing: section '{name}' absent")
            continue
        words = len(body.split())
        if words < 30:
            problems.append(f"RUBRIC:thin: section '{name}' has {words} words (<30)")
        if not CITE.search(body):
            problems.append(f"RUBRIC:uncited: section '{name}' contains no evidence citation (path, rule id, or test)")

    # plan-leakage guard: the profile records what IS, not the plan
    if re.search(r"^#{2,4}\s+T-\d+", text, re.M) or re.search(r"\btask breakdown\b", text, re.I):
        problems.append("RUBRIC:plan-leakage: profile contains task structures — M2/M3 own sequencing and tasks")

    # §7 classification cross-check (deterministic): every class the legacy
    # source marks CDI/JAX-RS/Spring-stereotype is a REDESIGN class and must
    # be marked REDESIGN in §7 — a service mislabeled HARVEST would be
    # re-pinned faithful, reintroducing the shipped-faithful bug.
    if len(sys.argv) > 2 and os.path.isdir(sys.argv[2]):
        sec7 = next((b for t, b in sections.items() if "class role" in t.lower()), "")
        for dp, _, fs in os.walk(sys.argv[2]):
            if "/test" in dp:
                continue
            for fn in fs:
                if not fn.endswith(".java"):
                    continue
                body = open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()
                if not REDESIGN_ANNO.search(body):
                    continue
                cls = fn[:-5]
                if not re.search(rf"\b{re.escape(cls)}\b[^\n]*REDESIGN", sec7):
                    problems.append(f"RUBRIC:classroles: '{cls}' carries a CDI/JAX-RS/stereotype annotation "
                                    f"but §7 does not classify it REDESIGN")

    print("\n".join(problems) if problems else
          f"PROFILE OK: {len(REQUIRED)} sections present, cited, plan-free")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
