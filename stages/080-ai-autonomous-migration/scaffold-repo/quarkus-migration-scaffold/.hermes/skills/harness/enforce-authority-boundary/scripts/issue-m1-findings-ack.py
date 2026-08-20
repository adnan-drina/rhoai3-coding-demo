#!/usr/bin/env python3
"""5.1 — issue m1-findings.ack.yaml as a RECORD when findings-handoff is green.

Does **not** invent a second envelope checker. Runs check-findings-handoff.py
and writes the yaml only on rc=0. Signer is gate:check-findings-handoff,
never a worker name (AR-1.1). M3 brief-identity is the same pattern
(`issue-m3-brief-identity-ack.py` / `gate:check-body-digest-match`).

Architect E-20260819T121808Z / AMEND 121859Z. v33 dest-cite 145002Z.

Usage:
  python3 issue-m1-findings-ack.py /projects/modernized [--task-id t_xxx]

Exit:
  0  record present (written or already valid)
  1  findings-handoff not green — do not write; typed BLOCK (not a human GO)
  2  missing harness script / usage
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SIGNER = "gate:check-findings-handoff"
ACK_REL = Path("evidence") / "acks" / "m1-findings.ack.yaml"
HANDOFF_REL = (
    Path(".hermes")
    / "skills"
    / "analysis"
    / "scan-with-mta"
    / "scripts"
    / "check-findings-handoff.py"
)
KEEP_SIGNERS = frozenset(
    {SIGNER, "operator", "lead"}
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def yaml_field(raw: str, name: str) -> str:
    m = re.search(rf"(?im)^{name}:\s*(.+)$", raw)
    return m.group(1).strip().strip("\"'") if m else ""


def resolve_task_id(root: Path, cli: str) -> str:
    if cli.strip():
        return cli.strip()
    pointer = root / "evidence" / "derived" / "phase-M1-task-id.txt"
    if pointer.is_file():
        token = pointer.read_text(encoding="utf-8").strip().split()
        if token:
            return token[0]
    env = os.environ.get("HERMES_KANBAN_TASK", "").strip()
    return env


def current_digests(root: Path) -> dict[str, str]:
    return {
        "evidence/mta-findings.json": sha256_file(root / "evidence" / "mta-findings.json"),
        "evidence/findings-handoff.json": sha256_file(
            root / "evidence" / "findings-handoff.json"
        ),
    }


def existing_is_valid(raw: str, digests: dict[str, str]) -> bool:
    if yaml_field(raw, "kind") != "migration-ack":
        return False
    if yaml_field(raw, "ack_type") != "m1-findings":
        return False
    if yaml_field(raw, "status").lower() != "acknowledged":
        return False
    if not yaml_field(raw, "task_id"):
        return False
    author = yaml_field(raw, "acknowledged_by").strip().lower()
    head = re.split(r"[\s(/]", author, maxsplit=1)[0] if author else ""
    if head not in KEEP_SIGNERS:
        return False
    for rel, digest in digests.items():
        if digest not in raw:
            return False
        if rel not in raw:
            return False
    return True


def ensure_acks_writable(acks: Path) -> None:
    acks.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(acks.stat().st_mode)
    if not (mode & stat.S_IWUSR):
        acks.chmod(mode | stat.S_IWUSR | stat.S_IXUSR)


def relock_grant(path: Path, acks: Path) -> None:
    try:
        path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
    except OSError:
        pass
    try:
        mode = stat.S_IMODE(acks.stat().st_mode)
        acks.chmod((mode & ~0o222) | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def write_record(path: Path, task_id: str, digests: dict[str, str]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "kind: migration-ack",
        "ack_type: m1-findings",
        "status: acknowledged",
        f"acknowledged_by: {SIGNER}",
        f"acknowledged_at: {now}",
        f"task_id: {task_id}",
        "gate_rc: 0",
        "artifact_digests:",
    ]
    for rel, digest in digests.items():
        lines.append(f"  {rel}: {digest}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", default="", help="M1 card id (else phase-M1-task-id.txt / HERMES_KANBAN_TASK)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    handoff = root / HANDOFF_REL
    if not handoff.is_file():
        print(f"FAIL: missing {HANDOFF_REL} (harness)", file=sys.stderr)
        return 2
    proc = subprocess.run(
        [sys.executable, str(handoff), str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        print(
            f"FAIL: 5.1 not issued — check-findings-handoff exit {proc.returncode} "
            f"(not a human m1-findings GO)",
            file=sys.stderr,
        )
        return 1 if proc.returncode == 1 else 2

    task_id = resolve_task_id(root, args.task_id)
    if not task_id:
        print(
            "FAIL: 5.1 missing task_id (pass --task-id, phase-M1-task-id.txt, or HERMES_KANBAN_TASK)",
            file=sys.stderr,
        )
        return 1

    try:
        digests = current_digests(root)
    except OSError as e:
        print(f"FAIL: 5.1 digest {e}", file=sys.stderr)
        return 1

    ack_path = root / ACK_REL
    if ack_path.is_file():
        raw = ack_path.read_text(encoding="utf-8")
        if existing_is_valid(raw, digests):
            print(f"OK: 5.1 m1-findings record already valid ← {ACK_REL}")
            return 0

    acks = ack_path.parent
    ensure_acks_writable(acks)
    try:
        write_record(ack_path, task_id, digests)
    except OSError as e:
        print(f"FAIL: 5.1 could not write {ACK_REL}: {e}", file=sys.stderr)
        return 1
    relock_grant(ack_path, acks)
    print(
        f"OK: 5.1 m1-findings record issued acknowledged_by={SIGNER} "
        f"gate_rc=0 task_id={task_id} ← {ACK_REL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
