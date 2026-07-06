# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_microsoft_azure_kubernetes_service_aks/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/installing_red_hat_developer_hub_on_microsoft_azure_kubernetes_service_aks/index |
| Documentation category | Install |
| Official guide | Installing Red Hat Developer Hub on Microsoft Azure Kubernetes Service (AKS) |
| Capture date | 2026-07-06 |

## Captured Sections

From Installing Red Hat Developer Hub on Microsoft Azure Kubernetes Service
(AKS):

- Chapter 1: Install Developer Hub on AKS by using the Operator
  - 1.1 Install the Operator on AKS by using OLM
  - 1.2 Provision your custom Red Hat Developer Hub configuration
  - 1.3 Provision your Red Hat Container Registry pull secret to your RHDH
    instance namespace
  - 1.4 Use the Red Hat Developer Hub Operator to run Developer Hub with your
    custom configuration
  - 1.5 Expose your Operator-based Developer Hub instance on AKS
- Chapter 2: Deploy Developer Hub on AKS with the Helm chart

## Source Boundaries

This skill captures the full AKS installation guide covering both Operator and
Helm chart installation methods, including AKS-specific pull secret
provisioning, Ingress configuration, and Backstage CR authoring.

It does not capture:

- RHDH configuration beyond initial deployment (authentication, authorization,
  plugins, catalog)
- RHDH on other platforms (EKS, GKE, OpenShift, OSD)
- RHDH upgrade or day-2 operations
- RHDH architecture or conceptual overview

## Related Official Sources To Add Later

- Red Hat Developer Hub 1.10 Configuring documentation
- Red Hat Developer Hub 1.10 Customizing documentation
- Red Hat Developer Hub 1.10 Installing on OpenShift Container Platform
