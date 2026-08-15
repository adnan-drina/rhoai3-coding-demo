#!/usr/bin/env python3
"""Mark dest path(s) completed on an implementer checkpoint (resume seam).

S-010 Class A #1b / Deputy E-20260810T115113Z + Architect E-20260811T175305Z:
completing a src/test/** operand requires a green **scoped** test-compile gate.
`--skip-test-compile-gate` is FORBIDDEN on live seats (fixture env only).
"""
from __future__ import annotations

import argparse
import json
import os
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


def resolve_migration_root(start: Path) -> Path:
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


def workspace_root(checkpoint: Path) -> Path:
    # evidence/runs/<task>/checkpoint.json → repo root via sentinel, not hop count
    return resolve_migration_root(checkpoint)


def resolve_body(root: Path, ck: dict) -> Path | None:
    for key in ("body_path", "typed_body", "body"):
        raw = ck.get(key)
        if isinstance(raw, str) and raw.endswith(".json"):
            p = Path(raw)
            if not p.is_file():
                p = root / raw
            if p.is_file():
                return p
    # Convention: evidence/bodies/m3-s-NNN.json from task title/story — scan refs
    refs = ck.get("refs") or []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        if ref.get("key") in ("typed_body", "body"):
            p = root / str(ref.get("path") or "")
            if p.is_file():
                return p
    # Fallback: body mentioned in work metadata
    story = ck.get("story_id") or ck.get("story")
    if story:
        cand = root / "evidence" / "bodies" / f"m3-{str(story).lower()}.json"
        if cand.is_file():
            return cand
        cand = root / "evidence" / "bodies" / f"{story}.json"
        if cand.is_file():
            return cand
    return None


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
        "--body",
        default="",
        help="Typed body JSON for scoped compile gate (required when stamping src/test/**)",
    )
    ap.add_argument(
        "--skip-test-compile-gate",
        action="store_true",
        help="FORBIDDEN on live seats — requires RHOAI3_FIXTURE_ALLOW_SKIP_TEST_COMPILE=1",
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
    if test_paths:
        if args.skip_test_compile_gate:
            if os.environ.get("RHOAI3_FIXTURE_ALLOW_SKIP_TEST_COMPILE") != "1":
                print(
                    "FAIL: --skip-test-compile-gate FORBIDDEN on live implementer seats "
                    "(Architect E-20260811T175305Z). Compliant fork: typed needs_input "
                    "BLOCK — do not bypass. Fixtures may set "
                    "RHOAI3_FIXTURE_ALLOW_SKIP_TEST_COMPILE=1.",
                    file=sys.stderr,
                )
                return 1
            print(
                "WARN: fixture skip-test-compile-gate allowed by env",
                file=sys.stderr,
            )
        else:
            root = workspace_root(path)
            body = Path(args.body) if args.body else None
            if body and not body.is_file():
                body = root / args.body
            if body is None or not body.is_file():
                body = resolve_body(root, ck)
            if body is None or not body.is_file():
                print(
                    "FAIL: scoped test-compile gate needs --body <typed body json> "
                    "(Architect E-20260811T175305Z Class A compile-scope). "
                    "Cannot silently skip.",
                    file=sys.stderr,
                )
                return 1
            gate = Path(__file__).resolve().parent / "run-scoped-compile-gate.py"
            cmd = [
                sys.executable,
                str(gate),
                str(root),
                "--task-id",
                str(ck.get("task_id") or "unknown"),
                "--body",
                str(body),
                "--goal",
                "test-compile",
            ]
            cp = subprocess.run(cmd, text=True, capture_output=True)
            sys.stderr.write(cp.stderr or "")
            sys.stdout.write(cp.stdout or "")
            if cp.returncode != 0:
                print(
                    "FAIL: refuse checkpoint advance — scoped test-compile gate red "
                    f"for src/test operand(s) {test_paths}. "
                    "If failures are OOS-only the scoped gate should PASS; "
                    "in-scope errors must be fixed. Typed needs_input if blocked.",
                    file=sys.stderr,
                )
                return 1
            gates = list(ck.get("test_compile_gates") or [])
            gates.append(
                {
                    "paths": test_paths,
                    "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "ok": True,
                    "scoped": True,
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
