#!/usr/bin/env python3
"""ADR-41 Move 1 — single task-contract schema for M3 typed tasks.

Callers (assign_tasks / plan-lint / render / packet / JUDGMENT upsert) MUST
import from this module. Success criterion: a second incompatible definition
cannot compile — duplicate literals in callers are instrument-refused.

Not a rewrite of plan-lint: instruments keep testing behaviour *through*
these helpers.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Optional

# --- field ownership (C1 / goal_source split) ---------------------------------

DERIVED_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "sid",
        "seq",
        "unit_keys",
        "kind",
        "scc_id",
        "owns",
        "title",
        "class",
        "shape",
        "role",
        "preconditions",
        "acceptance",
        "owning_phase",
        "oracle",
        "port",
        "findings",
    }
)

# O-DERIVEDFPDEF — single definition id for freeze/C1 tuples.
# Bump only when DERIVED_FIELDS membership or canonicalization changes.
DERIVED_FP_DEFINITION_ID = "derived-fields-v2"  # O-ADR45-S1: +preconditions +owning_phase

SEAT_FIELDS: frozenset[str] = frozenset({"goal", "plan", "risk", "filled", "goal_source"})


def derived_fingerprint(model: dict) -> dict[str, Any]:
    """Canonical C1 fingerprint over DERIVED_FIELDS (O-DERIVEDFPDEF).

    Returns ``{definition_id, n, DERIVED_FP}``. Reviewers and capture scripts
    must call this — do not re-implement the field set ad hoc.
    """
    tasks = list(model.get("tasks") or [])
    rows: list[dict[str, Any]] = []
    for t in sorted(
        tasks,
        key=lambda x: (
            str(x.get("sid") or ""),
            int(x.get("seq") or 0),
            str(x.get("id") or ""),
        ),
    ):
        row: dict[str, Any] = {}
        for k in sorted(DERIVED_FIELDS):
            row[k] = t.get(k)
        rows.append(row)
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "definition_id": DERIVED_FP_DEFINITION_ID,
        "n": len(rows),
        "DERIVED_FP": hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16],
    }

# --- vocabularies ------------------------------------------------------------

TASK_CLASSES: frozenset[str] = frozenset({"rewrite", "infer"})
ROLES: frozenset[str] = frozenset({"HARVEST", "REDESIGN", "UNDECIDED"})

# Atomic shapes + SCC batch form (O-SCCHARVESTSHAPE / O-SHAPEDECL).
SHAPE_ATOMS: frozenset[str] = frozenset(
    {"create", "modify", "remove", "structure", "verify"}
)
SHAPE_ATOM_RE = re.compile(
    r"^(?:create|modify|remove|structure|verify|batch:SCC-\d+)$"
)
# For plan-lint markdown Shape lines (same atoms). Callers MUST interpolate
# this — do not re-type the alternation (ADR-41 Move 1 falsifier).
SHAPE_LINE_ATOM = r"create|modify|remove|structure|verify|batch:SCC-\d+"
# Human-facing lint messages (N not \\d+).
SHAPE_DISPLAY = "create|modify|remove|structure|verify|batch:SCC-N"
# oracle_derive historically accepted a non-plan-lint "harvest" shape token.
SHAPE_LINE_ATOM_ORACLE = SHAPE_LINE_ATOM + r"|harvest"

# Typed composite ids: S0N-T-NNN-Name (letters after digits are allowed).
TASK_ID_RE = re.compile(r"^(S\d+)-T-(\d{3})(?:-([A-Za-z0-9]+))?$")
TYPED_TASK_ID_ATOM = r"S\d+-T-\d{3}(?:-[A-Za-z0-9]+)?"
# O-M4TCHEADING: god/cover characterization emits S0N-TC-<Name> (not T-NNN).
# Must parse in M4 heading order or supervisor skips every char task → convert
# runs first → O-T6d need-src-test / false MiniMax (S02-T-001 live).
TYPED_CHAR_TASK_ID_ATOM = r"S\d+-TC-[A-Za-z0-9]+"
TYPED_CHAR_TASK_ID_RE = re.compile(rf"^{TYPED_CHAR_TASK_ID_ATOM}$")
# Legacy prose headings still accepted by plan-lint non-typed path.
LEGACY_TASK_ID_ATOM = r"T[-A-Za-z0-9]*\d+[A-Za-z]*"
LEGACY_TASK_ID_RE = re.compile(rf"^{LEGACY_TASK_ID_ATOM}$")
# Heading / M4 parse atom — typed char + typed convert + legacy (O-M4COMPOSITE).
# TC alternation MUST precede T-NNN (prefix overlap). Keep in sync with
# supervisor.sh HEADING_TASK_ID_ATOM + outer-loop TASK_ID_ERE.
HEADING_TASK_ID_ATOM = (
    rf"(?:{TYPED_CHAR_TASK_ID_ATOM}|{TYPED_TASK_ID_ATOM}|{LEGACY_TASK_ID_ATOM})"
)
HEADING_TASK_ID_RE = re.compile(rf"^{HEADING_TASK_ID_ATOM}$")
# O-T6dTCHEADING: single SoT for markdown task headings (mechan-match, ESCW,
# already-complete, seat-budget, findings scope, …). Hardcoding S0N-T-NNN-only
# made mechan-match print no-task for S0N-TC-* → false MiniMax after Qwen tip.
HEADING_LINE_RE = re.compile(
    rf"^#{{2,6}}\s+({HEADING_TASK_ID_ATOM})\s*:\s*(.+)$",
    re.M,
)
# Commit-subject / skip-line prefix (no markdown hashes).
HEADING_SUBJECT_RE = re.compile(
    rf"^({HEADING_TASK_ID_ATOM})\s*:",
)


def iter_task_headings(text: str):
    """Yield regex matches for ``#### S0N-TC-*|S0N-T-*|T-* : title`` lines."""
    return HEADING_LINE_RE.finditer(text or "")


