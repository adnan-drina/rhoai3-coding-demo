# v10 validation run

This is the execution plan after the 2026-09-22 review. It supersedes the
session-local `tmp/080-operator/V10-PLAN.md` and `v10-preflight.sh`. Do not use
those historical files: they select an old golden and the shared database.

## Purpose and comparison

Run a fresh PetClinic destination with Qwen 3.8 INT4, unit formation and runtime
feedback enabled. v9 remains the assisted baseline, closed as PROVISIONAL_ACCEPT,
not shipped. Reconfirm its archived close row and both-mode receipts; do not
infer successful parity from closure. Preserve all Operator steps and rewinds.

The comparison is descriptive. Model, harness, bootstrap repairs and other
reported pins can differ; their individual causal contributions are unknown.
A same-model experiment is not a launch prerequisite. Compare the common
unchanged request/expectation contract, selected before outcomes. Report all
34 entry points per security mode and additional coverage separately. The 13
v9 gaps and retired-source coverage debt do not disappear from the denominator.
This run cannot establish specimen independence.

## Qualified inputs

The release record must name full platform and golden commits, the golden file
manifest, frozen-source digest, decisions, corpus/captures, comparator digests,
worker model/provider/configuration, served context, concurrency and cache state.
There is no hardcoded successor golden: publish the corrected, validated tree,
then fill the release record from the actual publication. No repaired v9 product
files may enter v10; only the enumerated decided bootstrap repairs apply.

The provisioning Task pins the PostgreSQL 16 and CLI image digests observed on
the guarded demo cluster on 2026-09-22. Record and verify these same references
in the isolation receipt. An image change requires that qualification again.
Run names must equal actual DevWorkspace names; the consumer checks the
operator-provided DEVWORKSPACE_NAME, not merely the devfile's intended name.

## Execution sequence

1. Archive v9's closed commit, package manifest, both-mode captures and receipts,
   board export, official worker logs, close row, outstanding items and retained
   stores needed to reproduce measurements. Stop dispatch and all remaining v9
   clients before retiring its shared database. Closure alone does not stop a pod.
2. Resolve the source-protection prerequisite described below before selecting
   the release pins. Run the focused regression checks and Stage 080 validation. Publish the
   corrected successor golden, recording source and published tree equivalence.
   Merge/sync the intended Stage 050 revision through the normal GitOps path;
   retire old shared resources and remove old global credential mounts through
   their owning platform lifecycle. Never hand-create a v10 credential Secret.
3. Run [the isolation demonstration](ISOLATION-DEMO.md) on two disposable runs.
   All required checks must PASS on the exact platform/golden/image pins before
   the official v10 workspace is created. Save its evidence-bound receipt.
4. Confirm the served Qwen 3.8 service and governed inference route are healthy.
   Keep declared context below the actual served window and retain the provider
   configuration without credential values. A model readiness failure blocks
   launch even if unrelated harness tests pass.
5. Verify the dated `run-budget.json` shipped in the qualified scaffold before
   creating the destination, so the declaration predates its first commit.
   Then scaffold `spring-petclinic-rest-legacy-v10` with the Application migration
   template and **Auto-start migration disabled**. Provisioning remains automatic.
   Do not manually run bootstrap before M1. The new database/fixture Secrets
   must be present before the workspace consumes them; if it started early,
   stop/start only this workspace after provisioning completes.
6. Before dispatch, verify the inherited `run-budget.json` and run the read-only [preflight](v10-preflight.sh). It requires the exact golden
   checkout, platform revision, live isolation receipt, fresh product tree,
   owned resources, model/configuration and source-protection prerequisites.
   Failure is a typed launch failure; do not relax a check to get started.
7. Enable/start the existing native M1 entry point. M1 owns freeze, derivation
   and source capture; M2 owns bootstrap, verified datasource reset and admission.
   Their existing gates must pass before M3. The preflight does not call those
   producers, reset the database, or mint a competing card.

