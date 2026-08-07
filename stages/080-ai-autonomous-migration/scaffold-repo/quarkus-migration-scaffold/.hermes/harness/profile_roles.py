#!/usr/bin/env python3
"""ADR-29 — typed profile decisions (SoT). Supersedes prose harvest (ADR-30).

Architecture (closes the §7 round-trip):

  migration/model.json          → units[].decision  (SoT)
  migration/profile-decisions.json → seat write surface (merged into model)
  migration/architecture-profile.md §7 → RENDERED VIEW only (never parsed for role)

A decision is:

  {
    "role": "HARVEST" | "REDESIGN",
    "rationale": "...",
    "evidence": {"path": "src/.../X.java", "line": 47, "token": "@Entity"},
    "target_contract": { ... }   # optional; hard when targetContract flags apply
  }

Coverage = count(profile_units with a typed decision whose evidence resolves
at path:line:token AND is ∈ the ADR-31 projected anchor set). Diversity is a
consequence of resolving anchors — not a prose heuristic. Grouped bullets /
deferral scaffolds / identical templates / invented line numbers are
unrepresentable as decisions (F-anchor-membership).

Commands:
  profile_roles.py init --root DIR
  profile_roles.py apply --root DIR [--decisions PATH]
  profile_roles.py upsert --root DIR --fqn FQN --role R --rationale … --path P --line N --token T
  profile_roles.py upsert --root DIR --json-file PATH   # ≤ UPSERT_MAX_ROWS rows
  profile_roles.py render --root DIR [--profile PATH]
  profile_roles.py lint --root DIR [--legacy PATH]
  profile_roles.py harvest …   # REMOVED — exits 2 (F-render-oneway)

O-DECISIONWRITEDROP / ADR-31: seats must use **upsert** (one or few rows per
tool call). Rewriting the entire profile-decisions.json in one patch is the
failure mode that drops Hermes mid tool-call. The harness owns persistence;
the seat supplies small deltas.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

SCHEMA = "profile-decisions/v1"
METRIC = "typed-decision"
ROLES = frozenset({"HARVEST", "REDESIGN"})
# Hard cap on upsert --json-file — keeps each tool-call payload small.
UPSERT_MAX_ROWS = 3

# Build-owned — never a class-role decision (O-RUBRICGENASSERT).
_GENASSERT = re.compile(
    r"MapperImpl\b|generated-sources|/target/generated|target/generated"
)


def _load_model_units(root: Path) -> list[dict]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model import load, profile_units  # type: ignore

    return profile_units(load(root))


def _load_model(root: Path) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model import load  # type: ignore

    return load(root)


def _save_model(root: Path, model: dict) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model import save  # type: ignore

    save(root, model)


def decisions_path(root: Path) -> Path:
    return root / "migration" / "profile-decisions.json"


def roles_path_legacy(root: Path) -> Path:
    """ADR-30 filename — forbidden residue (O-ADR30ALIASDEL). Never a read SoT."""
    return root / "migration" / "profile-roles.json"


def _refuse_adr30_alias(root: Path) -> Optional[str]:
    """Fail-closed if the superseded profile-roles.json sidecar is present.

    (O-ADR30ALIASDEL — bank id; keep out of user-facing refuse text.)
    """
    legacy = roles_path_legacy(root)
    if legacy.is_file():
        return (
            "REFUSE migration/profile-roles.json — superseded. "
            "Use migration/profile-decisions.json + "
            "model.units[].decision only (delete the old sidecar)."
        )
    return None


def _sec7_span(text: str) -> tuple[int, int]:
    m = re.search(r"^(#{2,6})[ \t]+.*class role.*$", text, re.M | re.I)
    if not m:
        return -1, -1
    level = len(m.group(1))
    start = m.end()
    rest = text[start:]
    nxt = re.search(r"^#{1," + str(level) + r"}[ \t]", rest, re.M)
    end = start + (nxt.start() if nxt else len(rest))
    return start, end


def normalize_evidence(raw: Any) -> Optional[dict[str, Any]]:
    """Accept object or 'path:line' / 'path:line:token' string → structured."""
    if isinstance(raw, dict):
        path = (raw.get("path") or "").strip()
        try:
            line = int(raw.get("line"))
        except (TypeError, ValueError):
            return None
        token = (raw.get("token") or "").strip()
        if not path or line < 1 or not token:
            return None
        return {"path": path, "line": line, "token": token}
    if isinstance(raw, str):
        s = raw.strip()
        # path:line:token  or  path:line (token missing → invalid for ADR-29)
        m = re.match(
            r"^(?P<path>(?:src/)?[\w./\-]+\.java):(?P<line>\d+)(?::(?P<token>.+))?$",
            s,
        )
        if not m:
            return None
        tok = (m.group("token") or "").strip()
        if not tok:
            return None
        return {
            "path": m.group("path"),
            "line": int(m.group("line")),
            "token": tok,
        }
    return None


def evidence_resolves(legacy_root: Path, evidence: dict[str, Any]) -> tuple[bool, str]:
    """F-evidence-resolves — token must occur on the cited line (G1 line-level)."""
    path = evidence.get("path") or ""
    line = int(evidence.get("line") or 0)
    token = (evidence.get("token") or "").strip()
    if not path or line < 1 or not token:
        return False, "evidence incomplete (need path, line≥1, token)"
    # Resolve under legacy root (accept path with or without legacy/ prefix).
    candidates = [
        legacy_root / path,
        legacy_root / "src" / path[4:] if path.startswith("src/") else None,
        Path(path) if Path(path).is_file() else None,
    ]
    # Also walk by basename if exact miss (same as G1 file resolve).
    fp: Optional[Path] = None
    for c in candidates:
        if c is not None and c.is_file():
            fp = c
            break
    if fp is None:
        base = Path(path).name
        if legacy_root.is_dir():
            for p in legacy_root.rglob(base):
                if "target" in p.parts or "build" in p.parts:
                    continue
                if p.is_file():
                    fp = p
                    break
    # O-PROFDTOANCHOR / O-PROFDTOLEGACYSRC: OpenAPI *Dto.java often lives only
    # under target/generated-sources/openapi. When callers pass …/legacy/src
    # (profile-rubric argv), codegen output is under the parent …/legacy/target.
    if fp is None:
        base = Path(path).name
        if base.lower().endswith("dto.java"):
            search_roots = [legacy_root] if legacy_root.is_dir() else []
            if legacy_root.name == "src" and legacy_root.parent.is_dir():
                search_roots.append(legacy_root.parent)
            for root in search_roots:
                if not root.is_dir():
                    continue
                for p in root.rglob(base):
                    if not p.is_file():
                        continue
                    parts_l = [x.lower() for x in p.parts]
                    if "generated-sources" in parts_l and (
                        "openapi" in parts_l or "swagger" in parts_l
                    ):
                        fp = p
                        break
                if fp is not None:
                    break
    if fp is None:
        return False, f"file not found for path={path}"
    try:
        lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return False, f"read failed: {e}"
    if line > len(lines):
        return False, f"line {line} past EOF ({len(lines)} lines) in {fp.name}"
    body = lines[line - 1]
    # Token match: exact substring; @Anno matches annotation forms.
    plain = token.lstrip("@")
    if token in body or plain in body:
        return True, "ok"
    # Case-insensitive fallback for package/import segments.
    if token.lower() in body.lower() or plain.lower() in body.lower():
        return True, "ok"
    return False, f"token {token!r} absent from {fp.name}:{line}"


def _decision_complete(d: Any) -> bool:
    if not isinstance(d, dict):
        return False
    if d.get("role") not in ROLES:
        return False
    if not (d.get("rationale") or "").strip():
        return False
    return normalize_evidence(d.get("evidence")) is not None


def _is_genassert_unit(u: dict) -> bool:
    blob = f"{u.get('legacy_fqn') or ''} {u.get('legacy_path') or ''}"
    return bool(_GENASSERT.search(blob))


def init_roles(root: Path) -> int:
    """Open typed decision slots on model + seat write surface (all undecided)."""
    model = _load_model(root)
    units = _load_model_units(root)
    by_fqn = {(u.get("legacy_fqn") or u.get("key")): u for u in model.get("units") or []}
    opened = 0
    for u in units:
        fqn = u.get("legacy_fqn") or u.get("key")
        mu = by_fqn.get(fqn)
        if mu is None:
            continue
        if _is_genassert_unit(mu):
            continue
        # Preserve already-decided rows across re-init.
        if _decision_complete(mu.get("decision")):
            continue
        if mu.get("decision") is None or not isinstance(mu.get("decision"), dict):
            mu["decision"] = None
            opened += 1
    _save_model(root, model)

    # Seat write surface — checklist of open units (null role).
    doc_units = []
    for u in units:
        if _is_genassert_unit(u):
            continue
        fqn = u.get("legacy_fqn") or u.get("key") or "?"
        mu = by_fqn.get(fqn) or u
        d = mu.get("decision") if isinstance(mu.get("decision"), dict) else None
        if _decision_complete(d):
            doc_units.append(
                {
                    "legacy_fqn": fqn,
                    "legacy_path": u.get("legacy_path") or "",
                    "role": d["role"],
                    "rationale": d.get("rationale") or "",
                    "evidence": normalize_evidence(d.get("evidence")),
                    "target_contract": d.get("target_contract"),
                }
            )
        else:
            doc_units.append(
                {
                    "legacy_fqn": fqn,
                    "legacy_path": u.get("legacy_path") or "",
                    "role": None,
                    "rationale": "",
                    "evidence": None,
                    "target_contract": None,
                }
            )
    doc = {"schema": SCHEMA, "metric": METRIC, "units": doc_units}
    path = decisions_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    # O-ADR30ALIASDEL: delete superseded sidecar so two stores cannot recur.
    legacy = roles_path_legacy(root)
    if legacy.is_file():
        legacy.unlink()
        print(f"O-ADR30ALIASDEL: removed stale {legacy.name}")
    decided = sum(1 for r in doc_units if r.get("role") in ROLES)
    print(
        f"O-ADR29 init: {len(doc_units)} units "
        f"({decided} decided, {len(doc_units) - decided} open) → "
        f"model.units[].decision + {path}"
    )
    return 0


def _legacy_root_for(root: Path, legacy: Optional[str] = None) -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from profile_anchors import resolve_legacy_root  # type: ignore

    return resolve_legacy_root(root, legacy)


def _anchors_for(root: Path, unit: dict, legacy: Optional[str] = None) -> list[dict]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from profile_anchors import anchors_for_unit  # type: ignore

    return anchors_for_unit(root, unit, legacy=legacy)


def _member_or_refuse(
    root: Path,
    unit: dict,
    ev: dict[str, Any],
    *,
    legacy: Optional[str] = None,
    sink: Optional[list[str]] = None,
) -> bool:
    """ADR-31 F-anchor-membership — evidence must be ∈ projected set."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from profile_anchors import evidence_in_anchor_set  # type: ignore

    anchors = _anchors_for(root, unit, legacy=legacy)
    if evidence_in_anchor_set(ev, anchors):
        return True
    fqn = unit.get("legacy_fqn") or unit.get("key") or "?"
    msg = (
        f"O-ADR31: REFUSE {fqn} evidence {ev.get('path')}:{ev.get('line')}:"
        f"{ev.get('token')!r} — not in projected anchor set "
        f"(F-anchor-membership; SELECT from DERIVED FACTS anchors)"
    )
    print(msg, file=sys.stderr)
    if sink is not None:
        sink.append(msg)
    return False


