#!/usr/bin/env python3
"""B-16: print M3 attach skills from a typed body (one name per line).

Always includes check-spec-readiness (lint). Then identity.operand_skills
from the body, minus pom skills unless pom.xml is in files_writable.
phase-dispatch.yaml M3.skills[] is the allow-list on disk: every printed
name must already be in that pool (refuse; do not drop).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

LINT_SKILL = "check-spec-readiness"


def _specimen(root: Path):
    path = (
        root
        / ".hermes"
        / "skills"
        / "sdd"
        / "check-spec-readiness"
        / "scripts"
        / "specimen_agnostic.py"
    )
    spec = importlib.util.spec_from_file_location("_attach_specimen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def attach_skills(body: dict, root: Path) -> list[str]:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    operand = ident.get("operand_skills") or []
    if isinstance(operand, str):
        operand = [operand]
    out: list[str] = []
    seen: set[str] = set()

    def add(name: object) -> None:
        n = str(name or "").strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)

    add(LINT_SKILL)
    if isinstance(operand, list):
        for s in operand:
            add(s)
    fw = body.get("files_writable") or ident.get("files_writable") or []
    if not isinstance(fw, list):
        fw = []
    return _specimen(root).filter_attach_skills_for_write_set(out, fw)


def load_m3_pool(root: Path) -> list[str]:
    reader = Path(__file__).resolve().parent / "read-phase-dispatch.py"
    yaml_path = root / ".hermes" / "phase-dispatch.yaml"
    if not yaml_path.is_file():
        raise FileNotFoundError(f"missing {yaml_path}")
    cp = subprocess.run(
        [
            sys.executable,
            str(reader),
            "--yaml",
            str(yaml_path),
            "--phase",
            "M3",
            "--print",
            "skills",
        ],
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    if cp.returncode != 0:
        err = (cp.stderr or cp.stdout or "").strip()
        raise RuntimeError(f"read-phase-dispatch.py rc={cp.returncode}: {err}")
    return [ln.strip() for ln in (cp.stdout or "").splitlines() if ln.strip()]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Print B-16 M3 attach skills from a typed body JSON (one per line)."
    )
    p.add_argument("body", help="path to typed M3 body JSON")
    p.add_argument("--root", default=".", help="scaffold root (phase-dispatch.yaml)")
    args = p.parse_args(argv)
    path = Path(args.body)
    if not path.is_file():
        print(f"FAIL: missing body {path}", file=sys.stderr)
        return 1
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot read body: {exc}", file=sys.stderr)
        return 1
    if not isinstance(body, dict):
        print("FAIL: body is not an object", file=sys.stderr)
        return 1
    root = Path(args.root).resolve()
    try:
        names = attach_skills(body, root)
    except (OSError, RuntimeError) as exc:
        print(f"FAIL: cannot filter attach skills: {exc}", file=sys.stderr)
        return 1
    try:
        pool = load_m3_pool(root)
    except (OSError, RuntimeError) as exc:
        print(f"FAIL: cannot load yaml M3.skills: {exc}", file=sys.stderr)
        return 1
    extra = [n for n in names if n not in pool]
    if extra:
        print(
            "FAIL: attach names not in yaml M3.skills: "
            f"{extra} (pool is superset, not a subset filter)",
            file=sys.stderr,
        )
        return 1
    for name in names:
        print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
