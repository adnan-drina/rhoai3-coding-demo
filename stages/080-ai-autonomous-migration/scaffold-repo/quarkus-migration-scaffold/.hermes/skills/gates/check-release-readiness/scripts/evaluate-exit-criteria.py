#!/usr/bin/env python3
"""Architect E-110403Z — evaluate cmd-shaped exit_criteria at any terminal (incl. wall)."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.exit-eval/v1"
WALLISH = frozenset({"timed_out", "timeout_kill", "gave_up"})
# Architect E-20260811T175305Z — whole-tree compile unsatisfiable mid-partition
SCOPED_COMPILE_CHECKS = frozenset({"compile", "test_compile"})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def run_scoped_compile(
    root: Path, task_id: str, body_path: Path, check: str
) -> tuple[bool, int, str]:
    """Return (ok, rc, cmd_label) via scope-filtered gate."""
    scoped = (
        root
        / ".hermes"
        / "skills"
        / "harness"
        / "record-run-evidence"
        / "scripts"
        / "run-scoped-compile-gate.py"
    )
    if not scoped.is_file():
        # Tip layout after Wave B: scripts live under .hermes/enforcement/
        scoped = (
            root
            / ".hermes"
            / "enforcement"
            / "record-run-evidence"
            / "scripts"
            / "run-scoped-compile-gate.py"
        )
    if not scoped.is_file():
        # Fallback relative to this script tree (older skills/harness layout)
        scoped = (
            Path(__file__).resolve().parents[2]
            / "harness"
            / "record-run-evidence"
            / "scripts"
            / "run-scoped-compile-gate.py"
        )
    goal = "test-compile" if check == "test_compile" else "compile"
    cp = subprocess.run(
        [
            sys.executable,
            str(scoped),
            str(root),
            "--task-id",
            task_id,
            "--body",
            str(body_path),
            "--goal",
            goal,
        ],
        text=True,
        capture_output=True,
    )
    return (
        cp.returncode == 0,
        cp.returncode,
        f"run-scoped-compile-gate.py --goal {goal}",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", required=True)
    ap.add_argument("--task-id", required=True)
    ap.add_argument(
        "--trigger",
        required=True,
        help="timed_out | timeout_kill | gave_up | complete | blocked",
    )
    ap.add_argument(
        "--skip-cmds",
        action="store_true",
        help="Record cmd exits as skipped (fixtures / dry meta only)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    body_path = Path(args.body)
    if not body_path.is_file():
        body_path = root / args.body
    if not body_path.is_file():
        print(f"FAIL: body not found: {args.body}", file=sys.stderr)
        return 1
    body = json.loads(body_path.read_text(encoding="utf-8"))
    if isinstance(body.get("body"), dict):
        body = body["body"]
    exits = body.get("exit_criteria") or body.get("done_when") or []
    trigger = args.trigger.strip().lower()
    results = []
    cmd_failed: list[str] = []
    for item in exits:
        if not isinstance(item, dict):
            continue
        check = str(item.get("check") or "")
        cmd = item.get("cmd")
        if cmd:
            if args.skip_cmds:
                results.append(
                    {
                        "check": check,
                        "kind": "cmd",
                        "ok": None,
                        "status": "skipped",
                        "cmd": str(cmd),
                    }
                )
                continue
            # Class A compile-scope: intercept compile / test_compile
            if check in SCOPED_COMPILE_CHECKS or (
                "test-compile" in str(cmd) or str(cmd).rstrip().endswith(" compile")
            ):
                scoped_check = (
                    "test_compile"
                    if check == "test_compile" or "test-compile" in str(cmd)
                    else "compile"
                )
                ok, rc, label = run_scoped_compile(
                    root, args.task_id, body_path, scoped_check
                )
                if not ok:
                    cmd_failed.append(check or label)
                results.append(
                    {
                        "check": check,
                        "kind": "cmd",
                        "rc": rc,
                        "ok": ok,
                        "cmd": label,
                        "scoped": True,
                        "body_cmd": str(cmd),
                    }
                )
                continue
            cp = subprocess.run(
                str(cmd),
                shell=True,
                cwd=root,
                text=True,
                capture_output=True,
            )
            ok = cp.returncode == 0
            if not ok:
                cmd_failed.append(check or str(cmd))
            results.append(
                {
                    "check": check,
                    "kind": "cmd",
                    "rc": cp.returncode,
                    "ok": ok,
                    "cmd": str(cmd),
                    "stderr_tail": (cp.stderr or "")[-400:],
                }
            )
        else:
            results.append(
                {
                    "check": check,
                    "kind": "assert",
                    "ok": None,
                    "status": "unevaluated_assert",
                    "assert": str(item.get("assert") or ""),
                }
            )

    try:
        rel_body = str(body_path.resolve().relative_to(root))
    except ValueError:
        rel_body = str(body_path)
    overall_ok = not cmd_failed and any(r.get("kind") == "cmd" for r in results)
    # Wall terminals with zero cmd exits still produce an artifact, but overall_ok false.
    if not any(r.get("kind") == "cmd" for r in results):
        overall_ok = False
    wallish = trigger in WALLISH
    # R-M3.31 (Architect E-20260810T230310Z): wallish + incomplete checkpoint ⇒
    # not product-green even when compile alone passes.
    notes: list[str] = [
        "R-M3.28: credit AD-009 freeze / >300s stream latency before classifying "
        "wall-fit PASS bodies as sizing defects"
    ]
    cp_incomplete = False
    cp_path = root / "evidence" / "runs" / args.task_id / "checkpoint.json"
    if cp_path.is_file():
        try:
            cp = json.loads(cp_path.read_text(encoding="utf-8"))
            work = cp.get("work_list") or []
            done = cp.get("completed") or []
            if work and len(done) < len(work):
                cp_incomplete = True
            elif work and cp.get("next") is not None and not done:
                cp_incomplete = True
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    if wallish and cp_incomplete:
        overall_ok = False
        notes.append(
            "R-M3.31: wallish + incomplete checkpoint → overall_ok=false "
            "(compile-only green is not product PASS)"
        )
    payload = {
        "schema": SCHEMA,
        "task_id": args.task_id,
        "body_path": rel_body,
        "body_sha256": sha256_file(body_path),
        "trigger": trigger,
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "results": results,
        "cmd_failed": cmd_failed,
        "overall_ok": overall_ok,
        "wallish": wallish,
        "checkpoint_incomplete": cp_incomplete,
        "notes": notes,
    }
    out_dir = root / "evidence" / "runs" / args.task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "exit-eval.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"OK: wrote {out.relative_to(root)} overall_ok={overall_ok} failed={cmd_failed}")
    # Non-zero when cmd checks failed — wall death must surface red compile etc.
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
