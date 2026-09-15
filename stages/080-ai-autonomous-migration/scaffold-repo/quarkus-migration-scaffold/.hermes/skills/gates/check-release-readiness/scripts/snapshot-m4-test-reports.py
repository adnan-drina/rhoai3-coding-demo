#!/usr/bin/env python3
"""Copy Maven test reports into evidence/ before any rebuild that can clean them.

Lead:m4-must-not-destroy-evidence-before-reading-it — dest-5 M4 ran
``mvn clean test`` and deleted unread surefire XML. A POPULATED snapshot is
never overwritten with an EMPTY ``target/``; that rule stands.

What it is not, and what ADR-015 changed: "first snapshot wins" was read as
"the first snapshot wins forever", and the M4 pre-verdict runner now rebuilds
under the ``m4-parity`` profile before it snapshots. On a tree that already
carried an M3 snapshot, the floors would then read reports taken BEFORE the
generated parity cases existed and measure a suite that did run as one that
never did. So a FRESHER run wins:

  --fresh          the caller just rebuilt the reports and says so (the
                   pre-verdict runner passes it only when the m4-parity build
                   actually ran and exited 0).
  newer reports    the live ``target/*-reports`` carry a file written after the
                   snapshot was taken.

Either way the replacement still needs live XML: an empty ``target/`` replaces
nothing, which is the dest-5 rule unchanged.

The receipt beside the snapshot says which of those happened, when the
snapshot's CONTENT was taken (``snapshot_of.epoch`` — not the time this script
last ran, or a keep would push the comparison forward every time), which source
directories it came from and how many files it holds.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCES = (
    ("surefire", Path("target") / "surefire-reports"),
    ("failsafe", Path("target") / "failsafe-reports"),
)
SNAP_ROOT = Path("evidence") / "m4-pre-rebuild" / "test-reports"
MANIFEST = Path("evidence") / "m4-pre-rebuild" / "manifest.json"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def xml_count(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.rglob("*.xml") if path.is_file())


def newest_mtime(directory: Path) -> float:
    """The most recent XML in ``directory``, 0.0 when it holds none."""
    if not directory.is_dir():
        return 0.0
    times = [p.stat().st_mtime for p in directory.rglob("*.xml") if p.is_file()]
    return max(times) if times else 0.0


def taken_at(root: Path) -> float:
    """When the snapshot's CONTENT was taken. The receipt says so; for a
    snapshot written before the receipt carried it, the snapshot's own newest
    file is the honest answer (copytree preserves mtimes)."""
    p = root / MANIFEST
    if p.is_file():
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = {}
        epoch = (doc or {}).get("snapshot_of", {}).get("epoch") if isinstance(doc, dict) else None
        if isinstance(epoch, (int, float)) and epoch > 0:
            return float(epoch)
    return newest_mtime(root / SNAP_ROOT)


def snapshot_root(root: Path, *, fresh: bool = False) -> dict:
    dest = root / SNAP_ROOT
    dest.mkdir(parents=True, exist_ok=True)
    existing = xml_count(dest)
    live = [(label, rel, xml_count(root / rel), newest_mtime(root / rel)) for label, rel in SOURCES]
    live_xml = sum(n for _, _, n, _ in live)
    live_newest = max([m for _, _, n, m in live if n], default=0.0)
    recorded = taken_at(root) if existing else 0.0

    if not existing:
        reason = "first snapshot"
    elif not live_xml:
        # dest-5: a populated snapshot is never overwritten with an empty
        # target/. This is the only way a keep happens.
        reason = ""
    elif fresh:
        reason = "--fresh: the caller rebuilt the reports before asking"
    elif live_newest > recorded:
        reason = "the live reports are newer than the snapshot (%s > %s)" % (
            _iso(live_newest), _iso(recorded) if recorded else "<unrecorded>")
    else:
        reason = ""

    copied: list[str] = []
    missing: list[str] = []
    sources: list[str] = []
    if reason:
        for label, rel, n, _mtime in live:
            if n == 0:
                missing.append(str(rel))
                continue
            target = dest / label
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(root / rel, target)
            copied.append("%s:%d" % (label, n))
            sources.append(rel.as_posix())
    else:
        missing = [str(rel) for _, rel, n, _ in live if n == 0]

    now = datetime.now(timezone.utc)
    if reason:
        snapshot_of = {
            "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "epoch": now.timestamp(),
            "sources": sources,
            "files": xml_count(dest),
            "reason": reason,
        }
    else:
        snapshot_of = _previous_snapshot_of(root)
        snapshot_of.setdefault("at", _iso(recorded) if recorded else now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        snapshot_of.setdefault("epoch", recorded)
        snapshot_of.setdefault("sources", [])
        snapshot_of["files"] = xml_count(dest)
        snapshot_of["reason"] = ("kept: the existing snapshot is the freshest evidence"
                                 if live_xml else
                                 "kept: no live report to replace it with (dest-5)")

    manifest = {
        "schema": "rhoai3.m4-test-report-snapshot/v1",
        "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kept_existing_snapshot": not reason,
        "copied": copied,
        "live_missing": missing,
        "snapshot_xml": xml_count(dest),
        "snapshot_of": snapshot_of,
    }
    (root / MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        "OK: snapshot-m4-test-reports (xml=%d kept=%s copied=%s; %s)"
        % (manifest["snapshot_xml"], manifest["kept_existing_snapshot"], ",".join(copied) or "-",
           snapshot_of["reason"]),
        file=sys.stderr,
    )
    return manifest


def _iso(epoch: float) -> str:
    if not epoch:
        return ""
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _previous_snapshot_of(root: Path) -> dict:
    p = root / MANIFEST
    if not p.is_file():
        return {}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    prev = (doc or {}).get("snapshot_of") if isinstance(doc, dict) else None
    return dict(prev) if isinstance(prev, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("root", type=Path, help="product / dest root")
    parser.add_argument("--fresh", action="store_true",
                        help="the caller just rebuilt the reports (the M4 pre-verdict runner passes this only after an "
                             "m4-parity build that ran and exited 0); replace the snapshot with them")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        return _fail("root is not a directory: " + str(root))
    snapshot_root(root, fresh=args.fresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