def task_heading_parts(text: str, tid: str) -> tuple[str, str]:
    """Return ``(title, body)`` for ``tid``, or ``("", "")`` if missing."""
    heads = list(iter_task_headings(text))
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        title = m.group(2).strip()
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        return title, text[start:end]
    return "", ""

# Hedge vocabulary — one owner for plan-lint LINT:hedge + upsert F-hedge.
HEDGE_RE = re.compile(
    r"\b(if needed|if necessary|as appropriate|as needed|"
    r"consider (?:using|adding)|optionally)\b",
    re.I,
)

# Move 2 — acceptance → evidence kinds (bounded packet closure).
ACCEPTANCE_EVIDENCE: dict[str, str] = {
    "byte-fidelity vs migration/staging": "staging_fact",
    "byte-fidelity vs migration/staging (LOC + serialVersionUID)": "staging_fact",
    "byte-fidelity vs migration/staging or generated-sources (DTO types)": "staging_fact",
    "package rename only; no behavior change": "derived",
    "implements typed target_contract for this unit": "target_contract",
    "REDESIGN no-flags-apply (M1 affirmative)": "target_contract",
    # O-ADR45-S1 amendment (W4-677): verify-absent / boot clauses
    "no @SpringBootApplication in src/main/java": "absence-in-tree",
    "Quarkus application starts without a Spring Boot main class": "boot-succeeds",
    "characterization pins legacy contract before convert": "characterization",
}

# O-ADR45-S1 / F-acceptance-is-verifiable — these belong in preconditions[] or
# owning_phase, never in acceptance[].
PRECONDITION_SHAPED_ACCEPTANCE_RE = re.compile(
    r"(?i)(role\s+undecided|refuse\s+ship\s+until\s+M1|"
    r"without\s+target_contract\s*—\s*complete\s+at\s+M1|"
    r"complete\s+at\s+M1)",
)

