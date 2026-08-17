#!/usr/bin/env python3
"""C-2(a) lint: single-persona default; GitOps must not create named profiles.

Golden suite does not require a live hermes profile list.
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
)
RESOLVER_NEEDLE = "resolve-seat-assignee.py"
FORBIDDEN_HOLE = "assignee default is the identity hole"
REQUIRED_ASSIGNEE = '--assignee "${ASSIGNEE}"'
GITOPS_REL = Path(
    "gitops/stages/050-advanced-app-platform/base/devspaces/"
    "maas-api-key-provisioning.yaml"
)
GITOPS_SKIP = "C-2(a): skip hermes profile create"


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
        description="Lint C-2(a) single-persona assignee (catalog + create + GitOps skip)."
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
    phases = data.get("phases") or {}
    if not isinstance(phases, dict) or not phases:
        print("FAIL: C-2(a) catalog has no phases map", file=sys.stderr)
        rc = 1
    else:
        for phase, name in phases.items():
            if name != "default":
                print(
                    f"FAIL: C-2(a) catalog phase {phase!r} maps to {name!r}, want default",
                    file=sys.stderr,
                )
                rc = 1
    for phase in ("M1", "M2", "M3", "M4", "M5", "factory"):
        try:
            got = resolve(phase, data)
        except SystemExit as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            rc = 1
            continue
        if got != "default":
            print(
                f"FAIL: C-2(a) {phase} must assignee default (got {got!r})",
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
        if FORBIDDEN_HOLE in text:
            print(
                f"FAIL: {rel} still treats default as the identity hole",
                file=sys.stderr,
            )
            rc = 1
        if 'ASSIGNEE}" != "default"' in text or "ASSIGNEE}\" != \"default\"" in text:
            print(f"FAIL: {rel} still refuses assignee default", file=sys.stderr)
            rc = 1
        if RESOLVER_NEEDLE not in text:
            print(f"FAIL: {rel} does not call {RESOLVER_NEEDLE}", file=sys.stderr)
            rc = 1
        if REQUIRED_ASSIGNEE not in text:
            print(f"FAIL: {rel} missing {REQUIRED_ASSIGNEE}", file=sys.stderr)
            rc = 1
    gitops = find_gitops(root)
    if gitops is None:
        print("FAIL: C-2(a) cannot find GitOps maas-api-key-provisioning.yaml", file=sys.stderr)
        rc = 1
    else:
        gtxt = gitops.read_text(encoding="utf-8")
        if GITOPS_SKIP not in gtxt:
            print(
                f"FAIL: GitOps init missing skip marker ({GITOPS_SKIP!r})",
                file=sys.stderr,
            )
            rc = 1
        if "profile create" in gtxt and GITOPS_SKIP not in gtxt:
            print("FAIL: GitOps still creates named Hermes profiles", file=sys.stderr)
            rc = 1
        if '"--clone"' in gtxt:
            print(
                "FAIL: GitOps still uses hermes profile create --clone (B-9/C-2(a))",
                file=sys.stderr,
            )
            rc = 1
    if rc == 0:
        print(
            "OK: C-2(a) single-persona assignee "
            f"(M3={resolve('M3', data)}; catalog={root / CATALOG_REL})"
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
