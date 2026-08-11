#!/usr/bin/env python3
"""R0/R3 — create-path tip sync proof (pre-v12 Architect E-20260811T102405Z).

Fail-closed if Hermes skill tree / M4 floor / measured-trap refs are missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_FILES = [
    ".hermes/skills/validation-release-gates/scripts/run-m4-floor.sh",
    ".hermes/skills/validation-release-gates/scripts/check-m4-floor-receipts.py",
    ".hermes/skills/validation-release-gates/scripts/write-receipt.py",
    "migration/contracts/m4-floor-runner.md",
    ".hermes/skills/spring-to-quarkus-patterns/references/security-config.md",
    ".hermes/skills/spring-to-quarkus-patterns/references/security-anti-essay.md",
    ".hermes/skills/spring-to-quarkus-patterns/references/di-config.md",
    ".hermes/skills/spring-to-quarkus-patterns/references/testing.md",
    "migration/fixtures/security/golden-basic-authz/README.md",
    "migration/fixtures/testing/golden-test-application.properties",
    "migration/fixtures/inventory/entry-point-inventory-petclinic-f11.json",
    ".hermes/skills/mta-analysis/scripts/check-findings-handoff.py",
    ".hermes/skills/sdd-readiness/scripts/check-findings-handoff.py",
]

REQUIRED_SUBSTRINGS = [
    (
        ".hermes/skills/spring-to-quarkus-patterns/references/di-config.md",
        'componentModel = "cdi"',
        "MapStruct CDI feedforward",
    ),
    (
        ".hermes/skills/spring-to-quarkus-patterns/references/di-config.md",
        "IfBuildProfile",
        "Profile API forbid",
    ),
    (
        ".hermes/skills/spring-to-quarkus-patterns/references/testing.md",
        "continuous-testing",
        "R-M3.59 continuous-testing enum",
    ),
    (
        "src/main/resources/application.properties",
        "quarkus.datasource.db-kind",
        "scaffold default DS (R4)",
    ),
    (
        "pom.xml",
        "quarkus-jdbc-",
        "scaffold jdbc driver (R4)",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/create-m3-implementer.sh",
        "check-create-path-tip-sync.py",
        "R0 wired into create-m3",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/create-m3-implementer.sh",
        "Pre-v12 R5 hard-invoke traps",
        "R5 M3 hard-invoke cites",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/dispatch-phase.sh",
        "check-create-path-tip-sync.py",
        "R0 wired into dispatch-phase",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/dispatch-phase.sh",
        "REFUSE bare M2",
        "R1 bare M2 refuse",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/dispatch-phase.sh",
        "run-m4-floor.sh",
        "R2 M4 floor in M4 body",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "M2a:",
        "R1 M2a phase key",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "M2b:",
        "R1 M2b phase key",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "mta-analysis",
        "M2a/M2b attach mta-analysis (Deputy E-112700Z)",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/check-phase-body-script-refs.py",
        "BODY_SCRIPT_LINT",
        "R0 body-script lint present",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/dispatch-phase.sh",
        "HERMES_SKILL_DIR:-.hermes/home/skills/software-development/sdd-readiness",
        "M2a runtime skill-root anchor (Deputy E-113300Z)",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/check-phase-body-script-refs.py",
        "software-development",
        "R0 lint accepts runtime software-development root",
    ),
    (
        ".hermes/skills/mta-analysis/scripts/check-findings-handoff.py",
        "2 = missing script",
        "gate exit semantics typed (Deputy E-113300Z)",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/check-phase-input-manifest.py",
        "phase input manifests",
        "R0 input-manifest lint present (Operator E-113700Z)",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/dispatch-phase.sh",
        "Input manifest",
        "M2a/M2b input manifests (Operator E-113700Z)",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/dispatch-phase.sh",
        "check-phase-input-manifest.py",
        "input-manifest wired into dispatch-phase",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/dispatch-phase.sh",
        "REVIEW_ADHERE_OBSERVE=",
        "dispatch emits Review adhere-observe Need (Operator E-114300Z)",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/create-m3-implementer.sh",
        "REVIEW_ADHERE_OBSERVE=",
        "create-m3 emits Review adhere-observe Need",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "speckit-specify",
        "M2a attaches speckit-specify (Architect E-115316Z)",
    ),
    (
        ".hermes/skills/phase-dispatch/scripts/dispatch-phase.sh",
        "Spec Kit invoke-or-BLOCK",
        "M2a Spec Kit invoke-or-needs_input (Architect E-115316Z)",
    ),
]


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    bad = 0
    for rel in REQUIRED_FILES:
        path = root / rel
        if not path.is_file():
            print(f"FAIL: missing {rel}", file=sys.stderr)
            bad = 1
        else:
            print(f"OK: {rel}")
    for rel, needle, label in REQUIRED_SUBSTRINGS:
        path = root / rel
        if not path.is_file():
            print(f"FAIL: {label}: missing {rel}", file=sys.stderr)
            bad = 1
            continue
        text = path.read_text(encoding="utf-8")
        if needle not in text:
            print(f"FAIL: {label}: {rel} missing {needle!r}", file=sys.stderr)
            bad = 1
        else:
            print(f"OK: {label}")
    if bad:
        print("FAIL: create-path tip sync (R0/R3)", file=sys.stderr)
        return 1
    print("OK: create-path tip sync (R0/R3)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
