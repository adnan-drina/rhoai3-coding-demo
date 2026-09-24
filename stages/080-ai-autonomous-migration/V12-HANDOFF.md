# v12 creation handoff — 2026-09-24

v12 is **not created**. Its 24-hour budget starts when the destination
repository is created, so every prerequisite below was completed first.

## Qualified inputs

| Input | Identity |
|-------|----------|
| Platform (`main`, Stage 050 Synced/Healthy) | `63c173885a4fce50d4f04196895e91e75473ec16` |
| Golden (`quarkus-migration-scaffold-v2` `main`) | `78b3e9dbca1ab917affe97680f4008233b6a65ec` |
| Source of the golden (branch `codex/v10-launch-scope`) | `106d334a`, recorded in `dc277bd3` |
| Database image | `registry.redhat.io/rhel9/postgresql-16@sha256:188e892c58c56037c8ff93051f3e3b76ec56773de5ba89791cd4a686f97b0cef` |
| Provisioner image | `registry.redhat.io/openshift4/ose-cli@sha256:69762925e16053d77685ff3a08b3b45dd2bfa5d68277851bc6969b368bbd0cb9` |
| Model | `qwen3-8-27b-int4` (golden `run-defaults.json`) |

The image digests agree in the golden defaults, the platform manifests and
the live `provision-migration-run` Task; nothing overrides them at trigger time.

## Isolation qualification

All 13 checks of [ISOLATION-DEMO.md](ISOLATION-DEMO.md) **PASS** on the fresh
disposable pair `iso-v12-qual` / `iso-v12-qual-retry`, created through the
Developer Hub *Application migration* form as `ai-developer` with Auto-start
**off**, and opened, restarted and deleted through the Dev Spaces dashboard.

- Receipt: `tmp/v12-qualification-20260924/isolation-receipt.json`, SHA-256
  `6fda37d9db0ce5a71316725a023c4a5f79e0493bee6d3f7167eb443e7c5fcc50`,
  binding 84 retained evidence files (local packet, like v11's).
- `run-preflight.sh`'s own receipt-validation block, executed verbatim, passes
  it for `spring-petclinic-rest-legacy-v12`, and refuses the v11 receipt, a
  different platform revision and a tampered evidence file.
- These were the first live factory runs after the run-declaration fix. Each
  initial commit carried `run-budget.json` v2 with its real scaffolder task
  id, no `run-configuration.json`. `planner.run_declaration` returned OK in
  both live workspaces.
- Two evaluations were corrected to the procedure's own criterion; both
  originals are retained in the packet. Repository non-authority now judges
  Applications by source, not name (the `project-<run>` delivery apps source
  the platform repository). Duplicate delivery now allows `provisionedAt` to
  move, because the provisioner re-stamps it on every success; the scaffold
  commit and secrets did not change.
- Incident: a misclick in the dashboard started `spring-petclinic-rest-legacy-v9`,
  which was stopped within about 10 s. Only init containers ran, so dest-init
  never executed (`incident-v9-misclick.json`).
- v10 and v11 run objects, secret digests, receipts and workspace state are
  unchanged (`preservation-final.json`). The v11 receipt is unchanged
  (`ecc9562a…`). Both disposable runs are retired, with tombstones kept and
  their workspaces deleted.

The complete `run-preflight.sh` has **not** run: its pod checks need the
actual v12 workspace.

## Checklist for creating v12

1. Developer Hub → *Application migration*: name `spring-petclinic-rest-legacy-v12`,
   legacy URL `https://github.com/adnan-drina/spring-petclinic-rest-legacy.git`,
   **untick Auto-start** (it defaults on). Creating the repository starts the
   24 h budget.
2. Open the workspace from the component's Dev Spaces link. Confirm exactly one
   DevWorkspace named `spring-petclinic-rest-legacy-v12` (no suffix) and
   `.hermes/AUTOSTART-STATUS` = `skipped`.
3. Close the IDE tab and reopen from the same link: the same workspace must
   open, with no second workspace.
4. Run the complete preflight against the v12 pod:
   `WORKSPACE=spring-petclinic-rest-legacy-v12 POD=<pod> GOLDEN_CHECKOUT=<clean clone at 78b3e9db>
   GOLDEN_SHA=78b3e9dbca1ab917affe97680f4008233b6a65ec PLATFORM_SHA=63c173885a4fce50d4f04196895e91e75473ec16
   ISOLATION_RECEIPT=tmp/v12-qualification-20260924/isolation-receipt.json bash stages/080-ai-autonomous-migration/run-preflight.sh`
5. Start the migration only after the preflight passes. If platform `main` or the
   golden has moved in the meantime, the receipt no longer binds and must be
   re-qualified.