def apply_decisions(
    root: Path,
    decisions_file: Optional[str] = None,
    *,
    legacy: Optional[str] = None,
) -> int:
    """Merge seat JSON into model.units[].decision (SoT). Never reads §7.

    ADR-31: refuses evidence not in the unit's projected anchor set
    (F-anchor-membership) — invention of path:line:token is unrepresentable.
    """
    refuse = _refuse_adr30_alias(root)
    if refuse:
        print(refuse, file=sys.stderr)
        return 2
    src = Path(decisions_file) if decisions_file else decisions_path(root)
    model = _load_model(root)
    by_fqn = {
        (u.get("legacy_fqn") or u.get("key")): u for u in model.get("units") or []
    }
    applied = 0
    refused = 0
    if src.is_file():
        try:
            doc = json.loads(src.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"O-ADR29 apply: cannot read {src}: {e}", file=sys.stderr)
            return 1
        for row in doc.get("units") or []:
            fqn = row.get("legacy_fqn") or row.get("key")
            if not fqn or fqn not in by_fqn:
                continue
            mu = by_fqn[fqn]
            if _is_genassert_unit(mu):
                mu["decision"] = None
                continue
            role = row.get("role")
            if role not in ROLES:
                # Explicit null / open — clear decision.
                if role is None or role == "":
                    mu["decision"] = None
                continue
            ev = normalize_evidence(row.get("evidence"))
            rationale = (row.get("rationale") or row.get("claim") or "").strip()
            if not ev or not rationale:
                mu["decision"] = None
                continue
            if not _member_or_refuse(root, mu, ev, legacy=legacy):
                mu["decision"] = None
                refused += 1
                continue
            dec: dict[str, Any] = {
                "role": role,
                "rationale": rationale,
                "evidence": ev,
            }
            if row.get("target_contract") is not None:
                dec["target_contract"] = row["target_contract"]
            mu["decision"] = dec
            applied += 1
    # Also accept decisions already written directly on model.json by the seat.
    for u in model.get("units") or []:
        d = u.get("decision")
        if not isinstance(d, dict):
            continue
        if d.get("role") not in ROLES:
            u["decision"] = None
            continue
        ev = normalize_evidence(d.get("evidence"))
        rationale = (d.get("rationale") or d.get("claim") or "").strip()
        if not ev or not rationale or _is_genassert_unit(u):
            u["decision"] = None
            continue
        if not _member_or_refuse(root, u, ev, legacy=legacy):
            u["decision"] = None
            refused += 1
            continue
        u["decision"] = {
            "role": d["role"],
            "rationale": rationale,
            "evidence": ev,
            **(
                {"target_contract": d["target_contract"]}
                if d.get("target_contract") is not None
                else {}
            ),
        }
    _save_model(root, model)
    # Refresh seat surface from model SoT.
    _sync_decisions_file(root, model)
    print(
        f"O-ADR29 apply: merged into model.units[].decision "
        f"(rows_from_file={applied} adr31_refused={refused})"
    )
    if refused:
        print(f"CLOSE:adr31 refused {refused} non-member evidence row(s)")
    return 0


