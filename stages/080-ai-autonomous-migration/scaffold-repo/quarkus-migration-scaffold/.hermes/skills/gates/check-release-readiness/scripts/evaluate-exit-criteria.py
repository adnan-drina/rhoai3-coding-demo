#!/usr/bin/env python3
"""Architect E-110403Z — evaluate cmd-shaped exit_criteria at any terminal (incl. wall).

R-OF.1 (066500Z): Maven `-Dtest=` is the official Surefire scope. Hermes
has no native exit-eval. This wrapper rewrites unscoped `mvn test|verify`
to proves FQCNs (task_scoped_tests) because minted cmds stay unscoped
(handover-mint freeze 1088 / AR-4.3). Fail-closed when proves yield no
FQCN — do not fall back to the whole suite.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.exit-eval/v1"
WALLISH = frozenset({"timed_out", "timeout_kill", "gave_up"})
# Architect E-20260811T175305Z — whole-tree compile unsatisfiable mid-partition
SCOPED_COMPILE_CHECKS = frozenset({"compile", "test_compile"})
# phase-dispatch.yaml M3 required_checks: task_scoped_tests
SCOPED_TEST_GOALS = frozenset({"test", "verify"})


def resolve_task_id(explicit: str | None) -> str:
    """Native spawn publishes HERMES_KANBAN_TASK. Do not mint a second id."""
    tid = (explicit or "").strip() or os.environ.get("HERMES_KANBAN_TASK", "").strip()
    return tid


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _migration_root(start: Path) -> Path:
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    while True:
        if (cur / "migration.yaml").is_file():
            return cur
        if cur == cur.parent:
            raise FileNotFoundError(
                f"no migration.yaml walking up from {start} (SR-2)"
            )
        cur = cur.parent


def run_scoped_compile(
    root: Path, task_id: str, body_path: Path, check: str
) -> tuple[bool, int, str]:
    """Return (ok, rc, cmd_label) via scope-filtered gate."""
    rel = (
        Path(".hermes")
        / "skills"
        / "harness"
        / "record-run-evidence"
        / "scripts"
        / "run-scoped-compile-gate.py"
    )
    scoped = root / rel
    if not scoped.is_file():
        try:
            mig = _migration_root(Path(__file__))
        except FileNotFoundError:
            mig = root
        scoped = mig / rel
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


def _cmd_has_dtest(parts: list[str]) -> bool:
    for i, tok in enumerate(parts):
        if tok == "-Dtest" or tok.startswith("-Dtest="):
            return True
        if tok == "-D" and i + 1 < len(parts) and parts[i + 1].startswith("test="):
            return True
    return False


def scoped_maven_test_cmd(cmd: str, item: dict, helpers: dict) -> tuple[str | None, str | None]:
    """Honor exit_criteria[].proves (L2a). Never run unscoped `mvn test`.

    Returns (cmd_to_run, fail_reason). fail_reason set ⇒ do not execute.
    """
    is_mvn, parts = helpers["semantic_exit_cmd_is_maven"](cmd)
    if not is_mvn or not parts:
        return str(cmd), None
    goal = parts[-1]
    if goal not in SCOPED_TEST_GOALS:
        return str(cmd), None
    if _cmd_has_dtest(parts):
        return str(cmd), None
    proves, perr = helpers["proving_test_rels"](item)
    if perr:
        return None, perr
    fqcns: list[str] = []
    for rel in proves or []:
        fq = helpers["proves_to_fqcn"](rel)
        if fq:
            fqcns.append(fq)
    if not fqcns:
        return None, (
            "unscoped mvn test/verify without proves FQCNs "
            "(task_scoped_tests; story-scope-and-exit.md L2a)"
        )
    new_parts = parts[:-1] + [f"-Dtest={','.join(fqcns)}", goal]
    return shlex.join(new_parts), None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", required=True)
    ap.add_argument(
        "--task-id",
        default="",
        help="Hermes card id; defaults to HERMES_KANBAN_TASK (native spawn)",
    )
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
    task_id = resolve_task_id(args.task_id)
    if not task_id:
        print(
            "FAIL: --task-id or HERMES_KANBAN_TASK required "
            "(do not guess story_id; native spawn publishes the card id)",
            file=sys.stderr,
        )
        return 1
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
    try:
        mig = _migration_root(Path(__file__))
    except FileNotFoundError:
        mig = root
    spec = (
        mig
        / ".hermes"
        / "skills"
        / "sdd"
        / "check-spec-readiness"
        / "scripts"
    )
    if spec.is_dir() and str(spec) not in sys.path:
        sys.path.insert(0, str(spec))
    try:
        from specimen_agnostic import (  # type: ignore
            proves_executable_errors,
            proves_to_fqcn,
            proving_test_rels,
            semantic_exit_cmd_is_maven,
        )
    except ImportError:
        proves_executable_errors = None  # type: ignore
        proves_to_fqcn = None  # type: ignore
        proving_test_rels = None  # type: ignore
        semantic_exit_cmd_is_maven = None  # type: ignore
    test_helpers = {
        "proves_to_fqcn": proves_to_fqcn,
        "proving_test_rels": proving_test_rels,
        "semantic_exit_cmd_is_maven": semantic_exit_cmd_is_maven,
    }
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
                    root, task_id, body_path, scoped_check
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
            run_cmd = str(cmd)
            if not all(test_helpers.values()):
                toks = run_cmd.split()
                if toks and toks[0].rsplit("/", 1)[-1] == "mvn" and toks[-1] in SCOPED_TEST_GOALS:
                    cmd_failed.append(check or "task_scoped_tests")
                    results.append(
                        {
                            "check": check,
                            "kind": "cmd",
                            "ok": False,
                            "cmd": run_cmd,
                            "detail": "cannot import specimen_agnostic to scope mvn test",
                            "scoped": False,
                        }
                    )
                    continue
            else:
                rewritten, scope_err = scoped_maven_test_cmd(
                    run_cmd, item, test_helpers
                )
                if scope_err:
                    cmd_failed.append(check or "task_scoped_tests")
                    results.append(
                        {
                            "check": check,
                            "kind": "cmd",
                            "ok": False,
                            "cmd": run_cmd,
                            "detail": scope_err,
                            "scoped": False,
                        }
                    )
                    continue
                if rewritten:
                    run_cmd = rewritten
            cp = subprocess.run(
                run_cmd,
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
                    "cmd": run_cmd,
                    "body_cmd": str(cmd),
                    "scoped": run_cmd != str(cmd),
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
        "wall-fit PASS bodies as sizing defects",
        "task_scoped_tests: mvn test/verify honors proves FQCNs; unscoped suite is refuse",
    ]
    cp_incomplete = False
    cp_path = root / "evidence" / "runs" / task_id / "checkpoint.json"
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
    if not args.skip_cmds:
        if proves_executable_errors is None:
            cmd_failed.append("proves_executable")
            results.append(
                {
                    "check": "proves_executable",
                    "kind": "assert",
                    "ok": False,
                    "detail": "specimen_agnostic.proves_executable_errors missing",
                }
            )
        else:
            for err in proves_executable_errors(root, body, stage="complete"):
                cmd_failed.append("proves_executable")
                results.append(
                    {
                        "check": "proves_executable",
                        "kind": "assert",
                        "ok": False,
                        "detail": err,
                    }
                )
        if cmd_failed:
            overall_ok = False
    payload = {
        "schema": SCHEMA,
        "task_id": task_id,
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
    out_dir = root / "evidence" / "runs" / task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "exit-eval.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"OK: wrote {out.relative_to(root)} overall_ok={overall_ok} failed={cmd_failed}")
    # Non-zero when cmd checks failed — wall death must surface red compile etc.
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
