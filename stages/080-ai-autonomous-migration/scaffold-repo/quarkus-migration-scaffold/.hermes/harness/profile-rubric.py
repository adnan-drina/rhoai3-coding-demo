#!/usr/bin/env python3
"""M1 rubric: deterministic structure/evidence check for
migration/architecture-profile.md (judgment quality is reviewed by a
human/retro; this gate only makes sure the judgment is inspectable).

Usage: profile-rubric.py <architecture-profile.md> [<legacy-src-dir>]
When the legacy source dir is given, §7 class-role classification is
cross-checked deterministically (every CDI/JAX-RS class must be REDESIGN).
O-RUBRICGENSRC: walk skips target/build/generated-sources (generated
MapStruct *MapperImpl must not induce classroles).
O-PROFDENSITY: class coverage |named|/|src classes| must be
≥ max(80%, previous accepted, best observed this PROFILE stage).
Previous accepted: PROFILE_COVERAGE_PREV or migration/.profile-coverage
(written on PROFILE OK). Best observed: migration/.profile-coverage-best
(updated on every rubric run, even RED) so a retry cannot ship lower
coverage than a rejected attempt already earned (O-PROFBESTOBS / W4-344).
O-RUBRICGENASSERT: §7 must not assign HARVEST/REDESIGN to generated
paths (target/build/generated-sources) or *MapperImpl — build owns those;
prose about MapStruct/codegen without a role assignment still passes.
O-PROFCLAIMTRUTH (ADR-21 G1): a §7 line that cites a path/class and names
a code token must have that token occur in the cited legacy file.
Claimtruth covers claims *about legacy code* only — declared target
contracts (Quarkus/Panache/ExceptionMapper/HTTP status shapes, ADR-4
"decisions are declared") are out of scope via _CLAIMTRUTH_DEST_OK and
must never be treated as fabrications (W4R7 W-5 / W4-367 `503` retraction).
Do not extend O-SPECCLAIMTRUTH (G5) onto target-contract prose.
O-PROFVOCAB (ADR-21 G2): §7 must not use targetContract decisive tokens
when the matching migration.yaml flag is not true (kills prior-specimen
residue like ConcurrentHashMap / normalize-before-derive under false
flags). Skills are intentionally excluded from the allow corpus — they
teach cart defaults and would launder residue.
Exit 0 = pass; findings printed one per line as 'RUBRIC:<class>: ...'.
"""
import os
import re
import sys

# O-PROFDENSITY — absolute floor; effective floor may ratchet upward.
COVERAGE_FLOOR = 0.80


def _parse_ratio(raw: str):
    """Parse '0.93', '93%', or '77/83' into a float ratio, or None."""
    s = (raw or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d+)\s*/\s*(\d+)$", s)
    if m:
        den = int(m.group(2))
        return (int(m.group(1)) / den) if den else None
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100.0
        except ValueError:
            return None
    try:
        v = float(s)
    except ValueError:
        return None
    if v > 1.0 + 1e-9:
        return v / 100.0
    return v


def _read_coverage_sidecar(path: str):
    """Return ratio from a coverage sidecar, preferring named/total."""
    if not os.path.isfile(path):
        return None
    named = total = ratio = None
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("ratio:"):
            ratio = _parse_ratio(line.split(":", 1)[1])
        elif line.startswith("named:"):
            try:
                named = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("total:"):
            try:
                total = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif ratio is None and ("/" in line or line.endswith("%") or
                                re.match(r"^\d", line)):
            ratio = _parse_ratio(line.split()[0] if line.split() else line)
    # Prefer named/total — decimal ratio alone can round above the true fraction
    # and false-RED the same accepted profile (77/83 vs ratio:0.927711).
    if named is not None and total:
        return named / total
    if ratio is not None:
        return ratio
    return None


def _coverage_side_dir(profile_path: str) -> str:
    return os.path.dirname(os.path.abspath(profile_path))


