#!/usr/bin/env python3
"""Phase 5 run-audit snapshot (fail-open observer). Never a gate.

Writes evidence/run-audit/<ts>.json: dest-tree path → mtime + sha256
(skip target/, .git/), git HEAD + last 5, optional claim windows from sqlite.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIR_NAMES = {".git", "target"}
SCHEMA = "rhoai3.run-audit-snapshot/v1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_files(root: Path) -> dict[str, dict]:
    files: dict[str, dict] = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in SKIP_DIR_NAMES for part in rel.parts):
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        try:
            digest = sha256_file(p)
        except OSError:
            digest = ""
        files[rel.as_posix()] = {
            "mtime": st.st_mtime,
            "sha256": digest,
            "size": st.st_size,
        }
    return files


def git_info(root: Path) -> dict:
    def run(args: list[str]) -> str:
        r = subprocess.run(
            args, cwd=str(root), capture_output=True, text=True, check=False
        )
        return (r.stdout or "").strip() if r.returncode == 0 else ""

    head = run(["git", "rev-parse", "HEAD"])
    log = run(["git", "log", "--format=%H %an %at", "-5"])
    return {
        "head": head,
        "log": [ln for ln in log.splitlines() if ln.strip()],
    }


def claim_windows_from_db(db: Path) -> list[dict]:
    if not db.is_file():
        return []
    try:
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        names = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        windows: list[dict] = []
        if "task_runs" in names:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(task_runs)").fetchall()}
            started = "started_at" if "started_at" in cols else None
            ended = "ended_at" if "ended_at" in cols else None
            task_col = "task_id" if "task_id" in cols else ("task" if "task" in cols else None)
            if started and task_col:
                q = f"SELECT * FROM task_runs WHERE {started} IS NOT NULL"
                for row in conn.execute(q):
                    d = dict(row)
                    windows.append(
                        {
                            "task_id": d.get(task_col),
                            "assignee": d.get("assignee") or d.get("worker") or "",
                            "started_at": d.get(started),
                            "ended_at": d.get(ended) if ended else None,
                        }
                    )
        conn.close()
        return windows
    except sqlite3.Error:
        return []


def attach_write_sets(root: Path, windows: list[dict]) -> None:
    """Join published write-sets onto claim windows (M1 [] honesty)."""
    ws_dir = root / "evidence" / "runtime" / "write-sets"
    for w in windows:
        if not isinstance(w, dict):
            continue
        tid = str(w.get("task_id") or "")
        if not tid:
            continue
        path = ws_dir / f"{tid}.json"
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict) and "files_writable" in doc:
            w["files_writable"] = doc.get("files_writable")
            w["files_writable_published"] = True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Snapshot dest-tree mtimes for the Phase 5 run audit (observer, not a gate)."
    )
    p.add_argument("root", help="destination / product root")
    p.add_argument("--db", default="", help="optional Hermes kanban.db for claim windows")
    p.add_argument(
        "--out",
        default="",
        help="output path (default: evidence/run-audit/<ts>.json)",
    )
    p.add_argument(
        "--boundary",
        default="",
        help="optional card-boundary label (create|claim|block|reclaim|complete)",
    )
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"FAIL: root is not a directory: {root}", file=sys.stderr)
        return 2
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    windows: list[dict] = []
    if args.db:
        windows = claim_windows_from_db(Path(args.db))
        attach_write_sets(root, windows)
    doc = {
        "schema": SCHEMA,
        "ts": ts,
        "root": str(root),
        "git": git_info(root),
        "files": walk_files(root),
        "claim_windows": windows,
    }
    if args.boundary:
        doc["boundary"] = str(args.boundary)
    if args.out:
        out = Path(args.out)
    else:
        out = root / "evidence" / "run-audit" / f"{ts}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"RUN_AUDIT_SNAPSHOT={out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
