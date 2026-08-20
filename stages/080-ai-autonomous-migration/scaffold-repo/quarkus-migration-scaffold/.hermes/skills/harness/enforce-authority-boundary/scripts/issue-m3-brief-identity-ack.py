#!/usr/bin/env python3
"""Issue M3 brief-identity as a RECORD when every minted body digest matches.

Does **not** invent a second envelope checker. Runs check-body-digest-match.py
per minted body (and assert-card-body-digest-match.py when kanban.db exists).
Writes yaml only on all-PASS. Signer is gate:check-body-digest-match, never a
worker name (AR-1.1). Operator E-20260820T122824Z: no manual approval gates.

Usage:
  python3 issue-m3-brief-identity-ack.py /projects/modernized [--task-id t_xxx]

Exit:
  0  record present (written or already valid)
  1  named mismatching body / incomplete mint — do not write; typed BLOCK
  2  missing harness script / usage
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SIGNER = "gate:check-body-digest-match"
ACK_REL = Path("evidence") / "acks" / "m3-brief-identity.ack.yaml"
ACK_CANONICAL = Path("evidence") / "acks" / "brief-identity.ack.yaml"
DIGEST_REL = (
    Path(".hermes")
    / "skills"
    / "harness"
    / "record-run-evidence"
    / "scripts"
    / "check-body-digest-match.py"
)
CARD_REL = (
    Path(".hermes")
    / "skills"
    / "harness"
    / "record-run-evidence"
    / "scripts"
    / "assert-card-body-digest-match.py"
)
KEEP_SIGNERS = frozenset({SIGNER})


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
    for rel in (
        Path("evidence") / "derived" / "phase-M3-ack-gate-task-id.txt",
        Path("evidence") / "derived" / "m3-ack-gate-task-id.txt",
    ):
        pointer = root / rel
        if pointer.is_file():
            token = pointer.read_text(encoding="utf-8").strip().split()
            if token:
                return token[0]
    return os.environ.get("HERMES_KANBAN_TASK", "").strip()


def kanban_db(root: Path) -> Path:
    primary = root / ".hermes" / "home" / "kanban.db"
    if primary.is_file():
        return primary
    alt = root / ".hermes" / "home" / "kanban" / "kanban.db"
    if alt.is_file() and alt.stat().st_size > 0:
        return alt
    return primary


def partition_story_ids(root: Path) -> set[str]:
    path = root / "evidence" / "briefs" / "partition.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    stories = data.get("stories") if isinstance(data, dict) else None
    if not isinstance(stories, list):
        raise ValueError(f"partition missing stories[]: {path}")
    out: set[str] = set()
    for i, s in enumerate(stories):
        if not isinstance(s, dict):
            raise ValueError(f"partition stories[{i}] is not an object")
        sid = str(s.get("story_id") or "").strip()
        if not sid:
            raise ValueError(f"partition stories[{i}] missing story_id")
        out.add(sid)
    if not out:
        raise ValueError("partition stories[] is empty")
    return out


def cards_from_json(root: Path) -> list[dict[str, str]]:
    path = root / "evidence" / "derived" / "created-story-cards.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    cards = data.get("cards") if isinstance(data, dict) else data
    out: list[dict[str, str]] = []
    if not isinstance(cards, list):
        return out
    for c in cards:
        if not isinstance(c, dict):
            continue
        tid = str(c.get("id") or "").strip()
        sid = str(c.get("story_id") or "").strip()
        if tid and sid:
            out.append({"id": tid, "story_id": sid})
    return out


def fill_missing_from_sqlite(
    root: Path, cards: list[dict[str, str]], missing: set[str]
) -> list[dict[str, str]]:
    db = kanban_db(root)
    if not missing or not db.is_file():
        return cards
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute("select id, body from tasks").fetchall()
    finally:
        conn.close()
    have = {c["story_id"] for c in cards}
    extra: list[dict[str, str]] = []
    for tid, body in rows:
        text = body or ""
        for sid in sorted(missing):
            needle = f"evidence/bodies/m3-{sid}.json"
            if needle in text and sid not in have:
                extra.append({"id": str(tid), "story_id": sid})
                have.add(sid)
    return cards + extra


def body_rel(story_id: str) -> str:
    return f"evidence/bodies/m3-{story_id}.json"


def run_named(cmd: list[str], label: str) -> int:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        print(f"FAIL: {label}", file=sys.stderr)
    return proc.returncode


def existing_is_valid(raw: str, digests: dict[str, str]) -> bool:
    if yaml_field(raw, "kind") != "migration-ack":
        return False
    if yaml_field(raw, "ack_type") != "brief-identity":
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
        "ack_type: brief-identity",
        "status: acknowledged",
        f"acknowledged_by: {SIGNER}",
        f"acknowledged_at: {now}",
        f"task_id: {task_id}",
        "gate_rc: 0",
        "artifact_digests:",
    ]
    for rel, digest in sorted(digests.items()):
        lines.append(f"  {rel}: {digest}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--task-id", default="", help="ack_gate task id")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    digest_script = root / DIGEST_REL
    if not digest_script.is_file():
        print(f"FAIL: missing {DIGEST_REL} (harness)", file=sys.stderr)
        return 2

    try:
        expected = partition_story_ids(root)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"FAIL: partition {e}", file=sys.stderr)
        return 1

    cards = cards_from_json(root)
    have = {c["story_id"] for c in cards}
    missing = expected - have
    if missing:
        cards = fill_missing_from_sqlite(root, cards, missing)
        have = {c["story_id"] for c in cards}
        missing = expected - have
    extra = have - expected
    if missing or extra:
        named = ", ".join(sorted(missing)) or "-"
        extra_s = ", ".join(sorted(extra)) or "-"
        print(
            f"FAIL: minted stories ≠ partition missing={named} extra={extra_s}",
            file=sys.stderr,
        )
        return 1

    bad = 0
    named_fail: list[str] = []
    digests: dict[str, str] = {}
    card_script = root / CARD_REL
    db = kanban_db(root)
    for card in sorted(cards, key=lambda c: c["story_id"]):
        rel = body_rel(card["story_id"])
        body = root / rel
        if not body.is_file():
            print(f"FAIL: missing minted body {rel}", file=sys.stderr)
            named_fail.append(rel)
            bad = 1
            continue
        rc = run_named(
            [sys.executable, str(digest_script), str(root), "--body", rel],
            f"check-body-digest-match {rel}",
        )
        if rc != 0:
            named_fail.append(rel)
            bad = 1
            continue
        if db.is_file() and card_script.is_file():
            rc2 = run_named(
                [
                    sys.executable,
                    str(card_script),
                    str(root),
                    "--task-id",
                    card["id"],
                    "--body",
                    rel,
                ],
                f"assert-card-body-digest-match {rel} task={card['id']}",
            )
            if rc2 != 0:
                named_fail.append(rel)
                bad = 1
                continue
        try:
            digests[rel] = sha256_file(body)
        except OSError as e:
            print(f"FAIL: digest {rel}: {e}", file=sys.stderr)
            named_fail.append(rel)
            bad = 1

    if bad:
        print(
            "FAIL: M3 brief-identity not issued — mismatching body "
            + ", ".join(named_fail)
            + " (not a human brief-identity GO)",
            file=sys.stderr,
        )
        return 1

    task_id = resolve_task_id(root, args.task_id)
    if not task_id:
        print(
            "FAIL: missing task_id (pass --task-id or HERMES_KANBAN_TASK)",
            file=sys.stderr,
        )
        return 1

    ack_path = root / ACK_REL
    canon_path = root / ACK_CANONICAL
    if ack_path.is_file():
        raw = ack_path.read_text(encoding="utf-8")
        if existing_is_valid(raw, digests):
            if not canon_path.is_file() or not existing_is_valid(
                canon_path.read_text(encoding="utf-8"), digests
            ):
                ensure_acks_writable(ack_path.parent)
                write_record(canon_path, task_id, digests)
                relock_grant(canon_path, ack_path.parent)
            print(f"OK: M3 brief-identity record already valid ← {ACK_REL}")
            return 0

    acks = ack_path.parent
    ensure_acks_writable(acks)
    try:
        write_record(ack_path, task_id, digests)
        write_record(canon_path, task_id, digests)
    except OSError as e:
        print(f"FAIL: could not write {ACK_REL}: {e}", file=sys.stderr)
        return 1
    relock_grant(ack_path, acks)
    relock_grant(canon_path, acks)
    print(
        f"OK: M3 brief-identity record issued acknowledged_by={SIGNER} "
        f"gate_rc=0 task_id={task_id} bodies={len(digests)} ← {ACK_REL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
