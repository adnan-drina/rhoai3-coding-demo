#!/usr/bin/env python3
"""R0/R3 — create-path tip sync proof (pre-v12 Architect E-20260811T102405Z).

Fail-closed if Hermes skill tree / M4 floor / measured-trap refs are missing.
"""
from __future__ import annotations

import re
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
    ".hermes/skills/harness/dispatch-phase/scripts/assert-m3-child-skills.py",
    ".hermes/skills/harness/dispatch-phase/scripts/holder-checkpoint.py",
    ".hermes/skills/harness/dispatch-phase/scripts/stamp-harness-rev.py",
    ".hermes/skills/harness/dispatch-phase/scripts/assert-autostart-gates.py",
    ".hermes/skills/harness/dispatch-phase/scripts/autostart-migration.sh",
    ".hermes/skills/harness/dispatch-phase/references/autostart-migration.md",
    ".hermes/skills/harness/dispatch-phase/scripts/run-pre-create-gates.py",
    ".hermes/skills/harness/dispatch-phase/scripts/compose-m3-card-markdown.py",
    ".hermes/skills/harness/dispatch-phase/scripts/assert-story-parked.py",
    ".hermes/skills/harness/dispatch-phase/references/m1-verifier.md",
    ".hermes/skills/harness/dispatch-phase/scripts/check-m1-verifier.py",
    ".hermes/skills/harness/enforce-authority-boundary/scripts/issue-m1-findings-ack.py",
    ".hermes/skills/harness/enforce-authority-boundary/scripts/issue-m3-brief-identity-ack.py",
    ".hermes/skills/harness/dispatch-phase/scripts/assert-seat-hermes-pin.py",
    ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
    ".hermes/skills/harness/dispatch-phase/scripts/scratch-assemble-mint.py",
    ".hermes/skills/harness/dispatch-phase/scripts/assert-partition-invented-routes.py",
    ".hermes/skills/harness/dispatch-phase/scripts/assert-compiled-route-fidelity.py",
    ".hermes/skills/gates/check-release-readiness/scripts/evaluate-exit-criteria.py",
    ".hermes/home/scripts/supervise-gateway.sh",
    ".hermes/skills/analysis/scan-with-mta/scripts/assert-ensure-cli-path.sh",
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
        ".hermes/skills/analysis/inventory-entry-points/scripts/inventory-type-graph.py",
        ".hermes/skills/sdd/check-spec-readiness/scripts/type_graph.py",
        ".hermes/skills/sdd/check-spec-readiness/scripts/generated_sources.py",
        ".hermes/skills/analysis/inventory-entry-points/SKILL.md",
    ".hermes/skills/harness/dispatch-phase/scripts/m3-attach-skills.py",
    ".hermes/skills/harness/dispatch-phase/scripts/check-phase-attach-matrix.py",
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
    ".hermes/skills/harness/record-run-evidence/scripts/restamp-card-and-sidecar.py",
    ".hermes/skills/harness/record-run-evidence/scripts/stamp-body-digest.py",
    ".hermes/skills/harness/dispatch-phase/scripts/resolve-story-parent-ids.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dest-generator-configured.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dest-pom-extensions.py",
    ".hermes/skills/analysis/scan-with-mta/scripts/emit-required-extensions.py",
    ".hermes/skills/migration/manage-quarkus-extensions/scripts/spring_dep_map.py",
    ".hermes/skills/migration/manage-quarkus-extensions/references/spring-dep-to-extension.md",
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-partition-topological-order.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/relocate-descendant-import-writesets.py",
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-setup-datasource-driver.py",
    ".hermes/skills/migration/reference-rh-quarkus-pom/scripts/verify-maven-settings.py",
    ".mvn/settings.xml",
    ".mvn/maven.config",
    ".hermes/skills/sdd/check-spec-readiness/scripts/assert-tasks-generator-uptake.py",
    ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
    # Architect E-20260812T064611Z / E-20260812T064637Z Class A — AD-012 lint + CS-7 bundle
    ".hermes/skills/harness/validate-contracts/scripts/check-skill-conformance.py",
    ".hermes/skills/harness/validate-contracts/references/r-sk4-line-exceptions.txt",
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
        ".hermes/home/scripts/stop-worker-session.sh",
        "refuse self-stop",
        "A-5 wrapper refuses worker self-SIGTERM (v32 t_adbb6995)",
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
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "DISPATCH_PARK_CHAIN",
        "M1 create parks M2 + M3 holder (Architect 102636Z / 100812Z)",
    ),
    (
        "devfile.yaml",
        "/etc/config/devspace-ai-tools-init",
        "postStart prefers ConfigMap volume over kube-API curl",
    ),
    (
        "devfile.yaml",
        "/projects/.platform/poststart.log",
        "postStart tees to PVC (survives FailedPostStartHook)",
    ),
    (
        "devfile.yaml",
        "supervise-gateway.sh",
        "postStart ensures hermes gateway run supervisor",
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
        "--initial-status todo",
        "V35-CREATE-STATUS stories todo; sticky-block only ack_gate",
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
        ".hermes/skills/harness/dispatch-phase/scripts/scratch-assemble-mint.py",
        "Never discover a tasks.md inside the harness tree",
        "scratch oracle ignores dest-shipped fixture tasks.md",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m2-planner.md",
        "python3 .hermes/skills/harness/dispatch-phase/scripts/scratch-assemble-mint.py",
        "m2-planner names interpreter+path for scratch-assembly Done oracle (124443Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/scratch-assemble-mint.py",
        "assert-partition-invented-routes.py",
        "M2 reverse-diff sibling after scratch --write (067420Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/assert-compiled-route-fidelity.py",
        "R-OF.1",
        "compiled-tree route fidelity dest-local (5724ea24 KEEP)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/native-dispatch.md",
        "dispatch_in_gateway: true",
        "gateway-embedded dispatcher not kanban daemon (066500Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/native-dispatch.md",
        "hermes kanban gc",
        "native gc/repair not a harness reaper (063049Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/constitution.md",
        "The legacy HTTP contract is immutable",
        "constitution VII legacy HTTP immutable (067050Z)",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/constitution.md",
        "not a gate",
        "constitution VII is guidance not a gate (070430Z)",
    ),
    (
        ".hermes/skills/migration/spring-to-quarkus-patterns/references/testing.md",
        "Do **not** use `java.net.http.HttpClient`",
        "M3 HTTP tests are RestAssured not URI.resolve (064940Z)",
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
        "card↔sidecar↔file digest mismatch",
        "Class A card↔sidecar↔file digest triple",
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
        "evidence/required-extensions.json",
        "V35-EXTENSIONS speckit overlay names required-extensions.json",
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
        ".hermes/skills/harness/enforce-authority-boundary/scripts/issue-m1-findings-ack.py",
        "gate:check-findings-handoff",
        "5.1 auto-issues m1-findings as gate-record (121859Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "issue-m1-findings-ack.py",
        "M1/M2 bodies path-invoke 5.1 issuer",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/check-ack-authority.py",
        "ALLOWED_GATE_SIGNERS",
        "AR-1.1 allowlists 5.1 gate signer",
    ),
    (
        "evidence/acks/README.md",
        "gate:check-findings-handoff",
        "acks README documents 5.1 gate-record",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/specimen_agnostic.py",
        "if not has_rest and has_test:",
        "test-only stamps test_suite_runs; rest+test keeps http_semantics (155354Z / V35-ORACLE-REST)",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: polish test-only stamps test_suite_runs",
        "stamp_oracles polish vs rest+test lock (155515Z)",
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
        ".hermes/skills/harness/dispatch-phase/scripts/assert-seat-hermes-pin.py",
        '["hermes", "--version"]',
        "seat Hermes pin probe is binary-local --version not version subcommand (v37)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/holder-card-body.md",
        ".hermes/skills/harness/enforce-authority-boundary/scripts/issue-m3-brief-identity-ack.py",
        "holder issues M3 gate-record via full issuer path (v38 body-script lint)",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: phase body script refs (live; dest create runs this)",
        "validate.sh runs live R0 body-script lint (v38 dest-cite)",
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
        "Do **not** pin `one-three-one-rule`",
        "holder create must not pin one-three-one-rule (I-11)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "Fail-closed kind map",
        "mint Procedure fail-closed kind map (094316Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "Do **not** pin `one-three-one-rule`",
        "mint Procedure holder does not skill-pin one-three-one-rule (I-11)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-complete-exit-criteria.py . --body evidence/bodies/m3-{story_id}.json",
        "pre-complete reads HERMES_KANBAN_TASK; no {id} placeholder",
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
        "Do **not** invoke `stop-worker-session.sh`",
        "holder must not self-SIGTERM on imagined OOB (v32 t_adbb6995)",
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
        ".hermes/skills/harness/dispatch-phase/references/native-dispatch.md",
        "REQUIRED same-turn watch",
        "watch official kanban log after spawn",
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
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "def merge_import_parents",
        "F-6 parents from import graph not Dependencies prose alone",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "CYCLE_IMPORT",
        "H-5 cyclic import is a named refuse not a silent skip",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "def assert_foundational_no_service",
        "H-6 T0 #3 *Service.java is not foundational write-set",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/holder-checkpoint.py",
        "init does not take --next",
        "H-2 init is not stamp --next",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/write-set-hook.py",
        "/dev/null",
        "H-3 device redirects are not dest writes",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/generated_sources.py",
        "def iter_dest_build_files",
        "H-1 GENERATOR_INPUTS dest-only build files",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py",
        "dest_only=True",
        "H-1 closure does not inherit legacy-at-3 generator specs",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "PATH_TOKEN extracted 0 pom.xml owners",
        "F-1/F-5 zero pom writer names tasks.md PATH_TOKEN surface",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "spec-kit has no create/amend distinction",
        "F-1 AMEND_EXISTING no longer skips path extraction",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/scratch-assemble-mint.py",
        "assert-partition-topological-order.py",
        "M2 scratch exit wires existing topological gate",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "assert-partition-topological-order.py",
        "M2 body cites topological gate after scratch --write",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m2-planner.md",
        "assert-partition-topological-order.py",
        "m2-planner names topological gate as M2 exit",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/specimen_agnostic.py",
        "Surface=typed bodies files_writable (writes_pom_xml)",
        "F-5 stamp_dd3 zero/multi writer names the body surface",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/assert-m3-child-skills.py",
        "filter_attach_skills_for_write_set",
        "F-3 child-skills gate asks write-set need not producer stdout",
    ),
    (
        ".hermes/skills/migration/manage-quarkus-extensions/scripts/spring_dep_map.py",
        "spring.profiles.active",
        "F-4 jdbc keys follow active profile not rglob order",
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
        ".hermes/skills/harness/dispatch-phase/references/handover-mint.md",
        "test_suite_runs",
        "oracle-stamps polish test-only (155354Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/handover-mint.md",
        "split the facade per aggregate",
        "LV-7a handover-mint.md names split-per-aggregate for T0_3_SERVICE",
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
        ".hermes/skills/harness/dispatch-phase/scripts/m3-attach-skills.py",
        "not in yaml M3.skills",
        "attach fail-closed vs yaml pool (50c3e13c)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/specimen_agnostic.py",
        "filter_attach_skills_for_write_set",
        "pom skills attach only on the pom.xml writer (113519Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/check-phase-attach-matrix.py",
        "OPERAND_CLASS_SKILLS",
        "M3 yaml pool is recommender vocab not a second five-name list (50c3e13c)",
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
        "do not subset attach stdout to yaml",
        "yaml is pool superset not a create filter (50c3e13c)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "REFUSE before kanban_create",
        "attach/pool mismatch is pre-create not a dead card (50c3e13c)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "Pom skills attach only when pom.xml is in",
        "foundational must not inherit setup pom skills (113519Z)",
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
        "card:kanban.db.body",
        "I-5 fence falls back to kanban.db card markdown when spawn env unset",
    ),
    (
        ".hermes/skills/harness/ground-in-harvest/scripts/check-citation.py",
        "identity.story_id",
        "AR-4.3 complete-path citation accepts assembler story slug",
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
        ".hermes/skills/harness/dispatch-phase/scripts/assert-m3-child-skills.py",
        "bare create OBJECT",
        "pre-create/pre-complete refuse empty skills (132404Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/holder-checkpoint.py",
        "rhoai3.m3-holder-checkpoint/v1",
        "M3 holder checkpoint schema (132404Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-m3-child-skills.py",
        "mint Procedure wires empty-skills refuse after create and before complete",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/holder-card-body.md",
        "holder-checkpoint.py init",
        "holder body inits procedure checkpoint before lint",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/SKILL.md",
        "do not Enable it",
        "skill_view Enable dispatch-phase is OBJECT; path-invoke Procedure",
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
    (
        ".hermes/skills/harness/dispatch-phase/references/holder-card-body.md",
        "You mint story children",
        "holder identity: mint not implement (102636Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md",
        "Wrong-card gate",
        "implementer standing fail-closes missing typed body",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "M3 WAVE HOLDER",
        "park-at-birth M3 title is wave holder not bounded transform",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "holder-card-body.md",
        "park-at-birth M3 body is holder-card-body.md (handover-mint never names the card)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "no implementer skill pin",
        "M3 case clears SKILLS after yaml load (f5bfdb74 consumer, not yaml)",
    ),
    (
        ".hermes/phase-dispatch.yaml",
        "M3 skills[] is the allow-list pool (B-16)",
        "do not empty yaml M3.skills to zero holder pins (f5bfdb74 trap)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "writeset_not_subset",
        "mint Procedure fail-closes body write-set extras vs partition",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py",
        "writeset_not_subset",
        "coverage gate names writeset_not_subset (E-20260819T104254Z)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
        "WRITESET_NOT_SUBSET",
        "dependency stamp refuses extras outside partition frame",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
        "inheritance-reachable dest twins onto partition",
        "V34-5 stamp assigns inheritance-reachable types onto partition",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
        "Do not stamp unowned collaborators as",
        "V34-5 AMEND: unowned import dest twins are not pre-exists",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: stamp assigns inheritance-reachable supers onto partition",
        "V34-5 validate lock: partition owns inheritance closure",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: stamp assigns import-reachable dest twins onto partition",
        "V34-5 AMEND validate lock: partition owns import closure",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "evidence/type-inventory.json",
        "type-inventory dest twins on the owning story",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "configure the dest generator",
        "generated types carry spec + configure generator",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
        'deps[dest] = "generated"',
        "stamp classifies generator output as provider generated",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py",
        "GENERATOR_INPUTS",
        "closure requires generator spec + build owned",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/generated_sources.py",
        "target/generated-sources",
        "generated detection is path/plugin/@Generated, not a name pattern",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/stop-before-implement.overlay.yml",
        "evidence/type-inventory.json",
        "speckit overlay names type-inventory.json",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m2-planner.md",
        "types_uncovered",
        "M2 planner covers type-inventory dest twins",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m2-planner.md",
        "GENERATOR_INPUTS",
        "M2 planner requires generator inputs owned",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/stop-before-implement.overlay.yml",
        "configure generator",
        "speckit overlay generated types carry spec",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/type_graph.py",
        "STAR_IMP_RE",
        "type graph resolves star-import packages",
    ),
    (
        ".hermes/skills/analysis/inventory-entry-points/scripts/inventory-type-graph.py",
        "rhoai3.type-inventory/v1",
        "M1 emits type-inventory.json without --body",
    ),
    (
        ".hermes/skills/analysis/inventory-entry-points/SKILL.md",
        "generated: true",
        "M1 type-inventory marks generator output, not Creates",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py",
        "types_uncovered",
        "partition coverage gap for uncovered dest twins",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "inventory-type-graph.py",
        "M1 card walks type graph after HTTP inventory",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: stamp assigns star-import dest twins onto partition",
        "star-import simple names join the write-set",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: type-inventory lists dest twins from entry files",
        "M1 type-graph smoke emits dest_file rows",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: PARTITION_COVERAGE types_uncovered when dest twin is unplanned",
        "coverage refuses a type-inventory dest twin missing from the partition",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: stamp classifies generated types",
        "stamp provider generated for generator output",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: generated DEST_MISS skipped when inputs owned",
        "assert skips DEST_MISS for provider generated",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: GENERATOR_INPUTS when spec unowned",
        "assert requires generator spec owned",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: GENERATOR_INPUTS skipped when dest has no plugin",
        "H-1 handwritten dest does not inherit legacy inputSpec",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: holder-checkpoint init refuses --next",
        "H-2 init --next assemble is not a silent no-op",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: write-set hook allows /dev/null",
        "H-3 /dev/null is not a dest write",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: F-6 sibling import parents the owning story",
        "H-4 F-6 parent not relocate-to-foundational",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: CYCLE_IMPORT refuses cyclic import parent",
        "H-5 Review test C CYCLE_IMPORT",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: T0_3_SERVICE refuses foundational *Service.java",
        "H-6 T0 #3 foundational service refuse",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "split per aggregate",
        "LV-7a T0_3_SERVICE remedy is split per aggregate",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: T0_3_SERVICE remedy is split per aggregate",
        "LV-7a T0_3_SERVICE validate names split per aggregate",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "Parent the owning story",
        "LV-7b CYCLE_IMPORT remedy is parent-or-split",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: LV-7c T0_3_SERVICE names no placement another gate refuses",
        "LV-7c unsatisfiable placement check",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/scratch-assemble-mint.py",
        "relocate-descendant-import-writesets.py",
        "LV-5 M2 assemble wires MULTI_OWNER relocate gate",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: scratch-assemble wires relocate-descendant MULTI_OWNER gate",
        "LV-5 validate wiring needle",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: scratch-assemble _run_relocate fails MULTI_OWNER",
        "LV-5 MULTI_OWNER fails M2 assemble not the holder",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dest-generator-configured.py",
        "REQUIRED_PLUGIN_CONFIGURATION",
        "LV-6 DEST_GENERATOR emits the validated plugin block",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: DEST_GENERATOR refusal emits required plugin configuration",
        "LV-6 validate emits useJakartaEe / library native",
    ),
    (
        ".hermes/skills/migration/manage-quarkus-extensions/SKILL.md",
        "useJakartaEe",
        "LV-6 manage-quarkus-extensions points at DEST_GENERATOR recipe",
    ),
    (
        ".hermes/skills/gates/check-release-readiness/scripts/check-runnable-db-config.py",
        "one working schema mechanism",
        "LD-1 AR-2.1 requires a working mechanism not named Flyway",
    ),
    (
        ".hermes/skills/gates/check-release-readiness/scripts/check-runnable-db-config.py",
        "idle→active",
        "LD-2 refusal names the idle-to-active flip",
    ),
    (
        ".hermes/skills/migration/spring-to-quarkus-patterns/references/persistence.md",
        "one working schema mechanism",
        "LD-1 persistence card is not Flyway project law",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: AR-2.1 schema generation + import.sql passes without Flyway",
        "LD-1 schema-gen + import.sql is a satisfying dest path",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: AR-2.1 names idle→active surface when datasource has no schema mechanism",
        "LD-2 validate lock: idle→active Surface on bare datasource",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: PARTITION_COVERAGE skips generated type-inventory dest twins",
        "coverage does not require Creating generator output",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: PARTITION_COVERAGE still demands handwritten type when generated:true is stored",
        "LV-2 stored generated boolean is not coverage authority",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: write-set hook refuses execute_code open(w) type-inventory",
        "LV-1 pathless execute_code write uses the resolved-path fence",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/write-set-hook.py",
        "extract_code_write_paths",
        "LV-1 python open(w) destinations are fenced",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/generated_sources.py",
        "def inventory_row_is_generated",
        "LV-2 generated is classified at read time",
    ),
    (
        ".hermes/SOUL.md",
        "Blocked terminal",
        "LV-3 Blocked terminal is kanban_block needs_input",
    ),
    (
        ".hermes/SOUL.md",
        "repeated_exact_failure_warning",
        "LV-4 consume the warning Hermes emits before the terminal dies",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/scratch-assemble-mint.py",
        "OK: type-closure stamp+assert",
        "V34-8 scratch-assemble reuses stamp+assert-dependency-closure",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m2-planner.md",
        "holder-checkpoint.py init --kind m2",
        "V34-3 M2 checkpoint same script as holder",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/holder-checkpoint.py",
        "rhoai3.m2-checkpoint/v1",
        "V34-3 M2 checkpoint schema",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/stamp-harness-rev.py",
        "HARNESS_REV",
        "V34-2 stamp resolved golden SHA at create",
    ),
    (
        "devfile.yaml",
        "autostart-migration.sh",
        "postStart autostart M1 create-check-dispatch (075106Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/autostart-migration.sh",
        "hermes kanban dispatch --max 1",
        "autostart spawn is native dispatch not kanban daemon --force",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/autostart-migration.sh",
        "kanban daemon --force",
        "autostart names the OBJECT daemon path",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/assert-autostart-gates.py",
        "M3 WAVE HOLDER",
        "autostart park-M3 discriminator",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "auto_decompose: false",
        "Architect V34-6 dest-home kanban pin",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "python3 .hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py",
        "M2 body full-path cites stamp (R0 body-script)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py",
        "M2 body full-path cites assert (R0 body-script)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-tasks-generator-uptake.py",
        "M2 body full-path cites uptake (R0 body-script)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "evidence/required-extensions.json",
        "V35-EXTENSIONS M1 Done / M2 input manifest names required-extensions.json",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/check-phase-input-manifest.py",
        "evidence/required-extensions.json",
        "V35-EXTENSIONS M2 required present is live-enforced dest evidence",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/check-dangling-hermes-refs.py",
        "evidence/required-extensions.json",
        "V35-EXTENSIONS dangling-refs allowlist dest required-extensions.json",
    ),
    (
        ".hermes/skills/harness/record-run-evidence/scripts/restamp-card-and-sidecar.py",
        "task.body",
        "V35-DIGEST restamp parses nested kanban show JSON",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "ORACLE_UNMAPPED",
        "V35-ORACLE-REST total exit_for refuses unmapped operand combos",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "identity.parents",
        "V35-SERIAL kanban --parent includes resolved identity.parents",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dest-pom-extensions.py",
        "DEST_EXTENSIONS",
        "V35-EXTENSIONS dest-only pom declares required artifactIds (GEN-POST is a case)",
    ),
    (
        ".hermes/skills/analysis/scan-with-mta/scripts/emit-required-extensions.py",
        "rhoai3.required-extensions/v2",
        "V35-EXTENSIONS M1 emits required-extensions.json (T-3 rewrite, kind-tagged entries)",
    ),
    (
        ".hermes/skills/migration/manage-quarkus-extensions/scripts/spring_dep_map.py",
        "jdbc:hsqldb",
        "G1 JDBC kind is a cited md row, not a Python else-H2",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-partition-topological-order.py",
        "TOPOLOGICAL_ORDER",
        "H1 mint refuses descendant/sibling imports (coverage is not topology)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/relocate-descendant-import-writesets.py",
        "FACADE_RELOCATE",
        "H1 #34 descendant-importing dest types move onto polish",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/relocate-descendant-import-writesets.py",
        "unique-owner",
        "H1 relocated facade is unique-owned; coverage does not catch serial non-pom overlap",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/relocate-descendant-import-writesets.py",
        "MULTI_OWNER",
        "T0 #11 leftover dest-path claimants are refused by name",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "OPERAND_CLASS_SEMANTIC_EXITS",
        "T0 #10 mint imports the one exit map (no local def exit_for)",
    ),
    (
        ".hermes/skills/harness/validate-contracts/references/r-sk4-line-exceptions.txt",
        "dispatch-phase 2026-09-03",
        "R-SK.4 dispatch-phase 272-line exception expires 2026-09-03",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "--expect-max-runtime 2700",
        "H2 mint asserts M3 max_runtime_seconds from phase-dispatch.yaml",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md",
        "No legal move",
        "H2 no-legal-move branch is kanban_block needs_input",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md",
        "invent a config key",
        "A3 Maven >60s is detached poll, not an invented Hermes timeout key",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/write-set-hook.py",
        "extract_terminal_write_paths",
        "G2 fence terminal redirects on resolved path including HOME",
    ),
    (
        ".mvn/maven.config",
        "-s",
        "G2 Maven 3 reads .mvn/settings.xml only via maven.config -s",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-dest-generator-configured.py",
        "DEST_GENERATOR",
        "V35-GEN-POST dest-only parse_generator_plugins (no legacy union; case of EXTENSIONS)",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-tasks-generator-uptake.py",
        "M2_UPTAKE",
        "V35-M2-UPTAKE generated types require plugin token in tasks.md",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/native-dispatch.md",
        "Do **not** invent a leave-triage CLI",
        "V34-K2 official CLI refuses triage; do not invent leave-triage",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md",
        "assert-body-writeset-subset-of-partition",
        "write-set subset bank vocabulary",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "restamp-card-and-sidecar.py",
        "mint Procedure restamps card and sidecar together",
    ),
    (
        ".hermes/skills/harness/record-run-evidence/scripts/stamp-body-digest.py",
        "sidecar already exists",
        "first-stamp script refuses sidecar-only restamp",
    ),
    (
        ".hermes/skills/harness/record-run-evidence/scripts/restamp-card-and-sidecar.py",
        "card and sidecar",
        "atomic restamp updates card and sidecar as one operation",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/references/body-integrity.md",
        "restamp-card-and-sidecar-atomically",
        "body-integrity names atomic restamp",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "M4 waits on the **wave**",
        "mint-time M4 parents are story children not the holder",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/SKILL.md",
        "WAVE HOLDER",
        "skill names park-at-birth M3 as wave holder",
    ),
    (
        ".hermes/SOUL.md",
        "One next action per turn",
        "SOUL turn law stops replan storms",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "only if **no** child title starts with `M4` or `M5`",
        "holder must not complete if M4/M5 are children",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "M3 IMPLEMENT: {story_id} —",
        "child title is phase-first house form (111244Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "already has title starting with `M3 IMPLEMENT: {story_id}`",
        "skip-if keys phase-first title not story_id: prefix (111244Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md",
        "does not start with",
        "standing wrong-card keys phase-first title not story_id: prefix (111244Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "run-pre-create-gates.py",
        "V34-O7 holder pre-create is one OK/REFUSE wrapper",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "compose-m3-card-markdown.py",
        "V34-O7 holder card markdown is composed, not json.load",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "assert-story-parked.py",
        "V34-O7 park assert is sqlite one-liner, not show --json",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/holder-card-body.md",
        "run-pre-create-gates.py",
        "V34-O7 holder body path-invokes pre-create wrapper",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: compose-m3-card-markdown prints title without JSON",
        "V34-O7 validate lock: composer starves JSON",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/issue-m3-brief-identity-ack.py",
        "gate:check-body-digest-match",
        "M3 brief-identity is a 5.1 gate-record (122824Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "issue-m3-brief-identity-ack.py",
        "mint Procedure issues M3 ack as verification gate (122824Z)",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/check-ack-authority.py",
        "gate:check-body-digest-match",
        "AR-1.1 allowlists M3 gate signer (122824Z)",
    ),
    (
        ".hermes/skills/harness/enforce-authority-boundary/scripts/check-acks.sh",
        "issue-m3-brief-identity-ack.py",
        "check-acks auto-issues M3 brief-identity (122824Z)",
    ),
    (
        ".hermes/skills/harness/validate-contracts/scripts/validate.sh",
        "OK: M3 brief-identity issuer names mismatching body",
        "M3 issuer refuse names the body (122824Z)",
    ),
]

