#!/usr/bin/env python3
"""ADR-29 — mechanical PROFILE closer (no LLM).

After an LLM PROFILE seat (and before spending attempt-2):

1. Apply migration/profile-decisions.json → model.units[].decision (SoT).
2. Strip genassert / build-owned decisions from the model.
3. Render architecture-profile.md §7 FROM the model (one-way — never harvest).

Exit 0 always (closer is best-effort). Prints CLOSE: lines for the outer log.
Usage: profile_close.py <architecture-profile.md> [--root DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _sec7_span(text: str) -> tuple[int, int]:
    import re

    m = re.search(r"^(#{2,6})[ \t]+.*class role.*$", text, re.M | re.I)
    if not m:
        return -1, -1
    level = len(m.group(1))
    start = m.end()
    rest = text[start:]
    nxt = re.search(r"^#{1," + str(level) + r"}[ \t]", rest, re.M)
    end = start + (nxt.start() if nxt else len(rest))
    return start, end


def close_profile(path: Path, root: Path) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from profile_roles import (  # type: ignore
        _GENASSERT,
        _load_model,
        _save_model,
        apply_declared_target_contracts,
        apply_decisions,
        render_sec7,
    )

    # 1) Seat JSON / in-model edits → SoT
    apply_decisions(root)
    print("CLOSE:adr29 applied profile-decisions.json → model.units[].decision")

    # 2) Clear build-owned decisions (MapperImpl / generated-sources)
    model = _load_model(root)
    cleared = 0
    for u in model.get("units") or []:
        blob = f"{u.get('legacy_fqn') or ''} {u.get('legacy_path') or ''}"
        if _GENASSERT.search(blob) and u.get("decision"):
            u["decision"] = None
            cleared += 1
    if cleared:
        _save_model(root, model)
        print(f"CLOSE:genassert cleared {cleared} build-owned decision(s) on model")

    # 2b) O-PROFTCHARDPIN (b) — declared policy onto typed REDESIGN surface units
    apply_declared_target_contracts(root)

    # 3) One-way render §7 (F-render-oneway) — hard-pins are declared-policy view
    render_sec7(root, profile=str(path))
    print(
        "CLOSE:adr29 §7 (Class Roles & Target Contract) rendered from model "
        "(no markdown harvest)"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ADR-29 mechanical PROFILE closer")
    ap.add_argument("profile")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    return close_profile(Path(args.profile), Path(args.root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
