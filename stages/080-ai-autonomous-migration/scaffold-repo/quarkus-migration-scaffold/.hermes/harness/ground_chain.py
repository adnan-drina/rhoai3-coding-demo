#!/usr/bin/env python3
"""Grounding chain helpers — G4 / G5 / G9 / G10 (W4-589 / W4-609).

Each check answers one pipeline-handoff question. Verdicts are PASS / FAIL /
NOT-LANDED. Callers (outer-loop) emit demo-facing GROUND lines; this module
owns the substance so population is not hand-maintained beside the emitters.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from task_contract import (  # type: ignore
    evidence_kinds_for_acceptance,
    is_valid_shape,
    story_state,
)

# Evidence kind → non-empty markers that must appear in the derived-facts block.
# Adding a kind to ACCEPTANCE_EVIDENCE + a marker here extends G4 automatically.
KIND_SECTION_MARKERS: dict[str, tuple[str, ...]] = {
    "staging_fact": ("STAGING FACTS", "provenance: staging_facts="),
    "target_contract": ("target_contract", " tc=", "implements typed target_contract"),
    "derived": ("===== BEGIN DERIVED FACTS", "BEGIN DERIVED FACTS"),
    "snippet": ("SNIPPET:",),
    # model.context_for projects findings inline as findings=[…] on unit lines
    "findings": ("findings=[", "findings:"),
    "dependency_order": ("dependency-order:", "\norder:", "order: "),
    "symbol_index": ("symbol-index",),
}

# Goal verbs inconsistent with HARVEST / byte-fidelity acceptance (W4-560 §5).
_HARVEST_BAD_GOAL = re.compile(
    r"\b(create|design|implement|author|write\s+new|invent)\b",
    re.I,
)
_HARVEST_GOOD_GOAL = re.compile(
    r"\b(harvest|pull|copy|relocate|rename|package[- ]rename|byte[- ]fidelity|from\s+staging)\b",
    re.I,
)
_PLACEHOLDER_ASSERT = re.compile(
    r"assertTrue\s*\(\s*true\s*\)|assertThat\s*\(\s*true\s*\)|assertEquals\s*\(\s*true\s*,\s*true\s*\)",
    re.I,
)
_SPRING_JAVAX = re.compile(
    r"\b(?:org\.springframework|javax\.(?:persistence|inject|annotation|validation))\b"
)
_JAVA_TYPE_TOKEN = re.compile(r"\b([A-Z][A-Za-z0-9]{2,})\b")


def _tasks_for(model: dict, sid: str) -> list[dict]:
    want = str(sid or "").strip()
    return [
        t
        for t in (model.get("tasks") or [])
        if str(t.get("sid") or "").strip() == want
    ]


def story_evidence_kinds(model: dict, sid: str) -> list[str]:
    """Union of evidence kinds declared by the story's typed acceptance."""
    out: list[str] = []
    for t in _tasks_for(model, sid):
        for k in evidence_kinds_for_acceptance(
            t.get("acceptance") or [], task_kind=str(t.get("kind") or "")
        ):
            if k not in out:
                out.append(k)
    # Baseline packet always projects these structural facts (ADR-21 / ADR-24).
    for k in ("derived", "findings", "dependency_order", "symbol_index"):
        if k not in out:
            out.append(k)
    return out


def g4_verdict(block: str, kinds: list[str]) -> tuple[str, str]:
    """G4 — are acceptance-declared evidence sections present and non-empty?"""
    text = block or ""
    if "BEGIN DERIVED FACTS" not in text:
        return (
            "FAIL",
            "derived-facts block missing from seat prompt (header absent)",
        )
    missing: list[str] = []
    present: list[str] = []
    for kind in kinds:
        markers = KIND_SECTION_MARKERS.get(kind)
        if not markers:
            continue
        ok = any(m in text for m in markers)
        if kind == "staging_fact":
            # Header alone is not enough — need at least one real fact line.
            in_sec = False
            fact_lines: list[str] = []
            for ln in text.splitlines():
                if "STAGING FACTS" in ln:
                    in_sec = True
                    continue
                if in_sec and ln.startswith("provenance:"):
                    break
                if in_sec and ln.strip().startswith("- "):
                    if "no staging" not in ln.lower():
                        fact_lines.append(ln)
            ok = ok and bool(fact_lines)
        if ok:
            present.append(kind)
        else:
            missing.append(kind)
    if missing:
        return (
            "FAIL",
            f"missing/empty evidence sections for kinds={missing}; present={present}",
        )
    return (
        "PASS",
        f"acceptance-derived kinds present and non-empty: {present}",
    )


