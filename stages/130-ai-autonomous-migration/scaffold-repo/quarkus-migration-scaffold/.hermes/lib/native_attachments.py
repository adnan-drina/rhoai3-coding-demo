"""Native Kanban attachment proof: the records Hermes holds for a task, checked
against the evidence the card owes.

v23 M1 (t_56d38285) named six attachments in its completion metadata, the
reviewer's `kanban_attachments` listed none, and the audit still passed: it
read the log and the workspace KEEP paths, never the attachment store. A file
name in metadata is a claim; the proof is a native record (`hermes kanban
attachments <task> --json`) whose stored file holds the same bytes as the
workspace evidence.

Used by the attach step (read-back after it attaches) and by the paved-road
audit (a step with ``native_attachments: true``).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


def hermes_bin() -> str:
    return os.environ.get("HERMES_BIN", "hermes")


def read_records(task_id: str, *, run: Runner | None = None, hermes: str | None = None) -> list[dict[str, Any]]:
    """The task's native attachment records. Raises ValueError when they cannot be read."""
    run = run or subprocess.run
    argv = [hermes or hermes_bin(), "kanban", "attachments", task_id, "--json"]
    try:
        proc = run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("cannot read native attachments of %s: %s" % (task_id, exc)) from exc
    if proc.returncode != 0:
        raise ValueError("cannot read native attachments of %s: exit %s %s"
                         % (task_id, proc.returncode, (proc.stderr or "").strip()[:200]))
    try:
        doc = json.loads(proc.stdout or "")
    except ValueError as exc:
        raise ValueError("native attachments of %s are not JSON: %s" % (task_id, exc)) from exc
    if not isinstance(doc, list) or not all(isinstance(r, dict) for r in doc):
        raise ValueError("native attachments of %s: expected a list of records" % task_id)
    return doc


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def latest_by_name(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The newest record per stored filename (a re-attach supersedes)."""
    out: dict[str, dict[str, Any]] = {}
    for r in records:
        name = str(r.get("filename") or "")
        if not name:
            continue
        cur = out.get(name)
        if cur is None or int(r.get("id") or 0) >= int(cur.get("id") or 0):
            out[name] = r
    return out


def record_matches(root: Path, rel: str, record: dict[str, Any] | None) -> str:
    """'' when the record proves the workspace file ``rel``; else what is wrong."""
    if record is None:
        return "missing"
    local = root / rel
    stored = Path(str(record.get("stored_path") or ""))
    if not stored.is_absolute() or not stored.is_file():
        return "incomplete: the stored file %s is absent" % (stored or "?")
    size = local.stat().st_size
    if int(record.get("size") or -1) != size or stored.stat().st_size != size:
        return "incomplete: %d byte(s) recorded, %d stored, %d in the workspace" % (
            int(record.get("size") or -1), stored.stat().st_size, size)
    if _sha256(stored) != _sha256(local):
        return "incomplete: the stored bytes differ from the workspace evidence"
    return ""


def attachment_gaps(root: Path, records: list[dict[str, Any]], expected: Iterable[str]) -> list[str]:
    """One line per expected evidence file the native records do not prove."""
    by_name = latest_by_name(records)
    gaps: list[str] = []
    for rel in expected:
        if not (root / rel).is_file():
            gaps.append("%s: no workspace evidence to compare" % rel)
            continue
        why = record_matches(root, rel, by_name.get(Path(rel).name))
        if why:
            gaps.append("%s: %s" % (rel, why))
    return gaps