def upsert_decision(
    root: Path,
    *,
    fqn: str,
    role: str,
    rationale: str,
    evidence: dict[str, Any],
    legacy: Optional[str] = None,
    target_contract: Any = None,
) -> int:
    """O-DECISIONWRITEDROP — persist ONE typed decision (small tool-call).

    Updates model.units[].decision and refreshes profile-decisions.json.
    Enforces ADR-31 F-anchor-membership. Exit 0 on success, 1 on refuse/error.
    """
    refuse = _refuse_adr30_alias(root)
    if refuse:
        print(refuse, file=sys.stderr)
        return 2
    fqn = (fqn or "").strip()
    role = (role or "").strip()
    rationale = (rationale or "").strip()
    if not fqn or role not in ROLES or not rationale:
        print(
            "O-DECISIONWRITEDROP: need --fqn, --role HARVEST|REDESIGN, --rationale",
            file=sys.stderr,
        )
        return 1
    ev = normalize_evidence(evidence)
    if ev is None:
        print(
            "O-DECISIONWRITEDROP: evidence incomplete (path, line≥1, token)",
            file=sys.stderr,
        )
        return 1
    model = _load_model(root)
    by_fqn = {
        (u.get("legacy_fqn") or u.get("key")): u for u in model.get("units") or []
    }
    mu = by_fqn.get(fqn)
    if mu is None:
        print(f"O-DECISIONWRITEDROP: unknown unit {fqn}", file=sys.stderr)
        return 1
    if _is_genassert_unit(mu):
        print(
            f"O-DECISIONWRITEDROP: REFUSE {fqn} — build-owned (O-RUBRICGENASSERT)",
            file=sys.stderr,
        )
        return 1
    if not _member_or_refuse(root, mu, ev, legacy=legacy):
        return 1
    dec: dict[str, Any] = {
        "role": role,
        "rationale": rationale,
        "evidence": ev,
    }
    if target_contract is not None:
        dec["target_contract"] = target_contract
    mu["decision"] = dec
    _save_model(root, model)
    _sync_decisions_file(root, model)
    print(
        f"O-DECISIONWRITEDROP upsert: {fqn} → {role} "
        f"@{ev['path']}:{ev['line']}:{ev['token']}"
    )
    return 0


