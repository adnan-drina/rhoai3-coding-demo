#!/usr/bin/env python3
"""K5 — diff baseline vs current findings for a story scope.

Usage:
  findings-diff.py <baseline.json> <current.json> [--scope id,id2 | --scope-all]

Exit 0 GREEN (no surviving/new in-scope incidents).
Exit 1 RED — prints FINDINGS: lines + FIX block.
Scoped rules absent from baseline are ignored. scaffold-presatisfied rules
are skipped (destination already satisfied — not story residual).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def load_rules(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for rs in data:
        for rid, v in (rs.get("violations") or {}).items():
            out[rid] = v
    return out


def load_presat() -> set[str]:
    out: set[str] = set()
    root = Path(".")
    for base in (
        root / "migration/scaffold-presatisfied.generated.txt",
        root / ".hermes/harness/scaffold-presatisfied.txt",
        Path(__file__).resolve().parent / "scaffold-presatisfied.txt",
    ):
        try:
            for ln in base.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    out.add(ln)
        except OSError:
            continue
    return out


def sites(v: dict) -> list[str]:
    out = []
    for inc in v.get("incidents") or []:
        uri = unquote(inc.get("uri") or "?")
        if uri.startswith("file:"):
            uri = urlparse(uri).path or uri
        line = inc.get("lineNumber", "?")
        msg = (inc.get("message") or "")[:80]
        out.append(f"{Path(uri).name}:{line} {msg}".rstrip())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline")
    ap.add_argument("current")
    ap.add_argument("--scope", default="", help="comma-separated rule ids")
    ap.add_argument("--scope-all", action="store_true")
    args = ap.parse_args()
    before = load_rules(Path(args.baseline))
    after = load_rules(Path(args.current))
    if not before:
        print("findings-diff: no baseline — skip GREEN")
        return 0
    if not Path(args.current).is_file():
        print("FINDINGS: current snapshot missing")
        print("FIX: ensure kantra after-scan wrote the current JSON (K5).")
        return 1
    presat = load_presat()
    if args.scope_all:
        scope = set(before) - presat
    else:
        scope = {s.strip() for s in args.scope.split(",") if s.strip()} - presat
    if not scope:
        print("findings-diff: empty scope — skip GREEN")
        return 0

    problems = []
    for rid in sorted(scope):
        if rid not in before:
            continue
        cur = after.get(rid)
        if cur and (cur.get("incidents") or []):
            for s in sites(cur)[:5]:
                problems.append(f"FINDINGS:survives:{rid}: {s}")
        # Newly appearing scoped rule (was in scope list but not baseline?) — rare
    # New rules in after that match scope prefixes and weren't in before
    for rid, v in sorted(after.items()):
        if rid in before or rid in presat:
            continue
        if rid in scope or any(rid.startswith(s.rstrip("0")[:12]) for s in scope if len(s) >= 12):
            if v.get("incidents"):
                for s in sites(v)[:3]:
                    problems.append(f"FINDINGS:new:{rid}: {s}")

    if problems:
        for p in problems[:40]:
            print(p)
        print(
            f"FINDINGS RED: {len(problems)} in-scope incident(s) survive or newly appear (K5)"
        )
        print(
            "FIX: convert/remove the surviving incidents (file:line above) for this "
            "story's Findings scope; re-run sensors.sh findings / milestone."
        )
        return 1
    print(f"findings-diff GREEN (scope={len(scope)} rules clear)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