FORBIDDEN_SUBSTRINGS = [
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "unsigned brief-identity",
        "M3 ack_gate is not a human unsigned wait (122824Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "Wait for Deputy",
        "M3 ack_gate does not wait for Operator complete (122824Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/holder-card-body.md",
        "The gate stays blocked",
        "holder completes ack_gate after issuer PASS (122824Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/SKILL.md",
        "--skill dispatch-phase",
        "I-10 B holder create argv must not pass --skill dispatch-phase",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/SKILL.md",
        "--skill one-three-one-rule",
        "I-11 holder create argv must not pin one-three-one-rule",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "--task-id {id}",
        "do not mint {id} placeholder; complete-path uses HERMES_KANBAN_TASK",
    ),
    (
        ".hermes/skills/sdd/init-spec-workspace/assets/tasks-template.md",
        "Verify quality gate",
        "I-16 polish sample must not Verify pom.xml (215010Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "M3 IMPLEMENT: bounded transform",
        "park-at-birth M3 must not use implementer title",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh",
        "for next in M2 M3 M4 M5",
        "do not park M4/M5 as children of the M3 holder",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "{story_id}: M3 IMPLEMENT: {story_id}",
        "child titles must not double story_id (111244Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md",
        "already has title prefix `{story_id}:`",
        "skip-if must not key the retired story_id: prefix (111244Z)",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md",
        "no `{story_id}:` prefix",
        "wrong-card must not key the retired story_id: prefix (111244Z)",
    ),
    (
        ".hermes/skills/gates/check-release-readiness/scripts/check-runnable-db-config.py",
        "initDB.sql without Flyway",
        "LD-1 must not refuse init SQL for lacking Flyway",
    ),
    (
        ".hermes/skills/migration/spring-to-quarkus-patterns/references/persistence.md",
        "Keep Flyway as the schema path",
        "LD-1 persistence agent text must not keep Flyway as the only schema path",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/assert-setup-datasource-driver.py",
        "also requires Flyway",
        "LD-1 setup-driver comment must not claim the runnable-db gate requires Flyway",
    ),
    (
        ".hermes/skills/sdd/check-spec-readiness/scripts/specimen_agnostic.py",
        "Rows with\n    ``generated: true`` are skipped",
        "LV-2 coverage must not skip on the stored generated boolean",
    ),
    (
        ".hermes/skills/harness/dispatch-phase/scripts/handover-mint.py",
        "Put the facade on polish",
        "LV-7a T0_3_SERVICE must not name polish as the *Service.java home",
    ),
]