def upsert_from_rows(
    root: Path,
    rows: list[dict[str, Any]],
    *,
    legacy: Optional[str] = None,
) -> int:
    """Upsert ≤ UPSERT_MAX_ROWS decision rows (JSON batch still small)."""
    if not rows:
        print("O-DECISIONWRITEDROP: empty row list", file=sys.stderr)
        return 1
    if len(rows) > UPSERT_MAX_ROWS:
        print(
            f"O-DECISIONWRITEDROP: REFUSE {len(rows)} rows — max "
            f"{UPSERT_MAX_ROWS} per upsert (split the batch; do not rewrite "
            f"profile-decisions.json wholesale)",
            file=sys.stderr,
        )
        return 1
    rc = 0
    for row in rows:
        fqn = row.get("legacy_fqn") or row.get("key") or ""
        role = row.get("role") or ""
        rationale = row.get("rationale") or row.get("claim") or ""
        ev = row.get("evidence")
        one = upsert_decision(
            root,
            fqn=str(fqn),
            role=str(role),
            rationale=str(rationale),
            evidence=ev if isinstance(ev, dict) else {},
            legacy=legacy,
            target_contract=row.get("target_contract"),
        )
        if one != 0:
            rc = one
    return rc


def _sync_decisions_file(root: Path, model: Optional[dict] = None) -> None:
    model = model or _load_model(root)
    units = _load_model_units(root) if model else []
    # Recompute profile units from this model
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model import profile_units  # type: ignore

    units = profile_units(model)
    doc_units = []
    for u in units:
        if _is_genassert_unit(u):
            continue
        d = u.get("decision") if isinstance(u.get("decision"), dict) else None
        if _decision_complete(d):
            doc_units.append(
                {
                    "legacy_fqn": u.get("legacy_fqn") or u.get("key"),
                    "legacy_path": u.get("legacy_path") or "",
                    "role": d["role"],
                    "rationale": d.get("rationale") or "",
                    "evidence": normalize_evidence(d.get("evidence")),
                    "target_contract": d.get("target_contract"),
                }
            )
        else:
            doc_units.append(
                {
                    "legacy_fqn": u.get("legacy_fqn") or u.get("key"),
                    "legacy_path": u.get("legacy_path") or "",
                    "role": None,
                    "rationale": "",
                    "evidence": None,
                    "target_contract": None,
                }
            )
    path = decisions_path(root)
    path.write_text(
        json.dumps({"schema": SCHEMA, "metric": METRIC, "units": doc_units}, indent=2)
        + "\n",
        encoding="utf-8",
    )


# O-PROFTCHARDPIN — decisive §7 lines for enabled migration.yaml targetContract
# flags. Must match profile-rubric DECISIVE tokens (404/400/ExceptionMapper/…).
_TARGET_CONTRACT_PINS: dict[str, str] = {
    "getIdempotent": (
        "- Target contract (`getIdempotent=true`): GET returns **404** on missing "
        "resources (404-on-missing).\n"
    ),
    "validateInput": (
        "- Target contract (`validateInput=true`): reject invalid input with "
        "**400** / `@Valid`.\n"
    ),
    "mapErrors": (
        "- Target contract (`mapErrors=true`): map failures via **ExceptionMapper** "
        "(**503** where applicable).\n"
    ),
    "threadSafeState": (
        "- Target contract (`threadSafeState=true`): shared mutable state via "
        "**ConcurrentHashMap** / `compute()`.\n"
    ),
    "cacheRefreshGuard": (
        "- Target contract (`cacheRefreshGuard=true`): cache via **@Cacheable** / "
        "Quarkus cache (bounded refresh).\n"
    ),
    "normalizeBeforeDerive": (
        "- Target contract (`normalizeBeforeDerive=true`): **normalize before** "
        "derive/aggregate.\n"
    ),
}


def _enabled_target_contract_flags(root: Path) -> list[str]:
    myaml_path = root / "migration.yaml"
    if not myaml_path.is_file():
        return []
    try:
        myaml = myaml_path.read_text(encoding="utf-8")
    except OSError:
        return []
    tc = re.search(r"^targetContract:(.*?)(^\S|\Z)", myaml, re.M | re.S)
    if not tc:
        return []
    return [
        flag
        for flag in _TARGET_CONTRACT_PINS
        if re.search(rf"^\s*{flag}:\s*true", tc.group(1), re.M)
    ]


def _target_contract_hardpins(root: Path) -> list[str]:
    """Declare-policy §7 bullets from migration.yaml (human-readable; not the gate).

    O-PROFTCHARDPIN / W4-487: these lines render *declared* operator policy.
    `RUBRIC:target-soft` must NOT be satisfied by this text alone — it checks
    typed `model.units[].decision.target_contract` (see profile-rubric).
    """
    flags = _enabled_target_contract_flags(root)
    if not flags:
        return []
    out: list[str] = [
        "<!-- O-PROFTCHARDPIN: declared targetContract policy from migration.yaml -->\n"
    ]
    for flag in flags:
        out.append(_TARGET_CONTRACT_PINS[flag])
    return out