def _previous_accepted_ratio(profile_path: str):
    """G3 — load prior accepted coverage for the no-regression ratchet."""
    env = _parse_ratio(os.environ.get("PROFILE_COVERAGE_PREV", ""))
    if env is not None:
        return env
    return _read_coverage_sidecar(
        os.path.join(_coverage_side_dir(profile_path), ".profile-coverage")
    )


def _best_observed_ratio(profile_path: str):
    """O-PROFBESTOBS — best coverage seen this PROFILE stage (incl. RED)."""
    env = _parse_ratio(os.environ.get("PROFILE_COVERAGE_BEST", ""))
    if env is not None:
        return env
    return _read_coverage_sidecar(
        os.path.join(_coverage_side_dir(profile_path), ".profile-coverage-best")
    )


def _write_coverage_sidecar(path: str, header: str, named: int, total: int) -> None:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(
                f"# {header}\n"
                f"named: {named}\n"
                f"total: {total}\n"
                f"ratio: {named}/{total}\n"
            )
    except OSError:
        pass


def _write_accepted_coverage(profile_path: str, named: int, total: int, ratio: float) -> None:
    _write_coverage_sidecar(
        os.path.join(_coverage_side_dir(profile_path), ".profile-coverage"),
        "O-PROFDENSITY previous-accepted (G3 ratchet)",
        named,
        total,
    )


def _note_best_observed(profile_path: str, named: int, total: int, ratio: float) -> None:
    """Raise .profile-coverage-best when this run exceeds prior observations."""
    side = os.path.join(_coverage_side_dir(profile_path), ".profile-coverage-best")
    prev_best = _read_coverage_sidecar(side)
    if prev_best is not None and ratio + 1e-6 < prev_best:
        return
    _write_coverage_sidecar(
        side,
        "O-PROFBESTOBS best-observed this PROFILE stage (even if RED)",
        named,
        total,
    )


def _path_skipped(path: str) -> bool:
    """O-RUBRICGENSRC — never grade generated/build output as source classroles."""
    return any(
        part in ("target", "build", "generated-sources")
        for part in path.replace("\\", "/").split("/")
    )


# Citation forms used beside §7 claims: (Foo.java:12) or src/main/.../Foo.java
_CITE_FILE = re.compile(
    r"\(([^()]+\.java)(?::\d[\d\-–,]*)?\)|"
    r"(src/(?:main|test)/[^\s)\]|,]+\.java)"
)
# Code tokens: @Anno, `Ident`, **Ident**, or bare multi-hump CamelCase types.
# Single-hump Title words (**Validation**, Configuration) are section labels,
# not Java types — require ≥2 humps for bold/bare (O-PROFCLAIMTRUTH).
_CODE_TOKEN = re.compile(
    r"@([A-Z][A-Za-z0-9]*)(?:\([^)]*\))?|"
    r"`([A-Za-z_][A-Za-z0-9_]*)`|"
    r"\*\*([A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]+)+)\*\*|"
    r"\b([A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]+)+)\b"
)
_SKIP_CLAIM_TOKENS = {
    # Role / CDI / JAX-RS vocabulary — not claimtruth member tokens.
    "REDESIGN", "HARVEST", "ApplicationScoped", "Inject", "Singleton",
    "RequestScoped", "Path", "Service", "Component", "RestController",
    "Repository", "Entity", "Target", "Preserve",
}
# Destination / platform types named in redesign prose need not occur in the
# cited *legacy* file (claimtruth asks about source fidelity, not targets).
_CLAIMTRUTH_DEST_OK = {
    "SmallRye", "OpenAPI", "ExceptionMapper", "ProcessingException",
    "ProblemDetail", "PanacheEntity", "PanacheRepository", "RestClient",
    "ConfigProperty", "Transactional", "ApplicationScoped", "RequestScoped",
    "QuarkusTest", "OpenApi", "MicroProfile",
}


