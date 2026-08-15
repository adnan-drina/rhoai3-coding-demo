#!/usr/bin/env python3
"""BV19-3 lint: --parent is the phase DAG; machinery must read the link graph.

M1 is the only root. M2/M3/M4/M5/factory and M3 mint must pass --parent.
After create, dispatch reads `kanban show --json` via read-link-graph.py.
Do not look up the DAG from titles or phase-*-task-id.txt.

Usage:
  python3 check-link-graph.py
  python3 check-link-graph.py /path/to/scaffold
  python3 check-link-graph.py --help
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

DISPATCH = (
    Path(".hermes") / "skills" / "harness" / "dispatch-phase" / "scripts" / "dispatch-phase.sh"
)
CREATE_M3 = (
    Path(".hermes")
    / "skills"
    / "harness"
    / "dispatch-phase"
    / "scripts"
    / "create-m3-implementer.sh"
)
MINT = Path(".hermes") / "skills" / "harness" / "dispatch-phase" / "scripts" / "mint-m3-wave.sh"
READER = Path(".hermes") / "skills" / "harness" / "dispatch-phase" / "scripts" / "read-link-graph.py"
TITLE_DAG = "phase_hint(title"


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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Lint BV19-3: link graph is the phase DAG (not titles/files)."
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
    reader = root / READER
    if not reader.is_file():
        print(f"FAIL: missing {READER}", file=sys.stderr)
        return 1
    dispatch = root / DISPATCH
    create = root / CREATE_M3
    mint = root / MINT
    for rel, path in (("dispatch-phase.sh", dispatch), ("create-m3-implementer.sh", create), ("mint-m3-wave.sh", mint)):
        if not path.is_file():
            print(f"FAIL: missing {path.relative_to(root)}", file=sys.stderr)
            rc = 1
            continue
        text = path.read_text(encoding="utf-8")
        if "read-link-graph.py" not in text:
            print(f"FAIL: {rel} does not call read-link-graph.py", file=sys.stderr)
            rc = 1
    if dispatch.is_file():
        dtxt = dispatch.read_text(encoding="utf-8")
        if "BV19-3: --parent REQUIRED" not in dtxt:
            print(
                "FAIL: dispatch-phase.sh missing BV19-3 --parent REQUIRED for non-M1",
                file=sys.stderr,
            )
            rc = 1
        if "--expect-parent" not in dtxt:
            print(
                "FAIL: dispatch-phase.sh must verify the created card's parent link",
                file=sys.stderr,
            )
            rc = 1
    if create.is_file():
        ctxt = create.read_text(encoding="utf-8")
        if "--parent REQUIRED" not in ctxt:
            print("FAIL: create-m3-implementer.sh lost --parent REQUIRED", file=sys.stderr)
            rc = 1
        if "--expect-parent" not in ctxt:
            print(
                "FAIL: create-m3-implementer.sh must verify the created card's parent link",
                file=sys.stderr,
            )
            rc = 1
    if mint.is_file():
        mtxt = mint.read_text(encoding="utf-8")
        if "--parent" not in mtxt or "PARENT_DONE" not in mtxt:
            print("FAIL: mint-m3-wave.sh must keep --parent + PARENT_DONE", file=sys.stderr)
            rc = 1
    runtime = root / ".hermes" / "home" / "scripts" / "enforce-max-runtime-hard.py"
    if runtime.is_file() and TITLE_DAG in runtime.read_text(encoding="utf-8"):
        print(
            "FAIL: enforce-max-runtime-hard.py still derives phase from title "
            "(BV19-3: link graph is identity)",
            file=sys.stderr,
        )
        rc = 1
    if rc == 0:
        print(f"OK: BV19-3 link graph is the phase DAG (reader={reader})")
    return rc


if __name__ == "__main__":
    sys.exit(main())
