---
name: rhdh-dynamic-plugins-configure
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when changing or reviewing how this demo configures Developer Hub
  plugins: the Kubernetes, Topology, Tekton and Argo CD plugins in
  dynamic-plugins-rhdh and app-config-rhdh, the entity annotations the
  catalog and templates set (backstage.io/kubernetes-id, janus-idp.io/tekton,
  argocd/app-name), the rhdh-kubernetes-reader identity, the cluster CA, and
  tabs that show "Problem retrieving Kubernetes objects". Do NOT use for
  installing or packaging plugins (use rhdh-dynamic-plugins-install), plugin
  support tiers (use rhdh-dynamic-plugins-reference), or authentication and
  RBAC (use rhdh-authentication, rhdh-authorization).
---

# RHDH dynamic plugin configuration

Thin skill: repo decisions and pitfalls here, product procedure in the linked
Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/rhdh/README.md` ("Plugins", "Trust").

## When to use

- A change touches `rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`,
  the `kubernetes:` or `argocd:` blocks of `app-config-configmap.yaml`, or
  `kubernetes-reader.yaml`.
- An entity's Topology, CI or Argo CD tab is empty or shows an error.
- A template skeleton's `catalog-info.yaml` annotations change.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Kubernetes plugin: one `config` cluster `local-cluster`, `authProvider: serviceAccount`, token from `rhdh-secrets`, `caFile` from the mounted `kube-root-ca.crt` | `gitops/stages/070-advanced-app-platform/rhdh/rhdh-instance/app-config-configmap.yaml` | [Kubernetes plugin annotations][topo-annot] |
| Plugin identity `rhdh-kubernetes-reader` bound to the built-in ClusterRole `view` (Gap: broader than the documented read-only ClusterRole) | `rhdh/rhdh-instance/kubernetes-reader.yaml` | [Enable the Tekton plugin][tekton] |
| `customResources`: Tekton `pipelineruns`, `taskruns` (`tekton.dev/v1`) and OpenShift `routes` | `app-config-configmap.yaml` | [View OpenShift routes][topo-routes], [View Tekton PipelineRuns][topo-tekton] |
| Tekton frontend mounted at `entity.page.ci/cards` (`TektonCI`, guarded by `isTektonCIAvailable`) | `rhdh/rhdh-instance/dynamic-plugins-configmap.yaml` | [Enable the Tekton plugin][tekton] |
| Argo CD: Community frontend with the Roadie backend, one `config` instance `main` with a reader token (Gap: the guide recommends Community with Community) | `dynamic-plugins-configmap.yaml`, `app-config-configmap.yaml` | [Enable the Argo CD plugin][argocd] |
| Entities link to cluster objects with `backstage.io/kubernetes-id`, `janus-idp.io/tekton` and `argocd/app-name` | `rhdh/catalog/all.yaml`, `rhdh/templates/*/skeleton/catalog-info.yaml` | [Enable the Tekton plugin][tekton], [Kubernetes plugin annotations][topo-annot] |
| `kubernetes` listed in `permission.rbac.pluginsWithPermission`; developers get only `kubernetes.clusters.read` and `kubernetes.resources.read` | `app-config-configmap.yaml`, `rhdh/rhdh-instance/rbac-policy.yaml` | see `rhdh-authorization` |
| Argo CD reader token and Kubernetes token are written into `rhdh-secrets` by the configure hook, never in Git | `rhdh/jobs/configure-rhdh.yaml` | — (repo pattern) |

## Procedure

1. Change plugin config only in the two ConfigMaps above; keep the Tekton and
   Argo CD packages as digest-pinned OCI references (`rhdh-dynamic-plugins-install`).
2. Static checks: `./stages/070-advanced-app-platform/validate.sh --static`
   (`stage070-upgrade.test.py`: `test_argo_plugins_follow_110_oci_packaging`,
   `test_tekton_frontend_is_wired_and_migration_requires_hub`;
   `security-boundaries.test.py`).
3. After the OpenShift safety guard in `AGENTS.md`, sync `070-rhdh` through
   `./stages/070-advanced-app-platform/deploy.sh` and run `validate.sh`.
4. Read-only checks:

   ```bash
   oc auth can-i list pods --as=system:serviceaccount:rhdh:rhdh-kubernetes-reader -A
   oc get configmap dynamic-plugins-rhdh -n rhdh -o jsonpath='{.data.dynamic-plugins\.yaml}'
   oc logs deployment/backstage-developer-hub -n rhdh -c backstage-backend --tail=200 | grep -i -E 'kubernetes|argocd|tekton'
   ```

## Pitfalls

- `caFile` alone does not work: RHDH's `global-agent` drops the plugin's
  agent, so the cluster CA must be trusted through `NODE_EXTRA_CA_CERTS`
  (`backstage.yaml`). Never use `NODE_TLS_REJECT_UNAUTHORIZED=0`; see
  `docs/TROUBLESHOOTING.md#developer-hub-topologycikubernetes-tabs-show-problem-retrieving-kubernetes-objects`.
- The Operator disables ServiceAccount token automount, so
  `/var/run/secrets/...` does not exist in the pod; the CA comes from the
  `kube-root-ca.crt` ConfigMap through `extraFiles`.
- The 1.10 Argo CD section documents `argocd/app-selector` and
  `argocd/instance-name`; the repo's `argocd/app-name` is not in that
  section (unverified against 1.10).
- Mixing Community and Roadie Argo CD plugins is "not recommended"
  ([Install and configure Argo CD][argocd-ch]); the current mix is a recorded Gap.
- Operator defaults and hook-patched fields can make `070-rhdh` OutOfSync while
  healthy: `docs/TROUBLESHOOTING.md#red-hat-developer-hub-is-healthy-but-stage-070-is-outofsync`.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Argo CD plugin | [Install and configure Argo CD][argocd-ch], [Enable the Argo CD plugin][argocd] |
| Tekton plugin | [Enable the Tekton plugin][tekton] |
| Topology plugin | [Install the Topology plugin][topo], [Configure][topo-config], [Labels and annotations][topo-labels] |
| Bulk Import, Kubernetes custom actions (not used) | [Bulk importing][bulk], [Kubernetes custom actions][k8s-actions] |
| Core backend service overrides (not used) | [Override core backend service configuration][override] |

## Related skills

`rhdh-dynamic-plugins-install`, `rhdh-dynamic-plugins-reference`,
`rhdh-dynamic-plugins-usage`, `rhdh-configure`, `rhdh-authorization`,
`ocp-gitops-operator`.

[argocd-ch]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#install-and-configure-argo-cd_configuring-dynamic-plugins
[argocd]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#enable-the-argo-cd-plugin_install-and-configure-argo-cd
[tekton]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#enable-the-tekton-plugin_configuring-dynamic-plugins
[topo]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#install-the-topology-plugin_configuring-dynamic-plugins
[topo-config]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#configure-the-topology-plugin_install-the-topology-plugin
[topo-routes]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#view-openshift-routes_configure-the-topology-plugin
[topo-tekton]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#view-tekton-pipelineruns_configure-the-topology-plugin
[topo-labels]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#manage-labels-and-annotations-for-topology-plugins_install-the-topology-plugin
[topo-annot]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#add-entity-annotations-and-labels-for-the-kubernetes-plugin_manage-labels-and-annotations-for-topology-plugins
[bulk]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#bulk-importing-in-rhdh_install-the-topology-plugin
[k8s-actions]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#kubernetes-custom-actions-in-rhdh_install-the-topology-plugin
[override]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index#override-core-backend-service-configuration_install-the-topology-plugin