def _assert_m3_holder_consumer(root: Path) -> list[str]:
    """Park-at-birth M3 is dispatch-phase.sh, not handover-mint / yaml.

    Operator f5bfdb74: yaml M3.skills is the children's B-16 allow-list.
    Emptying it to get zero holder pins is the trap. The M3 case must
    cat holder-card-body.md, set the holder title, and SKILLS=() after
    the yaml load so CREATE_ARGS grows no --skill pins.
    """
    fails: list[str] = []
    sh = (
        root
        / ".hermes"
        / "skills"
        / "harness"
        / "dispatch-phase"
        / "scripts"
        / "dispatch-phase.sh"
    )
    text = sh.read_text(encoding="utf-8") if sh.is_file() else ""
    m = re.search(r"^\s+M3\)\s*\n(.*?)^\s+;;", text, re.M | re.S)
    if not m:
        fails.append("dispatch-phase.sh missing M3) case")
        return fails
    block = m.group(1)
    if "holder-card-body.md" not in block:
        fails.append(
            "M3 case must cat holder-card-body.md "
            "(handover-mint.py never names the park-at-birth card)"
        )
    if "M3 WAVE HOLDER" not in block:
        fails.append("M3 case must override TITLE to WAVE HOLDER (yaml title is not the card)")
    if "SKILLS=()" not in block:
        fails.append(
            "M3 case must SKILLS=() after yaml load "
            "(yaml M3.skills is the child allow-list, not holder pins)"
        )
    if "M3 IMPLEMENT: bounded transform" in block:
        fails.append("M3 case still hardcodes implementer title")
    ypath = root / ".hermes" / "phase-dispatch.yaml"
    ytext = ypath.read_text(encoding="utf-8") if ypath.is_file() else ""
    ym = re.search(r"^  M3:\n(.*?)(?=^  M[0-9]|^  factory:|\Z)", ytext, re.M | re.S)
    if not ym:
        fails.append("phase-dispatch.yaml missing M3:")
        return fails
    yblock = ym.group(1)
    skills = re.findall(r"^      - (\S+)", yblock, re.M)
    if "check-spec-readiness" not in skills:
        fails.append(
            "yaml M3.skills must keep check-spec-readiness "
            "(child allow-list; do not empty to un-pin the holder)"
        )
    if len(skills) < 3:
        fails.append(
            f"yaml M3.skills has {len(skills)} entries; "
            "emptying the pool to zero holder pins is the f5bfdb74 trap"
        )
    if "allow-list pool" not in yblock:
        fails.append("yaml M3 comment must keep allow-list pool (B-16)")
    return fails


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
    consumer_fails = _assert_m3_holder_consumer(root)
    for msg in consumer_fails:
        print(f"FAIL: {msg}", file=sys.stderr)
        bad = 1
    if not consumer_fails:
        print("OK: park-at-birth M3 consumer clears skills; yaml pool stays")
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
