#!/usr/bin/env python3
"""Architect E-104925Z / E-110403Z — M3 bodies must carry measured operand_count."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

DEFAULT_MAX = 40
HIGH_MAX = 80
# Proving-min wall-fit (Architect E-111450Z): refuse undecomposed scopes whose
# estimated runtime exceeds budget. Tuned so 60@3600 refuses while completed
# M3 stories (~35@2700 / 34@3600) still pass. Not a claim of measured rate.
SECONDS_PER_OPERAND = 75
DEFAULT_BUDGET_SEC = 2700
HIGH_BUDGET_SEC = 3600


def normalize_dest(item: Any) -> Optional[str]:
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
    if not p.startswith("src/"):
        return None
    return p


def measured_operands(body: dict) -> list[str]:
    out: list[str] = []
    for key in ("files_writable", "filesWritable", "files_in_scope", "filesInScope"):
        items = body.get(key) or []
        if not isinstance(items, list) or not items:
            continue
        for item in items:
            p = normalize_dest(item)
            if p and p not in out:
                out.append(p)
        if key in ("files_writable", "filesWritable") and out:
            return out
    return out


def max_for(body: dict) -> int:
    effort = str(body.get("effort_class") or "").strip().lower()
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
    for d in (root / "migration/bodies", root / "migration/tasks"):
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
    measured = measured_operands(body)
    if not measured:
        print(f"BODY_SIZE: {label}: no measurable dest src/ operands", file=sys.stderr)
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
            f"(effort_class={body.get('effort_class')!r}) — decompose; "
            f"do not raise wall (Architect E-104925Z)",
            file=sys.stderr,
        )
        return 1
    if wall_fit:
        budget = budget_sec(body)
        estimated = len(measured) * SECONDS_PER_OPERAND
        if estimated > budget:
            print(
                f"BODY_SIZE: {label}: wall-fit refuse "
                f"estimated={estimated}s ({len(measured)}×{SECONDS_PER_OPERAND}s) "
                f"> budget={budget}s — decompose (Architect E-111450Z / §3b units>wall); "
                f"do not raise wall",
                file=sys.stderr,
            )
            return 1
        print(
            f"OK: {label} operand_count={raw} measured={len(measured)} "
            f"max={cap} wall-fit estimated={estimated}s<=budget={budget}s"
        )
    else:
        print(f"OK: {label} operand_count={raw} measured={len(measured)} max={cap}")
    return 0


def main() -> int:
    wall_fit = "--wall-fit" in sys.argv[1:]
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
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
