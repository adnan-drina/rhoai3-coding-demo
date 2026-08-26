#!/usr/bin/env python3
"""FAIL unless dest-init smokes specify via the same helper M2 uses.

Architect ``190736ZA``: dest-init presence/``--version`` is the proxy class.
Smoke is a fail-closed invocation of the skill-mandated dispatch path, not
a full speckit LLM run. Control: a dest-init that only writes the PATH
shim must REFUSE.

Required in dest-init (GitOps ``maas-api-key-provisioning.yaml``):

- helper ``specify-from-project.sh``
- argv ``workflow run speckit`` with ``-i spec=`` (bare dies at the input
  gate before skill lookup)
- ``SPECIFY_REAL`` probe for **four** overlay skills (specify/clarify/plan/tasks)
- ``hermes kanban ls`` (``hermes --version`` is the proxy class)

Exit 0: dest-init contains the smoke.
Exit 1: shim-only / missing mandated argv.
Exit 2: usage.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _fail(msg: str) -> int:
    print("REFUSE: dest-init specify smoke: " + msg, file=sys.stderr)
    return 1


def check_text(text: str) -> list[str]:
    gaps: list[str] = []
    if "specify-from-project.sh" not in text:
        gaps.append("missing specify-from-project.sh")
    if "SPECIFY_REAL" not in text:
        gaps.append("missing SPECIFY_REAL probe (would LLM or skip capability)")
    if "specify-dest-init-smoke" not in text:
        gaps.append("missing specify-dest-init-smoke probe binary")
    if "spec=dest-init-smoke" not in text:
        gaps.append("missing -i spec=dest-init-smoke (bare Required input is not skill lookup)")
    if '"workflow"' not in text or '"speckit"' not in text:
        gaps.append("missing mandated argv workflow run speckit")
    if "speckit-specify" not in text:
        gaps.append("missing speckit-specify (workflow step specify)")
    if "speckit-clarify" not in text:
        gaps.append("missing speckit-clarify (one-skill smoke is not four-step)")
    if "speckit-plan" not in text:
        gaps.append("missing speckit-plan")
    if "speckit-tasks" not in text:
        gaps.append("missing speckit-tasks")
    if "hermes kanban ls" not in text:
        gaps.append("missing hermes kanban ls (hermes --version is the proxy class)")
    return gaps


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "dest_init",
        nargs="?",
        help="path to maas-api-key-provisioning.yaml",
    )
    args = ap.parse_args(argv)
    if not args.dest_init:
        return 2
    path = Path(args.dest_init)
    if not path.is_file():
        return _fail("missing dest-init file %s" % path)
    text = path.read_text(encoding="utf-8")
    gaps = check_text(text)
    if gaps:
        for g in gaps:
            print("  - " + g, file=sys.stderr)
        return _fail("today's dest-init cannot dispatch specify")
    print("OK: dest-init specify smoke (four-step skills + helper-by-path + hermes kanban ls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
