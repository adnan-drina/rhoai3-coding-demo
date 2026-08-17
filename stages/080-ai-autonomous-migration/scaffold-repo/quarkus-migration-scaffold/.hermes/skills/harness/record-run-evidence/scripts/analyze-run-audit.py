#!/usr/bin/env python3
"""Phase 5 run-audit analyzer (fail-open observer). Never a gate.

Three checks against a snapshot:
  - out-of-window dest edit ⇒ INTERVENTION
  - in-window dest write with unpublished files_writable ⇒ UNATTRIBUTED
  - in-window dest write with published [] / populated set ⇒ OOS if not listed
  - done with no matching worker kanban_complete / status change with no
    task_event ⇒ forced transition

Harness-written prefixes from SR-8 (evidence/**) are allow-listed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA = "rhoai3.run-audit-findings/v1"
HARNESS_PREFIXES = (
    "evidence/",
    ".hermes/",
    ".specify/",
    "specs/",
    "target/",
    ".git/",
)

# Include-gate (Deputy 175134Z / Architect 185414Z). Keep HARNESS_PREFIXES as
# the exclude. pom.xml + src/ remain so M3 product writes are scored; the
# extra names are paths this dest has before those exist.
DEST_FILES = frozenset(
    {
        "pom.xml",
        "migration.yaml",
        "AGENTS.md",
        "devfile.yaml",
        "Containerfile",
        "catalog-info.yaml",
    }
)
DEST_PREFIXES = ("src/", "k8s/")


def _in_window(mtime: float, windows: list[dict]) -> dict | None:
    for w in windows:
        start = w.get("started_at")
        end = w.get("ended_at")
        try:
            start_f = float(start) if start is not None else None
        except (TypeError, ValueError):
            start_f = None
        try:
            end_f = float(end) if end is not None else None
        except (TypeError, ValueError):
            end_f = None
        if start_f is None:
            continue
        if mtime < start_f:
            continue
        if end_f is not None and mtime > end_f:
            continue
        if end_f is None:
            # open window
            return w
        return w
    return None


def _is_dest_path(rel: str) -> bool:
    if rel in DEST_FILES:
        return True
    return any(rel.startswith(p) for p in DEST_PREFIXES)


def _changed_since_baseline(rel: str, meta: dict, baseline_files: dict | None) -> bool:
    """When a t0 baseline is supplied, only score new or content-changed files.

    Analyzing t0 in isolation would flag every provision-time dest file as
    INTERVENTION. t0-vs-self must be 0; later snapshots vs t0 are the metric.
    """
    if baseline_files is None:
        return True
    prev = baseline_files.get(rel)
    if not isinstance(prev, dict):
        return True
    cur_hash = meta.get("sha256") or ""
    prev_hash = prev.get("sha256") or ""
    if cur_hash and prev_hash:
        return cur_hash != prev_hash
    try:
        return float(meta.get("mtime")) != float(prev.get("mtime"))
    except (TypeError, ValueError):
        return True


def _is_harness(rel: str) -> bool:
    return any(rel == p.rstrip("/") or rel.startswith(p) for p in HARNESS_PREFIXES)


def analyze(
    snap: dict,
    events: list[dict] | None,
    comments: list[dict] | None,
    baseline: dict | None = None,
) -> dict:
    windows = snap.get("claim_windows") or []
    if not isinstance(windows, list):
        windows = []
    files = snap.get("files") or {}
    baseline_files = None
    if isinstance(baseline, dict):
        bf = baseline.get("files")
        if isinstance(bf, dict):
            baseline_files = bf
    findings: list[dict] = []
    for rel, meta in files.items():
        if not isinstance(meta, dict):
            continue
        if _is_harness(rel) or not _is_dest_path(rel):
            continue
        if not _changed_since_baseline(rel, meta, baseline_files):
            continue
        mtime = meta.get("mtime")
        try:
            mtime_f = float(mtime)
        except (TypeError, ValueError):
            continue
        hit = _in_window(mtime_f, windows)
        if hit is None:
            findings.append(
                {
                    "kind": "INTERVENTION",
                    "path": rel,
                    "mtime": mtime_f,
                    "note": "dest mtime falls inside no worker claim window",
                }
            )
            continue
        writable_published = "files_writable" in hit
        writable = hit.get("files_writable")
        if not writable_published:
            findings.append(
                {
                    "kind": "UNATTRIBUTED",
                    "path": rel,
                    "task_id": hit.get("task_id"),
                    "note": "in-window dest write with unpublished files_writable (omit)",
                }
            )
            continue
        if isinstance(writable, list):
            allowed = {str(x) for x in writable}
            if rel not in allowed:
                findings.append(
                    {
                        "kind": "OOS_WRITE",
                        "path": rel,
                        "task_id": hit.get("task_id"),
                        "note": "mtime inside claim window but path not in files_writable",
                    }
                )
    events = events or []
    comments = comments or []
    done_ids = {
        str(e.get("task_id"))
        for e in events
        if str(e.get("status") or "").lower() == "done"
        or str(e.get("to_status") or "").lower() == "done"
    }
    completes = {
        str(e.get("task_id"))
        for e in events
        if str(e.get("event") or e.get("kind") or "").lower()
        in {"kanban_complete", "complete", "task_complete"}
    }
    for tid in sorted(done_ids):
        if tid and tid not in completes:
            findings.append(
                {
                    "kind": "FORCED_TRANSITION",
                    "task_id": tid,
                    "note": "status done with no matching worker kanban_complete",
                }
            )
    status_changes = [
        e
        for e in events
        if e.get("to_status") or str(e.get("event") or "").lower() == "status_change"
    ]
    evented = {
        str(e.get("task_id"))
        for e in events
        if str(e.get("event") or e.get("kind") or "")
        and str(e.get("event") or e.get("kind") or "").lower() != "status_change"
    }
    for e in status_changes:
        tid = str(e.get("task_id") or "")
        if tid and tid not in evented and str(e.get("event") or "").lower() == "status_change":
            # status_change rows without a sibling task_event of another kind
            if not any(
                str(x.get("task_id")) == tid
                and str(x.get("event") or x.get("kind") or "").lower()
                not in {"status_change", ""}
                for x in events
            ):
                findings.append(
                    {
                        "kind": "FORCED_TRANSITION",
                        "task_id": tid,
                        "note": "status change with no corresponding task_event",
                    }
                )
    foreign_comments = 0
    for c in comments:
        author = str(c.get("author") or "")
        worker = str(c.get("worker") or c.get("assignee") or "")
        if author and worker and author != worker:
            foreign_comments += 1
            findings.append(
                {
                    "kind": "FOREIGN_COMMENT",
                    "task_id": c.get("task_id"),
                    "author": author,
                    "note": "task_comments author is not the card worker",
                }
            )
    interventions = [f for f in findings if f.get("kind") == "INTERVENTION"]
    return {
        "schema": SCHEMA,
        "ts": snap.get("ts"),
        "intervention_count": len(interventions),
        "foreign_comment_count": foreign_comments,
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Analyze a run-audit snapshot (observer, not a gate). Exit 0 always unless usage error."
    )
    p.add_argument("snapshot", help="snapshot JSON from snapshot-run-audit.py")
    p.add_argument("--events-json", default="", help="optional task_event list")
    p.add_argument("--comments-json", default="", help="optional task_comments list")
    p.add_argument(
        "--baseline",
        default="",
        help="t0 snapshot JSON; only score dest files changed since that snapshot",
    )
    p.add_argument("--out", default="", help="optional findings JSON path")
    args = p.parse_args(argv)
    path = Path(args.snapshot)
    if not path.is_file():
        print(f"FAIL: missing snapshot {path}", file=sys.stderr)
        return 2
    snap = json.loads(path.read_text(encoding="utf-8"))
    events = None
    comments = None
    if args.events_json:
        events = json.loads(Path(args.events_json).read_text(encoding="utf-8"))
    if args.comments_json:
        comments = json.loads(Path(args.comments_json).read_text(encoding="utf-8"))
    baseline = None
    if args.baseline:
        bpath = Path(args.baseline)
        if not bpath.is_file():
            print(f"FAIL: missing baseline {bpath}", file=sys.stderr)
            return 2
        baseline = json.loads(bpath.read_text(encoding="utf-8"))
    report = analyze(snap, events, comments, baseline=baseline)
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"RUN_AUDIT_FINDINGS={out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    # Fail-open: never gate. Print a count on stderr for humans.
    print(
        f"RUN_AUDIT intervention_count={report['intervention_count']} "
        f"findings={len(report['findings'])}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
