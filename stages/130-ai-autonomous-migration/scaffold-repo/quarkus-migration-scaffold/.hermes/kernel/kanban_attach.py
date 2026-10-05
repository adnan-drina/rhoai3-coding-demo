#!/usr/bin/env python3
"""Attach M1 KEEP evidence to the Kanban card (dual-write with PVC paths).

Official: kanban_attach / complete(artifacts=), 25 MB/file
(`.agents/skills/hermes-kanban/`). PVC paths stay. A dest wipe must not
be the only copy. Not dest-4 mid-run.

The evidence bundle (``evidence/planning/evidence-bundle.json``, root of
the planner digest chain) and the type graph are on the card. A Boot 3
derivation manifest is not — dest-13 attached that basename instead of the
type graph, so M2 reading ``kanban_attachments`` had no structural input.

``--exec`` is proven, not assumed: after attaching, the native records are
read back (``hermes kanban attachments --json``) and every expected file must
be held with its workspace bytes, or the step exits 1 naming the gap. v23 M1
ran the dry run, printed OK and attached nothing; the reviewer's listing was
empty and the audit passed. A file already proven is not attached twice.
DEFAULT_REL is the paved-road-m1 ``kanban-attach`` KEEP set (selftest).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

_KERNEL = Path(__file__).resolve().parent
_LIB = _KERNEL.parent / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))
from native_attachments import attachment_gaps, latest_by_name, read_records, record_matches  # noqa: E402

MAX_BYTES = 25 * 1024 * 1024
DEFAULT_REL = (
    "evidence/planning/evidence-bundle.json",
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
    absent: list[str] = []
    for path in wanted:
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            absent.append(str(path))
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
        "absent": absent,
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


def attach_and_prove(root: Path, task_id: str, plan: dict[str, Any], *, runner: Runner,
                     hermes: str = "hermes", read: Callable[[str], list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Attach what the native records do not already prove, then read the
    records back and check the whole expected set against the workspace."""
    read = read or (lambda t: read_records(t, hermes=hermes))
    before = latest_by_name(read(task_id))
    todo = dict(plan, files=[f for f in plan["files"]
                             if record_matches(root, _rel(root, f["path"]), before.get(f["name"]))])
    result = attach_files(task_id, todo, runner=runner, hermes=hermes)
    result["already_attached"] = [f["path"] for f in plan["files"] if f not in todo["files"]]
    records = read(task_id)
    result["records"] = len(records)
    result["gaps"] = attachment_gaps(root, records, DEFAULT_REL)
    return result


def _rel(root: Path, path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except ValueError:
        return path


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
            result = attach_and_prove(root, task, planned, runner=subprocess_runner, hermes=hermes)
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
    if execute:
        if result["gaps"]:
            print("FAIL: NATIVE_ATTACHMENTS %d of %d evidence file(s) are not held as native attachments of %s: %s"
                  % (len(result["gaps"]), len(DEFAULT_REL), task, "; ".join(result["gaps"])), file=sys.stderr)
            return 1
        print("OK: kanban attach (%d attached, %d already attached; %d of %d evidence file(s) proven by native records)."
              % (len(result["attached"]), len(result["already_attached"]), len(DEFAULT_REL), len(DEFAULT_REL)), file=sys.stderr)
    else:
        print("PLAN ONLY: %d file(s) would be attached; NOTHING was attached. Run again with --exec."
              % len(planned["files"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