Example (all pins are actual full committed values from the release record):

```bash
POD="$V10_POD" GOLDEN_CHECKOUT="$QUALIFIED_GOLDEN_CHECKOUT" \
GOLDEN_SHA="$QUALIFIED_GOLDEN_SHA" PLATFORM_SHA="$QUALIFIED_PLATFORM_SHA" \
ISOLATION_RECEIPT="$LIVE_ISOLATION_RECEIPT" \
  bash stages/080-ai-autonomous-migration/v10-preflight.sh
```

## Budget and terminal outcomes

Declare `max_wall_hours: 24` before dispatch, with an actual UTC `declared_at`
in `run-budget.json`. Its timestamp must precede the destination first commit;
a boolean claiming this is not evidence. The measured clock begins at the earlier destination first
commit or M1 dispatch, before bootstrap; record provisioning/setup time too.
Keep native worker timeouts and the sealed unit/family retry budget enabled.

Stop the autonomous attempt at the first of: a terminal M4 outcome in both
modes; 24 hours elapsed; a blocking harness defect requiring an installation;
or exhaustion of the sealed retry budget. Full acceptance and provisional
closure are different outcomes. Do not grant three more attempts after a
cluster becomes manual, change its identity to reset a budget, or restart the
clock. An Operator repair, rewind or harness replacement starts a separately
reported assisted continuation. Preserve the original attempt and its costs.

Classification is `autonomous_execution_with_predecided_repairs` only when no
live intervention occurred. Bootstrap repairs remain prior authored assistance.
Record tokens where measured; missing token telemetry remains unknown.

## Readiness and rollback

The combined implementation, including source protection, was validated on
2026-09-22 and merged as `19f742aa`: Stage 080 reported
**359 passed, 0 failed, 2 warnings** (exit 2 means warnings in validate-lib.sh).
The warnings were Stage 050 OutOfSync and the existing MTA ConsoleLink
placeholder. Both changed Kustomize directories rendered, and the live API
accepted the provisioning Task with server-side dry run. The lifecycle tests
execute its actual shell with overlapping events; the bootstrap integration
test exercises separate profile files and repeated application. These results
do not substitute for the live two-workspace demonstration or v10 preflight,
neither of which has run. No successor golden was published by this change.

Local regression success is not live isolation qualification. The live
isolation receipt, Stage 050 sync and v10 preflight remain mandatory evidence.
The template initializes a separate `legacy-input` volume once, records its
source URL and commit inside `.git`, and mounts it read-only at `/projects/legacy`
in the worker. Restarts verify the retained checkout without updating it.
The preflight checks both the filesystem's read-only flag and the admitted
Pod for writable aliases of that source volume, including other runtime
containers. Permissions alone are insufficient. The initializer trusts only
its exact PVC clone path because the storage provisioner owns the mount root.
This prevents ordinary in-container source edits; it does not make a user with
permission to change the Pod or DevWorkspace an unprivileged sandbox tenant.

The 2026-09-22 disposable source probe on DWO 0.43.0 passed source-write and
chmod refusal (EROFS), destination writes, runtime alias inspection and restart
commit stability. This is mount qualification, not full template/isolation
qualification. The initial failure and corrected results are retained locally
under `tmp/v10-readiness-20260922/`.

The narrow `container-overrides` patch sets only `readOnly` on the declared
legacy mount. DWO 0.43 supplies its volume name and subPath; no generated
credential or metadata mounts are replaced. A live admitted-Pod test is required
for any operator change. See the [DWO 0.43 override contract](https://github.com/devfile/devworkspace-operator/blob/v0.43.0/docs/additional-configuration.adoc).
Do not install this generation onto closed v9 to qualify v10. If qualification
fails, preserve disposable-run evidence, stop their clients, and use the platform
retirement Pipeline; preserve tombstones. Roll back platform code through GitOps
only with lifecycle tasks stopped, never while a provisioner still owns a lock.
