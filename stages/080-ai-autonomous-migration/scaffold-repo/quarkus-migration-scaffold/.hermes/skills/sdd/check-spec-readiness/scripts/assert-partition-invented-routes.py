#!/usr/bin/env python3
"""Refuse a partition whose stories name HTTP routes the legacy app does not have.

`constitution.md` VII names this checker; it was never built. dest-5's
`T020_POLISH` claimed no endpoint and existed to test `GET /q/health` — the
legacy app has **one** entry point and **zero** health mentions — so it invented
scope, could not satisfy its own acceptance, and shipped a failing test
(Operator E-20260825T201440ZO).

Coverage is one-directional: it reports inventory rows with no story
(`endpoints_uncovered`). It has no concept of a story with no inventory. This is
the other direction.

Predicate (Architect E-20260825T202337ZA; join is ``http_join``,
Operator E-20260826T062245ZO):
  every HTTP path named in a story's `endpoints`, acceptance criteria, or the
  tests it may write must be a row in entry-point-inventory.json. An empty
  `endpoints` list is legal for scaffolding **iff** the story names no HTTP path
  anywhere. `/q/health` is not a grounding exception. `/api` + inventory path
  is dest layering (same helper as ``check-partition-coverage``). Do not keep a
  second ``dest_root_path()`` join here.

Exit codes:
  0  every named route is grounded, or the partition names no routes
  1  REFUSE — a story names a route absent from the inventory
  2  usage / harness defect (unreadable inputs are fail-closed, not idle)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# A route token: /segment, optionally with more segments. Excludes bare "/" and
# anything that looks like a file path (has a dot in the last segment).
ROUTE = re.compile(r"(?<![\w.])/(?!/)[A-Za-z0-9_][A-Za-z0-9_\-/{}]*")
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from http_join import inventory_http_paths, invented_route_gaps  # noqa: E402


def _norm(path: str) -> str:
    p = "/" + path.strip().strip("/")
    return p.rstrip("/") or "/"


def _looks_like_file(tok: str) -> bool:
    last = tok.rstrip("/").rsplit("/", 1)[-1]
    return "." in last


def routes_in(text: str) -> set[str]:
    found = set()
    for m in ROUTE.finditer(text or ""):
        tok = m.group(0)
        if _looks_like_file(tok):
            continue
        found.add(_norm(tok))
    return found


def story_routes(story: dict) -> set[str]:
    """Every HTTP path this story names, from endpoints and acceptance text."""
    found: set[str] = set()
    for ep in story.get("endpoints") or []:
        s = str(ep).strip()
        for meth in METHODS:
            if s.upper().startswith(meth + " "):
                s = s[len(meth) + 1 :].strip()
                break
        found |= routes_in(s)
    blob: list[str] = []
    for key in ("acceptance_criteria", "acceptance", "ac", "title", "notes"):
        v = story.get(key)
        if v:
            blob.append(json.dumps(v) if not isinstance(v, str) else v)
    found |= routes_in(" ".join(blob))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--partition", default=None,
                    help="default: evidence/partition.json, then evidence/briefs/partition.json")
    ap.add_argument("--inventory", default="evidence/entry-point-inventory.json")
    args = ap.parse_args()
    root = Path(args.root)

    if args.partition:
        part = root / args.partition if not Path(args.partition).is_absolute() else Path(args.partition)
    else:
        part = next((root / c for c in ("evidence/partition.json",
                                        "evidence/briefs/partition.json")
                     if (root / c).is_file()), root / "evidence/partition.json")
    inv_p = root / args.inventory

    # Fail closed: a missing input is not "no invented routes".
    for label, p in (("partition", part), ("inventory", inv_p)):
        if not p.is_file():
            print(f"REFUSE: INVENTED_ROUTES missing {label} at {p} "
                  f"(fail-closed; absence is not evidence)", file=sys.stderr)
            return 1
    try:
        partition = json.loads(part.read_text(encoding="utf-8"))
        inventory = json.loads(inv_p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"REFUSE: INVENTED_ROUTES unreadable input: {exc}", file=sys.stderr)
        return 1

    stories = [s for s in (partition.get("stories") or []) if isinstance(s, dict)]
    named = 0
    for story in stories:
        named += len(story_routes(story))

    # Same join as check-partition-coverage (Operator 062245ZO). Do not reintroduce
    # dest_root_path() here — http_join already proved /api + inventory is dest
    # layering; dest-6 stale AC is stale_ac, not this gate.
    gaps = invented_route_gaps(root, stories, inventory)
    invented: list[tuple[str, str]] = []
    for gap in gaps:
        if not gap.startswith("invented_route:"):
            continue
        rest = gap[len("invented_route:") :]
        sid, _, path = rest.partition(":")
        invented.append((sid, path))

    if invented:
        inv_paths = inventory_http_paths(inventory)
        print("REFUSE: INVENTED_ROUTES a story names a route the legacy app "
              "does not expose:", file=sys.stderr)
        for sid, r in invented:
            print(f"  - {sid}: {r}", file=sys.stderr)
        print(f"  grounded routes in entry-point-inventory.json: "
              f"{sorted(inv_paths) or '(none)'}", file=sys.stderr)
        print("  Remedy: drop the story, or ground it in a real entry point. "
              "Migration covers what the source has; it does not add features.",
              file=sys.stderr)
        return 1

    print(f"OK: assert-partition-invented-routes ({named} route mention(s) "
          f"across {len(stories)} story(ies), all grounded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
