#!/usr/bin/env python3
"""M2 gate: deterministic roadmap/brief check (redesign §2).

Usage: roadmap-lint.py <roadmap.md> [findings-inventory.md] [legacy-dir]
                       [architecture-profile.md] [--story SNN]

  --story SNN  O-M3PREFLIGHT: only emit LINT lines for that story id
               (brief-quality gate before first M3 seat; other stories
               proceed independently).

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
  non-mandatory — (K3) every non-mandatory inventory rule is marked
               adopt or defer (reason) in the roadmap or a brief
  O-PORTDERIVE — (ARCH A1) stories that own OPEN DESIGN findings or scope
               a profile §7 REDESIGN class must carry a REDESIGN target-
               contract in the brief (class + target shape). Profile path
               is argv[4] or sibling architecture-profile.md.
  O-STORYKIND — (ARCH A3) those same stories must declare
               kind: rename|reimplement|mixed. OPEN DESIGN forbids bare
               rename; mixed requires justification / split suggestion.
  O-SEATBUDGET — (ARCH A5) stories with kind must declare seat-budget: N
               matching kind × max(incident units, scope floor)
               (see seat-budget.py / O-SEATSIZE). Brief must publish the same N.
  O-SCOPECOVER — every migration/staging/**/*.java path is in exactly one
               story scope; every src/**/*.java scope path is in staging
               or migration/scope-exclusions.md (typed reason).
  O-BRIEFCOVER — every path in a story's roadmap scope must be named
               (basename or full path) in that story's brief — stops
               layer-sample briefs that leave M3 with no per-class contracts.
  O-BRIEFCONTRACT — every §7 REDESIGN class in story scope must have its
               own contract line in the brief (class + target-shape token).
               O-PORTDERIVE is story-level existence; this is per-class density.
  O-BRIEFFRESH — brief carries <!-- O-BRIEFFRESH sha256=… --> matching a
               content hash of current roadmap scope/findings/kind/budget
               (mtime is not trusted; recompose without regen → RED).
  O-BRIEFQUALITY — composite score (coverage, contracts, specificity,
               oracle, freshness); floor BRIEF_QUALITY_FLOOR (default 80).
               Enforced on --story (O-M3PREFLIGHT), BRIEF_QUALITY_ENFORCE=1,
               and outer-loop M2 exit (m2_brief_quality_exit); full M2 without
               ENFORCE prints SCORE lines without failing.
  O-BRIEFQCONT — contracts dimension = dedicated/required (family lines
               that name multiple in-scope classes do not max the score).
  O-CYCLEPART — every class/path in dependency-order.md "## Circular group"
               must be owned by one story, or roadmap must carry an explicit
               cycle waiver (## Cycle partition waivers / O-CYCLEPART-WAIVE).
  O-SEATBUDGETUNIQ — brief must not publish conflicting seat-budget: N
               values (presence alone is not enough).
  O-M3PREFLIGHT — outer-loop re-runs this lint per story (--story) against
               the *current* roadmap before the first M3 seat; SID-scoped
               RED refuses that story's seats without blocking others.
"""
import glob
import hashlib
import importlib.util
import os
import re
import sys

problems = []
STORY_FILTER = None  # set by --story SNN (O-M3PREFLIGHT)
quality_reports = []  # (sid, score, dims)

_FRESH_MARK = re.compile(
    r"<!--\s*O-BRIEFFRESH\s+sha256=([0-9a-fA-F]+)\s*-->", re.I
)

_SB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seat-budget.py")
_sb_spec = importlib.util.spec_from_file_location("seat_budget", _SB_PATH)
seat_budget = importlib.util.module_from_spec(_sb_spec)
assert _sb_spec.loader is not None
_sb_spec.loader.exec_module(seat_budget)


def lint(cls, detail):
    problems.append(f"LINT:{cls}: {detail}")


# O-BRIEFCONTRACT substance: bare `target:` / JUDGMENT placeholders do NOT count.
# Family §7 paste must carry a concrete shape token (or non-comment target text).
_TARGET_SHAPE = re.compile(
    r"(?i)(?:→|->|=>|target contract|JAX-RS|@ApplicationScoped|"
    r"Panache|ConcurrentHashMap|ExceptionMapper|\b404\b|CDI|Agroal|"
    r"@Path\b|PersistenceException|compute\(|@Transactional|"
    r"\bremoved\b|target\s*:\s*(?!<!--)\S)"
)
_JUDGMENT_TARGET = re.compile(
    r"(?i)target\s*:\s*<!--\s*JUDGMENT"
)
_CLASS_TOKEN = re.compile(r"`([A-Z][A-Za-z0-9]+)`|\*\*([A-Z][A-Za-z0-9]+)\*\*")


