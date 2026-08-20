#!/usr/bin/env python3
"""Autostart gates: HARNESS_REV vs golden main, park-M3 discriminator.

Architect BIND E-20260820T075106Z + AMEND E-20260820T140201Z:
create then check then dispatch. Known-bad fixtures MUST refuse:
mismatched HARNESS_REV, skill-pinned WAVE HOLDER. Parked-with-reason
(not workspace Unhealthy). persist-postStart dump is not this script.

Usage:
  assert-autostart-gates.py harness-rev --root DIR [--expected-sha 40hex]
  assert-autostart-gates.py holder --root DIR
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DEFAULT_URL = "https://github.com/adnan-drina/quarkus-migration-scaffold.git"
HOLDER_PREFIX = "M3 WAVE HOLDER"


def parse_skills(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    if text in ("", "[]", "null", "None"):
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [p.strip() for p in text.split(",") if p.strip()]
    if isinstance(data, list):
        return [str(x).strip() for x in data if str(x).strip()]
    return []


def kanban_db(root: Path) -> Path:
    primary = root / ".hermes" / "home" / "kanban.db"
    if primary.is_file():
        return primary
    alt = root / ".hermes" / "home" / "kanban" / "kanban.db"
    if alt.is_file() and alt.stat().st_size > 0:
        return alt
    return primary


def resolve_expected_sha(url: str, explicit: str) -> str:
    pin = (explicit or os.environ.get("RHOAI3_HARNESS_REV") or "").strip()
    if pin:
        if not SHA_RE.match(pin):
            raise SystemExit(f"REFUSE: HARNESS_REV expected-sha must be 40-hex, got {pin!r}")
        return pin
    proc = subprocess.run(
        ["git", "ls-remote", url, "refs/heads/main"],
        capture_output=True,
        text=True,
        check=False,
    )
    line = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
    sha = line.split()[0] if line else ""
    if proc.returncode != 0 or not SHA_RE.match(sha):
        err = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"REFUSE: git ls-remote {url} main: {err or 'no sha'}")
    return sha


def check_harness_rev(root: Path, expected: str, url: str) -> int:
    path = root / ".hermes" / "HARNESS_REV"
    if not path.is_file():
        print("REFUSE: HARNESS_REV missing", file=sys.stderr)
        return 1
    got = path.read_text(encoding="utf-8").strip()
    if not SHA_RE.match(got):
        print(f"REFUSE: HARNESS_REV not 40-hex: {got!r}", file=sys.stderr)
        return 1
    want = resolve_expected_sha(url, expected)
    if got != want:
        print(
            f"REFUSE: HARNESS_REV mismatch dest={got} golden_main={want}",
            file=sys.stderr,
        )
        return 1
    print(f"OK: HARNESS_REV {got} matches golden main")
    return 0


def check_holder(root: Path) -> int:
    db = kanban_db(root)
    if not db.is_file() or db.stat().st_size == 0:
        print(f"REFUSE: missing kanban.db {db}", file=sys.stderr)
        return 1
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(tasks)").fetchall()}
        if "title" not in cols:
            print("REFUSE: tasks table has no title", file=sys.stderr)
            return 1
        skill_col = "skills" if "skills" in cols else None
        rows = con.execute("SELECT id, title FROM tasks").fetchall()
        holders = [r for r in rows if str(r["title"] or "").startswith(HOLDER_PREFIX)]
        if not holders:
            print("REFUSE: no M3 WAVE HOLDER card after create", file=sys.stderr)
            return 1
        if len(holders) != 1:
            ids = ",".join(str(r["id"]) for r in holders)
            print(f"REFUSE: multiple WAVE HOLDER cards: {ids}", file=sys.stderr)
            return 1
        hid = holders[0]["id"]
        skills: list[str] = []
        if skill_col:
            raw = con.execute(
                f"SELECT {skill_col} FROM tasks WHERE id=?", (hid,)
            ).fetchone()
            skills = parse_skills(raw[0] if raw else None)
        if skills:
            print(
                f"REFUSE: skill-pinned holder {hid} skills={skills!r} (want [])",
                file=sys.stderr,
            )
            return 1
        print(f"OK: holder {hid} title starts with {HOLDER_PREFIX!r} skills=[]")
        return 0
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("harness-rev", "holder"))
    ap.add_argument("--root", required=True)
    ap.add_argument("--expected-sha", default="")
    ap.add_argument("--url", default=DEFAULT_URL)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.mode == "harness-rev":
        return check_harness_rev(root, args.expected_sha, args.url)
    return check_holder(root)


if __name__ == "__main__":
    raise SystemExit(main())
