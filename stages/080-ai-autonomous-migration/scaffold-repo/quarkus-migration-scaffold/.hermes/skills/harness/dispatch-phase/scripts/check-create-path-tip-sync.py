#!/usr/bin/env python3
"""R0/R3 — create-path tip sync proof (pre-v12 Architect E-20260811T102405Z).

Fail-closed if Hermes skill tree / M4 floor / measured-trap refs are missing.
"""
from __future__ import annotations

import subprocess
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
    ".hermes/skills/harness/dispatch-phase/fixtures/security/golden-basic-authz/README.md",
    ".hermes/skills/harness/dispatch-phase/fixtures/testing/golden-test-application.properties",
    ".hermes/skills/sdd/check-spec-readiness/fixtures/inventory/entry-point-inventory-petclinic-f11.json",
    ".hermes/skills/analysis/scan-with-mta/scripts/check-findings-handoff.py",
    # AD-S / Deputy E-120800Z — Non-Goals override must ride tip+overlay/R0
    ".hermes/skills/sdd/init-spec-workspace/assets/spec-template.md",
    ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
    ".hermes/skills/sdd/init-spec-workspace/assets/constitution.md",
    ".hermes/skills/sdd/init-spec-workspace/assets/stop-before-implement.overlay.yml",
    # Architect E-121308Z — R0 Spec Kit preseed gate (live assert; script on tip)
    ".hermes/skills/harness/dispatch-phase/scripts/check-specify-preseed.py",
    ".hermes/skills/harness/validate-contracts/scripts/check-specify-absent.py",
    # Deputy E-20260813T184709Z — root scripts/ negative-space retired
    ".hermes/skills/harness/validate-contracts/scripts/check-scripts-absent.py",
    ".hermes/skills/harness/validate-contracts/scripts/pre-commit-index-suite.sh",
    # GR1 / Deputy E-20260814T081104Z — contract lifecycle (no EOL in active dir)
    ".hermes/skills/harness/validate-contracts/scripts/check-contract-lifecycle.py",
    ".hermes/skills/harness/validate-contracts/references/contract-lifecycle.md",
    ".hermes/pins.json",
    ".hermes/platform/known-hermes-behaviours.md",
    ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    # Architect E-122959Z — decision-complete card lint
    ".hermes/skills/harness/dispatch-phase/scripts/check-decision-complete-cards.py",
    # F2 / F6 / F9
    ".hermes/skills/sdd/check-spec-readiness/scripts/injection_receipt.py",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md",
    # Operator E-20260811T144200Z — deps + dest-inventory at create
    ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
    # Z3-a / A-6 — migration.yaml package stamp assert
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-migration-yaml-stamp.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-destination-inventory.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py",
    # Deputy E-20260814T074759Z V1 — M2 created-cards claim wrapper (F8a/F8b)
    # GR2: assert stays; mint Procedure is mint-m3-hermes.md (holder kanban_create)
    ".hermes/skills/harness/dispatch-phase/scripts/assert-m2b-created-cards-claim.sh",
    ".hermes/skills/harness/dispatch-phase/scripts/check-created-cards-claim.py",
    ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
    ".hermes/skills/harness/dispatch-phase/references/holder-card-body.md",
    ".hermes/skills/harness/dispatch-phase/references/m1-verifier.md",
    ".hermes/skills/harness/dispatch-phase/scripts/check-m1-verifier.py",
    ".hermes/skills/harness/dispatch-phase/scripts/assert-seat-hermes-pin.py",
    ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
    ".hermes/skills/harness/dispatch-phase/scripts/scratch-assemble-mint.py",
    ".hermes/skills/harness/dispatch-phase/references/handover-mint.md",
    ".hermes/skills/harness/dispatch-phase/references/delivery-path.md",
    ".hermes/skills/harness/dispatch-phase/references/native-dispatch.md",
    ".hermes/skills/harness/dispatch-phase/references/m2-planner.md",
        ".hermes/skills/harness/dispatch-phase/fixtures/handover/tasks.attempt-2-speckit.md",
        ".hermes/skills/harness/dispatch-phase/fixtures/handover/inventory.attempt-2.json",
        ".hermes/skills/harness/dispatch-phase/fixtures/handover/tasks.native-speckit.md",
        ".hermes/skills/harness/dispatch-phase/fixtures/handover/inventory.native-speckit.json",
        ".hermes/skills/harness/dispatch-phase/fixtures/handover/tasks.a8-routes.md",
        ".hermes/skills/harness/dispatch-phase/fixtures/handover/inventory.a8-routes.json",
        ".hermes/skills/harness/dispatch-phase/fixtures/handover/inventory.a8-uncovered-post.json",
        ".hermes/skills/harness/dispatch-phase/fixtures/handover/tasks.attempt-3-speckit.md",
        ".hermes/skills/harness/dispatch-phase/fixtures/handover/inventory.attempt-3.json",
        ".hermes/skills/analysis/inventory-entry-points/scripts/inventory-entry-points.py",
        ".hermes/skills/analysis/inventory-entry-points/SKILL.md",
    ".hermes/skills/harness/dispatch-phase/scripts/m3-attach-skills.py",
    ".hermes/skills/harness/dispatch-phase/scripts/assert-skills-not-disabled.py",
    ".hermes/skills/harness/dispatch-phase/scripts/mint-remediation-card.py",
    ".hermes/skills/harness/record-run-evidence/scripts/snapshot-run-audit.py",
    ".hermes/skills/harness/record-run-evidence/scripts/analyze-run-audit.py",
    ".hermes/skills/harness/record-run-evidence/scripts/snapshot-card-boundary.sh",
    ".hermes/skills/harness/record-run-evidence/references/run-audit.md",
    ".hermes/home/plugins/run-audit-boundary/plugin.yaml",
    ".hermes/home/plugins/run-audit-boundary/plugin.py",
    ".hermes/home/plugins/run-audit-boundary/__init__.py",
    ".hermes/home/scripts/enforce-m2b-created-cards-claim.py",
    # Architect E-20260811T170706Z Class A — quarantine survives dispatch
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-quarantine-tombstones.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/register-quarantine-tombstone.py",
    # EX-2: check-s008-resurrection-order.py retired (not in golden scaffold)
    # Architect E-20260811T173254Z Class A — residual worker kill+verify
    ".hermes/home/scripts/kill-and-verify-task-worker.sh",
    ".hermes/platform/known-hermes-behaviours.md",
    # Architect E-20260811T175305Z Class A — scope-filtered compile
    ".hermes/skills/harness/record-run-evidence/scripts/run-scoped-compile-gate.py",
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
    # EX-2: kanban-dispatch-guarded.sh retired (not in golden scaffold)
    # Architect E-20260811T195141Z Class A — own-body digest at complete
    ".hermes/skills/harness/record-run-evidence/scripts/check-body-digest-match.py",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    # Architect E-20260811T200911Z Class A — mint-completeness + park-at-birth
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-constraints-complete.py",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    # L2 / SR-13 — mint oracles (refs, task_id, discriminating exit)
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-oracles.py",
    # Architect E-20260811T203657Z Class A — dependency/pre-exists closure
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py",
    ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
    # EX-2: check-conversation-liveness.py retired (not in golden scaffold)
    # Operator E-20260812T061639Z / Architect E-20260812T061718Z Class A — card↔sidecar
    ".hermes/skills/harness/record-run-evidence/scripts/assert-card-body-digest-match.py",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    # Architect E-20260812T064611Z / E-20260812T064637Z Class A — AD-012 lint + CS-7 bundle
    ".hermes/skills/harness/validate-contracts/scripts/check-skill-conformance.py",
    ".hermes/skills/harness/validate-contracts/scripts/check-sr2-sentinel-root.py",
    ".hermes/skills/harness/validate-contracts/scripts/check-sr12-root-allowlist.py",
    ".hermes/skills/harness/validate-contracts/scripts/check-sr8-path-producers.py",
    ".hermes/skills/harness/validate-contracts/references/path-producers.json",
    ".hermes/skills/harness/dispatch-phase/scripts/read-phase-dispatch.py",
    ".hermes/skills/harness/enforce-authority-boundary/scripts/write-set-hook.py",
    ".hermes/skills/harness/enforce-authority-boundary/scripts/emit-write-set-cache.py",
    ".hermes/skills/harness/enforce-authority-boundary/scripts/hermes-spawn-hydrate.py",
    ".hermes/skills/harness/enforce-authority-boundary/scripts/prove-v24-env-fence.sh",
    ".hermes/skills/harness/enforce-authority-boundary/scripts/check-ack-authority.py",
    ".hermes/skills/harness/enforce-authority-boundary/references/ack-authority.md",
    ".hermes/skills/harness/dispatch-phase/scripts/resolve-seat-assignee.py",
    ".hermes/skills/harness/dispatch-phase/scripts/check-seat-assignee-profiles.py",
    ".hermes/skills/harness/dispatch-phase/references/assignee-profiles.json",
    ".hermes/skills/harness/enforce-authority-boundary/scripts/check-ex5-constraint-layers.py",
    ".hermes/skills/harness/enforce-authority-boundary/references/constraint-layers.json",
    ".hermes/skills/harness/dispatch-phase/scripts/read-link-graph.py",
    ".hermes/skills/harness/dispatch-phase/scripts/check-link-graph.py",
    ".hermes/skills/harness/dispatch-phase/fixtures/link-graph/child-with-parent.json",
    ".hermes/skills/harness/dispatch-phase/fixtures/link-graph/root-wrapped.json",
    ".hermes/skills/harness/dispatch-phase/scripts/assert-bundle-skills-exist.py",
    ".hermes/home/skill-bundles/m3-implementer.yaml",
    # Architect E-20260812T074514Z RW-2 BANK-DEST-INV-HARDINVOKE-1
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dest-inventory-hardinvoke.py",
    # EX-2: classify/arm-conv-live/check-stream-liveness retired (not in golden scaffold)
    # A2 — watchdog + fast-deny (KEEP)
    ".hermes/home/scripts/kanban-stuck-watchdog.py",
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
        "doctrine pending R-SKILL-F",
        "MapStruct CDI doctrine pending R-SKILL-F (B-3)",
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
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "enforcement/ must not exist",
        "EX-3 enforcement category dissolved",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "check-sr2-sentinel-root.py",
        "SR-2 sentinel-root lint is in the validate suite",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "write-set hook refuses in-repo OOS",
        "EX-3 write-set hook both-directions probe",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "C-2(a) M3 cards resolve to assignee default",
        "C-2(a) single-persona assignee",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "EX-5 constraint layers",
        "EX-5 layers 1-3 overlays",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "BV19-3 link graph",
        "BV19-3 link graph is the phase DAG",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "hermeticity refuses scaffold tmp/",
        "LG4 scaffold attic must not ship",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "hermeticity refuses authoring ledger",
        "LG3 reintroduced authoring ledger must BLOCK",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "SR-12 refuses root tmp/",
        "SR-12 allow-list sees directories (LG5)",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "SR-8 refuses retired migration/",
        "SR-8 path-provenance lint (SR-8a)",
    ),
    (
        ".hermes/skills/analysis/scan-with-mta/scripts/mta-analyze-legacy.sh",
        "${ROOT}/evidence/mta",
        "SR-8a MTA output under evidence/ (not retired migration/)",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "no eval of phase-dispatch parser",
        "LG7 eval of YAML parser retired",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "read-phase-dispatch.py",
        "LG7 dispatch reads phase-dispatch as JSON",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "read-phase-dispatch.py",
        "LG7 mint Procedure reads phase-dispatch as JSON",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assignee=default",
        "C-2(a) mint Procedure uses assignee default",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/check-skill-conformance.py",
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
        "T-8 skill attached on M3",
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
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "check-pom-jacoco-wiring.py",
        "A-3 Jacoco wiring gate in validate-contracts",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "assert-extension-tooling.py",
        "W3 extension tooling typed preflight",
    ),
    (
        ".hermes/skills/migration/bootstrap-quarkus-project/SKILL.md",
        "Author",
        "bootstrap skill documents POM authoring (DD1/DD2)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "check-create-path-tip-sync.py",
        "R0 wired into mint Procedure",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-quarantine-tombstones.py",
        "C1 pre-create gates are repo-relative paths (173010Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md",
        "Pre-v12 R5 hard-invoke traps",
        "R5 M3 hard-invoke cites",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "check-create-path-tip-sync.py",
        "R0 wired into dispatch-phase",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "REFUSE M2a/M2b",
        "R1/GR2 refuse retired M2a/M2b",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
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
        ".hermes/skills/harness/dispatch-phase/scripts/check-phase-body-script-refs.py",
        "BODY_SCRIPT_LINT",
        "R0 body-script lint present",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "HERMES_SKILL_DIR:-.hermes/home/skills/software-development/scan-with-mta",
        "M1/M2 findings-handoff uses canonical scan-with-mta path",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "skills.disabled",
        "path-invoke harness packs hidden from skills_list (125528Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/delivery-path.md",
        "factory inlines dest",
        "DEFAULT_EXTENSIONS delivery path is RHDH skeleton + factory create",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/check-phase-body-script-refs.py",
        "software-development",
        "R0 lint accepts runtime software-development root",
    ),
    (
        ".hermes/skills/analysis/scan-with-mta/scripts/check-findings-handoff.py",
        "2 = missing script",
        "gate exit semantics typed (Deputy E-113300Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/check-phase-input-manifest.py",
        "phase input manifests",
        "R0 input-manifest lint present (Operator E-113700Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "Input manifest",
        "M2 input manifests (Operator E-113700Z / GR2)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "check-phase-input-manifest.py",
        "input-manifest wired into dispatch-phase",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "REVIEW_ADHERE_OBSERVE=",
        "dispatch emits Review adhere-observe Need (Operator E-114300Z)",
    ),

    (
        ".hermes/phase-dispatch.yaml",
        "speckit-specify",
        "M2 attaches speckit-specify (Architect E-115316Z / GR2)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "Spec Kit invoke-or-BLOCK",
        "M2 Spec Kit invoke-or-needs_input (Architect E-115316Z / GR2)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/check-completion-na-reject.py",
        "COMPLETION_NA",
        "completion consumer N/A reject (Operator E-120200Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "verify-or-BLOCK",
        "M2 step0 verify-or-BLOCK (Architect E-121308Z provision-owns-tools)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "check-specify-preseed.py",
        "M2 dispatch wires Spec Kit preseed R0",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
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
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "Per-artifact Spec Kit resume ladder",
        "M2 per-artifact resume ladder (Operator E-122500Z / GR2)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "check-decision-complete-cards.py",
        "decision-complete lint wired into dispatch",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/check-decision-complete-cards.py",
        "jump to /speckit-tasks",
        "decision-complete lint forbids jump-over-plan",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/check-operand-count.py",
        "build_config",
        "operand_class build_config (Operator E-124000Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "check-kanban-body.py --body",
        "mint Procedure validates each body (Operator E-124000Z)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
        "operand_class",
        "story-sizing documents operand classes",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "--initial-status blocked",
        "M3 born parked (Deputy E-131900Z serial breach)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "Do NOT dispatch here",
        "mint Procedure must not auto-dispatch (Deputy E-131900Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "--parent REQUIRED",
        "mint Procedure requires --parent (Operator E-133000Z #5)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "created-by",
        "mint Procedure created_by=holder for card-claim (Operator E-133000Z #5)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/check-created-cards-claim.py",
        "CREATED_CARDS_REJECT",
        "empty created_cards rejected when derived nonempty",
    ),
    (
        ".hermes/home/scripts/block-and-signal-worker.sh",
        "SIGTERM",
        "block-and-signal-worker (Operator E-133000Z #2)",
    ),
    # V1 (E-20260814T074759Z): assert property chain, not a bare script-name
    # inside dispatch-phase.sh. GR2: claim check lives on mint Procedure.
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-m2b-created-cards-claim.sh",
        "mint Procedure wires created_cards claim check (GR2 holder mint)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "wave-holder worker",
        "GR2/AD-016 M3 mint is holder-session kanban_create",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "PARENT_DONE",
        "mint Procedure fail-closed when park-at-birth parent is already done",
    ),

    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "Immediately after each `kanban_create`",
        "run-audit create snapshot is after kanban_create not pre-create (182330Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "snapshot-card-boundary.sh create",
        "mint Procedure snapshots run-audit after each kanban_create (no Hermes create hook)",
    ),
    (
        ".hermes/skills/harness/record-run-evidence/scripts/analyze-run-audit.py",
        "migration.yaml",
        "run-audit include-gate covers dest files this seat has before src/",
    ),
    (
        ".hermes/skills/harness/record-run-evidence/scripts/analyze-run-audit.py",
        "--baseline",
        "run-audit analyzer accepts t0 baseline so provision files are not scored",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/assert-m2b-created-cards-claim.sh",
        "check-created-cards-claim.py",
        "M2 claim wrapper invokes check-created-cards-claim.py",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/assert-m2b-created-cards-claim.sh",
        "m2b-created-cards-ok.json",
        "M2 claim wrapper stamps m2b-created-cards-ok.json receipt",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/assert-m2b-created-cards-claim.sh",
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
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-quarantine-tombstones.py",
        "Class A quarantine tombstones at create (Architect E-170706Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
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
        ".hermes/skills/sdd/check-spec-readiness/scripts/specimen_agnostic.py",
        "intra_package_maps",
        "leaf maps beside path_rewrites (Architect E-20260818T180200Z)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
        "intra_package_maps",
        "deriver applies leaf maps (Architect E-20260818T180200Z)",
    ),
    (
        "migration.yaml",
        "intra_package_maps:",
        "golden declares empty leaf maps (Architect E-20260818T180200Z)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py",
        "allow-specimen-fixture",
        "coverage gate fixture-gated (Operator E-150800Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "scratch-assemble-mint.py",
        "M2 Done is scratch --write assembly (221200Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/scratch-assemble-mint.py",
        "assert-polish-excludes",
        "ownership strips dual-named polish path (203811Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m2-planner.md",
        "scratch-assemble-mint.py",
        "m2-planner scratch-assembly Done oracle (221200Z)",
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
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "stamp-body-dependencies.py",
        "mint Procedure wires dependencies stamp",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "stamp-destination-inventory.py",
        "mint Procedure wires destination-inventory stamp",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-complete-exit-criteria.py",
        "Class A complete-cmd assert before kanban_complete",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md",
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
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "check-interface-closure.py",
        "Class A interface-closure wired into mint Procedure",
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
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-constraints-preserved.py",
        "F9 mint Procedure wires constraints snapshot-before",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
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
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "Architect E-20260811T205329Z Class A",
        "Class A Managed Scope pin in dispatch-phase",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "DISPATCH_START_DAEMON",
        "v20-flow does not spawn kanban daemon --force from dispatch-phase",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "SPECIFY_FEATURE_DIRECTORY",
        "M2 write-set is .specify/ + specs/; no SPECIFY_FEATURE_DIRECTORY dodge",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/write-set-hook.py",
        "A published empty list",
        "published [] denies specs/ and every dest path (invert a158ef06)",
    ),
    (
        ".hermes/home/scripts/kanban-stuck-watchdog.py",
        "STILLBORN",
        "null-heartbeat stillborn watchdog",
    ),
    (
        ".hermes/skills/harness/record-run-evidence/scripts/check-body-digest-match.py",
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
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "PARK_AT_BIRTH",
        "Class A park-at-birth verify after create",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
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
        ".hermes/skills/harness/record-run-evidence/scripts/assert-card-body-digest-match.py",
        "card↔sidecar digest mismatch",
        "Class A card↔sidecar digest cross-assert script",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
        "card↔sidecar",
        "card-sidecar-digest-cross-assert contract",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-card-body-digest-match.py",
        "Class A card↔sidecar assert wired into mint Procedure ack path",
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
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-dependency-closure.py",
        "Class A dependency-closure wired into mint Procedure",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dest-inventory-hardinvoke.py",
        "DEST_INV_HARDINVOKE",
        "RW-2 dest-inventory hard-invoke lint",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md",
        "BANK-DEST-INV-HARDINVOKE-1",
        "dest-inventory-hardinvoke standing cite",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "BANK-DEST-INV-HARDINVOKE-1",
        "RW-2 dest-inventory cite obligation on mint Procedure",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md",
        "BANK-DEST-INV-HARDINVOKE-1",
        "F6 standing procedure carries BANK-DEST-INV detail",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "m3-implementer-standing.md",
        "F6 card points at standing procedure (≤1500 chars)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
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
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-bundle-skills-exist.py",
        "RW-3 CS-7 bundle exists-assert wired into mint Procedure",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/apply-write-fence.sh",
        ".hermes/skills/harness",
        "A-1 FS-RO write-fence locks .hermes/skills/harness (DD5)",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/check-ack-authority.py",
        "block mappings",
        "AR-1.1 ack YAML parser accepts block-mapping artifact_digests",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/references/ack-authority.md",
        "artifact_digests",
        "AR-1.1 ack schema lives in the skill, not retired governance/",
    ),
    (
        "evidence/acks/README.md",
        "task_id:",
        "acks README example carries task_id (AR-1.1)",
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
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "identity.story_id required",
        "D3 story id persisted on M3 card (Operator E-180236Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "created-story-cards.json",
        "D3 story↔card map stamped at create",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-mint-oracles.py",
        "L2 mint oracles wired into mint Procedure (SR-13)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
        "SR-13",
        "SR-13 discriminating-exit in story scope/exit",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/check-create-path-tip-sync.py",
        "SR-14 untracked (not in git index)",
        "SR-14 check is wired into tip-sync",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/pre-commit-index-suite.sh",
        "git checkout-index -a --prefix=",
        "LG9a index snapshot pre-commit",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
        "exactly one owner",
        "V19-8 file-granular ownership after grouping",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
        "Live HTTP acceptance belongs to M4/M5",
        "A-3c.1 reversal: HTTP is a @QuarkusTest, not curl",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
        "M2 partition shape",
        "A-6 stamper accepts {legacy, dest} scope",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/scripts/init-workspace.sh",
        "assets/constitution.md",
        "V20-3 constitution overlay at provision",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/stop-before-implement.overlay.yml",
        "remove: implement",
        "A-1 speckit overlay removes implement",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/stop-before-implement.overlay.yml",
        "remove: review-spec",
        "A-1 overlay removes type:gate review-spec (unattended)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/stop-before-implement.overlay.yml",
        "evidence/findings-handoff.json",
        "A-3 specify args name M1 findings-handoff",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/stop-before-implement.overlay.yml",
        "one user story per inventory HTTP shape",
        "speckit.tasks overlay restates HTTP-shape unique-owner (120010Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "one creator phase per dest path",
        "tasks-template unique-owner emit pin (075500Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "one user story per inventory HTTP shape",
        "tasks-template HTTP-shape unique-owner pin (120010Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        '@Path("',
        "tasks-template @Path emit pin (200540Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "never a path prefix in a task line",
        "tasks-template repo-relative path pin (131510Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "CLASS-LEVEL ABSOLUTE",
        "tasks-template class-level @Path pin (133010Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "creates a Resource class",
        "tasks-template @Path MUST scoped to class-creating tasks (140510Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "already carries the class-level path",
        "tasks-template T022 foreign @Path in prose (135010Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "only inside the story phase that owns",
        "tasks-template @Path owning-story-phase pin (135010Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/stop-before-implement.overlay.yml",
        "CLASS-LEVEL ABSOLUTE",
        "speckit.tasks overlay restates class-level @Path (133010Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/stop-before-implement.overlay.yml",
        "never prefix /projects/modernized",
        "speckit.tasks overlay restates repo-relative paths (131510Z)",
    ),
    (
        ".hermes/pins.json",
        '"version": "v0.20.4"',
        "seat Hermes pin v0.20.4 (111730Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m1-verifier.md",
        "refuse-on-nonzero",
        "M1 verifier refuse-on-nonzero (095340Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "assert-skills-not-disabled.py",
        "B3 wired into dispatch-phase create (25a7c1e9)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "assert-seat-hermes-pin.py",
        "live dispatch asserts seat Hermes pin (111730Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "check-m1-verifier.py",
        "M1 body points verifier card at check-m1-verifier.py",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/spec-template.md",
        "enumerate every inventory http_path",
        "spec-template inventory-enumerate pin (203500Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/spec-template.md",
        "one user story per inventory HTTP shape",
        "spec-template HTTP-shape unique-owner restatement (120010Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/SKILL.md",
        "Fail-closed kind map",
        "dispatch-phase fail-closed kind map at top (094840Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/SKILL.md",
        "--skill one-three-one-rule",
        "holder create pins official one-three-one-rule (094840Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "Fail-closed kind map",
        "mint Procedure fail-closed kind map (094316Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "one-three-one-rule",
        "mint Procedure holder skill pin (094840Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "the park protection",
        "mint Procedure initial_status is not the park protection (113650Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/holder-card-body.md",
        "Fail-closed kind map",
        "holder card body carries fail-closed kind map (094840Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/holder-card-body.md",
        "needs_input",
        "holder body maps A-8 / dest-forbidden rewrite to needs_input (3a0b92b6)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "Read inventory before specify",
        "M2 job reads inventory before speckit-specify (203500Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m2-planner.md",
        "Read `evidence/entry-point-inventory.json`",
        "m2-planner names inventory-before-specify (203500Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/scripts/init-workspace.sh",
        "overrides/tasks-template.md",
        "provision installs unique-owner tasks override",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "hermes kanban dispatch --max 1",
        "serial GO is native dispatch --max 1 not chat -q",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/native-dispatch.md",
        "hermes kanban dispatch --max 1",
        "native-dispatch standing doc names GO (not a wrapper script)",
    ),
    (
        ".hermes/skills/harness/record-run-evidence/scripts/snapshot-run-audit.py",
        "attach_write_sets",
        "run-audit joins published write-sets; session --windows-json retired",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "specify workflow resolve speckit (no implement; no gates; clarify)",
        "A-1 overlay resolve is in validate-contracts",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/scripts/init-workspace.sh",
        "overlays/speckit/stop-before-implement.yml",
        "provision installs speckit overlay not Path-A workflow",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-oracles.py",
        "pre-story tree",
        "L2 discriminating-exit evaluates dest minus write-set",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "L2a unrelated remaining test does not satisfy SR-13",
        "L2a per-story proving test (Deputy E-20260815T014500Z)",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "script card exit refused",
        "A-3c.1 reversal: curl/scripts are not card exits",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/specimen_agnostic.py",
        "B-1: a file with methods but no executable test fails the card",
        "B-1 proves must be an executable @Test",
    ),
    (
        ".hermes/skills/gates/check-domain-parity/scripts/lib/verdict.py",
        "INCONCLUSIVE_FIXTURE",
        "B-5 fixture ACCEPT cannot close product gates",
    ),
    (
        ".hermes/skills/analysis/scan-with-mta/scripts/assert-mta-rescan.py",
        "handoff presence is not a rescan",
        "WC-5 mta_rescan proves analyzer ran",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "FILE_OVERLAP (cross-phase artifact disjointness)",
        "A-5 is in-flight; mint FILE_OVERLAP dropped while serial (131858Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "DEPENDENCIES_MISSING",
        "A-4 parents transcribed from Dependencies; missing section refuses",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "--ensure-wave-holder",
        "HKN-2 look-ahead: mint under a still-open wave-holder, not a done M2",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "per-story native speckit",
        "A-4 transcribes native per-story User Story bullets",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "PATH_A_PARTITION",
        "A-6 Path-A authored partition.json is not handover input",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "KIND_PHASE",
        "Phase-N structural mint uses heading number, not title prose",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "015216Z",
        "A-8 amend inherits earlier file @Path; methods from the amend body",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "endpoints_uncovered",
        "A-8 endpoint coverage vs M1 inventory is fail-closed",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "http_path",
        "A-8 mint joins on transcribed http_path, not RestController filename",
    ),
    (
        ".hermes/skills/analysis/inventory-entry-points/scripts/inventory-entry-points.py",
        "http_method",
        "A-8 scanner emits structured http_method",
    ),
    (
        ".hermes/skills/analysis/inventory-entry-points/SKILL.md",
        "http_path",
        "A-8 inventory procedure documents http_path",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/handover-mint.md",
        "E-20260816T193813Z",
        "A-8 mint contract is route/symbol join, not a filename mapper",
    ),

    (
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
        "pom owner unique",
        "A-5 pom.xml has exactly one writer",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "OBJECT Option B",
        "B-6 story park is incomplete ack_gate parent, not sticky-block",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/m3-attach-skills.py",
        "operand_skills",
        "B-16 attach from identity.operand_skills",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/mint-remediation-card.py",
        "leave-triage",
        "C-3(a) remediation forbids leave-triage",
    ),
    (
        ".hermes/skills/harness/record-run-evidence/scripts/analyze-run-audit.py",
        "INTERVENTION",
        "Phase 5 run-audit out-of-window edit is INTERVENTION",
    ),
    (
        ".hermes/pins.json",
        '"status": "unpinned"',
        "B-3 MapStruct GAV unpinned pending R-SKILL-F",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "A-4/A-5/A-8 handover-mint",
        "handover-mint dry-run is in validate-contracts",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "check-body-digest-match.py --expect",
        "card body contract AR-4.3 --expect REFUSE (035010Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "skills = full m3-attach-skills.py stdout",
        "card body contract B-16 no-drop attach stdout (035010Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "evidence/bodies/m3-",
        "card body contract typed-body path on kanban markdown (035010Z)",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "Card body contract on mint Procedure",
        "validate-contracts pins mint card body contract (035010Z)",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/write-set-hook.py",
        "task-set-unresolved",
        "v24 fence DENIES when TASK set and FILES_WRITABLE unset",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/write-set-hook.py",
        "must not read dest JSON",
        "v24 dest write-set JSON is cache not policy",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/emit-write-set-cache.py",
        "cache-not-policy",
        "mint still emits write-set cache (Architect 35099226)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "emit-write-set-cache.py",
        "M3 mint emits write-set cache after kanban_create",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/write-set-hook.py",
        "defense-in-depth, not a trust boundary",
        "terminal matcher is defense-in-depth not hole-1/2 fix",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md",
        "HERMES_KANBAN_FILES_WRITABLE",
        "M3 standing fence names spawn-env FILES_WRITABLE (144100Z card/yaml fallback)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/SKILL.md",
        "Do **not** pin `dispatch-phase`",
        "I-10 B holder create must not pin dispatch-phase (25a7c1e9)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/holder-card-body.md",
        "Do **not** declare `dispatch-phase`",
        "I-10 B holder body path-invokes mint Procedure (25a7c1e9)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "Do **not** pin `dispatch-phase`",
        "I-10 B mint Procedure holder skill pin (25a7c1e9)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-skills-not-disabled.py",
        "B3 create-time declared-vs-disabled refuse (25a7c1e9)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "mirror the legacy sub-package",
        "F1 destination sub-packages mirror legacy (25a7c1e9)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "intra_package_maps",
        "F option 2 deriver maps named in tasks-template (180200Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "NAMES a dest file must CREATE it",
        "I-16 polish task naming a file must Create it (215010Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/stop-before-implement.overlay.yml",
        "NAMES a dest file must CREATE it",
        "I-16 speckit.tasks overlay restates polish Create (215010Z)",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/write-set-hook.py",
        "phase-yaml:",
        "B2 fence falls back to phase yaml when card unpublished",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "do NOT publish files_writable here",
        "B2 M3 omits phase files_writable (card-resolved)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        '"M2")',
        "B2 guard labels quoted so extract_body skips them (184010Z)",
    ),
]

