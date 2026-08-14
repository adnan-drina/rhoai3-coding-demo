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
    ".hermes/skills/gates/check-release-readiness/references/m4-floor-runner.md",
    ".hermes/skills/migration/spring-to-quarkus-patterns/references/security-config.md",
    ".hermes/skills/migration/spring-to-quarkus-patterns/references/security-anti-essay.md",
    ".hermes/skills/migration/spring-to-quarkus-patterns/references/di-config.md",
    ".hermes/skills/migration/spring-to-quarkus-patterns/references/testing.md",
    ".hermes/enforcement/dispatch-phase/fixtures/security/golden-basic-authz/README.md",
    ".hermes/enforcement/dispatch-phase/fixtures/testing/golden-test-application.properties",
    ".hermes/skills/sdd/check-spec-readiness/fixtures/inventory/entry-point-inventory-petclinic-f11.json",
    ".hermes/skills/analysis/scan-with-mta/scripts/check-findings-handoff.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/check-findings-handoff.py",
    # AD-S / Deputy E-120800Z — Non-Goals override must ride tip+overlay/R0
    ".hermes/skills/sdd/init-spec-workspace/assets/spec-template.md",
    # Architect E-121308Z — R0 Spec Kit preseed gate (live assert; script on tip)
    ".hermes/enforcement/dispatch-phase/scripts/check-specify-preseed.py",
    ".hermes/enforcement/validate-contracts/scripts/check-specify-absent.py",
    # Deputy E-20260813T184709Z — root scripts/ negative-space retired
    ".hermes/enforcement/validate-contracts/scripts/check-scripts-absent.py",
    # GR1 / Deputy E-20260814T081104Z — contract lifecycle (no EOL in active dir)
    ".hermes/enforcement/validate-contracts/scripts/check-contract-lifecycle.py",
    ".hermes/enforcement/validate-contracts/references/contract-lifecycle.md",
    ".hermes/pins.json",
    ".hermes/platform/known-hermes-behaviours.md",
    ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    # Architect E-122959Z — decision-complete card lint
    ".hermes/enforcement/dispatch-phase/scripts/check-decision-complete-cards.py",
    # F2 / F6 / F9
    ".hermes/skills/sdd/check-spec-readiness/scripts/injection_receipt.py",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    ".hermes/enforcement/dispatch-phase/references/m3-implementer-standing.md",
    # Operator E-20260811T144200Z — deps + dest-inventory at create
    ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
    # Z3-a / A-6 — migration.yaml package stamp assert
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-migration-yaml-stamp.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-destination-inventory.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py",
    # Deputy E-20260814T074759Z V1 — M2 created-cards claim wrapper (F8a/F8b)
    # GR2: assert stays; mint moves to mint-m3-wave.sh (orchestrator-owned)
    ".hermes/enforcement/dispatch-phase/scripts/assert-m2b-created-cards-claim.sh",
    ".hermes/enforcement/dispatch-phase/scripts/check-created-cards-claim.py",
    ".hermes/enforcement/dispatch-phase/scripts/mint-m3-wave.sh",
    ".hermes/home/scripts/enforce-m2b-created-cards-claim.py",
    # Architect E-20260811T170706Z Class A — quarantine survives dispatch
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-quarantine-tombstones.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/register-quarantine-tombstone.py",
    # S-008 / W4 — parent-chain triad resurrection order
    ".hermes/enforcement/dispatch-phase/scripts/check-s008-resurrection-order.py",
    # Architect E-20260811T173254Z Class A — residual worker kill+verify
    ".hermes/home/scripts/kill-and-verify-task-worker.sh",
    ".hermes/home/scripts/stamp-worker-pid-from-ps.py",
    ".hermes/home/scripts/assert-no-residual-workers.py",
    ".hermes/platform/known-hermes-behaviours.md",
    # Architect E-20260811T175305Z Class A — scope-filtered compile
    ".hermes/enforcement/record-run-evidence/scripts/run-scoped-compile-gate.py",
    ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
    # Architect E-20260811T175509Z Class A — complete enforces cmd exits
    ".hermes/skills/gates/check-release-readiness/scripts/assert-complete-exit-criteria.py",
    ".hermes/home/scripts/enforce-complete-exit-criteria.py",
    ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
    # Architect E-20260811T181749Z Class A — interface-closure at create
    ".hermes/skills/sdd/check-spec-readiness/scripts/check-interface-closure.py",
    ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
    # Architect E-20260811T182820Z Class A — constraints preservation on amend
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-constraints-preserved.py",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    # Operator E-20260811T184628Z — Managed Scope required at spawn (not symlink)
    ".hermes/home/scripts/assert-managed-scope-active.py",
    # Architect E-20260811T205329Z Class A — pin Managed Scope dir + guarded dispatch
    ".hermes/home/scripts/kanban-dispatch-guarded.sh",
    # Architect E-20260811T195141Z Class A — own-body digest at complete
    ".hermes/enforcement/record-run-evidence/scripts/check-body-digest-match.py",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    # Architect E-20260811T200911Z Class A — mint-completeness + park-at-birth
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-constraints-complete.py",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    # Architect E-20260811T203657Z Class A — dependency/pre-exists closure
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py",
    ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
    # Architect E-20260812T055516Z Class A — BANK-CONV-LIVE-WD-1 (stream-stale / warm-hb)
    ".hermes/home/scripts/check-conversation-liveness.py",
    # Operator E-20260812T061639Z / Architect E-20260812T061718Z Class A — card↔sidecar
    ".hermes/enforcement/record-run-evidence/scripts/assert-card-body-digest-match.py",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    # Architect E-20260812T064611Z / E-20260812T064637Z Class A — AD-012 lint + CS-7 bundle
    ".hermes/enforcement/validate-contracts/scripts/check-skill-conformance.py",
    ".hermes/enforcement/dispatch-phase/scripts/assert-bundle-skills-exist.py",
    ".hermes/home/skill-bundles/m3-implementer.yaml",
    # Architect E-20260812T074514Z RW-2 BANK-DEST-INV-HARDINVOKE-1
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dest-inventory-hardinvoke.py",
    # Architect E-20260812T074514Z RW-1 CONV-LIVE deepen
    ".hermes/home/scripts/classify-conv-live-stall.py",
    # Architect E-20260812T090529Z Class A — CONV-LIVE arm on dispatch path (D4)
    ".hermes/home/scripts/arm-conv-live-watchdog.sh",
    # A2 — stream-liveness + fast-deny (watchdog callers)
    ".hermes/home/scripts/kanban-stuck-watchdog.py",
    ".hermes/home/scripts/check-stream-liveness.py",
    ".hermes/home/scripts/check-vllm-validation-fast-deny.py",
    ".hermes/platform/known-hermes-behaviours.md",
    # A5 — spring-compat REJECT reference
    ".hermes/skills/migration/spring-to-quarkus-patterns/references/spring-compat-reject.md",
    # Wave B — bootstrap skill + skeleton retirement
    ".hermes/skills/migration/bootstrap-quarkus-project/SKILL.md",
    ".hermes/skills/migration/bootstrap-quarkus-project/scripts/bootstrap.sh",
    ".hermes/skills/migration/manage-quarkus-extensions/scripts/check-pom-platform-pins.py",
    # W1 / W3 / A-3 — CLI provision, tooling assert, Jacoco gate
    ".hermes/skills/migration/manage-quarkus-extensions/scripts/provision-quarkus-cli.sh",
    ".hermes/skills/migration/manage-quarkus-extensions/scripts/assert-extension-tooling.py",
    ".hermes/skills/migration/manage-quarkus-extensions/scripts/check-pom-jacoco-wiring.py",
    ".hermes/skills/migration/bootstrap-quarkus-project/references/foundation-jacoco-wiring.md",
    "devfile.yaml",
    # §K / A-5
    ".hermes/home/scripts/stop-worker-session.sh",
    ".hermes/platform/known-hermes-behaviours.md",
    # T-8 / Z2
    ".hermes/skills/sdd/derive-story-oracles/SKILL.md",
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
    # T-1 / Z2
    ".hermes/skills/migration/reference-rh-quarkus-pom/SKILL.md",
    ".hermes/skills/migration/reference-rh-quarkus-pom/references/pom-structure.md",
    # RS1 / Z2
    ".hermes/skills/migration/configure-quarkus-profiles/SKILL.md",
    # T-7 / R-SKILL / Z2
    ".hermes/skills/migration/form-entity-persistence/SKILL.md",
    ".hermes/skills/migration/spring-to-quarkus-patterns/references/transitive-supporting-types.md",
]

