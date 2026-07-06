# Official Doc Extraction

Use this extraction to keep OCP observability content grounded in the official
OCP sources. When implementation needs exact monitoring, logging, or Cluster
Observability Operator fields, verify the separate Red Hat documentation and
active cluster schema before authoring manifests.

## OCP-Level Observability Definition

The official Observability overview frames Red Hat OpenShift Observability as
real-time visibility, monitoring, and analysis of metrics, logs, traces, and
events so users can diagnose and troubleshoot issues before they affect systems
or applications.

The overview identifies these Observability components:

- Monitoring
- Logging
- Distributed tracing
- Red Hat build of OpenTelemetry
- Network Observability
- Power monitoring

It also states that Red Hat OpenShift Observability connects open-source tools
and technologies into a unified solution whose components help collect, store,
deliver, analyze, and visualize data.

## Release Cadence Boundary

The Observability overview states that, except for monitoring, Red Hat
OpenShift Observability components have release cycles separate from core OCP
release cycles.

Implications for this repo:

- OCP 4.20 is the platform baseline, but it does not by itself pin a detailed
  Logging, COO, OpenTelemetry, distributed tracing, Network Observability, or
  Power monitoring operator version.
- Do not hard-code non-monitoring observability Operator channels, CRD schemas,
  or custom resource fields from the OCP baseline alone.
- Pin or capture separate Red Hat observability product documentation before
  creating detailed reusable skills for those components.

## Monitoring

The official Monitoring page says to use metrics and customized alerts from the
monitoring stack to track the health and performance of applications running on
OCP clusters.

It also states:

- OCP includes a preconfigured, preinstalled, and self-updating monitoring
  stack.
- That stack provides monitoring for core platform components.
- After OCP installation, cluster administrators can optionally enable
  monitoring for user-defined projects.
- With user-defined project monitoring enabled, administrators, developers, and
  other users can specify how services and pods are monitored in their own
  projects.
- Detailed monitoring stack documentation is maintained separately as
  Monitoring stack for Red Hat OpenShift documentation.

The Observability overview adds that monitoring stack components are deployed
and managed by the Cluster Monitoring Operator, and that default components
include Prometheus, Alertmanager, Thanos Querier, and others.

The official alert notification documentation states that default platform
alerts are visible in the console after installation but are not configured to
send notifications to external systems by default. Red Hat documents supported
receiver types including webhook, email, Slack, PagerDuty, and Microsoft Teams.
The Monitoring Stack documentation shows the supported CLI path for core
platform monitoring: extract, edit, and replace the
`openshift-monitoring/alertmanager-main` Secret that contains
`alertmanager.yaml`, then validate the routing tree with `amtool`. Receiver
names alone are not enough; at least one receiver must define a real
integration for `AlertmanagerReceiversNotConfigured` to clear.

## Logging

The official Logging page says logging is used to collect, visualize, forward,
and store log data to troubleshoot issues, identify performance bottlenecks,
and detect security threats in OCP.

It also states:

- Cluster administrators can deploy logging on an OCP cluster.
- Logging can collect and aggregate node system audit logs, application
  container logs, and infrastructure logs.
- Logging can forward logs to chosen outputs, including on-cluster Red
  Hat-managed log storage.
- Logging can visualize log data in the OCP web console.
- Logging releases on a different cadence from OCP, so detailed logging
  documentation is maintained separately as Red Hat OpenShift Logging
  documentation.

Do not author collector, store, forwarder, output, retention, or query fields
from the OCP Logging overview alone.

## Cluster Observability Operator

The official Cluster Observability Operator page says COO is used to deploy and
configure observability components in OCP.

It also states that COO is optional and is designed for creating and managing
highly customizable monitoring stacks. COO helps cluster administrators
automate observability configuration and management and can provide a more
tailored and detailed namespace view than the default OCP monitoring system.

Detailed COO behavior is maintained in the standalone Red Hat OpenShift
Cluster Observability Operator documentation.

## Demo-Specific Handoff

The following are project constraints, not claims extracted from the OCP
observability overview pages:

- All active observability resources should be GitOps-managed once the new
  implementation exists.
- Do not commit observability sink credentials, tokens, external endpoint
  secrets, or sensitive log samples.
- Do not claim demo observability coverage until the corresponding manifests,
  dashboards, alerts, or validation commands exist.
- Use `rhoai-observability`, `rhoai-model-management-monitoring`, and
  `rhoai-monitoring-trustyai` for RHOAI-specific observability behavior.

Use `project-gitops-authoring` and `project-manifest-review` for repo-specific
implementation and review rules.

## Verification Before Implementation

Before implementing active observability resources, verify:

- active OCP version and Cluster Version Operator state
- default monitoring Operator state
- monitoring namespaces and pods
- user workload monitoring configuration and namespace state
- available monitoring CRDs
- available logging Operators, subscriptions, CSVs, namespaces, and CRDs
- available COO subscription, CSV, namespace, and CRDs
- exact fields for any monitoring, logging, or COO resource to be authored
- RBAC, service accounts, secrets, external outputs, and retention/storage
  settings

Discovery commands belong in `references/validation-checklist.md`; do not run
them unless the OpenShift safety guard confirms the target cluster.
