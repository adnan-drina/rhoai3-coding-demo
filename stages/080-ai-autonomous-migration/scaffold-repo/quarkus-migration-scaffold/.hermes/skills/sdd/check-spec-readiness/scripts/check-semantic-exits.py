#!/usr/bin/env python3
"""AR-2.3–2.7 — semantic product exit_criteria for REST/persistence stories.

Lints every M3 body under `<root>/evidence/bodies` and `<root>/evidence/tasks`,
or only the body files named after ROOT (create-m3 passes the single body it is
about to mint).

Usage:
  python3 check-semantic-exits.py .
  python3 check-semantic-exits.py . evidence/bodies/m3-s-010.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — every REST/persistence M3 body carries its semantic exit_criteria,
     or idle (no M3 bodies / no REST-ish bodies)
  1  BLOCK — unreadable body passed explicitly, unknown semantic family, or
     missing semantic exits for a declared family (AR-2.3–2.7)
  2  usage / harness defect (bad or unknown argument)
"""

FAMILY_CHECKS: dict[str, frozenset[str]] = {
    "create_fk": frozenset({"create_fk"}),  # F1: dropped specimen owner_pet_visit_create
    "route_contract": frozenset({"route_contract", "endpoint_contract"}),
    "hql_entity_path": frozenset({"hql_entity_path", "delete_cascade_it"}),
    "http_semantics": frozenset({"http_semantics", "exception_mapping"}),
    "tx_rmw": frozenset({"tx_rmw", "concurrency"}),
    # Non-REST families (F1)
    "build_resolves": frozenset({"build_resolves"}),
    "config_profile_load": frozenset({"config_profile_load"}),
    "test_suite_runs": frozenset({"test_suite_runs"}),
    "log_output": frozenset({"log_output"}),
    "cache_hit": frozenset({"cache_hit"}),
    "health_probe": frozenset({"health_probe"}),
}

RESTISH = ("RestController", "Repository", "ApplicationService")

from specimen_agnostic import (  # noqa: E402
    COMPILE_ONLY,
    is_oracle_unavailable,
    normalize_operand_class,
    oracle_unavailable_allowed_for_class,
)



def load_m3(root: Path) -> list[tuple[str, dict]]:
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
            if not isinstance(body, dict):
                continue
            if str(body.get("phase") or "").upper() != "M3":
                continue
            out.append((str(path.relative_to(root)), body))
    return out


