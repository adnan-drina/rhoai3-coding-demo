"""The run's M3 execution policy, pinned when the run was created (PARALLEL-M3-PILOT.md).

``run-defaults.json`` ``configuration.parallel_m3`` names it. It is read from the destination's
INITIAL commit -- the one the factory made when the run was created -- so a later edit of the working
tree cannot turn a serial run parallel, and a run created from an earlier golden (``deferred``) stays
serial. Only ``outcome-board/v2`` runs can be pilots: the pilot is expressed in the native board.

Pure reads; nothing here changes a file or the board.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

PILOT = "m3-pair-pilot/v1"
SERIAL = "serial"
POLICY_KEY = "parallel_m3"
DEFAULTS = "run-defaults.json"
WORKTREES_DIR = ".worktrees"          # pilot worktrees live here, inside the destination tree (gitignored)
PAIR_MAX_IN_PROGRESS = 2             # one pair; the chain keeps everything else to one at a time
SERIAL_MAX_IN_PROGRESS = 1


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)


def _initial_defaults(root: Path) -> tuple[dict[str, Any] | None, str]:
    """run-defaults.json as the initial commit holds it, or (None, why)."""
    p = _git(root, "rev-list", "--max-parents=0", "HEAD")
    commits = [c for c in p.stdout.split() if c] if p.returncode == 0 else []
    if len(commits) != 1:
        return None, "no single initial commit (%s)" % (p.stderr.strip()[:120] or "%d roots" % len(commits))
    show = _git(root, "show", "%s:%s" % (commits[0], DEFAULTS))
    if show.returncode != 0:
        return None, "the initial commit %s has no %s" % (commits[0][:12], DEFAULTS)
    try:
        doc = json.loads(show.stdout)
    except ValueError:
        return None, "the initial commit's %s is not JSON" % DEFAULTS
    return (doc if isinstance(doc, dict) else None), "initial commit %s" % commits[0][:12]


def pinned_policy(root: Path, *, execution: str = "") -> dict[str, Any]:
    """{"policy": PILOT | SERIAL, "declared": <value>, "source": <where it was read>, "why": <reason>}.

    A qualification fixture (``execution == "qualification"``) with no git history reads its
    working-tree run-defaults.json; a real run reads only its initial commit."""
    root = Path(root)
    doc, source = _initial_defaults(root)
    if doc is None and execution == "qualification":
        try:
            doc = json.loads((root / DEFAULTS).read_text(encoding="utf-8"))
            source = "qualification working tree"
        except (OSError, ValueError):
            doc = None
    if not isinstance(doc, dict):
        return {"policy": SERIAL, "declared": None, "source": source, "why": "no pinned declaration: serial"}
    declared = ((doc.get("configuration") or {}).get(POLICY_KEY)) if isinstance(doc.get("configuration"), dict) else None
    if declared != PILOT:
        return {"policy": SERIAL, "declared": declared, "source": source,
                "why": "parallel_m3 is %r, not %s: serial" % (declared, PILOT)}
    try:
        from planner.outcome_protocol import select_protocol
        protocol = select_protocol(root).protocol
    except Exception as exc:  # noqa: BLE001 - an unreadable selection is not a pilot
        return {"policy": SERIAL, "declared": declared, "source": source, "why": "protocol unreadable (%s): serial" % type(exc).__name__}
    if protocol != "outcome-board/v2":
        return {"policy": SERIAL, "declared": declared, "source": source,
                "why": "the pilot needs outcome-board/v2, this run selects %s: serial" % protocol}
    return {"policy": PILOT, "declared": declared, "source": source, "why": "pinned at creation"}


def max_in_progress(policy: str) -> int:
    """The dispatcher cap the policy needs: 2 only for the pilot (the board chain admits one pair)."""
    return PAIR_MAX_IN_PROGRESS if policy == PILOT else SERIAL_MAX_IN_PROGRESS
