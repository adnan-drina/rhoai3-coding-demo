# Live isolation qualification — 2026-09-22

**Operational prerequisite met for the controlled v10 experiment.** Twelve
checks passed; `workspace_identity` remains FAIL on the actual worker accounts.
The initial full-isolation verdict was FAIL. The Operator subsequently agreed
on 2026-09-22 to defer permission hardening and proceed with migration testing.
The original receipt and failure are unchanged; the v10 launch policy requires
the 12 operational checks and reports the identity failure as a warning.
The earlier command-approval timeout was resolved and did not cause the finding.

## Inputs and evidence

- Platform: `af7c389c7a333476e3481c4b150c3439c9ec9551`, observed Synced/Healthy.
- Golden: `eab9efd9406ed6226724e1bd9f928548ca1f1b52`, 593 files matched to the
  committed scaffold. Both disposable repositories originally scaffolded the
  prior golden; two corrected ownership-CLI files were committed before either
  workspace started. All 541 installed harness files checked matched this golden.
- Disposable runs: `iso-v10-final` (A) and `iso-v10-final-retry` (B), created
  through Developer Hub with migration dispatch disabled.
- Evidence packet: local `tmp/v10-readiness-20260922/`, including the manifest,
  `isolation-receipt.json`, `workspace-identity-finding.json`, lifecycle TaskRuns,
  logs, data/credential hashes and pre-retirement evidence archives. Secret
  values and database rows are not included in the comparisons.

The original template events were real deliveries. Subsequent concurrent and
post-retirement replay tests used reconstructed branch-creation envelopes,
signed through the real listener. They are not claimed as archived GitHub
delivery bodies. Test bootstrapping produced reset assets without completing
M1/M2, admitting a migration, or starting M3 workers.

## Passing checks

`secret_binding`, `wrong_targets`, `assignment_removal`, `receipt_fields`,
`delayed_resources`, `data_independence`, `credential_independence`,
`workspace_independence`, `repository_non_authority`, `duplicate_delivery`,
`overlapping_retirement`, and `retirement` passed.

Each workspace received its own parity Secrets and refused 16 malformed or
missing ownership bindings. An unavailable assigned database failed reset;
after recovery, both resets verified the source-declared rows and sequences.

B retained its public-schema marker, logical data/sequence digest, Secret
digests, database pod identity and workspace pod identity through A's reset,
database restart, concurrent replays, interrupted retirement and completed
retirement. Seven database snapshots agreed. Duplicate provisioning preserved
credentials and pods; it refreshed `provisionedAt`, not the scaffold binding.

An ordinary repository push did not provision resources. A one-minute timeout
interrupted a real retirement held by a test finalizer. Its `retiring` receipt
survived, the overlapping provision request refused, and the lock was released
after the writer stopped. Only then was the test finalizer removed and normal
retirement resumed. Post-retirement creation replay refused; an ordinary push
created no provisioning run. B's mismatched-scaffold request also refused.

Both runs finished with retired tombstones, no generated database/Service/Secret
objects, no lifecycle locks and no DevWorkspaces. Evidence and repositories were
retained. Official `spring-petclinic-rest-legacy-v10` was never created.

## Failed check and required repair

`workspace_identity: FAIL`. The accounts actually used inside A and B were
their generated workspace service accounts. Both successfully requested the
other run's database Secret with name-only output. The assigned
`devworkspace-default-role` also grants Secret mutation, ConfigMap mutation,
pod execution and DevWorkspace updates. The privileged provisioner is correctly
confined to the build namespace and workers cannot create its PipelineRuns;
that does not remove the broader workspace namespace permissions.

Owner: Stage 050 workspace identity/provisioning implementation, with the
Stage 080 factory and preflight consuming any future restriction. Keep this
check failed until a fresh demonstration proves the replacement. This is
deferred platform work, not a prerequisite for the controlled v10 experiment.

The narrow candidate is a platform-provisioned service account per migration
run, selected through a per-workspace DevWorkspaceOperatorConfig. DWO 0.43.0's
controller has a `serviceAccount.disableCreation` path for an existing named
account, and its [configuration reference](https://github.com/devfile/devworkspace-operator/blob/v0.43.0/docs/dwo-configuration.md#devworkspace-specific-configuration)
documents workspace-specific configuration. This is an implementation direction,
not a tested remediation or a Red Hat support claim.

Required exits: the installed worker cannot read another run's credentials,
alter lifecycle receipts or locks, execute in another run's pod, change another
workspace, or invoke the provisioner. Its normal IDE, mounted credentials, MaaS
initialization, source protection, reset and restart must still work. Provision
and retire the identity/configuration through the same platform lifecycle;
requalify exact release pins. A restriction on direct Secret reads alone does
not close the pod-exec and workspace-edit routes. Human administrator access
remains outside this worker boundary.

The agreed launch scope is operational run independence, not security
confinement between workers. Preserve the original test and FAIL, record the
scope change, and retain it in the v10 report. Do not patch an operator-owned
role in place or claim this experiment proves security confinement.
