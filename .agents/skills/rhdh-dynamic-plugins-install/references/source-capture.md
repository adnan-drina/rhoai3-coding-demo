# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Extend |
| Official guide | Installing and viewing plugins in Red Hat Developer Hub |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Install dynamic plugins in Red Hat Developer Hub
  - 1.1 Install dynamic plugins with the RHDH Operator (ConfigMap, Backstage CR)
  - 1.2 Dynamic plugins dependency management
    - 1.2.1 Cluster level plugin dependencies configuration
    - 1.2.2 Plugin dependencies infrastructure
    - 1.2.3 Plugin configuration
  - 1.3 Installing dynamic plugins using the Helm chart
  - 1.4 Example Helm chart configurations
  - 1.5 Install in air-gapped environment (Helm)
  - 1.6 Install in air-gapped environment (Operator)
  - 1.7 Mirror RHDH dynamic plugins in disconnected environments
    - 1.7.1 Prerequisites (Skopeo, tar, jq, Podman)
    - 1.7.2 Mirror from catalog index (partial disconnect)
    - 1.7.3 Mirror from catalog index (full disconnect, two-phase)
    - 1.7.4 Mirror specific plugins by direct reference
    - 1.7.5 Mirror plugins from a file
    - 1.7.6 Combine many plugin sources
- Chapter 2: Install plugins from OCI registries with custom certificates
  - 2.1 Prerequisites (CA bundle creation)
  - 2.2 Per-registry TLS configuration
  - 2.3 Mount CA bundle
  - 2.4 OpenShift cluster-wide trusted CA
- Chapter 3: Custom plugins in Red Hat Developer Hub
  - 3.1 Export custom plugins (rhdh-cli, backend/frontend export)
  - 3.2 Package and publish (OCI, TGZ, JavaScript package)
    - 3.2.1 Create OCI image
    - 3.2.2 Create TGZ file
    - 3.2.3 Create JavaScript package
  - 3.3 Install custom plugins
    - 3.3.1 Load from OCI image (pull secrets, digest, version inheritance)
    - 3.3.2 Load from TGZ
    - 3.3.3 Load from JavaScript package
  - 3.4 Example: Entity Feedback community plugin
  - 3.5 Add custom dynamic plugin to RHDH
  - 3.6 Display front-end plugin
- Chapter 4: Using the dynamic plugin factory
- Chapter 5: Enable plugins in RHDH container image
  - `dynamic-plugins.default.yaml` retrieval, `{{inherit}}` tag
- Chapter 6: Extensions in Red Hat Developer Hub (Tech Preview)
  - 6.1 View available plugins
  - 6.2 View installed plugins
  - 6.3 Search plugins by name
  - 6.4 Disable the Extensions interface
- Chapter 7: Developer Preview — install/test plugins via Extensions
  - 7.1 Configure RHDH development environment (PVC, extensions config)
    - 7.1.1 Configure RBAC for Extensions
    - 7.1.2 Install plugins via Extensions
    - 7.1.3 Enable/disable plugins via Extensions
  - 7.2 Use RHDH Local for Extensions testing
- Chapter 8: Troubleshoot pod startup failure after enabling a plugin
- Chapter 9: Front-end plugin wiring
  - 9.1 Understanding front-end plugin wiring
    - 9.1.1 Wiring concepts (dynamicRoutes, mountPoints, appIcons, etc.)
  - 9.2 Extend internal icon catalog

## Source Boundaries

This source is authoritative for installing, configuring, viewing, and managing
dynamic plugins in Red Hat Developer Hub 1.10. It covers Operator and Helm
installation methods, ConfigMap-based plugin configuration, air-gapped and
disconnected mirroring, custom TLS certificates for OCI registries, custom
plugin export and packaging (OCI/TGZ/NPM), plugin loading mechanisms, front-end
wiring, the Extensions UI (Technology Preview), Developer Preview plugin
installation, dependency management, and startup troubleshooting.

It does **not** cover:
- Developing new plugins from scratch (separate "Develop" guide)
- Using specific installed plugins like Argo CD, Tekton (separate "Using" guide)
- RHDH Operator or Helm chart installation itself
- RHDH platform administration, RBAC, or authentication configuration
- Dynamic plugins reference (separate guide)

## API Versions Documented

| Resource | apiVersion | Kind |
|----------|-----------|------|
| Backstage CR | `rhdh.redhat.com/v1alpha5` | `Backstage` |
| ConfigMap (dynamic plugins) | `v1` | `ConfigMap` |
| Secret (NPM registry) | `v1` | `Secret` |
| Secret (OCI registry auth) | `v1` | `Secret` |
| ConfigMap (trusted CA) | `v1` | `ConfigMap` |

## Related Official Sources

- Red Hat Developer Hub 1.10 "Develop and deploy dynamic plugins" guide
- Red Hat Developer Hub 1.10 "Using dynamic plugins" guide
- Red Hat Developer Hub 1.10 "Configuring plugins" guide
- Red Hat Developer Hub 1.10 "Dynamic plugins reference" guide
