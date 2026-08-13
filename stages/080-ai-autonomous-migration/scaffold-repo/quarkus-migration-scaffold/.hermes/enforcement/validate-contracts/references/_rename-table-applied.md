# v14 mint-boundary rename (APPLIED — Wave B / UPLIFT-6 + enforcement Slice B)

Harness leaves landed under `.hermes/enforcement/` (not
`.hermes/skills/harness/`). Guidance leaves stay under `.hermes/skills/`.

| Was | Now | Tree |
|-----|-----|------|
| `analysis/mta-analysis` | `analysis/scan-with-mta` | guidance |
| `gates/domain-gates` | `gates/check-domain-parity` | guidance |
| `gates/validation-release-gates` | `gates/check-release-readiness` | guidance |
| `harness/auditability-repeatability` | `enforcement/record-run-evidence` | enforcement |
| `harness/grounded-generation` | `enforcement/ground-in-harvest` | enforcement |
| `harness/harness-validate` | `enforcement/validate-contracts` | enforcement |
| `harness/phase-dispatch` | `enforcement/dispatch-phase` | enforcement |
| `harness/role-authority` → `harness/enforce-authority-boundary` | `enforcement/enforce-authority-boundary` | enforcement |
| `sdd/sdd-readiness` | `sdd/check-spec-readiness` | guidance |
| `sdd/specify-workspace-init` | `sdd/init-spec-workspace` | guidance |

**Unchanged:** `analysis/inventory-entry-points`,
`migration/derive-legacy-boot3` (already N1);
`migration/spring-to-quarkus-patterns` (N3 pair);
`migration/manage-quarkus-extensions` (Wave A);
`migration/bootstrap-quarkus-project` (Wave B guidance, new).

Enforcement packages are **path-invoked** by `validate.sh` / create helpers —
they MUST NOT appear on card `skills[]` / bundles.
