# v11 launch packet — updated 2026-09-24

Prerequisites qualified live on September 24. Creation of
`spring-petclinic-rest-legacy-v11` remains the user's manual handoff with
auto-start disabled. Do not dest-install or dest-dispatch from this file.
Closed v10 stays frozen
(`ns wksp-ai-developer`, workspace `spring-petclinic-rest-legacy-v10`).

## Publication mapping

Do not reuse `8c8cc195` or previously published `87251b73`.

| Identity | Value |
|---|---|
| Source commit | `2c92983eb8880b1ee0f29b8b401875f75d474ad3` |
| Scaffold git tree | `dfb88e0ef33fbdb7daca6a5a752f9af05a9328d4` |
| Golden repository | `github.com/adnan-drina/quarkus-migration-scaffold-v2` |
| Golden commit | `8f83dbdbc1cdb07b0702e54c48f7356352114ae1` |

Equivalence: the published golden tree (dest omit `.hermes/_park`) must
match the recorded scaffold Git tree (`git rev-parse GOLDEN^{tree}`).
The September 24 correction only documents the existing M5 self-test.
Stage 080 validation: 367 passed, one existing MTA ConsoleLink warning, zero
failed. Qualified Stage 050 platform revision:
`080d2585ce49682b604a3d022beca4265932bb66` (Synced/Healthy). This includes
the dedicated kubeconfig directory mount that prevents late Dashboard human
credential injection. The golden is unchanged. This qualification record is
published on the authoring branch; it does not advance platform main.

Frozen runtime/model (`run-configuration.json` in the golden):

- Model `qwen3-8-27b-int4` / provider `qwen38`, Ready, served
  `--max-model-len=262144`, declared `context_length` 220000
- Hermes `v0.20.5` / `2026.8.19`
- Overlay `sha256:0d3e19e298f541e2b1c5e61e86e4219fa32bee37b39987fd701ecca68457572f`
- PostgreSQL 16 and ose-cli image digests as in
  `task-provision-migration-run.yaml` defaults
- Serial M3; parallel execution deferred
- Golden `pins.planner.activation: not-activated`

Frozen budget (`run-budget.json`): `declared_at` 2026-09-23T17:10:00Z,
`max_wall_hours` 24. M5 delivery is a separate continuation after M4 close:
PREFLIGHT 1h, DEPLOY 3h, VALIDATE 1h, `max_retries` 1. Do not extend the
24h migration deadline to cover M5.

## Isolation qualification

The focused identity checks and all 13 [isolation checks](ISOLATION-DEMO.md)
passed on fresh `iso-worker-c` / `iso-worker-c-retry`, using the exact platform
and golden revisions above. The same pair was retained for the operational
checks after focused startup/restart validation; no second pair was needed.
Both are now retired, their workspaces removed, and their tombstones retained.
Do not reuse these names. V10's pod identity, service account, default Role
UID/resourceVersion, and binding were unchanged. V11 has not been created.

Local evidence packet: `tmp/v11-readiness-20260924/isolation-receipt.json`.
Receipt SHA-256:
`ecc9562a80cea2b0c9c55299560f658ca025a0ce49f7f3bcc6b344baaed42ec1`.
The receipt pins 46 retained evidence files. Preserve the packet; it is not
replaced by this summary or by static tests.

Measured boundaries:

- Initial startup, normal stop/start, explicit Dashboard credential refresh,
  and both workers' permission matrices retained the restricted pod identity.
  The earlier `iso-worker-b` restart FAIL is preserved separately.
- Actual cross-run Secret metadata GETs returned 403. The existing named
  MaaS Secret GET exception remains; this is not a claim of zero Secret API
  access or isolation of legacy v10 workers.
- Both workers refused 16 wrong-target, receipt, and missing-assignment cases.
  A real reset failed while its database was unavailable.
- B's data marker, logical dump, credential digests and pod identities survived
  A's reset, database restart, and retirement unchanged.
- Concurrent reconstructed, signed creation events went through the real
  listener. These are integration-test events, not archived GitHub deliveries.
  Provisioning/retirement overlapped; tombstones prevented resurrection.
- The pushed repository canary was not executed in the workspace namespace.

The receipt-validation function from [v11-preflight.sh](v11-preflight.sh)
passed against these 13 results, but its
**complete pod-specific preflight remains required after the user creates v11**.
It checks the fresh destination, source protection, actual pod/CLI identity,
golden files, model, owned resources and declared budget. No migration task
was issued during disposable qualification.

## Activation GO packet (destination only, after M1)

Do not flip the golden `pins.json`. After M1 has written
`evidence/planning/evidence-bundle.json`, an Operator edits **that
destination's** `.hermes/pins.json`:

```json
"planner": {
  "activation": "pilot",
  "pilot": {
    "run_id": "v11",
    "authorized_by": "<operator>",
    "evidence_bundle_sha256": "<sha256 of evidence/planning/evidence-bundle.json>"
  }
}
```

Then re-run paved-road-m2 from the activation gate. Admission admits only
that bundle. A worker never edits this block. Preserve `pins.json` across
any later harness copy.

## User creation checklist (auto-start disabled)

1. Confirm publication mapping, isolation receipt, Stage 050 Synced/Healthy
   at `PLATFORM_SHA`, model Ready, and Tekton/listener ready. Confirm the live
   three-workspace capacity before disposable qualification; keep v10 running.
2. In Developer Hub **Application migration** template:
   - Name: `spring-petclinic-rest-legacy-v11`
   - Legacy URL: the approved PetClinic freeze-fork
   - **Auto-start migration: off**
3. Wait until `migration-run-spring-petclinic-rest-legacy-v11` is
   `provisioned` and the database Deployment is Available.
4. Open the Dev Spaces link to create the workspace, then stop it through
   Dev Spaces with auto-start migration still off. Run
   `scripts/patch-workspace-maas-route.sh spring-petclinic-rest-legacy-v11`.
   The helper refuses a route change while the workspace is started, preserving
   its postStart and per-run ServiceAccount.
5. Start/open the workspace. Confirm the IDE is Ready. Do not enable dest-init
   dispatch yet; the preflight checks the pod and CLI worker identities.
6. Run [v11-preflight.sh](v11-preflight.sh) with `POD`, `GOLDEN_CHECKOUT`,
   `GOLDEN_SHA`, `PLATFORM_SHA`, `ISOLATION_RECEIPT`.
7. Only after preflight PASS: Operator GO (pilot seal after M1, or enable
   auto-start and restart dest-init). Do not copy v10 dest product, verdicts,
   or overlays.

## Out of this packet

- Creating or launching v11
- Overlay install
- Parallel M3
- Changing golden activation from `not-activated`