# Paths that typically own HTTP/runtime contract surface (specimen-agnostic).
_CONTRACT_SURFACE = re.compile(
    r"(^|/)(rest|controller|resource|service|web|api)(/|$)|"
    r"(RestController|Resource|Endpoint|Controller|ServiceImpl)$",
    re.I,
)

# O-PROFTCCONSTANT / W4-526 PART A — enabled flags ∩ unit evidence.
# Prefer ADR-31 anchors; file-body scan is fallback for method-level tokens
# missing from the capped anchor set. normalizeBeforeDerive OMITTED (no
# reliable anchor per W4-526).
_FLAG_EVIDENCE: dict[str, tuple[re.Pattern[str], ...]] = {
    "getIdempotent": (
        re.compile(r"@GetMapping\b"),
        re.compile(r"@GET\b"),
        re.compile(r"@RequestMapping\b[^\n]*GET|\bRequestMethod\.GET\b"),
        re.compile(r"\bGetMapping\b"),
    ),
    "validateInput": (
        re.compile(r"@Valid\b"),
        re.compile(r"@Validated\b"),
        re.compile(r"@RequestBody\b"),
    ),
    "mapErrors": (
        re.compile(r"@ExceptionHandler\b"),
        re.compile(r"\bResponseEntity\b"),
        re.compile(r"ExceptionMapper"),
        re.compile(r"@ControllerAdvice\b"),
        re.compile(r"@ResponseStatus\b"),
    ),
    "threadSafeState": (
        re.compile(r"\bConcurrentHashMap\b"),
        re.compile(r"\bAtomic(?:Integer|Long|Boolean|Reference)\b"),
    ),
    "cacheRefreshGuard": (
        re.compile(r"@Cacheable\b"),
        re.compile(r"@CacheEvict\b"),
        re.compile(r"@Cache\b"),
        re.compile(r"\bCacheManager\b"),
    ),
}


