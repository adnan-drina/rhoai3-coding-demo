#!/usr/bin/env python3
"""Attach M1 KEEP evidence to the Kanban card (dual-write with PVC paths).

Official: kanban_attach / complete(artifacts=), 25 MB/file
(`.agents/skills/hermes-kanban/`). PVC paths stay. A dest wipe must not
be the only copy. Not dest-4 mid-run.

The type graph (``evidence/type-inventory.json``) is on the card. The
derivation manifest (``evidence/derived/legacy-at-3.json``) is not —
dest-13 attached that basename instead of the type graph, so M2 reading
``kanban_attachments`` had no T0_3 input (PVC fallback hid it).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

MAX_BYTES = 25 * 1024 * 1024
DEFAULT_REL = (
    "evidence/findings-handoff.json",
    "evidence/entry-point-inventory.json",
    "evidence/type-inventory.json",
    "evidence/required-extensions.json",
    "evidence/mta-findings.json",
)
TASK_ID_RE = re.compile(r"^t_[A-Za-z0-9]+$")
Runner = Callable[[list[str]], tuple[int, str, str]]


def argv_for_attach(task_id: str, path: Path, *, hermes: str = "hermes") -> list[str]:
    tid = str(task_id).strip()
    if not TASK_ID_RE.match(tid):
        raise ValueError("FAIL: task id must be t_* (got %r)" % task_id)
    return [hermes, "kanban", "attach", tid, str(path)]


def plan_attachments(root: Path, *, extra: list[Path] | None = None) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    wanted = [root / rel for rel in DEFAULT_REL]
    if extra:
        wanted.extend(extra)
    seen: set[Path] = set()
    for path in wanted:
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > MAX_BYTES:
            skipped.append(
                {"path": str(path), "bytes": size, "reason": "exceeds 25 MiB cap"}
            )
            continue
        if size < 1:
            skipped.append({"path": str(path), "bytes": size, "reason": "empty"})
            continue
        files.append({"path": str(path), "name": path.name, "bytes": size})
    return {
        "files": files,
        "skipped": skipped,
        "complete_artifacts": [f["path"] for f in files],
        "claimed_control": False,
    }


def attach_files(
    task_id: str,
    plan: dict[str, Any],
    *,
    runner: Runner,
    hermes: str = "hermes",
) -> dict[str, Any]:
    attached: list[dict[str, Any]] = []
    for item in plan["files"]:
        argv = argv_for_attach(task_id, Path(item["path"]), hermes=hermes)
        if "swarm" in argv or "decompose" in argv or "daemon" in argv:
            raise ValueError("FAIL: attach argv used OBJECT verb")
        code, out, err = runner(argv)
        if code != 0:
            raise ValueError(
                "FAIL: attach %s exit %s stderr=%s"
                % (item["path"], code, (err or "").strip()[:200])
            )
        attached.append({"path": item["path"], "argv": argv, "stdout": out.strip()})
    return {
        "task_id": task_id,
        "attached": attached,
        "skipped": plan.get("skipped") or [],
        "complete_artifacts": plan["complete_artifacts"],
        "claimed_control": False,
    }


def subprocess_runner(argv: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(argv, capture_output=True, text=True)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(".")
    task = os.environ.get("HERMES_KANBAN_TASK", "").strip()
    hermes = os.environ.get("HERMES_BIN", "hermes")
    execute = False
    extras: list[Path] = []
    i = 0
    while i < len(args):
        if args[i] == "--root" and i + 1 < len(args):
            root = Path(args[i + 1])
            i += 2
            continue
        if args[i] in ("--task", "--task-id") and i + 1 < len(args):
            task = args[i + 1]
            i += 2
            continue
        if args[i] == "--file" and i + 1 < len(args):
            extras.append(Path(args[i + 1]))
            i += 2
            continue
        if args[i] == "--hermes" and i + 1 < len(args):
            hermes = args[i + 1]
            i += 2
            continue
        if args[i] == "--exec":
            execute = True
            i += 1
            continue
        print("FAIL: unknown arg %s" % args[i], file=sys.stderr)
        return 1
    root = root.resolve()
    if not task:
        print(
            "OK: kanban attach idle (no HERMES_KANBAN_TASK / --task)",
            file=sys.stderr,
        )
        print(json.dumps({"idle": True, "claimed_control": False}))
        return 0
    try:
        planned = plan_attachments(root, extra=extras)
        if execute:
            result = attach_files(task, planned, runner=subprocess_runner, hermes=hermes)
        else:
            result = {
                "task_id": task,
                "argv": [
                    argv_for_attach(task, Path(f["path"]), hermes=hermes)
                    for f in planned["files"]
                ],
                "skipped": planned["skipped"],
                "complete_artifacts": planned["complete_artifacts"],
                "claimed_control": False,
            }
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("OK: kanban attach (%d file(s))." % len(planned["files"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
