# v11 launch packet — updated 2026-09-24

Preparation only. Do not create `spring-petclinic-rest-legacy-v11` and do
not dest-install or dest-dispatch from this file. Closed v10 stays frozen
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
failed. Stage 050 worker identity and CLI-image repair was published at
`bbd623997b9b29ce56b0811b914762de45c12bee`; bind live isolation evidence to
the actual synchronized platform revision after this launch record lands.

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

Do not run the full 13-check demonstration until the Stage 050 worker-identity
repair has passed focused live validation in
[WORKER-IDENTITY-REPAIR.md](WORKER-IDENTITY-REPAIR.md). That repair is GitOps
only until synced; it does not revoke v10's generated `workspace*-sa`. Do not
launch v11 from this packet.

After that focused plan PASSes, use [ISOLATION-DEMO.md](ISOLATION-DEMO.md)
with disposable names:

```
A = iso-v11-final
B = iso-v11-final-retry
```

`autoStartMigration=false`. No M3 workers. Do not touch v10. Bind the
receipt to the **resulting** platform commit, published golden SHA, and Task
image digests. Required checks: the twelve operational names plus
`workspace_identity`. Every result must be the measured outcome. A FAIL
stays FAIL. The v10 `workspace_identity` deferral does not apply.

[v11-preflight.sh](v11-preflight.sh) refuses any non-PASS, including a
copied v10 receipt.

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
