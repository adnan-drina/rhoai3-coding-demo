#!/usr/bin/env python3
"""Architect E-104925Z / E-110403Z — M3 bodies must carry measured operand_count.

Lints every M3 body under `<root>/evidence/bodies` and `<root>/evidence/tasks`,
or only the body files named after ROOT (create-m3 passes the single body it is
about to mint).

Usage:
  python3 check-operand-count.py .
  python3 check-operand-count.py . evidence/bodies/m3-s-010.json --wall-fit
  python3 check-operand-count.py /projects/modernized BODY.json --wall-fit --v13
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

EXIT_CODES = """Exit codes:
  0  pass — every M3 body carries a measured operand_count within cap (and
     within wall budget under --wall-fit), or idle (no M3 bodies)
  1  BLOCK — BODY_SIZE refusal: no measurable dest operands, sizing_basis not
     'operand_count', operand_count missing/mismatched, over cap, dual-stack
     JPA+JDBC split required, or wall-fit estimate over budget
  2  usage / harness defect (bad or unknown argument)
"""

DEFAULT_MAX = 40
HIGH_MAX = 80
# W4 / AD-014 (Operator E-133805Z): v13 mint target FIS ≤ ~5 + parent-chain.
V13_DEFAULT_MAX = 5
V13_HIGH_MAX = 8
# build_config (pom.xml / resources) — small scopes; separate class (Operator E-124000Z)
BUILD_CONFIG_MAX = 12
BUILD_CONFIG_HIGH_MAX = 20
# Proving-min wall-fit (Architect E-111450Z / R-M3.9 E-20260810T184700Z):
# refuse undecomposed scopes whose estimated runtime exceeds budget.
# Tuned from v11 S-003 #20 timed_out (~86s/file observed at 42 FIS@3600) —
# 75s/op admitted 42×75=3150≤3600 and still wall-exhausted. Prefer split
# (JPA-repos vs JDBC-repos) over blind wall raise.
SECONDS_PER_OPERAND = 90
SECONDS_PER_OPERAND_BUILD_CONFIG = 180
DEFAULT_BUDGET_SEC = 2700
HIGH_BUDGET_SEC = 3600
# Dual-stack repository stories (JPA + JDBC impl trees) at FIS≥20 must split.
DUAL_STACK_SPLIT_MIN = 20

OPERAND_CLASS_SRC = "src_code"
OPERAND_CLASS_BUILD = "build_config"


def operand_class(body: dict) -> str:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    raw = str(ident.get("operand_class") or OPERAND_CLASS_SRC).strip().lower()
    if raw in {"build_config", "build-config", "config", "pom"}:
        return OPERAND_CLASS_BUILD
    return OPERAND_CLASS_SRC


def normalize_dest(item: Any, *, oclass: str = OPERAND_CLASS_SRC) -> Optional[str]:
    if isinstance(item, str):
        p = item
    elif isinstance(item, dict):
        p = (
            item.get("dest")
            or item.get("dst")
            or item.get("destination")
            or item.get("src")
            or ""
        )
    else:
        return None
    p = str(p).replace("\\", "/")
    if "/projects/modernized/" in p:
        p = p.split("/projects/modernized/", 1)[1]
    if "/.derived/" in p or p.startswith("projects/legacy"):
        return None
    if oclass == OPERAND_CLASS_BUILD:
        # Build-system / config stories (Operator E-20260811T124000Z)
        if p == "pom.xml" or p.endswith("/pom.xml"):
            return "pom.xml" if p.endswith("pom.xml") else p
        if p.startswith("src/main/resources/") or p.startswith("src/test/resources/"):
            return p
        return None
    if not p.startswith("src/"):
        return None
    return p


def measured_operands(body: dict) -> list[str]:
    oclass = operand_class(body)
    out: list[str] = []
    for key in ("files_writable", "filesWritable", "files_in_scope", "filesInScope"):
        items = body.get(key) or []
        if not isinstance(items, list) or not items:
            continue
        for item in items:
            p = normalize_dest(item, oclass=oclass)
            if p and p not in out:
                out.append(p)
        if key in ("files_writable", "filesWritable") and out:
            return out
    return out


def max_for(body: dict) -> int:
    effort = str(body.get("effort_class") or "").strip().lower()
    if operand_class(body) == OPERAND_CLASS_BUILD:
        if effort in {"high", "effort-high", "effort_high"}:
            return BUILD_CONFIG_HIGH_MAX
        return BUILD_CONFIG_MAX
    if effort in {"high", "effort-high", "effort_high"}:
        return HIGH_MAX
    return DEFAULT_MAX


def budget_sec(body: dict) -> int:
    raw = body.get("runtime_budget_sec")
    if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
        return raw
    effort = str(body.get("effort_class") or "").strip().lower()
    if effort in {"high", "effort-high", "effort_high"}:
        return HIGH_BUDGET_SEC
    return DEFAULT_BUDGET_SEC


def seconds_per_operand(body: dict) -> int:
    if operand_class(body) == OPERAND_CLASS_BUILD:
        return SECONDS_PER_OPERAND_BUILD_CONFIG
    return SECONDS_PER_OPERAND

def load_bodies(root: Path, only: list[Path]) -> list[tuple[str, dict]]:
    if only:
        out = []
        for p in only:
            data = json.loads(p.read_text(encoding="utf-8"))
            body = data.get("body") if isinstance(data.get("body"), dict) else data
            if isinstance(body, dict) and str(body.get("phase") or "").upper() == "M3":
                out.append((str(p), body))
        return out
    out = []
    for d in (root / "evidence/bodies", root / "evidence/tasks"):
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            if path.name.endswith(".sha256.json"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            body = data.get("body") if isinstance(data.get("body"), dict) else data
            if isinstance(body, dict) and str(body.get("phase") or "").upper() == "M3":
                out.append((str(path.relative_to(root)), body))
    return out


def check_one(label: str, body: dict, *, wall_fit: bool) -> int:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    oclass = operand_class(body)
    measured = measured_operands(body)
    if not measured:
        hint = (
            "pom.xml or src/main|test/resources/**"
            if oclass == OPERAND_CLASS_BUILD
            else "src/**"
        )
        print(
            f"BODY_SIZE: {label}: no measurable dest operands "
            f"(operand_class={oclass}; expect {hint})",
            file=sys.stderr,
        )
        return 1
    basis = str(ident.get("sizing_basis") or "").strip()
    if basis != "operand_count":
        print(
            f"BODY_SIZE: {label}: identity.sizing_basis must be 'operand_count' "
            f"(got {basis!r}; phase-name sizing REJECT)",
            file=sys.stderr,
        )
        return 1
    raw = ident.get("operand_count")
    if not isinstance(raw, int) or isinstance(raw, bool) or raw < 1:
        print(
            f"BODY_SIZE: {label}: identity.operand_count required int>=1 "
            f"(got {raw!r})",
            file=sys.stderr,
        )
        return 1
    if raw != len(measured):
        print(
            f"BODY_SIZE: {label}: operand_count={raw} != measured={len(measured)}",
            file=sys.stderr,
        )
        return 1
    cap = max_for(body)
    if len(measured) > cap:
        print(
            f"BODY_SIZE: {label}: measured={len(measured)} > max={cap} "
            f"(effort_class={body.get('effort_class')!r}; "
            f"operand_class={oclass}) — decompose; "
            f"do not raise wall (Architect E-104925Z)",
            file=sys.stderr,
        )
        return 1
    if wall_fit:
        budget = budget_sec(body)
        spo = seconds_per_operand(body)
        estimated = len(measured) * spo
        paths_l = [p.lower() for p in measured]
        has_jpa = any("/jpa/" in p or p.endswith("/jpa") for p in paths_l)
        has_jdbc = any("/jdbc/" in p or p.endswith("/jdbc") for p in paths_l)
        if (
            oclass == OPERAND_CLASS_SRC
            and has_jpa
            and has_jdbc
            and len(measured) >= DUAL_STACK_SPLIT_MIN
        ):
            print(
                f"BODY_SIZE: {label}: R-M3.9 dual-stack refuse — "
                f"JPA+JDBC repository trees with measured={len(measured)}≥"
                f"{DUAL_STACK_SPLIT_MIN} — split into JPA-repos vs JDBC-repos "
                f"cards (Architect E-20260810T184700Z); do not raise wall",
                file=sys.stderr,
            )
            return 1
        if estimated > budget:
            print(
                f"BODY_SIZE: {label}: wall-fit refuse "
                f"estimated={estimated}s ({len(measured)}×{spo}s) "
                f"> budget={budget}s — decompose (Architect E-111450Z / R-M3.9); "
                f"prefer JPA vs JDBC split (src_code) or split config packs "
                f"(build_config); do not raise wall alone",
                file=sys.stderr,
            )
            return 1
        print(
            f"OK: {label} operand_class={oclass} operand_count={raw} "
            f"measured={len(measured)} max={cap} "
            f"wall-fit estimated={estimated}s<=budget={budget}s"
        )
    else:
        print(
            f"OK: {label} operand_class={oclass} operand_count={raw} "
            f"measured={len(measured)} max={cap}"
        )
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="product root containing evidence/bodies + evidence/tasks (default: .)",
    )
    ap.add_argument(
        "bodies",
        nargs="*",
        help="optional body JSON paths (absolute, or relative to ROOT) — "
        "restricts the lint to those bodies; non-existent paths are ignored",
    )
    ap.add_argument(
        "--wall-fit",
        action="store_true",
        help="also refuse scopes whose estimated runtime exceeds runtime_budget_sec",
    )
    ap.add_argument(
        "--v13",
        action="store_true",
        help="apply the v13 mint caps (default max 5, effort-high max 8)",
    )
    parsed = ap.parse_args()
    wall_fit = parsed.wall_fit
    if parsed.v13:
        global DEFAULT_MAX, HIGH_MAX
        DEFAULT_MAX = V13_DEFAULT_MAX
        HIGH_MAX = V13_HIGH_MAX
    args = [parsed.root, *parsed.bodies]
    root = Path(args[0] if args else ".").resolve()
    only: list[Path] = []
    for a in args[1:]:
        p = Path(a)
        if not p.is_absolute():
            p = (root / p).resolve() if (root / p).is_file() else p.resolve()
        if p.is_file():
            only.append(p)
    bodies = load_bodies(root, only)
    if not bodies:
        print("OK: BODY_SIZE idle (no M3 bodies)")
        return 0
    bad = 0
    for label, body in bodies:
        bad |= check_one(label, body, wall_fit=wall_fit)
    if bad:
        print("BODY_SIZE operand-count checks FAILED", file=sys.stderr)
        return 1
    print(f"OK: BODY_SIZE operand-count ({len(bodies)} M3 body(ies))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