def line_has_contract_substance(ln: str) -> bool:
    """True when a brief/profile line carries a real target shape (not a stub)."""
    if _JUDGMENT_TARGET.search(ln):
        return False
    return bool(_TARGET_SHAPE.search(ln))


def brief_has_redesign_contract(btext: str) -> bool:
    """REDESIGN/OPEN DESIGN + CapWord class + target-shape token (O-PORTDERIVE)."""
    if not re.search(r"(?i)\bREDESIGN\b|\bOPEN DESIGN\b", btext):
        return False
    if not _CLASS_TOKEN.search(btext):
        return False
    for ln in btext.splitlines():
        if _CLASS_TOKEN.search(ln) and line_has_contract_substance(ln):
            return True
    return False


def brief_classes_missing_contracts(btext: str, classes) -> list:
    """O-BRIEFCONTRACT — each §7 REDESIGN class needs class+shape on one line."""
    missing = []
    for c in classes:
        ok = False
        for ln in btext.splitlines():
            if not re.search(
                rf"(?:`{re.escape(c)}`|\*\*{re.escape(c)}\*\*|\b{re.escape(c)}\b)",
                ln,
            ):
                continue
            if line_has_contract_substance(ln):
                ok = True
                break
        if not ok:
            missing.append(c)
    return missing


def brief_dedicated_contract_classes(btext: str, classes) -> set:
    """O-BRIEFQCONT — classes with a *dedicated* (single-class) contract line.

    A family / comma-list line that names multiple in-scope REDESIGN classes
    counts for O-BRIEFCONTRACT (binary) but not as dedicated for the quality
    score — shared paste must not max the contracts dimension.
    """
    class_set = set(classes)
    dedicated = set()
    for ln in btext.splitlines():
        if not line_has_contract_substance(ln):
            continue
        named = []
        for m in _CLASS_TOKEN.finditer(ln):
            nm = m.group(1) or m.group(2)
            if nm in class_set:
                named.append(nm)
        if len(named) == 1:
            dedicated.add(named[0])
    return dedicated


