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
        "acceptance",
        "oracle",
        "port",
        "findings",
    }
)

# O-DERIVEDFPDEF — single definition id for freeze/C1 tuples.
# Bump only when DERIVED_FIELDS membership or canonicalization changes.
DERIVED_FP_DEFINITION_ID = "derived-fields-v1"

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
# Legacy prose headings still accepted by plan-lint non-typed path.
LEGACY_TASK_ID_ATOM = r"T[-A-Za-z0-9]*\d+[A-Za-z]*"
LEGACY_TASK_ID_RE = re.compile(rf"^{LEGACY_TASK_ID_ATOM}$")

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
}

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


def evidence_kinds_for_acceptance(acceptance: Iterable[str]) -> list[str]:
    """Map acceptance clauses to evidence kinds for packet closure."""
    out: list[str] = []
    for a in acceptance or []:
        a = (a or "").strip()
        if not a:
            continue
        kind = ACCEPTANCE_EVIDENCE.get(a)
        if kind is None:
            if "staging" in a.lower() or "byte-fidelity" in a.lower():
                kind = "staging_fact"
            elif a.startswith("contract:"):
                kind = "target_contract"
            else:
                kind = "derived"
        if kind not in out:
            out.append(kind)
    return out


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
