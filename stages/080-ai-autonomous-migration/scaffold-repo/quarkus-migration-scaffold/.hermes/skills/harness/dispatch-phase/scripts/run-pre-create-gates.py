#!/usr/bin/env python3
"""Run M3 pre-create gates for one body; print one OK/REFUSE line.

Holder must not invoke the 17 gates, python3 -c, execute_code, or dump
JSON. Child stdout/stderr stay captured. JSON-looking lines are dropped
from the REFUSE reason.

Usage:
  python3 run-pre-create-gates.py --root /projects/modernized \\
    --body evidence/bodies/m3-foundational.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def skill(root: Path, *parts: str) -> Path:
    return root.joinpath(".hermes", "skills", *parts)


def reason_line(text: str) -> str:
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s[:1] in "{[":
            continue
        return s[:200]
    return "rc!=0"


def run_step(root: Path, name: str, argv: list[str]) -> int:
    cp = subprocess.run(
        argv,
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    if cp.returncode == 0:
        return 0
    blob = (cp.stderr or "") + "\n" + (cp.stdout or "")
    print(f"REFUSE: {name} rc={cp.returncode} {reason_line(blob)}")
    return cp.returncode if cp.returncode != 0 else 1


def attach_skills(root: Path, body: Path) -> list[str] | int:
    script = skill(root, "harness", "dispatch-phase", "scripts", "m3-attach-skills.py")
    cp = subprocess.run(
        [sys.executable, str(script), str(body), "--root", str(root)],
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    if cp.returncode != 0:
        print(
            f"REFUSE: m3-attach-skills.py rc={cp.returncode} "
            f"{reason_line((cp.stderr or '') + (cp.stdout or ''))}"
        )
        return cp.returncode if cp.returncode != 0 else 1
    return [ln.strip() for ln in (cp.stdout or "").splitlines() if ln.strip()]


def story_id(body: Path) -> str:
    try:
        raw = json.loads(body.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return body.stem
    if isinstance(raw.get("body"), dict):
        raw = raw["body"]
    ident = raw.get("identity") if isinstance(raw, dict) else {}
    if isinstance(ident, dict) and ident.get("story_id"):
        return str(ident["story_id"])
    stem = body.stem
    return stem[3:] if stem.startswith("m3-") else stem


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--body", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    body = Path(args.body)
    if not body.is_file():
        body = root / args.body
    if not body.is_file():
        print(f"REFUSE: missing body {args.body}")
        return 1
    try:
        rel = str(body.resolve().relative_to(root))
    except ValueError:
        rel = str(body)
    py = sys.executable
    sdd = skill(root, "sdd", "check-spec-readiness", "scripts")
    disp = skill(root, "harness", "dispatch-phase", "scripts")
    rec = skill(root, "harness", "record-run-evidence", "scripts")

    steps: list[tuple[str, list[str]]] = [
        ("check-create-path-tip-sync.py", [py, str(disp / "check-create-path-tip-sync.py"), str(root)]),
        ("check-phase-body-script-refs.py", [py, str(disp / "check-phase-body-script-refs.py"), str(root)]),
        (
            "relocate-descendant-import-writesets.py",
            [
                py,
                str(sdd / "relocate-descendant-import-writesets.py"),
                str(root),
                "--write",
            ],
        ),
        (
            "stamp-body-dependencies.py",
            [py, str(sdd / "stamp-body-dependencies.py"), str(root), "--body", rel, "--write"],
        ),
        (
            "check-interface-closure.py",
            [py, str(sdd / "check-interface-closure.py"), str(root), "--body", rel],
        ),
        (
            "stamp-destination-inventory.py",
            [py, str(sdd / "stamp-destination-inventory.py"), str(root), "--body", rel, "--write"],
        ),
        (
            "check-partition-coverage.py",
            [
                py,
                str(sdd / "check-partition-coverage.py"),
                str(root),
                "--write-receipt",
                "evidence/receipts/partition-coverage/latest.json",
            ],
        ),
        (
            "assert-partition-topological-order.py",
            [py, str(sdd / "assert-partition-topological-order.py"), str(root)],
        ),
        ("assert-quarantine-tombstones.py", [py, str(sdd / "assert-quarantine-tombstones.py"), str(root)]),
        (
            "assert-mint-constraints-complete.py --inject",
            [py, str(sdd / "assert-mint-constraints-complete.py"), str(root), "--body", rel, "--inject"],
        ),
        (
            "assert-mint-constraints-complete.py",
            [py, str(sdd / "assert-mint-constraints-complete.py"), str(root), "--body", rel],
        ),
        (
            "assert-constraints-preserved.py",
            [py, str(sdd / "assert-constraints-preserved.py"), str(root), "--body", rel, "--snapshot-before"],
        ),
        (
            "assert-dependency-closure.py",
            [py, str(sdd / "assert-dependency-closure.py"), str(root), "--body", rel],
        ),
        (
            "check-kanban-body.py",
            [py, str(sdd / "check-kanban-body.py"), str(root), "--body", rel],
        ),
        ("check-phase-attach-matrix.py", [py, str(disp / "check-phase-attach-matrix.py"), str(root)]),
        (
            "assert-bundle-skills-exist.py",
            [py, str(disp / "assert-bundle-skills-exist.py"), str(root), "--bundle", "m3-implementer"],
        ),
    ]
    sidecar = body.with_suffix(body.suffix + ".sha256.json")
    digest_argv = [py, str(rec / "stamp-body-digest.py"), str(body)]
    if sidecar.is_file():
        digest_argv.append("--allow-sidecar-only")
    steps.append(("stamp-body-digest.py", digest_argv))
    steps.extend(
        [
            (
                "check-surgical-scopes.py",
                [py, str(sdd / "check-surgical-scopes.py"), str(root), rel],
            ),
            (
                "check-semantic-exits.py",
                [py, str(sdd / "check-semantic-exits.py"), str(root), rel],
            ),
            (
                "check-operand-count.py",
                [py, str(sdd / "check-operand-count.py"), str(root), rel, "--wall-fit"],
            ),
            (
                "assert-mint-oracles.py",
                [py, str(sdd / "assert-mint-oracles.py"), str(root), "--body", rel, "--skip-task-id"],
            ),
        ]
    )
    for name, argv in steps:
        rc = run_step(root, name, argv)
        if rc != 0:
            return rc
    skills = attach_skills(root, body)
    if isinstance(skills, int):
        return skills
    disabled_argv = [py, str(disp / "assert-skills-not-disabled.py"), str(root)]
    for name in skills:
        disabled_argv.extend(["--skill", name])
    rc = run_step(root, "assert-skills-not-disabled.py", disabled_argv)
    if rc != 0:
        return rc
    print(f"OK: pre-create gates {story_id(body)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
