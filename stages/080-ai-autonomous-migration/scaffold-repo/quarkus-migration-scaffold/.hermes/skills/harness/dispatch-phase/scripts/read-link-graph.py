#!/usr/bin/env python3
"""BV19-3 — read Hermes Kanban parent/child links (the phase DAG).

Parses `hermes kanban show --json` (or a fixture file / stdin). Identity is
task ids on the link graph, never titles or `phase-*-task-id.txt`.

Official: dispatcher promotes todo→ready when all parents are done
(hermes-kanban Core concepts / `kanban link`). HKN-2: `--parent` / `link`
gates; `--force` is not a durable bypass.

Usage:
  hermes kanban show t_xxx --json | python3 read-link-graph.py --print parents
  python3 read-link-graph.py --json-file fixture.json --expect-parent t_m1
  python3 read-link-graph.py --help
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _ids(raw: Any) -> list[str]:
    out: list[str] = []
    if raw is None:
        return out
    if isinstance(raw, str):
        s = raw.strip()
        return [s] if s else []
    if isinstance(raw, dict):
        tid = raw.get("id") or raw.get("task_id") or ""
        return [str(tid)] if str(tid).strip() else []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            out.extend(_ids(item))
        return out
    s = str(raw).strip()
    return [s] if s else []


def parse_show(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("kanban show JSON must be an object")
    task = data.get("task") if isinstance(data.get("task"), dict) else data
    if not isinstance(task, dict):
        task = data
    parents = data.get("parents")
    if parents is None:
        parents = task.get("parents") or task.get("parent_ids")
    children = data.get("children")
    if children is None:
        children = task.get("children") or task.get("child_ids")
    tid = task.get("id") or data.get("id") or task.get("task_id") or ""
    return {
        "id": str(tid or "").strip(),
        "status": str(task.get("status") or data.get("status") or "").strip().lower(),
        "parents": _ids(parents),
        "children": _ids(children),
    }


def load_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Read Kanban parent/child links from show JSON (BV19-3)."
    )
    p.add_argument(
        "--json-file",
        default="-",
        help="show JSON path, or - for stdin (default)",
    )
    p.add_argument(
        "--print",
        dest="print_field",
        choices=("id", "status", "parents", "children"),
        help="print one field (parents/children as space-separated ids)",
    )
    p.add_argument("--expect-parent", action="append", default=[], metavar="ID")
    p.add_argument("--expect-child", action="append", default=[], metavar="ID")
    p.add_argument(
        "--expect-no-parents",
        action="store_true",
        help="fail if the record has any parent (DAG root)",
    )
    args = p.parse_args(argv)
    try:
        rec = parse_show(load_json(args.json_file))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: BV19-3 cannot parse kanban show JSON ({exc})", file=sys.stderr)
        return 1
    rc = 0
    for pid in args.expect_parent:
        if pid not in rec["parents"]:
            print(
                f"FAIL: BV19-3 missing parent {pid!r} "
                f"(id={rec['id']!r} parents={rec['parents']})",
                file=sys.stderr,
            )
            rc = 1
    for cid in args.expect_child:
        if cid not in rec["children"]:
            print(
                f"FAIL: BV19-3 missing child {cid!r} "
                f"(id={rec['id']!r} children={rec['children']})",
                file=sys.stderr,
            )
            rc = 1
    if args.expect_no_parents and rec["parents"]:
        print(
            f"FAIL: BV19-3 expected DAG root with no parents "
            f"(id={rec['id']!r} parents={rec['parents']})",
            file=sys.stderr,
        )
        rc = 1
    if args.print_field:
        val = rec[args.print_field]
        if isinstance(val, list):
            print(" ".join(val))
        else:
            print(val)
    elif rc == 0 and (args.expect_parent or args.expect_child or args.expect_no_parents):
        print(
            f"OK: BV19-3 link graph "
            f"id={rec['id']} status={rec['status']} "
            f"parents={rec['parents']} children={rec['children']}"
        )
    elif rc == 0 and not args.print_field:
        print(
            f"OK: BV19-3 link graph "
            f"id={rec['id']} status={rec['status']} "
            f"parents={rec['parents']} children={rec['children']}"
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