# Contract-derived patterns (no specimen names) for clauses with variable text.
ACCEPTANCE_EVIDENCE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)pins\s+legacy\s+contract\s+before\s+convert"), "characterization"),
    (re.compile(r"(?i)^no\s+@?\w+\s+in\s+src/"), "absence-in-tree"),
    (re.compile(r"(?i)application\s+starts\s+without"), "boot-succeeds"),
    (re.compile(r"(?i)^contract:"), "target_contract"),
    (re.compile(r"(?i)byte-fidelity|staging"), "staging_fact"),
    (re.compile(r"(?i)package\s+rename\s+only"), "derived"),
    (
        re.compile(
            r"(?i)ValidatorTests|characterization|layer\s+contract\s+for\s+ship"
        ),
        "characterization",
    ),
]

# Bounded staging projection (ADR-41 Move 2 — selective, not a tree dump).
MAX_STAGING_FACTS = 8
MAX_STAGING_FACT_CHARS = 240
MAX_STAGING_SECTION_CHARS = 3500


def is_valid_shape(shape: str) -> bool:
    return bool(SHAPE_ATOM_RE.match((shape or "").strip()))


def is_valid_class(cls: str) -> bool:
    return (cls or "").strip().lower() in TASK_CLASSES


def class_for_role(role: str) -> str:
    r = (role or "").strip().upper()
    if r == "HARVEST":
        return "rewrite"
    if r == "REDESIGN":
        return "infer"
    return "rewrite"


def port_for_role(role: str) -> Optional[str]:
    """O-PORTDERIVE — REDESIGN → Port=reimplement by default; HARVEST → rename."""
    r = (role or "").strip().upper()
    if r == "HARVEST":
        return "rename"
    if r == "REDESIGN":
        return "reimplement"
    return None


def make_task_id(sid: str, seq: int, slug: str) -> str:
    """Harness-owned typed id — sole constructor for assign_tasks."""
    s = re.sub(r"[^A-Za-z0-9]+", "", slug or "unit")[:48] or "unit"
    return f"{sid}-T-{int(seq):03d}-{s}"


def task_num(tid: str) -> int:
    """Numeric T-NNN for ordering (typed S0N-T-NNN-Name and legacy T-NNN*)."""
    m = re.search(r"(?:^|-)T-(\d+)", tid or "")
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)$", tid or "")
    return int(m.group(1)) if m else 0


def find_hedge(text: str) -> Optional[re.Match[str]]:
    return HEDGE_RE.search(text or "")


def is_precondition_shaped_acceptance(clause: str) -> bool:
    """True when a clause is routing/precondition prose, not artifact evidence."""
    return bool(PRECONDITION_SHAPED_ACCEPTANCE_RE.search(clause or ""))


def clause_evidence_kind(clause: str, *, task_kind: str = "") -> Optional[str]:
    """Map one acceptance clause to an evidence kind, or None if unmatched.

    O-ADR45-S1 amendment (W4-677): ``kind=characterize`` tasks classify as
    ``characterization`` from the typed kind field — never from prose alone.
    """
    a = (clause or "").strip()
    if not a or is_precondition_shaped_acceptance(a):
        return None
    tk = (task_kind or "").strip().lower()
    if tk == "characterize":
        return "characterization"
    kind = ACCEPTANCE_EVIDENCE.get(a)
    if kind is not None:
        return kind
    for pat, mapped in ACCEPTANCE_EVIDENCE_PATTERNS:
        if pat.search(a):
            return mapped
    return None


def evidence_kinds_for_acceptance(
    acceptance: Iterable[str], *, task_kind: str = ""
) -> list[str]:
    """Map acceptance clauses to evidence kinds for packet closure.

    O-ADR45-S1: precondition-shaped clauses are skipped. Unmatched verifiable
    clauses no longer silently become ``derived`` — callers that need a kind
    must use ``clause_evidence_kind`` / corpus instrument (fail-closed).
    """
    out: list[str] = []
    for a in acceptance or []:
        kind = clause_evidence_kind(a, task_kind=task_kind)
        if kind and kind not in out:
            out.append(kind)
    return out


