#!/usr/bin/env python3
"""R0 — Spec Kit preseed assert (Architect E-20260811T121308Z provision-owns-tools).

Fail-closed before M2a dispatch: `.specify/` must already exist from workspace
provision (devfile postStart / init-workspace.sh), with Non-Goals override
installed. Agents must not run `specify init` — verify-or-needs_input only.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    specify = root / ".specify"
    marker = specify / ".rhoai3-ads-provisioned"
    override = specify / "templates" / "overrides" / "spec-template.md"
    provision_asset = (
        root
        / ".hermes"
        / "skills"
        / "sdd"
        / "init-spec-workspace"
        / "assets"
        / "spec-template.md"
    )
    bad = 0

    if not specify.is_dir():
        print(
            "FAIL: .specify/ missing — provision must own Spec Kit init "
            "(devfile postStart / init-spec-workspace); agent has no init authority",
            file=sys.stderr,
        )
        bad = 1
    else:
        print("OK: .specify/ present")

    if not marker.is_file():
        print(
            "FAIL: missing .specify/.rhoai3-ads-provisioned (AD-S provision marker)",
            file=sys.stderr,
        )
        bad = 1
    else:
        print(f"OK: provision marker ({marker.read_text(encoding='utf-8').strip()})")

    if not override.is_file():
        print(
            "FAIL: missing Non-Goals override at "
            ".specify/templates/overrides/spec-template.md",
            file=sys.stderr,
        )
        bad = 1
    else:
        text = override.read_text(encoding="utf-8")
        if "Non-Goals" not in text and "Non-goals" not in text and "non-goals" not in text:
            print(
                "FAIL: override present but lacks Non-Goals section marker",
                file=sys.stderr,
            )
            bad = 1
        else:
            print("OK: Non-Goals override installed under .specify/")

    if not provision_asset.is_file():
        print(
            "FAIL: missing tip skill asset "
            ".hermes/skills/sdd/init-spec-workspace/assets/spec-template.md",
            file=sys.stderr,
        )
        bad = 1
    else:
        print("OK: tip Non-Goals skill asset present")

    if bad:
        print("FAIL: Spec Kit preseed (R0 / provision-owns-tools)", file=sys.stderr)
        return 1
    print("OK: Spec Kit preseed (R0 / provision-owns-tools)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
