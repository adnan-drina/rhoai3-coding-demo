#!/usr/bin/env python3
"""Deterministic M3 plan lint (improvement plan B2).

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
               (requires the findings JSON); when the rule has incidents,
               each incident file must be owned by exactly one task (K1)
  incident-unowned / incident-conflict — K1 ownership failures
"""
import json
import re
import sys

problems = []


def lint(cls, detail):
    problems.append(f"LINT:{cls}: {detail}")


def _norm_incident_uri(uri: str) -> str:
    u = (uri or "?").replace("file:///", "/").replace("file://", "")
    for marker in ("src/main/", "src/test/"):
        i = u.find(marker)
        if i >= 0:
            return u[i:]
    return u.lstrip("/") if u != "?" else "?"


def _map_pkg_path(rel: str, legacy_slash: str, target_slash: str) -> str:
    """Rewrite src/{main,test}/java/<legacy>/… → …/<target>/…"""
    for kind in ("main", "test"):
        pref = f"src/{kind}/java/{legacy_slash}/"
        if rel.startswith(pref):
            return f"src/{kind}/java/{target_slash}/{rel[len(pref):]}"
    return rel


_JAVA_PATH = re.compile(r"src/(?:main|test)/[A-Za-z0-9_./-]+\.java")
# Lines that declare ownership (not disclaimers).
_CLAIM_LINE = re.compile(
    r"(?i)(?:^\s*\*?\*?(?:Absorbs|Owns|Target\s*design|Target|Design)\*?\*?\s*:)"
    r"|(?:→|->)\s*`?src/"
)
_OOS_LINE = re.compile(
    r"(?i)(?:^\s*\*?\*?Out of scope\*?\*?\s*:)"
    r"|(?:\bdo NOT touch\b)"
    r"|(?:\bowned by T[-A-Za-z0-9]*\d+)"
)


def _parse_path_field(body: str, *labels: str) -> set[str]:
    """Collect paths/basenames from Absorbs:/Owns: field lines."""
    out: set[str] = set()
    for label in labels:
        for m in re.finditer(
            rf"^\*?\*?{re.escape(label)}\*?\*?\s*:?\s*(.+)$",
            body,
            re.M | re.I,
        ):
            for tok in re.split(r"[,;\s]+", m.group(1).strip()):
                tok = tok.strip().strip("`")
                if tok and not tok.startswith("("):
                    out.add(_norm_incident_uri(tok))
    return out


def _declared_claim_paths(body: str) -> set[str]:
    """Paths claimed via Target/Absorbs/Owns (excludes Out-of-scope lines)."""
    paths = _parse_path_field(body, "Absorbs", "Owns")
    for line in body.splitlines():
        if _OOS_LINE.search(line):
            continue
        if not _CLAIM_LINE.search(line):
            continue
        for p in _JAVA_PATH.findall(line):
            paths.add(_norm_incident_uri(p))
    return paths


def _ownership_fallback_corpus(body: str) -> str:
    """Last-resort body scan — drop Out-of-scope / disclaimer lines (K1-OWN)."""
    keep = []
    for line in body.splitlines():
        if _OOS_LINE.search(line):
            continue
        keep.append(line)
    return "\n".join(keep)


def _path_claimed(claim_paths: set[str], legacy_rel: str, target_rel: str) -> bool:
    base = legacy_rel.rsplit("/", 1)[-1]
    if legacy_rel in claim_paths or target_rel in claim_paths:
        return True
    if base.endswith(".java") and base in claim_paths:
        return True
    for p in claim_paths:
        if p.endswith("/" + base) or p == base:
            return True
    return False


def _task_owns_incident(body: str, legacy_rel: str, target_rel: str) -> bool:
    """K1 ownership: declared fields first; body scan only if none declared."""
    if not body:
        return False
    declared = _declared_claim_paths(body)
    if declared:
        return _path_claimed(declared, legacy_rel, target_rel)
    # Last resort when the task declares no Target/Absorbs/Owns paths at all.
    corpus = _ownership_fallback_corpus(body)
    if legacy_rel != "?" and legacy_rel in corpus:
        return True
    if target_rel != legacy_rel and target_rel in corpus:
        return True
    return False