def write_paths(body: dict) -> list[str]:
    for k in ("files_writable", "write_set", "files_in_scope", "filesInScope"):
        v = body.get(k)
        if isinstance(v, list):
            return [str(x) if not isinstance(x, dict) else str(x.get("dest") or x.get("path") or "") for x in v]
    return []


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
    only: list[Path] = []
    for a in args[1:]:
        p = Path(a)
        if not p.is_absolute():
            p = (root / p).resolve() if (root / p).is_file() else p.resolve()
        if p.is_file():
            only.append(p)
    bodies = load_m3(root)
    if only:
        filtered = []
        for p in only:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"FAIL: AR-2.x {p}: {e}", file=sys.stderr)
                return 1
            body = data.get("body") if isinstance(data.get("body"), dict) else data
            if isinstance(body, dict) and str(body.get("phase") or "").upper() == "M3":
                filtered.append((str(p), body))
        bodies = filtered
    if not bodies:
        print("OK: AR-2.3–2.7 idle (no M3 bodies)")
        return 0

    bad = 0
    checked = 0
    for label, body in bodies:
        identity = body.get("identity") if isinstance(body.get("identity"), dict) else {}
        families = identity.get("semantic_families") or identity.get("semanticFamilies")
        paths = " ".join(write_paths(body))
        restish = any(tok in paths for tok in RESTISH)
        exits_pre = body.get("exit_criteria") or []
        if not families and not restish:
            # Still enforce measurable non-compile exits (L2) even for non-REST bodies
            for x in exits_pre if isinstance(exits_pre, list) else []:
                if not isinstance(x, dict):
                    continue
                check = str(x.get("check") or "").strip()
                if not check or check in COMPILE_ONLY:
                    continue
                # F5: oracle_unavailable needs reason, not cmd
                if check == "oracle_unavailable":
                    oclass = normalize_operand_class(body)
                    if not oracle_unavailable_allowed_for_class(oclass):
                        print(
                            f"FAIL: AR-2.3–2.7 {label}: oracle_unavailable forbidden for "
                            f"operand_class={oclass!r} (F5a E-20260813T221456Z)",
                            file=sys.stderr,
                        )
                        bad = 1
                    elif not is_oracle_unavailable(x):
                        print(
                            f"FAIL: AR-2.3–2.7 {label}: oracle_unavailable lacks reason "
                            f"(E-20260813T220250Z F5)",
                            file=sys.stderr,
                        )
                        bad = 1
                    checked += 1
                    continue
                cmd = x.get("cmd")
                if not (isinstance(cmd, str) and cmd.strip()):
                    print(
                        f"FAIL: AR-2.3–2.7 {label}: exit {check!r} has no cmd "
                        f"(unmeasurable; add cmd, use oracle_unavailable+reason, or drop — "
                        f"E-20260813T215058Z L2 / E-20260813T220250Z F5)",
                        file=sys.stderr,
                    )
                    bad = 1
                    checked += 1
            continue
        checked += 1
        if isinstance(families, str):
            families = [families]
        if not isinstance(families, list) or not families:
            # default proving-min for REST-ish write sets
            families = ["create_fk", "http_semantics"]
        exits = body.get("exit_criteria") or []
        checks = {
            str(x.get("check") or "")
            for x in exits
            if isinstance(x, dict)
        }
        missing = []
        for fam in families:
            fam_s = str(fam).strip()
            allowed = FAMILY_CHECKS.get(fam_s)
            if not allowed:
                print(f"FAIL: AR-2.x {label}: unknown semantic family {fam_s!r}", file=sys.stderr)
                bad = 1
                continue
            if not (checks & allowed):
                missing.append(f"{fam_s}→{sorted(allowed)}")
        if missing:
            print(
                f"FAIL: AR-2.3–2.7 {label}: missing semantic exits {missing}",
                file=sys.stderr,
            )
            bad = 1

        # Deputy E-20260813T215058Z L2: non-compile exits must be measurable (cmd)
        # or removed — prose-only asserts are vacuous-pass class.
        for x in exits:
            if not isinstance(x, dict):
                continue
            check = str(x.get("check") or "").strip()
            if not check or check in COMPILE_ONLY:
                continue
            # F5: oracle_unavailable needs reason, not cmd (Lead triage)
            if check == "oracle_unavailable":
                oclass = normalize_operand_class(body)
                if not oracle_unavailable_allowed_for_class(oclass):
                    print(
                        f"FAIL: AR-2.3–2.7 {label}: oracle_unavailable forbidden for "
                        f"operand_class={oclass!r} (F5a E-20260813T221456Z)",
                        file=sys.stderr,
                    )
                    bad = 1
                elif not is_oracle_unavailable(x):
                    print(
                        f"FAIL: AR-2.3–2.7 {label}: oracle_unavailable lacks reason "
                        f"(E-20260813T220250Z F5)",
                        file=sys.stderr,
                    )
                    bad = 1
                continue
            cmd = x.get("cmd")
            if not (isinstance(cmd, str) and cmd.strip()):
                print(
                    f"FAIL: AR-2.3–2.7 {label}: exit {check!r} has no cmd "
                    f"(unmeasurable; add cmd, use oracle_unavailable+reason, or drop — "
                    f"E-20260813T215058Z L2 / E-20260813T220250Z F5)",
                    file=sys.stderr,
                )
                bad = 1

    if checked == 0:
        print("OK: AR-2.3–2.7 idle (no REST/persistence M3 bodies)")
        return 0
    if bad:
        print("AR-2.3–2.7 semantic exits FAILED", file=sys.stderr)
        return 1
    print(f"OK: AR-2.3–2.7 semantic exits ({checked} body(ies))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
