#!/usr/bin/env python3
"""EX-4 lint: named seat profiles, no --assignee default, --description present.

Golden suite does not require a live hermes profile list (seat init owns create).
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

_RESOLVE_PY = Path(__file__).resolve().parent / "resolve-seat-assignee.py"
_spec = importlib.util.spec_from_file_location("resolve_seat_assignee", _RESOLVE_PY)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
CATALOG_REL = _mod.CATALOG_REL
load_catalog = _mod.load_catalog
migration_root = _mod.migration_root
resolve = _mod.resolve

CREATE_SCRIPTS = (
    Path(".hermes")
    / "skills"
    / "harness"
    / "dispatch-phase"
    / "scripts"
    / "dispatch-phase.sh",
    Path(".hermes")
    / "skills"
    / "harness"
    / "dispatch-phase"
    / "scripts"
    / "create-m3-implementer.sh",
)
RESOLVER_NEEDLE = "resolve-seat-assignee.py"
FORBIDDEN = "--assignee default"
GITOPS_REL = Path(
    "gitops/stages/050-advanced-app-platform/base/devspaces/"
    "maas-api-key-provisioning.yaml"
)


def find_gitops(start: Path) -> Path | None:
    cur = start.resolve()
    while True:
        cand = cur / GITOPS_REL
        if cand.is_file():
            return cand
        if cur == cur.parent:
            return None
        cur = cur.parent


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Lint EX-4 seat assignee profiles (catalog + create paths)."
    )
    p.add_argument(
        "root",
        nargs="?",
        default="",
        help="scaffold root (default: walk up to migration.yaml)",
    )
    args = p.parse_args(argv)
    root = Path(args.root).resolve() if args.root else migration_root(Path(__file__))
    rc = 0
    data = load_catalog(root)
    profiles = data.get("profiles") or {}
    phases = data.get("phases") or {}
    if "default" in profiles or "default" in (phases.values() if isinstance(phases, dict) else []):
        print("FAIL: EX-4 catalog must not use profile name default", file=sys.stderr)
        rc = 1
    if not profiles:
        print("FAIL: EX-4 catalog has no profiles", file=sys.stderr)
        rc = 1
    for name, spec in profiles.items():
        desc = (spec or {}).get("description") or ""
        if not str(desc).strip():
            print(f"FAIL: EX-4 profile {name!r} missing description", file=sys.stderr)
            rc = 1
    for phase in ("M1", "M2", "M3", "M4", "M5", "factory"):
        try:
            got = resolve(phase, data)
        except SystemExit as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            rc = 1
            continue
        if phase == "M3" and got != "implementer":
            print(
                f"FAIL: EX-4 M3 must assignee implementer (got {got!r})",
                file=sys.stderr,
            )
            rc = 1
    for rel in CREATE_SCRIPTS:
        path = root / rel
        if not path.is_file():
            print(f"FAIL: missing {rel}", file=sys.stderr)
            rc = 1
            continue
        text = path.read_text(encoding="utf-8")
        if FORBIDDEN in text:
            print(f"FAIL: {rel} still has {FORBIDDEN!r} (identity hole)", file=sys.stderr)
            rc = 1
        if RESOLVER_NEEDLE not in text:
            print(f"FAIL: {rel} does not call {RESOLVER_NEEDLE}", file=sys.stderr)
            rc = 1
    gitops = find_gitops(root)
    if gitops is None:
        print("FAIL: EX-4 cannot find GitOps maas-api-key-provisioning.yaml", file=sys.stderr)
        rc = 1
    else:
        gtxt = gitops.read_text(encoding="utf-8")
        for needle, label in (
            ("assignee-profiles.json", "catalog path"),
            ("profile create", "hermes profile create"),
            ("--description", "description flag"),
            ("--no-alias", "no command alias"),
            ("EX-4", "EX-4 marker"),
        ):
            if needle not in gtxt:
                print(f"FAIL: GitOps init missing {label} ({needle!r})", file=sys.stderr)
                rc = 1
    if rc == 0:
        print(
            "OK: EX-4 seat assignee profiles "
            f"(M3={resolve('M3', data)}; catalog={root / CATALOG_REL})"
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
