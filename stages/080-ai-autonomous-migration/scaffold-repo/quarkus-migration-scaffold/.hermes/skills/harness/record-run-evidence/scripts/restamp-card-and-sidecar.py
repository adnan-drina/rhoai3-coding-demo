#!/usr/bin/env python3
"""Re-stamp typed-body digest on kanban card and sidecar as one operation.

Operator E-20260819T104826Z / restamp-card-and-sidecar-atomically.

The mint window may repair a body and re-stamp. Sidecar-only stamp after
the first stamp left card verify FAIL (polish 0258dcb6 vs sidecar 85d15de2).
This script updates the card markdown (every prior body digest) and the
sidecar, then asserts card-digest == sidecar-digest. Either both move or
it refuses and restores.

Usage:
  restamp-card-and-sidecar.py --root . --body evidence/bodies/m3-s.json --task-id t_xxx
  restamp-card-and-sidecar.py --root . --body ... --task-id t_xxx --kanban-db path.db
    (fixture-only sqlite write; dest uses hermes kanban edit)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CARD_DIGEST_RES = (
    re.compile(r"Body digest \(AR-4\.3\): `([0-9a-f]{64})`"),
    re.compile(r"AR-4\.3 digest: ([0-9a-f]{64})"),
    re.compile(r"--expect ([0-9a-f]{64})"),
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sidecar_path(body: Path) -> Path:
    return body.with_suffix(body.suffix + ".sha256.json")


def read_sidecar_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    d = str(doc.get("body_sha256") or "").strip().lower()
    return d if len(d) == 64 else None


def card_digest_hexes(text: str) -> list[str]:
    out: list[str] = []
    for rx in CARD_DIGEST_RES:
        out.extend(rx.findall(text))
    return out


def replace_digests(text: str, olds: set[str], new: str) -> str:
    out = text
    for old in olds:
        if old and old != new:
            out = out.replace(old, new)
    return out


def card_markdown_from_show(doc: object) -> str:
    """Live hermes kanban show --json nests markdown under task.body (V35-DIGEST)."""
    if not isinstance(doc, dict):
        raise RuntimeError("kanban show JSON must be an object")
    body = doc.get("body")
    if isinstance(body, str) and body.strip():
        return body
    task = doc.get("task")
    if isinstance(task, dict):
        nested = task.get("body")
        if isinstance(nested, str) and nested.strip():
            return nested
        if isinstance(nested, dict):
            for key in ("markdown", "text", "content", "body"):
                val = nested.get(key)
                if isinstance(val, str) and val.strip():
                    return val
    raise RuntimeError("kanban show missing body (looked at body and task.body)")


def read_card_body_hermes(task_id: str) -> str:
    proc = subprocess.run(
        ["hermes", "kanban", "show", task_id, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"hermes kanban show {task_id} rc={proc.returncode} {proc.stderr.strip()}"
        )
    doc = json.loads(proc.stdout)
    return card_markdown_from_show(doc)


def write_card_body_hermes(task_id: str, markdown: str) -> None:
    proc = subprocess.run(
        ["hermes", "kanban", "edit", task_id, "--body", markdown],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"hermes kanban edit {task_id} rc={proc.returncode} {proc.stderr.strip()}"
        )


def read_card_body_sqlite(db: Path, task_id: str) -> str:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = conn.execute("select body from tasks where id=?", (task_id,)).fetchone()
    finally:
        conn.close()
    if not row or row[0] is None:
        raise RuntimeError(f"unknown task {task_id} in {db}")
    return str(row[0])


def write_card_body_sqlite(db: Path, task_id: str, markdown: str) -> None:
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("update tasks set body=? where id=?", (markdown, task_id))
        if cur.rowcount != 1:
            raise RuntimeError(f"sqlite update {task_id} rowcount={cur.rowcount}")
        conn.commit()
    finally:
        conn.close()


def write_sidecar(body: Path, sidecar: Path, digest: str) -> None:
    try:
        doc = json.loads(body.read_text(encoding="utf-8"))
        task_id = str(doc.get("task_id") or doc.get("id") or body.stem)
    except Exception:
        task_id = body.stem
    stamp = {
        "schema": "rhoai3.body-digest/v1",
        "task_id": task_id,
        "body_path": str(body),
        "body_sha256": digest,
        "stamped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    sidecar.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--body", required=True)
    ap.add_argument("--task-id", required=True)
    ap.add_argument(
        "--kanban-db",
        default="",
        help="fixture-only: update tasks.body here instead of hermes kanban edit",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    body = Path(args.body)
    if not body.is_absolute():
        body = (root / body).resolve()
    if not body.is_file():
        print(f"FAIL: missing body {body}", file=sys.stderr)
        return 1
    task_id = str(args.task_id).strip()
    if not task_id.startswith("t_"):
        print(f"FAIL: bad task-id {task_id!r}", file=sys.stderr)
        return 1
    sidecar = sidecar_path(body)
    new_digest = sha256_file(body)
    old_sidecar = sidecar.read_text(encoding="utf-8") if sidecar.is_file() else None
    old_digest = read_sidecar_digest(sidecar)
    db = Path(args.kanban_db) if args.kanban_db else (root / ".hermes" / "home" / "kanban.db")
    use_sqlite = bool(args.kanban_db)
    try:
        old_card = (
            read_card_body_sqlite(db, task_id)
            if use_sqlite
            else read_card_body_hermes(task_id)
        )
    except Exception as exc:
        print(f"REFUSE: cannot read card {task_id}: {exc}", file=sys.stderr)
        return 1
    olds = set(card_digest_hexes(old_card))
    if old_digest:
        olds.add(old_digest)
    if not olds:
        print(
            f"REFUSE: card {task_id} has no AR-4.3 digest line to restamp",
            file=sys.stderr,
        )
        return 1
    new_card = replace_digests(old_card, olds, new_digest)
    if new_digest not in new_card:
        print(
            f"REFUSE: restamp did not land digest on card {task_id}",
            file=sys.stderr,
        )
        return 1
    try:
        if use_sqlite:
            write_card_body_sqlite(db, task_id, new_card)
        else:
            write_card_body_hermes(task_id, new_card)
    except Exception as exc:
        print(f"REFUSE: card update failed (sidecar unchanged): {exc}", file=sys.stderr)
        return 1
    try:
        write_sidecar(body, sidecar, new_digest)
    except Exception as exc:
        try:
            if use_sqlite:
                write_card_body_sqlite(db, task_id, old_card)
            else:
                write_card_body_hermes(task_id, old_card)
        except Exception:
            pass
        print(f"REFUSE: sidecar write failed; card restored: {exc}", file=sys.stderr)
        return 1
    # Cross-assert against sqlite (assert-card-body-digest-match.py).
    assert_db = db if db.is_file() else (root / ".hermes" / "home" / "kanban.db")
    checker = (
        Path(__file__).resolve().parent / "assert-card-body-digest-match.py"
    )
    if checker.is_file() and assert_db.is_file():
        proc = subprocess.run(
            [
                sys.executable,
                str(checker),
                str(root),
                "--task-id",
                task_id,
                "--body",
                str(body),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            try:
                if use_sqlite:
                    write_card_body_sqlite(db, task_id, old_card)
                else:
                    write_card_body_hermes(task_id, old_card)
                if old_sidecar is None:
                    sidecar.unlink(missing_ok=True)
                else:
                    sidecar.write_text(old_sidecar, encoding="utf-8")
            except Exception:
                pass
            print(
                "REFUSE: card↔sidecar assert failed after restamp; restored. "
                + (proc.stderr or proc.stdout),
                file=sys.stderr,
            )
            return 1
    print(f"OK: restamped card+sidecar task={task_id} sha256={new_digest}")
    print(new_digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
