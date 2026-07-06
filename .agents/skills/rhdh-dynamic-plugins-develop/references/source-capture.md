# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Extend |
| Official guide | Develop and deploy dynamic plugins in Red Hat Developer Hub |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/develop_and_deploy_dynamic_plugins_in_red_hat_developer_hub/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/develop_and_deploy_dynamic_plugins_in_red_hat_developer_hub/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Preface
- Chapter 1: Dynamic Plugins
  - Plugin system overview, `dynamic-plugins.yaml` format
- Chapter 2: Prepare your development environment
  - 2.1 The development toolchain (Node.js v22, Yarn 4, Docker/Podman, rhdh-cli)
- Chapter 3: Develop a new plugin
  - 3.1 Determine RHDH version (compatibility matrix)
  - 3.2 Create a new Backstage application
  - 3.3 Create a new plugin (`yarn new`)
  - 3.4 Implement a plugin component (entity card example)
  - 3.5 Test a plugin locally (dev harness, RHDH Local)
  - 3.6 Configure front-end plugin wiring (`dynamicRoutes`, `mountPoints`)
- Chapter 4: Convert a custom plugin into a dynamic plugin
  - rhdh-cli `plugin export` command
  - 4.1 Using the dynamic plugin factory
- Chapter 5: Deployment configurations
  - 5.1 Add a dynamic plugin to RHDH (`dynamic-plugins.yaml`)
- Chapter 6: Verify plugins locally
  - RHDH Local paths, `dynamic-plugins.override.yaml`, `local-plugins/`

## Source Boundaries

This source is authoritative for developing, converting, packaging, and
deploying custom dynamic plugins for Red Hat Developer Hub 1.10. It covers the
development toolchain, Backstage compatibility matrix, plugin creation,
component implementation, local testing, front-end wiring, dynamic export via
rhdh-cli, OCI/TGZ packaging, and RHDH Local verification.

It does **not** cover:
- Installing pre-built or shipped plugins (separate "Installing" guide)
- Using already-installed plugins such as Argo CD, Tekton, Topology (separate
  "Using" guide)
- RHDH Operator or Helm installation procedures
- RBAC, authentication, or catalog configuration
- Plugin configuration for specific third-party integrations

## Related Official Sources

- Red Hat Developer Hub 1.10 "Installing and viewing plugins" guide
- Red Hat Developer Hub 1.10 "Using dynamic plugins" guide
- Red Hat Developer Hub 1.10 "Configuring plugins" guide
- Red Hat Developer Hub 1.10 "Dynamic plugins reference" guide
