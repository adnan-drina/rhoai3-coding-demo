# Console observability and plugin list (`010-console-observability`)

This Application adds Perses dashboards to the OpenShift web console. It enables the Cluster Observability Operator
monitoring UI plugin with Perses. It also owns the full list of enabled console plugins on the cluster `Console`
operator configuration. Users see **Observe > Dashboards (Perses)** and can pick the RHOAI monitoring project. Every
stage that installs a console plugin (GitOps, ODF, Connectivity Link, Lightspeed, Pipelines) depends on this list.

| | |
|---|---|
| Argo CD Application | `010-console-observability` ([manifest](../../../applications/010-console-observability.yaml)) |
| Deployed by | Its own script, [`stages/010-openshift-ai-platform-foundation/deploy-console-observability.sh`](../../../../stages/010-openshift-ai-platform-foundation/deploy-console-observability.sh) (annotation `demo.rhoai.io/deploy-script`). Stage 010 `deploy.sh` calls it after the deploy-order components |
| Validated by | [`validate-console-observability.sh`](../../../../stages/010-openshift-ai-platform-foundation/validate-console-observability.sh) (called by `validate.sh` and by the deploy script) |
| Sync | Automated, prune and self-heal; `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`; Server-Side Diff via annotation. The `Console` object uses resource-level `ServerSideApply=true,Prune=false,Delete=false` |
| Depends on | `010-observability-operators` (COO provides the `UIPlugin` CRD and the Perses operator); `010-rhoai-platform` (RHOAI generates the dashboards and datasources Perses shows) |
| Used by | Console users and personas; every component that installs a `ConsolePlugin` listed here |

## Why

COO delivers console UI plugins through the cluster-scoped `UIPlugin` resource. The documented way to enable Perses
dashboards is a `UIPlugin` named `monitoring` of `type: Monitoring` with `monitoring.perses.enabled: true` [1].

The console loads a dynamic plugin only when its `ConsolePlugin` name is in `spec.plugins` of
`consoles.operator.openshift.io/cluster` [2]. The documented CLI method appends one name with a JSON patch [2].
`spec.plugins` is a single list. Any writer that sends the whole list replaces it, and on this cluster entries were
lost twice (2026-10-12 and 2026-10-13) when other writers rewrote it. The repository therefore declares the complete
list in Git and lets self-heal restore it. The `console-plugins.yaml` comment records this history.

The plugin list and the UIPlugin are console configuration with their own redeploy path. They sit in a separate
Application from the foundation components.

## What

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| UIPlugin | `monitoring` | (cluster) | `type: Monitoring`, `perses.enabled: true` |
| Console (`operator.openshift.io/v1`) | `cluster` | (cluster) | Owns only `spec.plugins`: `monitoring-plugin`, `networking-console-plugin`, `monitoring-console-plugin`, `gitops-plugin`, `odf-console`, `kuadrant-console-plugin`, `lightspeed-console-plugin`, `pipelines-console-plugin` |

There are no sync waves or hooks.

The `Console` object has `argocd.argoproj.io/sync-options: ServerSideApply=true,Prune=false,Delete=false`. Argo CD
applies it with server-side apply, so it owns only the fields in Git. Deleting the file or the Application never
deletes the cluster singleton [3].

Not in Git (COO-owned, generated from the UIPlugin): the `monitoring-console-plugin` ConsolePlugin and its Deployment,
and the console `Perses` server with its StatefulSet in `openshift-cluster-observability-operator`. The other listed
ConsolePlugin objects belong to the operators that install them (OpenShift, GitOps, ODF, Connectivity Link, Lightspeed,
Pipelines).

## How

- **Own deploy script.** `deploy-console-observability.sh` checks the following before its first write:
  - the Stage 010 source matches the selected, published commit (`stage_apps.py select`);
  - an existing Application has the expected identity;
  - an existing `UIPlugin/monitoring` has no owner, is not being deleted, has no foreign tracking id, and has exactly
    the reviewed spec.

  It then applies the Application pinned to the commit and waits up to 600 s for the validator to pass.
- **Server-side apply on one object.** `.agents/rules/gitops.md` forbids `ServerSideApply=true` at the Application
  level. Here it is set on the `Console` resource only, so Argo CD owns `spec.plugins` and nothing else on the shared
  singleton [3].
- **Adding a plugin.** Add its name to `console-plugins.yaml` and publish. Do not `oc patch` the list: self-heal
  reverts the patch. A listed plugin whose `ConsolePlugin` is not installed yet is skipped by the console. Example:
  `pipelines-console-plugin` before Stage 070.
- **Credentials.** None. Perses datasource access follows the user's project permissions (see `docs/OPERATIONS.md`,
  "Stage 010 console observability component").
- **Cluster-specific values.** None.

## Validation

`validate-console-observability.sh` checks the following:

- The Application is Synced and Healthy, and its last operation succeeded at its 40-character `targetRevision`.
- The `UIPlugin` has Perses enabled and carries this Application's tracking id.
- Every declared plugin that is installed is enabled.
- Every installed `ConsolePlugin` is declared in Git.
- Exactly one UIPlugin-owned Perses is `Available`.
- The UIPlugin-owned Deployments and the Perses StatefulSet are fully rolled out.

```bash
oc get console.operator.openshift.io cluster -o jsonpath='{.spec.plugins}{"\n"}'; oc get consoleplugins
oc get uiplugin monitoring -o jsonpath='{.spec}{"\n"}'; oc get perses -n openshift-cluster-observability-operator
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Perses in the console | `UIPlugin` `monitoring`, `type: Monitoring`, `perses.enabled: true` [1] | Same | Aligned |
| Enabling plugins | Add the `ConsolePlugin` name to `spec.plugins`; CLI example appends with a JSON patch [2] | Full list declared in Git, applied by SSA, restored by self-heal | Deviation (justified: append-only writers lost entries; one declared owner is reproducible) |
| Shared singleton safety | Resource-level `Prune=false`, `Delete=false`, `ServerSideApply=true` (upstream) [3] | Set on `Console/cluster` | Aligned |
| COO version | 1.5.3 released [4] | Live 1.5.3 (installed by `010-observability-operators`) | Aligned |

## References

1. UI plugins for Red Hat OpenShift Cluster Observability Operator, Enable the monitoring plugin to use Perses dashboards. Cluster Observability Operator 1-latest (no 1.5-specific page is published). https://docs.redhat.com/en/documentation/red_hat_openshift_cluster_observability_operator/1-latest/html-single/ui_plugins_for_red_hat_openshift_cluster_observability_operator/index
2. Web console, Dynamic plugins: Enable a dynamic plugin with the CLI. OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/web_console/dynamic-plugins
3. Sync Options: No Prune Resources, No Resource Deletion, Server-Side Apply (upstream). Argo CD. https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
4. Cluster Observability Operator release notes. Cluster Observability Operator 1-latest. https://docs.redhat.com/en/documentation/red_hat_openshift_cluster_observability_operator/1-latest/html/red_hat_openshift_cluster_observability_operator_release_notes