def g5_verdict(model: dict, sid: str) -> tuple[str, str]:
    """G5 — derived half by construction; seat goal/plan tokens must resolve."""
    if story_state(model, sid) != "SPECIFIED":
        return ("NOT-LANDED", f"{sid}: UNSPECIFIED — G5 deferred until SPECIFIED")
    tasks = _tasks_for(model, sid)
    if not tasks:
        return ("NOT-LANDED", f"{sid}: no typed tasks")
    # Derived half — Shape / Acceptance / owns are harness-owned.
    for t in tasks:
        shape = str(t.get("shape") or "")
        if shape and not is_valid_shape(shape):
            return (
                "FAIL",
                f"{t.get('id')}: invalid harness shape {shape!r} (by-construction broken)",
            )
        if not (t.get("acceptance") or []):
            return ("FAIL", f"{t.get('id')}: empty acceptance (must be derived)")
        if not (t.get("owns") or t.get("unit_keys") or []):
            return ("FAIL", f"{t.get('id')}: empty owns/unit_keys")
    # Seat-prose half — claimtruth style (same bar as G1 at M3):
    # tokens that name a *model unit* must be in this story's dependency
    # closure (own units + depends_on*). Tooling words ignored; cross-story
    # deps (PetType on a repository task) are in-scope by construction.
    units_by_key = {
        str(u.get("key")): u for u in (model.get("units") or []) if u.get("key")
    }
    model_names: dict[str, str] = {}  # simple → key
    for key, u in units_by_key.items():
        simple = key.rsplit(".", 1)[-1]
        model_names[simple] = key
        lp = str(u.get("legacy_path") or "")
        if lp.endswith(".java"):
            model_names[Path(lp).stem] = key
    seed: set[str] = set()
    for st in model.get("stories") or []:
        if str(st.get("id") or "") != sid:
            continue
        for k in st.get("units") or []:
            seed.add(str(k))
    for t in tasks:
        for uk in t.get("unit_keys") or []:
            seed.add(str(uk))
    # depends_on closure (bounded)
    closure = set(seed)
    frontier = set(seed)
    for _ in range(max(8, len(units_by_key) + 2)):
        nxt: set[str] = set()
        for k in frontier:
            for d in (units_by_key.get(k) or {}).get("depends_on") or []:
                ds = str(d)
                if ds in units_by_key and ds not in closure:
                    closure.add(ds)
                    nxt.add(ds)
        frontier = nxt
        if not frontier:
            break
    story_names = {k.rsplit(".", 1)[-1] for k in closure}
    for t in tasks:
        for o in t.get("owns") or []:
            if str(o).endswith(".java"):
                story_names.add(Path(str(o)).stem)
    foreign: list[str] = []
    checked = 0
    for t in tasks:
        prose = f"{t.get('goal') or ''} {t.get('plan') or ''}"
        for tok in _JAVA_TYPE_TOKEN.findall(prose):
            if tok not in model_names:
                continue
            checked += 1
            if tok not in story_names:
                foreign.append(f"{t.get('id')}:{tok}")
    if foreign:
        sample = ", ".join(foreign[:6])
        return (
            "FAIL",
            f"{sid}: goal/plan names model units outside story+deps "
            f"({len(foreign)}): {sample}",
        )
    return (
        "PASS",
        f"{sid}: Shape/Acceptance/owns harness-derived; "
        f"goal/plan model-unit tokens in story+deps (checked={checked})",
    )


def g9_verdict(model: dict, sid: str) -> tuple[str, str]:
    """G9 — Goal↔Acceptance coherence (seat judgment vs derived acceptance)."""
    if story_state(model, sid) != "SPECIFIED":
        return ("NOT-LANDED", f"{sid}: UNSPECIFIED — G9 deferred until SPECIFIED")
    tasks = _tasks_for(model, sid)
    if not tasks:
        return ("NOT-LANDED", f"{sid}: no typed tasks")
    bad: list[str] = []
    ok_n = 0
    for t in tasks:
        goal = str(t.get("goal") or "").strip()
        if len(goal) < 8:
            bad.append(f"{t.get('id')}: empty/short goal")
            continue
        kinds = evidence_kinds_for_acceptance(
            t.get("acceptance") or [], task_kind=str(t.get("kind") or "")
        )
        role = str(t.get("role") or "").upper()
        if "staging_fact" in kinds or role == "HARVEST":
            if _HARVEST_BAD_GOAL.search(goal) and not _HARVEST_GOOD_GOAL.search(goal):
                bad.append(
                    f"{t.get('id')}: HARVEST/byte-fidelity acceptance but goal "
                    f"verbs create/design/implement (W4-560 §5 shape)"
                )
                continue
        ok_n += 1
    if bad:
        return ("FAIL", f"{sid}: {len(bad)} coherence FAIL — " + "; ".join(bad[:4]))
    return (
        "PASS",
        f"{sid}: Goal↔Acceptance coherent on {ok_n}/{len(tasks)} tasks",
    )


def _unit_for_task(model: dict, task: dict) -> Optional[dict]:
    for uk in task.get("unit_keys") or []:
        for u in model.get("units") or []:
            if u.get("key") == uk:
                return u
    return None