FORBIDDEN_SUBSTRINGS = [
    (
        ".hermes/skills/harness/dispatch-phase/SKILL.md",
        "--skill dispatch-phase",
        "I-10 B holder create argv must not pass --skill dispatch-phase",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "Verify quality gate",
        "I-16 polish sample must not Verify pom.xml (215010Z)",
    ),
]


def _git_index_status(root: Path, rel: str) -> str:
    """Return 'idle', 'tracked', or 'untracked' for SR-14."""
    probe = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return "idle"
    ls = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--error-unmatch", "-z", "--", rel],
        capture_output=True,
        text=True,
    )
    return "tracked" if ls.returncode == 0 else "untracked"


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    bad = 0
    sr14_idle = False
    sr14_untracked = 0
    sr14_checked = 0
    for rel in REQUIRED_FILES:
        path = root / rel
        if not path.is_file():
            print(f"FAIL: missing {rel}", file=sys.stderr)
            bad = 1
            continue
        print(f"OK: {rel}")
        st = _git_index_status(root, rel)
        if st == "idle":
            sr14_idle = True
        elif st == "tracked":
            sr14_checked += 1
        else:
            print(f"FAIL: SR-14 untracked (not in git index): {rel}", file=sys.stderr)
            bad = 1
            sr14_untracked += 1
            sr14_checked += 1
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
    for rel, needle, label in FORBIDDEN_SUBSTRINGS:
        path = root / rel
        if not path.is_file():
            print(f"FAIL: {label}: missing {rel}", file=sys.stderr)
            bad = 1
            continue
        text = path.read_text(encoding="utf-8")
        if needle in text:
            print(f"FAIL: {label}: {rel} still has {needle!r}", file=sys.stderr)
            bad = 1
        else:
            print(f"OK: {label}")
    if sr14_untracked:
        print("FAIL: SR-14 required files missing from git index", file=sys.stderr)
    elif sr14_idle:
        print("OK: SR-14 idle (not a git work tree)")
    elif sr14_checked:
        print("OK: SR-14 required files are git-tracked")
    if bad:
        print("FAIL: create-path tip sync (R0/R3)", file=sys.stderr)
        return 1
    print("OK: create-path tip sync (R0/R3)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