def _resolve_cited_java(cite: str, legacy_root: str):
    """Map a citation like ClinicServiceImpl.java to a file under legacy."""
    cite = cite.strip().lstrip("/")
    if cite.startswith("src/"):
        cand = os.path.join(legacy_root, cite)
        return cand if os.path.isfile(cand) else None
    base = os.path.basename(cite)
    for dp, dirnames, fs in os.walk(legacy_root):
        dirnames[:] = [
            d for d in dirnames
            if d not in ("target", "build", "generated-sources")
        ]
        if _path_skipped(dp):
            continue
        if base in fs:
            return os.path.join(dp, base)
    return None


def _tokens_on_line(line: str) -> list[str]:
    # Class names that only appear as Foo.java citations are subjects, not claims.
    cited_bases = {
        os.path.basename(g).removesuffix(".java")
        for m in _CITE_FILE.finditer(line)
        for g in m.groups() if g
    }
    # Also strip bare `Foo.java` mentions the cite regex might miss.
    cited_bases.update(re.findall(r"\b([A-Z][A-Za-z0-9]+)\.java\b", line))
    out: list[str] = []
    for m in _CODE_TOKEN.finditer(line):
        tok = next(g for g in m.groups() if g)
        if tok in _SKIP_CLAIM_TOKENS or tok in cited_bases:
            continue
        if tok in _CLAIMTRUTH_DEST_OK:
            continue
        out.append(tok)
    return out


def _is_legacy_type_name(tok: str, legacy_root: str) -> bool:
    """True when tok names a .java type in legacy (subject label, not a claim)."""
    plain = tok.lstrip("@")
    return _resolve_cited_java(plain + ".java", legacy_root) is not None


def _check_claim_truth(sec7: str, legacy_root: str, problems: list) -> None:
    """O-PROFCLAIMTRUTH — cited-file *legacy* claims must be true of that file.

    Out of scope: declared target contracts (destination types / HTTP shapes /
    Quarkus APIs named as the decided redesign). Those are ADR-4 decisions,
    not legacy facts — see module docstring and _CLAIMTRUTH_DEST_OK (W-5).
    """
    if not legacy_root or not os.path.isdir(legacy_root):
        return
    seen: set[tuple[str, str]] = set()
    for line in sec7.splitlines():
        cites = [g for m in _CITE_FILE.finditer(line) for g in m.groups() if g]
        if not cites:
            continue
        tokens = [
            t for t in _tokens_on_line(line)
            if not _is_legacy_type_name(t, legacy_root)
        ]
        if not tokens:
            continue
        bodies: list[tuple[str, str]] = []
        for cite in cites:
            path = _resolve_cited_java(cite, legacy_root)
            if path is None:
                continue
            try:
                bodies.append(
                    (path, open(path, encoding="utf-8", errors="replace").read())
                )
            except OSError:
                continue
        if not bodies:
            continue
        for tok in tokens:
            plain = tok.lstrip("@")
            plain_l = plain.lower()
            # Case-insensitive: SpringFox ↔ springfox package/import segments.
            if any(
                plain in body or tok in body or plain_l in body.lower()
                for _, body in bodies
            ):
                continue
            # Token absent from every cited file on this line.
            key = (tuple(os.path.basename(p) for p, _ in bodies), tok)
            if key in seen:
                continue
            seen.add(key)
            cited = ", ".join(os.path.basename(p) for p, _ in bodies)
            problems.append(
                f"RUBRIC:claimtruth: §7 cites {cited} and names '{tok}' but "
                f"that token is absent from the cited file(s) "
                f"(O-PROFCLAIMTRUTH / ADR-21 G1)"
            )


def _flag_true(myaml: str, flag: str) -> bool:
    return bool(re.search(rf"^\s*{re.escape(flag)}:\s*true\b", myaml, re.M))