def _read(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def g10_verdict(root: Path, model: dict, sid: str) -> tuple[str, str]:
    """G10 — is M4 code derived from the M3 typed task acceptance?"""
    tasks = [t for t in _tasks_for(model, sid) if t.get("kind") != "characterize"]
    char_tasks = [t for t in _tasks_for(model, sid) if t.get("kind") == "characterize"]
    if not tasks and not char_tasks:
        return ("NOT-LANDED", f"{sid}: no typed tasks for G10")
    fails: list[str] = []
    passes = 0
    not_landed = 0
    for t in tasks:
        tid = str(t.get("id") or "?")
        u = _unit_for_task(model, t)
        target = ""
        staging = ""
        if u:
            target = str(u.get("target_path") or "")
            staging = str(u.get("staging_path") or "")
            if not staging and u.get("legacy_path"):
                staging = f"migration/staging/{u.get('legacy_path')}"
        tgt_path = root / target if target else None
        if not tgt_path or not tgt_path.is_file():
            not_landed += 1
            continue
        body = _read(tgt_path) or ""
        kinds = evidence_kinds_for_acceptance(
            t.get("acceptance") or [], task_kind=str(t.get("kind") or "")
        )
        role = str(t.get("role") or "").upper()
        if "staging_fact" in kinds or role == "HARVEST":
            stg_path = root / staging if staging else None
            if not stg_path or not stg_path.is_file():
                fails.append(f"{tid}: HARVEST target landed but staging missing")
                continue
            stg = _read(stg_path) or ""
            # Package rename only — compare LOC ±2 and serialVersionUID.
            loc_t = body.count("\n") + (0 if body.endswith("\n") else 1 if body else 0)
            loc_s = stg.count("\n") + (0 if stg.endswith("\n") else 1 if stg else 0)
            if abs(loc_t - loc_s) > 2:
                fails.append(f"{tid}: LOC drift target={loc_t} staging={loc_s}")
                continue
            suid_t = re.search(r"serialVersionUID\s*=\s*(-?\d+)L?", body)
            suid_s = re.search(r"serialVersionUID\s*=\s*(-?\d+)L?", stg)
            if suid_s and (not suid_t or suid_t.group(1) != suid_s.group(1)):
                fails.append(f"{tid}: serialVersionUID drift vs staging")
                continue
        if role == "REDESIGN" or "target_contract" in kinds:
            if _SPRING_JAVAX.search(body):
                fails.append(f"{tid}: spring/javax residue in REDESIGN target")
                continue
            if u and u.get("target_fqn"):
                pkg = ".".join(str(u["target_fqn"]).split(".")[:-1])
                if pkg and f"package {pkg}" not in body:
                    fails.append(f"{tid}: target package {pkg} not in file")
                    continue
        passes += 1
    for t in char_tasks:
        tid = str(t.get("id") or "?")
        # Characterization tests live under src/test — scan owns paths.
        found_test = False
        for o in t.get("owns") or []:
            p = root / str(o)
            if not p.is_file():
                # also try test tree by simple name
                continue
            found_test = True
            body = _read(p) or ""
            if _PLACEHOLDER_ASSERT.search(body):
                fails.append(f"{tid}: G-PLACE ceremonial assert in {o}")
        if not found_test:
            # Scan recent test files mentioning task title tokens — soft.
            not_landed += 1
            continue
        passes += 1
    if fails:
        return (
            "FAIL",
            f"{sid}: G10 FAIL {len(fails)} — " + "; ".join(fails[:5]),
        )
    if passes == 0 and not_landed > 0:
        return (
            "NOT-LANDED",
            f"{sid}: no M4 targets on disk yet (pending={not_landed})",
        )
    return (
        "PASS",
        f"{sid}: code matches typed acceptance on {passes} task(s) "
        f"(pending_files={not_landed})",
    )


def _load_model(root: Path) -> dict:
    p = root / "migration" / "model.json"
    if not p.is_file():
        raise SystemExit(f"ground_chain: missing {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("g4", "g5", "g9", "g10", "kinds"))
    ap.add_argument("--root", default=".")
    ap.add_argument("--sid", default="")
    ap.add_argument("--block-file", default="")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if args.cmd == "g4":
        block = Path(args.block_file).read_text(encoding="utf-8") if args.block_file else sys.stdin.read()
        model = _load_model(root) if (root / "migration" / "model.json").is_file() else {}
        kinds = story_evidence_kinds(model, args.sid) if args.sid else ["derived"]
        status, detail = g4_verdict(block, kinds)
        print(f"{status}\t{detail}")
        return 0 if status == "PASS" else 1
    model = _load_model(root)
    sid = args.sid
    if not sid:
        raise SystemExit("ground_chain: --sid required")
    if args.cmd == "kinds":
        print(",".join(story_evidence_kinds(model, sid)))
        return 0
    if args.cmd == "g10":
        status, detail = g10_verdict(root, model, sid)
    elif args.cmd == "g5":
        status, detail = g5_verdict(model, sid)
    else:
        status, detail = g9_verdict(model, sid)
    print(f"{status}\t{detail}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
