# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Installing |
| Official guide | Installing Red Hat Developer Hub in an air-gapped environment |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_in_an_air-gapped_environment/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_in_an_air-gapped_environment/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Air-gapped environment
  - Fully disconnected vs partially disconnected definitions
- Chapter 2: Install Red Hat Developer Hub in an air-gapped environment with the Operator
  - 2.1 Fully disconnected with Operator
    - Prerequisites (tools: oc-mirror, opm, Podman 5.3+, Skopeo 1.20+, umoci, yq 4.44+)
    - Download mirroring script (prepare-restricted-environment.sh)
    - Mirror to disk (--to-dir)
    - Install from disk (install.sh --from-dir)
    - Update cluster pull secret
    - Kubernetes pull secret alternative
    - Plugin mirroring (mirror-plugins.sh --to-dir / --from-dir)
    - registries.conf ConfigMap
    - Mount in Backstage CR (extraFiles.configMaps with containers selector)
    - Optional signature verification (policy.json)
    - Verification
  - 2.2 Partially disconnected with Operator
    - Prerequisites (oc-mirror recommended)
    - Download and run mirroring script (--to-registry)
    - Update cluster pull secret
    - Kubernetes pull secret alternative
    - Plugin mirroring (--to-registry)
    - registries.conf ConfigMap and mount
    - Optional signature verification
    - Verification
- Chapter 3: Install on OCP in an air-gapped environment with Helm chart
  - 3.1 Fully disconnected with Helm (OCP)
    - ImageSetConfiguration (mirror.openshift.io/v2alpha1)
    - oc mirror --v2 to disk
    - oc mirror --v2 from disk to registry
    - Apply IDMS/ITMS manifests
    - Update cluster pull secret
    - helm install from workspace chart archive
    - Plugin mirroring
    - registries.conf in Helm values (extraVolumes + initContainers)
    - Helm merge limitation warning
    - Optional signature verification
  - 3.2 Partially disconnected with Helm (OCP)
    - ImageSetConfiguration
    - oc mirror --v2 direct to registry
    - Apply IDMS/ITMS manifests
    - Update cluster pull secret
    - helm install
    - Plugin mirroring
    - registries.conf in Helm values
- Chapter 4: Install on supported Kubernetes in air-gapped environment with Helm
  - 4.1 Fully disconnected (AKS, EKS, GKE)
    - helm repo add/pull workflow
    - skopeo copy to disk and to registry
    - Pull secret creation (kubectl)
    - Platform-specific values.yaml templates (AKS, EKS, GKE)
    - Plugin mirroring
    - registries.conf
  - 4.2 Partially disconnected (AKS, EKS, GKE)
    - helm repo add/pull workflow
    - skopeo copy direct to mirror
    - Pull secret creation
    - Platform-specific values.yaml
    - Plugin mirroring
    - registries.conf

## Source Boundaries

This source is authoritative for installing Red Hat Developer Hub 1.10 in
network-restricted environments. It covers fully disconnected and partially
disconnected workflows for both the Operator and Helm chart installation
methods, including image mirroring scripts, oc-mirror workflows,
ImageSetConfiguration, plugin artifact mirroring, pull secret management,
registries.conf configuration, and optional signature verification.

It does **not** cover:
- Connected (online) installation procedures (separate guide)
- Post-installation configuration (authentication, RBAC, plugins)
- Operator upgrade procedures
- Uninstallation
- Sizing requirements details (referenced but not defined here)

## API Versions Documented

| Resource | apiVersion | Kind |
|----------|-----------|------|
| Backstage CR | `rhdh.redhat.com/v1alpha5` | `Backstage` |
| ImageSetConfiguration | `mirror.openshift.io/v2alpha1` | `ImageSetConfiguration` |
| ConfigMap (registries.conf) | `v1` | `ConfigMap` |
| ConfigMap (policy.json) | `v1` | `ConfigMap` |
| Secret (pull-secret) | `v1` | `Secret` |

## Related Official Sources

- Red Hat Developer Hub 1.10 "Installing on OpenShift Container Platform" — connected install
- Red Hat Developer Hub 1.10 "Administration" — post-install configuration
- OpenShift Container Platform "Installing the oc-mirror plugin" — oc-mirror setup
- OpenShift Container Platform "Exposing the registry" — internal registry access
