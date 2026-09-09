"""Deterministic v3 pipeline: bundle → work list → receipt.

Called by the producer skills' CLIs. Writes canonical JSON. No LLM. No
environment-dependent content in any artifact.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from planner.admission import compose_receipt
from planner.canonical import digest, write_canonical
from planner.decisions import load_decisions
from planner.evidence import assemble
from planner.paths import ADMISSION_RECEIPT, EVIDENCE_BUNDLE
from planner.worklist import build_worklist


def assemble_bundle(root: Path, *, write: bool = True) -> tuple[dict[str, Any], str]:
    root = Path(root)
    try:
        decisions = load_decisions(root)
    except ValueError:
        decisions = None
    bundle = assemble(root, decisions=decisions)
    d = digest(bundle)
    if write:
        write_canonical(root / EVIDENCE_BUNDLE, bundle)
    return bundle, d


def plan(root: Path, *, write: bool = True) -> dict[str, Any]:
    """The work list from the bundle and the verification state on disk."""
    root = Path(root)
    if not (root / EVIDENCE_BUNDLE).is_file():
        raise FileNotFoundError("missing %s (assemble-evidence-bundle did not run)" % EVIDENCE_BUNDLE)
    return build_worklist(root, write=write)


def admit(root: Path, *, write: bool = True) -> dict[str, Any]:
    root = Path(root)
    receipt = compose_receipt(root)
    if write:
        write_canonical(root / ADMISSION_RECEIPT, receipt)
    return receipt
