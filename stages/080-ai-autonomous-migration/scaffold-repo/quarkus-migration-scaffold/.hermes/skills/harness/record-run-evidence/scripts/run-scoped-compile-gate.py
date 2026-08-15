#!/usr/bin/env python3
"""Scope-filtered compile / test-compile gate (Architect E-20260811T175305Z Class A).

Whole-tree `mvn -q test-compile` is unsatisfiable mid-partition (BANK-COMPILE-SCOPE-1).
This gate runs Maven, then FAIL-CLOSED only when error paths intersect the story's
`files_writable` (own scope). Out-of-scope errors → OK with typed note (not a skip).

Usage:
  python3 run-scoped-compile-gate.py /projects/modernized \\
    --task-id t_xxx --body evidence/bodies/m3-s-004.json [--goal test-compile|compile]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.scoped-compile-gate/v1"
# Maven / javac style: [ERROR] /abs/path/Foo.java:[12,34] error: ...
ERR_RE = re.compile(
    r"(?:\[ERROR\]\s+)?(/?(?:[\w./-]+)\.java)(?::\[|\s|:)",
)


def norm_rel(path: str, root: Path) -> str:
    p = path.replace("\\", "/")
    root_s = str(root).replace("\\", "/")
    for prefix in (
        root_s + "/",
        "/projects/modernized/",
        "projects/modernized/",
    ):
        if p.startswith(prefix):
            p = p[len(prefix) :]
    return p.lstrip("./")


def writable_rels(body: dict, root: Path) -> set[str]:
    out: set[str] = set()
    for item in body.get("files_writable") or body.get("write_set") or []:
        raw = None
        if isinstance(item, str):
            raw = item
        elif isinstance(item, dict):
            for k in ("dest", "dst", "destination", "path", "file"):
                if item.get(k):
                    raw = str(item[k])
                    break
        if not raw:
            continue
        rel = norm_rel(raw, root)
        if rel.endswith(".java") or rel.startswith("src/"):
            out.add(rel)
    return out


def error_paths(text: str, root: Path) -> set[str]:
    found: set[str] = set()
    for m in ERR_RE.finditer(text or ""):
        found.add(norm_rel(m.group(1), root))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--body", required=True, help="Typed body JSON (files_writable)")
    ap.add_argument(
        "--goal",
        choices=("test-compile", "compile"),
        default="test-compile",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    body_path = Path(args.body)
    if not body_path.is_file():
        body_path = root / args.body
    if not body_path.is_file():
        print(f"FAIL: body not found: {args.body}", file=sys.stderr)
        return 1
    if not (root / "pom.xml").is_file():
        print(f"FAIL: no pom.xml under {root}", file=sys.stderr)
        return 1

    body = json.loads(body_path.read_text(encoding="utf-8"))
    if isinstance(body.get("body"), dict):
        body = body["body"]
    scope = writable_rels(body, root)
    # build_config tasks (pom.xml only) have no src/ Java files in scope —
    # fall back to whole-tree compile (no scope filtering needed).
    has_java_scope = bool(scope)
    if not has_java_scope:
        # Check whether any writable path looks like a build config
        all_writable = [
            str(item) if isinstance(item, str) else item.get("dest") or item.get("dst") or item.get("path") or ""
            for item in body.get("files_writable") or body.get("write_set") or []
        ]
        is_build_config = any(
            x.endswith("pom.xml") or x.endswith(".gradle") or x.endswith("build.gradle")
            for x in all_writable
        )
        if not is_build_config:
            print("FAIL: files_writable empty — cannot scope-filter compile", file=sys.stderr)
            return 1
        # build_config: run whole-tree compile; any error is in-scope

    mvn_goal = "test-compile" if args.goal == "test-compile" else "compile"
    cp = subprocess.run(
        ["mvn", "-q", mvn_goal],
        cwd=root,
        text=True,
        capture_output=True,
    )
    blob = (cp.stdout or "") + "\n" + (cp.stderr or "")
    errs = error_paths(blob, root)
    in_scope: set[str] = set()
    for e in errs:
        for s in scope:
            if e == s or e.startswith(s.rstrip("/") + "/"):
                in_scope.add(e)
                break
    oos = sorted(errs - in_scope)
    in_scope_l = sorted(in_scope)

    ok = True
    reason = "mvn_green"
    if cp.returncode != 0:
        if in_scope_l:
            ok = False
            reason = "in_scope_compile_errors"
        else:
            ok = True
            reason = "oos_only_compile_errors_scoped_ok"

    out_dir = root / "evidence" / "runs" / args.task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "task_id": args.task_id,
        "goal": mvn_goal,
        "cmd": f"mvn -q {mvn_goal}",
        "mvn_rc": cp.returncode,
        "ok": ok,
        "reason": reason,
        "files_writable_count": len(scope),
        "error_paths": sorted(errs),
        "in_scope_errors": in_scope_l,
        "oos_errors": oos,
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stderr_tail": (cp.stderr or "")[-600:],
        "notes": [
            "Architect E-20260811T175305Z Class A — BANK-COMPILE-SCOPE-1 elevated",
            "OOS errors do not FAIL this gate; in-scope errors FAIL closed",
            "Do not use --skip-test-compile-gate; typed needs_input if blocked by OOS",
        ],
    }
    out = out_dir / f"scoped-{mvn_goal}-gate.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if not ok:
        print(
            f"FAIL: scoped {mvn_goal} — in-scope errors {in_scope_l} → {out.relative_to(root)}",
            file=sys.stderr,
        )
        return 1
    print(
        f"OK: scoped {mvn_goal} reason={reason} "
        f"oos_errors={len(oos)} → {out.relative_to(root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
