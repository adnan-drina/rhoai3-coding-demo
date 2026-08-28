#!/usr/bin/env python3
"""AD-H §18.0 ¶4 — derive shared-substrate re-open set from §11.3 closures.

Usage:
  compute-substrate-reopen.py <root> [--check verdict.json]
  compute-substrate-reopen.py <root> --implicated a,b --print

Closure map: evidence/slices/closure-map.json
{
  "stories": {
    "S-1": {"closure": ["com.example.Entity", "src/Foo.java"]},
    "S-2": {"closure": ["com.example.Entity"]}
  },
  "accept_state": {
    "S-1": "PROVISIONAL_ACCEPT",
    "S-2": "ACCEPT"
  }
}

Re-open = every story that is NOT full ACCEPT whose closure intersects
implicated_substrate. Missing map → exit 2 (caller treats as INCONCLUSIVE/blocked).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


FULL_ACCEPT = {"ACCEPT", "FULL_ACCEPT", "FULL"}


def load_closure_map(root: Path) -> dict | None:
    path = root / "evidence/slices/closure-map.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_state(v: str) -> str:
    return str(v or "").upper().replace("-", "_")


def is_full_accept(state: str) -> bool:
    s = normalize_state(state)
    return s in FULL_ACCEPT


def compute_reopen(
    closure_map: dict, implicated: list[str], failing_story: str | None = None
) -> list[str]:
    implicated_set = {str(x) for x in implicated if x}
    stories = closure_map.get("stories") or {}
    states = closure_map.get("accept_state") or {}
    reopen: list[str] = []
    for sid, meta in stories.items():
        if is_full_accept(str(states.get(sid) or "")):
            continue
        closure = set()
        if isinstance(meta, dict):
            closure = {str(x) for x in (meta.get("closure") or [])}
        elif isinstance(meta, list):
            closure = {str(x) for x in meta}
        if closure & implicated_set:
            reopen.append(str(sid))
    # failing story with provisional always included if listed
    if failing_story and failing_story not in reopen:
        if not is_full_accept(str(states.get(failing_story) or "PROVISIONAL_ACCEPT")):
            reopen.append(failing_story)
    return sorted(reopen)


def main() -> int:
    ap = argparse.ArgumentParser(description="§18.0¶4 substrate re-open set")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--check", metavar="VERDICT_JSON", help="validate reopen_story_ids")
    ap.add_argument("--implicated", help="comma-separated path/FQN list")
    ap.add_argument("--failing-story", default="")
    ap.add_argument("--print", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    cmap = load_closure_map(root)
    if cmap is None:
        print(
            "INCONCLUSIVE: missing evidence/slices/closure-map.json "
            "(AD-H §18.0 ¶4 — do not invent a smaller set)",
            file=sys.stderr,
        )
        return 2

    if args.check:
        path = Path(args.check)
        if not path.is_file():
            path = root / args.check
        obj = json.loads(path.read_text(encoding="utf-8"))
        implicated = obj.get("implicated_substrate") or obj.get("implicatedSubstrate") or []
        if not isinstance(implicated, list) or not implicated:
            print(
                f"FAIL: {path}: shared-substrate claim needs implicated_substrate[]",
                file=sys.stderr,
            )
            return 1
        failing = str(obj.get("story_id") or obj.get("failing_story_id") or args.failing_story)
        expected = compute_reopen(cmap, [str(x) for x in implicated], failing or None)
        got = obj.get("reopen_story_ids") or obj.get("reopenStoryIds")
        if got is None:
            print(
                f"FAIL: {path}: missing reopen_story_ids (derived set required)",
                file=sys.stderr,
            )
            return 1
        got_list = sorted(str(x) for x in got)
        if got_list != expected:
            print(
                f"FAIL: {path}: reopen_story_ids={got_list} != computed {expected} "
                f"(AD-H §18.0 ¶4)",
                file=sys.stderr,
            )
            return 1
        print(f"OK: reopen_story_ids match closure ∩ substrate ({expected})")
        return 0

    if args.implicated is None:
        print("usage: provide --implicated or --check", file=sys.stderr)
        return 1
    implicated = [x.strip() for x in args.implicated.split(",") if x.strip()]
    reopen = compute_reopen(cmap, implicated, args.failing_story or None)
    if args.print:
        print(json.dumps({"reopen_story_ids": reopen}, indent=2))
    else:
        print(",".join(reopen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