def _unit_evidence_blob(root: Path, unit: dict) -> str:
    """Unit-local evidence text: ADR-31 anchors ∪ legacy file body."""
    parts: list[str] = []
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from profile_anchors import anchors_for_unit  # type: ignore

        for a in anchors_for_unit(root, unit) or []:
            parts.append(str(a.get("token") or ""))
            parts.append(str(a.get("note") or ""))
    except Exception:
        pass
    lp = (unit.get("legacy_path") or "").replace("\\", "/").lstrip("./")
    if lp:
        # Prefer /projects/legacy layout; also try root-relative for fixtures.
        candidates = [
            Path("/projects/legacy") / lp,
            root / "legacy" / lp,
            root / lp,
        ]
        for fp in candidates:
            if fp.is_file():
                try:
                    parts.append(fp.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
                break
    # Decision evidence token is also unit-local.
    d = unit.get("decision") if isinstance(unit.get("decision"), dict) else None
    if d and isinstance(d.get("evidence"), dict):
        parts.append(str(d["evidence"].get("token") or ""))
    return "\n".join(parts)


def _flags_evidenced_for_unit(root: Path, unit: dict, enabled: list[str]) -> list[str]:
    """O-PROFTCCONSTANT: enabled yaml flags ∩ shapes evidenced on this unit."""
    blob = _unit_evidence_blob(root, unit)
    if not blob.strip():
        return []
    out: list[str] = []
    for flag in enabled:
        pats = _FLAG_EVIDENCE.get(flag) or ()
        if any(p.search(blob) for p in pats):
            out.append(flag)
    return out


def apply_declared_target_contracts(root: Path) -> int:
    """O-PROFTCHARDPIN (b) + O-PROFTCCONSTANT — per-unit contract stamp.

    Selection: REDESIGN contract-surface units (path/name heuristic) — unchanged.
    Content: enabled migration.yaml flags **∩** shapes evidenced in that unit's
    ADR-31 anchors / legacy file (W4-493). Never copy the full global flag set
    onto every surface unit.
    """
    flags = _enabled_target_contract_flags(root)
    if not flags:
        return 0
    model = _load_model(root)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model import profile_units  # type: ignore

    # Decisive labels for typed blob (matches rubric DECISIVE tokens).
    decisive = {
        "getIdempotent": "404-on-missing",
        "validateInput": "400/@Valid",
        "mapErrors": "503/ExceptionMapper",
        "threadSafeState": "ConcurrentHashMap/compute",
        "cacheRefreshGuard": "@Cacheable/quarkus-cache",
        "normalizeBeforeDerive": "normalize-before-derive",
    }
    stamped = 0
    skipped_no_evidence = 0
    for u in profile_units(model):
        d = u.get("decision") if isinstance(u.get("decision"), dict) else None
        if not _decision_complete(d):
            continue
        if str(d.get("role") or "").upper() != "REDESIGN":
            continue
        surface = f"{u.get('legacy_path') or ''} {u.get('legacy_fqn') or ''}"
        if not _CONTRACT_SURFACE.search(surface):
            continue
        local_flags = _flags_evidenced_for_unit(root, u, flags)
        if not local_flags:
            # Eligible surface but no unit-local shape evidence — leave unset
            # rather than stamp the global constant (O-PROFTCCONSTANT).
            if d.get("target_contract"):
                d.pop("target_contract", None)
                u["decision"] = d
            skipped_no_evidence += 1
            continue
        tc: dict = {}
        for flag in local_flags:
            tc[flag] = True
            if flag in decisive:
                tc.setdefault("decisive", [])
                if isinstance(tc["decisive"], list) and decisive[flag] not in tc["decisive"]:
                    tc["decisive"].append(decisive[flag])
        d["target_contract"] = tc
        u["decision"] = d
        stamped += 1
    if stamped or skipped_no_evidence:
        _save_model(root, model)
        # O-PROFDECPROJ / W4-489 — always rebuild seat projection from SoT.
        # Prior path only patched when profile-decisions.json was a bare list;
        # live schema is {"schema","metric","units":[...]} so stamps landed in
        # model.json and left every projection target_contract=null.
        _sync_decisions_file(root, model)
    print(
        f"CLOSE:O-PROFTCHARDPIN stamped target_contract on {stamped} REDESIGN "
        f"surface unit(s) (O-PROFTCCONSTANT per-unit ∩ evidence; "
        f"skipped_no_local_evidence={skipped_no_evidence})"
    )
    return stamped


def render_sec7(root: Path, profile: Optional[str] = None) -> int:
    """One-way: write architecture-profile §7 from model decisions (F-render-oneway)."""
    model = _load_model(root)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model import profile_units  # type: ignore

    units = [u for u in profile_units(model) if not _is_genassert_unit(u)]
    lines = [
        "\n",
        "<!-- O-ADR29: §7 (Class Roles & Target Contract) rendered from "
        "model.units[].decision — do not hand-edit roles -->\n",
    ]
    # Specimen-agnostic contract pins belong in §7 (rubric reads sec7 only).
    lines.extend(_target_contract_hardpins(root))
    for u in units:
        fqn = u.get("legacy_fqn") or u.get("key") or "?"
        lp = u.get("legacy_path") or ""
        d = u.get("decision") if isinstance(u.get("decision"), dict) else None
        if not _decision_complete(d):
            lines.append(
                f"- `{fqn}` ({lp}) — UNDECIDED: fill migration/profile-decisions.json "
                f"(role + rationale + evidence.path/line/token)\n"
            )
            continue
        ev = normalize_evidence(d.get("evidence")) or {}
        cite = f"{ev.get('path')}:{ev.get('line')}"
        tok = ev.get("token") or ""
        rationale = (d.get("rationale") or "").strip()
        tc = d.get("target_contract")
        extra = ""
        if isinstance(tc, dict) and tc:
            extra = " target_contract=" + json.dumps(tc, separators=(",", ":"))
        elif isinstance(tc, str) and tc.strip():
            extra = f" target: {tc.strip()}"
        lines.append(
            f"- `{fqn}` ({lp}) — {d['role']}: {rationale} "
            f"({cite} `{tok}`){extra}\n"
        )

    path = Path(profile) if profile else root / "migration" / "architecture-profile.md"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Architecture profile\n\n"
            "## 1. Purpose & Domain\n\n(LLM fills.)\n\n"
            "## 2. Components & Relationships\n\n(LLM fills.)\n\n"
            "## 3. Integration Surfaces\n\n(LLM fills.)\n\n"
            "## 4. Behavioral Contract Sources\n\n(LLM fills.)\n\n"
            "## 5. Modernization Surface\n\n(LLM fills.)\n\n"
            "## 6. Domain Boundaries\n\n(LLM fills.)\n\n"
            "## 7. Class Roles & Target Contract\n",
            encoding="utf-8",
        )
    text = path.read_text(encoding="utf-8")
    start, end = _sec7_span(text)
    body = "".join(lines)
    if start < 0:
        text = text.rstrip() + "\n\n## 7. Class Roles & Target Contract\n" + body
    else:
        text = text[:start] + body + text[end:]
    path.write_text(text, encoding="utf-8")
    decided = sum(
        1
        for u in units
        if _decision_complete(u.get("decision") if isinstance(u.get("decision"), dict) else None)
    )
    print(
        f"O-ADR29 render: §7 (Class Roles & Target Contract) ← model "
        f"({decided}/{len(units)} decided) → {path}"
    )
    return 0