def _legacy_blob(legacy_root: str) -> str:
    """Concatenate non-generated legacy sources (skills intentionally omitted)."""
    chunks: list[str] = []
    if not legacy_root or not os.path.isdir(legacy_root):
        return ""
    for dp, dirnames, fs in os.walk(legacy_root):
        dirnames[:] = [
            d for d in dirnames
            if d not in ("target", "build", "generated-sources")
        ]
        if _path_skipped(dp):
            continue
        for fn in fs:
            if not fn.endswith((".java", ".xml", ".properties", ".yml", ".yaml")):
                continue
            try:
                chunks.append(
                    open(os.path.join(dp, fn), encoding="utf-8",
                         errors="replace").read()
                )
            except OSError:
                pass
    return "\n".join(chunks)


def _check_prof_vocab(sec7: str, legacy_root: str, problems: list) -> None:
    """O-PROFVOCAB — refuse prior-specimen decisive residue in §7.

    Direction opposite DECISIVE: when targetContract.<flag> is not true,
    §7 must not smuggle that flag's decisive vocabulary. Skills are out of
    corpus — they document cart defaults and would launder residue.
    Additionally, ConcurrentHashMap in §7 must exist somewhere in legacy
    when threadSafeState is true (redesign pin must still be specimen-real).
    """
    try:
        myaml = open("migration.yaml", encoding="utf-8").read()
    except OSError:
        myaml = ""
    # flag -> (regex, label) decisive tokens forbidden unless flag is true
    anti = {
        "threadSafeState": [
            (r"\bConcurrentHashMap\b", "ConcurrentHashMap"),
            (r"\bcompute\s*\(", "compute()"),
        ],
        "normalizeBeforeDerive": [
            (r"normalize-before-derive|normalize.{0,20}before\s+(?:deriv|aggregat|comput|total)",
             "normalize-before-derive"),
        ],
        "cacheRefreshGuard": [
            (r"clear-on-miss|clear.?on.?miss|no\s+clear-on-miss",
             "clear-on-miss"),
        ],
    }
    for flag, pats in anti.items():
        if _flag_true(myaml, flag):
            continue
        for pat, label in pats:
            if re.search(pat, sec7, re.I):
                problems.append(
                    f"RUBRIC:profvocab: §7 uses '{label}' but "
                    f"targetContract.{flag} is not true — prior-specimen "
                    f"residue (O-PROFVOCAB / ADR-21 G2)"
                )
                break
    # Even when threadSafeState is true: ConcurrentHashMap must occur in
    # legacy (coolstore) — inventing it for a specimen that never had it is
    # residue. mapErrors/ExceptionMapper stay out: they are destination types.
    if re.search(r"\bConcurrentHashMap\b", sec7):
        blob = _legacy_blob(legacy_root)
        if blob and "ConcurrentHashMap" not in blob:
            problems.append(
                "RUBRIC:profvocab: §7 names ConcurrentHashMap but that type "
                "does not occur in legacy source (O-PROFVOCAB / ADR-21 G2)"
            )

REQUIRED = [
    "Purpose & domain",
    "Components & relationships",
    "Integration surfaces",
    "Behavioral contract sources",
    "Modernization surface",
    "Domain boundaries",
    "Class roles",
]

# a class carrying one of these is a REDESIGN class (owns runtime behavior).
# O-MAPPINGS-PETCLINIC: @Aspect / AspectJ imports are hard REDESIGN (no Quarkus AOP).
# Do NOT match bare @Before/@After — those collide with JUnit.
# O-PROFILE7GAP: ControllerAdvice / ExceptionHandler own error-mapping runtime.
REDESIGN_ANNO = re.compile(
    r"@(Service|Component|RestController|ControllerAdvice|ExceptionHandler|"
    r"Repository|Path|ApplicationScoped"
    r"|Singleton|RequestScoped|RegisterRestClient|Aspect)\b"
    r"|org\.aspectj\.|org\.springframework\.aop\.")

# O-PROFILE7GAP — main-src helpers that must be named in §7 even without
# stereotype annotations (RowMapper/Extractor/custom Spring Data impls).
SEC7_COVER_NAME = re.compile(
    r"(RepositoryImpl|RowMapper|Extractor|ControllerAdvice|ExceptionMapper|"
    r"RepositoryOverride)$"
)

