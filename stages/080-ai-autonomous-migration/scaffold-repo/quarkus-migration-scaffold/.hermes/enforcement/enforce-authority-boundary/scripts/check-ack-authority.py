#!/usr/bin/env python3
"""AD-H §16.5 / AR-1.1 — refuse worker self-ACK as stage authority.

Scans evidence/acks/*.{json,yaml,yml,ack.yaml,...}.
Fail closed when an acknowledged ack is authored by a worker role, lacks
task_id / digests, or is a bare .json grant without authenticated signer.

Human unlock/lock around real ACK remains F2 residual.

Usage:
  python3 check-ack-authority.py                 # scan the current directory
  python3 check-ack-authority.py /path/to/repo   # explicit workspace root
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_CODES = """\
Exit codes:
  0  pass — every acknowledged grant carries non-worker signer, task_id and
     digests; or lint idle (no evidence/acks dir, no grant files, or no
     acknowledged grants to validate)
  1  BLOCK — at least one FAIL: line on stderr (parse error, worker/self ACK
     author, missing task_id, missing artifact_digests, or a bare .json grant)
  2  usage error (bad/unknown arguments; emitted by argparse)
"""

WORKER_AUTHORS = frozenset(
    {
        "planner",
        "spec-author",
        "spec_author",
        "implementer",
        "evidence-analyst",
        "evidence_analyst",
        "reviewer",  # reviewer may request; not grant human ACK
        "validator",
        "default",
        "worker",
        "hermes",
        "agent",
    }
)


def load_doc(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json" or path.name.endswith(".json"):
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    # minimal YAML field scrape (no PyYAML required)
    def field(name: str) -> str:
        m = re.search(rf"(?im)^{name}:\s*(.+)$", raw)
        return m.group(1).strip().strip("\"'") if m else ""

    return {
        "kind": field("kind"),
        "ack_type": field("ack_type"),
        "status": field("status"),
        "acknowledged_by": field("acknowledged_by"),
        "task_id": field("task_id"),
        "artifact_digests": field("artifact_digests"),
    }


def author_is_worker(author: str) -> bool:
    a = author.strip().lower()
    if not a:
        return True
    # "planner (M2 …)" → planner
    head = re.split(r"[\s(/]", a, maxsplit=1)[0]
    if head in WORKER_AUTHORS:
        return True
    for w in WORKER_AUTHORS:
        if a == w or a.startswith(w + " ") or a.startswith(w + "("):
            return True
    return False


def has_digests(doc: dict) -> bool:
    digests = doc.get("artifact_digests") or doc.get("digests")
    if isinstance(digests, dict) and digests:
        return True
    if isinstance(digests, list) and digests:
        return True
    if isinstance(digests, str) and digests.strip() and digests.strip() not in {"{}", "[]"}:
        return True
    refs = doc.get("artifact_refs")
    if isinstance(refs, list):
        for r in refs:
            if isinstance(r, dict) and (r.get("sha256") or r.get("digest")):
                return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="workspace root containing evidence/acks (default: current directory)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    adir = root / "evidence" / "acks"
    if not adir.is_dir():
        print("OK: no evidence/acks — AR-1.1 idle")
        return 0

    paths = sorted(
        p
        for p in adir.iterdir()
        if p.is_file()
        and p.name != "README.md"
        and not p.name.startswith(".")
        and (
            "ack" in p.name.lower()
            or p.suffix in {".json", ".yaml", ".yml"}
        )
    )
    if not paths:
        print("OK: acks dir empty of grants — AR-1.1 idle")
        return 0

    bad = 0
    checked = 0
    for path in paths:
        rel = str(path.relative_to(root))
        try:
            doc = load_doc(path)
        except Exception as e:
            print(f"FAIL: {rel}: parse error {e}", file=sys.stderr)
            bad = 1
            continue
        status = str(doc.get("status") or "").lower()
        # Non-ack sidecar files (e.g. README already skipped) — skip non-ack kinds
        kind = str(doc.get("kind") or "")
        if kind and kind != "migration-ack":
            continue
        if not kind and not doc.get("ack_type") and not doc.get("acknowledged_by"):
            continue
        checked += 1
        if status and status != "acknowledged":
            continue  # not claiming advance authority
        author = str(doc.get("acknowledged_by") or "")
        if author_is_worker(author):
            print(
                f"FAIL: AR-1.1 {rel}: worker/self ACK author={author!r} "
                f"— not stage authority",
                file=sys.stderr,
            )
            bad = 1
        task_id = str(doc.get("task_id") or doc.get("taskId") or "").strip()
        if not task_id:
            print(f"FAIL: AR-1.1 {rel}: missing task_id", file=sys.stderr)
            bad = 1
        if not has_digests(doc):
            print(
                f"FAIL: AR-1.1 {rel}: missing artifact_digests / digest-bearing refs",
                file=sys.stderr,
            )
            bad = 1
        # Bare .json without .ack. in name is a forgeable grant pattern (live defect)
        if path.suffix == ".json" and ".ack." not in path.name and "ack" not in path.stem.lower():
            print(
                f"FAIL: AR-1.1 {rel}: bare JSON grant — use *.ack.yaml with signer+digests",
                file=sys.stderr,
            )
            bad = 1

    if checked == 0:
        print("OK: no acknowledged ack grants to validate")
        return 0
    if bad:
        print(f"AR-1.1 ack authority FAILED ({checked} grant(s))", file=sys.stderr)
        return 1
    print(f"OK: AR-1.1 ack authority ({checked} grant(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