def evaluate_roles(root: Path, legacy: Optional[str] = None) -> dict[str, Any]:
    """Coverage + problems from model.units[].decision (ADR-29 SoT).

    Distinguishes **authored** (complete decision object on the model) from
    **credited/named** (authored AND evidence resolves on the cited line).
    W4-450: model can show 19 decisions while COVERAGE is 10/79 when 9
    anchors fail F-evidence-resolves — both numbers must be visible.
    """
    model = _load_model(root)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model import profile_units  # type: ignore

    units = [u for u in profile_units(model) if not _is_genassert_unit(u)]
    legacy_root = Path(legacy) if legacy else root / ".." / "legacy"
    # Common workspace layout: /projects/modernized + /projects/legacy
    if not legacy_root.is_dir():
        legacy_root = root.parent / "legacy"
    if not legacy_root.is_dir():
        # Fixture: legacy sources may live under root/src
        legacy_root = root

    problems: list[str] = []
    undecided: list[str] = []
    evidence_miss: list[str] = []
    decided_rows: list[dict] = []
    authored = 0
    for u in units:
        fqn = u.get("legacy_fqn") or u.get("key") or "?"
        d = u.get("decision") if isinstance(u.get("decision"), dict) else None
        if not _decision_complete(d):
            undecided.append(fqn)
            continue
        authored += 1
        ev = normalize_evidence(d.get("evidence"))
        assert ev is not None
        ok, why = evidence_resolves(legacy_root, ev)
        if not ok:
            problems.append(
                f"RUBRIC:evidence: {fqn} evidence does not resolve ({why}) "
                f"(evidence token must resolve at cited path:line)"
            )
            evidence_miss.append(fqn)
            undecided.append(fqn)
            continue
        # ADR-31 — belt: membership even if something bypassed apply.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from profile_anchors import (  # type: ignore
            anchors_for_unit,
            evidence_in_anchor_set,
        )

        anchors = anchors_for_unit(root, u, legacy_root=legacy_root)
        if not evidence_in_anchor_set(ev, anchors):
            problems.append(
                f"RUBRIC:anchor-membership: {fqn} evidence not in projected "
                f"projected set (F-anchor-membership)"
            )
            evidence_miss.append(fqn)
            undecided.append(fqn)
            continue
        decided_rows.append({"legacy_fqn": fqn, **d, "evidence": ev})

    total = len(units)
    named = len(decided_rows)
    if undecided:
        problems.append(
            f"RUBRIC:roles: {len(undecided)}/{total} profile-units lack a "
            f"typed decision on model.units[].decision"
        )
    # Duplicate evidence anchors (same path:line:token) — templates collapse.
    if len(decided_rows) >= 2:
        anchors = [
            f"{r['evidence']['path']}:{r['evidence']['line']}:{r['evidence']['token']}"
            for r in decided_rows
        ]
        if len(set(anchors)) < len(anchors):
            problems.append(
                f"RUBRIC:roles: duplicate evidence anchors among {len(decided_rows)} "
                f"decisions — each unit needs its own resolving path:line:token"
            )
    # F-scope-width / W4-526 PART B / ADR-36 S-2 REV-1 — claim fields must
    # vary per unit. Byte-identical claim content across N>1 → RED.
    # reference fields (story_id, scc, …) may be shared.
    problems.extend(_scope_width_problems(decided_rows))
    return {
        "named": named,
        "authored": authored,
        "evidence_miss": evidence_miss,
        "total": total,
        "undecided": undecided,
        "problems": problems,
        "sot": "model-decision",
        "metric": METRIC,
        "decided": decided_rows,
    }


# Per-unit decision fields typed claim vs reference (W4-526 / ADR-36 S-2).
_CLAIM_FIELDS = ("role", "rationale", "target_contract", "evidence")


def _claim_fingerprint(field: str, value: Any) -> Optional[str]:
    """Stable fingerprint for a claim field; None = skip (empty/absent)."""
    if value is None or value == "" or value == {}:
        return None
    if field == "target_contract":
        if not isinstance(value, dict):
            return None
        # Ignore empty decisive-only noise; require at least one flag/key.
        if not any(k != "decisive" for k in value):
            return None
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if field == "evidence":
        if not isinstance(value, dict):
            return None
        # Evidence path:line:token is expected unique — duplicate already
        # covered above; still treat as claim for F-scope-width.
        p, ln, tok = value.get("path"), value.get("line"), value.get("token")
        if p is None or ln is None or tok is None:
            return None
        return f"{p}:{ln}:{tok}"
    if field == "role":
        # role ∈ {HARVEST,REDESIGN} — binary vocabulary; identical across
        # many units is expected. Not a width claim.
        return None
    s = str(value).strip()
    return s or None


def _scope_width_problems(decided_rows: list[dict]) -> list[str]:
    """F-scope-width (W4-526): RED when a claim field has distinct=1 across N>1.

    Tip e94285c: target_contract n=13 distinct=1 → RED. Rationale with many
    distinct values (even if some pairs collide) stays silent — the defect is
    a *constant* claim stamped on every unit, not ordinary partial overlap.
    """
    out: list[str] = []
    for field in _CLAIM_FIELDS:
        buckets: dict[str, list[str]] = {}
        for r in decided_rows:
            fp = _claim_fingerprint(field, r.get(field))
            if fp is None:
                continue
            buckets.setdefault(fp, []).append(r.get("legacy_fqn") or "?")
        if len(buckets) != 1:
            continue
        fp, fqns = next(iter(buckets.items()))
        if len(fqns) <= 1:
            continue
        sample = ", ".join(fqns[:3])
        more = f" (+{len(fqns) - 3})" if len(fqns) > 3 else ""
        out.append(
            f"RUBRIC:scope-width: claim field {field!r} is constant across "
            f"{len(fqns)} units (distinct=1; {sample}{more}) — F-scope-width "
            f"(per-unit claim must not copy a wider-scope constant)"
        )
    return out


def lint_roles(root: Path, legacy: Optional[str] = None) -> int:
    ev = evaluate_roles(root, legacy=legacy)
    miss = len(ev.get("evidence_miss") or [])
    print(
        f"ROLES: {ev['named']}/{ev['total']} credited "
        f"authored={ev.get('authored', ev['named'])} evidence_miss={miss} "
        f"metric={ev['metric']} sot={ev['sot']}"
    )
    for fqn in ev["undecided"]:
        print(f"UNDECIDED: {fqn}")
    for p in ev["problems"]:
        print(p)
    return 1 if ev["problems"] or ev["undecided"] else 0


def harvest_roles(root: Path, profile: Optional[str] = None) -> int:
    """Removed — F-render-oneway. Parsing §7 for roles is forbidden."""
    print(
        "O-ADR29: harvest from markdown REMOVED (F-render-oneway). "
        "Write migration/profile-decisions.json or model.units[].decision; "
        "then: profile_roles.py apply && profile_roles.py render",
        file=sys.stderr,
    )
    return 2


