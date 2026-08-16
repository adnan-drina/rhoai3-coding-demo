#!/usr/bin/env python3
"""C-3(a): on gate REFUSE, write a remediation receipt (and optionally mint a card).

Fail-closed: no waiver, no leave-triage, no Lead dest repair. A REFUSE that
needs a human to unpark or patch dest is a validation-run failure. The
receipt is the golden proof; --create-card is seat-only (off in validate).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "rhoai3.remediation-needed/v1"
FORBIDDEN = (
    "waiver",
    "leave-triage",
    "leave_triage",
    "dest-repair",
    "dest_repair",
    "HITL",
)


def _slug(text: str) -> str:
    keep = []
    for ch in text.lower():
        if ch.isalnum() or ch in "-_":
            keep.append(ch)
        elif ch in " ./":
            keep.append("-")
    s = "".join(keep).strip("-") or "refuse"
    return s[:80]


def receipt_from_obj(obj: dict, source: str) -> dict:
    verdict = str(obj.get("verdict") or obj.get("gate_verdict") or "").upper()
    gate = str(obj.get("gate") or obj.get("check") or "unknown")
    reason = str(obj.get("reason") or obj.get("note") or obj.get("routing") or verdict)
    parent = obj.get("parent") or obj.get("task_id") or obj.get("story_id") or ""
    return {
        "schema": SCHEMA,
        "verdict": verdict or "REFUSE",
        "gate": gate,
        "reason": reason,
        "parent": parent or None,
        "source": source,
        "forbidden": list(FORBIDDEN),
        "create_card": False,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def write_receipt(root: Path, doc: dict) -> Path:
    out_dir = root / "evidence" / "derived" / "remediation"
    out_dir.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(
        {k: doc.get(k) for k in ("gate", "verdict", "reason", "source", "parent")},
        sort_keys=True,
    )
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:10]
    name = f"{_slug(str(doc.get('gate') or 'gate'))}-{digest}.json"
    path = out_dir / name
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def maybe_create_card(root: Path, doc: dict) -> str | None:
    title = f"REMEDIATE: {doc.get('gate')} {doc.get('reason')}"
    body = (
        f"# REMEDIATE (C-3(a))\n\n"
        f"Gate `{doc.get('gate')}` scored `{doc.get('verdict')}`.\n"
        f"Reason: {doc.get('reason')}\n\n"
        f"Do **not** waive. Do **not** leave-triage. Do **not** dest-repair.\n"
        f"Fix the product or the brief, then re-run the gate.\n"
    )
    cmd = [
        "hermes",
        "kanban",
        "create",
        "--json",
        "--assignee",
        "default",
        "--initial-status",
        "blocked",
        "--body",
        body,
    ]
    parent = doc.get("parent")
    if parent:
        cmd.extend(["--parent", str(parent)])
    cmd.append(title[:120])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root), check=False)
    except FileNotFoundError:
        print("FAIL: hermes not on PATH for --create-card", file=sys.stderr)
        return None
    if out.returncode != 0:
        print(
            f"FAIL: hermes kanban create: {(out.stderr or out.stdout or '').strip()}",
            file=sys.stderr,
        )
        return None
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None
    return str(data.get("id") or "") or None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Write a C-3(a) remediation receipt for a gate REFUSE (optional card mint)."
    )
    p.add_argument("root", help="product / scaffold root")
    p.add_argument("--verdict-file", default="", help="verdict JSON (object or list)")
    p.add_argument("--index", type=int, default=0, help="index when verdict-file is a list")
    p.add_argument("--gate", default="", help="gate id when no verdict-file")
    p.add_argument("--reason", default="", help="reason when no verdict-file")
    p.add_argument(
        "--create-card",
        action="store_true",
        help="hermes kanban create (seat only; never from validate-contracts)",
    )
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if args.verdict_file:
        path = Path(args.verdict_file)
        if not path.is_file():
            print(f"FAIL: missing verdict file {path}", file=sys.stderr)
            return 1
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else [data]
        if args.index < 0 or args.index >= len(items):
            print("FAIL: --index out of range", file=sys.stderr)
            return 1
        obj = items[args.index]
        if not isinstance(obj, dict):
            print("FAIL: verdict item is not an object", file=sys.stderr)
            return 1
        doc = receipt_from_obj(obj, source=str(path))
    else:
        if not args.gate:
            print("FAIL: --gate or --verdict-file required", file=sys.stderr)
            return 2
        doc = receipt_from_obj(
            {"verdict": "REFUSE", "gate": args.gate, "reason": args.reason or "REFUSE"},
            source="cli",
        )
    written = write_receipt(root, doc)
    print(f"REMEDIATION_RECEIPT={written}", file=sys.stderr)
    if args.create_card:
        tid = maybe_create_card(root, doc)
        if not tid:
            return 1
        doc["create_card"] = True
        doc["task_id"] = tid
        written.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(f"REMEDIATION_CARD={tid}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
