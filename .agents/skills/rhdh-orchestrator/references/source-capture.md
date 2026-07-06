# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Extend |
| Official guide | Orchestrator in Red Hat Developer Hub |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/orchestrator_in_red_hat_developer_hub/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/orchestrator_in_red_hat_developer_hub/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: About Orchestrator in Red Hat Developer Hub
  - 1.1 Compatibility guide (plugin, RHDH, OCP, OSL, Serverless versions)
  - 1.2 Architecture (RHDH plugins, SonataFlow, Data Index, Job Service,
    Knative, PostgreSQL, AMQ Streams)
  - 1.3 Getting started overview
  - 1.4 Plugin dependencies for Operator installation (SonataFlowPlatform,
    NetworkPolicies, PostgreSQL auto-provisioning)
- Chapter 2: Enable Orchestrator plugin components
  - 2.1 Configure Orchestrator plugins (frontend, backend, form-widgets,
    scaffolder-backend-module, notifications, signals)
- Chapter 3: CloudEvents and Kafka integration
  - 3.1 Event-driven workflow execution concepts
  - 3.2 Enable event-driven workflows (Kafka configuration)
  - 3.3 Run workflows via UI with CloudEvents
  - 3.4 CloudEvent structure reference
- Chapter 4: Custom review pages
  - 4.1 Overview and use cases
  - 4.2 Build custom review pages (OrchestratorFormApi, ReviewComponentProps)
  - 4.3 Custom review page API reference
- Chapter 5: Operator installation
  - 5.1 Enable plugins using the Operator (ConfigMap, Backstage CR)
  - 5.2 Connect to existing PostgreSQL infrastructure
  - 5.3 Upgrade OSL Operator for RHDH 1.10
  - 5.4 Upgrade plugin ConfigMap for 1.10
  - 5.5 Resolve pod startup failure (1.8.6 upgrade)
  - 5.6 Orchestrator plugin permissions reference
  - 5.7 Manage permissions using RBAC policies
- Chapter 6: Helm installation
  - 6.1 Install using Helm CLI
  - 6.2 Install from OCP web console
  - 6.3 Connect to existing PostgreSQL using Helm
  - 6.4 Resource limits for SonataFlowPlatform
  - 6.5 Install components manually
- Chapter 7: Air-gapped installation with Operator
  - 7.1 Fully disconnected (oc mirror to disk)
  - 7.2 Partially disconnected (oc mirror to registry)
- Chapter 8: Air-gapped installation with Helm chart
  - 8.1 Fully disconnected
  - 8.2 Partially disconnected
- Chapter 9: Loki log integration
  - 9.1 Integrate Loki logs for workflow debugging
- Chapter 10: Centralized logging diagnostics
  - 10.1 Enable JSON logging (Quarkus, processInstanceId)
  - 10.2 Log rotation
  - 10.3 Link logs to traces (OpenTelemetry)

## Source Boundaries

This source is authoritative for configuring and installing the Orchestrator
plugin in Red Hat Developer Hub 1.10. It covers plugin enablement, architecture,
CloudEvent/Kafka integration, custom review pages, RBAC permissions, Operator
and Helm installation, external PostgreSQL configuration, air-gapped deployment,
Loki log integration, and SonataFlow structured logging.

It does **not** cover:
- General RHDH installation or deployment
- Scorecard plugin configuration (separate guide)
- Diagnostic data collection (separate guide)
- OpenShift Serverless or Serverless Logic Operator internals beyond
  Orchestrator integration
- SonataFlow workflow authoring (separate OSL documentation)

## API Versions Documented

| Resource | apiVersion | Kind |
|----------|-----------|------|
| Backstage CR | `rhdh.redhat.com/v1alpha5` | `Backstage` |
| SonataFlowPlatform | `sonataflow.org/v1alpha08` | `SonataFlowPlatform` |
| ConfigMap (plugins) | `v1` | `ConfigMap` |
| ConfigMap (app-config) | `v1` | `ConfigMap` |
| Secret (backend-auth) | `v1` | `Secret` |
| Subscription (OSL) | `operators.coreos.com/v1alpha1` | `Subscription` |
| ImageSetConfiguration | `mirror.openshift.io/v2alpha1` | `ImageSetConfiguration` |

## Related Official Sources

- Red Hat Developer Hub 1.10 "Scorecards" guide — Scorecard plugin
- Red Hat Developer Hub 1.10 "Collect diagnostic data" guide — must-gather
- OpenShift Serverless Logic Operator documentation — SonataFlow internals
- OpenShift Serverless documentation — Knative eventing and functions