# a citation is a source path with optional :line, a finding rule id,
# a test class reference, or an M1 analyze artifact (ANALYSIS §2 interprets
# dependency-order.md — O-PROFITECITEMIG).
CITE = re.compile(
    r"(src/(?:main|test)/\S+|/projects/legacy/\S+|"
    r"migration/(?:dependency-order|findings-inventory|mta-findings|"
    r"recipe-log|ruleset-coverage)\.md\S*|"
    r"\b(?:dependency-order|findings-inventory|recipe-log|"
    r"ruleset-coverage)\.md(?::\d[\d,.\-]*)?|"
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
    coverage_snapshot = None  # (named, total, ratio) when O-PROFDENSITY ran
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

    # O-RUBRICGENASSERT — §7 must not class-role generated build outputs.
    # O-RUBRICGENSRC removed them from the walk (no coercion); this refuses
    # the opposite failure: asserting HARVEST/REDESIGN on MapperImpl / target/.
    sec7_early = section_body(text, "class role")
    for line in sec7_early.splitlines():
        if not re.search(r"\b(HARVEST|REDESIGN)\b", line):
            continue
        if re.search(
            r"MapperImpl\b|generated-sources|/target/|\bbuild/|"
            r"target/generated",
            line,
        ):
            problems.append(
                "RUBRIC:genassert: §7 assigns HARVEST/REDESIGN to a generated "
                "build artifact — omit the class-role (build-codegen owns it); "
                "naming MapStruct as a build concern without a role is OK "
                "(O-RUBRICGENASSERT)"
            )
            break

    # §7 classification cross-check (deterministic): every class the legacy
    # source marks CDI/JAX-RS/Spring-stereotype is a REDESIGN class and must
    # be marked REDESIGN in §7 — a service mislabeled HARVEST would be
    # re-pinned faithful, reintroducing the shipped-faithful bug.
    # O-PROFILE7GAP: also require §7 to *name* RepositoryImpl/RowMapper/
    # Extractor/Advice helpers (family lines OK) so BRIEFCONTRACT has a source.
    # O-PROFDENSITY: count source classes named anywhere in the profile.
    src_classes: list[str] = []
    if len(sys.argv) > 2 and os.path.isdir(sys.argv[2]):
        for dp, dirnames, fs in os.walk(sys.argv[2]):
            # Prune generated/build trees early (O-RUBRICGENSRC).
            dirnames[:] = [
                d for d in dirnames
                if d not in ("target", "build", "generated-sources")
                and not _path_skipped(os.path.join(dp, d))
            ]
            if _path_skipped(dp):
                continue
            if "/test" in dp or "/src/test" in dp:
                continue
            if "src/main" not in dp.replace("\\", "/"):
                # Still walk when callers pass a flat legacy root without
                # src/main in the path (coolstore fixtures).
                pass
            for fn in fs:
                if not fn.endswith(".java"):
                    continue
                path = os.path.join(dp, fn)
                # Skip test trees even when legacy root is shallow
                if "/src/test/" in path.replace("\\", "/"):
                    continue
                if _path_skipped(path):
                    continue
                body = open(path, encoding="utf-8", errors="replace").read()
                cls = fn[:-5]
                src_classes.append(cls)
                needs_redesign = bool(REDESIGN_ANNO.search(body))
                needs_named = needs_redesign or bool(SEC7_COVER_NAME.search(cls))
                if not needs_named:
                    continue
                role = governing_role(sec7, cls)
                if needs_redesign and role != "REDESIGN":
                    problems.append(
                        f"RUBRIC:classroles: '{cls}' carries a "
                        f"CDI/JAX-RS/stereotype annotation but §7 does not "
                        f"classify it REDESIGN"
                    )
                elif role is None:
                    problems.append(
                        f"RUBRIC:sec7-cover: '{cls}' is a main-src migration "
                        f"helper (O-PROFILE7GAP) but §7 does not name it — "
                        f"add a per-class or family REDESIGN/HARVEST line"
                    )

        # O-PROFDENSITY — class coverage floor (specimen-derived denominator).
        # G3 + O-PROFBESTOBS: floor = max(80%, previous accepted, best observed).
        if src_classes:
            named = sum(
                1 for cls in src_classes
                if re.search(r"\b" + re.escape(cls) + r"\b", text)
            )
            total = len(src_classes)
            ratio = named / total if total else 1.0
            pct = int(round(ratio * 100))
            prev = _previous_accepted_ratio(sys.argv[1])
            # Read best *before* updating — current run must clear prior best.
            best = _best_observed_ratio(sys.argv[1])
            floor = COVERAGE_FLOOR
            if prev is not None:
                floor = max(floor, prev)
            if best is not None:
                floor = max(floor, best)
            floor_pct = int(round(floor * 100))
            notes = []
            if prev is not None:
                notes.append(f"prev={int(round(prev * 100))}%")
            if best is not None:
                notes.append(f"best={int(round(best * 100))}%")
            note = (" " + " ".join(notes)) if notes else ""
            print(
                f"COVERAGE: {named}/{total} ({pct}%) "
                f"floor={floor_pct}%{note}"
            )
            if ratio + 1e-6 < floor:
                why = []
                if prev is not None and abs(floor - prev) <= 1e-6:
                    why.append("G3 no-regression ratchet")
                if best is not None and abs(floor - best) <= 1e-6:
                    why.append("O-PROFBESTOBS within-stage best")
                problems.append(
                    f"RUBRIC:coverage: class coverage {named}/{total} ({pct}%) "
                    f"is below floor {floor_pct}% (O-PROFDENSITY"
                    + (("; " + ", ".join(why)) if why else "")
                    + ")"
                )
            # Record observation after the check (even when RED) so retries
            # inherit this attempt's coverage as the new within-stage floor.
            _note_best_observed(sys.argv[1], named, total, ratio)
            coverage_snapshot = (named, total, ratio)

        # ADR-21 G1/G2 — claim truth + prior-specimen vocabulary (need legacy).
        _check_claim_truth(sec7, sys.argv[2], problems)
        _check_prof_vocab(sec7, sys.argv[2], problems)

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
        # Spring @Cacheable / Quarkus Cache are valid decisions; do not force
        # cart-only "clear-on-miss" prose when the specimen merely has @Cacheable
        # (ADR-21 — DECISIVE must not re-inject prior-specimen residue).
        "cacheRefreshGuard": (
            r"no clear|clear.?on.?miss|refresh.?guard|\bTTL\b|\b60\s*s|"
            r"time.?stamp guard|@Cacheable|\bCacheable\b|quarkus.?cache|CacheResult",
            "refresh-guard/@Cacheable",
        ),
        "normalizeBeforeDerive": (r"normalize.{0,20}before|dedup.{0,20}before|before (?:deriv|aggregat|comput|total|pric|sum)", "normalize-before-derive"),
    }
    # Cart / service numeric oracles (not targetContract flags): when §7
    # mentions add()/cart quantity semantics, require the additive→4 decision
    # token so soft "idempotent add" prose cannot pass (V6 P3.1 / P1.3).
    if re.search(r"\badd\s*\(|\badd\b.{0,40}quantit", sec7, re.I):
        if not re.search(r"additive|qty\s*4|quantity\s*4|two\s+add.{0,40}\b4\b", sec7, re.I):
            problems.append(
                "RUBRIC:target-soft: §7 discusses cart add()/quantity but does not "
                "decide additive→quantity 4 — lock the oracle, not soft idempotency prose"
            )
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

    if problems:
        print("\n".join(problems))
        return 1
    print(f"PROFILE OK: {len(REQUIRED)} sections present, cited, plan-free")
    # G3 — persist accepted coverage so the next PROFILE cannot regress below it.
    if coverage_snapshot is not None:
        n, t, r = coverage_snapshot
        _write_accepted_coverage(sys.argv[1], n, t, r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
