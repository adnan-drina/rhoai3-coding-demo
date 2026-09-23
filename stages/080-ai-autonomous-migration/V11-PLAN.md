# v11 launch packet — 2026-09-23

Preparation only. Do not create `spring-petclinic-rest-legacy-v11` and do
not dest-install or dest-dispatch from this file. Closed v10 stays frozen
(`ns wksp-ai-developer`, workspace `spring-petclinic-rest-legacy-v10`).

## Publication mapping

Do not reuse `8c8cc195` or previously published `87251b73`.

| Identity | Value |
|---|---|
| Source commit | `1082d51e230e378c1f71032d6e834b00e641a997` |
| Scaffold git tree | `5fed3d349297887d76ea8a004647f3e0d519425a` |
| Scaffold tree sha256 | `d2d6166104f5a69b31a9b1a276190ef8e8b077af4ca5d044267f4a9d2d5411f7` (613 files; dest omit `.hermes/_park`) |
| Golden repository | `github.com/adnan-drina/quarkus-migration-scaffold-v2` |
| Golden commit | `80b47c6ca5cf605a25145df18d39cb13fb6ad49a` |

Equivalence: the published golden tree (dest omit `.hermes/_park`) must
match the recorded scaffold tree sha256.

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

Use [ISOLATION-DEMO.md](ISOLATION-DEMO.md) with disposable names:

```
A = iso-v11-final
B = iso-v11-final-retry
```

`autoStartMigration=false`. No M3 workers. Do not touch v10. Bind the
receipt to the **final** platform commit, published golden SHA, and Task
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
   at `PLATFORM_SHA`, model Ready, and Tekton/listener ready.
2. In Developer Hub **Application migration** template:
   - Name: `spring-petclinic-rest-legacy-v11`
   - Legacy URL: the approved PetClinic freeze-fork
   - **Auto-start migration: off**
3. Wait until `migration-run-spring-petclinic-rest-legacy-v11` is
   `provisioned` and the database Deployment is Available.
4. `scripts/patch-workspace-maas-route.sh spring-petclinic-rest-legacy-v11`
5. Start/open the workspace. Do not enable dest-init dispatch yet.
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
