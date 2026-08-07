#!/usr/bin/env python3
"""M4←M3 consumer assertions (ADR-47 / build step 1b).

Trust is the outcome of a passed assert — not M3 GATE GREEN.

Asserts (specimen-agnostic):
  1. acceptance — no precondition-shaped clauses
  1b. char_surface — characterize Owns test must exercise ≥1 public member
     of unit_keys (W4-708 / W4-768 refuse-char default)
  2. unit_keys — every key resolves in model.units
  3. identity atom — task id matches HEADING_TASK_ID_RE
  4. staging hash — capture present + staging_immutable.check green
  5. role-vs-predicted-dest — HARVEST must not leave contract-forbidden
     content after configTransforms (predicted dest, not raw staging)
  6. edge_order — zero requires-type/characterizes order violations against
     wave-ordered plan (O-EDGEASSERT / W4-739) — graph as check, not scheduler

Modes:
  observe     — print fires; always exit 0
  refuse      — exit 1 if any fire (typed stop; no in-place repair)
  refuse-char — exit 1 only on char_surface fires (W4-768 default; other
                asserts remain observe)

Usage:
  m4_consumer_assert.py [--mode=observe|refuse|refuse-char] [--story=S0N]
                        [--json=path] [--explain-drop=REASON]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("SENSOR_ROOT", ".")).resolve()
sys.path.insert(0, str(Path(__file__).resolve().parent))

from task_contract import (  # noqa: E402
    HEADING_TASK_ID_RE,
    clause_evidence_kind,
    is_precondition_shaped_acceptance,
)
from task_lifecycle import task_has_run  # noqa: E402
from m4_edges import derive_edges, order_violations  # noqa: E402
from m4_wave import order_ids  # noqa: E402

_FORBIDDEN_PROP = re.compile(
    r"(?m)^\s*((?:spring|server)\.[A-Za-z0-9._-]+)\s*=",
)

_JAVA_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_JAVA_LINE_COMMENT = re.compile(r"//.*?$", re.M)
_JAVA_STRING = re.compile(r'"(?:\\.|[^"\\])*"')
# Interface/class method decls (specimen-agnostic).
_JAVA_METHOD_DECL = re.compile(
    r"(?:(?:public|protected|private|default|static|final|abstract|"
    r"synchronized|native)\s+)*(?:<[^>]+>\s+)?"
    r"(?:[\w.]+(?:\s*<[^>]*>)?(?:\s*\[\s*\])*(?:\s*\.\s*[\w.]+(?:\s*<[^>]*>)?(?:\s*\[\s*\])*)*)\s+"
    r"(\w+)\s*\([^;{}]*\)\s*(?:throws\s+[^{;]+)?\s*[;{]",
)
_JAVA_KEYWORDS = frozenset(
    {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "return",
        "new",
        "throw",
        "assert",
        "else",
        "try",
        "do",
        "case",
        "class",
        "interface",
        "enum",
        "record",
        "void",
    }
)
_HISTORY = "migration/m4-observe-history.jsonl"
_LAST = "migration/m4-consumer-assert-last.json"


def _load_model() -> dict:
    p = ROOT / "migration" / "model.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _units_by_key(model: dict) -> dict[str, dict]:
    out = {}
    for u in model.get("units") or []:
        k = u.get("key")
        if k:
            out[str(k)] = u
    return out


def _tasks(model: dict, story: str | None) -> list[dict]:
    tasks = list(model.get("tasks") or [])
    if story:
        tasks = [t for t in tasks if str(t.get("sid") or "").startswith(story) or str(t.get("id") or "").startswith(story)]
    return tasks


def _acceptance_clauses(t: dict) -> list[str]:
    """Acceptance[] only — do not scrape goal/plan (W4-708 false-fire)."""
    v = t.get("acceptance")
    if isinstance(v, str) and v.strip():
        return [v.strip()]
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return []


def _owns_paths(t: dict) -> list[str]:
    owns = t.get("owns") or []
    if isinstance(owns, str):
        return [owns] if owns.strip() else []
    return [str(x) for x in owns if str(x).strip()]


def _strip_java_noise(text: str) -> str:
    text = _JAVA_BLOCK_COMMENT.sub(" ", text)
    text = _JAVA_LINE_COMMENT.sub(" ", text)
    text = _JAVA_STRING.sub('""', text)
    return text


def _java_public_members(source: str) -> list[str]:
    """Method names from a Java type body (interfaces + classes)."""
    body = _strip_java_noise(source)
    # Drop package/imports header noise is fine; decls still match.
    simple = None
    m_cls = re.search(r"\b(?:class|interface|enum|record)\s+(\w+)", body)
    if m_cls:
        simple = m_cls.group(1)
    out: list[str] = []
    seen: set[str] = set()
    for m in _JAVA_METHOD_DECL.finditer(body):
        name = m.group(1)
        if name in _JAVA_KEYWORDS or name == simple:
            continue
        # Reject `new Foo(` constructor calls mistaken for decls.
        head = m.group(0).lstrip().split(None, 1)
        if head and head[0] == "new":
            continue
        if name[:1].isupper() and name not in (simple or "",):
            # Type-looking token as "method name" → almost always a false decl.
            continue
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _test_exercises_members(test_text: str, members: list[str]) -> list[str]:
    """Return members referenced as invocations in the test body."""
    body = _strip_java_noise(test_text)
    hit: list[str] = []
    for name in members:
        # Prefer call / method-ref forms; bare name( also catches helpers.
        if re.search(rf"(?:\.\s*|::\s*){re.escape(name)}\s*\(", body):
            hit.append(name)
            continue
        if re.search(rf"\b{re.escape(name)}\s*\(", body):
            hit.append(name)
    return hit


def _java_extends_simple(source: str) -> str | None:
    m = re.search(
        r"\b(?:class|interface)\s+\w+(?:\s*<[^>]+>)?\s+extends\s+([\w.]+)",
        _strip_java_noise(source),
    )
    return m.group(1) if m else None


def _resolve_staging_for_simple(
    units: dict[str, dict], simple_or_fqcn: str, from_pkg: str
) -> Path | None:
    """Locate staging source for a simple name or FQCN (inheritance walk)."""
    name = simple_or_fqcn.split(".")[-1]
    # Prefer exact unit key match / suffix match
    for key, u in units.items():
        if key == simple_or_fqcn or key.endswith("." + name) or key == name:
            sp = u.get("staging_path")
            if sp and (ROOT / str(sp)).is_file():
                return ROOT / str(sp)
    # Same-package guess from caller staging path package
    if from_pkg:
        cand = ROOT / "migration/staging/src/main/java" / from_pkg.replace(".", "/") / f"{name}.java"
        if cand.is_file():
            return cand
    # Broad staging search (bounded)
    staging = ROOT / "migration/staging"
    if staging.is_dir():
        hits = list(staging.rglob(f"{name}.java"))
        if len(hits) == 1:
            return hits[0]
    return None


def _effective_public_members(
    src_path: Path, units: dict[str, dict], *, depth: int = 0
) -> list[str]:
    """Declared members plus inherited (W4-736 §4). Cap depth to avoid cycles."""
    if depth > 6 or not src_path.is_file():
        return []
    text = src_path.read_text(encoding="utf-8", errors="replace")
    members = list(_java_public_members(text))
    seen = set(members)
    parent = _java_extends_simple(text)
    if not parent:
        return members
    pkg_m = re.search(r"^\s*package\s+([\w.]+)\s*;", text, re.M)
    pkg = pkg_m.group(1) if pkg_m else ""
    parent_path = _resolve_staging_for_simple(units, parent, pkg)
    if parent_path is None:
        return members
    for m in _effective_public_members(parent_path, units, depth=depth + 1):
        if m not in seen:
            seen.add(m)
            members.append(m)
    return members


def _char_surface_fires(t: dict, units: dict[str, dict]) -> list[dict]:
    """W4-708: characterize Owns test must exercise unit_keys public surface.

    W4-736: Owns-missing only after task has run; surface includes inheritance.
    """
    tid = str(t.get("id") or "")
    tk = str(t.get("kind") or "").lower()
    if tk != "characterize":
        return []
    keys = t.get("unit_keys") or []
    if isinstance(keys, str):
        keys = [keys]
    if not keys:
        return [
            {
                "assert": "char_surface",
                "task": tid,
                "detail": "characterize task missing unit_keys (W4-708)",
            }
        ]
    owns = [p for p in _owns_paths(t) if p.endswith(".java")]
    if not owns:
        return [
            {
                "assert": "char_surface",
                "task": tid,
                "detail": "characterize task has no Owns *.java test path (W4-708)",
            }
        ]
    # W4-738 §5.2 — shared predicate (task_lifecycle), not assert-local only
    has_run = task_has_run(tid, root=ROOT)
    fires: list[dict] = []
    for uk in keys:
        u = units.get(str(uk)) or {}
        sp = str(u.get("staging_path") or "")
        if not sp:
            fires.append(
                {
                    "assert": "char_surface",
                    "task": tid,
                    "detail": f"unit_key={uk} has no staging_path for surface check",
                }
            )
            continue
        src_path = ROOT / sp
        if not src_path.is_file():
            fires.append(
                {
                    "assert": "char_surface",
                    "task": tid,
                    "detail": f"staging source missing for unit_key={uk}: {sp}",
                }
            )
            continue
        members = _effective_public_members(src_path, units)
        if not members:
            fires.append(
                {
                    "assert": "char_surface",
                    "task": tid,
                    "detail": (
                        f"unit_key={uk} has empty effective public surface "
                        f"(incl. inherited) — not independently characterizable "
                        f"(W4-736 §4)"
                    ),
                }
            )
            continue
        exercised: list[str] = []
        missing_tests: list[str] = []
        for op in owns:
            tp = ROOT / op
            if not tp.is_file():
                missing_tests.append(op)
                continue
            exercised.extend(
                _test_exercises_members(
                    tp.read_text(encoding="utf-8", errors="replace"), members
                )
            )
        # W4-736 §3 — pre-dispatch absence is not a defect
        if missing_tests and not exercised:
            if has_run:
                fires.append(
                    {
                        "assert": "char_surface",
                        "task": tid,
                        "detail": (
                            f"Owns test missing after task ran: {missing_tests[0]} "
                            f"(W4-736 lifecycle)"
                        ),
                    }
                )
            continue
        if missing_tests and not has_run:
            # Test not produced yet — skip surface-zero on absent Owns
            continue
        # unique preserve order
        seen: set[str] = set()
        uniq = []
        for m in exercised:
            if m not in seen:
                seen.add(m)
                uniq.append(m)
        if not uniq:
            fires.append(
                {
                    "assert": "char_surface",
                    "task": tid,
                    "detail": (
                        f"test exercises 0/{len(members)} public members of "
                        f"{uk} (surface={members[:8]}; W4-708)"
                    ),
                }
            )
    return fires


def _parse_config_transforms() -> dict[str, str]:
    """from→to bare keys from migration.yaml configTransforms."""
    try:
        from config_derived import _parse_yaml_transforms  # type: ignore
    except Exception:
        return {}
    ypath = ROOT / "migration.yaml"
    if not ypath.is_file():
        return {}
    transforms, _errs = _parse_yaml_transforms(ypath.read_text(encoding="utf-8"))
    return {frm: (meta.get("to") or "") for frm, meta in transforms.items()}


def _predicted_props_forbidden(staging_path: Path, transforms: dict[str, str]) -> list[str]:
    """Keys that remain forbidden after applying configTransforms to staged props."""
    if not staging_path.is_file():
        return []
    text = staging_path.read_text(encoding="utf-8", errors="replace")
    survivors = []
    for m in _FORBIDDEN_PROP.finditer(text):
        key = m.group(1)
        if key in transforms:
            continue  # mapped away
        # profile-stripped match
        bare = key.split(".", 1)[-1] if key.startswith("spring.") else key
        if any(frm == key or frm.endswith(key) or key.endswith(frm) for frm in transforms):
            continue
        survivors.append(key)
    return survivors


def _staging_check() -> list[str]:
    script = Path(__file__).resolve().parent / "staging_immutable.py"
    if not script.is_file():
        return ["staging_immutable.py missing"]
    if not (ROOT / "migration" / "staging").is_dir():
        return []
    r = subprocess.run(
        [sys.executable, str(script), "check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        return []
    return [(r.stdout or r.stderr or "staging check failed").strip().splitlines()[:1][0]]


def run_asserts(story: str | None = None) -> list[dict]:
    model = _load_model()
    units = _units_by_key(model)
    transforms = _parse_config_transforms()
    fires: list[dict] = []

    # Assert 4 — once per run (not per task)
    for msg in _staging_check():
        fires.append({"assert": "staging_hash", "task": "*", "detail": msg})

    for t in _tasks(model, story):
        tid = str(t.get("id") or "")
        if not tid:
            continue

        # 3 — identity atom
        if not HEADING_TASK_ID_RE.match(tid):
            fires.append(
                {
                    "assert": "identity_atom",
                    "task": tid,
                    "detail": f"id {tid!r} outside HEADING_TASK_ID_ATOM",
                }
            )

        # 2 — unit_keys resolve
        keys = t.get("unit_keys") or []
        if isinstance(keys, str):
            keys = [keys]
        for uk in keys:
            if str(uk) not in units:
                fires.append(
                    {
                        "assert": "unit_keys",
                        "task": tid,
                        "detail": f"unresolvable unit_key={uk}",
                    }
                )

        # 1 — verifiable acceptance (W4-735): typed kind classifies characterize;
        # semantic oracle is surface check below — do NOT prose-grep pins-legacy.
        tk = str(t.get("kind") or "")
        for clause in _acceptance_clauses(t):
            if is_precondition_shaped_acceptance(clause):
                fires.append(
                    {
                        "assert": "acceptance",
                        "task": tid,
                        "detail": f"precondition-shaped acceptance: {clause[:120]}",
                    }
                )
            elif (
                tk.lower() != "characterize"
                and clause_evidence_kind(clause, task_kind=tk) is None
            ):
                fires.append(
                    {
                        "assert": "acceptance",
                        "task": tid,
                        "detail": f"no evidence kind for acceptance: {clause[:120]}",
                    }
                )

        # 1b — W4-708 / W4-735 §4: Owns test exercises ≥1 public member of unit_keys
        fires.extend(_char_surface_fires(t, units))

        # 5 — role-vs-predicted-dest (HARVEST only)
        role = str(t.get("role") or "").upper()
        if role == "HARVEST":
            for uk in keys:
                u = units.get(str(uk)) or {}
                sp = u.get("staging_path") or ""
                if not sp or not str(sp).endswith(".properties"):
                    continue
                staging = ROOT / str(sp)
                bad = _predicted_props_forbidden(staging, transforms)
                if bad:
                    fires.append(
                        {
                            "assert": "role_vs_predicted_dest",
                            "task": tid,
                            "detail": (
                                f"HARVEST predicted dest still has forbidden keys "
                                f"{bad[:5]} — role should be REDESIGN/COORD or "
                                f"add configTransforms (assert-5)"
                            ),
                        }
                    )

    # 6 — O-EDGEASSERT (W4-739): graph is a consumer check, not a scheduler.
    # Evaluate against wave-ordered ids (same projection supervisor dispatches).
    try:
        by_id = {
            str(t.get("id")): t
            for t in (model.get("tasks") or [])
            if t.get("id")
        }
        ids = list(by_id.keys())
        if story:
            ids = [
                i
                for i in ids
                if i.startswith(story)
                or str((by_id[i].get("sid") or "")).startswith(story)
            ]
        ordered = order_ids(ids, by_id)
        edges = derive_edges(model)
        # Scope edges to tasks in this assert window
        idset = set(ordered)
        scoped = [
            e
            for e in edges
            if e.get("before") in idset and e.get("after") in idset
        ]
        viol = order_violations(scoped, ordered)
        for v in viol[:40]:
            fires.append(
                {
                    "assert": "edge_order",
                    "task": str(v.get("after") or "*"),
                    "detail": (
                        f"{v.get('type')}: {v.get('before')} must precede "
                        f"{v.get('after')} (O-EDGEASSERT / INVALID_INPUT→M3)"
                    ),
                }
            )
        if len(viol) > 40:
            fires.append(
                {
                    "assert": "edge_order",
                    "task": "*",
                    "detail": f"… {len(viol) - 40} more edge_order violations",
                }
            )
    except Exception as exc:
        fires.append(
            {
                "assert": "edge_order",
                "task": "*",
                "detail": f"O-EDGEASSERT derive failed: {exc}",
            }
        )
    return fires


def _record_history(summary: dict, explain_drop: str) -> None:
    """O-FIREBASELINE — track observe fire counts; drops need an explanation."""
    hist_path = ROOT / _HISTORY
    last_path = ROOT / _LAST
    prev_count = None
    if last_path.is_file():
        try:
            prev = json.loads(last_path.read_text(encoding="utf-8"))
            prev_count = int(prev.get("fire_count") or 0)
        except Exception:
            prev_count = None
    last_path.parent.mkdir(parents=True, exist_ok=True)
    last_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": summary.get("mode"),
        "fire_count": summary.get("fire_count"),
        "by_assert": summary.get("by_assert"),
        "prev_fire_count": prev_count,
        "explain_drop": explain_drop or "",
    }
    with hist_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    if (
        prev_count is not None
        and int(summary.get("fire_count") or 0) < prev_count
        and not explain_drop
    ):
        print(
            f"M4_CONSUMER_ASSERT:FIRE_DROP {prev_count}→{summary.get('fire_count')} "
            f"without --explain-drop (O-FIREBASELINE / W4-734 §4)",
            file=sys.stderr,
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mode",
        choices=("observe", "refuse", "refuse-char"),
        default=os.environ.get("M4_CONSUMER_ASSERT", "refuse-char"),
        help=(
            "observe=log only; refuse=any fire stops; refuse-char (default, W4-768)="
            "only char_surface fires refuse (characterize unit exercise oracle)"
        ),
    )
    ap.add_argument("--story", default=None)
    ap.add_argument("--json", default="")
    ap.add_argument(
        "--explain-drop",
        default=os.environ.get("M4_FIRE_DROP_EXPLAIN", ""),
        help="Required when observe fire_count drops vs last run (O-FIREBASELINE)",
    )
    args = ap.parse_args()
    fires = run_asserts(args.story)
    summary = {
        "mode": args.mode,
        "fire_count": len(fires),
        "by_assert": {},
        "fires": fires,
    }
    for f in fires:
        summary["by_assert"][f["assert"]] = summary["by_assert"].get(f["assert"], 0) + 1
    text = json.dumps(summary, indent=2)
    if args.json:
        Path(args.json).write_text(text + "\n", encoding="utf-8")
    _record_history(summary, args.explain_drop)
    print(f"M4_CONSUMER_ASSERT mode={args.mode} fires={len(fires)} by={summary['by_assert']}")
    for f in fires[:40]:
        print(f"  FIRE {f['assert']} {f['task']}: {f['detail']}")
    if len(fires) > 40:
        print(f"  … {len(fires) - 40} more")
    if args.mode == "refuse" and fires:
        print("M4_CONSUMER_ASSERT:REFUSE — INVALID_INPUT (no in-place repair)")
        return 1
    if args.mode == "refuse-char":
        char_fires = [f for f in fires if f.get("assert") == "char_surface"]
        if char_fires:
            print(
                f"M4_CONSUMER_ASSERT:REFUSE-CHAR — {len(char_fires)} char_surface "
                "fire(s) (W4-768; other asserts still observe)"
            )
            return 1
        print(
            "M4_CONSUMER_ASSERT:REFUSE-CHAR — no char_surface fires "
            f"(other={len(fires)} observe-only)"
        )
        return 0
    if args.mode == "observe":
        print("M4_CONSUMER_ASSERT:OBSERVE — no refuse (pre-1b measurement)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
