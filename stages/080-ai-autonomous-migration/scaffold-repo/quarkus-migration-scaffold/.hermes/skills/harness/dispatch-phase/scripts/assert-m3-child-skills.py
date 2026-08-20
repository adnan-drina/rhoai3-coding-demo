#!/usr/bin/env python3
"""Refuse M3 story cards with empty skills; refuse holder complete on that shape.

Operator E-20260819T132404Z / E-20260819T133942Z: Procedure already OBJECT
bare create; v32 minted 11 children with skills=None. This is the gate.

Modes:
  --task-id t_xxx [--body evidence/bodies/m3-US1.json]
      After kanban_create: refuse unless card skills are non-empty.
      With --body, the card must carry every skill the write-set requires
      (filter_attach_skills_for_write_set). Extra skills are allowed.
  --holder-id t_xxx
      Pre-complete: every child titled ``M3 IMPLEMENT:`` must have non-empty
      skills, an AR-4.3 digest line, and typed-body exit_criteria.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

DIGEST_RES = (
    re.compile(r"Body digest \(AR-4\.3\): `([0-9a-f]{64})`"),
    re.compile(r"AR-4\.3 digest: ([0-9a-f]{64})"),
    re.compile(r"--expect ([0-9a-f]{64})"),
)


def kanban_db(root: Path) -> Path:
    primary = root / ".hermes" / "home" / "kanban.db"
    if primary.is_file():
        return primary
    alt = root / ".hermes" / "home" / "kanban" / "kanban.db"
    if alt.is_file() and alt.stat().st_size > 0:
        return alt
    return primary


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


def skills_required_by_body(root: Path, body_path: Path) -> list[str]:
    """Consumer: skills this write-set needs (not producer stdout equality)."""
    data = json.loads(body_path.read_text(encoding="utf-8"))
    inner = data.get("body") if isinstance(data.get("body"), dict) else data
    if not isinstance(inner, dict):
        inner = {}
    ident = inner.get("identity") if isinstance(inner.get("identity"), dict) else {}
    operand = ident.get("operand_skills") or []
    if isinstance(operand, str):
        operand = [operand]
    names: list[str] = []
    seen: set[str] = set()

    def add(name: object) -> None:
        n = str(name or "").strip()
        if n and n not in seen:
            seen.add(n)
            names.append(n)

    add("check-spec-readiness")
    if isinstance(operand, list):
        for s in operand:
            add(s)
    fw = inner.get("files_writable") or ident.get("files_writable") or []
    if not isinstance(fw, list):
        fw = []
    ready = (
        root
        / ".hermes"
        / "skills"
        / "sdd"
        / "check-spec-readiness"
        / "scripts"
    )
    if not (ready / "specimen_agnostic.py").is_file():
        cur = Path(__file__).resolve().parent
        ready = Path("/nonexistent")
        for _ in range(8):
            cand = cur / "sdd" / "check-spec-readiness" / "scripts"
            if (cand / "specimen_agnostic.py").is_file():
                ready = cand
                break
            cand = cur / ".hermes" / "skills" / "sdd" / "check-spec-readiness" / "scripts"
            if (cand / "specimen_agnostic.py").is_file():
                ready = cand
                break
            cur = cur.parent
    if str(ready) not in sys.path:
        sys.path.insert(0, str(ready))
    from specimen_agnostic import filter_attach_skills_for_write_set

    return filter_attach_skills_for_write_set(names, fw)


def connect(root: Path) -> sqlite3.Connection:
    db = kanban_db(root)
    if not db.is_file() or db.stat().st_size == 0:
        raise FileNotFoundError(f"missing kanban.db {db}")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def story_id_from_title(title: str) -> str:
    # M3 IMPLEMENT: setup — ...
    if not title.startswith("M3 IMPLEMENT:"):
        return ""
    rest = title[len("M3 IMPLEMENT:") :].strip()
    return rest.split(" — ", 1)[0].strip()


def check_task(root: Path, task_id: str, body: Path | None) -> int:
    con = connect(root)
    try:
        row = con.execute(
            "select id, title, skills, body from tasks where id=?",
            (task_id,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        print(f"FAIL: unknown task {task_id}", file=sys.stderr)
        return 1
    skills = parse_skills(row["skills"])
    if not skills:
        print(
            f"FAIL: {task_id} skills empty (bare create OBJECT; "
            "mint-m3-hermes.md:11 / Operator 132404Z)",
            file=sys.stderr,
        )
        return 1
    if body is not None:
        required = skills_required_by_body(root, body)
        missing = [s for s in required if s not in skills]
        if missing:
            print(
                f"FAIL: {task_id} missing write-set skills {missing!r} "
                f"(card={skills!r}; surface=typed body files_writable / "
                "identity.operand_skills via filter_attach_skills_for_write_set)",
                file=sys.stderr,
            )
            return 1
    print(f"OK: {task_id} skills={','.join(skills)}")
    return 0


def check_holder(root: Path, holder_id: str) -> int:
    con = connect(root)
    try:
        children = con.execute(
            """
            select t.id, t.title, t.skills, t.body
            from tasks t
            join task_links l on l.child_id = t.id
            where l.parent_id = ?
            order by t.created_at
            """,
            (holder_id,),
        ).fetchall()
    finally:
        con.close()
    stories = [
        r
        for r in children
        if str(r["title"] or "").startswith("M3 IMPLEMENT:")
    ]
    if not stories:
        print(
            f"FAIL: holder {holder_id} has no M3 IMPLEMENT children",
            file=sys.stderr,
        )
        return 1
    bad = 0
    for row in stories:
        tid = row["id"]
        title = row["title"]
        skills = parse_skills(row["skills"])
        if not skills:
            print(f"FAIL: {tid} ({title}) skills empty", file=sys.stderr)
            bad = 1
            continue
        card_body = row["body"] or ""
        digest_hits: list[str] = []
        for rx in DIGEST_RES:
            digest_hits.extend(rx.findall(card_body))
        if not digest_hits:
            print(
                f"FAIL: {tid} missing AR-4.3 digest line",
                file=sys.stderr,
            )
            bad = 1
        sid = story_id_from_title(title)
        body_path = root / "evidence" / "bodies" / f"m3-{sid}.json"
        if not body_path.is_file():
            print(f"FAIL: {tid} missing typed body {body_path}", file=sys.stderr)
            bad = 1
            continue
        try:
            payload = json.loads(body_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"FAIL: {tid} body unreadable: {exc}", file=sys.stderr)
            bad = 1
            continue
        exit_criteria = payload.get("exit_criteria") or payload.get("exitCriteria")
        if not exit_criteria:
            print(f"FAIL: {tid} typed body missing exit_criteria", file=sys.stderr)
            bad = 1
    if bad:
        print(
            "FAIL: holder complete refuse — children violate mint contract "
            "(skills / AR-4.3 digest / exit_criteria)",
            file=sys.stderr,
        )
        return 1
    print(f"OK: holder {holder_id} {len(stories)} story children mint-complete")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--task-id")
    g.add_argument("--holder-id")
    ap.add_argument("--body", default="", help="typed body for write-set skill check")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.task_id:
        body = Path(args.body) if args.body else None
        if body is not None and not body.is_file():
            body = root / args.body
            if not body.is_file():
                print(f"FAIL: body not found: {args.body}", file=sys.stderr)
                return 1
        return check_task(root, args.task_id, body)
    return check_holder(root, args.holder_id)


if __name__ == "__main__":
    raise SystemExit(main())
