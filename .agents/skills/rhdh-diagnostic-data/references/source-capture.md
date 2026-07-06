# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Observability |
| Official guide | Collect diagnostic data to streamline support resolution |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/collect_diagnostic_data_to_streamline_support_resolution/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/collect_diagnostic_data_to_streamline_support_resolution/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Diagnostic data collection overview
  - Technology Preview support posture
  - Typical collection sizes (10-50 MB basic, 500 MB-2 GB with heap dumps)
  - Security/privacy considerations
- Chapter 2: Run must-gather on OpenShift
  - Prerequisites (cluster-admin or RBAC, authenticated `oc`)
  - Basic and advanced collection commands
  - Verification
- Chapter 3: Run must-gather on Kubernetes
  - Helm-based install, wait, extract, cleanup workflow
  - Verification
- Chapter 4: Air-gapped clusters with mirrored must-gather image
  - Partially and fully disconnected mirroring via `skopeo`
  - Image pull authentication (OCP global pull secret, K8s docker-registry secret)
  - Running must-gather with mirrored image
  - Troubleshooting (ImagePullBackOff, certificate errors)
- Chapter 5: Diagnostic data types and collection scope
  - 5.1 Default-enabled collectors (platform, helm, operator, orchestrator,
    route-ingress, namespace-inspect)
  - 5.2 Opt-in collectors (cluster-info, heap-dumps)
- Chapter 6: Collect heap dumps to diagnose memory issues
  - Inspector protocol vs SIGUSR2 methods
  - Operator and Helm deployment configurations
  - Liveness probe timeout configuration
  - Timeout adjustment for large memory footprints
- Chapter 7: Configuration options
  - 7.1 Command-line flags
  - 7.2 Environment variables
  - 7.3 Helm chart values
- Chapter 8: Diagnostic data output structure
  - 8.1 Top-level directory structure
  - 8.2 Heap dump file locations
  - 8.3 Common diagnostic data locations

## Source Boundaries

This source is authoritative for collecting diagnostic data from Red Hat
Developer Hub 1.10 deployments using the must-gather tool. It covers OpenShift
and Kubernetes collection workflows, air-gapped mirroring, heap dump collection,
collector configuration, and output structure.

It does **not** cover:
- General RHDH installation or deployment
- Scorecard plugin configuration (separate guide)
- Orchestrator plugin configuration (separate guide)
- RHDH troubleshooting beyond diagnostic data collection
- Support ticket submission procedures

## Related Official Sources

- Red Hat Developer Hub 1.10 "Evaluate project health using Scorecards" —
  Scorecard plugin configuration
- Red Hat Developer Hub 1.10 "Orchestrator" guide — serverless workflows
- Red Hat OpenShift Container Platform "Gathering data about your cluster" —
  general must-gather usage