# Tip-sync substring table (R0/R3).
# V2 audit (E-20260814T074759Z): prefer receipt / invocation chains over bare
# script-name greps inside callers. Name literals remain only where the
# *behaviour* is the presence of that token (schema ids, reject tokens,
# contract BANK-* ids). The M2b created-cards row was converted to the
# wrapper→claim-check→receipt chain after F8a (V1).
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
        ".hermes/skills/migration/bootstrap-quarkus-project/SKILL.md",
        "quarkus create app",
        "Wave B skeleton retired — bootstrap skill forbids create-app",
    ),
    (
        ".hermes/skills/migration/bootstrap-quarkus-project/SKILL.md",
        "check-pom-platform-pins.py",
        "bootstrap skill pins lint",
    ),
    (
        ".hermes/skills/migration/bootstrap-quarkus-project/scripts/bootstrap.sh",
        "CREATE_PATH_RETIRED",
        "bootstrap create path retired (DD1)",
    ),
(
        "AGENTS.md",
        "stop-worker-session.sh",
        "A-5 AGENTS cites worker stop entry point",
    ),
    (
        ".hermes/enforcement/validate-contracts/scripts/validate.sh",
        "--include-enforcement",
        "§K skill conformance covers enforcement packages",
    ),
    (
        ".hermes/enforcement/validate-contracts/scripts/check-skill-conformance.py",
        "## Pitfalls",
        "§K Pitfalls is a required skill section",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/check-surgical-scopes.py",
        "dual-oracle refuse",
        "T-8 dual-oracle refuse in surgical-scopes",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "derive-story-oracles",
        "T-8 skill attached on M2/M3",
    ),
    (
        ".hermes/skills/sdd/derive-story-oracles/SKILL.md",
        "derive-story-oracles",
        "T-8 derive-story-oracles present (semantic-exits retired)",
    ),
    (
        ".hermes/skills/migration/reference-rh-quarkus-pom/SKILL.md",
        "reference-rh-quarkus-pom",
        "T-1 RH Quarkus POM structure skill",
    ),
    (
        ".hermes/skills/migration/bootstrap-quarkus-project/SKILL.md",
        "reference-rh-quarkus-pom",
        "bootstrap cites in-tree T-1 skill",
    ),
    (
        ".hermes/skills/migration/manage-quarkus-extensions/references/extension-obligations.md",
        "migrate-at-start",
        "T-3 extension obligations reference",
    ),
    (
        ".hermes/skills/migration/configure-quarkus-profiles/SKILL.md",
        "config_profile_load",
        "RS1 configure-quarkus-profiles skill",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "configure-quarkus-profiles",
        "RS1 skill attached on M3",
    ),
    (
        ".hermes/skills/migration/form-entity-persistence/SKILL.md",
        "MappedSuperclass",
        "T-7 form-entity-persistence skill",
    ),
    (
        ".hermes/skills/migration/spring-to-quarkus-patterns/references/transitive-supporting-types.md",
        "supporting type",
        "R-SKILL-A transitive supporting types",
    ),
    (
        ".hermes/skills/migration/spring-to-quarkus-patterns/references/cache-adopt-defer.md",
        "CacheResult",
        "R-SKILL-C cache adopt/defer",
    ),
    (
        ".hermes/skills/migration/spring-to-quarkus-patterns/references/cdi-service-facade.md",
        "readOnly",
        "R-SKILL-D CDI service facade",
    ),
    (
        "devfile.yaml",
        "provision-quarkus-cli.sh",
        "W1 Quarkus CLI provisioned from postStart",
    ),
    (
        ".hermes/skills/migration/manage-quarkus-extensions/scripts/provision-quarkus-cli.sh",
        "registry.quarkus.redhat.com",
        "W1 RH registry-first config",
    ),
    (
        ".hermes/enforcement/validate-contracts/scripts/validate.sh",
        "check-pom-jacoco-wiring.py",
        "A-3 Jacoco wiring gate in validate-contracts",
    ),
    (
        ".hermes/enforcement/validate-contracts/scripts/validate.sh",
        "assert-extension-tooling.py",
        "W3 extension tooling typed preflight",
    ),
    (
        ".hermes/skills/migration/bootstrap-quarkus-project/SKILL.md",
        "Author",
        "bootstrap skill documents POM authoring (DD1/DD2)",
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
        "REFUSE M2a/M2b",
        "R1/GR2 refuse retired M2a/M2b",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "run-m4-floor.sh",
        "R2 M4 floor in M4 body",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "M2a:",
        "R1 M2a phase key (retired stub GR2)",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "M2b:",
        "R1 M2b phase key (retired stub GR2)",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "scan-with-mta",
        "M2 attach scan-with-mta (Deputy E-112700Z / GR2)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/check-phase-body-script-refs.py",
        "BODY_SCRIPT_LINT",
        "R0 body-script lint present",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "HERMES_SKILL_DIR:-.hermes/home/skills/software-development/check-spec-readiness",
        "M2 runtime skill-root anchor (Deputy E-113300Z / GR2)",
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
        "M2 input manifests (Operator E-113700Z / GR2)",
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
        "M2 attaches speckit-specify (Architect E-115316Z / GR2)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "Spec Kit invoke-or-BLOCK",
        "M2 Spec Kit invoke-or-needs_input (Architect E-115316Z / GR2)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/check-completion-na-reject.py",
        "COMPLETION_NA",
        "completion consumer N/A reject (Operator E-120200Z)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "verify-or-BLOCK",
        "M2 step0 verify-or-BLOCK (Architect E-121308Z provision-owns-tools)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "check-specify-preseed.py",
        "M2 dispatch wires Spec Kit preseed R0",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/dispatch-phase.sh",
        "no init authority",
        "M2 forbids agent specify init",
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
        "M2 per-artifact resume ladder (Operator E-122500Z / GR2)",
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
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
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
    # V1 (E-20260814T074759Z): assert property chain, not a bare script-name
    # inside dispatch-phase.sh. GR2: claim check lives on mint-m3-wave.sh.
    (
        ".hermes/enforcement/dispatch-phase/scripts/mint-m3-wave.sh",
        "assert-m2b-created-cards-claim.sh",
        "mint-m3-wave wires created_cards claim check (GR2 orchestrator mint)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/mint-m3-wave.sh",
        "orchestrator-owned mint",
        "GR2/AD-016 mint-m3-wave is orchestrator-owned",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/assert-m2b-created-cards-claim.sh",
        "check-created-cards-claim.py",
        "M2 claim wrapper invokes check-created-cards-claim.py",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/assert-m2b-created-cards-claim.sh",
        "m2b-created-cards-ok.json",
        "M2 claim wrapper stamps m2b-created-cards-ok.json receipt",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/assert-m2b-created-cards-claim.sh",
        "rhoai3.m2b-created-cards-ok/v1",
        "M2 claim receipt schema id",
    ),
    (
        ".hermes/home/scripts/enforce-m2b-created-cards-claim.py",
        "m2b-created-cards-ok.json",
        "F8b machinery reclaims done without M2 ok receipt",
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
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-quarantine-tombstones.py",
        "rhoai3.quarantine-tombstones/v1",
        "quarantine-survives-dispatch wired (assert schema)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
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
        "M2 wires partition-coverage VALID (GR2)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
        "DEPENDENCY_HOLE",
        "body dependencies stamp (Operator E-144200Z)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-migration-yaml-stamp.py",
        "MIGRATION_YAML_STAMP_VACUOUS",
        "Z3-a migration.yaml package stamp assert",
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
        ".hermes/enforcement/dispatch-phase/references/m3-implementer-standing.md",
        "run-scoped-compile-gate.py",
        "Class A scoped compile cited in M3 standing procedure (F6)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
        "files_writable",
        "compile-scope-filtered contract",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
        "complete-exit-ok.json",
        "complete-cmd-exit-criteria contract",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "check-interface-closure.py",
        "Class A interface-closure wired into create-m3",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
        "BANK-CREATE-PATH-IFACE-1",
        "interface-closure contract",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-constraints-preserved.py",
        "CONSTRAINTS_PRESERVATION",
        "Class A constraints-preservation script",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "assert-constraints-preserved.py",
        "F9 create-m3 wires constraints snapshot-before",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "assert-constraints-preserved.py",
        "F9 scar-archive triage: constraints snapshot wired at create",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-constraints-complete.py",
        "F7 short imperatives",
        "F7 constraints are short imperatives",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
        "silently drop",
        "constraints-preservation-on-amend contract",
    ),
    (
        ".hermes/home/scripts/assert-managed-scope-active.py",
        "HERMES_MANAGED_DIR_PIN",
        "Managed Scope spawn assert (dir pin)",
    ),
    (
        ".hermes/home/scripts/assert-managed-scope-active.py",
        "HERMES_MANAGED_DIR_PIN",
        "managed-scope-at-spawn pin assert present",
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
        ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
        "own sidecar",
        "body-digest-own-story contract",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-constraints-complete.py",
        "MINT_COMPLETENESS",
        "Class A mint-completeness script",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
        "preserve ≠ invent",
        "mint-completeness-constraints contract",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "PARK_AT_BIRTH",
        "Class A park-at-birth verify after create",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "auto-promote",
        "park-at-birth: create path refuses auto-promote",
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
        ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
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
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
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
        ".hermes/enforcement/dispatch-phase/references/m3-implementer-standing.md",
        "BANK-DEST-INV-HARDINVOKE-1",
        "dest-inventory-hardinvoke standing cite",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "BANK-DEST-INV-HARDINVOKE-1",
        "RW-2 dest-inventory cite obligation on create-m3",
    ),
    (
        ".hermes/enforcement/dispatch-phase/references/m3-implementer-standing.md",
        "BANK-DEST-INV-HARDINVOKE-1",
        "F6 standing procedure carries BANK-DEST-INV detail",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "m3-implementer-standing.md",
        "F6 card points at standing procedure (≤1500 chars)",
    ),
    (
        ".hermes/enforcement/dispatch-phase/scripts/create-m3-implementer.sh",
        "F6 card budget exceeded",
        "F6 fail-closed card char budget",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/injection_receipt.py",
        "rhoai3.injection-receipt/v1",
        "F2 injection receipt helper",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
        "rhoai3.injection-receipt/v1",
        "F2 injection-receipts contract",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-constraints-complete.py",
        "write_injection_receipt",
        "F2 mint-constraints --inject stamps receipt",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
        "write_injection_receipt",
        "F2 dependencies --write stamps receipt",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-destination-inventory.py",
        "write_injection_receipt",
        "F2 dest-inventory --write stamps receipt",
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
        ".hermes/home/scripts/classify-conv-live-stall.py",
        "CONV_LIVE_CLASSIFY",
        "RW-1 CONV-LIVE bounded retry classifier present",
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
        ".hermes/home/scripts/arm-conv-live-watchdog.sh",
        "BANK-CONV-LIVE-WD-1",
        "CONV-LIVE arm-on-dispatch bank id present",
    ),
    (
        ".hermes/enforcement/enforce-authority-boundary/scripts/apply-write-fence.sh",
        ".hermes/enforcement",
        "A-1 FS-RO write-fence locks .hermes/enforcement (DD5)",
    ),
    (
        "AGENTS.md",
        "DD5",
        "DD5 refusal doctrine in AGENTS.md",
    ),
    (
        ".hermes/SOUL.md",
        "DD5",
        "DD5 refusal doctrine in SOUL.md",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
        "DD6",
        "DD6 foundation asserts resolution in story-sizing",
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