def unmatched_acceptance_clauses(tasks: Iterable[dict]) -> list[tuple[str, str]]:
    """Return [(task_id, clause), ...] with no evidence kind (corpus instrument)."""
    bad: list[tuple[str, str]] = []
    for t in tasks or []:
        tid = str(t.get("id") or "?")
        tk = str(t.get("kind") or "")
        for a in t.get("acceptance") or []:
            a = str(a).strip()
            if not a or is_precondition_shaped_acceptance(a):
                continue
            if clause_evidence_kind(a, task_kind=tk) is None:
                bad.append((tid, a))
    return bad


def staging_fact_lines(
    root: Path,
    legacy_paths: Iterable[str],
    *,
    max_facts: int = MAX_STAGING_FACTS,
    max_fact_chars: int = MAX_STAGING_FACT_CHARS,
    max_section_chars: int = MAX_STAGING_SECTION_CHARS,
) -> list[str]:
    """Bounded staging facts for HARVEST acceptance (F-staging-projected).

    Emits path / LOC / package / serialVersionUID when present — never the
    full file body. Selective closure for ADR-41 Move 2.
    """
    lines: list[str] = [
        "STAGING FACTS (harness-projected — do NOT Read migration/staging):",
    ]
    n = 0
    budget = max_section_chars
    for lp in legacy_paths:
        if n >= max_facts or budget <= 0:
            break
        rel = (lp or "").replace("\\", "/").lstrip("/")
        rel = re.sub(r"^projects/legacy/", "", rel)
        if not rel.endswith(".java"):
            continue
        staged = root / "migration" / "staging" / rel
        if not staged.is_file():
            # Also try path as already under migration/staging
            alt = root / rel if rel.startswith("migration/staging/") else None
            if alt and alt.is_file():
                staged = alt
            else:
                continue
        try:
            text = staged.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        loc = text.count("\n") + (0 if text.endswith("\n") else 1 if text else 0)
        pkg_m = re.search(r"(?m)^package\s+([\w.]+)\s*;", text)
        pkg = pkg_m.group(1) if pkg_m else "-"
        suid_m = re.search(
            r"serialVersionUID\s*=\s*(-?\d+)L?",
            text,
        )
        suid = suid_m.group(1) if suid_m else "-"
        try:
            show = str(staged.relative_to(root))
        except ValueError:
            show = str(staged)
        fact = f"  - {show} LOC={loc} package={pkg} serialVersionUID={suid}"
        if len(fact) > max_fact_chars:
            fact = fact[: max_fact_chars - 1] + "…"
        if len(fact) + 1 > budget:
            break
        lines.append(fact)
        budget -= len(fact) + 1
        n += 1
    if n == 0:
        lines.append("  - (no staging .java resolved for this story's HARVEST owns)")
    lines.append(f"provenance: staging_facts={n} cap={max_facts}")
    return lines


# --- ADR-42: readiness is derived from the typed store (gate ≠ scheduler) -----

STORY_STATES: frozenset[str] = frozenset({"UNSPECIFIED", "SPECIFIED"})


def story_state(model: dict, sid: str) -> str:
    """ADR-42 — ``UNSPECIFIED`` | ``SPECIFIED`` from ``model.tasks[]``.

    Readiness is a function of the typed store, not something discovered by
    running plan-lint. Outer-loop may promote SPECIFIED → GREEN only after a
    single plan-lint invocation (quality gate, not scheduler).
    """
    want = str(sid or "").strip()
    tasks = [
        t
        for t in (model.get("tasks") or [])
        if str(t.get("sid") or "").strip() == want
    ]
    if not tasks:
        return "UNSPECIFIED"
    if any(not t.get("filled") for t in tasks):
        return "UNSPECIFIED"
    return "SPECIFIED"


# --- ADR-39 / O-SCOPESOT: story membership scope is typed — roadmap is VIEW ---

