#!/usr/bin/env python3
"""ADR-35 / ADR-40 — M3 write-inversion loop (Qwen port).

Same shape as profile_prose_loop / ADR-32 decide:
  harness enumerates typed tasks → model returns one judgment → harness writes.

Seat MUST NOT author task id or acceptance (F-taskid-generated /
F-acceptance-derived). Packet includes context_for SNIPPETs (O-M3SNIPPET).

Backends:
  dry-run       — deterministic fixture judgment (instruments)
  opencode-qwen — OpenCode returns JSON; harness upserts + re-renders tasks.md

Usage:
  m3_task_loop.py run --root DIR [--sid SID] [--backend opencode-qwen|dry-run]
  m3_task_loop.py upsert --root DIR --unit-key K --goal '…' [--plan …] [--risk …]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent


def _log(msg: str, *, err: bool = False) -> None:
    print(msg, file=sys.stderr if err else sys.stdout, flush=True)


def _load_model_api():
    sys.path.insert(0, str(HERE))
    import model as m  # type: ignore

    return m


def _unfilled(tasks: list[dict]) -> list[dict]:
    out = []
    for t in tasks:
        goal = (t.get("goal") or "").strip()
        if t.get("filled") and len(goal) >= 20:
            continue
        if "JUDGMENT" in goal or len(goal) < 20:
            out.append(t)
    return out


def _dry_run_judgment(task: dict) -> dict:
    keys = task.get("unit_keys") or []
    slug = keys[0].rsplit(".", 1)[-1] if keys else "unit"
    role = task.get("role") or "UNDECIDED"
    return {
        "unit_keys": keys,
        "goal": (
            f"Migrate {slug} ({role}) using projected SNIPPET/contract facts only; "
            f"harness-owned acceptance applies."
        ),
        "plan": f"Apply {task.get('class')}/{task.get('shape')} for {slug}",
        "risk": "low" if role == "HARVEST" else "medium",
    }


def _parse_judgment(blob: str, expect_keys: list[str]) -> Optional[dict]:
    """Extract {unit_keys|unit_key, goal, plan?, risk?} — reject id/acceptance."""
    candidates: list[dict] = []
    for m in re.finditer(r"\{.*?\}", blob, re.S):
        try:
            o = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            candidates.append(o)
    # also try last balanced object
    start, end = blob.rfind("{"), blob.rfind("}")
    if start >= 0 and end > start:
        try:
            o = json.loads(blob[start : end + 1])
            if isinstance(o, dict):
                candidates.append(o)
        except json.JSONDecodeError:
            pass
    expect = sorted(expect_keys)
    for o in candidates:
        if o.get("id") not in (None, ""):
            continue  # F-taskid-generated — ignore / refuse later on upsert
        if o.get("acceptance") not in (None, "", [], {}):
            continue
        keys = o.get("unit_keys")
        if not keys and o.get("unit_key"):
            keys = [o["unit_key"]]
        if not isinstance(keys, list):
            continue
        if sorted(str(k) for k in keys) != expect:
            continue
        goal = o.get("goal")
        if isinstance(goal, str) and len(goal.strip()) >= 20:
            return {
                "unit_keys": [str(k) for k in keys],
                "goal": goal.strip(),
                "plan": str(o.get("plan") or "").strip(),
                "risk": str(o.get("risk") or "").strip(),
            }
    return None


def _opencode_judgment(
    root: Path,
    *,
    task: dict,
    sid: str,
    worker_model: str,
    timeout: int,
    legacy: str,
) -> dict:
    m = _load_model_api()
    model = m.load(root)
    projected = m.context_for(model, sid, root=root)
    keys = list(task.get("unit_keys") or [])
    packet = "\n".join(
        [
            "Author JUDGMENT for ONE typed M3 task. Harness owns id + acceptance.",
            f"story: {sid}",
            f"unit_keys: {json.dumps(keys)}",
            f"role: {task.get('role')}",
            f"class/shape: {task.get('class')}/{task.get('shape')}",
            f"owns: {task.get('owns')}",
            "Acceptance is ALREADY DERIVED — do NOT invent acceptance or task id.",
            "ALL code quotes are in SNIPPET lines in DERIVED FACTS — do NOT read legacy.",
            "",
            projected,
            "",
            "Reply with ONLY this JSON (no file edits, no tools required):",
            json.dumps(
                {
                    "unit_keys": keys,
                    "goal": "<one sentence from brief + SNIPPET>",
                    "plan": "<short plan>",
                    "risk": "low|medium|high",
                }
            ),
            "Rules:",
            "- do NOT include id or acceptance fields (refused)",
            "- do NOT edit specs/**/tasks.md (harness writes)",
            "- do NOT git commit",
            "- goal ≥ 20 chars",
        ]
    )
    slog = Path("/tmp") / f"m3-task-{sid}-{task.get('seq')}.log"
    slog.write_text(packet[:2000] + "\n…\n", encoding="utf-8")
    # Prefer workspace opencode wrapper used by outer-loop
    cmd = [
        "bash",
        "-lc",
        (
            f"cd {root!s} && "
            f"timeout {int(timeout)} opencode run --model {worker_model!s} "
            f"<<'EOF'\n{packet}\nEOF"
        ),
    ]
    # Simpler: pipe packet via env file
    pfile = Path("/tmp") / f"m3-task-prompt-{sid}-{task.get('seq')}.txt"
    pfile.write_text(packet, encoding="utf-8")
    env = os.environ.copy()
    try:
        proc = subprocess.run(
            [
                "timeout",
                str(int(timeout)),
                "opencode",
                "run",
                "--model",
                worker_model,
                str(pfile),
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    except FileNotFoundError:
        # Fallback: hermes-style not available — raise for outer retry
        raise RuntimeError("opencode binary not found for m3_task_loop")
    blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
    slog.write_text(blob, encoding="utf-8")
    parsed = _parse_judgment(blob, keys)
    if not parsed:
        raise RuntimeError(
            f"m3_task_loop: no valid judgment JSON for {keys} (see {slog})"
        )
    return parsed


def run_loop(
    root: Path,
    *,
    sid: str = "",
    backend: str = "opencode-qwen",
    worker_model: str = "",
    timeout: int = 180,
    legacy: str = "/projects/legacy",
    limit: int = 0,
) -> int:
    m = _load_model_api()
    model = m.load(root)
    if not (model.get("tasks") or []):
        model = m.assign_tasks(root, model)
    sids = [sid] if sid else sorted(
        {t.get("sid") for t in (model.get("tasks") or []) if t.get("sid")}
    )
    worker_model = worker_model or os.environ.get(
        "WORKER_MODEL", "qwen27b/qwen3-6-27b"
    )
    ok = fail = 0
    for s in sids:
        tasks = _unfilled(m.tasks_for_story(model, s))
        if limit > 0:
            tasks = tasks[:limit]
        _log(f"m3_task_loop: {s} unfilled={len(tasks)} backend={backend}")
        for t in tasks:
            keys = list(t.get("unit_keys") or [])
            try:
                if backend == "dry-run":
                    j = _dry_run_judgment(t)
                elif backend in ("opencode-qwen", "opencode", "qwen"):
                    j = _opencode_judgment(
                        root,
                        task=t,
                        sid=s,
                        worker_model=worker_model,
                        timeout=timeout,
                        legacy=legacy,
                    )
                else:
                    raise ValueError(f"unknown backend {backend}")
                m.upsert_task_judgment(
                    root,
                    unit_keys=j["unit_keys"],
                    goal=j["goal"],
                    plan=j.get("plan") or "",
                    risk=j.get("risk") or "",
                    payload=j,
                )
                ok += 1
                _log(f"  OK {t.get('id')} keys={keys}")
            except Exception as e:
                fail += 1
                _log(f"  FAIL {t.get('id')}: {e}", err=True)
        # refresh model after story
        model = m.load(root)
        m.render_tasks_md(root, s, model)
    _log(f"m3_task_loop: done ok={ok} fail={fail}")
    return 1 if fail else 0


def cmd_upsert(args: argparse.Namespace) -> int:
    m = _load_model_api()
    keys = [k for k in (args.unit_key or []) if k]
    if args.unit_keys_json:
        keys = json.loads(args.unit_keys_json)
    try:
        t = m.upsert_task_judgment(
            Path(args.root).resolve(),
            unit_keys=keys,
            goal=args.goal,
            plan=args.plan or "",
            risk=args.risk or "",
            payload={
                k: v
                for k, v in {
                    "id": args.forbid_id,
                    "acceptance": args.forbid_acceptance,
                }.items()
                if v
            }
            if (args.forbid_id or args.forbid_acceptance)
            else {},
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(json.dumps({"id": t.get("id"), "filled": t.get("filled")}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ADR-35 M3 write-inversion loop")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run")
    r.add_argument("--root", default=".")
    r.add_argument("--sid", default="")
    r.add_argument("--backend", default="opencode-qwen")
    r.add_argument("--worker-model", default="")
    r.add_argument("--timeout", type=int, default=180)
    r.add_argument("--legacy", default="/projects/legacy")
    r.add_argument("--limit", type=int, default=0)
    r.set_defaults(
        func=lambda a: run_loop(
            Path(a.root).resolve(),
            sid=a.sid,
            backend=a.backend,
            worker_model=a.worker_model,
            timeout=a.timeout,
            legacy=a.legacy,
            limit=a.limit,
        )
    )

    u = sub.add_parser("upsert")
    u.add_argument("--root", default=".")
    u.add_argument("--unit-key", action="append", default=[])
    u.add_argument("--unit-keys-json", default="")
    u.add_argument("--goal", required=True)
    u.add_argument("--plan", default="")
    u.add_argument("--risk", default="")
    u.add_argument("--forbid-id", default="", help="instruments: inject id to refuse")
    u.add_argument(
        "--forbid-acceptance", default="", help="instruments: inject acceptance to refuse"
    )
    u.set_defaults(func=cmd_upsert)

    args = ap.parse_args()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
