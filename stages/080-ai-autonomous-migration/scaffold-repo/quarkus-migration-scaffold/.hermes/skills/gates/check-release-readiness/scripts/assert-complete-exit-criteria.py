#!/usr/bin/env python3
"""Architect E-20260811T175509Z Class A — refuse complete when cmd exits fail.

BANK-COMPLETE-CMD-1 elevated: Hermes `kanban_complete` does not evaluate
cmd-shaped exit_criteria. Workers MUST run this script (rc=0) before calling
`kanban_complete`. Lead/watchdog MAY reclaim `done` cards that lack a green
receipt via enforce-complete-exit-criteria.py.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.complete-exit-ok/v1"
_DEST_POM_REL = (
    Path(".hermes")
    / "skills"
    / "sdd"
    / "check-spec-readiness"
    / "scripts"
    / "assert-dest-pom-extensions.py"
)
_DEST_POM_FROM_SKILLS = (
    Path("sdd")
    / "check-spec-readiness"
    / "scripts"
    / "assert-dest-pom-extensions.py"
)


def _locate_dest_pom_extensions_script(root: Path) -> Path:
    """Seat copy first; else walk from this file to the skills tree.

    Do not use Path.parents[N] (SR-2). Fixtures often have no dest .hermes copy.
    One dest-pom predicate; generator configuration is a case of it.
    """
    in_root = root / _DEST_POM_REL
    if in_root.is_file():
        return in_root
    here = Path(__file__).resolve().parent
    d = here
    while True:
        from_skills = d / _DEST_POM_FROM_SKILLS
        if from_skills.is_file():
            return from_skills
        seat = d / _DEST_POM_REL
        if seat.is_file():
            return seat
        parent = d.parent
        if parent == d:
            return in_root
        d = parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--task-id",
        default="",
        help="Hermes card id; defaults to HERMES_KANBAN_TASK (native spawn)",
    )
    ap.add_argument("--body", required=True)
    args = ap.parse_args()
    task_id = (args.task_id or "").strip() or os.environ.get(
        "HERMES_KANBAN_TASK", ""
    ).strip()
    if not task_id:
        print(
            "FAIL: --task-id or HERMES_KANBAN_TASK required "
            "(do not guess story_id; native spawn publishes the card id)",
            file=sys.stderr,
        )
        return 1
    root = Path(args.root).resolve()
    body = Path(args.body)
    if not body.is_file():
        body = root / args.body
    if not body.is_file():
        print(f"FAIL: body not found: {args.body}", file=sys.stderr)
        return 1

    eval_py = (
        Path(__file__).resolve().parent / "evaluate-exit-criteria.py"
    )
    cp = subprocess.run(
        [
            sys.executable,
            str(eval_py),
            str(root),
            "--body",
            str(body),
            "--task-id",
            task_id,
            "--trigger",
            "complete",
        ],
        text=True,
        capture_output=True,
    )
    sys.stdout.write(cp.stdout or "")
    sys.stderr.write(cp.stderr or "")

    eval_path = root / "evidence" / "runs" / task_id / "exit-eval.json"
    overall_ok = False
    cmd_failed: list = []
    if eval_path.is_file():
        try:
            payload = json.loads(eval_path.read_text(encoding="utf-8"))
            overall_ok = bool(payload.get("overall_ok"))
            cmd_failed = list(payload.get("cmd_failed") or [])
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    out_dir = root / "evidence" / "runs" / task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": SCHEMA,
        "task_id": task_id,
        "ok": overall_ok and cp.returncode == 0,
        "eval_rc": cp.returncode,
        "cmd_failed": cmd_failed,
        "exit_eval": str(eval_path.relative_to(root)) if eval_path.is_file() else None,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": [
            "Architect E-20260811T175509Z Class A — BANK-COMPLETE-CMD-1 elevated",
            "Architect E-20260814T205052Z DD3 — check-kanban-body on complete path",
            "kanban_complete MUST NOT be called unless ok=true",
            "compile/test_compile use scope-filtered gate (compile-scope-filtered.md)",
            "http_semantics mvn test/verify honors proves FQCNs (task_scoped_tests)",
            "--task-id defaults to HERMES_KANBAN_TASK; do not mint {TASK_ID}",
        ],
    }
    out = out_dir / "complete-exit-ok.json"
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    if not receipt["ok"]:
        print(
            f"FAIL: refuse kanban_complete — cmd exits failed {cmd_failed} "
            f"(receipt {out.relative_to(root)})",
            file=sys.stderr,
        )
        return 1

    # Architect E-20260813T152211Z / Lead wire-or-retire: AD-H §17/§19 must not
    # depend on skill_view. Invoke enforcement scripts on the complete path.
    # Wave B tip layout: enforcement scripts live under .hermes/skills/harness/
    # (skills/harness retained as legacy fallback).
    skills = root / ".hermes" / "skills" / "harness"
    enforcement = root / ".hermes" / "enforcement"
    gates = root / ".hermes" / "skills" / "gates" / "check-release-readiness" / "scripts"

    def find_script(rel: str) -> Path:
        for base in (enforcement, skills):
            cand = base / rel
            if cand.is_file():
                return cand
        return skills / rel  # for missing-script error path

    citation = find_script("ground-in-harvest/scripts/check-citation.py")
    body_digest = find_script(
        "record-run-evidence/scripts/check-body-digest-match.py"
    )
    provenance = find_script("record-run-evidence/scripts/check-provenance.py")
    runnable_db = gates / "check-runnable-db-config.py"
    empty_security = gates / "check-empty-security.py"
    test_toolchain = gates / "check-test-toolchain.py"
    kanban_body = (
        root
        / ".hermes"
        / "skills"
        / "sdd"
        / "check-spec-readiness"
        / "scripts"
        / "check-kanban-body.py"
    )
    for label, cmd in (
        (
            "kanban-body",
            [sys.executable, str(kanban_body), str(root), "--body", str(body)],
        ),
        (
            "body-digest",
            [sys.executable, str(body_digest), str(root), "--body", str(body)],
        ),
        (
            "citation",
            [
                sys.executable,
                str(citation),
                str(root),
                "--packet",
                str(body),
            ],
        ),
        (
            "provenance",
            [sys.executable, str(provenance), str(root)],
        ),
        # A2 / runnable-db-security — refuse complete on HSQLDB / empty security
        (
            "runnable-db-config",
            [sys.executable, str(runnable_db), str(root)],
        ),
        (
            "empty-security",
            [sys.executable, str(empty_security), str(root)],
        ),
        (
            "test-toolchain",
            [sys.executable, str(test_toolchain), str(root)],
        ),
    ):
        if not Path(cmd[1]).is_file():
            print(f"FAIL: missing enforcement script for {label}: {cmd[1]}", file=sys.stderr)
            return 2
        sub = subprocess.run(cmd, text=True, capture_output=True)
        sys.stdout.write(sub.stdout or "")
        sys.stderr.write(sub.stderr or "")
        if sub.returncode != 0:
            print(
                f"FAIL: refuse kanban_complete — {label} enforcement rc={sub.returncode} "
                f"(Architect E-20260813T152211Z mechanical path)",
                file=sys.stderr,
            )
            return 1 if sub.returncode == 1 else sub.returncode

    dest_pom = _locate_dest_pom_extensions_script(Path(root))
    if dest_pom.is_file():
        sub = subprocess.run(
            [
                sys.executable,
                str(dest_pom),
                str(root),
                "--body",
                str(body),
            ],
            text=True,
            capture_output=True,
        )
        sys.stdout.write(sub.stdout or "")
        sys.stderr.write(sub.stderr or "")
        if sub.returncode != 0:
            print(
                f"FAIL: refuse kanban_complete — dest-pom-extensions rc={sub.returncode} "
                f"(V35-EXTENSIONS dest-only; generator is a case; do not union legacy)",
                file=sys.stderr,
            )
            return 1 if sub.returncode == 1 else sub.returncode
    else:
        print(f"FAIL: missing dest-pom-extensions script: {dest_pom}", file=sys.stderr)
        return 2

    setup_jdbc = (
        root
        / ".hermes"
        / "skills"
        / "sdd"
        / "check-spec-readiness"
        / "scripts"
        / "assert-setup-datasource-driver.py"
    )
    if not setup_jdbc.is_file():
        setup_jdbc = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "sdd"
            / "check-spec-readiness"
            / "scripts"
            / "assert-setup-datasource-driver.py"
        )
    if not setup_jdbc.is_file():
        print(f"FAIL: missing setup-datasource-driver script: {setup_jdbc}", file=sys.stderr)
        return 2
    sub = subprocess.run(
        [sys.executable, str(setup_jdbc), str(root)],
        text=True,
        capture_output=True,
    )
    sys.stdout.write(sub.stdout or "")
    sys.stderr.write(sub.stderr or "")
    if sub.returncode != 0:
        print(
            f"FAIL: refuse kanban_complete — SETUP_JDBC rc={sub.returncode}",
            file=sys.stderr,
        )
        return 1 if sub.returncode == 1 else sub.returncode

    inner: dict = {}
    try:
        raw_body = json.loads(body.read_text(encoding="utf-8"))
        maybe = raw_body.get("body") if isinstance(raw_body.get("body"), dict) else raw_body
        if isinstance(maybe, dict):
            inner = maybe
    except (OSError, json.JSONDecodeError, TypeError):
        inner = {}
    ident = inner.get("identity") if isinstance(inner.get("identity"), dict) else {}
    writes = inner.get("files_writable") or ident.get("files_writable") or []
    writes_l = [str(x).replace("\\", "/") for x in writes if isinstance(x, str)]
    owns_pom = any(p == "pom.xml" or p.endswith("/pom.xml") for p in writes_l)
    if owns_pom:
        mvn_set = (
            root
            / ".hermes"
            / "skills"
            / "migration"
            / "reference-rh-quarkus-pom"
            / "scripts"
            / "verify-maven-settings.py"
        )
        if not mvn_set.is_file():
            mvn_set = (
                Path(__file__).resolve().parent.parent.parent.parent
                / "migration"
                / "reference-rh-quarkus-pom"
                / "scripts"
                / "verify-maven-settings.py"
            )
        if not mvn_set.is_file():
            print(f"FAIL: missing verify-maven-settings script: {mvn_set}", file=sys.stderr)
            return 2
        sub = subprocess.run(
            [sys.executable, str(mvn_set), str(root), "--files-only"],
            text=True,
            capture_output=True,
        )
        sys.stdout.write(sub.stdout or "")
        sys.stderr.write(sub.stderr or "")
        if sub.returncode != 0:
            print(
                f"FAIL: refuse kanban_complete — MAVEN_REPOS rc={sub.returncode}",
                file=sys.stderr,
            )
            return 1 if sub.returncode == 1 else sub.returncode

    phase = str(inner.get("phase") or "").upper() if inner else ""
    if phase == "M5":
        rescan = (
            root
            / ".hermes"
            / "skills"
            / "analysis"
            / "scan-with-mta"
            / "scripts"
            / "assert-mta-rescan.py"
        )
        if not rescan.is_file():
            print(f"FAIL: missing mta_rescan script: {rescan}", file=sys.stderr)
            return 2
        sub = subprocess.run(
            [sys.executable, str(rescan), str(root)],
            text=True,
            capture_output=True,
        )
        sys.stdout.write(sub.stdout or "")
        sys.stderr.write(sub.stderr or "")
        if sub.returncode != 0:
            print(
                f"FAIL: refuse kanban_complete — mta_rescan rc={sub.returncode} (WC-5)",
                file=sys.stderr,
            )
            return 1 if sub.returncode == 1 else sub.returncode

    print(f"OK: complete-exit green → {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
