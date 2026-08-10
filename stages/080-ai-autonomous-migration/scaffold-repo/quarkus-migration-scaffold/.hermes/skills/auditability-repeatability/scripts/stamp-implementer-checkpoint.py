#!/usr/bin/env python3
"""Mark dest path(s) completed on an implementer checkpoint (resume seam).

S-010 Class A #1b / Deputy E-20260810T115113Z: completing a src/test/** operand
requires a green mvn test-compile gate first (structural invariant, not prose).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.implementer-checkpoint/v1"


def normalize(raw: str) -> str:
    p = raw.replace("\\", "/")
    if "/projects/modernized/" in p:
        p = p.split("/projects/modernized/", 1)[1]
    return p


def is_test_operand(p: str) -> bool:
    return p.startswith("src/test/") or "/src/test/" in p


def workspace_root(checkpoint: Path) -> Path:
    # .../migration/runs/<task>/checkpoint.json → repo root
    return checkpoint.resolve().parents[3]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkpoint")
    ap.add_argument(
        "--completed",
        action="append",
        default=[],
        help="Dest-relative path completed (repeatable)",
    )
    ap.add_argument(
        "--skip-test-compile-gate",
        action="store_true",
        help="Fixture/authoring only — FORBIDDEN on live implementer seats",
    )
    args = ap.parse_args()
    path = Path(args.checkpoint)
    if not path.is_file():
        print(f"FAIL: checkpoint missing: {path}", file=sys.stderr)
        return 1
    if not args.completed:
        print("FAIL: pass --completed PATH", file=sys.stderr)
        return 1
    ck = json.loads(path.read_text(encoding="utf-8"))
    if ck.get("schema") != SCHEMA:
        print(f"FAIL: bad schema {ck.get('schema')!r}", file=sys.stderr)
        return 1
    work = list(ck.get("work_list") or [])
    done = list(ck.get("completed") or [])
    new_paths: list[str] = []
    for raw in args.completed:
        p = normalize(raw)
        if p not in work:
            print(f"FAIL: {p} not in work_list", file=sys.stderr)
            return 1
        if p not in done:
            done.append(p)
            new_paths.append(p)

    test_paths = [p for p in new_paths if is_test_operand(p)]
    if test_paths and not args.skip_test_compile_gate:
        root = workspace_root(path)
        gate = (
            Path(__file__).resolve().parent / "run-test-compile-gate.py"
        )
        cmd = [
            sys.executable,
            str(gate),
            str(root),
            "--task-id",
            str(ck.get("task_id") or "unknown"),
        ]
        for p in test_paths:
            cmd.extend(["--paths", p])
        cp = subprocess.run(cmd, text=True, capture_output=True)
        sys.stderr.write(cp.stderr or "")
        sys.stdout.write(cp.stdout or "")
        if cp.returncode != 0:
            print(
                "FAIL: refuse checkpoint advance — src/test operand(s) without "
                "green test-compile gate (Deputy E-115113Z #1b invariant). "
                f"paths={test_paths}",
                file=sys.stderr,
            )
            return 1
        gates = list(ck.get("test_compile_gates") or [])
        gates.append(
            {
                "paths": test_paths,
                "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ok": True,
            }
        )
        ck["test_compile_gates"] = gates

    remaining = [p for p in work if p not in done]
    ck["completed"] = done
    ck["next"] = remaining[0] if remaining else None
    ck["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(ck, indent=2) + "\n", encoding="utf-8")
    print(f"OK: completed={len(done)}/{len(work)} next={ck['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
