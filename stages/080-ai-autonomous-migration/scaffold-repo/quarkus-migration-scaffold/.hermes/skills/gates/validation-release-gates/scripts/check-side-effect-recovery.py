#!/usr/bin/env python3
"""AD-H §18.3 — side-effect recovery boundaries (external review finding 6).

When migration/recovery/*.json (or verdict recovery blocks) exist, each must
declare: side_effect_class, terminal_record, replay_digest, reset_rule.
Re-queue alone is insufficient — workspace restore must be named.

Idle when no recovery claims present.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = ("side_effect_class", "terminal_record", "replay_digest", "reset_rule")


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    claims: list[tuple[str, dict]] = []
    rdir = root / "migration" / "recovery"
    if rdir.is_dir():
        for path in sorted(rdir.glob("*.json")):
            for obj in load_items(path):
                if isinstance(obj, dict):
                    claims.append((str(path.relative_to(root)), obj))
    vdir = root / "migration" / "verdicts"
    if vdir.is_dir():
        for path in sorted(vdir.glob("*.json")):
            for obj in load_items(path):
                if isinstance(obj, dict) and isinstance(obj.get("side_effect_recovery"), dict):
                    claims.append(
                        (str(path.relative_to(root)) + "#side_effect_recovery", obj["side_effect_recovery"])
                    )

    if not claims:
        print("OK: no side-effect recovery claims — §18.3 gate idle")
        return 0

    bad = 0
    for label, obj in claims:
        for field in REQUIRED:
            if obj.get(field) in (None, ""):
                print(
                    f"FAIL: {label}: missing {field} "
                    f"(requeue≠workspace restore; finding 6)",
                    file=sys.stderr,
                )
                bad = 1
        if obj.get("requeue_only") in (True, "true", "yes", 1):
            print(
                f"FAIL: {label}: requeue_only=true insufficient (finding 6)",
                file=sys.stderr,
            )
            bad = 1
    if bad:
        return 1
    print(f"OK: side-effect recovery boundaries ({len(claims)} claim(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