def story_scope(model: dict, sid: str) -> list[str]:
    """Legacy paths owned by ``sid`` in ``model.stories[].units`` (ADR-39).

    Sole enforcement input for ``--story-scope`` / O-M3TASKSCOPE. Roadmap
    ``- scope:`` prose is a rendered VIEW of this list — never a second
    membership store (W4-617). Returns sorted unique ``legacy_path`` values.
    """
    want = str(sid or "").strip()
    if not want:
        return []
    units_by_key: dict[str, dict[str, Any]] = {}
    for u in model.get("units") or []:
        if not isinstance(u, dict):
            continue
        key = str(u.get("key") or u.get("legacy_fqn") or "").strip()
        if key:
            units_by_key[key] = u
    paths: list[str] = []
    seen: set[str] = set()
    for st in model.get("stories") or []:
        if not isinstance(st, dict):
            continue
        if str(st.get("id") or "").strip() != want:
            continue
        for raw in st.get("units") or []:
            key = raw if isinstance(raw, str) else str(
                (raw or {}).get("key") or (raw or {}).get("legacy_fqn") or ""
            ).strip()
            if not key:
                continue
            u = units_by_key.get(key) or {}
            lp = str(u.get("legacy_path") or "").replace("\\", "/").strip()
            if not lp or lp in seen:
                continue
            seen.add(lp)
            paths.append(lp)
        break
    return sorted(paths)


def story_scope_csv(model: dict, sid: str) -> str:
    """Comma-space joined ``story_scope`` for outer-loop / plan-lint CLI."""
    return ", ".join(story_scope(model, sid))


def story_findings(model: dict, sid: str) -> list[str]:
    """Finding ids owned by ``sid`` (ADR-39 findings SoT / O-FINDINGSOT).

    Sole store: ``model.stories[].findings`` after ``assign_stories`` K1
    partition (earliest story wins). Do **not** re-union ``unit.findings`` —
    that reintroduces cross-story dual-own (same finding on units in S02+S04).
    Roadmap ``- findings:`` prose is a VIEW — never O-M3ALL-K1 enforcement.
    """
    want = str(sid or "").strip()
    if not want:
        return []
    out: set[str] = set()
    for st in model.get("stories") or []:
        if not isinstance(st, dict):
            continue
        if str(st.get("id") or "").strip() != want:
            continue
        for fid in st.get("findings") or []:
            if fid:
                out.add(str(fid).strip())
        break
    return sorted(out)


def story_findings_csv(model: dict, sid: str) -> str:
    return ", ".join(story_findings(model, sid))


def _cli(argv: Optional[list[str]] = None) -> int:
    """Minimal CLI: ``story-scope|story-findings --root DIR --sid S0N``."""
    import argparse
    import sys

    # Late import — model.py imports this module; avoid cycle at import time.
    ap = argparse.ArgumentParser(description="task_contract CLI (ADR-39/41/42)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_scope = sub.add_parser(
        "story-scope",
        help="print typed story scope CSV (enforcement SoT; roadmap is VIEW)",
    )
    p_scope.add_argument("--root", default=".", help="migration workspace root")
    p_scope.add_argument("--sid", required=True, help="story id (S01…)")
    p_find = sub.add_parser(
        "story-findings",
        help="print typed story findings CSV (K1 SoT; roadmap is VIEW)",
    )
    p_find.add_argument("--root", default=".")
    p_find.add_argument("--sid", required=True)
    args = ap.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model import load as model_load  # type: ignore

    root = Path(args.root).resolve()
    model = model_load(root)
    if args.cmd == "story-scope":
        csv = story_scope_csv(model, args.sid)
        if not csv:
            print(
                f"O-SCOPESOT: no typed scope for {args.sid} "
                f"(model.stories[] missing or empty units)",
                file=sys.stderr,
            )
            return 2
        print(csv)
        return 0
    if args.cmd == "story-findings":
        print(story_findings_csv(model, args.sid))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
