#!/usr/bin/env python3
"""Deterministic M3 plan lint (improvement plan B2).

Usage: plan-lint.py <tasks.md> [mta-findings.json]
         [--findings-scope id1,id2] [--story-deploy true|false]
         [--story-scope path1,path2]

--findings-scope (M3 story scoping, redesign §3): restrict the
mandatory-findings coverage check to the listed rule ids — the story's
assigned findings from the roadmap. All other checks stay global.

--story-deploy (O-M3ACCEPT): when true, acceptance.path must be tasked with
Java @Path substance. When false (non-deploy stories), path must NOT be
tasked with endpoint substance (defer to deploy story; S-AC1/G-OK). When
omitted, defaults to true for back-compat with older instrument fixtures.

--story-scope (O-M3DTOSCOPE / O-M3TASKSCOPE): comma/space-separated roadmap
scope path globs. When set: (1) incident-unowned is only enforced for
incidents whose legacy path matches a scope entry — platform stories must
not own **/dto/** just because a findings-scope rule also hits later-story
files; (2) O-M3TASKSCOPE REDs non-test Target/→ destinations outside that
scope (repository stories must not schedule service/controller/endpoint
Targets).

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
  O-PLANEXISTS — task work target already gone / already Quarkus (N10/R-217b)
  O-SPECREIMPL — (ARCH A2) when sibling spec.md names REDESIGN/OPEN DESIGN
               classes, each must appear in some task with Port: reimplement
"""
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

# O-ORACLEDERIVE / O-INFERABSENT — shared derive + block predicate
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from oracle_derive import (  # type: ignore
        derive_oracle,
        inferabsent_blocks,
        task_shape as _oracle_task_shape,
    )
except ImportError:  # pragma: no cover
    import importlib.util

    _odp = Path(__file__).resolve().parent / "oracle_derive.py"
    _spec = importlib.util.spec_from_file_location("oracle_derive", _odp)
    _od = importlib.util.module_from_spec(_spec)  # type: ignore
    assert _spec and _spec.loader
    _spec.loader.exec_module(_od)
    derive_oracle = _od.derive_oracle
    inferabsent_blocks = _od.inferabsent_blocks
    _oracle_task_shape = _od.task_shape

problems = []


def _incident_in_story_scope(legacy_rel: str, scopes: list[str]) -> bool:
    """True if incident path is inside roadmap story scope (or scope unset).

    O-M3DTOSCOPE: findings-scope rule ids can list incidents across packages;
    ownership is only required for files the story's scope actually covers.
    """
    if not scopes:
        return True
    rel = legacy_rel.lstrip("./")
    base = rel.rsplit("/", 1)[-1]
    for raw in scopes:
        g = raw.strip().lstrip("./")
        if not g:
            continue
        if rel == g or rel.endswith("/" + g):
            return True
        if fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(rel, "*/" + g):
            return True
        # basename match for shared roots (pom.xml) and exact file scopes
        if g == base or g.endswith("/" + base):
            return True
        # directory prefix (scope entry without wildcard)
        if not any(ch in g for ch in "*?[") and (
            rel.startswith(g.rstrip("/") + "/") or rel.startswith(g + "/")
        ):
            return True
    return False


def _pkg_path_variants(rel: str, legacy_pkg: str, target_pkg: str) -> list[str]:
    """legacy↔target package remaps for a src/{main,test}/java path."""
    rel = (rel or "").lstrip("./")
    out = [rel]
    if not legacy_pkg or not target_pkg or legacy_pkg == target_pkg:
        return out
    leg = legacy_pkg.replace(".", "/")
    tgt = target_pkg.replace(".", "/")
    for kind in ("main", "test"):
        lp = f"src/{kind}/java/{leg}/"
        tp = f"src/{kind}/java/{tgt}/"
        if rel.startswith(tp):
            out.append(lp + rel[len(tp) :])
        if rel.startswith(lp):
            out.append(tp + rel[len(lp) :])
    # de-dupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _expand_scope_pkg_variants(
    scopes: list[str], legacy_pkg: str, target_pkg: str
) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for s in scopes:
        for v in _pkg_path_variants(s.strip(), legacy_pkg, target_pkg):
            if v and v not in seen:
                seen.add(v)
                expanded.append(v)
    return expanded


def _norm_work_path(raw: str) -> str:
    """Normalize a Target work path (strip ticks / trailing globs)."""
    p = (raw or "").strip().strip("`").lstrip("./")
    p = re.sub(r"/\*\*?$", "", p)
    p = re.sub(r"/\*$", "", p)
    return p


# Work destinations under Target/→ (broader than .java-only ownership claims).
_WORK_PATH = re.compile(
    r"(?:src/main/[A-Za-z0-9_./${}*-]+|pom\.xml|k8s/[A-Za-z0-9_./-]+)"
)


def _target_work_paths(body: str) -> list[str]:
    """Collect non-test Target/→ destinations for O-M3TASKSCOPE.

    Scans Target / Target design blocks and arrow lines. Skips Out-of-scope
    and Absorbs/Owns-only deferral lines (those are not work Targets).
    """
    paths: list[str] = []
    seen: set[str] = set()
    in_target = False
    for line in body.splitlines():
        if _OOS_LINE.search(line):
            in_target = False
            continue
        hm = re.match(r"^\s*\*?\*?([A-Za-z][A-Za-z0-9 ]*?)\*?\*?\s*:", line)
        if hm:
            field = hm.group(1).strip().lower()
            if field.startswith("target") or field == "design":
                in_target = True
            elif field in (
                "absorbs",
                "owns",
                "class",
                "shape",
                "goal",
                "findings",
                "acceptance",
                "oracle",
                "out of scope",
            ):
                in_target = False
                if field in ("absorbs", "owns"):
                    continue
        if not in_target and "→" not in line and "->" not in line:
            continue
        if not in_target and not re.search(r"(?i)target", line):
            # Bare arrow outside Target blocks: only count when the line
            # itself is a Target claim (`Target: … → src/…`).
            if not re.search(r"(?i)\btarget\b", line):
                continue
        # Prefer RHS destinations of arrows; fall back to any work path
        # (covers `legacy.java → Update imports…` prose RHS).
        rhs = [
            _norm_work_path(m.group(1))
            for m in re.finditer(
                r"(?:→|->)\s*`?(" + _WORK_PATH.pattern + r")", line
            )
        ]
        rhs = [p for p in rhs if p]
        cands = rhs if rhs else [_norm_work_path(m.group(0)) for m in _WORK_PATH.finditer(line)]
        for p in cands:
            if not p or p in seen:
                continue
            if p.startswith("src/test/"):
                continue
            seen.add(p)
            paths.append(p)
    return paths


def _work_path_in_story_scope(
    rel: str, scopes: list[str], legacy_pkg: str, target_pkg: str
) -> bool:
    """True if a Target work path is inside roadmap story scope.

    O-M3TASKSCOPE: match exact/fnmatch scope entries (with legacy↔target
    remap) or the immediate parent directory of a scoped file (so a
    repository-layer story may Target sibling repository files / package
    wildcards, but not service/controller/rest layers).
    """
    if not scopes:
        return True
    expanded = _expand_scope_pkg_variants(scopes, legacy_pkg, target_pkg)
    variants = _pkg_path_variants(rel, legacy_pkg, target_pkg)
    for v in variants:
        if _incident_in_story_scope(v, expanded):
            return True
    # Immediate parents of scoped files (remapped).
    allowed_dirs: set[str] = set()
    for s in expanded:
        sn = s.lstrip("./")
        if "/" in sn:
            allowed_dirs.add(sn.rsplit("/", 1)[0] + "/")
    for v in variants:
        vn = v.lstrip("./")
        base = vn.rsplit("/", 1)[-1] if "/" in vn else vn
        # Package-dir / wildcard Targets (…/repository or …/repository/**).
        if base not in (".gitkeep", "package-info.java") and "." not in base:
            vd = vn.rstrip("/") + "/"
            for s in expanded:
                if s.lstrip("./").startswith(vd):
                    return True
        parent = vn.rsplit("/", 1)[0] + "/" if "/" in vn else ""
        if parent and parent in allowed_dirs:
            return True
    return False


