---
name: rhdh-monitoring
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone asks about Red Hat Developer Hub 1.10 log levels or metrics:
  setting the log level with the Operator, enabling metrics so the Operator
  creates a ServiceMonitor, or AWS/AKS monitoring. Not used in this repo: the
  Backstage CR enables no metrics. Do NOT use for audit events (use
  rhdh-audit-logs), support data (use rhdh-diagnostic-data) or cluster
  monitoring in general (use ocp-observability).
---

# Developer Hub monitoring and logging

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- Someone wants Developer Hub metrics in user workload monitoring, or more verbose backend logs.

## Not used in this repo

`gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-instance/backstage.yaml`
sets no `spec.monitoring`, so no ServiceMonitor exists for the portal.
NetworkPolicy `platform-ingress`
(`gitops/stages/070-advanced-app-platform/070-rhdh/network-policy.yaml`) already
admits the monitoring namespaces. The documented Operator path is
`spec.monitoring.enabled: true`, after which the Operator creates the
ServiceMonitor; user workload monitoring must be on.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Log levels | [Log levels][l1] |
| Set the log level with the Operator | [Set the log level with the Operator][l2] |
| Observability on OpenShift | [Observability on OpenShift][l3] |
| Metrics with the Operator | [Metrics with the Operator][l4] |
| Keycloak metrics | [Keycloak metrics][l5] |

## Related skills

`rhdh-audit-logs`, `rhdh-diagnostic-data`, `ocp-observability`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/monitoring_and_logging/index#log-levels_monitoring-and-logging
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/monitoring_and_logging/index#configure-the-log-level-with-the-rhdh-operator_log-levels
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/monitoring_and_logging/index#enable-observability-for-rhdh-on-ocp_monitoring-and-logging
[l4]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/monitoring_and_logging/index#enable-metrics-monitoring-in-a-rhdh-operator-installation-on-an-ocp-cluster_enable-observability-for-rhdh-on-ocp
[l5]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/monitoring_and_logging/index#rhbk-metrics_monitoring-and-logging-rhdh-on
