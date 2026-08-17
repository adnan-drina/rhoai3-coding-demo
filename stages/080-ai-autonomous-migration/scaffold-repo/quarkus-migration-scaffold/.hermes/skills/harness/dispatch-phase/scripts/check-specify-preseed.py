#!/usr/bin/env python3
"""R0 — Spec Kit preseed assert (Architect E-20260811T121308Z provision-owns-tools).

Fail-closed before M2 dispatch: `.specify/` must already exist from workspace
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
    tasks_override = specify / "templates" / "overrides" / "tasks-template.md"
    provision_asset = (
        root
        / ".hermes"
        / "skills"
        / "sdd"
        / "init-spec-workspace"
        / "assets"
        / "spec-template.md"
    )
    provision_tasks = (
        root
        / ".hermes"
        / "skills"
        / "sdd"
        / "init-spec-workspace"
        / "assets"
        / "tasks-template.md"
    )
    provision_constitution = (
        root
        / ".hermes"
        / "skills"
        / "sdd"
        / "init-spec-workspace"
        / "assets"
        / "constitution.md"
    )
    provision_overlay = (
        root
        / ".hermes"
        / "skills"
        / "sdd"
        / "init-spec-workspace"
        / "assets"
        / "stop-before-implement.overlay.yml"
    )
    dest_constitution = specify / "memory" / "constitution.md"
    dest_overlay = (
        specify / "workflows" / "overlays" / "speckit" / "stop-before-implement.yml"
    )
    dest_legacy_workflow = specify / "workflows" / "sdd-to-tasks.yml"
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

    if not tasks_override.is_file():
        print(
            "FAIL: missing unique-owner override at "
            ".specify/templates/overrides/tasks-template.md",
            file=sys.stderr,
        )
        bad = 1
    else:
        ttext = tasks_override.read_text(encoding="utf-8")
        if "one creator phase per dest path" not in ttext:
            print(
                "FAIL: tasks-template override present but lacks unique-owner pin",
                file=sys.stderr,
            )
            bad = 1
        else:
            print("OK: unique-owner tasks-template override installed under .specify/")

    if not provision_asset.is_file():
        print(
            "FAIL: missing tip skill asset "
            ".hermes/skills/sdd/init-spec-workspace/assets/spec-template.md",
            file=sys.stderr,
        )
        bad = 1
    else:
        print("OK: tip Non-Goals skill asset present")

    if not provision_tasks.is_file():
        print(
            "FAIL: missing tip skill asset "
            ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
            file=sys.stderr,
        )
        bad = 1
    else:
        ptt = provision_tasks.read_text(encoding="utf-8")
        if "one creator phase per dest path" not in ptt:
            print(
                "FAIL: tip tasks-template asset lacks unique-owner pin",
                file=sys.stderr,
            )
            bad = 1
        else:
            print("OK: tip unique-owner tasks-template skill asset present")

    if not provision_constitution.is_file():
        print(
            "FAIL: missing tip constitution asset "
            ".hermes/skills/sdd/init-spec-workspace/assets/constitution.md",
            file=sys.stderr,
        )
        bad = 1
    else:
        ctext = provision_constitution.read_text(encoding="utf-8")
        if "[PRINCIPLE_1" in ctext or "[PROJECT_NAME]" in ctext or "[PLACEHOLDER]" in ctext:
            print("FAIL: constitution asset still has spec-kit placeholders", file=sys.stderr)
            bad = 1
        elif "3.27.3.SP1" not in ctext or "Java 21" not in ctext:
            print(
                "FAIL: constitution asset missing Quarkus 3.27.3.SP1 / Java 21",
                file=sys.stderr,
            )
            bad = 1
        else:
            print("OK: tip constitution asset names Red Hat Quarkus + Java 21")

    if not provision_overlay.is_file():
        print(
            "FAIL: missing tip overlay "
            ".hermes/skills/sdd/init-spec-workspace/assets/"
            "stop-before-implement.overlay.yml",
            file=sys.stderr,
        )
        bad = 1
    else:
        wtext = provision_overlay.read_text(encoding="utf-8")
        if "command: speckit.implement" in wtext:
            print(
                "FAIL: speckit overlay must not invoke speckit.implement",
                file=sys.stderr,
            )
            bad = 1
        elif "remove: implement" not in wtext:
            print("FAIL: speckit overlay missing remove: implement", file=sys.stderr)
            bad = 1
        elif "speckit.clarify" not in wtext:
            print("FAIL: speckit overlay missing speckit.clarify", file=sys.stderr)
            bad = 1
        elif "evidence/findings-handoff.json" not in wtext:
            print(
                "FAIL: speckit overlay missing M1 findings-handoff path",
                file=sys.stderr,
            )
            bad = 1
        elif "evidence/entry-point-inventory.json" not in wtext:
            print(
                "FAIL: speckit overlay missing M1 entry-point-inventory path",
                file=sys.stderr,
            )
            bad = 1
        elif "_transcribed_http" in wtext:
            print(
                "FAIL: speckit overlay must not cite handover-mint _transcribed_http "
                "(ingress-only; emit pin is tasks-template override)",
                file=sys.stderr,
            )
            bad = 1
        else:
            print("OK: tip speckit overlay (clarify, no implement, M1 paths, ingress-only)")

    if specify.is_dir():
        if not dest_constitution.is_file():
            print(
                "FAIL: missing .specify/memory/constitution.md "
                "(provision overlay; not spec-kit placeholders)",
                file=sys.stderr,
            )
            bad = 1
        else:
            dtext = dest_constitution.read_text(encoding="utf-8")
            if "[PRINCIPLE_1" in dtext or "[PROJECT_NAME]" in dtext:
                print(
                    "FAIL: dest constitution still spec-kit placeholders",
                    file=sys.stderr,
                )
                bad = 1
            elif "3.27.3.SP1" not in dtext:
                print("FAIL: dest constitution missing Quarkus pin", file=sys.stderr)
                bad = 1
            else:
                print("OK: dest constitution populated")
        if dest_legacy_workflow.is_file():
            print(
                "FAIL: leftover Path-A .specify/workflows/sdd-to-tasks.yml "
                "(A-1 overlay replaces it; re-run init-workspace.sh)",
                file=sys.stderr,
            )
            bad = 1
        if not dest_overlay.is_file():
            print(
                "FAIL: missing .specify/workflows/overlays/speckit/"
                "stop-before-implement.yml",
                file=sys.stderr,
            )
            bad = 1
        else:
            print("OK: dest speckit overlay installed")

    if bad:
        print("FAIL: Spec Kit preseed (R0 / provision-owns-tools)", file=sys.stderr)
        return 1
    print("OK: Spec Kit preseed (R0 / provision-owns-tools)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
