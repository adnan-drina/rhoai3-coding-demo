# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Installing |
| Official guide | Installing Red Hat Developer Hub on OpenShift Container Platform |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Preface
- Chapter 1: Red Hat Developer Hub installation methods on OpenShift Container Platform
  - Operator vs Helm chart comparison
  - baseUrl requirement
- Chapter 2: Install Red Hat Developer Hub on OpenShift Container Platform with the Operator
  - 2.1 Install the Red Hat Developer Hub Operator
    - Prerequisites (OCP 4.18–4.21, AMD64/Intel 64)
    - Update channels (fast, fast-1.10)
    - Installation mode (All namespaces)
    - Installed namespace (rhdh-operator recommended)
    - Verification
  - 2.2 Provision your custom Red Hat Developer Hub configuration
    - Secrets provisioning (secrets.txt → Secret)
    - app-config.yaml → ConfigMap
    - dynamic-plugins.yaml → ConfigMap
    - Namespace creation
  - 2.3 Use the Operator to run Developer Hub with custom configuration
    - Backstage CR (rhdh.redhat.com/v1alpha5)
    - spec.application.appConfig.configMaps
    - spec.application.dynamicPluginsConfigMapName
    - spec.application.extraEnvs (secrets, envs)
    - spec.application.extraFiles (secrets with certificates)
    - spec.application.route
    - spec.database.enableLocalDb
    - spec.deployment
- Chapter 3: Install Red Hat Developer Hub on OpenShift Container Platform with the Helm chart
  - 3.1 Deploy from OpenShift web console
    - Form view and YAML view
    - global.clusterRouterBase configuration
    - Troubleshooting CrashLoopBackOff
  - 3.2 Deploy with the Helm CLI
    - Project creation
    - helm upgrade -i with chart URL (1.10.1)
    - PostgreSQL password retrieval
    - Cluster router base detection
    - Verification (open URL in browser)

## Source Boundaries

This source is authoritative for installing Red Hat Developer Hub 1.10 on a
connected OpenShift Container Platform cluster. It covers the Operator
installation via OperatorHub, Helm chart deployment via web console or CLI,
custom configuration provisioning (config maps, secrets, dynamic plugins),
Backstage CR creation, and post-installation verification.

It does **not** cover:
- Air-gapped or disconnected installation (separate guide)
- Installation on non-OpenShift Kubernetes platforms (EKS, AKS, GKE)
- Post-installation configuration (authentication, plugins, RBAC)
- Upgrade procedures
- Uninstallation

## API Versions Documented

| Resource | apiVersion | Kind |
|----------|-----------|------|
| Backstage CR | `rhdh.redhat.com/v1alpha5` | `Backstage` |
| ConfigMap | `v1` | `ConfigMap` |
| Secret | `v1` | `Secret` |

## Related Official Sources

- Red Hat Developer Hub 1.10 "Installing in an air-gapped environment" — disconnected install
- Red Hat Developer Hub 1.10 "Administration" — post-install configuration
- Red Hat Developer Hub 1.10 "Configuring plugins" — dynamic plugins management
- Red Hat Developer Hub 1.10 "Release notes" — version changes and known issues
