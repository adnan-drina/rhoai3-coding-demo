# Red Hat OpenShift AI operator (`010-rhoai-operator`)

This Application installs the Red Hat OpenShift AI (RHOAI) Operator through OLM. It delivers the operator only. The
platform configuration (DSCInitialization, DataScienceCluster, Auth, dashboard configuration) lives in
[`010-rhoai-platform`](../010-rhoai-platform/README.md). Every later stage that uses OpenShift AI depends on this operator.

| | |
|---|---|
| Argo CD Application | `010-rhoai-operator` ([manifest](../../../applications/010-rhoai-operator.yaml)) |
| Deployed by | [`stages/010-openshift-ai-platform-foundation/deploy.sh`](../../../../stages/010-openshift-ai-platform-foundation/deploy.sh) (deploy-order 1) |
| Validated by | [`validate.sh`](../../../../stages/010-openshift-ai-platform-foundation/validate.sh) (Application Synced/Healthy at the reviewed revision; `rhods-operator` CSV `Succeeded`); `check_operator_policy` in `scripts/lib.sh` --verify` (channel and minimum version) |
| Sync | Automated, prune and self-heal; `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`; Server-Side Diff via the `compare-options` annotation |
| Depends on | OpenShift GitOps bootstrap (`deploy.sh` steps 1-3) and the `redhat-operators` catalog source |
| Used by | `010-rhoai-platform` (needs the RHOAI CRDs) and every later stage that uses OpenShift AI APIs |

## Why

OpenShift AI is installed and upgraded by its operator, which owns the CRDs and all generated components. The
documented CLI method creates a Namespace, an OperatorGroup and a Subscription in `redhat-ods-operator` [1]. This
component holds exactly those three objects. The operator lifecycle (channel, approval) is separate from the
platform configuration, so it has its own Application. Changing the channel then never re-syncs the DSC.

## What

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `redhat-ods-operator` | (cluster) | Operator namespace. Label `openshift.io/cluster-monitoring: "true"` |
| OperatorGroup | `rhods-operator-group` | `redhat-ods-operator` | No `targetNamespaces` (AllNamespaces mode), as in the documented example [1] |
| Subscription | `rhods-operator` | `redhat-ods-operator` | Channel `stable-3.5`, `installPlanApproval: Automatic`, source `redhat-operators`; env `DISABLE_DSC_CONFIG=true` |

No sync waves or hooks. The kustomization adds `argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true` to
every object.

Not in Git (owned by OLM and the operator): the InstallPlan, the CSV (live `rhods-operator.3.5.1`), the CRDs, the
operator Deployment, and the `redhat-ods-applications` namespace the operator creates later.

## How

- **Channel and approval.** `stable-3.5` is a version-pinned stable channel. The documentation lists `stable-x.y` as a
  valid channel value [1] and gives it seven months of full support with a release every three months [2].
  Approval is `Automatic`, so z-stream updates within 3.5 install without review. The repository accepts this on
  purpose: `check_operator_policy` in `scripts/lib.sh` refuses any channel other than `stable-3.5` and any installed
  version below the qualified minimum `3.5.1` or outside the 3.5 minor. No `startingCSV` is set.
- **`DISABLE_DSC_CONFIG=true`.** This stops the operator from creating the default DSCInitialization, so
  `010-rhoai-platform` can create `default-dsci` from Git with the monitoring stack configured [3]. This environment
  variable is documented in the upstream Open Data Hub operator [3], not in the RHOAI 3.5 installation guide [1]. Do not
  remove it while `010-rhoai-platform` owns the DSCI. Removing it would let the operator create a DSCI that GitOps then
  has to adopt.
- **Ordering.** `deploy.sh` applies all deploy-order Applications in one `oc apply`. Ordering against
  `010-rhoai-platform` therefore comes from Argo CD retry (limit 10, backoff 5s to 3m) and
  `SkipDryRunOnMissingResource`, not from a wait in the script. Before applying, `deploy.sh` runs
  `check_operator_policy` to check the catalog. After applying, it waits up to 1800 s for the CSV to succeed.
- **Credentials.** None.
- **Cluster-specific values.** None. `deploy.sh` stamps `repoURL` and the reviewed commit SHA on the Application.

## Validation

`validate.sh` checks that the Subscription's `installedCSV` is in phase `Succeeded`. `stage-apps.sh status 010` also
requires the Application to be Synced and Healthy at the reviewed revision. Check by hand:

```bash
oc get subscription rhods-operator -n redhat-ods-operator -o jsonpath='{.spec.channel} {.status.installedCSV}{"\n"}'
oc get csv -n redhat-ods-operator -l operators.coreos.com/rhods-operator.redhat-ods-operator
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Installation method | CLI: Namespace `redhat-ods-operator`, OperatorGroup, Subscription `rhods-operator` from `redhat-operators` [1] | Same three objects, same names except the OperatorGroup name | Aligned |
| OperatorGroup scope | The example has no `spec` (AllNamespaces) [1] | No `targetNamespaces` | Aligned |
| Update channel | One of `fast`, `fast-x.y`, `stable`, `stable-x.y`, `eus-x.y`, `alpha` [1]; `stable-x.y` gets 7 months of full support [2] | `stable-3.5` | Aligned |
| Update approval | The CLI example sets no approval mode [1] | `Automatic`, bounded by the repository version policy | Deviation (justified: demo follows z-streams; the policy script enforces minor and minimum version) |
| Default DSCI creation | Not covered by the RHOAI 3.5 guide; upstream operator documents `DISABLE_DSC_CONFIG` [3] | Set to `true`; GitOps creates the DSCI | Deviation (justified: GitOps owns the DSCI; upstream-only setting, see findings) |
| Cluster monitoring label | Not stated in [1] | `openshift.io/cluster-monitoring: "true"` on the namespace | Aligned (additive) |

## References

1. Installing and deploying OpenShift AI, Install the Red Hat OpenShift AI Operator by using the CLI. Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install#installing-openshift-ai-operator-using-cli_operator-install
2. Understanding update channels. Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/understanding-update-channels_install
3. opendatahub-operator README, Usage: Configuration and Installation (`DISABLE_DSC_CONFIG`) (upstream). https://github.com/opendatahub-io/opendatahub-operator
