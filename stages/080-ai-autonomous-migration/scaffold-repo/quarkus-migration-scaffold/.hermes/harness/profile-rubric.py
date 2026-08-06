#!/usr/bin/env python3
"""M1 rubric: deterministic structure/evidence check for
migration/architecture-profile.md (judgment quality is reviewed by a
human/retro; this gate only makes sure the judgment is inspectable).

Usage: profile-rubric.py <architecture-profile.md> [<legacy-src-dir>]
When the legacy source dir is given, §7 class-role classification is
cross-checked deterministically (every CDI/JAX-RS class must be REDESIGN).
O-RUBRICGENSRC: walk skips target/build/generated-sources (generated
MapStruct *MapperImpl must not induce classroles).
O-PROFDENSITY / ADR-26 / ADR-28: class coverage |named|/|profile-units|
must be ≥ max(80%, previous accepted, best observed this PROFILE stage).
When migration/model.json exists, the denominator is model profile_units
(FQN identity, package-info excluded) — not a parallel filesystem walk.
ADR-28 (O-PROF7DENSITY): a unit counts as covered only via a
**unit-claim atom** — a §7 HARVEST/REDESIGN line whose subject set is
exactly that one unit. Group bullets (`Services (A, B, C) — REDESIGN`)
name many units but carry one claim; they credit **none**. Metric id
`unit-claim` — prior ratchet rows without this metric are ignored so a
grouped 100% cannot freeze an unreachable floor.
UNNAMED: lines list every uncovered FQN for PROFILE retry feedback.
Previous accepted: PROFILE_COVERAGE_PREV or migration/.profile-coverage
(written on PROFILE OK). Best observed: migration/.profile-coverage-best
(updated on every rubric run, even RED) so a retry cannot ship lower
coverage than a rejected attempt already earned (O-PROFBESTOBS / W4-344).
O-RUBRICGENASSERT: §7 must not assign HARVEST/REDESIGN to generated
paths (target/build/generated-sources) or *MapperImpl — build owns those;
prose about MapStruct/codegen without a role assignment still passes.
O-PROFCLAIMTRUTH (ADR-21 G1 / ADR-29): a cited path:line:token must have
that token occur **on the cited line** (line-level; file-level alone is
insufficient — (Owner.java:1) with @Entity elsewhere must refuse).
Claimtruth covers claims *about legacy code* only — declared target
contracts (Quarkus/Panache/ExceptionMapper/HTTP status shapes, ADR-4
"decisions are declared") are out of scope via _CLAIMTRUTH_DEST_OK and
must never be treated as fabrications (W4R7 W-5 / W4-367 `503` retraction).
Do not extend O-SPECCLAIMTRUTH (G5) onto target-contract prose.
ADR-29: PROFILE coverage SoT is model.units[].decision (metric=typed-decision);
§7 is a rendered view — never parse markdown to recover a role.
O-PROFVOCAB (ADR-21 G2): §7 must not use targetContract decisive tokens
when the matching migration.yaml flag is not true (kills prior-specimen
residue like ConcurrentHashMap / normalize-before-derive under false
flags). Skills are intentionally excluded from the allow corpus — they
teach cart defaults and would launder residue.
Exit 0 = pass; findings printed one per line as 'RUBRIC:<class>: ...'.
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

# O-PROFDENSITY — absolute floor; effective floor may ratchet upward.
COVERAGE_FLOOR = 0.80
# ADR-28/29 — coverage semantics version. Mismatched/missing metric ⇒ ignore ratchet.
COVERAGE_METRIC = "unit-claim"  # prose unit-claim (pre-typed / fixtures)
COVERAGE_METRIC_ROLES = "typed-decision"  # ADR-29 model.units[].decision SoT


def _find_model_path(profile_path: str) -> Optional[str]:
    """Locate migration/model.json beside the profile or under cwd."""
    p = Path(profile_path).resolve()
    candidates = [
        p.parent / "model.json",
        p.parent / "migration" / "model.json",
        Path("migration/model.json").resolve(),
        Path("model.json").resolve(),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def _load_profile_units(profile_path: str) -> Optional[List[dict]]:
    """ADR-26 — universe from model; None if model absent (fixture fallback)."""
    mp = _find_model_path(profile_path)
    if not mp:
        return None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from model import profile_units  # type: ignore

        model = json.loads(Path(mp).read_text(encoding="utf-8"))
        return profile_units(model)
    except Exception:
        return None


def _unit_simple(u: dict) -> str:
    fqn = u.get("legacy_fqn") or ""
    if fqn:
        return fqn.rsplit(".", 1)[-1]
    lp = (u.get("legacy_path") or "").replace("\\", "/")
    return Path(lp).stem if lp else ""


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


def _expected_metric_for_sot(sot: Optional[str]) -> str:
    # ADR-29: model-decision SoT must never inherit unit-claim / decided-role floors
    # (W4-446 ratchet trap — laxer metric flooring a stricter one).
    if sot in ("roles", "model-decision"):
        return COVERAGE_METRIC_ROLES  # typed-decision
    return COVERAGE_METRIC


def _read_coverage_sidecar(path: str, expect_sot: Optional[str] = None):
    """Return ratio from a coverage sidecar, preferring named/total.

    ADR-26: when expect_sot is set, ignore sidecars from a different universe
    (filesystem vs model ratios are incomparable).
    ADR-28/30: require matching metric for the SoT — cross-metric floors ignored.
    """
    if not os.path.isfile(path):
        return None
    named = total = ratio = None
    sot = None
    metric = None
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
        elif line.startswith("sot:"):
            sot = line.split(":", 1)[1].strip()
        elif line.startswith("metric:"):
            metric = line.split(":", 1)[1].strip()
        elif ratio is None and ("/" in line or line.endswith("%") or
                                re.match(r"^\d", line)):
            ratio = _parse_ratio(line.split()[0] if line.split() else line)
    if expect_sot and (sot or "filesystem") != expect_sot:
        return None
    want = _expected_metric_for_sot(expect_sot or sot)
    if (metric or "") != want:
        return None
    # Prefer named/total — decimal ratio alone can round above the true fraction
    # and false-RED the same accepted profile (77/83 vs ratio:0.927711).
    if named is not None and total:
        return named / total
    if ratio is not None:
        return ratio
    return None


def _coverage_side_dir(profile_path: str) -> str:
    return os.path.dirname(os.path.abspath(profile_path))


def _read_model_coverage_prov(
    profile_path: str, expect_sot: Optional[str] = None, which: str = "accepted"
):
    """ADR-26 — committed ratchet in model.json provenance (survives sidecar wipe)."""
    mp = _find_model_path(profile_path)
    if not mp:
        return None
    try:
        model = json.loads(Path(mp).read_text(encoding="utf-8"))
    except Exception:
        return None
    pc = (model.get("provenance") or {}).get("profile_coverage") or {}
    if expect_sot and (pc.get("sot") or "filesystem") != expect_sot:
        return None
    # ADR-28/30 — cross-metric floors are incomparable.
    want = _expected_metric_for_sot(expect_sot or pc.get("sot"))
    if (pc.get("metric") or "") != want:
        return None
    key_n = "accepted_named" if which == "accepted" else "best_named"
    key_t = "accepted_total" if which == "accepted" else "best_total"
    try:
        named = int(pc[key_n])
        total = int(pc[key_t])
    except (KeyError, TypeError, ValueError):
        return None
    return (named / total) if total else None


def _write_model_coverage_prov(
    profile_path: str,
    named: int,
    total: int,
    ratio: float,
    sot: str,
    *,
    is_best: bool = False,
    is_accepted: bool = False,
) -> None:
    """Persist coverage into model.json provenance (committed with ANALYZE/PROFILE)."""
    mp = _find_model_path(profile_path)
    if not mp or total <= 0:
        return
    try:
        model = json.loads(Path(mp).read_text(encoding="utf-8"))
    except Exception:
        return
    prov = model.setdefault("provenance", {})
    pc = prov.setdefault("profile_coverage", {})
    pc["sot"] = sot
    pc["metric"] = _expected_metric_for_sot(sot)
    if is_best:
        prev_b = _read_model_coverage_prov(profile_path, expect_sot=sot, which="best")
        if prev_b is None or ratio + 1e-6 >= prev_b:
            pc["best_named"] = named
            pc["best_total"] = total
            pc["best_ratio"] = f"{named}/{total}"
    if is_accepted:
        pc["accepted_named"] = named
        pc["accepted_total"] = total
        pc["accepted_ratio"] = f"{named}/{total}"
    try:
        Path(mp).write_text(
            json.dumps(model, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
    except OSError:
        pass


def _previous_accepted_ratio(profile_path: str, expect_sot: Optional[str] = None):
    """G3 — load prior accepted coverage for the no-regression ratchet."""
    env = _parse_ratio(os.environ.get("PROFILE_COVERAGE_PREV", ""))
    if env is not None:
        return env
    # Prefer committed model provenance (survives deliberate sidecar wipe).
    m = _read_model_coverage_prov(profile_path, expect_sot=expect_sot, which="accepted")
    if m is not None:
        return m
    return _read_coverage_sidecar(
        os.path.join(_coverage_side_dir(profile_path), ".profile-coverage"),
        expect_sot=expect_sot,
    )


def _best_observed_ratio(profile_path: str, expect_sot: Optional[str] = None):
    """O-PROFBESTOBS — best coverage seen this PROFILE stage (incl. RED)."""
    env = _parse_ratio(os.environ.get("PROFILE_COVERAGE_BEST", ""))
    if env is not None:
        return env
    m = _read_model_coverage_prov(profile_path, expect_sot=expect_sot, which="best")
    if m is not None:
        return m
    return _read_coverage_sidecar(
        os.path.join(_coverage_side_dir(profile_path), ".profile-coverage-best"),
        expect_sot=expect_sot,
    )


def _write_coverage_sidecar(
    path: str, header: str, named: int, total: int, sot: str = "filesystem"
) -> None:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(
                f"# {header}\n"
                f"named: {named}\n"
                f"total: {total}\n"
                f"ratio: {named}/{total}\n"
                f"sot: {sot}\n"
                f"metric: {_expected_metric_for_sot(sot)}\n"
            )
    except OSError:
        pass


def _write_accepted_coverage(
    profile_path: str, named: int, total: int, ratio: float, sot: str = "filesystem"
) -> None:
    _write_coverage_sidecar(
        os.path.join(_coverage_side_dir(profile_path), ".profile-coverage"),
        "O-PROFDENSITY previous-accepted (G3 ratchet)",
        named,
        total,
        sot=sot,
    )


def _note_best_observed(
    profile_path: str, named: int, total: int, ratio: float, sot: str = "filesystem"
) -> None:
    """Raise .profile-coverage-best when this run exceeds prior observations."""
    side = os.path.join(_coverage_side_dir(profile_path), ".profile-coverage-best")
    prev_best = _read_coverage_sidecar(side, expect_sot=sot)
    if prev_best is not None and ratio + 1e-6 < prev_best:
        return
    _write_coverage_sidecar(
        side,
        "O-PROFBESTOBS best-observed this PROFILE stage (even if RED)",
        named,
        total,
        sot=sot,
    )


def _path_skipped(path: str) -> bool:
    """O-RUBRICGENSRC — never grade generated/build output as source classroles."""
    return any(
        part in ("target", "build", "generated-sources")
        for part in path.replace("\\", "/").split("/")
    )


# Citation forms beside §7 claims. Group 'line' is kept for ADR-29 G1 line-level.
_CITE_FILE = re.compile(
    r"\(([^()]+\.java)(?::(\d[\d\-–,]*))?\)|"
    r"(src/(?:main|test)/[^\s)\]|,]+\.java)(?::(\d+))?"
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
    cited_bases = set()
    for m in _CITE_FILE.finditer(line):
        for g in (m.group(1), m.group(3)):
            if g and g.endswith(".java"):
                cited_bases.add(os.path.basename(g).removesuffix(".java"))
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
    """O-PROFCLAIMTRUTH — cited legacy claims must be true at path[:line].

    ADR-29: when a citation includes :N, the token must occur on line N
    (G1 line-level). File-level-only checks remain for citations without a line.
    Out of scope: declared target contracts (_CLAIMTRUTH_DEST_OK).
    """
    if not legacy_root or not os.path.isdir(legacy_root):
        return
    seen: set[tuple] = set()
    for line in sec7.splitlines():
        cite_hits: list[tuple[str, Optional[int]]] = []
        for m in _CITE_FILE.finditer(line):
            # groups: (file_in_parens, line_in_parens, src_path, src_line)
            f1, l1, f2, l2 = m.group(1), m.group(2), m.group(3), m.group(4)
            if f1:
                ln = None
                if l1:
                    try:
                        ln = int(re.match(r"\d+", l1).group(0))  # type: ignore
                    except (AttributeError, ValueError):
                        ln = None
                cite_hits.append((f1, ln))
            elif f2:
                ln = int(l2) if l2 else None
                cite_hits.append((f2, ln))
        if not cite_hits:
            continue
        tokens = [
            t for t in _tokens_on_line(line)
            if not _is_legacy_type_name(t, legacy_root)
        ]
        if not tokens:
            continue
        bodies: list[tuple[str, list[str], Optional[int]]] = []
        for cite, ln in cite_hits:
            path = _resolve_cited_java(cite, legacy_root)
            if path is None:
                continue
            try:
                lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
            except OSError:
                continue
            bodies.append((path, lines, ln))
        if not bodies:
            continue
        for tok in tokens:
            plain = tok.lstrip("@")
            plain_l = plain.lower()
            ok = False
            for _path, lines, ln in bodies:
                if ln is not None:
                    if 1 <= ln <= len(lines):
                        body = lines[ln - 1]
                        if (
                            plain in body
                            or tok in body
                            or plain_l in body.lower()
                        ):
                            ok = True
                            break
                    # line OOB or miss — not ok for this cite; try others
                    continue
                # No line: file-level (legacy G1)
                whole = "\n".join(lines)
                if plain in whole or tok in whole or plain_l in whole.lower():
                    ok = True
                    break
            if ok:
                continue
            key = (
                tuple(os.path.basename(p) for p, _, _ in bodies),
                tok,
                tuple(ln for _, _, ln in bodies),
            )
            if key in seen:
                continue
            seen.add(key)
            cited = ", ".join(
                os.path.basename(p) + (f":{ln}" if ln else "")
                for p, _, ln in bodies
            )
            problems.append(
                f"RUBRIC:claimtruth: §7 cites {cited} and names '{tok}' but "
                f"that token is absent from the cited line/file "
                f"(claim must resolve at cited path:line)"
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
                    f"residue (forbidden prior-specimen vocabulary)"
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
                "does not occur in legacy source (forbidden vocabulary)"
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


def _unit_keys(u: dict) -> list[str]:
    """Identity tokens for a profile unit (FQN + simple name)."""
    keys: list[str] = []
    fqn = (u.get("legacy_fqn") or "").strip()
    simple = _unit_simple(u)
    if fqn:
        keys.append(fqn)
    if simple and simple not in keys:
        keys.append(simple)
    return keys


def _units_mentioned_on_line(line: str, units: List[dict]) -> list[str]:
    """Distinct profile-unit labels named on a §7 line (FQN preferred)."""
    hits: list[str] = []
    seen: set[str] = set()
    for u in units:
        label = u.get("legacy_fqn") or u.get("legacy_path") or "?"
        for tok in _unit_keys(u):
            if re.search(r"\b" + re.escape(tok) + r"\b", line):
                if label not in seen:
                    seen.add(label)
                    hits.append(label)
                break
    return hits


# Legacy prose unit-claim path only (filesystem / pre-model fixtures).
# Load-bearing PROFILE coverage is ADR-29 typed decisions — not these heuristics.
# O-PROF7DECIDE three-heuristic gate DELETED (withdrawn; was never ADR-29).
_DEFERRAL_CLAIM = re.compile(
    r"confirm or upgrade|\bTBD\b|\bpending\b|to be decided|scaffold for|"
    r"—\s*UNNAMED:|needs HARVEST or REDESIGN",
    re.I,
)


def _line_is_role_claim(line: str) -> bool:
    """True for a HARVEST|REDESIGN atom that is not scaffold/deferral prose."""
    if not re.search(r"\b(HARVEST|REDESIGN)\b", line):
        return False
    if _DEFERRAL_CLAIM.search(line):
        return False
    return True


def _unit_covered_in_sec7(
    sec7: str, u: dict, all_units: Optional[List[dict]] = None
) -> bool:
    """ADR-26 + ADR-28 — prose unit-claim coverage (legacy / filesystem SoT only).

    When model.units[].decision exists, evaluate_roles is authoritative (ADR-29)
    and this helper is not consulted. Kept for pre-model fixtures.

    A §7 line credits unit U iff:
      1. it assigns HARVEST|REDESIGN (not scaffold/deferral), and
      2. it names U (FQN preferred; path-anchored simple OK), and
      3. no *other* profile_unit is named on that same line.
    """
    fqn = u.get("legacy_fqn") or ""
    simple = _unit_simple(u)
    lp = (u.get("legacy_path") or "").replace("\\", "/")
    units = all_units if all_units is not None else [u]
    my_label = fqn or lp or simple or "?"

    for line in sec7.splitlines():
        if not _line_is_role_claim(line):
            continue
        mentions_me = False
        if fqn and re.search(r"\b" + re.escape(fqn) + r"\b", line):
            mentions_me = True
        elif simple and re.search(r"\b" + re.escape(simple) + r"\b", line):
            # Path-anchor when available (ADR-26 invariant 3).
            if lp and (lp in line or Path(lp).name in line):
                mentions_me = True
            elif not lp:
                mentions_me = True
            else:
                # Simple name without path is OK only as sole subject atom.
                mentions_me = True
        if not mentions_me:
            continue
        subjects = _units_mentioned_on_line(line, units)
        if subjects == [my_label] or (
            len(subjects) == 1 and subjects[0] == my_label
        ):
            return True
        # Sole-subject fallback when label forms differ but only this unit hits.
        if len(subjects) == 1:
            only = subjects[0]
            if only == my_label or only == fqn or only == simple or only == lp:
                return True
    return False


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
    # Score the *unit identity* (left of —/→), not rationale prose: a live FP
    # REDs REDESIGN SpringDataPetRepositoryImpl because the rationale said
    # "Not a MapStruct *MapperImpl" (O-RUBRICGENASSERTFP).
    _GEN_ARTIFACT_RE = re.compile(
        r"MapperImpl\b|generated-sources|/target/|\bbuild/|target/generated"
    )
    sec7_early = section_body(text, "class role")
    for line in sec7_early.splitlines():
        if not re.search(r"\b(HARVEST|REDESIGN)\b", line):
            continue
        subject = re.split(r"\s+[—–]\s+|\s+→\s+|\s+->\s+", line, maxsplit=1)[0]
        if _GEN_ARTIFACT_RE.search(subject):
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

        # ADR-21 G1/G2 — claim truth + prior-specimen vocabulary (need legacy).
        _check_claim_truth(sec7, sys.argv[2], problems)
        _check_prof_vocab(sec7, sys.argv[2], problems)

    # O-PROFDENSITY / ADR-26 / ADR-29 — coverage universe.
    # Prefer model.units[].decision (typed-decision SoT) when model exists.
    model_units = _load_profile_units(sys.argv[1])
    cover_items: list[str] = []
    unnamed: list[str] = []
    sot = "filesystem"
    cov_metric = COVERAGE_METRIC
    _authored_decisions = 0
    _evidence_miss_n = 0
    prof_path = Path(sys.argv[1]).resolve()
    root_guess = prof_path.parent.parent
    model_path = _find_model_path(sys.argv[1])
    if model_path and model_units is not None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from profile_roles import evaluate_roles  # type: ignore

        legacy_arg = sys.argv[2] if len(sys.argv) > 2 else None
        ev = evaluate_roles(root_guess, legacy=legacy_arg)
        sot = ev.get("sot") or "model-decision"
        cov_metric = ev.get("metric") or COVERAGE_METRIC_ROLES
        unnamed = list(ev.get("undecided") or [])
        cover_items = [
            (u.get("legacy_fqn") or u.get("legacy_path") or "?")
            for u in model_units
            if (u.get("legacy_fqn") or u.get("legacy_path") or "?") not in unnamed
        ]
        problems.extend(ev.get("problems") or [])
        # W4-450 / O-PROF1OF79STOP: keep authored vs credited visible on COVERAGE.
        _authored_decisions = int(ev.get("authored") or len(cover_items))
        _evidence_miss_n = len(ev.get("evidence_miss") or [])
    elif model_units is not None:
        sot = "model"
        for u in model_units:
            label = u.get("legacy_fqn") or u.get("legacy_path") or "?"
            if _unit_covered_in_sec7(sec7, u, model_units):
                cover_items.append(label)
            else:
                unnamed.append(label)
    elif src_classes:
        # Fixture / pre-model fallback — basename walk (legacy behaviour).
        for cls in src_classes:
            if re.search(r"\b" + re.escape(cls) + r"\b", text):
                cover_items.append(cls)
            else:
                unnamed.append(cls)

    if cover_items or unnamed:
        named = len(cover_items)
        total = named + len(unnamed)
        ratio = named / total if total else 1.0
        pct = int(round(ratio * 100))
        # Ratchet: typed-decision is a new universe — ignore prose floors.
        if sot == "model-decision":
            prev = _previous_accepted_ratio(
                sys.argv[1], expect_sot="model-decision"
            )
            best = _best_observed_ratio(
                sys.argv[1], expect_sot="model-decision"
            )
        else:
            prev = _previous_accepted_ratio(sys.argv[1], expect_sot=sot)
            best = _best_observed_ratio(sys.argv[1], expect_sot=sot)
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
        notes.append(f"sot={sot}")
        notes.append(f"metric={cov_metric}")
        if sot == "model-decision":
            # Credited = named; authored may be higher when evidence fails resolve.
            auth = _authored_decisions if _authored_decisions else named
            notes.append(f"authored={auth}")
            notes.append(f"evidence_miss={_evidence_miss_n}")
        note = " " + " ".join(notes)
        print(
            f"COVERAGE: {named}/{total} ({pct}%) "
            f"floor={floor_pct}%{note}"
        )
        for u in unnamed:
            print(f"UNNAMED: {u}")
        if sot in ("model", "model-decision", "roles") and unnamed:
            problems.append(
                f"RUBRIC:unnamed: {len(unnamed)}/{total} profile-units lack a "
                f"typed decision (model.units[].decision) — "
                f"fill profile-decisions.json for every UNNAMED: FQN"
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
        _note_best_observed(sys.argv[1], named, total, ratio, sot=sot)
        _write_model_coverage_prov(
            sys.argv[1], named, total, ratio, sot, is_best=True
        )
        coverage_snapshot = (named, total, ratio, sot)

    # O-PROFTCHARDPIN / W4-487 — target-soft checks TYPED decisions, not §7 text.
    # §7 hard-pin bullets are declared-policy rendering and must NOT satisfy this
    # gate (tautology). Each enabled migration.yaml flag must appear on at least
    # one model.units[].decision.target_contract (or seat-authored equivalent).
    DECISIVE = {
        "getIdempotent": (r"\b404\b|getIdempotent|404-on-missing", "404-on-missing"),
        "validateInput": (r"\b400\b|@Min|@Valid|problem.?detail|validateInput", "400/validation"),
        "mapErrors": (r"\b503\b|ExceptionMapper|mapErrors", "503/ExceptionMapper"),
        "threadSafeState": (r"ConcurrentHashMap|compute\(|threadSafeState", "ConcurrentHashMap/compute"),
        "cacheRefreshGuard": (
            r"no clear|clear.?on.?miss|refresh.?guard|\bTTL\b|\b60\s*s|"
            r"time.?stamp guard|@Cacheable|\bCacheable\b|quarkus.?cache|CacheResult|"
            r"cacheRefreshGuard",
            "refresh-guard/@Cacheable",
        ),
        "normalizeBeforeDerive": (
            r"normalize.{0,20}before|dedup.{0,20}before|"
            r"before (?:deriv|aggregat|comput|total|pric|sum)|normalizeBeforeDerive",
            "normalize-before-derive",
        ),
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
        # Collect typed target_contract blobs from model SoT (not §7 markdown).
        typed_blobs: list[str] = []
        if model_path and model_units is not None:
            for u in model_units:
                d = u.get("decision") if isinstance(u.get("decision"), dict) else None
                if not d:
                    continue
                tcv = d.get("target_contract")
                if tcv is None:
                    continue
                if isinstance(tcv, dict):
                    typed_blobs.append(json.dumps(tcv))
                else:
                    typed_blobs.append(str(tcv))
        typed_join = "\n".join(typed_blobs)
        for flag, (tok, label) in DECISIVE.items():
            if not re.search(rf"^\s*{flag}:\s*true", tc.group(1), re.M):
                continue
            if typed_blobs and re.search(tok, typed_join, re.I):
                continue
            problems.append(
                f"RUBRIC:target-soft: targetContract.{flag} is true but no typed "
                f"decision.target_contract decides it ({label}) — attach on REDESIGN "
                f"contract-surface units (O-PROFTCHARDPIN); §7 hard-pins alone do not count"
            )

    # O-PROFHARVESTSPRING / W4-491 — WARN only (not RED): HARVEST whose legacy
    # file imports org.springframework.* excluding the model's own FQN root.
    # Own-root derived from shared prefix — never hardcode specimen package.
    if model_units:
        fqns = [
            (u.get("legacy_fqn") or u.get("key") or "")
            for u in model_units
            if isinstance(u.get("decision"), dict) and u["decision"].get("role")
        ]
        fqns = [f for f in fqns if f]
        if fqns:
            parts = [f.split(".") for f in fqns]
            own = ".".join(
                p
                for i, p in enumerate(parts[0])
                if all(len(q) > i and q[i] == p for q in parts)
            )
            legacy_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
            for u in model_units:
                d = u.get("decision") if isinstance(u.get("decision"), dict) else None
                if not d or str(d.get("role") or "").upper() != "HARVEST":
                    continue
                rel = u.get("legacy_path") or ""
                src = legacy_root / rel
                if not src.is_file():
                    src = Path(rel)
                if not src.is_file():
                    continue
                try:
                    text = src.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                imps = re.findall(
                    r"^import\s+(org\.springframework\.[\w.]+);", text, re.M
                )
                ext = [i for i in imps if own and not i.startswith(own)]
                if ext:
                    fqn = u.get("legacy_fqn") or u.get("key") or "?"
                    print(
                        f"WARN:harvest-spring: {fqn} HARVEST imports non-own-root "
                        f"Spring ({', '.join(sorted(set(ext))[:3])}) — review "
                        f"(O-PROFHARVESTSPRING; own_root={own})"
                    )

    if problems:
        print("\n".join(problems))
        return 1
    print(f"PROFILE OK: {len(REQUIRED)} sections present, cited, plan-free")
    # G3 — persist accepted coverage so the next PROFILE cannot regress below it.
    if coverage_snapshot is not None:
        n, t, r, snap_sot = coverage_snapshot
        _write_accepted_coverage(sys.argv[1], n, t, r, sot=snap_sot)
        _write_model_coverage_prov(
            sys.argv[1], n, t, r, snap_sot, is_accepted=True, is_best=True
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
