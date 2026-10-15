---
name: rhoai-uninstallation
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when the user explicitly wants to decommission OpenShift AI from a demo
  cluster or to tear the demo down: ordering the Argo CD Application deletes
  (docs/OPERATIONS.md Cleanup Guidance), stopping 010-rhoai-operator and
  010-rhoai-platform from re-creating objects, backing up PVC-backed data
  (MLflow and MaaS PostgreSQL, the rhoai-mlflow-artifacts bucket), the official
  CLI uninstall in redhat-ods-operator, and reviewing what remains. Also use to
  turn off a single delegated DSC component safely. Do NOT use for cost
  shutdown or GPU scale-down (use manage-resources, resume-gpu-demo),
  reinstall failures (use rhoai-installation-troubleshooting), or moving
  objects between Applications (use gitops-move-applications).
---

# RHOAI Uninstallation

Thin skill: this repo's teardown order and guards, with the uninstall itself in
the linked OpenShift AI 3.5 chapter. Uninstalling is destructive; run nothing
live unless the user asked for it and confirmed the cluster.

## When to use

- The user asks to remove OpenShift AI or the whole demo from a cluster.
- A stage or a DSC component must be switched off without breaking others.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| The repo has no uninstall script; teardown is a cascade delete of Applications in reverse deploy order (070 down to 010, components last-deployed first) | `docs/OPERATIONS.md#cleanup-guidance`, `scripts/shared/stage_apps.py` | [Understanding the uninstallation process][understand] |
| Applications have no finalizers: deleting one without cascade orphans its objects; a cascade delete removes namespaces and PVCs too (`Prune=false` does not protect against Application deletion) | `docs/OPERATIONS.md#cleanup-guidance` | — (repo GitOps rule) |
| `010-rhoai-operator` owns the `redhat-ods-operator` namespace, OperatorGroup and Subscription; `010-rhoai-platform` owns DSCI, DSC and `Auth` | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-operator/`, `.../rhoai-platform/` | [Uninstall by CLI][cli] |
| To switch off one component, turn it off through its owning stage first; removing its `ignoreDifferences` pointer restores `Removed` from Git and uninstalls it | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/README.md` (Rules for changes) | [Install components by CLI][comp-cli] |
| Data to back up first: MLflow PostgreSQL PVC and the `rhoai-mlflow-artifacts` bucket (preserve by policy), the MaaS PostgreSQL database | `docs/OPERATIONS.md` (Object storage purposes and preservation), `gitops/stages/050-model-evaluation/050-mlflow/`, `gitops/stages/040-governed-models-as-a-service/040-maas-database/` | [Back up storage data][backup] |
| Cost shutdown is not uninstall: GPU MachineSets scale to zero and resume | `scripts/platform/resume-gpu-demo.sh`, `docs/OPERATIONS.md` (Resuming GPU-Backed Stages After Shutdown) | — |

## Procedure

1. Confirm intent (decommission, not shutdown) and the target cluster; pass the
   OpenShift safety guard in `AGENTS.md`.
2. Back up the data in the table above ([Back up storage data][backup]).
3. Delete Stages 070 to 020 per `docs/OPERATIONS.md#cleanup-guidance`
   (`python3 scripts/shared/stage_apps.py names <stage> --all --reverse`).
4. For Stage 010, delete the RHOAI Applications without cascade so Argo CD
   stops reconciling but the operator stays to run its own removal:

   ```bash
   argocd app delete 010-rhoai-platform --cascade=false
   argocd app delete 010-rhoai-operator --cascade=false
   ```

5. Run the official [CLI uninstall][cli] (it labels a ConfigMap in
   `redhat-ods-operator`; the operator then removes its resources and the
   namespace goes last).
6. Review what remains: user projects, user-created CRs and CRDs are kept by
   design. Delete them only with the user's approval; then cascade-delete the
   other Stage 010 Applications (ODF, observability operators, access).

   ```bash
   oc get subscription -n redhat-ods-operator rhods-operator --ignore-not-found
   oc get ns redhat-ods-applications redhat-ods-operator --ignore-not-found
   oc get crd -o name | grep -E 'opendatahub|kserve' | head
   ```

Not exercised in this repo: steps 4 to 6 have no recorded live run. Record the
outcome in `docs/OPERATIONS.md` when they are.

## Pitfalls

- Cascade-deleting `010-rhoai-operator` removes the Subscription and namespace
  directly; that is not the documented uninstall.
- If the `argocd` CLI is unavailable, use the OpenShift GitOps UI
  (`docs/OPERATIONS.md#cleanup-guidance`); check `argocd version` first.
- The console plugin list (`010-console-observability`) is `Prune/Delete=false`;
  review it by hand after uninstall.
- Never commit backups, kubeconfigs or uninstall logs.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Uninstall | [Uninstall OpenShift AI Self-Managed][chapter], [Understanding the uninstallation process][understand], [Uninstall by CLI][cli] |
| Backups | [Back up storage data][backup], [Cluster backup][cluster-backup] |
| Component states | [Install components by CLI][comp-cli] |

## Related skills

`manage-resources`, `resume-gpu-demo`, `gitops-move-applications`,
`rhoai-installation-troubleshooting`, `rhoai-dsci-dsc-configuration`,
`odf-object-bucket-claims`.

[chapter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#uninstalling-openshift-ai-self-managed_uninstalling-openshift-ai-self-managed
[understand]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#understanding-the-uninstallation-process_uninstalling-openshift-ai-self-managed
[cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#uninstalling-openshift-ai-self-managed-using-cli_uninstalling-openshift-ai-self-managed
[comp-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-components-using-cli_component-install
[backup]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#backing-up-storage-data_data-mgmt
[cluster-backup]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#backing-up-your-cluster_data-mgmt
