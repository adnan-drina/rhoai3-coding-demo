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


def section_body(text, needle):
    """Body of the heading containing `needle`, down to the next heading of
    the SAME or HIGHER level — so deeper (###/####) subheadings within the
    section are included, not treated as its terminator."""
    m = re.search(r"^(#{2,6})[ \t]+.*" + needle + r".*$", text, re.M | re.I)
    if not m:
        return ""
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(r"^#{1," + str(level) + r"}[ \t]", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def governing_role(sec7, cls):
    """REDESIGN/HARVEST governing a class mention in §7 — handles BOTH the
    inline form (`Cls` — REDESIGN) and the subheading form (### REDESIGN /
    - `Cls`). Returns 'REDESIGN', 'HARVEST', or None (not found)."""
    m = re.search(r"\b" + re.escape(cls) + r"\b", sec7)
    if not m:
        return None
    ls = sec7.rfind("\n", 0, m.start()) + 1
    le = sec7.find("\n", m.end())
    line = sec7[ls: le if le >= 0 else len(sec7)]
    if "REDESIGN" in line:
        return "REDESIGN"
    if "HARVEST" in line:
        return "HARVEST"
    pre = sec7[:m.start()]  # nearest preceding subheading wins
    return "REDESIGN" if pre.rfind("REDESIGN") > pre.rfind("HARVEST") else "HARVEST"


def main():
    text = open(sys.argv[1], encoding="utf-8").read()
    # split into sections by heading
    parts = re.split(r"^#{2,3}\s+(?:\d+\.\s*)?(.+)$", text, flags=re.M)
    sections = {}
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i].strip()] = parts[i + 1]
    # §7 may carry ### HARVEST / ### REDESIGN subheadings, which the
    # #{2,3} split above would truncate at — capture the whole section
    # (down to the next same-or-higher heading) so its classifications
    # survive for the thin/cite/classroles checks.
    sec7 = section_body(text, "class role")
    for t in list(sections):
        if "class role" in t.lower():
            sections[t] = sec7

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
                if governing_role(sec7, cls) != "REDESIGN":
                    problems.append(f"RUBRIC:classroles: '{cls}' carries a CDI/JAX-RS/stereotype annotation "
                                    f"but §7 does not classify it REDESIGN")

    # targetContract -> §7 hard-pin cross-check (V5: getIdempotent/
    # validateInput/mapErrors/cacheRefreshGuard were all true but §7 wrote
    # SOFT prose — "GET idempotent" without 404, "needs bounded refresh"
    # without the guard). Each enabled flag must appear in §7 as its
    # DECISIVE token (404, 400, 503, ...) — decisive tokens do not occur in
    # descriptive/aspirational prose, so this forces a real decision.
    DECISIVE = {
        "getIdempotent": (r"\b404\b", "404-on-missing"),
        "validateInput": (r"\b400\b|@Min|@Valid|problem.?detail", "400/validation"),
        "mapErrors": (r"\b503\b|ExceptionMapper", "503/ExceptionMapper"),
        "threadSafeState": (r"ConcurrentHashMap|compute\(", "ConcurrentHashMap/compute"),
        "cacheRefreshGuard": (r"no clear|clear.?on.?miss|refresh.?guard|\bTTL\b|\b60\s*s|time.?stamp guard", "refresh-guard"),
        "normalizeBeforeDerive": (r"normalize.{0,20}before|dedup.{0,20}before|before (?:deriv|aggregat|comput|total|pric|sum)", "normalize-before-derive"),
    }
    try:
        myaml = open("migration.yaml", encoding="utf-8").read()
    except OSError:
        myaml = ""
    tc = re.search(r"^targetContract:(.*?)(^\S|\Z)", myaml, re.M | re.S)
    if tc:
        for flag, (tok, label) in DECISIVE.items():
            if re.search(rf"^\s*{flag}:\s*true", tc.group(1), re.M) and not re.search(tok, sec7, re.I):
                problems.append(f"RUBRIC:target-soft: targetContract.{flag} is true but §7 does not concretely "
                                f"decide it ({label}) — state the decided target, not descriptive prose")

    print("\n".join(problems) if problems else
          f"PROFILE OK: {len(REQUIRED)} sections present, cited, plan-free")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