# Back-compat aliases used by older call sites.
init_decisions = init_roles
evaluate_decisions = evaluate_roles


def redesign_fqns(root: Path) -> set[str]:
    """M2 consumer — CapWord / FQN with role=REDESIGN from model (not §7).

    Missing model.json → empty set (fixtures / pre-model compose fall back to §7).
    Never raises FileNotFoundError into m2-compose.
    """
    if not (root / "migration" / "model.json").is_file():
        return set()
    model = _load_model(root)
    out: set[str] = set()
    for u in model.get("units") or []:
        d = u.get("decision") if isinstance(u.get("decision"), dict) else None
        if not d or d.get("role") != "REDESIGN":
            continue
        fqn = u.get("legacy_fqn") or u.get("key") or ""
        if fqn:
            out.add(fqn.rsplit(".", 1)[-1])
            out.add(fqn)
    return out


def redesign_contract_hints(root: Path) -> dict[str, str]:
    """class simple name → target_contract / rationale for REDESIGN units."""
    if not (root / "migration" / "model.json").is_file():
        return {}
    model = _load_model(root)
    hints: dict[str, str] = {}
    for u in model.get("units") or []:
        d = u.get("decision") if isinstance(u.get("decision"), dict) else None
        if not d or d.get("role") != "REDESIGN":
            continue
        simple = (u.get("legacy_fqn") or u.get("key") or "?").rsplit(".", 1)[-1]
        tc = d.get("target_contract")
        if isinstance(tc, dict) and tc:
            hints[simple] = json.dumps(tc, separators=(",", ":"))
        elif isinstance(tc, str) and tc.strip():
            hints[simple] = tc.strip()
        else:
            hints[simple] = (d.get("rationale") or "").strip()
    return hints


def main() -> int:
    ap = argparse.ArgumentParser(description="ADR-29 typed profile decisions")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser(
        "init", parents=[common], help="Open decision slots on model + decisions file"
    )
    p_init.set_defaults(func=lambda a: init_roles(Path(a.root).resolve()))

    p_apply = sub.add_parser(
        "apply", parents=[common], help="Merge decisions file → model SoT"
    )
    p_apply.add_argument("--decisions", default=None)
    p_apply.add_argument(
        "--legacy",
        default=None,
        help="Legacy source root for ADR-31 anchor membership (default: sibling legacy/ or root)",
    )
    p_apply.set_defaults(
        func=lambda a: apply_decisions(
            Path(a.root).resolve(),
            decisions_file=a.decisions,
            legacy=a.legacy,
        )
    )

    p_upsert = sub.add_parser(
        "upsert",
        parents=[common],
        help="O-DECISIONWRITEDROP — persist 1 (or ≤UPSERT_MAX_ROWS) typed decision(s)",
    )
    p_upsert.add_argument("--legacy", default=None)
    p_upsert.add_argument(
        "--json-file",
        default=None,
        help=f"JSON list or {{units:[…]}} with ≤{UPSERT_MAX_ROWS} rows (small batch)",
    )
    p_upsert.add_argument("--fqn", default=None, help="legacy_fqn for single-row upsert")
    p_upsert.add_argument("--role", default=None, choices=sorted(ROLES))
    p_upsert.add_argument("--rationale", default=None)
    p_upsert.add_argument("--path", dest="ev_path", default=None, help="evidence.path")
    p_upsert.add_argument("--line", dest="ev_line", type=int, default=None)
    p_upsert.add_argument("--token", dest="ev_token", default=None)

    def _upsert_cmd(a: argparse.Namespace) -> int:
        root = Path(a.root).resolve()
        if a.json_file:
            try:
                raw = json.loads(Path(a.json_file).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                print(f"O-DECISIONWRITEDROP: cannot read --json-file: {e}", file=sys.stderr)
                return 1
            if isinstance(raw, dict):
                rows = list(raw.get("units") or [])
            elif isinstance(raw, list):
                rows = raw
            else:
                print("O-DECISIONWRITEDROP: --json-file must be list or {units:[…]}", file=sys.stderr)
                return 1
            return upsert_from_rows(root, rows, legacy=a.legacy)
        if not a.fqn:
            print(
                "O-DECISIONWRITEDROP: need --fqn … or --json-file (small payload)",
                file=sys.stderr,
            )
            return 1
        return upsert_decision(
            root,
            fqn=a.fqn,
            role=a.role or "",
            rationale=a.rationale or "",
            evidence={
                "path": a.ev_path or "",
                "line": a.ev_line if a.ev_line is not None else 0,
                "token": a.ev_token or "",
            },
            legacy=a.legacy,
        )

    p_upsert.set_defaults(func=_upsert_cmd)

    p_render = sub.add_parser(
        "render", parents=[common], help="Render §7 from model decisions"
    )
    p_render.add_argument("--profile", default=None)
    p_render.set_defaults(
        func=lambda a: render_sec7(Path(a.root).resolve(), profile=a.profile)
    )

    p_lint = sub.add_parser(
        "lint", parents=[common], help="Fail-closed typed-decision gate"
    )
    p_lint.add_argument("--legacy", default=None)
    p_lint.set_defaults(
        func=lambda a: lint_roles(Path(a.root).resolve(), legacy=a.legacy)
    )

    p_harvest = sub.add_parser(
        "harvest", parents=[common], help="REMOVED (F-render-oneway)"
    )
    p_harvest.add_argument("--profile", default=None)
    p_harvest.set_defaults(
        func=lambda a: harvest_roles(Path(a.root).resolve(), profile=a.profile)
    )

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
