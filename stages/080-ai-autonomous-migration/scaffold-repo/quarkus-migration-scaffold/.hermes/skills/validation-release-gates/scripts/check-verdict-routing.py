#!/usr/bin/env python3
"""AD-H §18 / §18.0 — verdict routing + provisional/full ACCEPT composition.

Looks under migration/verdicts/*.json and migration/preflight/*.json.
Idle (exit 0) when no verdict artifacts exist.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

VALID_ROUTING = {
    "REFUSE": {
        "auto_fix",
        "retry",
        "fix_session",
        "requeue",
        "reopen_story",
        "blocked",
        "human",
        "human_queue",
    },
    "INCONCLUSIVE": {
        "human",
        "human_queue",
        "blocked",
        "steerer",
        "reopen_story",
    },
    "ACCEPT": {"advance", "ship", "close", "none", ""},
}


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def truthy(v: object) -> bool:
    return v in (True, "true", "yes", 1)


def check_composition(label: str, obj: dict) -> int:
    """AD-H §18.0 provisional vs full + kill-ratio interim."""
    bad = 0
    phase = str(obj.get("phase") or "").upper()
    verdict = str(obj.get("verdict") or obj.get("gate_verdict") or "").upper()
    kind = str(obj.get("accept_kind") or obj.get("acceptKind") or "").lower()
    ship = truthy(obj.get("ship")) or str(obj.get("status") or "").lower() in {
        "shipped",
        "released",
        "merged_main",
    }
    kill = str(obj.get("g1_kill_ratio") or obj.get("g1KillRatio") or "").lower()
    pinned = truthy(obj.get("g1_kill_ratio_threshold_pinned"))
    waiver = truthy(obj.get("g1_kill_ratio_waiver")) or (
        isinstance(obj.get("operator_waiver"), dict)
        and truthy(obj["operator_waiver"].get("g1_kill_ratio"))
    )
    routing = str(obj.get("routing") or obj.get("failure_class") or "").lower().replace(
        "-", "_"
    )
    prior = str(obj.get("prior_accept_kind") or "").lower()
    gate = str(obj.get("gate") or obj.get("failed_gate") or "").lower()

    if verdict == "ACCEPT":
        if phase == "M4":
            if kind != "provisional":
                print(
                    f"FAIL: {label}: M4 ACCEPT requires accept_kind=provisional (AD-H §18.0)",
                    file=sys.stderr,
                )
                bad = 1
            if ship:
                print(
                    f"FAIL: {label}: provisional M4 ACCEPT must never ship (AD-H §18.0)",
                    file=sys.stderr,
                )
                bad = 1
            if kill == "pass" and not pinned:
                print(
                    f"FAIL: {label}: g1_kill_ratio=PASS forbidden until threshold pinned "
                    f"(AD-H §18.0 option A)",
                    file=sys.stderr,
                )
                bad = 1
            if kill and kill not in {"pending_threshold", "pass"}:
                print(
                    f"FAIL: {label}: unknown g1_kill_ratio={kill!r}",
                    file=sys.stderr,
                )
                bad = 1
        elif phase == "M5":
            if kind != "full":
                print(
                    f"FAIL: {label}: M5 ACCEPT requires accept_kind=full (AD-H §18.0)",
                    file=sys.stderr,
                )
                bad = 1
            if kind == "provisional":
                print(
                    f"FAIL: {label}: M5 must not record provisional ACCEPT",
                    file=sys.stderr,
                )
                bad = 1
            # Full ACCEPT: kill-ratio PASS+pinned OR typed waiver (interim option A)
            if kill == "pass" and not pinned:
                print(
                    f"FAIL: {label}: g1_kill_ratio=PASS without threshold pin (AD-H §18.0)",
                    file=sys.stderr,
                )
                bad = 1
            if kind == "full" and kill in {"", "pending_threshold"} and not waiver:
                print(
                    f"FAIL: {label}: M5 full ACCEPT needs g1_kill_ratio PASS "
                    f"(threshold pinned) or g1_kill_ratio_waiver (AD-H §18.0)",
                    file=sys.stderr,
                )
                bad = 1
            if ship and kind != "full":
                print(
                    f"FAIL: {label}: ship requires accept_kind=full",
                    file=sys.stderr,
                )
                bad = 1

    # Composition re-open: M5 G-4 fail after provisional → reopen_story / blocked
    if (
        phase == "M5"
        and verdict in {"REFUSE", "INCONCLUSIVE"}
        and (prior == "provisional" or "g4" in gate)
        and prior == "provisional"
    ):
        if routing not in {"reopen_story", "blocked", "human", "human_queue", "steerer"}:
            print(
                f"FAIL: {label}: M5 G-4 fail after provisional requires "
                f"routing=reopen_story|blocked (got {routing!r}; AD-H §18.0)",
                file=sys.stderr,
            )
            bad = 1

    return bad


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
            # Skip pure factory claims without a gate verdict
            verdict = str(obj.get("verdict") or obj.get("gate_verdict") or "").upper()
            if not verdict and str(obj.get("phase") or "").upper() == "FACTORY":
                continue
            if not verdict:
                # preflight without verdict — ignore for routing
                if "verdict" not in obj and "gate_verdict" not in obj:
                    continue
            checked += 1
            label = rel if len(items) == 1 else f"{rel}[{i}]"
            routing = str(obj.get("routing") or obj.get("failure_class") or "").lower().replace(
                "-", "_"
            )
            ship = truthy(obj.get("ship")) or str(obj.get("status") or "").lower() in {
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
                if verdict != "ACCEPT" and routing not in allowed:
                    print(
                        f"FAIL: {label}: verdict={verdict} routing={routing!r} "
                        f"not in {sorted(allowed)} (AD-H §18)",
                        file=sys.stderr,
                    )
                    bad = 1

            if str(obj.get("failure_class") or "").lower() == "block_wave" and routing in {
                "auto_fix",
                "retry",
                "fix_session",
            }:
                print(f"FAIL: {label}: wave block must not auto_fix", file=sys.stderr)
                bad = 1

            bad |= check_composition(label, obj)

    if bad:
        print(f"Verdict-routing checks FAILED ({checked} artifact(s)).", file=sys.stderr)
        return 1
    print(f"OK: verdict-routing checks passed ({checked} artifact(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