def main():
    args = sys.argv[1:]
    scope = None
    if "--findings-scope" in args:
        i = args.index("--findings-scope")
        scope = {s.strip() for s in args[i + 1].split(",") if s.strip()}
        del args[i:i + 2]
    profile_path = None
    if "--profile" in args:
        i = args.index("--profile")
        profile_path = args[i + 1]
        del args[i:i + 2]
    tasks_path = args[0]
    text = open(tasks_path).read()

    # forbidden->preserve inversion (V5 T-011: the plan read the forbidden
    # tripwire `getMockProducts` as a preserve contract — a fabrication
    # seed). A forbidden: pattern named in a keep/preserve/maintain context
    # is inverted; forbidden items are REMOVED, never preserved.
    try:
        myaml = open("migration.yaml", encoding="utf-8").read()
        fsec = re.search(r"^forbidden:(.*?)(^\S|\Z)", myaml, re.M | re.S)
        forbidden = re.findall(r"^\s*-\s*\"?([^\"\n]+?)\"?\s*$", fsec.group(1), re.M) if fsec else []
    except OSError:
        myaml, forbidden = "", []
    # package identity from migration.yaml (single source; no hardcoded root)
    m = re.search(r"legacyPackage:\s*([\w.]+)", myaml or "")
    legacy_pkg = m.group(1) if m else "com.redhat.coolstore"
    m = re.search(r"targetPackage:\s*([\w.]+)", myaml or "")
    target_pkg = m.group(1) if m else "com.demo"
    legacy_path = legacy_pkg.replace(".", "/")
    for pat in forbidden:
        for m in re.finditer(re.escape(pat), text):
            ls = text.rfind("\n", 0, m.start() - 120)
            window = text[max(ls, 0): m.end() + 40]
            if re.search(r"preserv|maintain|\bkeep\b|retain|contract", window, re.I) and \
               not re.search(r"remove|delete|elimin|must not|never|forbidden", window, re.I):
                lint("forbidden-inverted", f"forbidden tripwire '{pat}' is treated as a preserve/maintain "
                                           f"contract — it is a fabrication guard, REMOVE it, never keep it")
                break

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

    # Characterization-scope (S01 T-008: a test task invented a src/main
    # class to have something to execute): test/characterization tasks
    # never TARGET src/main — value-pinning for out-of-scope logic uses
    # test-local expectation helpers.
    for _, tid, title in heads:
        if re.search(r"\b(test|characteri[sz])", title, re.I):
            m = re.search(r"(?:Target|→|->)[^\n]*src/main/", bodies.get(tid, ""))
            if m:
                lint("test-scope", f"{tid}: test task targets src/main ({m.group(0)[:60].strip()}) — tests pin values in TEST scope only")

    # Hedge-word lint (V3 S02: "convert to a Quarkus main class if
    # needed" contradicted the decided mapping and two sessions took the
    # escape hatch): designs state decisions, never options.
    HEDGE = re.compile(r"\b(if needed|if necessary|as appropriate|as needed|consider (?:using|adding)|optionally)\b", re.I)
    for _, tid, _ in heads:
        m = HEDGE.search(bodies.get(tid, ""))
        if m:
            lint("hedge", f"{tid}: design contains hedge phrase '{m.group(0)}' — state the decided shape, not options")

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
    leg_slash = re.escape(legacy_path)
    leg_dotslash = re.escape(legacy_pkg).replace(r"\.", "[./]")
    # V6 abort: plans that TARGET com.demo.coolstore when targetPackage is
    # com.demo (partial rename) feed OpenCode the wrong package.
    leg_last = legacy_pkg.rsplit(".", 1)[-1]
    wrong_pkg = f"{target_pkg}.{leg_last}"
    wrong_slash = wrong_pkg.replace(".", "/")
    for line in text.splitlines():
        if "migration/staging/" in line:
            continue
        if re.search(rf"(?:Target|→|->)\s*[^\n]*src/(?:main|test)/java/{leg_slash}", line) \
                or re.search(rf"^\*\*Target\*\*.*{leg_dotslash}", line):
            lint("package", f"legacy package in TARGET position: {line.strip()[:80]} — project root is {target_pkg} (migration.yaml targetPackage)")
        if re.search(rf"(?:Target|→|->)\s*[^\n]*src/(?:main|test)/java/{re.escape(wrong_slash)}", line) \
                or re.search(rf"\b{re.escape(wrong_pkg)}\b", line):
            # Allow prose that forbids the wrong prefix.
            if re.search(r"\b(never|not|forbid|wrong|incorrect|must not)\b", line, re.I):
                continue
            lint("package", f"wrong rewrite prefix in TARGET position: {line.strip()[:80]} — full rename is {legacy_pkg} → {target_pkg} (never {wrong_pkg})")
    # Task substance (T-029 class, M3 dry-run catch: 'waiver' and
    # 'coverage' tasks with no code path): every task body must name a
    # concrete artifact it changes.
    substance = re.compile(r"src/(?:main|test)/|pom\.xml|k8s/|application\.properties|migration\.yaml|migration/staging/")
    soft = re.compile(
        r"\b(prepare for|preparation for|verification[- ]only|verify only|final commit|"
        r"run validation|validate (?:the )?gate|note for later|remember (?:the )?path)\b",
        re.I,
    )
    for _, tid, title in heads:
        body = bodies.get(tid, "")
        if not substance.search(body):
            lint("substance", f"{tid}: task body names no code/config path it changes — ceremonial task (waivers belong in spec prose, not tasks)")
        # S-SOFT: soft prepare / verification-only tasks even when they cite a path
        if soft.search(title) or soft.search(body.split("\n", 3)[0] if body else ""):
            lint(
                "substance",
                f"{tid}: soft prepare/verification-only task (S-SOFT) — fold into a concrete file-changing task",
            )

    # N2: every preserve: item in migration.yaml must appear in the plan
    try:
        my = open("migration.yaml").read()
        import re as _re
        # Bound the slice to the preserve: section — stop at the next
        # top-level key (V5 run-4: the old `my[index('preserve:'):]` read to
        # EOF, sweeping in the forbidden: list below, so the tripwire
        # `getMockProducts` was mis-read as a preserve item and failed every
        # plan that didn't happen to name it — same over-read class as the
        # forbidden: fix above).
        _psec = _re.search(r"^preserve:(.*?)(^\S|\Z)", my, _re.M | _re.S)
        pres = _re.findall(r"^\s*-\s*([A-Za-z0-9_./:-]+)", _psec.group(1), _re.M) if _psec else []
        for item in pres:
            if item not in text:
                lint("preserve", f"preserved integration '{item}' mapped to no task")
        # Ship acceptance is part of the contract (cart run #2: the stamped
        # acceptance.path had no endpoint anywhere in the plan, discovered
        # only at ship time). The path must be mapped to a task.
        # V5/run-4: a comment (or blank lines) between `acceptance:` and
        # `path:` made the old immediate-next-line regex miss entirely, so
        # S05 plan-lint stayed green with the path untasked (V6 R7).
        m = _re.search(
            r"^acceptance:\s*\n(?:[ \t]*#.*\n|[ \t]*\n)*[ \t]*path:\s*(\S+)",
            my,
            _re.M,
        )
        if m and m.group(1) not in text:
            lint("acceptance", f"acceptance path '{m.group(1)}' (migration.yaml) mapped to no task — the app must serve it")
        elif m:
            # V6 R7 substance: covering tasks must name a Java resource surface
            # (@Path / Endpoint / src/main/...java) — not a ceremonial string cite.
            path = m.group(1)
            covering = [b for b in bodies.values() if path in b]
            if covering:
                joined = "\n".join(covering)
                if not re.search(
                    r"@Path|src/main/java/\S+\.java|\bEndpoint\b|\bResource\b|acceptanceCheck",
                    joined,
                ):
                    lint(
                        "acceptance",
                        f"acceptance path '{path}' tasked without Java @Path/resource substance "
                        f"— ceremonial mapping (V6 R7)",
                    )
    except FileNotFoundError:
        pass

    # findings coverage — a mandatory rule is covered by a task OR by a
    # recipe execution recorded in migration/recipe-log.md (R3: recipe-
    # executed rewrites need no plan task).
    # K1: when a mandatory rule has incidents, every incident *file* must
    # be claimed by exactly one task (target path, legacy path, or Absorbs:).
    if len(args) > 1:
        d = json.load(open(args[1]))
        mandatory = {}
        for rs in d:
            for rid, v in (rs.get("violations") or {}).items():
                if (v.get("category") or "mandatory") == "mandatory":
                    mandatory[rid] = v
        if scope is not None:
            mandatory = {r: v for r, v in mandatory.items() if r in scope}
        try:
            recipe_log = open("migration/recipe-log.md").read()
        except OSError:
            recipe_log = ""
        target_slash = target_pkg.replace(".", "/")
        # Per-file owners across all in-scope mandatory rules (conflict is
        # file-level — two tasks must not claim the same incident file).
        file_owners: dict[str, set[str]] = {}
        for rid, v in mandatory.items():
            if rid in recipe_log:
                continue
            incidents = v.get("incidents") or []
            # Zero-incident rules: keep rule-id string-mention (pre-K1).
            if not incidents:
                if rid not in text:
                    lint(
                        "findings",
                        f"mandatory finding {rid} mapped to no task (and not recipe-executed)",
                    )
                continue
            # Rules with incidents: id mention alone is not enough — own files.
            for inc in incidents:
                if not isinstance(inc, dict):
                    continue
                legacy_rel = _norm_incident_uri(str(inc.get("uri") or "?"))
                if legacy_rel == "?":
                    continue
                target_rel = _map_pkg_path(legacy_rel, legacy_path, target_slash)
                owners = [
                    tid
                    for tid, body in bodies.items()
                    if _task_owns_incident(body, legacy_rel, target_rel)
                ]
                key = legacy_rel
                file_owners.setdefault(key, set()).update(owners)
                if not owners:
                    lint(
                        "incident-unowned",
                        f"{rid} {legacy_rel} owned by no task "
                        f"(claim via Target/→ {target_rel}, Absorbs:, or Owns:)",
                    )
        for fpath, owners in sorted(file_owners.items()):
            if len(owners) > 1:
                claimed = " and ".join(sorted(owners))
                lint(
                    "incident-conflict",
                    f"{fpath} claimed by {claimed}",
                )

    # §7-traceability (PROCESS-FIX): each REDESIGN class named in the
    # profile's §7 must have a task that names it AND a target-shape token,
    # so the production-grade defaults for #2/#5 do not stay soft guidance.
    if profile_path:
        try:
            prof = open(profile_path, encoding="utf-8").read()
        except OSError:
            prof = ""
        # §7 body down to the next SAME-OR-HIGHER heading, so ###/####
        # HARVEST/REDESIGN subheadings inside §7 are not treated as its end.
        sec7 = ""
        m = re.search(r"^(#{2,6})[ \t]+.*Class roles.*$", prof, re.M | re.I)
        if m:
            level = len(m.group(1))
            rest = prof[m.end():]
            nxt = re.search(r"^#{1," + str(level) + r"}[ \t]", rest, re.M)
            sec7 = rest[:nxt.start()] if nxt else rest
        # collect REDESIGN class names — inline (`Cls` — REDESIGN) AND
        # subheading (### REDESIGN / - `Cls`) forms. A backtick-quoted
        # CapWord counts as REDESIGN if the nearest preceding role marker
        # (same line or a subheading above) is REDESIGN.
        def _governs_redesign(off):
            ls = sec7.rfind("\n", 0, off) + 1
            le = sec7.find("\n", off)
            line = sec7[ls: le if le >= 0 else len(sec7)]
            if "REDESIGN" in line:
                return True
            if "HARVEST" in line:
                return False
            pre = sec7[:off]
            return pre.rfind("REDESIGN") > pre.rfind("HARVEST")
        # A name is a real REDESIGN CLASS only if it is governed by REDESIGN
        # AND §7 gives it a `.java` file reference — this filters SHAPE
        # LABELS (Concurrency, ExceptionMapper, Validation) that appear in a
        # class's target description but are not classes (V5 false positive).
        # Names appear as `Cls`, **Cls**, or Cls.java (models vary emphasis).
        NAME = re.compile(r"`([A-Z]\w+)`|\*\*([A-Z]\w+)\*\*|\b([A-Z]\w+)\.java\b")
        java_named = set(re.findall(r"\b([A-Z]\w+)\.java\b", sec7))

        def targeted(cls):  # a task creates/targets this class's src/main file
            return any(re.search(rf"src/(?:main|test)/java/\S*\b{re.escape(cls)}\.java", b)
                       for b in bodies.values())
        # A name is a real CLASS if §7 gives it a .java ref OR a task targets
        # it — shape LABELS (Concurrency, ExceptionMapper) are neither, so
        # they drop out (V5 false positive).
        redesign, firsts = set(), {}
        for mm in NAME.finditer(sec7):
            nm = mm.group(1) or mm.group(2) or mm.group(3)
            if _governs_redesign(mm.start()) and (nm in java_named or targeted(nm)):
                redesign.add(nm)
                firsts.setdefault(nm, mm.start())
        # Decisive tokens only — soft prose like "idempotent" alone is not
        # enough when §7 also decided 404 (profile-rubric). Cart add() oracle:
        # additive / qty 4 must be cited when §7 decides that shape (V6 P3.1).
        TARGET = re.compile(
            r"ConcurrentHashMap|compute\(|thread-safe|refresh|cache|"
            r"404|idempoten|valid|@Min|ExceptionMapper|400|503|dedupe|"
            r"normalize|additive|qty\s*4|quantity\s*4|\badd\(", re.I)
        # per-class §7 entry: from the class's FIRST mention to the first
        # mention of a DIFFERENT redesign class (or end of §7) — require only
        # the shapes §7 DECIDED for THIS class.
        def entry_of(cls):
            start = firsts.get(cls)
            if start is None:
                return ""
            later = [o for c, o in firsts.items() if c != cls and o > start]
            return sec7[start: min(later) if later else len(sec7)]
        # A class is THIS plan's responsibility only if a task TARGETS its
        # src/main file — a LATER story owns the rest (V5: the platform story
        # S01 was wrongly required to cite every §7 class, forcing a
        # ceremonial "future shapes" doc). Not-targeted classes are skipped;
        # cross-story coverage (every class converted somewhere) is
        # roadmap-lint's domain, not per-story plan-lint's.
        for cls in sorted(redesign):
            if not targeted(cls):
                continue
            want = {s.lower() for s in TARGET.findall(entry_of(cls))}
            body = "\n".join(b for t, b in bodies.items() if cls in b)
            if want and not (want & {s.lower() for s in TARGET.findall(body)}):
                lint("target-trace", f"REDESIGN class {cls}: §7 decides a target shape "
                                     f"({', '.join(sorted(want))}) that no task cites")

    # S-CHAR (V8 S02 HOLD): harvesting model classes without any src/test
    # task drops characterization / coverage — deferring *service* tests is
    # fine; emptying test obligations is not.
    if re.search(r"src/main/java/\S*/model/\S+\.java", text) and not re.search(
        r"src/test/", text
    ):
        lint(
            "S-CHAR",
            "plan targets src/main/.../model/*.java but names no src/test/ path — "
            "add model-level characterization tests (deferring service tests ≠ empty tests; V8 S02)",
        )

    # S-AC1 (V9 S01 HOLD): platform stories must not schedule ceremonial
    # acceptance placeholders (status-map / "simple status") — that belongs
    # on the deploying story with a real catalog/products proof (G-OK/G-FAKE).
    if re.search(
        r"(?i)acceptance endpoint placeholder|simple status response|"
        r"returns simple status|status response for web surface",
        text,
    ):
        lint(
            "S-AC1",
            "plan schedules a ceremonial acceptance placeholder/status response — "
            "defer real acceptance to the deploy story (V9 S01 HOLD / G-OK)",
        )

    # S-PKGDIR (O-PKGDIR V9 S03): package-structure / mkdir tasks must require
    # a trackable file (.gitkeep or package-info.java). Empty dirs leave no
    # git commit → worker rc=0 + mechan skip → MiniMax escalation.
    for _, tid, title in heads:
        blob = f"{title}\n{bodies.get(tid, '')}"
        if re.search(
            r"(?i)package structure|create (the )?service package|"
            r"mkdir.*package|empty package|package director",
            blob,
        ) and not re.search(r"(?i)\.gitkeep|package-info\.java", blob):
            lint(
                "S-PKGDIR",
                f"{tid}: package-structure task must require .gitkeep or "
                f"package-info.java so git can commit (O-PKGDIR)",
            )

    print("\n".join(problems) if problems else
          f"PLAN OK: {len(heads)} tasks, classes {dict((c, list(classes.values()).count(c)) for c in set(classes.values()))}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
