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
from planner.roadmap import compose_serial_roadmap
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
    semantics: dict[str, Any] = {}
    receipt = compose_receipt(root, semantics_out=semantics)
    if write:
        if semantics and not semantics.get("frozen"):
            # frozen by the first ADMITTED receipt; never rewritten after it
            semantics["frozen"] = receipt.get("status") == "ADMITTED"
            # plan semantics v1: exactly the document the receipt sealed, and
            # its derived human-readable view (no authority, never a queue)
            from planner.outcome_protocol import select_protocol
            from planner.paths import PLAN_SEMANTICS, PLAN_VIEW
            from planner.plan_semantics import plan_view

            write_canonical(root / PLAN_SEMANTICS, semantics)
            try:
                protocol = select_protocol(root).protocol
            except Exception:  # an unreadable selection is the serial loop's observational view
                protocol = "serial-loop/v1"
            write_canonical(root / PLAN_VIEW, plan_view(semantics, protocol=protocol))
        write_canonical(root / ADMISSION_RECEIPT, receipt)
        # Derived serial view only. Not sealed, not a KEEP, not a mint, not a
        # release gate. A compose failure must not change the admission verdict.
        try:
            compose_serial_roadmap(root)
        except (FileNotFoundError, OSError, ValueError):
            pass
    return receipt
