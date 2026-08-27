#!/usr/bin/env python3
"""FAIL unless dest-init smokes specify via the same helper M2 uses.

Architect ``190736ZA``: dest-init presence/``--version`` is the proxy class.
Smoke is a fail-closed invocation of the skill-mandated dispatch path, not
a full speckit LLM run. Control: a dest-init that only writes the PATH
shim must REFUSE.

Required in dest-init (GitOps ``maas-api-key-provisioning.yaml``):

- helper ``specify-from-project.sh``
- ``export SPECIFY_REAL`` in the dest-init shim
- four overlay skills (specify/clarify/plan/tasks) on disk
- inspect ``hermes.manifest.json`` ``files`` (Architect ``170540ZA``:
  ``files: {}`` is not workflow dispatch)
- must **not** print ``MATCH helper-by-path workflow run speckit``
- ``hermes kanban ls``
- ``specify init --here --integration hermes --force --ignore-agent-tools``
  on a ``dest-init-fresh-smoke`` tree
- ``mvn … test`` on a ``dest-init-mvn-smoke`` tree

Exit 0: dest-init contains the honest smoke.
Exit 1: shim-only / vacuous workflow-run MATCH.
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
    if "MATCH helper-by-path workflow run speckit" in text:
        gaps.append(
            "vacuous MATCH helper-by-path workflow run speckit "
            "(hermes.manifest files:{} cannot dispatch that argv)"
        )
    if "specify-from-project.sh" not in text:
        gaps.append("missing specify-from-project.sh")
    if "SPECIFY_REAL" not in text:
        gaps.append("missing SPECIFY_REAL probe (would LLM or skip capability)")
    if "export SPECIFY_REAL" not in text:
        gaps.append(
            "missing export SPECIFY_REAL in dest-init shim "
            "(PATH search rediscovers the wrapper)"
        )
    if "hermes.manifest.json" not in text:
        gaps.append("missing hermes.manifest.json inspect (files:{} is the seam)")
    if "files empty" not in text and 'files: {}' not in text:
        gaps.append("missing hermes.manifest files empty handling")
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
    if "specify init" not in text:
        gaps.append("missing specify init (presence of .specify is not capability)")
    if "--here" not in text or "--integration" not in text:
        gaps.append("missing specify init --here --integration hermes")
    if "--force" not in text or "--ignore-agent-tools" not in text:
        gaps.append("missing specify init --force --ignore-agent-tools")
    if "dest-init-fresh-smoke" not in text:
        gaps.append("missing dest-init-fresh-smoke (must not specify init dest-9)")
    if "dest-init-mvn-smoke" not in text:
        gaps.append("missing dest-init-mvn-smoke (must not mvn test dest-9)")
    if '"test"' not in text and "'test'" not in text:
        gaps.append("missing mvn test argv (mvn --version is the proxy class)")
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
        return _fail("today's dest-init cannot smoke specify honestly")
    print("OK: dest-init specify smoke (four-step + specify init + mvn test + hermes kanban ls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
