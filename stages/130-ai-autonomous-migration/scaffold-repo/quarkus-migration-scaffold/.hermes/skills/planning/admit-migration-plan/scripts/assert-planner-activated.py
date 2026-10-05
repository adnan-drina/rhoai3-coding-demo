#!/usr/bin/env python3
"""Planner activation gate (SAD §12). First step of every M2 card.

Passes when .hermes/pins.json pins.planner.activation == "activated", or
== "pilot" with a seal (run_id, authorized_by, evidence_bundle_sha256)
bound to the evidence bundle on disk. The same check is re-derived by
admission and by K4, so this step is a fast refusal, never the boundary.
Flipping the pin or writing a seal is a named Operator GO; a worker never
does it. Exit 0 admissible; 1 not; 2 usage.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.canonical import digest, load_json  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402
from planner.pins import activation_gaps, load_pins, planner_activation  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        pins = load_pins(root)
    except (OSError, ValueError) as exc:
        print("FAIL: PLANNER_NOT_ACTIVATED cannot read pins: %s" % exc, file=sys.stderr)
        return 1
    bundle_path = root / EVIDENCE_BUNDLE
    bundle_digest = digest(load_json(bundle_path)) if bundle_path.is_file() else ""
    gaps = activation_gaps(pins, bundle_digest)
    if gaps:
        for g in gaps:
            print("  - " + g, file=sys.stderr)
        print(
            "REFUSE: PLANNER_NOT_ACTIVATED — pins.planner.activation is %r; "
            "M2 PLAN is unavailable until the activation gate (SOLUTION-ARCHITECTURE §12) passes "
            "or an Operator seals one pilot run to this evidence bundle. "
            "Terminator: kanban_block (kind=needs_input) naming this gate. Do not improvise a plan." % planner_activation(pins),
            file=sys.stderr,
        )
        return 1
    print("OK: planner %s" % planner_activation(pins))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
