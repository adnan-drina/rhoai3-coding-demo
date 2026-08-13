#!/usr/bin/env python3
"""R0/R3 — create-path tip sync proof (pre-v12 Architect E-20260811T102405Z).

Fail-closed if Hermes skill tree / M4 floor / measured-trap refs are missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_FILES = [
    ".hermes/skills/gates/check-release-readiness/scripts/run-m4-floor.sh",
    ".hermes/skills/gates/check-release-readiness/scripts/check-m4-floor-receipts.py",
    ".hermes/skills/gates/check-release-readiness/scripts/write-receipt.py",
    "governance/contracts/m4-floor-runner.md",
    ".hermes/skills/migration/spring-to-quarkus-patterns/references/security-config.md",
    ".hermes/skills/migration/spring-to-quarkus-patterns/references/security-anti-essay.md",
    ".hermes/skills/migration/spring-to-quarkus-patterns/references/di-config.md",
    ".hermes/skills/migration/spring-to-quarkus-patterns/references/testing.md",
    "governance/fixtures/security/golden-basic-authz/README.md",
    "governance/fixtures/testing/golden-test-application.properties",
    "governance/fixtures/inventory/entry-point-inventory-petclinic-f11.json",
    ".hermes/skills/analysis/scan-with-mta/scripts/check-findings-handoff.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/check-findings-handoff.py",
    # AD-S / Deputy E-120800Z — Non-Goals override must ride tip+overlay/R0
    ".hermes/skills/sdd/init-spec-workspace/assets/spec-template.md",
    # Architect E-121308Z — R0 Spec Kit preseed gate (live assert; script on tip)
    ".hermes/enforcement/dispatch-phase/scripts/check-specify-preseed.py",
    ".hermes/enforcement/validate-contracts/scripts/check-specify-absent.py",
    # Deputy E-20260813T184709Z — root scripts/ negative-space retired
    ".hermes/enforcement/validate-contracts/scripts/check-scripts-absent.py",
    # Architect E-122959Z — decision-complete card lint
    ".hermes/enforcement/dispatch-phase/scripts/check-decision-complete-cards.py",
    # Operator E-20260811T144200Z — deps + dest-inventory at create
    ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-destination-inventory.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py",
    # Architect E-20260811T170706Z Class A — quarantine survives dispatch
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-quarantine-tombstones.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/register-quarantine-tombstone.py",
    "governance/contracts/quarantine-survives-dispatch.md",
    # S-008 / W4 — parent-chain triad resurrection order
    ".hermes/enforcement/dispatch-phase/scripts/check-s008-resurrection-order.py",
    "governance/contracts/s008-quarantine-resurrection-order.md",
    # Architect E-20260811T173254Z Class A — residual worker kill+verify
    ".hermes/home/scripts/kill-and-verify-task-worker.sh",
    ".hermes/home/scripts/stamp-worker-pid-from-ps.py",
    ".hermes/home/scripts/assert-no-residual-workers.py",
    "governance/contracts/residual-worker-kill.md",
    # Architect E-20260811T175305Z Class A — scope-filtered compile
    ".hermes/enforcement/record-run-evidence/scripts/run-scoped-compile-gate.py",
    "governance/contracts/compile-scope-filtered.md",
    # Architect E-20260811T175509Z Class A — complete enforces cmd exits
    ".hermes/skills/gates/check-release-readiness/scripts/assert-complete-exit-criteria.py",
    ".hermes/home/scripts/enforce-complete-exit-criteria.py",
    "governance/contracts/complete-cmd-exit-criteria.md",
    # Architect E-20260811T181749Z Class A — interface-closure at create
    ".hermes/skills/sdd/check-spec-readiness/scripts/check-interface-closure.py",
    "governance/contracts/interface-closure.md",
    # Architect E-20260811T182820Z Class A — constraints preservation on amend
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-constraints-preserved.py",
    "governance/contracts/constraints-preservation-on-amend.md",
    # Operator E-20260811T184628Z — Managed Scope required at spawn (not symlink)
    ".hermes/home/scripts/assert-managed-scope-active.py",
    "governance/contracts/managed-scope-at-spawn.md",
    # Architect E-20260811T205329Z Class A — pin Managed Scope dir + guarded dispatch
    ".hermes/home/scripts/kanban-dispatch-guarded.sh",
    # Architect E-20260811T195141Z Class A — own-body digest at complete
    ".hermes/enforcement/record-run-evidence/scripts/check-body-digest-match.py",
    "governance/contracts/body-digest-own-story.md",
    # Architect E-20260811T200911Z Class A — mint-completeness + park-at-birth
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-constraints-complete.py",
    "governance/contracts/mint-completeness-constraints.md",
    "governance/contracts/park-at-birth.md",
    # Architect E-20260811T203657Z Class A — dependency/pre-exists closure
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py",
    "governance/contracts/dependency-closure.md",
    # Architect E-20260812T055516Z Class A — BANK-CONV-LIVE-WD-1 (stream-stale / warm-hb)
    ".hermes/home/scripts/check-conversation-liveness.py",
    # Operator E-20260812T061639Z / Architect E-20260812T061718Z Class A — card↔sidecar
    ".hermes/enforcement/record-run-evidence/scripts/assert-card-body-digest-match.py",
    "governance/contracts/card-sidecar-digest-cross-assert.md",
    # Architect E-20260812T064611Z / E-20260812T064637Z Class A — AD-012 lint + CS-7 bundle
    ".hermes/enforcement/validate-contracts/scripts/check-skill-conformance.py",
    ".hermes/enforcement/dispatch-phase/scripts/assert-bundle-skills-exist.py",
    ".hermes/home/skill-bundles/m3-implementer.yaml",
    # Architect E-20260812T074514Z RW-2 BANK-DEST-INV-HARDINVOKE-1
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dest-inventory-hardinvoke.py",
    "governance/contracts/dest-inventory-hardinvoke.md",
    # Architect E-20260812T074514Z RW-1 CONV-LIVE deepen
    ".hermes/home/scripts/classify-conv-live-stall.py",
    "governance/contracts/conv-live-bounded-retry.md",
    # Architect E-20260812T090529Z Class A — CONV-LIVE arm on dispatch path (D4)
    ".hermes/home/scripts/arm-conv-live-watchdog.sh",
    "governance/contracts/conv-live-arm-on-dispatch.md",
    # A2 — stream-liveness + fast-deny (watchdog callers)
    ".hermes/home/scripts/kanban-stuck-watchdog.py",
    ".hermes/home/scripts/check-stream-liveness.py",
    ".hermes/home/scripts/check-vllm-validation-fast-deny.py",
    "governance/contracts/stream-liveness.md",
    "governance/contracts/compaction-headroom-and-fast-deny.md",
    # A5 — spring-compat REJECT reference
    ".hermes/skills/migration/spring-to-quarkus-patterns/references/spring-compat-reject.md",
    # Wave B — bootstrap skill + skeleton retirement
    "BOOTSTRAP.md",
    ".hermes/skills/migration/bootstrap-quarkus-project/SKILL.md",
    ".hermes/skills/migration/bootstrap-quarkus-project/scripts/bootstrap.sh",
    ".hermes/skills/migration/manage-quarkus-extensions/scripts/check-pom-platform-pins.py",
]

REQUIRED_SUBSTRINGS = [
    (
        ".hermes/skills/migration/spring-to-quarkus-patterns/references/di-config.md",
        'componentModel = "cdi"',
        "MapStruct CDI feedforward",
    ),
    (
        ".hermes/skills/migration/spring-to-quarkus-patterns/references/di-config.md",
        "IfBuildProfile",
        "Profile API forbid",
    ),
    (
        ".hermes/skills/migration/spring-to-quarkus-patterns/references/testing.md",
        "continuous-testing",
        "R-M3.59 continuous-testing enum",
    ),
    (
        "BOOTSTRAP.md",
        "bootstrap-quarkus-project",
        "Wave B skeleton retired — bootstrap skill cited",
    ),
    (
        ".hermes/skills/migration/bootstrap-quarkus-project/SKILL.md",
        "check-pom-platform-pins.py",
        "bootstrap skill pins lint",
    ),
    (
        ".hermes/skills/migration/bootstrap-quarkus-project/scripts/bootstrap.sh",
        "BOOTSTRAP_MODE",
        "bootstrap dual-path CLI|Maven",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "check-create-path-tip-sync.py",
        "R0 wired into create-m3",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "Pre-v12 R5 hard-invoke traps",
        "R5 M3 hard-invoke cites",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "check-create-path-tip-sync.py",
        "R0 wired into dispatch-phase",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "REFUSE bare M2",
        "R1 bare M2 refuse",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
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
        "scan-with-mta",
        "M2a/M2b attach scan-with-mta (Deputy E-112700Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/check-phase-body-script-refs.py",
        "BODY_SCRIPT_LINT",
        "R0 body-script lint present",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "HERMES_SKILL_DIR:-.hermes/home/skills/software-development/check-spec-readiness",
        "M2a runtime skill-root anchor (Deputy E-113300Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/check-phase-body-script-refs.py",
        "software-development",
        "R0 lint accepts runtime software-development root",
    ),
    (
        ".hermes/skills/analysis/scan-with-mta/scripts/check-findings-handoff.py",
        "2 = missing script",
        "gate exit semantics typed (Deputy E-113300Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/check-phase-input-manifest.py",
        "phase input manifests",
        "R0 input-manifest lint present (Operator E-113700Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "Input manifest",
        "M2a/M2b input manifests (Operator E-113700Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "check-phase-input-manifest.py",
        "input-manifest wired into dispatch-phase",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "REVIEW_ADHERE_OBSERVE=",
        "dispatch emits Review adhere-observe Need (Operator E-114300Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "REVIEW_ADHERE_OBSERVE=",
        "create-m3 emits Review adhere-observe Need",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "speckit-specify",
        "M2a attaches speckit-specify (Architect E-115316Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "Spec Kit invoke-or-BLOCK",
        "M2a Spec Kit invoke-or-needs_input (Architect E-115316Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/check-completion-na-reject.py",
        "COMPLETION_NA",
        "completion consumer N/A reject (Operator E-120200Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "verify-or-BLOCK",
        "M2a step0 verify-or-BLOCK (Architect E-121308Z provision-owns-tools)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "check-specify-preseed.py",
        "M2a dispatch wires Spec Kit preseed R0",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "no init authority",
        "M2a forbids agent specify init",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/scripts/init-workspace.sh",
        'ASSET_OVERRIDE="${SKILL_DIR}/assets/spec-template.md"',
        "init-workspace resolves Non-Goals via ROOT (not SCRIPT_DIR walk)",
    ),
    (
        "devfile.yaml",
        "provision-owns-tools",
        "devfile postStart owns Spec Kit init",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "Per-artifact Spec Kit resume ladder",
        "M2b per-artifact resume ladder (Operator E-122500Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "check-decision-complete-cards.py",
        "decision-complete lint wired into dispatch",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/check-decision-complete-cards.py",
        "jump to /speckit-tasks",
        "decision-complete lint forbids jump-over-plan",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/check-operand-count.py",
        "build_config",
        "operand_class build_config (Operator E-124000Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        '--body "${BODY_JSON}"',
        "create-m3 validates single body (Operator E-124000Z)",
    ),
    (
        "governance/contracts/story-sizing.md",
        "operand_class",
        "story-sizing documents operand classes",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "--initial-status blocked",
        "M3 born parked (Deputy E-131900Z serial breach)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "Do NOT dispatch here",
        "create-m3 must not auto-dispatch (Deputy E-131900Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "--parent REQUIRED",
        "create-m3 requires --parent (Operator E-133000Z #5)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        'created-by "${PARENT_PRIMARY}"',
        "create-m3 created_by=parent for card-claim (Operator E-133000Z #5)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/check-created-cards-claim.py",
        "CREATED_CARDS_REJECT",
        "empty created_cards rejected when derived nonempty",
    ),
    (
        ".hermes/home/scripts/block-and-signal-worker.sh",
        "SIGTERM",
        "block-and-signal-worker (Operator E-133000Z #2)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "check-created-cards-claim.py",
        "M2b wires created_cards claim check",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py",
        "PARTITION_COVERAGE",
        "partition-coverage gate script (Architect E-133858Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "assert-quarantine-tombstones.py",
        "Class A quarantine tombstones at create (Architect E-170706Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "assert-quarantine-tombstones.py",
        "Class A quarantine tombstones at dispatch-phase (Architect E-170706Z)",
    ),
    (
        "governance/contracts/quarantine-survives-dispatch.md",
        "rhoai3.quarantine-tombstones/v1",
        "quarantine-survives-dispatch contract",
    ),
    (
        "governance/contracts/partition-coverage.md",
        "runtime inventory count",
        "partition-coverage contract (specimen-agnostic)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/specimen_agnostic.py",
        "path_rewrites",
        "specimen-agnostic helpers (Operator E-150800Z)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py",
        "allow-specimen-fixture",
        "coverage gate fixture-gated (Operator E-150800Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "Partition-coverage gate",
        "M2a wires partition-coverage VALID",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
        "DEPENDENCY_HOLE",
        "body dependencies stamp (Operator E-144200Z)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-destination-inventory.py",
        "destination-inventory",
        "destination inventory stamp (Operator E-144200Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "stamp-body-dependencies.py",
        "create-m3 wires dependencies stamp",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "stamp-destination-inventory.py",
        "create-m3 wires destination-inventory stamp",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "assert-complete-exit-criteria.py",
        "Class A complete-cmd assert before kanban_complete",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "run-scoped-compile-gate.py",
        "Class A scoped compile cited in M3 body",
    ),
    (
        "governance/contracts/compile-scope-filtered.md",
        "files_writable",
        "compile-scope-filtered contract",
    ),
    (
        "governance/contracts/complete-cmd-exit-criteria.md",
        "complete-exit-ok.json",
        "complete-cmd-exit-criteria contract",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "check-interface-closure.py",
        "Class A interface-closure wired into create-m3",
    ),
    (
        "governance/contracts/interface-closure.md",
        "BANK-CREATE-PATH-IFACE-1",
        "interface-closure contract",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-constraints-preserved.py",
        "CONSTRAINTS_PRESERVATION",
        "Class A constraints-preservation script",
    ),
    (
        "governance/contracts/constraints-preservation-on-amend.md",
        "silently drop",
        "constraints-preservation-on-amend contract",
    ),
    (
        ".hermes/home/scripts/assert-managed-scope-active.py",
        "HERMES_MANAGED_DIR_PIN",
        "Managed Scope spawn assert (dir pin)",
    ),
    (
        "governance/contracts/managed-scope-at-spawn.md",
        "not equal to pin",
        "managed-scope-at-spawn contract (pin)",
    ),
    (
        ".hermes/home/scripts/kanban-dispatch-guarded.sh",
        "assert-managed-scope-active.py",
        "Class A guarded kanban dispatch wrapper",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "Architect E-20260811T205329Z Class A",
        "Class A Managed Scope pin in dispatch-phase",
    ),
    (
        ".hermes/home/scripts/kanban-stuck-watchdog.py",
        "STILLBORN",
        "null-heartbeat stillborn watchdog",
    ),
    (
        ".hermes/enforcement/record-run-evidence/scripts/check-body-digest-match.py",
        "Class A E-20260811T195141Z",
        "own-body digest scope at --body alone",
    ),
    (
        "governance/contracts/body-digest-own-story.md",
        "own sidecar",
        "body-digest-own-story contract",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-constraints-complete.py",
        "MINT_COMPLETENESS",
        "Class A mint-completeness script",
    ),
    (
        "governance/contracts/mint-completeness-constraints.md",
        "preserve ≠ invent",
        "mint-completeness-constraints contract",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "PARK_AT_BIRTH",
        "Class A park-at-birth verify after create",
    ),
    (
        "governance/contracts/park-at-birth.md",
        "auto-promote",
        "park-at-birth contract",
    ),
    (
        ".hermes/home/scripts/kanban-stuck-watchdog.py",
        "COMPLETE-CMD enforce",
        "watchdog auto-wires complete-cmd reclaim",
    ),
    (
        ".hermes/home/scripts/kanban-stuck-watchdog.py",
        "BANK-CONV-LIVE-WD-1",
        "conversation-liveness warm-hb post-tool stall watchdog",
    ),
    (
        ".hermes/home/scripts/check-conversation-liveness.py",
        "BANK-CONV-LIVE-WD-1",
        "conversation-liveness detector script",
    ),
    (
        ".hermes/enforcement/record-run-evidence/scripts/assert-card-body-digest-match.py",
        "card↔sidecar digest mismatch",
        "Class A card↔sidecar digest cross-assert script",
    ),
    (
        "governance/contracts/card-sidecar-digest-cross-assert.md",
        "card↔sidecar",
        "card-sidecar-digest-cross-assert contract",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "assert-card-body-digest-match.py",
        "Class A card↔sidecar assert wired into create-m3 ack path",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py",
        "DEPENDENCY_CLOSURE",
        "Class A dependency-closure script",
    ),
    (
        "governance/contracts/dependency-closure.md",
        "BANK-DEP-CLOSURE-1",
        "dependency-closure contract",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "assert-dependency-closure.py",
        "Class A dependency-closure wired into create-m3",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dest-inventory-hardinvoke.py",
        "DEST_INV_HARDINVOKE",
        "RW-2 dest-inventory hard-invoke lint",
    ),
    (
        "governance/contracts/dest-inventory-hardinvoke.md",
        "BANK-DEST-INV-HARDINVOKE-1",
        "dest-inventory-hardinvoke contract",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "BANK-DEST-INV-HARDINVOKE-1",
        "RW-2 dest-inventory cite obligation on create-m3",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "assert-bundle-skills-exist.py",
        "RW-3 CS-7 bundle exists-assert wired into create-m3",
    ),
    (
        ".hermes/home/scripts/classify-conv-live-stall.py",
        "CONV_LIVE_CLASSIFY",
        "RW-1 CONV-LIVE stream-layer classifier",
    ),
    (
        "governance/contracts/conv-live-bounded-retry.md",
        "BOUNDED_RETRY",
        "RW-1 CONV-LIVE bounded in-turn retry contract",
    ),
    (
        ".hermes/home/scripts/arm-conv-live-watchdog.sh",
        "conv-live-watchdog-loop",
        "Class A CONV-LIVE arm-on-dispatch poller",
    ),
    (
        ".hermes/home/scripts/kanban-dispatch-guarded.sh",
        "arm-conv-live-watchdog.sh",
        "Class A CONV-LIVE arm wired into guarded dispatch",
    ),
    (
        "governance/contracts/conv-live-arm-on-dispatch.md",
        "BANK-CONV-LIVE-WD-1",
        "CONV-LIVE arm-on-dispatch contract",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "identity.story_id required",
        "D3 story id persisted on M3 card (Operator E-180236Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "created-story-cards.json",
        "D3 story↔card map stamped at create",
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