def story_fresh_hash(sid, scope, findings_raw, kind_raw, seat_budget_raw) -> str:
    """O-BRIEFFRESH — content hash of roadmap fields that invalidate a brief."""
    paths = sorted(p.strip() for p in (scope or "").split(",") if p.strip())
    payload = "\n".join(
        [
            (sid or "").strip(),
            ",".join(paths),
            (findings_raw or "").strip(),
            (kind_raw or "").strip(),
            (seat_budget_raw or "").strip(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def parse_circular_groups(dep_text: str) -> list:
    """Paths (preferred) or ClassName.java from ## Circular group sections."""
    groups = []
    for m in re.finditer(
        r"(?ims)^##\s+Circular group[^\n]*\n(.*?)(?=^##\s|\Z)",
        dep_text,
    ):
        body = m.group(1)
        paths = re.findall(r"\(([^)]+\.java)\)", body)
        if not paths:
            # FQCN bullets without path — use simple name
            for fq in re.findall(
                r"(?m)^-\s+([a-zA-Z0-9_.]+)\s*$", body
            ):
                simple = fq.rsplit(".", 1)[-1]
                if simple and simple[0].isupper():
                    paths.append(simple + ".java")
        if paths:
            groups.append(paths)
    return groups


def roadmap_has_cycle_waiver(roadmap_text: str) -> bool:
    """Explicit architect waiver for multi-story circular groups."""
    if re.search(r"(?i)O-CYCLEPART-WAIVE", roadmap_text):
        return True
    if re.search(
        r"(?im)^##\s+Cycle partition waivers\b", roadmap_text
    ) and re.search(
        r"(?im)^-\s*.*\bwaive\b", roadmap_text
    ):
        return True
    return False


def brief_quality_score(
    btext: str,
    scope_paths,
    scope_hit_classes,
    *,
    fresh_ok: bool,
) -> tuple:
    """O-BRIEFQUALITY — composite 0..100 across five dimensions.

    O-BRIEFQCONT: contracts = dedicated/required (family lines do not max).
    """
    dims = {}
    if scope_paths:
        named = sum(
            1
            for p in scope_paths
            if p in btext or os.path.basename(p) in btext
        )
        dims["coverage"] = int(round(100.0 * named / len(scope_paths)))
    else:
        dims["coverage"] = 100
    if scope_hit_classes:
        # Continuous: only dedicated per-class lines raise the score.
        ded = brief_dedicated_contract_classes(btext, scope_hit_classes)
        dims["contracts"] = int(
            round(100.0 * len(ded) / len(scope_hit_classes))
        )
    else:
        dims["contracts"] = 100
    spec = 0
    if "```" in btext:
        spec += 40
    # O-BRIEFQCONT: specificity needs real class tokens + shape substance,
    # not merely the word "acceptance" next to a fence.
    n_cls = len(_CLASS_TOKEN.findall(btext))
    if n_cls >= 4 and any(
        line_has_contract_substance(ln) for ln in btext.splitlines()
    ):
        spec += 30
    elif n_cls >= 2:
        spec += 20
    elif n_cls >= 1 or _TARGET_SHAPE.search(btext):
        spec += 10
    if re.search(
        r"(?i)\b(preserve|behavioral|oracle|assert|pin|idempotent|"
        r"characterization)\b",
        btext,
    ):
        spec += 20
    if re.search(r"(?i)\bacceptance\b", btext) and n_cls >= 2:
        spec += 10
    dims["specificity"] = min(100, spec)
    m_done = re.search(
        r"(?is)^##\s+Done-criteria\s*(.*?)(?:^##\s|\Z)", btext, re.M
    )
    done = (m_done.group(1) if m_done else "").strip()
    # Strip HTML comments for length
    done_plain = re.sub(r"<!--.*?-->", "", done, flags=re.S).strip()
    if len(done_plain) > 60:
        dims["oracle"] = 100
    elif len(done_plain) > 25:
        dims["oracle"] = 70
    elif len(done_plain) > 8:
        dims["oracle"] = 40
    else:
        dims["oracle"] = 15
    dims["freshness"] = 100 if fresh_ok else 0
    score = int(round(sum(dims.values()) / len(dims)))
    return score, dims


def redesign_classes_from_profile(prof: str) -> set:
    """CapWord classes governed by REDESIGN in architecture-profile §7.

    Family lines (comma-lists / All ClassA, ClassB under a REDESIGN heading)
    expand to every backtick/bold CapWord — not only .java-backed names.
    """
    sec7 = ""
    m = re.search(r"^(#{2,6})[ \t]+.*Class roles.*$", prof, re.M | re.I)
    if not m:
        return set()
    level = len(m.group(1))
    rest = prof[m.end():]
    nxt = re.search(r"^#{1," + str(level) + r"}[ \t]", rest, re.M)
    sec7 = rest[: nxt.start()] if nxt else rest
    java_named = set(re.findall(r"\b([A-Z]\w+)\.java\b", sec7))
    name_re = re.compile(r"`([A-Z]\w+)`|\*\*([A-Z]\w+)\*\*|\b([A-Z]\w+)\.java\b")
    out = set()
    for mm in name_re.finditer(sec7):
        nm = mm.group(1) or mm.group(2) or mm.group(3)
        if not nm or nm in ("REDESIGN", "HARVEST", "All"):
            continue
        ls = sec7.rfind("\n", 0, mm.start()) + 1
        le = sec7.find("\n", mm.start())
        line = sec7[ls: le if le >= 0 else len(sec7)]
        if "HARVEST" in line and "REDESIGN" not in line:
            continue
        pre = sec7[: mm.start()]
        under_redesign = (
            "REDESIGN" in line or pre.rfind("REDESIGN") > pre.rfind("HARVEST")
        )
        if not under_redesign:
            continue
        # Backtick/bold CapWord OR .java mention — family lines expand here.
        if nm in java_named or mm.group(1) or mm.group(2):
            out.add(nm)
    return out


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


def _parse_argv(argv):
    """Positional args + optional --story SNN / --story=SNN (O-M3PREFLIGHT)."""
    global STORY_FILTER
    pos = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--story" and i + 1 < len(argv):
            STORY_FILTER = argv[i + 1].strip()
            i += 2
            continue
        if a.startswith("--story="):
            STORY_FILTER = a.split("=", 1)[1].strip()
            i += 1
            continue
        if a.startswith("--"):
            print(f"LINT:args: unknown flag {a}", file=sys.stderr)
            i += 1
            continue
        pos.append(a)
        i += 1
    return pos


def main():
    global problems, quality_reports
    problems = []
    quality_reports = []
    argv = _parse_argv(sys.argv[1:])
    if not argv:
        print("Usage: roadmap-lint.py <roadmap.md> [findings-inventory.md] "
              "[legacy-dir] [architecture-profile.md] [--story SNN]",
              file=sys.stderr)
        return 2
    text = open(argv[0], encoding="utf-8").read()
    # Positionals only — --story already captured in STORY_FILTER.
    sys.argv = [sys.argv[0]] + argv
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
        # Same-line value only — do NOT let \s after ':' eat the newline
        # (that glued "- findings:\\n- depends:" into findings="depends: -").
        m = re.search(rf"^-\s*{name}:[ \t]*(.*)$", bodies.get(sid, ""), re.M)
        if not m:
            return None
        return m.group(1).strip()

    owned = {}
    deploy_flags = []
    for pos, sid in enumerate(ids):
        for name in ("scope", "findings", "depends", "deploy", "done", "rationale"):
            if field(sid, name) is None:
                lint("stories", f"{sid}: missing field '{name}'")
        scope = field(sid, "scope") or ""
        if not re.search(r"(src/|\.java|\.properties|pom\.xml|k8s/)", scope):
            lint("substance", f"{sid}: scope names no code/test path — ceremonial story")
        # O-SCOPENOGEN — build outs (target/, build/) must not appear in scope
        gen_hits = [
            p.strip()
            for p in scope.split(",")
            if p.strip()
            and re.search(
                r"(?:^|/)(?:target|build)(?:/|$)|(?:^|/)generated-sources/",
                p.strip().replace("\\", "/").lstrip("./"),
            )
        ]
        if gen_hits:
            lint(
                "O-SCOPENOGEN",
                f"{sid}: scope lists build-generated path(s) "
                f"({gen_hits[0]}"
                f"{' +' + str(len(gen_hits) - 1) + ' more' if len(gen_hits) > 1 else ''}"
                f") — exclude target/build outs; harvest DTOs via staging/"
                f"src paths (O-SCOPENOGEN)",
            )
        # S-FND: blank findings are a footgun (M2 bounce). "-" is allowed only
        # for pure HARVEST/characterization stories (models/tests, no redesign).
        findings_raw = (field(sid, "findings") or "").strip()
        if not findings_raw:
            lint("stories", f"{sid}: findings field is empty — list rule ids or '-' for a pure HARVEST story (S-FND)")
        elif findings_raw == "-":
            rationale = (field(sid, "rationale") or "") + " " + (field(sid, "done") or "")
            scope = field(sid, "scope") or ""
            harvestish = bool(
                re.search(r"HARVEST|characterization|model layer|models?", rationale + " " + scope, re.I)
            )
            redesignish = bool(
                re.search(r"service/|rest/|Endpoint|Service\.java|pom\.xml", scope, re.I)
            )
            if redesignish and not harvestish:
                lint(
                    "stories",
                    f"{sid}: findings: '-' is only for HARVEST/characterization stories — own the redesign findings or split the story (S-FND)",
                )
        for fid in re.split(r"[,\s]+", findings_raw):
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

    # O-CYCLEPART — Circular group members must share one story (or waiver)
    base_early = os.path.dirname(os.path.abspath(sys.argv[1]))
    dep_path = os.path.join(base_early, "dependency-order.md")
    if os.path.isfile(dep_path) and not roadmap_has_cycle_waiver(text):
        try:
            dep_text = open(dep_path, encoding="utf-8").read()
        except OSError:
            dep_text = ""
        for gi, gpaths in enumerate(parse_circular_groups(dep_text), start=1):
            owners = {}
            for p in gpaths:
                base_n = os.path.basename(p)
                for sid in ids:
                    scope = field(sid, "scope") or ""
                    if p in scope or re.search(
                        rf"(?:^|[,/\s]){re.escape(base_n)}(?:\s|,|$)", scope
                    ):
                        owners.setdefault(sid, []).append(base_n)
                        break
            story_set = sorted(owners)
            if len(story_set) > 1:
                counts = ", ".join(
                    f"{s}:{len(owners[s])}" for s in story_set
                )
                lint(
                    "O-CYCLEPART",
                    f"circular group #{gi} spans {len(story_set)} stories "
                    f"({counts}) — keep the cycle in one story or add "
                    f"'## Cycle partition waivers' / O-CYCLEPART-WAIVE with "
                    f"reason (O-CYCLEPART)",
                )

    # coverage vs the inventory's mandatory (recipe/rewrite/infer/OPEN) sets;
    # recipe-executed and non-mandatory ids are exempt from story ownership
    inv = ""
    open_design = set()
    if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
        inv = open(sys.argv[2], encoding="utf-8").read()
        must, exempt = set(), set()
        def _rule_ids(blob: str) -> set:
            # Only real rule-ids (reject empty "0 —" tails / inventory prose).
            return {
                i.strip()
                for i in blob.split(",")
                if i.strip()
                and re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+", i.strip())
            }

        for m in re.finditer(r"^-\s*(rewrite|infer|OPEN DESIGN):\s*\d+\s*—\s*(.*)$", inv, re.M):
            ids_line = _rule_ids(m.group(2))
            must |= ids_line
            if m.group(1) == "OPEN DESIGN":
                open_design |= ids_line
        for m in re.finditer(r"^-\s*(recipe|non-mandatory):\s*\d+\s*—\s*(.*)$", inv, re.M):
            exempt |= _rule_ids(m.group(2))
        for fid in sorted(must - set(owned)):
            lint("coverage", f"mandatory finding {fid} owned by no story")
        for fid in sorted(set(owned) & exempt):
            lint("coverage", f"{fid} is {'recipe-executed' if fid not in must else 'exempt'} — no story should own it (owned by {owned[fid]})")

    # O-SCOPECOVER — staging file coverage (mirror findings coverage)
    base = os.path.dirname(os.path.abspath(sys.argv[1]))
    staging_root = os.path.join(base, "staging")
    if os.path.isdir(staging_root):
        # O-SCOPENONJAVA — same suffixes as m2-compose list_staging_java
        _scope_suf = (".java", ".properties", ".yaml", ".yml", ".xml")

        def _is_scope_path(path: str) -> bool:
            low = path.lower()
            return any(low.endswith(s) for s in _scope_suf)

        staging_files: set[str] = set()
        for dirpath, _dns, fnames in os.walk(staging_root):
            for fn in fnames:
                if not _is_scope_path(fn):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, staging_root).replace("\\", "/")
                if rel.startswith("target/") or "/target/" in f"/{rel}":
                    continue
                staging_files.add(rel)
        scope_owner: dict[str, str] = {}
        for sid in ids:
            scope = field(sid, "scope") or ""
            for part in scope.split(","):
                p = part.strip().lstrip("./")
                if not p or p.startswith("<!--"):
                    continue
                if not _is_scope_path(p):
                    continue
                if p.startswith("target/") or "/target/" in f"/{p}":
                    continue
                if p in scope_owner and scope_owner[p] != sid:
                    lint(
                        "O-SCOPECOVER",
                        f"path {p} owned by both {scope_owner[p]} and {sid}",
                    )
                scope_owner[p] = sid
        excl: set[str] = set()
        excl_path = os.path.join(base, "scope-exclusions.md")
        if os.path.isfile(excl_path):
            try:
                for ln in open(excl_path, encoding="utf-8").read().splitlines():
                    m = re.match(r"^-\s+`?([^`\s]+)`?", ln.strip())
                    if m and _is_scope_path(m.group(1)):
                        excl.add(m.group(1).lstrip("./"))
            except OSError:
                pass
        orphans = sorted(staging_files - set(scope_owner))
        if orphans:
            # O-SCOPECOVERMSG: full list to sidecar (no "+N more" truncation)
            side = "/tmp/roadmap-scopecover.txt"
            try:
                with open(side, "w", encoding="utf-8") as sf:
                    sf.write("# O-SCOPECOVER orphans (staging in no story scope)\n")
                    for p in orphans:
                        sf.write(p + "\n")
            except OSError:
                side = "(sidecar write failed)"
            # Cap inline message but always point at full list
            shown = orphans[:8]
            more = (
                f" … +{len(orphans) - len(shown)} more — full list {side}"
                if len(orphans) > len(shown)
                else f" — full list {side}"
            )
            lint(
                "O-SCOPECOVER",
                f"staging path in no story scope: {', '.join(shown)}{more} "
                f"(O-SCOPECOVER; partition via O-STAGESCOPE)",
            )
        phantoms = sorted(
            p
            for p in scope_owner
            if p.startswith("src/") and p not in staging_files and p not in excl
        )
        if phantoms:
            side = "/tmp/roadmap-scopecover.txt"
            # write (not append) when no orphans so we do not keep a stale orphan list
            mode = "a" if orphans else "w"
            try:
                with open(side, mode, encoding="utf-8") as sf:
                    sf.write("# O-SCOPECOVER phantoms (scope absent from staging)\n")
                    for p in phantoms:
                        sf.write(p + "\n")
            except OSError:
                side = "(sidecar write failed)"
            shown = phantoms[:8]
            more = (
                f" … +{len(phantoms) - len(shown)} more — full list {side}"
                if len(phantoms) > len(shown)
                else f" — full list {side}"
            )
            lint(
                "O-SCOPECOVER",
                f"scope path absent from staging (and not in "
                f"scope-exclusions.md): {', '.join(shown)}{more} (O-SCOPECOVER)",
            )
        # O-SCOPECOVERCLEAR (W4-178 P3): remove stale sidecar on clean coverage
        if not orphans and not phantoms:
            try:
                os.remove("/tmp/roadmap-scopecover.txt")
            except FileNotFoundError:
                pass
            except OSError:
                pass

    # briefs exist and are complete
    base = os.path.dirname(os.path.abspath(sys.argv[1]))
    legacy_dir = sys.argv[3] if len(sys.argv) > 3 and os.path.isdir(sys.argv[3]) else None
    # O-PORTDERIVE: optional profile (argv[4] or sibling architecture-profile.md)
    profile_path = None
    if len(sys.argv) > 4 and os.path.isfile(sys.argv[4]):
        profile_path = sys.argv[4]
    else:
        for cand in (
            os.path.join(base, "architecture-profile.md"),
            os.path.join(os.path.dirname(base), "architecture-profile.md"),
        ):
            if os.path.isfile(cand):
                profile_path = cand
                break
    redesign_cls = set()
    if profile_path:
        try:
            redesign_cls = redesign_classes_from_profile(
                open(profile_path, encoding="utf-8").read()
            )
        except OSError:
            redesign_cls = set()
    brief_texts = []
    for sid in ids:
        matches = glob.glob(os.path.join(base, "briefs", f"{sid}-*.md"))
        if not matches:
            lint("briefs", f"{sid}: no brief file migration/briefs/{sid}-*.md")
            continue
        btext = open(matches[0], encoding="utf-8").read()
        brief_texts.append(btext)
        for sec in BRIEF_SECTIONS:
            if sec.lower() not in btext.lower():
                lint("briefs", f"{sid}: brief missing section '{sec}'")
        if "```" not in btext:
            lint("briefs", f"{sid}: brief has no code excerpt (In scope must quote legacy lines)")
        if legacy_dir:
            brief_fidelity(sid, btext, legacy_dir)
        # O-BRIEFCOVER — every roadmap scope path named in the owning brief
        scope = field(sid, "scope") or ""
        scope_paths = [p.strip() for p in scope.split(",") if p.strip()]
        missing_paths = [
            p
            for p in scope_paths
            if p not in btext and os.path.basename(p) not in btext
        ]
        if missing_paths:
            shown = missing_paths[:8]
            more = (
                f" … +{len(missing_paths) - 8} more"
                if len(missing_paths) > 8
                else ""
            )
            lint(
                "O-BRIEFCOVER",
                f"{sid}: brief omits {len(missing_paths)} in-scope path(s): "
                f"{', '.join(shown)}{more} — name every roadmap scope path "
                f"in the brief (O-BRIEFCOVER; pair O-SCOPECOVER)",
            )
        # O-SEATBUDGETUNIQ — conflicting seat-budget: N values in one brief
        seat_vals = sorted(
            {int(v) for v in re.findall(r"(?im)seat-budget:\s*(\d+)", btext)}
        )
        if len(seat_vals) > 1:
            lint(
                "O-SEATBUDGETUNIQ",
                f"{sid}: brief publishes conflicting seat-budget values "
                f"{seat_vals} — keep exactly one N matching the roadmap "
                f"(O-SEATBUDGETUNIQ)",
            )
        # O-BRIEFFRESH — content hash vs current roadmap (not mtime)
        findings_raw = (field(sid, "findings") or "").strip()
        kind_raw_early = field(sid, "kind")
        seat_raw_early = field(sid, "seat-budget")
        expect_h = story_fresh_hash(
            sid, scope, findings_raw, kind_raw_early, seat_raw_early
        )
        m_fresh = _FRESH_MARK.search(btext)
        fresh_ok = bool(m_fresh and m_fresh.group(1).lower() == expect_h)
        if not m_fresh:
            lint(
                "O-BRIEFFRESH",
                f"{sid}: brief missing <!-- O-BRIEFFRESH sha256={expect_h} --> "
                f"— stamp via m2-compose fill/regen after roadmap changes "
                f"(O-BRIEFFRESH; mtime is not trusted)",
            )
        elif not fresh_ok:
            lint(
                "O-BRIEFFRESH",
                f"{sid}: brief freshness hash {m_fresh.group(1).lower()} != "
                f"current roadmap {expect_h} — scope/findings/kind/budget "
                f"changed without regenerating the brief (O-BRIEFFRESH)",
            )
        # O-PORTDERIVE / ARCH A1 — REDESIGN signal must survive M1→brief
        story_fids = {
            f for f in re.split(r"[,\s]+", findings_raw) if f and f != "-"
        }
        owns_open = bool(story_fids & open_design)
        scope_hit = sorted(
            c for c in redesign_cls
            if re.search(rf"\b{re.escape(c)}(?:\.java)?\b", scope)
        )
        # O-BRIEFQUALITY — gradient score (enforced on --story / ENFORCE=1)
        q_score, q_dims = brief_quality_score(
            btext, scope_paths, scope_hit, fresh_ok=fresh_ok
        )
        quality_reports.append((sid, q_score, q_dims))
        try:
            q_floor = int(os.environ.get("BRIEF_QUALITY_FLOOR", "80"))
        except ValueError:
            q_floor = 80
        q_enforce = bool(STORY_FILTER) or os.environ.get(
            "BRIEF_QUALITY_ENFORCE", ""
        ) in ("1", "true", "yes")
        if q_enforce and q_score < q_floor:
            dim_s = " ".join(f"{k}={v}" for k, v in q_dims.items())
            lint(
                "O-BRIEFQUALITY",
                f"{sid}: brief quality {q_score} < floor {q_floor} "
                f"({dim_s}) — raise coverage/contracts/specificity/oracle/"
                f"freshness before M3 (O-BRIEFQUALITY)",
            )
        if owns_open or scope_hit:
            if not brief_has_redesign_contract(btext):
                why = []
                if owns_open:
                    why.append(
                        "owns OPEN DESIGN finding(s) "
                        + ",".join(sorted(story_fids & open_design))
                    )
                if scope_hit:
                    why.append(
                        "scope names §7 REDESIGN class(es) "
                        + ",".join(scope_hit)
                    )
                lint(
                    "O-PORTDERIVE",
                    f"{sid}: brief missing REDESIGN target contract "
                    f"({'; '.join(why)}) — name each REDESIGN class with a "
                    f"target shape from architecture-profile §7 "
                    f"(O-PORTDERIVE / ARCH A1)",
                )
        # O-BRIEFCONTRACT — per-class density (not one layer line for N repos)
        if scope_hit:
            miss_cls = brief_classes_missing_contracts(btext, scope_hit)
            if miss_cls:
                shown = miss_cls[:8]
                more = (
                    f" … +{len(miss_cls) - 8} more"
                    if len(miss_cls) > 8
                    else ""
                )
                lint(
                    "O-BRIEFCONTRACT",
                    f"{sid}: brief missing per-class §7 contract for "
                    f"{len(miss_cls)} REDESIGN class(es): "
                    f"{', '.join(shown)}{more} — one class+target-shape line "
                    f"each (O-BRIEFCONTRACT; pair O-PORTDERIVE)",
                )
        # O-STORYKIND / ARCH A3 — transform kind is the story-level Port
        kind_raw = field(sid, "kind")
        if owns_open or scope_hit:
            if not kind_raw:
                lint(
                    "O-STORYKIND",
                    f"{sid}: missing field 'kind' (rename|reimplement|mixed) — "
                    f"required when story owns OPEN DESIGN or scopes §7 "
                    f"REDESIGN (O-STORYKIND / ARCH A3)",
                )
            else:
                km = re.match(
                    r"(?i)^(rename|reimplement|mixed)\b",
                    kind_raw.strip(),
                )
                if not km:
                    lint(
                        "O-STORYKIND",
                        f"{sid}: kind must be rename|reimplement|mixed "
                        f"(got '{kind_raw[:60]}') (O-STORYKIND / ARCH A3)",
                    )
                else:
                    kval = km.group(1).lower()
                    if owns_open and kval == "rename":
                        lint(
                            "O-STORYKIND",
                            f"{sid}: owns OPEN DESIGN finding(s) — kind cannot "
                            f"be 'rename' alone; use reimplement or mixed "
                            f"(O-STORYKIND / ARCH A3)",
                        )
                    if kval == "mixed":
                        just_blob = " ".join(
                            [
                                kind_raw,
                                field(sid, "rationale") or "",
                                field(sid, "done") or "",
                            ]
                        )
                        if not re.search(
                            r"(?i)\b(split|justif|both\s+kinds?|"
                            r"rename\s*\+?\s*reimplement|"
                            r"reimplement\s+and\s+rename|"
                            r"mixed\s+because|harvest\s*\+?\s*convert|"
                            r"cannot\s+split)\b",
                            just_blob,
                        ):
                            lint(
                                "O-STORYKIND",
                                f"{sid}: kind: mixed requires justification / "
                                f"split suggestion (O-STORYKIND / ARCH A3)",
                            )
        # O-SEATBUDGET / ARCH A5 + O-SEATSIZE — kind × max(incidents, scope) → budget
        kind_for_budget = seat_budget.parse_kind(kind_raw) if kind_raw else None
        if kind_for_budget:
            inc = seat_budget.story_incident_total(inv, story_fids)
            scope_n = seat_budget.scope_path_count(scope)
            try:
                expected = seat_budget.expected_budget(
                    kind_for_budget, inc, scope_paths=scope_n
                )
            except ValueError as e:
                lint("O-SEATBUDGET", f"{sid}: {e}")
                expected = None
            declared = seat_budget.parse_seat_budget_field(field(sid, "seat-budget"))
            if declared is None:
                lint(
                    "O-SEATBUDGET",
                    f"{sid}: missing field 'seat-budget' — derive from "
                    f"kind×incidents×scope ({kind_for_budget}×{inc}/"
                    f"scope={scope_n} → {expected}) "
                    f"(O-SEATBUDGET / O-SEATSIZE)",
                )
            elif expected is not None and declared != expected:
                lint(
                    "O-SEATBUDGET",
                    f"{sid}: seat-budget: {declared} != expected {expected} "
                    f"(kind={kind_for_budget} × incidents={inc} "
                    f"scope_paths={scope_n} / "
                    f"unit={seat_budget.unit_size()}) "
                    f"(O-SEATBUDGET / ARCH A5)",
                )
            elif expected is not None and not seat_budget.brief_has_seat_budget(
                btext, expected
            ):
                lint(
                    "O-SEATBUDGET",
                    f"{sid}: brief must publish seat-budget: {expected} "
                    f"(O-SEATBUDGET / ARCH A5)",
                )

    # K3 — every non-mandatory inventory rule needs adopt / defer (reason)
    # in the roadmap or a brief (not silently dropped).
    if inv:
        nm = set()
        for m in re.finditer(r"^-\s*non-mandatory:\s*\d+\s*—\s*(.+)$", inv, re.M):
            nm |= {i.strip() for i in m.group(1).split(",") if i.strip()}
        for m in re.finditer(
            r"^\|\s*`?([a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+)`?\s*\|\s*"
            r"(optional|potential|information)\b",
            inv,
            re.M | re.I,
        ):
            nm.add(m.group(1))
        if nm:
            corpus = text + "\n" + "\n".join(brief_texts)
            # Bullet: - `rule-id`: adopt | defer (reason)
            # Table:  | rule-id | adopt|defer | reason |  (mirrors inventory K3 table)
            dec_re = re.compile(
                r"^-\s*`?([a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+)`?\s*:\s*"
                r"(adopt|defer)\b(?:\s*\(([^)]*)\))?",
                re.M | re.I,
            )
            dec_table_re = re.compile(
                r"^\|\s*`?([a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+)`?\s*\|\s*"
                r"(adopt|defer)\s*\|\s*([^|\n]*?)\s*\|?\s*$",
                re.M | re.I,
            )
            decisions = {}
            for m in dec_re.finditer(corpus):
                decisions[m.group(1)] = (
                    m.group(2).lower(),
                    (m.group(3) or "").strip(),
                )
            for m in dec_table_re.finditer(corpus):
                rid = m.group(1)
                if rid in decisions:
                    continue
                decisions[rid] = (
                    m.group(2).lower(),
                    (m.group(3) or "").strip(),
                )
            for rid in sorted(nm):
                if rid not in decisions:
                    lint(
                        "non-mandatory",
                        f"{rid}: no adopt/defer decision in roadmap or briefs (K3) — "
                        f"add under '## Non-mandatory decisions'",
                    )
                elif decisions[rid][0] == "defer" and not decisions[rid][1]:
                    lint(
                        "non-mandatory",
                        f"{rid}: defer requires a reason in parentheses (K3) "
                        f"(or a non-empty reason column in the decision table)",
                    )

    # O-BRIEFQUALITY score lines (informational on full M2; gated on --story)
    for sid, q_score, q_dims in quality_reports:
        if STORY_FILTER and sid != STORY_FILTER:
            continue
        dim_s = " ".join(f"{k}={v}" for k, v in q_dims.items())
        print(f"BRIEF-QUALITY {sid}: {q_score} ({dim_s})")

    # O-M3PREFLIGHT — keep only SID-scoped findings when --story is set so a
    # deficient S03 refuses S03 seats while S01 can still proceed.
    emit = problems
    if STORY_FILTER:
        sid_re = re.compile(rf":\s*{re.escape(STORY_FILTER)}:")
        emit = [p for p in problems if sid_re.search(p)]
        if emit:
            print("\n".join(emit))
            return 1
        print(
            f"ROADMAP OK (story {STORY_FILTER}): brief-quality clear "
            f"for M3 preflight (O-M3PREFLIGHT)"
        )
        return 0

    print("\n".join(emit) if emit else
          f"ROADMAP OK: {len(ids)} stories, {len(owned)} findings owned, "
          f"deploy milestones: {[s for s, f in deploy_flags if f]}")
    return 1 if emit else 0


if __name__ == "__main__":
    sys.exit(main())
