#!/usr/bin/env python3
"""AD-H §16.9 / AR-4.4 — surgical write sets + non-overlap + non-compile-only exits.

Lints every M3 body under `<root>/evidence/bodies` and `<root>/evidence/tasks`,
or only the body files named after ROOT (create-m3 passes the single body it is
about to mint).

Usage:
  python3 check-surgical-scopes.py .
  python3 check-surgical-scopes.py . evidence/bodies/m3-s-010.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — every M3 body has a surgical, non-overlapping destination write set
     with at least one endpoint/semantic exit, or idle (no M3 bodies)
  1  BLOCK — unreadable body passed explicitly, empty destination write set,
     missing endpoint/semantic exit_criteria (by operand_class), or
     compile-shaped-only exit_criteria (AR-4.4)
  2  usage / harness defect (bad or unknown argument)
"""

# F4: single shared definition (specimen_agnostic). F1: vocab by operand_class.
# F5: oracle_unavailable escape. Cross-story overlap owned by partition-coverage.
from specimen_agnostic import (  # noqa: E402
    COMPILE_ONLY,
    ENDPOINTISH,
    is_oracle_unavailable,
    normalize_operand_class,
    required_semantic_exits_for,
)


def load_bodies(root: Path) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
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
            items = data if isinstance(data, list) else [data]
            for i, obj in enumerate(items):
                if not isinstance(obj, dict):
                    continue
                body = obj.get("body") if isinstance(obj.get("body"), dict) else obj
                if not isinstance(body, dict):
                    continue
                if str(body.get("phase") or "").upper() != "M3":
                    continue
                label = str(path.relative_to(root))
                if len(items) > 1:
                    label = f"{label}[{i}]"
                out.append((label, body))
    return out


def path_list(body: dict, *keys: str) -> list[str]:
    for k in keys:
        v = body.get(k)
        if isinstance(v, list) and v:
            out = []
            for item in v:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    for kk in ("dest", "dst", "destination", "path", "legacy", "src"):
                        if item.get(kk):
                            out.append(str(item[kk]))
            return out
    return []


def dest_write_set(body: dict) -> list[str]:
    writes = path_list(body, "files_writable", "write_set", "filesWritable")
    if writes:
        return [p for p in writes if "legacy" not in p and "/.derived/" not in p]
    scope = path_list(body, "files_in_scope", "filesInScope")
    return [
        p
        for p in scope
        if ("/modernized/" in p or p.startswith("src/") or "/src/" in p)
        and "legacy" not in p
        and "/.derived/" not in p
    ]


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
    parsed = ap.parse_args()
    args = [parsed.root, *parsed.bodies]
    root = Path(args[0] if args else ".").resolve()
    # Optional extra body paths restrict the check (create-helper passes one body)
    only: list[Path] = []
    for a in args[1:]:
        p = Path(a)
        if not p.is_absolute():
            p = (root / p).resolve() if (root / p).is_file() else p.resolve()
        if p.is_file():
            only.append(p)
    bodies = load_bodies(root)
    if only:
        only_set = {p.resolve() for p in only}
        filtered = []
        for label, body in bodies:
            # label is relative path — resolve
            cand = (root / label.split("[")[0]).resolve()
            if cand in only_set:
                filtered.append((label, body))
        # always include explicitly passed bodies even if phase parse missed
        if not filtered:
            for p in only:
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except Exception as e:
                    print(f"FAIL: AR-4.4 {p}: {e}", file=sys.stderr)
                    return 1
                body = data.get("body") if isinstance(data.get("body"), dict) else data
                if isinstance(body, dict):
                    filtered.append((str(p), body))
        bodies = filtered
    if not bodies:
        print("OK: AR-4.4 idle (no M3 bodies)")
        return 0

    bad = 0
    # F4: cross-story write overlap is owned solely by check-partition-coverage.py
    # (honours sequence_after + pom exemption). This gate owns body-local facts.
    for label, body in bodies:
        writes = dest_write_set(body)
        if not writes:
            print(f"FAIL: AR-4.4 {label}: empty destination write set", file=sys.stderr)
            bad = 1
            continue

        exits = body.get("exit_criteria") or body.get("done_when") or []
        if not isinstance(exits, list):
            exits = []
        checks = {
            str(x.get("check") or "")
            for x in exits
            if isinstance(x, dict)
        }
        # F5: typed escape — oracle_unavailable with reason routes to Lead
        has_oracle_escape = any(
            is_oracle_unavailable(x) for x in exits if isinstance(x, dict)
        )
        oclass = normalize_operand_class(body)
        required = required_semantic_exits_for(body)
        if has_oracle_escape:
            # legal standalone semantic exit for any class
            pass
        elif not (checks & required):
            print(
                f"FAIL: AR-4.4 {label}: no semantic exit for operand_class={oclass!r} "
                f"(need one of {sorted(required)[:8]}; or oracle_unavailable+reason — "
                f"E-20260813T220250Z F1/F5)",
                file=sys.stderr,
            )
            bad = 1
        elif not (checks & ENDPOINTISH):
            print(
                f"FAIL: AR-4.4 {label}: exit check not in shared SEMANTIC_EXIT_VOCAB "
                f"(got {sorted(checks - COMPILE_ONLY)})",
                file=sys.stderr,
            )
            bad = 1
        if checks and checks <= COMPILE_ONLY and not has_oracle_escape:
            print(
                f"FAIL: AR-4.4 {label}: exit_criteria are compile-shaped only {sorted(checks)}",
                file=sys.stderr,
            )
            bad = 1

    if bad:
        print("AR-4.4 surgical scopes FAILED", file=sys.stderr)
        return 1
    print(f"OK: AR-4.4 surgical scopes ({len(bodies)} M3 body(ies))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
