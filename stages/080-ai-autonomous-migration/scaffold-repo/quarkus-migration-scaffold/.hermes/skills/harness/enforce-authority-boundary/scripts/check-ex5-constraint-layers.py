#!/usr/bin/env python3
"""EX-5 lint: layers 1-3 pinned in GitOps Managed Scope; semantic gates stay.

Layer 1 = approvals.deny (checked before mode off / --yolo).
Layer 2 = HERMES_WRITE_SAFE_ROOT in managed .env (native write sandbox).
Layer 3 = terminal.backend local (workspace pod is the container; nested
docker is not provisioned and would skip dangerous-command checks).

Does not retire mint-lints, receipts, the EX-3 write-set hook, or
check-write-fence.py. Walks up to migration.yaml / GitOps (SR-2).

Usage:
  python3 check-ex5-constraint-layers.py
  python3 check-ex5-constraint-layers.py /path/to/scaffold
  python3 check-ex5-constraint-layers.py --help
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CATALOG_REL = (
    Path(".hermes")
    / "skills"
    / "harness"
    / "enforce-authority-boundary"
    / "references"
    / "constraint-layers.json"
)
GITOPS_REL = Path(
    "gitops/stages/050-advanced-app-platform/base/devspaces/"
    "maas-api-key-provisioning.yaml"
)
EX3_HOOK = "write-set-hook.py"
WRITE_MATCHER = "write|write_file|patch|edit_file|apply_patch|create_file|terminal"


def migration_root(start: Path) -> Path:
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    while True:
        if (cur / "migration.yaml").is_file():
            return cur
        if cur == cur.parent:
            raise SystemExit(
                "cannot find project root (migration.yaml) walking up "
                f"from {start} (SR-2)"
            )
        cur = cur.parent


def find_gitops(start: Path) -> Path | None:
    cur = start.resolve()
    while True:
        cand = cur / GITOPS_REL
        if cand.is_file():
            return cand
        if cur == cur.parent:
            return None
        cur = cur.parent


def load_catalog(root: Path) -> dict:
    path = root / CATALOG_REL
    if not path.is_file():
        raise SystemExit(f"FAIL: EX-5 catalog missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("FAIL: EX-5 catalog is not an object")
    return data


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Lint EX-5 constraint layers (approvals.deny, write-safe-root, "
            "terminal.backend local)."
        )
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
    deny = data.get("layer1_approvals_deny") or []
    if not isinstance(deny, list) or len(deny) < 3:
        print("FAIL: EX-5 catalog layer1_approvals_deny must have >=3 globs", file=sys.stderr)
        rc = 1
        deny = []
    if data.get("layer2_write_safe_root_env") != "HERMES_WRITE_SAFE_ROOT":
        print("FAIL: EX-5 catalog layer2 env must be HERMES_WRITE_SAFE_ROOT", file=sys.stderr)
        rc = 1
    if data.get("layer3_terminal_backend") != "local":
        print(
            "FAIL: EX-5 catalog layer3_terminal_backend must be local "
            "(nested docker is not provisioned)",
            file=sys.stderr,
        )
        rc = 1
    if data.get("retires_nothing") is not True:
        print("FAIL: EX-5 catalog must set retires_nothing true", file=sys.stderr)
        rc = 1
    forbidden = data.get("forbidden_terminal_backends") or []
    gitops = find_gitops(root)
    if gitops is None:
        print("FAIL: EX-5 cannot find GitOps maas-api-key-provisioning.yaml", file=sys.stderr)
        return 1
    gtxt = gitops.read_text(encoding="utf-8")
    if "EX-5" not in gtxt:
        print("FAIL: GitOps init missing EX-5 marker", file=sys.stderr)
        rc = 1
    for glob in deny:
        needle = json.dumps(glob)
        if needle not in gtxt:
            print(
                f"FAIL: GitOps approvals.deny missing catalog glob {needle}",
                file=sys.stderr,
            )
            rc = 1
    if 'fh.write(f"HERMES_WRITE_SAFE_ROOT=' not in gtxt:
        print(
            "FAIL: GitOps managed .env does not pin HERMES_WRITE_SAFE_ROOT (L2)",
            file=sys.stderr,
        )
        rc = 1
    if '"backend": "local"' not in gtxt:
        print('FAIL: GitOps missing terminal.backend local pin (L3)', file=sys.stderr)
        rc = 1
    for backend in forbidden:
        needle = f'"backend": "{backend}"'
        if needle in gtxt:
            print(
                f"FAIL: GitOps sets terminal.backend {backend!r} "
                "(skips dangerous-command checks; not provisioned)",
                file=sys.stderr,
            )
            rc = 1
    if EX3_HOOK not in gtxt:
        print("FAIL: GitOps lost EX-3 write-set hook copy", file=sys.stderr)
        rc = 1
    if WRITE_MATCHER not in gtxt:
        print("FAIL: GitOps lost EX-3 write-tool matcher", file=sys.stderr)
        rc = 1
    if gtxt.count(WRITE_MATCHER) != 1:
        print(
            "FAIL: GitOps must keep exactly one write-tool pre_tool_call matcher "
            f"(found {gtxt.count(WRITE_MATCHER)})",
            file=sys.stderr,
        )
        rc = 1
    if "hermes-spawn-hydrate.py" not in gtxt:
        print("FAIL: GitOps lost v24 spawn-hydrate wrapper copy", file=sys.stderr)
        rc = 1
    if rc == 0:
        print(
            "OK: EX-5 constraint layers "
            f"(deny={len(deny)}; backend=local; catalog={root / CATALOG_REL})"
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
