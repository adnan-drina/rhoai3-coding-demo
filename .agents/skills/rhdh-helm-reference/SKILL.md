---
name: rhdh-helm-reference
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone proposes Helm chart values for Developer Hub in this
  demo, or reads an RHDH guide that gives only a Helm example: this repo
  installs RHDH 1.10 with the Operator and the Backstage CR, never the Helm
  chart, so the skill maps common Helm values (route, database, dynamic
  plugins, extra env and files, upstream backstage values) to the Operator
  objects in Git and links the chart reference for comparison. Do NOT use to
  add a Helm release (not used here), for plugin settings (use
  rhdh-dynamic-plugins-configure), or for the Orchestrator chart (use
  rhdh-orchestrator).
---

# RHDH Helm chart reference (Operator equivalents)

Thin skill: this repo does not use the Helm chart. It keeps the Operator path
documented in [Install with the Operator][op-install]; the chart reference is
linked only to translate Helm-only examples. Detailed record:
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md`.

## When to use

- A product procedure shows only `values.yaml` and you need the Operator form.
- Reviewing a proposal to switch to Helm (answer: not without an
  architecture decision; the stage validator and hooks assume the Operator).

## Repo decisions (Helm concept → Operator object in Git)

| Helm chart concept | Operator equivalent in Git | Official section |
|---|---|---|
| Install (`helm install`) | `rhdh` Subscription `fast-1.10`, Manual approval, CSV `rhdh-operator.v1.10.6`: `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-operator/` | [Install with the Operator][op-install], [Helm install (not used)][helm-install] |
| `route.enabled` | Operator-created Route (Operator default); hostname read by the hooks: `070-rhdh/rhdh-instance/backstage.yaml` | [Route values][route] |
| `global.dynamic.plugins`, `global.dynamic.includes` | ConfigMap `dynamic-plugins-rhdh` via `dynamicPluginsConfigMapName` (`rhdh-dynamic-plugins-install`) | [Global values][global] |
| `upstream.backstage.appConfig`, `extraAppConfig` | ConfigMap `app-config-rhdh` via `spec.application.appConfig` | [Upstream values][upstream] |
| `upstream.backstage.extraEnvVars`, `extraEnvVarsSecrets`, `extraVolumes` | `spec.application.extraEnvs` (`NODE_EXTRA_CA_CERTS`; Secrets `rhdh-secrets`, `rhdh-gitlab`) and `extraFiles` (RBAC CSV, runtime catalog, cluster CA) | [Upstream values][upstream] |
| Deployment strategy (no chart key listed) | `spec.deployment.patch` with `maxSurge: 0` | [Additional upstream values][upstream-extra] |
| `upstream.postgresql.enabled` | Operator-managed local PostgreSQL StatefulSet `backstage-psql-developer-hub` (Deviation: demo) | [Upstream values][upstream] |
| `orchestrator` values, Orchestrator infrastructure chart | Not used | [Orchestrator values][orch], [Orchestrator infrastructure][orch-infra] |

## Procedure

1. Find the Helm value in the chart reference, then the matching row above;
   edit only the Operator object in Git.
2. Validate: `./stages/070-advanced-app-platform/validate.sh --static`, then,
   after the OpenShift safety guard in `AGENTS.md`, deploy with
   `./stages/070-advanced-app-platform/deploy.sh` and run `validate.sh`.
3. Compare a value read-only: `oc get backstage developer-hub -n rhdh -o yaml`.

## Pitfalls

- Helm and Operator installs of the same instance must not coexist; never run
  `helm install` against the `rhdh` namespace.
- The Operator owns the Deployment, Route and database; patch them only
  through the `Backstage` CR, or Argo CD and the Operator fight
  (`docs/TROUBLESHOOTING.md#red-hat-developer-hub-is-healthy-but-stage-070-is-outofsync`).
- `strategy.type: Recreate` through `spec.deployment.patch` yields an invalid
  Deployment because the Operator keeps its `rollingUpdate` block; use
  `maxSurge: 0` (comment in `backstage.yaml`).

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Chart values | [List values with Helm CLI][list], [Root][root], [Global][global], [Route][route], [Test][test], [Upstream][upstream], [Additional upstream][upstream-extra] |
| Orchestrator (not used) | [Orchestrator values][orch], [Orchestrator infrastructure][orch-infra] |
| Install paths | [Operator (used)][op-install], [Helm chart (not used)][helm-install] |

## Related skills

`rhdh-install-ocp`, `rhdh-configure`, `rhdh-dynamic-plugins-install`,
`rhdh-getting-started-setup`, `rhdh-orchestrator`.

[op-install]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index#install-rhdh-on-ocp-with-the-operator_installing-rhdh-on-ocp
[helm-install]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index#install-rhdh-on-ocp-with-the-helm-chart_installing-rhdh-on-ocp
[list]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/helm_chart_configuration_reference/index#display-a-complete-list-of-helm-chart-values-with-helm-cli_helm-chart-configuration-reference
[root]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/helm_chart_configuration_reference/index#root-namespace-value_helm-chart-configuration-reference
[global]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/helm_chart_configuration_reference/index#global-namespace-values_helm-chart-configuration-reference
[orch]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/helm_chart_configuration_reference/index#orchestrator-namespace-values_helm-chart-configuration-reference
[route]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/helm_chart_configuration_reference/index#route-namespace-values_helm-chart-configuration-reference
[test]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/helm_chart_configuration_reference/index#test-namespace-values_helm-chart-configuration-reference
[upstream]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/helm_chart_configuration_reference/index#upstream-namespace-values_helm-chart-configuration-reference
[upstream-extra]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/helm_chart_configuration_reference/index#additional-upstream-chart-values_helm-chart-configuration-reference
[orch-infra]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/helm_chart_configuration_reference/index#helm-chart-orchestrator-infrastructure-reference_helm-chart-config-reference