def _committed_task_ids() -> set:
    """Task ids that already have a T-NNN: tip in git history.

    O-PLANEXISTSSKIP (R-227 / hotswap re-enter): mid-story plan re-lint must
    not RED delivered tasks — the tree is already Quarkus, so every completed
    Spring→Quarkus convert looks "dead" and would force a destructive M3
    revision (Wave2 S03 after O-HOTSWAPRELOAD).
    """
    try:
        out = subprocess.check_output(
            ["git", "log", "--format=%s"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return set()
    ids = set()
    for line in out.splitlines():
        m = re.match(r"^(T-\d+):", line)
        if m:
            ids.add(m.group(1))
    return ids


def lint(cls, detail):
    problems.append(f"LINT:{cls}: {detail}")


def _norm_incident_uri(uri: str) -> str:
    u = (uri or "?").replace("file:///", "/").replace("file://", "")
    for marker in ("src/main/", "src/test/"):
        i = u.find(marker)
        if i >= 0:
            return u[i:]
    rel = u.lstrip("/") if u != "?" else "?"
    if rel == "?":
        return "?"
    # Strip workspace prefixes so pom.xml / root files match roadmap scope
    # (O-M3DTOSCOPE): incidents often arrive as projects/legacy/pom.xml.
    for pref in (
        "projects/legacy/",
        "projects/modernized/",
        "legacy/",
        "modernized/",
    ):
        if rel.startswith(pref):
            rel = rel[len(pref) :]
            break
    if rel.endswith("/pom.xml") or rel == "pom.xml":
        return "pom.xml"
    return rel


def _map_pkg_path(rel: str, legacy_slash: str, target_slash: str) -> str:
    """Rewrite src/{main,test}/java/<legacy>/… → …/<target>/…"""
    for kind in ("main", "test"):
        pref = f"src/{kind}/java/{legacy_slash}/"
        if rel.startswith(pref):
            return f"src/{kind}/java/{target_slash}/{rel[len(pref):]}"
    return rel


_JAVA_PATH = re.compile(r"src/(?:main|test)/[A-Za-z0-9_./-]+\.java")
# K1-SHARED: pom / properties / k8s may also be Target/Owns claims.
_SHARED_PATH = re.compile(
    r"(?<![\w./])(?:pom\.xml|"
    r"src/(?:main|test)/resources/[A-Za-z0-9_./-]+\.(?:properties|ya?ml|xml)|"
    r"k8s/[A-Za-z0-9_./-]+)"
)
# Lines that declare ownership (not disclaimers).
_CLAIM_LINE = re.compile(
    r"(?i)(?:^\s*\*?\*?(?:Absorbs|Owns|Target\s*design|Target|Design)\*?\*?\s*:)"
    r"|(?:→|->)\s*`?(?:src/|pom\.xml|k8s/)"
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
        for p in _SHARED_PATH.findall(line):
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
    # O-M3ACCEPT: default True preserves pre-flag instrument behaviour.
    story_deploy = True
    if "--story-deploy" in args:
        i = args.index("--story-deploy")
        raw = (args[i + 1] if i + 1 < len(args) else "true").strip().lower()
        story_deploy = raw in ("1", "true", "yes", "on")
        del args[i:i + 2]
    # O-M3DTOSCOPE: roadmap story scope (comma-separated path globs). When set,
    # incident-unowned is only enforced for incidents inside that scope — S01
    # platform must not own **/dto/** just because removed-javaee is in findings.
    story_scope_raw = ""
    if "--story-scope" in args:
        i = args.index("--story-scope")
        story_scope_raw = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
    # parse-roadmap emits space-separated scope; outer may also pass commas.
    # Splitting only on "," treated the whole string as one blob → no path
    # matched → every incident skipped (false PLAN OK on S01 fcc506c).
    story_scope = [s for s in re.split(r"[\s,]+", story_scope_raw) if s]
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
    # S-SOFT-NARROW: title-leading Verify/Ensure/Confirm/Validate is soft even
    # when the body cites a path (Poll 29 T-009/T-010; pairs with O-ACVERIFY).
    soft_title = re.compile(r"^\s*(verify|ensure|confirm|validate)\b", re.I)
    for _, tid, title in heads:
        body = bodies.get(tid, "")
        if not substance.search(body):
            lint("substance", f"{tid}: task body names no code/config path it changes — ceremonial task (waivers belong in spec prose, not tasks)")
        # S-SOFT: soft prepare / verification-only tasks even when they cite a path
        if (
            soft.search(title)
            or soft_title.search(title)
            or soft.search(body.split("\n", 3)[0] if body else "")
        ):
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
        # only at ship time). O-M3ACCEPT: only deploy stories must task it
        # with Java substance; non-deploy stories must defer (S-AC1/G-OK).
        # V5/run-4: a comment (or blank lines) between `acceptance:` and
        # `path:` made the old immediate-next-line regex miss entirely, so
        # S05 plan-lint stayed green with the path untasked (V6 R7).
        m = _re.search(
            r"^acceptance:\s*\n(?:[ \t]*#.*\n|[ \t]*\n)*[ \t]*path:\s*(\S+)",
            my,
            _re.M,
        )
        if m:
            path = m.group(1)
            covering = [b for b in bodies.values() if path in b]
            endpoint_re = (
                r"@Path|src/main/java/\S+\.java|\bEndpoint\b|\bResource\b|acceptanceCheck"
            )
            has_endpoint = bool(
                covering
                and re.search(endpoint_re, "\n".join(covering))
            )
            if story_deploy:
                if path not in text:
                    lint(
                        "acceptance",
                        f"acceptance path '{path}' (migration.yaml) mapped to no task "
                        f"— the app must serve it",
                    )
                elif covering and not has_endpoint:
                    # V6 R7 substance: covering tasks must name a Java resource
                    # surface — not a ceremonial string cite.
                    lint(
                        "acceptance",
                        f"acceptance path '{path}' tasked without Java @Path/resource substance "
                        f"— ceremonial mapping (V6 R7)",
                    )
            else:
                # Non-deploy: inverse — endpoint substance is forbidden here.
                if has_endpoint:
                    lint(
                        "acceptance",
                        f"acceptance path '{path}' tasked with endpoint substance on a "
                        f"non-deploy story — defer to the deploy story (O-M3ACCEPT / S-AC1)",
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
        # O-DESTBASE / K6: scaffold-presatisfied (+ M1-generated) rules are
        # already true on the Quarkus destination — omit from M3 ownership.
        presat = set()
        for _base in (
            Path("migration/scaffold-presatisfied.generated.txt"),
            Path(".hermes/harness/scaffold-presatisfied.txt"),
            Path(__file__).resolve().parent / "scaffold-presatisfied.txt",
        ):
            try:
                for _ln in _base.read_text(encoding="utf-8").splitlines():
                    _ln = _ln.strip()
                    if _ln and not _ln.startswith("#"):
                        presat.add(_ln)
            except OSError:
                continue
        target_slash = target_pkg.replace(".", "/")
        # Per-file owners across all in-scope mandatory rules (conflict is
        # file-level — two tasks must not claim the same incident file).
        file_owners: dict[str, set[str]] = {}
        for rid, v in mandatory.items():
            if rid in recipe_log or rid in presat:
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
                # O-M3GENSRC: MapStruct/OpenAPI generated under target/generated-sources
                # is build noise — never require M3 task ownership (S01 platform RED).
                if "/target/generated-sources/" in f"/{legacy_rel}" or legacy_rel.startswith(
                    "target/generated-sources/"
                ):
                    continue
                # O-M3DTOSCOPE: skip incidents outside this story's roadmap scope
                # (e.g. removed-javaee dto/** on a pom/properties-only S01).
                if not _incident_in_story_scope(legacy_rel, story_scope):
                    continue
                target_rel = _map_pkg_path(legacy_rel, legacy_path, target_slash)
                owners = [
                    tid
                    for tid, body in bodies.items()
                    if _task_owns_incident(body, legacy_rel, target_rel)
                ]
                if not owners:
                    lint(
                        "incident-unowned",
                        f"{rid} {legacy_rel} owned by no task "
                        f"(claim via Target/→ {target_rel}, Absorbs:, or Owns:)",
                    )
                # K1-SHARED (Poll 11): pom/properties/k8s are shared surfaces —
                # require ownership but do not incident-conflict across tasks.
                # Restrict conflict tracking to src/**/*.java only.
                def _src_java(p: str) -> bool:
                    return p.endswith(".java") and (
                        p.startswith("src/") or "/src/" in p
                    )

                if _src_java(legacy_rel) or _src_java(target_rel):
                    file_owners.setdefault(legacy_rel, set()).update(owners)
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

        # O-PORTDERIVE (ARCH A1): Port is derived from §7 REDESIGN — convert
        # tasks that target a REDESIGN class default to Port: reimplement.
        # O-PORTREIMPL stays the API-swap consistency / mapping-table check.
        _port_decl = re.compile(
            r"(?im)^\*\*Port\*\*\s*:?\s*(rename|reimplement)\b"
            r"|^\*\*Port\s*:\s*(rename|reimplement)\*\*"
            r"|^Port\s*:\s*(rename|reimplement)\b"
        )
        _rename_ok = re.compile(
            r"(?i)\b(same\s+API|transliteration|API\s+unchanged|"
            r"justify(?:ied)?\s+rename|Port:\s*rename\s*\()\b"
        )
        for _, tid, title in heads:
            body = bodies.get(tid, "")
            blob = f"{title}\n{body}"
            if not re.search(
                r"(?im)^\*\*Shape\*\*\s*:?\s*(create|modify)\b"
                r"|^\*\*Shape\s*:\s*(create|modify)\*\*",
                body,
            ):
                continue
            hit = sorted(
                c for c in redesign
                if re.search(
                    rf"src/(?:main|test)/java/\S*\b{re.escape(c)}\.java"
                    rf"|\b{re.escape(c)}\.java\b",
                    blob,
                )
            )
            if not hit:
                continue
            pm = _port_decl.search(body)
            if not pm:
                lint(
                    "O-PORTDERIVE",
                    f"{tid}: §7 REDESIGN class(es) {', '.join(hit)} require "
                    f"**Port**: reimplement (derived from architecture-profile "
                    f"§7 / O-PORTDERIVE) — declare Port or justify "
                    f"Port: rename (same API)",
                )
                continue
            port_val = next(g for g in pm.groups() if g).lower()
            if port_val == "rename" and not _rename_ok.search(blob):
                lint(
                    "O-PORTDERIVE",
                    f"{tid}: §7 REDESIGN class(es) {', '.join(hit)} default to "
                    f"Port: reimplement — Port: rename needs same-API / "
                    f"transliteration justification (O-PORTDERIVE)",
                )

    # O-SPECREIMPL (ARCH A2): sibling spec.md REDESIGN/OPEN DESIGN classes
    # must land as Port: reimplement tasks (middle-hop coverage). Soft when
    # spec.md is absent so older fixtures stay green.
    #
    # Extraction is intentionally narrow (false-green risk elsewhere is
    # worse than missing a soft prose mention):
    #   1) same-line role form: `Foo` / **Foo** / Foo.java near REDESIGN|
    #      OPEN DESIGN (not the platform bullet label "**REDESIGN**: …")
    #   2) under a heading that itself contains "Redesign", only primary
    #      class subjects: **Foo** (`…Foo.java`) / `Foo.java` / Foo.java
    _spec_path = Path(tasks_path).resolve().parent / "spec.md"
    if _spec_path.is_file():
        try:
            _spec_text = _spec_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            _spec_text = ""
        if _spec_text.strip():
            _spec_skip = {
                "REDESIGN",
                "HARVEST",
                "OPEN",
                "DESIGN",
                "Required",
                "Implementations",
                "JDBC",
                "JPA",
                "Spring",
                "Data",
                "Target",
                "Legacy",
                "Preserve",
                "Contract",
            }
            _name_any = re.compile(
                r"`([A-Z][A-Za-z0-9]+)`|\*\*([A-Z][A-Za-z0-9]+)\*\*"
                r"|\b([A-Z][A-Za-z0-9]+)\.java\b"
            )
            _name_primary = re.compile(
                r"\*\*([A-Z][A-Za-z0-9]+)\*\*\s*\([^)]*\.java\)"
                r"|`([A-Z][A-Za-z0-9]+)\.java`"
                r"|\b([A-Z][A-Za-z0-9]+)\.java\b"
            )
            _spec_cls: set[str] = set()
            _in_redesign_sec = False
            for _ln in _spec_text.splitlines():
                if re.match(r"^#{1,6}\s+", _ln):
                    _in_redesign_sec = bool(re.search(r"(?i)\bredesign\b", _ln))
                    continue
                # Platform prose label — not a class-role declaration
                if re.search(r"(?i)^\s*[-*]\s*\*\*REDESIGN\*\*\s*:", _ln):
                    continue
                if re.search(r"(?i)\b(?:REDESIGN|OPEN DESIGN)\b", _ln):
                    if "HARVEST" in _ln and not re.search(
                        r"(?i)\bREDESIGN\b", _ln
                    ):
                        continue
                    for mm in _name_any.finditer(_ln):
                        nm = mm.group(1) or mm.group(2) or mm.group(3)
                        if nm and nm not in _spec_skip:
                            _spec_cls.add(nm)
                    continue
                if _in_redesign_sec:
                    for mm in _name_primary.finditer(_ln):
                        nm = mm.group(1) or mm.group(2) or mm.group(3)
                        if nm and nm not in _spec_skip:
                            _spec_cls.add(nm)
            _port_reimpl = re.compile(
                r"(?im)^\*\*Port\*\*\s*:?\s*reimplement\b"
                r"|^\*\*Port\s*:\s*reimplement\*\*"
                r"|^Port\s*:\s*reimplement\b"
            )
            for cls in sorted(_spec_cls):
                covered = False
                for _, tid, title in heads:
                    body = bodies.get(tid, "")
                    blob = f"{title}\n{body}"
                    if not re.search(
                        rf"src/(?:main|test)/java/\S*\b{re.escape(cls)}\.java"
                        rf"|\b{re.escape(cls)}\.java\b"
                        rf"|Target:[^\n]*\b{re.escape(cls)}\b"
                        rf"|`{re.escape(cls)}`",
                        blob,
                    ):
                        continue
                    if _port_reimpl.search(body):
                        covered = True
                        break
                if not covered:
                    lint(
                        "O-SPECREIMPL",
                        f"spec.md names REDESIGN/OPEN DESIGN class {cls} but "
                        f"no task declares **Port**: reimplement for it "
                        f"(O-SPECREIMPL / ARCH A2)",
                    )

    # S-CHAR (V8 S02 HOLD; O-M3CHARSCOPE): target-side model *.java harvest
    # must name src/test — legacy **Absorbs** cites and Shape=structure prep
    # (.gitkeep) must not false-RED platform stories (petclinic S01).
    target_slash = target_pkg.replace(".", "/")
    _tgt_model_java = re.compile(
        rf"src/main/java/{re.escape(target_slash)}/model/[A-Za-z0-9_./-]+\.java"
    )
    _absorbs_line = re.compile(r"(?i)^\s*\*?\*?Absorbs\*?\*?\s*:")
    _structure_shape = re.compile(
        r"(?i)\*\*Shape\*\*:\s*(structure|verify)\b"
    )

    def _schar_claim_text(body: str) -> str:
        return "\n".join(
            ln
            for ln in body.splitlines()
            if not _absorbs_line.match(ln.strip())
        )

    _schar_needs_tests = False
    for _, tid, _ in heads:
        body = bodies.get(tid, "")
        if _structure_shape.search(body):
            continue
        if _tgt_model_java.search(_schar_claim_text(body)):
            _schar_needs_tests = True
            break
    if _schar_needs_tests and not re.search(r"src/test/", text):
        lint(
            "S-CHAR",
            "plan targets src/main/.../model/*.java but names no src/test/ path — "
            "add model-level characterization tests (deferring service tests ≠ empty tests; V8 S02)",
        )

    # K2-LABEL (V10 Poll 13): task-packet reads **Findings**: — a **Finds**:
    # alias used to pass plan-lint (whole-doc id scan) while injecting zero
    # evidence. Require the canonical label when a task cites rule ids.
    for _, tid, _title in heads:
        body = bodies.get(tid, "")
        if re.search(r"(?im)^\*?\*?Findings\*?\*?\s*:", body):
            continue
        if re.search(r"(?im)^\*?\*?Finds?\*?\*?\s*:", body):
            lint(
                "K2-LABEL",
                f"{tid}: use canonical **Findings**: (not Finds/Finding) so "
                f"task-packet injects Analysis evidence (K2)",
            )

    # S-AC1 (V9 S01 HOLD / V10 S01): platform stories must not schedule
    # ceremonial acceptance placeholders (status-map / MinimalAcceptance /
    # "simple status") — that belongs on the deploying story with a real
    # catalog/products proof (G-OK/G-FAKE). Cite acceptance.path as a full
    # literal string in prose/defer notes; do not invent a status endpoint.
    # O-M3GOK (S05): also catch status/ok and String "ok" acceptance tasked
    # onto CartEndpoint / any endpoint (deploy=true must keep catalog-backed
    # products[] proof — G-CAT / G-OK).
    # S-AC1-NEG: skip lines that negate the placeholder (e.g. "No
    # MinimalAcceptanceEndpoint…") so defer prose does not false-RED.
    _ac1_pat = re.compile(
        r"(?i)acceptance endpoint placeholder|simple status response|"
        r"returns simple status|status response for web surface|"
        r"MinimalAcceptanceEndpoint|platform_ready|"
        r"Map\.of\s*\(\s*\"status\"|"
        r"Return JSON response with status information|"
        r"platform readiness verification|"
        r"status/ok|"
        r"return\s+[\"']ok[\"']|"
        r"AcceptanceStatus|"
        r"ceremonial\s+status|"
        r"@Path\s*\(\s*[\"']/?status[\"']",
    )
    _ac1_neg = re.compile(
        r"(?i)\b(no|not|never|without|avoid|do\s+not|don't|must\s+not|do\s+NOT)\b"
        r".{0,80}(MinimalAcceptance|platform_ready|Map\.of|status/ok|"
        r"AcceptanceStatus|ceremonial\s+status|simple status|status response)",
    )
    _ac1_hit = False
    for _line in text.splitlines():
        if _ac1_neg.search(_line):
            continue
        if _ac1_pat.search(_line):
            _ac1_hit = True
            break
    if _ac1_hit:
        lint(
            "S-AC1",
            "plan schedules a ceremonial acceptance placeholder/status response — "
            "defer real acceptance to the deploy story (V9 S01 HOLD / G-OK / O-M3GOK)",
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

    # O-PKGORD (Poll 20): package-rename before any harvested .java → empty
    # ESCW. Defer until staging or src has at least one .java to rename.
    _has_java = False
    for _root in (
        Path("src/main/java"),
        Path("src/test/java"),
        Path("migration/staging/src/main/java"),
        Path("migration/staging/src/test/java"),
    ):
        if _root.is_dir() and any(_root.rglob("*.java")):
            _has_java = True
            break
    if not _has_java:
        for _, tid, title in heads:
            blob = f"{title}\n{bodies.get(tid, '')}"
            if re.search(
                r"(?i)package\s*rename|rename\s+(the\s+)?package|"
                r"apply\s+(the\s+)?package\s+rename|legacyPackage\s*→",
                blob,
            ):
                lint(
                    "O-PKGORD",
                    f"{tid}: package-rename scheduled with no harvested .java "
                    f"in src/ or migration/staging — defer to first harvest story",
                )

    # O-DTOFIRST: DTO (type-dependency) harvest must precede MapStruct/mapper
    # harvest in the same story — otherwise mapper compile RED → MiniMax.
    def _task_num(tid: str) -> int:
        m = re.search(r"(\d+)$", tid)
        return int(m.group(1)) if m else 0

    _dto_re = re.compile(
        r"(?i)\b(harvest\s+dto|dto[s]?\s+with\s+jakarta|jakarta\s+validation\s+imports|"
        r"data\s+transfer\s+object|/dto/|\.dto\.)"
    )
    _mapper_re = re.compile(
        r"(?i)\b(mapstruct|harvest\s+.*mapper|mapper\s+interface|/mapper/|\.mapper\.)"
    )
    dto_tasks, mapper_tasks = [], []
    for _, tid, title in heads:
        blob = f"{title}\n{bodies.get(tid, '')}"
        # Prefer Target path signals; title/goal fallback.
        is_dto = bool(_dto_re.search(blob)) and not re.search(
            r"(?i)mapstruct|/mapper/", blob
        )
        # Ignore package-structure / verify tasks that only mention /mapper/
        # paths or summarize MapStruct in acceptance text (S03 T-001/T-008).
        is_mapper = bool(_mapper_re.search(blob)) and not re.search(
            r"(?i)\*\*Shape\*\*:\s*(structure|verify)\b", blob
        )
        if is_dto:
            dto_tasks.append(tid)
        if is_mapper:
            mapper_tasks.append(tid)
    if dto_tasks and mapper_tasks:
        first_mapper = min(mapper_tasks, key=_task_num)
        last_dto = max(dto_tasks, key=_task_num)
        if _task_num(first_mapper) <= _task_num(last_dto):
            lint(
                "O-DTOFIRST",
                f"{first_mapper} MapStruct/mapper harvest precedes or equals "
                f"{last_dto} DTO harvest — schedule DTO (type deps) before "
                f"mappers (O-DTOFIRST)",
            )

    # O-DTOFIRST (absent-DTO story): mapper-only plans still compile-RED when
    # mapper tasks reference *.dto / /dto/ but the story never harvests DTOs
    # (petclinic-rest-v2 S03 T-005 → MiniMax). Ordering rule above is a no-op
    # when dto_tasks is empty — close that hole.
    if mapper_tasks and not dto_tasks:
        for tid in mapper_tasks:
            blob = bodies.get(tid, "")
            if re.search(r"(?i)(/dto/|\.dto\.|dto\s+imports|com\.demo\.dto)", blob):
                lint(
                    "O-DTOFIRST",
                    f"{tid} MapStruct/mapper harvest references DTOs but this "
                    f"story has no DTO harvest task — add DTO harvest before "
                    f"mappers or defer mappers (O-DTOFIRST)",
                )
                break

    # O-CDIORDER: repository CDI/Panache beans before services that @Inject them.
    # Service-first → task GREEN (unit tests) then milestone Arc
    # UnsatisfiedResolutionException (Wave2 petclinic T-007).
    # Migration-general: no specimen class names (F-70 Phase 0.5 / F-57 §3).
    _svc_cdi_re = re.compile(
        r"(?i)\b(convert\s+\w*service\w*\s+to\s+quarkus\s+cdi|"
        r"@ApplicationScoped.*service|serviceimpl\s+to\s+quarkus|"
        r"spring\s+@Service\s+to\s+quarkus)"
    )
    _repo_cdi_re = re.compile(
        r"(?i)\b(repository\s+implementation|jpa\s+repository|jdbc\s+repository|"
        r"convert\s+.*repository|/repository/|panache|"
        r"spring\s+data\s+jpa\s+repositor)"
    )
    svc_cdi_tasks, repo_cdi_tasks = [], []
    for _, tid, title in heads:
        blob = f"{title}\n{bodies.get(tid, '')}"
        if _svc_cdi_re.search(blob) or (
            re.search(r"(?i)quarkus\s+cdi|@ApplicationScoped", blob)
            and re.search(r"(?i)service", blob)
            and not re.search(r"(?i)repository", blob)
        ):
            svc_cdi_tasks.append(tid)
        if _repo_cdi_re.search(blob):
            repo_cdi_tasks.append(tid)
    if svc_cdi_tasks and repo_cdi_tasks:
        first_svc = min(svc_cdi_tasks, key=_task_num)
        first_repo = min(repo_cdi_tasks, key=_task_num)
        if _task_num(first_svc) < _task_num(first_repo):
            lint(
                "O-CDIORDER",
                f"{first_svc} service CDI precedes {first_repo} repository "
                f"CDI/Panache — schedule repository beans before services "
                f"that @Inject them (O-CDIORDER)",
            )

    # O-SHAPEDECL / O-M3SHAPEHARD (F-28): every task declares Shape for M4.
    # Default HARD (RED) so outer-loop M3_LINT_CMD and drafter self-verify
    # share the same bar without env choreography. Grandfather soft via
    # PLAN_LINT_SHAPE_WARN=1 (or legacy PLAN_LINT_REQUIRE_SHAPE=0) for
    # fixture modernization only.
    import os as _os

    _shape_re = re.compile(
        r"^\*\*Shape\s*:\s*(create|modify|remove|structure|verify)\*\*\s*$"
        r"|^\*\*Shape\*\*\s*:?\s*(create|modify|remove|structure|verify)\s*$"
        r"|^Shape\s*:\s*(create|modify|remove|structure|verify)\s*$",
        re.M | re.I,
    )
    _shape_env = _os.environ.get("PLAN_LINT_REQUIRE_SHAPE", "").lower()
    _shape_warn = _os.environ.get("PLAN_LINT_SHAPE_WARN", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if _shape_env in ("0", "false", "no") or _shape_warn:
        _require_shape = False
    elif _shape_env in ("1", "true", "yes"):
        _require_shape = True
    else:
        _require_shape = True  # O-M3SHAPEHARD default
    for _, tid, _ in heads:
        body = bodies.get(tid, "")
        if not _shape_re.search(body):
            msg = f"{tid}: missing **Shape**: create|modify|remove|structure|verify"
            if _require_shape:
                lint("O-SHAPEDECL", msg)
            else:
                print(f"WARN:O-SHAPEDECL: {msg}")

    # O-SHAPELINT: Shape=structure requires a package/.gitkeep Target deliverable.
    # Property/datasource converts marked structure get O-STRUCTTGT .gitkeep-only
    # packets and burn the worker (W4 S01 T-002). Migration-general.
    for _, tid, title in heads:
        body = bodies.get(tid, "")
        sm = re.search(
            r"(?im)^\*\*Shape\*\*\s*:?\s*(create|modify|remove|structure|verify)\b"
            r"|^\*\*Shape\s*:\s*(create|modify|remove|structure|verify)\*\*",
            body,
        )
        if not sm:
            continue
        shape = next(g for g in sm.groups() if g).lower()
        if shape != "structure":
            continue
        blob = f"{title}\n{body}"
        has_pkg = bool(
            re.search(
                r"(?i)src/(?:main|test)/java/[A-Za-z0-9_./]+/\.gitkeep"
                r"|src/(?:main|test)/java/[A-Za-z0-9_./]+/"
                r"|\.gitkeep|package-info\.java|package structure",
                blob,
            )
        )
        if not has_pkg:
            lint(
                "O-SHAPELINT",
                f"{tid}: Shape=structure requires Target package dir / .gitkeep "
                f"(or package-info) — use modify/create for property/file converts",
            )

    # O-STRUCTJAVA: Shape=structure must not list non-scaffold .java Targets.
    # Structure seats get O-STRUCTTGT .gitkeep-only packets; Panache/harvest
    # .java Targets under Shape=structure confuse the worker (READ_THRASH →
    # MiniMax). Use Shape=create|modify for convert/implement; allow only
    # package-info.java as a structure soft deliverable. Absorbs/Owns cites
    # are ignored (_target_work_paths). Migration-general.
    for _, tid, title in heads:
        body = bodies.get(tid, "")
        sm = re.search(
            r"(?im)^\*\*Shape\*\*\s*:?\s*(create|modify|remove|structure|verify)\b"
            r"|^\*\*Shape\s*:\s*(create|modify|remove|structure|verify)\*\*",
            body,
        )
        if not sm:
            continue
        shape = next(g for g in sm.groups() if g).lower()
        if shape != "structure":
            continue
        bad_java: list[str] = []
        seen_j: set[str] = set()
        for dest in _target_work_paths(body):
            base = Path(dest).name
            if not dest.endswith(".java"):
                continue
            if base == "package-info.java":
                continue
            if dest not in seen_j:
                seen_j.add(dest)
                bad_java.append(dest)
        # Also catch Target-design basenames without src/ prefix
        # (e.g. `SpringDataOwnerRepository.java` on a structure seat).
        in_target = False
        for line in body.splitlines():
            hm = re.match(r"^\s*\*?\*?([A-Za-z][A-Za-z0-9 ]*?)\*?\*?\s*:", line)
            if hm:
                field = hm.group(1).strip().lower()
                if field.startswith("target") or field == "design":
                    in_target = True
                elif field in (
                    "absorbs",
                    "owns",
                    "class",
                    "shape",
                    "goal",
                    "findings",
                    "acceptance",
                    "oracle",
                    "out of scope",
                ):
                    in_target = False
            if not in_target:
                continue
            for m in re.finditer(
                r"\b([A-Za-z_][A-Za-z0-9_]+\.java)\b", line
            ):
                base = m.group(1)
                if base == "package-info.java":
                    continue
                if base not in seen_j:
                    seen_j.add(base)
                    bad_java.append(base)
        if bad_java:
            # Prefer full paths over bare basenames already covered by a path.
            covered = {
                Path(p).name for p in bad_java if "/" in p
            }
            uniq = [
                p
                for p in bad_java
                if "/" in p or p not in covered
            ]
            sample = ", ".join(f"`{p}`" for p in uniq[:4])
            more = "…" if len(uniq) > 4 else ""
            lint(
                "O-STRUCTJAVA",
                f"{tid}: Shape=structure must not Target .java sources "
                f"({sample}{more}) — use create/modify for convert/harvest/"
                f"implement; structure delivers package dirs + .gitkeep "
                f"(or package-info.java only)",
            )

    # O-M3TASKSCOPE: when --story-scope is set, RED non-test Target/→
    # destinations outside roadmap scope (migration-general; parameterized by
    # scope list + migration.yaml package remap — no specimen class names).
    # Repository-layer stories must not schedule service/controller/endpoint
    # Targets. Characterization src/test/ and Out-of-scope/Absorbs deferrals
    # are allowed.
    if story_scope:
        for _, tid, _title in heads:
            body = bodies.get(tid, "")
            for dest in _target_work_paths(body):
                if _work_path_in_story_scope(
                    dest, story_scope, legacy_pkg, target_pkg
                ):
                    continue
                lint(
                    "O-M3TASKSCOPE",
                    f"{tid}: Target `{dest}` is outside --story-scope "
                    f"(roadmap scope keywords/paths) — drop or defer to the "
                    f"owning story; characterization src/test/ only",
                )

    # G5 / O-INFERABSENT (Wave4 §2.1/§2.2): derive Oracle from filesystem
    # (legacy test for Target? Target in destination?) — never default
    # undeclared → present. infer + derived-absent fails PLAN OK unless a
    # documented proceed path applies (Shape=create|verify, or
    # Proceed: O-NULLACTION one-liner for fixtures / honest stop).
    for _, tid, _ in heads:
        body = bodies.get(tid, "")
        cls = classes.get(tid, "")
        if cls != "infer":
            continue
        oracle = derive_oracle(
            body, root=Path.cwd(), legacy_pkg=legacy_pkg, target_pkg=target_pkg
        )
        shape = _oracle_task_shape(body)
        if inferabsent_blocks(
            cls=cls, oracle=oracle, shape=shape, body=body
        ):
            lint(
                "O-INFERABSENT",
                f"{tid}: infer + derived Oracle:absent (no legacy test for "
                f"Target and Target missing from destination) — reshape to "
                f"Shape=create (create-procedure), Shape=verify (deferral), "
                f"or one-line Proceed: O-NULLACTION (O-INFERABSENT / "
                f"O-ORACLEDERIVE)",
            )

    # O-PLANORDER (N11): conversion order from migration/dependency-order.md
    # + bean-uniqueness (same Target .java owned by two tasks).
    root = Path.cwd()

    def _path_to_fqn(rel: str) -> str:
        for kind in ("main", "test"):
            pref = f"src/{kind}/java/"
            if rel.startswith(pref) and rel.endswith(".java"):
                return rel[len(pref) : -5].replace("/", ".")
        return ""

    dep_md = root / "migration" / "dependency-order.md"
    fqn_rank: dict[str, int] = {}
    god_nodes: set[str] = set()
    if dep_md.is_file():
        for line in dep_md.read_text(encoding="utf-8", errors="replace").splitlines():
            dm = re.match(r"^\s*(\d+)\.\s+([\w.]+)\s+\(", line)
            if dm:
                fqn_rank[dm.group(2)] = int(dm.group(1))
                if re.search(r"(?i)god-node", line):
                    god_nodes.add(dm.group(2))

    task_fqns: dict[str, set[str]] = {tid: set() for _, tid, _ in heads}
    target_owners: dict[str, str] = {}
    for _, tid, _ in heads:
        body = bodies.get(tid, "")
        # Only Claim lines count as ownership (not "Out of scope: …Beta.java").
        claimed: list[str] = []
        for line in body.splitlines():
            if _OOS_LINE.search(line):
                continue
            if _CLAIM_LINE.search(line) or "→" in line or "->" in line:
                claimed.extend(_JAVA_PATH.findall(line))
        for rel in claimed:
            prev = target_owners.get(rel)
            if prev and prev != tid:
                lint(
                    "O-PLANORDER",
                    f"bean-uniqueness: {rel} owned by both {prev} and {tid}",
                )
            else:
                target_owners[rel] = tid
            fqn = _path_to_fqn(rel)
            if fqn:
                task_fqns[tid].add(fqn)
                # Also accept legacy→target remap for dep-order matching
                if legacy_pkg and target_pkg and fqn.startswith(target_pkg + "."):
                    task_fqns[tid].add(
                        legacy_pkg + fqn[len(target_pkg) :]
                    )

    if fqn_rank:
        task_for_fqn: dict[str, str] = {}
        for tid, fqns in task_fqns.items():
            for f in fqns:
                # Prefer exact dep-order keys; keep first owner
                task_for_fqn.setdefault(f, tid)
        # If A converts before B in dependency-order (rank A < rank B),
        # A's task number must be ≤ B's task number.
        owned = [(f, r) for f, r in fqn_rank.items() if f in task_for_fqn]
        for i, (f1, r1) in enumerate(owned):
            for f2, r2 in owned[i + 1 :]:
                if r1 >= r2:
                    continue
                t1, t2 = task_for_fqn[f1], task_for_fqn[f2]
                if t1 != t2 and _task_num(t1) > _task_num(t2):
                    lint(
                        "O-PLANORDER",
                        f"{t2} ({f2}) precedes {t1} ({f1}) but "
                        f"dependency-order converts {f1} before {f2}",
                    )

    # S-GODORDER: god-node harvest must follow an earlier-indexed
    # characterization that names the class (plan-lint, not predicate grammar).
    # Complements S-CHAR (any src/test existence) — v3 S02 inverted god nodes
    # before T-013 tail characterization with no gate.
    # O-GODORDERMID / W4-048a: mid-M4 hot-swap must NOT force MiniMax to
    # renumber already-committed T-NNN tips. Skip harvest tasks that already
    # have a T-NNN: tip since RUN_BASE (fresh M3 still REDs — no tip yet).
    if god_nodes:
        import subprocess as _sp

        def _is_char_task(title: str, body: str) -> bool:
            blob = f"{title}\n{body}"
            return bool(
                re.search(r"(?i)\bcharacterization\b", blob)
                or re.search(r"src/test/", blob)
            )

        def _names_simple(blob: str, simple: str) -> bool:
            return bool(
                re.search(rf"\b{re.escape(simple)}\b", blob)
                or re.search(rf"\b{re.escape(simple)}Test\b", blob)
            )

        def _tip_already_committed(tid: str) -> bool:
            if _os.environ.get("PLAN_LINT_GODORDER_STRICT", "").lower() in (
                "1",
                "true",
                "yes",
            ):
                return False
            run_base = _os.environ.get("RUN_BASE", "").strip()
            # O-GODORDERUNSET: without RUN_BASE, `git log HEAD --grep ^T-NNN:`
            # matches prior-story tips and falsely skips S-GODORDER on fresh M3
            # (v3 S03 573cc08 outer GREEN → supervisor RED). Mid-run skip only
            # when RUN_BASE is set (O-GODORDERMID / W4-048a).
            if not run_base:
                return False
            rev_range = f"{run_base}..HEAD"
            try:
                out = _sp.check_output(
                    [
                        "git",
                        "log",
                        "--oneline",
                        rev_range,
                        "--grep",
                        rf"^{re.escape(tid)}:",
                        "-E",
                    ],
                    cwd=str(root),
                    stderr=_sp.DEVNULL,
                    text=True,
                )
            except (_sp.CalledProcessError, FileNotFoundError, OSError):
                return False
            return bool(out.strip())

        for _, tid, title in heads:
            body = bodies.get(tid, "")
            if _structure_shape.search(body):
                continue
            if _is_char_task(title, body) and not re.search(
                r"(?i)\bharvest\b|\bconvert\b|src/main/java/", f"{title}\n{body}"
            ):
                continue
            if _tip_already_committed(tid):
                print(
                    f"WARN:S-GODORDER: {tid}: harvest tip already committed — "
                    f"skip mid-run renumber (O-GODORDERMID / W4-048a)"
                )
                continue
            owned_gods = sorted(task_fqns.get(tid, set()) & god_nodes)
            # Also match target-pkg remapped gods via simple-name Owns paths
            for g in list(god_nodes):
                simple = g.rsplit(".", 1)[-1]
                if re.search(
                    rf"src/main/java/[A-Za-z0-9_./]+/{re.escape(simple)}\.java",
                    body,
                ):
                    if g not in owned_gods:
                        owned_gods.append(g)
            seen_simple: set[str] = set()
            for gfqn in owned_gods:
                simple = gfqn.rsplit(".", 1)[-1]
                if simple in seen_simple:
                    continue
                seen_simple.add(simple)
                earlier = False
                for _, otid, otitle in heads:
                    if _task_num(otid) >= _task_num(tid):
                        continue
                    obody = bodies.get(otid, "")
                    if _is_char_task(otitle, obody) and _names_simple(
                        f"{otitle}\n{obody}", simple
                    ):
                        earlier = True
                        break
                if not earlier:
                    lint(
                        "S-GODORDER",
                        f"{tid}: god-node {simple} harvest lacks earlier "
                        f"characterization naming {simple} "
                        f"(dependency-order mark; put char tests before convert)",
                    )

    # O-PLANEXISTS (N10 / R-217b / F-66): every task must still have real work.
    # rewrite/convert of Spring→Quarkus is dead when Quarkus is already in place;
    # remove tasks are dead when the named symbol/file is already absent.
    try:
        pom = (root / "pom.xml").read_text(encoding="utf-8", errors="replace")
    except OSError:
        pom = ""
    has_quarkus_bom = bool(re.search(r"quarkus-(?:universe-)?bom", pom))
    has_spring_parent = bool(re.search(r"spring-boot-starter-parent", pom))
    has_quarkus_plugin = bool(re.search(r"quarkus-maven-plugin", pom))
    has_spring_plugin = bool(re.search(r"spring-boot-maven-plugin", pom))
    has_spring_dep = bool(re.search(r"spring-boot-starter", pom))

    def _src_has(pattern: str) -> bool:
        rx = re.compile(pattern)
        for base in (root / "src/main/java", root / "src/test/java"):
            if not base.is_dir():
                continue
            for p in base.rglob("*.java"):
                try:
                    if rx.search(p.read_text(encoding="utf-8", errors="replace")):
                        return True
                except OSError:
                    continue
        return False

    delivered = _committed_task_ids()
    for _, tid, title in heads:
        # Already shipped this run — skip dead-work RED (mid-story re-enter).
        if tid in delivered:
            continue
        blob = f"{title}\n{bodies.get(tid, '')}"
        # Spring Boot parent / platform BOM → Quarkus
        if re.search(r"(?i)spring\s*boot\s*parent|platform\s*bom|quarkus\s*platform\s*bom", blob):
            if has_quarkus_bom and not has_spring_parent:
                lint(
                    "O-PLANEXISTS",
                    f"{tid}: Spring Boot parent/BOM already absent and Quarkus BOM "
                    f"present — task is dead (O-PLANEXISTS)",
                )
        # Spring Boot Maven plugin → Quarkus plugin
        if re.search(r"(?i)spring\s*boot\s*maven\s*plugin", blob) and re.search(
            r"(?i)\b(replace|convert)\b", title
        ):
            if has_quarkus_plugin and not has_spring_plugin:
                lint(
                    "O-PLANEXISTS",
                    f"{tid}: spring-boot-maven-plugin already absent and "
                    f"quarkus-maven-plugin present — task is dead (O-PLANEXISTS)",
                )
        # Spring Boot dependencies → Quarkus extensions
        if re.search(r"(?i)spring\s*boot\s*dependenc|spring-specific\s*dependenc", blob) and re.search(
            r"(?i)\b(convert|replace|remove)\b", title
        ):
            if has_quarkus_bom and not has_spring_dep:
                lint(
                    "O-PLANEXISTS",
                    f"{tid}: Spring Boot dependencies already absent under Quarkus "
                    f"BOM — task is dead (O-PLANEXISTS)",
                )
        # Remove @SpringBootApplication (S03 T-010 class)
        if re.search(r"(?i)@?SpringBootApplication", blob) and re.search(
            r"(?i)\b(remove|delete|eliminate)\b", blob
        ):
            if not _src_has(r"@SpringBootApplication"):
                lint(
                    "O-PLANEXISTS",
                    f"{tid}: @SpringBootApplication already absent — remove task "
                    f"is dead (O-PLANEXISTS)",
                )
        # Actuator → SmallRye Health (S03 T-011 / O-PLANHEALTH): dead when
        # quarkus-smallrye-health is present and Spring actuator is gone.
        if re.search(r"(?i)actuator", blob) and re.search(
            r"(?i)health|smallrye", blob
        ):
            has_smallrye = bool(re.search(r"quarkus-smallrye-health", pom))
            has_actuator_dep = bool(re.search(r"spring-boot-starter-actuator", pom))
            has_actuator_src = _src_has(
                r"org\.springframework\.boot\.actuate|@Endpoint\b"
            )
            if has_smallrye and not has_actuator_dep and not has_actuator_src:
                lint(
                    "O-PLANEXISTS",
                    f"{tid}: spring-boot-starter-actuator already absent and "
                    f"quarkus-smallrye-health present — health convert is dead "
                    f"(O-PLANEXISTS)",
                )
        # Shape:remove / Remove title with Target .java that is already gone
        if re.search(r"(?i)\*\*Shape\*\*\s*:\s*`?remove`?", blob) or re.match(
            r"(?i)^\s*Remove\b", title
        ):
            for m in _JAVA_PATH.finditer(blob):
                rel = m.group(0)
                if not (root / rel).is_file():
                    lint(
                        "O-PLANEXISTS",
                        f"{tid}: remove/Target {rel} already absent — task is dead "
                        f"(O-PLANEXISTS)",
                    )

    # O-PORTREIMPL: API-swap convert tasks must declare Port: rename|reimplement.
    # S03 evidence (W4-101 / clean-stop): harness vocabulary had Class+Shape but
    # no axis for "target API ≠ source API". T-003 (EntityManager unchanged =
    # rename) went first-pass green; T-002/T-004 (JDBC→Agroal / Spring Data→
    # Panache = reimplement) burned seats under transliteration assumptions.
    # Migration-general — keyword/API signals only; no specimen class names.
    _port_re = re.compile(
        r"(?im)^\*\*Port\*\*\s*:?\s*(rename|reimplement)\b"
        r"|^\*\*Port\s*:\s*(rename|reimplement)\*\*"
        r"|^Port\s*:\s*(rename|reimplement)\b"
    )
    _port_reimpl_signal = re.compile(
        r"(?i)\b("
        r"spring\s*data|springdatajpa|panache|"
        r"namedparameterjdbctemplate|simplejdbcinsert|jdbctemplate|"
        r"agroal|java\.sql\.|javax\.sql\.|"
        r"re-?implement|consolidat\w*\s+.*repositor|"
        r"convert\w*\s+.*(?:panache|agroal|jdbc)|"
        r"@query\b|crudrepository|jpa\.repository"
        r")\b"
    )
    _port_map_table = re.compile(
        r"(?i)(?:legacy|from|spring|source).{0,40}(?:→|->|=>|to|⇒).{0,40}"
        r"(?:target|panache|agroal|jakarta|quarkus|persistence)|"
        r"(?:mapping\s+table|api\s+mapping|exception\s+map)|"
        r"DataAccessException.{0,20}PersistenceException|"
        r"EmptyResultDataAccessException.{0,20}NoResultException|"
        r"@Query.{0,40}(?:panache|find\(|list\()|"
        r"JdbcTemplate.{0,40}(?:DataSource|java\.sql)|"
        r"harvest.?then.?convert|convert.?after.?harvest|"
        r"O-SDJPAHARVEST|O-JDBCHARVESTAPI|O-DAOEXMAP"
    )
    for _, tid, title in heads:
        body = bodies.get(tid, "")
        blob = f"{title}\n{body}"
        sm = re.search(
            r"(?im)^\*\*Shape\*\*\s*:?\s*(create|modify)\b"
            r"|^\*\*Shape\s*:\s*(create|modify)\*\*",
            body,
        )
        if not sm:
            continue
        if not _port_reimpl_signal.search(blob):
            continue
        # Skip pure package/structure harvest titles without API swap verbs
        if re.search(r"(?i)\b(package\s+rename|package-info|\.gitkeep)\b", blob) and not re.search(
            r"(?i)\b(panache|agroal|jdbctemplate|spring\s*data|@query)\b", blob
        ):
            continue
        pm = _port_re.search(body)
        if not pm:
            lint(
                "O-PORTREIMPL",
                f"{tid}: API-swap convert (Spring Data/JDBC/Panache/Agroal) "
                f"must declare **Port**: rename|reimplement — reimplement when "
                f"target API differs from staging (not a transliteration). "
                f"Prefer harvest-then-convert split or Shape=create + "
                f"O-SDJPAHARVESTONLY convert-after-harvest (O-PORTREIMPL)",
            )
            continue
        port_val = next(g for g in pm.groups() if g).lower()
        if port_val == "reimplement" and not _port_map_table.search(blob):
            lint(
                "O-PORTREIMPL",
                f"{tid}: Port=reimplement requires an API mapping table "
                f"(legacy→target pairs, e.g. @Query→Panache find/list, "
                f"DataAccessException→PersistenceException) or explicit "
                f"harvest-then-convert / O-SDJPAHARVEST convert-after-harvest "
                f"prose (O-PORTREIMPL / O-DAOEXMAP)",
            )
        # O-REIMPLCREATE: Port=reimplement Shape=create must carry create-
        # procedure prose (harvest → mapping → first-write). Packet always
        # injects the tip; plan-lint refuses plans that omit the procedure.
        if port_val == "reimplement" and re.search(
            r"(?im)^\*\*Shape\*\*\s*:?\s*create\b|^\*\*Shape\s*:\s*create\*\*",
            body,
        ):
            if not re.search(
                r"(?i)harvest.?from.?staging|harvest.?then.?convert|"
                r"convert.?after.?harvest|create.?from.?legacy|"
                r"O-SDJPAHARVEST|O-REIMPLCREATE|O-RESTCREATE|first.?write",
                blob,
            ):
                lint(
                    "O-REIMPLCREATE",
                    f"{tid}: Port=reimplement Shape=create must declare the "
                    f"create-procedure (harvest-from-staging → API mapping "
                    f"table → first-write anchor; O-RESTCREATE class) "
                    f"(O-REIMPLCREATE)",
                )

    # O-M3PRESERVEDAO: M3 Target prose "Preserve DataAccessException" / add
    # spring-tx fights O-FIDELITYDAO / O-HARVESTREPO — Quarkus poms have no
    # spring-dao. Remap to PersistenceException or drop throws; never
    # greenwash with spring-tx/spring-jdbc/spring-orm.
    # W4-085a / O-DAOEXMAP: when Preserve/remap is mentioned, require an
    # exact-symbol mapping table (EmptyResult→NoResult, ObjectRetrieval→
    # EntityNotFound, …) — RED substring-only
    # "DataAccessException→PersistenceException" one-liners that invite
    # inventing EmptyResultPersistenceException under spring.dao.
    _dao_remap_ok = re.compile(
        r"(?i)PersistenceException|jakarta\.persistence|"
        r"strip\s+(throws\s+)?DataAccess|remap.{0,40}DataAccess|"
        r"drop\s+throws|omit\s+throws|remove\s+throws.{0,40}DataAccess|"
        r"no\s+spring-(tx|dao|jdbc|orm)",
    )
    _dao_preserve_bad = re.compile(
        r"(?i)(?:preserv\w*|maintain|keep|retain).{0,60}"
        r"(?:DataAccessException|DataRetrievalFailureException|"
        r"EmptyResultDataAccessException|ObjectRetrievalFailureException|"
        r"org\.springframework\.dao)|"
        r"(?:DataAccessException|DataRetrievalFailureException|"
        r"EmptyResultDataAccessException|ObjectRetrievalFailureException|"
        r"org\.springframework\.dao).{0,60}"
        r"(?:preserv\w*|maintain|keep|retain)|"
        r"keep\s+throws\s+DataAccess|"
        r"throws\s+DataAccessException.{0,40}(?:preserv|unchanged|verbatim)",
    )
    _dao_spring_dep_bad = re.compile(
        r"(?i)(?:add|include|depend|bring\s+back|re-?add).{0,50}"
        r"spring-(?:tx|dao|jdbc|orm)|"
        r"spring-(?:tx|dao|jdbc|orm).{0,50}"
        r"(?:add|include|depend|provided|compile\s+green|greenwash)",
    )
    _dao_preserve_neg = re.compile(
        r"(?i)\b(no|not|never|without|avoid|do\s+not|don't|must\s+not|"
        r"do\s+NOT)\b.{0,60}(?:preserv\w*|keep|retain|maintain).{0,60}"
        r"(?:DataAccessException|DataRetrievalFailureException|"
        r"org\.springframework\.dao)",
    )
    _dao_family_mention = re.compile(
        r"(?i)\b(?:DataAccessException|EmptyResultDataAccessException|"
        r"DataRetrievalFailureException|ObjectRetrievalFailureException|"
        r"org\.springframework\.dao)\b"
    )
    _dao_omit_throws = re.compile(
        r"(?i)(?:omit|drop|remove|strip)\s+throws|no\s+throws\s+DataAccess|"
        r"without\s+throws"
    )
    _dao_exact_empty = re.compile(
        r"(?i)EmptyResultDataAccessException.{0,80}NoResultException|"
        r"NoResultException.{0,80}EmptyResultDataAccessException"
    )
    _dao_exact_orf = re.compile(
        r"(?i)ObjectRetrievalFailureException.{0,80}EntityNotFoundException|"
        r"EntityNotFoundException.{0,80}ObjectRetrievalFailureException"
    )
    # Standalone DataAccessException→PersistenceException (not EmptyResult*).
    # (?<!EmptyResult) is fixed-width — required by Python re lookbehind.
    _dao_exact_dae = re.compile(
        r"(?i)(?<!EmptyResult)DataAccessException.{0,80}PersistenceException|"
        r"PersistenceException.{0,80}(?<!EmptyResult)DataAccessException"
    )
    for _, tid, title in heads:
        blob = f"{title}\n{bodies.get(tid, '')}"
        if _dao_spring_dep_bad.search(blob) and not re.search(
            r"(?i)never\s+add|do\s+not\s+add|must\s+not\s+add|forbid|"
            r"refuse|O-JDBCREGRESS|O-HYGIENEWORKER",
            blob,
        ):
            lint(
                "O-M3PRESERVEDAO",
                f"{tid}: do not schedule spring-tx/spring-dao/spring-jdbc/"
                f"spring-orm to green Spring DAO harvest — remap with an "
                f"exact-symbol table (EmptyResultDataAccessException→"
                f"NoResultException, ObjectRetrievalFailureException→"
                f"EntityNotFoundException, DataAccessException→"
                f"PersistenceException) or drop throws "
                f"(O-M3PRESERVEDAO / O-JDBCREGRESS / W4-085a)",
            )
            continue
        if (
            _dao_preserve_bad.search(blob)
            and not _dao_remap_ok.search(blob)
            and not _dao_preserve_neg.search(blob)
        ):
            lint(
                "O-M3PRESERVEDAO",
                f"{tid}: do not Preserve/keep Spring DataAccessException "
                f"(or spring.dao types) on Quarkus harvest — provide an "
                f"exact-symbol mapping table "
                f"(EmptyResultDataAccessException→NoResultException, "
                f"ObjectRetrievalFailureException→EntityNotFoundException, "
                f"DataAccessException→PersistenceException) or omit throws; "
                f"never substring-invent *PersistenceException under "
                f"org.springframework (O-M3PRESERVEDAO / O-DAOEXMAP / W4-085a)",
            )
            continue
        # W4-085a: remap path (even with parenthetical "or omit throws")
        # requires exact-symbol table. Omit-throws-ONLY (no remap verb /
        # mapping arrow) remains a valid exit without a table.
        _dao_remap_path = re.search(
            r"(?i)\bremap\b|mapping\s+table|exception\s+map|"
            r"(?<!EmptyResult)DataAccessException.{0,40}(?:→|->|=>|to)\s*"
            r"`?PersistenceException|"
            r"(?:→|->|=>)\s*`?PersistenceException",
            blob,
        )
        _dao_has_exact_table = (
            _dao_exact_empty.search(blob)
            and _dao_exact_orf.search(blob)
            and _dao_exact_dae.search(blob)
        )
        if (
            _dao_family_mention.search(blob)
            and _dao_remap_path
            and not _dao_has_exact_table
        ):
            lint(
                "O-M3PRESERVEDAO",
                f"{tid}: Spring DAO exception remap must include an "
                f"exact-symbol mapping table — at minimum "
                f"DataAccessException→PersistenceException, "
                f"EmptyResultDataAccessException→NoResultException, "
                f"ObjectRetrievalFailureException→EntityNotFoundException "
                f"(per-type; never substring rewrite). Omit-throws-only "
                f"(no remap) is OK without a table. "
                f"(O-M3PRESERVEDAO / O-DAOEXMAP / W4-085a)",
            )

    # O-T4SPRINGDATA: do not require SpringData* harvest Targets in
    # rewrite/create when Quarkus pom has no spring-data deps — unless
    # Port=reimplement / Panache convert / redesign / skip / defer.
    has_spring_data_dep = bool(
        re.search(r"(?i)spring-data|quarkus-spring-data", pom)
    )
    for _, tid, title in heads:
        body = bodies.get(tid, "")
        blob = f"{title}\n{body}"
        has_sd_target = bool(
            re.search(
                r"(?i)SpringData\w+\.java|springdatajpa/[A-Za-z0-9_./-]+\.java|"
                r"SpringData\w+Repository",
                blob,
            )
        )
        if not has_sd_target:
            continue
        if re.search(
            r"(?i)\*\*Port\*\*\s*:?\s*reimplement|Port\s*:\s*reimplement|"
            r"\bredesign\b|\bdefer(?:red)?\b|\bskip\b|panache|"
            r"O-SDJPA|O-T4SPRINGDATA|O-SDJPA-SKIP|"
            r"convert.?after.?harvest|harvest.?then.?convert|"
            r"already.?complete",
            blob,
        ):
            continue
        sm = re.search(
            r"(?im)^\*\*Shape\*\*\s*:?\s*(create|modify)\b"
            r"|^\*\*Shape\s*:\s*(create|modify)\*\*",
            body,
        )
        if not sm:
            continue
        if has_quarkus_plugin and not has_spring_data_dep and not has_spring_dep:
            lint(
                "O-T4SPRINGDATA",
                f"{tid}: SpringData* Target on Quarkus pom without spring-data "
                f"deps — do not burn harvest/compile seats. Declare "
                f"**Port**: reimplement + Panache mapping table, or "
                f"redesign/skip/defer / O-SDJPA-SKIP (Jpa* CDI cover). "
                f"(O-T4SPRINGDATA)",
            )

    # O-CHARORACLE: characterization Source→Target (or Source:) under
    # src/test/ must resolve to an existing file in migration/staging or a
    # legacy specimen root. Phantom oracle → Qwen READ_THRASH → MiniMax
    # invents hollow G-PLACE suites (Wave4 S03 T-002). Migration-general:
    # path existence only — no specimen class names.
    def _is_char_task_blob(title: str, body: str) -> bool:
        blob = f"{title}\n{body}"
        return bool(
            re.search(
                r"(?i)\bcharacterization\b|\bcharacterize\b|"
                r"\bport\s+legacy\s+.{0,40}\btest|\blegacy\s+test",
                blob,
            )
            or (
                re.search(r"(?i)\bsrc/test/", blob)
                and re.search(
                    r"(?i)\b(test|assert|verify|pin)\b", blob
                )
            )
        )

    def _char_oracle_roots() -> list[Path]:
        roots: list[Path] = []
        for cand in (
            root / "migration" / "staging",
            Path("/projects/legacy"),
            root / "legacy",
            root.parent / "legacy",
        ):
            try:
                if cand.is_dir() and cand not in roots:
                    roots.append(cand)
            except OSError:
                continue
        return roots

    def _norm_oracle_rel(raw: str) -> str:
        rel = (raw or "").strip().strip("`").lstrip("./")
        rel = re.sub(r"^/?projects/legacy/", "", rel)
        return rel

    def _oracle_file_exists(rel: str, roots: list[Path]) -> bool:
        rel = _norm_oracle_rel(rel)
        if not rel.endswith(".java"):
            return False
        for base in roots:
            try:
                if (base / rel).is_file():
                    return True
            except OSError:
                continue
        return False

    _char_src_arrow = re.compile(
        r"(?P<src>(?:/?projects/legacy/)?"
        r"src/test/java/[A-Za-z0-9_./-]+\.java)\s*(?:→|->)\s*"
        r"`?(?:src/test/java/[A-Za-z0-9_./-]+\.java)",
    )
    _char_source_field = re.compile(
        r"(?im)(?:\*\*)?(?:Source|Oracle\s*path|Legacy\s*test)(?:\*\*)?\s*:\s*`?"
        r"((?:/?projects/legacy/)?src/test/java/[A-Za-z0-9_./-]+\.java)",
    )
    oracle_roots = _char_oracle_roots()
    for _, tid, title in heads:
        body = bodies.get(tid, "")
        if tid in delivered:
            continue
        if not _is_char_task_blob(title, body):
            continue
        blob = f"{title}\n{body}"
        cited: list[str] = []
        seen_src: set[str] = set()
        for m in _char_src_arrow.finditer(blob):
            rel = _norm_oracle_rel(m.group("src"))
            if rel and rel not in seen_src:
                seen_src.add(rel)
                cited.append(rel)
        for m in _char_source_field.finditer(blob):
            rel = _norm_oracle_rel(m.group(1))
            if rel and rel not in seen_src:
                seen_src.add(rel)
                cited.append(rel)
        if not cited:
            continue
        missing = [p for p in cited if not _oracle_file_exists(p, oracle_roots)]
        if missing:
            lint(
                "O-CHARORACLE",
                f"{tid}: characterization Source/oracle path(s) absent from "
                f"migration/staging and legacy specimen — {', '.join(missing[:4])}"
                f"{'…' if len(missing) > 4 else ''}. Drop/re-scope the char task "
                f"or cite an existing staging/legacy test (do not invent G-PLACE)",
            )

    # O-COLLABOWN: Shape=modify/create convert/harvest Targets must own (or
    # explicitly defer) every same-package type their staging sources
    # reference. Missing collaborators → compile-impossible convert →
    # tree-fix stub-nuke (O-TREEFIXSTUB). Migration-general: staging
    # directory peers only — no specimen class names.
    staging_main = root / "migration" / "staging" / "src" / "main" / "java"
    claimed_by_base: dict[str, str] = {}
    deferred_bases: set[str] = set()
    for _, tid, _ in heads:
        body = bodies.get(tid, "")
        for line in body.splitlines():
            if _OOS_LINE.search(line):
                for m in _JAVA_PATH.finditer(line):
                    deferred_bases.add(Path(m.group(0)).stem)
                for m in re.finditer(r"\b([A-Z][\w]+)\b", line):
                    deferred_bases.add(m.group(1))
                continue
            if _CLAIM_LINE.search(line) or "→" in line or "->" in line:
                for m in _JAVA_PATH.finditer(line):
                    rel = m.group(0)
                    claimed_by_base.setdefault(Path(rel).stem, tid)
    _collab_task = re.compile(
        r"(?i)\b(harvest|convert|rewrite|jdbc|repository|cdi|@autowired|"
        r"namedparameterjdbctemplate|simplejdbcinsert)\b"
    )
    _shape_cm = re.compile(
        r"(?im)^\*\*Shape\*\*\s*:?\s*(create|modify)\b"
        r"|^\*\*Shape\s*:\s*(create|modify)\*\*"
    )
    if staging_main.is_dir():
        for _, tid, title in heads:
            body = bodies.get(tid, "")
            blob = f"{title}\n{body}"
            if not _shape_cm.search(blob) or not _collab_task.search(blob):
                continue
            targets: list[str] = []
            for line in body.splitlines():
                if _OOS_LINE.search(line):
                    continue
                if _CLAIM_LINE.search(line) or "→" in line or "->" in line:
                    targets.extend(_JAVA_PATH.findall(line))
            targets = [t for t in targets if t.startswith("src/main/") and t.endswith(".java")]
            if not targets:
                continue
            missing_collabs: list[str] = []
            for tgt in targets:
                # Map target path → staging via package remap
                variants = _pkg_path_variants(tgt, legacy_pkg, target_pkg)
                staging_file = None
                for v in variants:
                    # migration/staging/<src/main/java/...> or under staging_main
                    for cand in (
                        root / "migration" / "staging" / v,
                        staging_main
                        / (
                            v[len("src/main/java/") :]
                            if v.startswith("src/main/java/")
                            else v
                        ),
                    ):
                        try:
                            if cand.is_file():
                                staging_file = cand
                                break
                        except OSError:
                            continue
                    if staging_file:
                        break
                if staging_file is None:
                    continue
                try:
                    src_text = staging_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                peer_dir = staging_file.parent
                peers = {
                    p.stem
                    for p in peer_dir.glob("*.java")
                    if p.name not in ("package-info.java", "module-info.java")
                    and p.stem != staging_file.stem
                }
                self_base = staging_file.stem
                for peer in sorted(peers):
                    if peer == self_base:
                        continue
                    # Same-package type use: peer appears as a type token
                    if not re.search(
                        rf"\b{re.escape(peer)}\b", src_text
                    ):
                        continue
                    if peer in claimed_by_base or peer in deferred_bases:
                        continue
                    missing_collabs.append(peer)
            # de-dupe preserve order
            seen_c: set[str] = set()
            uniq_c: list[str] = []
            for c in missing_collabs:
                if c not in seen_c:
                    seen_c.add(c)
                    uniq_c.append(c)
            if uniq_c:
                lint(
                    "O-COLLABOWN",
                    f"{tid}: Target staging peers referenced but not owned/"
                    f"deferred: {', '.join(uniq_c[:6])}"
                    f"{'…' if len(uniq_c) > 6 else ''} — claim via Target/"
                    f"Owns/Absorbs or Out-of-scope/Deferred (O-COLLABOWN; "
                    f"pairs O-TREEFIXSTUB)",
                )

    print("\n".join(problems) if problems else
          f"PLAN OK: {len(heads)} tasks, classes {dict((c, list(classes.values()).count(c)) for c in set(classes.values()))}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
