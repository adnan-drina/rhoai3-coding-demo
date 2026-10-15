---
name: ocp-grafana-operator
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when someone proposes Grafana, the Grafana Operator, GrafanaDashboard or
  GrafanaDatasource for this repo, or follows a "MaaS Grafana" entry in
  docs/TROUBLESHOOTING.md. The repo deploys no Grafana: dashboards are console
  dashboards and Perses (COO UIPlugin, PersesDashboard). Do NOT use for
  monitoring configuration or Perses dashboards (use ocp-observability) or
  RHOAI model metrics (use rhoai-observability).
---

# OCP Grafana Operator (not deployed)

Thin skill: this repo does not install the Grafana Operator or any Grafana
instance, and the doc map has no Red Hat product for it. The dashboard paths
in use are console dashboards and the Cluster Observability Operator Perses
plugin. This skill exists to stop new Grafana
work and to route dashboard work to what is deployed.

## When to use

- A change or plan mentions `Grafana`, `GrafanaDashboard`, `GrafanaDatasource`
  or a Grafana Route/OAuth proxy.
- A user follows `docs/TROUBLESHOOTING.md#maas-grafana-dashboard-shows-no-data`
  or the other "MaaS Grafana ..." entries.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| No Grafana Operator Subscription, instance, datasource or dashboard CR anywhere in Git | — (search: no `kind: Grafana*` under `gitops/`) | — |
| Cluster dashboards: Perses through the COO `UIPlugin` `monitoring` | `gitops/stages/010-openshift-ai-platform-foundation/010-console-observability/monitoring-uiplugin.yaml` | [COO UI plugins][coo-ui] |
| GPU dashboard: upstream DCGM JSON shipped as a console dashboard ConfigMap (`console.openshift.io/dashboard: "true"`) | `gitops/stages/020-gpu-infrastructure-private-ai/020-nvidia-gpu-operator/console-dashboard/` | [About OpenShift monitoring][monitoring] |
| MaaS cost and tokenomics tabs: `PersesDashboard` objects in `redhat-ods-monitoring`, maintained directly as YAML | `gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/` | [Perses dashboards][perses] |

## Procedure

1. For a new dashboard, extend the Perses or console-dashboard path above
   (see `ocp-observability`); do not add a Grafana Operator.
2. If Grafana is truly required, treat it as a new component: record the
   decision in `BACKLOG.md`, state the support posture (community operator,
   not a Red Hat product), and follow `.agents/rules/gitops.md`.

## Pitfalls

- The `docs/TROUBLESHOOTING.md` "MaaS Grafana Route ...", "... OAuth Login
  Returns 403", "... Shows 401" and "... Shows No Data" entries describe a
  retired Grafana deployment; nothing in Git creates those objects now.
- Grafana field names, CRD versions and catalog sources are not Red Hat
  product documentation; do not cite them as product authority.

## Official documentation

| Topic | Section |
|---|---|
| Console dashboards (OCP 4.22) | [About OpenShift monitoring][monitoring] |
| Perses dashboards (COO 1-latest) | [Monitoring UI plugin][coo-ui], [Perses dashboards][perses] |

## Related skills

`ocp-observability`, `rhoai-observability`, `ocp-web-console`.

[monitoring]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/monitoring/index#about-ocp-monitoring
[coo-ui]: https://docs.redhat.com/en/documentation/red_hat_openshift_cluster_observability_operator/1-latest/html-single/ui_plugins_for_red_hat_openshift_cluster_observability_operator/index#monitoring-ui-plugin
[perses]: https://docs.redhat.com/en/documentation/red_hat_openshift_cluster_observability_operator/1-latest/html-single/ui_plugins_for_red_hat_openshift_cluster_observability_operator/index#perses-dashboard
