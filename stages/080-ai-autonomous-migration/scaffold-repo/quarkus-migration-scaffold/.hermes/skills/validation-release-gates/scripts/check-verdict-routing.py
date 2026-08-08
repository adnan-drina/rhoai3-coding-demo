#!/usr/bin/env python3
"""AD-H §18 — cheap refuse of bad failure routing / INCONCLUSIVE-as-ship.

Looks under migration/verdicts/*.json and migration/preflight/*.json.
Idle (exit 0) when no verdict artifacts exist.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

VALID_ROUTING = {
    "REFUSE": {"auto_fix", "retry", "fix_session", "requeue"},
    "INCONCLUSIVE": {"human", "human_queue", "blocked", "steerer"},
    "ACCEPT": {"advance", "ship", "close", "none", ""},
}


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    files: list[Path] = []
    for d in (root / "migration/verdicts", root / "migration/preflight"):
        if d.is_dir():
            files.extend(sorted(d.glob("*.json")))
    if not files:
        print("OK: no verdict/preflight artifacts — routing lint idle")
        return 0

    bad = 0
    checked = 0
    for path in files:
        rel = str(path.relative_to(root))
        try:
            items = load_items(path)
        except Exception as e:
            print(f"FAIL: {rel}: {e}", file=sys.stderr)
            bad = 1
            continue
        for i, obj in enumerate(items):
            if not isinstance(obj, dict):
                continue
            checked += 1
            label = rel if len(items) == 1 else f"{rel}[{i}]"
            verdict = str(obj.get("verdict") or obj.get("gate_verdict") or "").upper()
            routing = str(obj.get("routing") or obj.get("failure_class") or "").lower().replace("-", "_")
            ship = obj.get("ship") in (True, "true", "yes", 1) or str(obj.get("status") or "").lower() in {
                "shipped",
                "released",
                "merged_main",
            }

            if not verdict:
                print(f"FAIL: {label}: missing verdict", file=sys.stderr)
                bad = 1
                continue

            if verdict == "INCONCLUSIVE" and ship:
                print(f"FAIL: {label}: INCONCLUSIVE must never ship (AD-H §18)", file=sys.stderr)
                bad = 1

            if ship and verdict != "ACCEPT":
                print(f"FAIL: {label}: ship requires ACCEPT, got {verdict}", file=sys.stderr)
                bad = 1

            if verdict in VALID_ROUTING and routing:
                allowed = VALID_ROUTING[verdict]
                # ACCEPT may omit routing
                if verdict != "ACCEPT" and routing not in allowed:
                    print(
                        f"FAIL: {label}: verdict={verdict} routing={routing!r} "
                        f"not in {sorted(allowed)} (AD-H §18)",
                        file=sys.stderr,
                    )
                    bad = 1

            # wave_block must not auto_fix
            if str(obj.get("failure_class") or "").lower() == "block_wave" and routing in {
                "auto_fix",
                "retry",
                "fix_session",
            }:
                print(f"FAIL: {label}: wave block must not auto_fix", file=sys.stderr)
                bad = 1

    if bad:
        print(f"Verdict-routing checks FAILED ({checked} artifact(s)).", file=sys.stderr)
        return 1
    print(f"OK: verdict-routing checks passed ({checked} artifact(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
