# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Configure |
| Official guide | Configuring Red Hat Developer Hub |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Understanding Red Hat Developer Hub configuration files
  - 1.1 Configuration files overview (cluster-provisioned vs application-consumed)
  - 1.2 Application configuration file (app-config.yaml)
  - 1.3 Red Hat Developer Hub secrets
  - 1.4 Dynamic plugins configuration file
  - 1.5 RBAC policy files
  - 1.6 Backstage custom resource
  - 1.7 Helm chart values file
  - 1.8 Catalog entity descriptor file
  - 1.9 Software template definition file
  - 1.10 TechDocs configuration file
  - 1.11 Configuration precedence
- Chapter 2: Provision and use your custom configuration
  - 2.1 Provision custom configuration (ConfigMaps, secrets)
  - 2.2 Operator deployment with custom configuration
  - 2.3 Helm chart deployment with custom configuration
- Chapter 3: Red Hat Developer Hub default configuration
  - 3.1 Default configuration guide (Operator resources)
- Chapter 4: Migrate to the front-end system (blueprint-based dynamic routing)
- Chapter 5: Automate environment provisioning (predefined Operator configurations)
- Chapter 6: Configure external PostgreSQL databases
- Chapter 7: Configure high availability
- Chapter 8: Optimize Operator memory usage for large clusters
- Chapter 9: Run RHDH behind a corporate proxy
- Chapter 10: Configure trust for corporate CA (NODE_EXTRA_CA_CERTS)
- Chapter 11: Configure HTTP server timeouts
- Chapter 12: Use the dynamic plugins cache
- Chapter 13: Enable the plugin assets cache
- Chapter 14: Inject extra files and environment variables
- Chapter 15: Configure mount paths for default Secrets and PVCs
- Chapter 16: Mount secrets and PVCs to specific containers
- Chapter 17: Configure deployment when using the Operator
- Chapter 18: Configure a route with external TLS certificate (Operator)
- Chapter 19: Configure RHDH with TLS connection in Kubernetes
- Chapter 20: Troubleshoot Developer Hub configuration issues

## Source Boundaries

This source is authoritative for configuring Red Hat Developer Hub for
production. It covers configuration file structure, provisioning methods,
Operator and Helm deployment, default resources, front-end system migration,
predefined configurations, external databases, high availability, proxy and
TLS settings, caching, deployment customization, and configuration
troubleshooting.

It does **not** cover:
- Initial Operator or Helm installation (separate "Installing" guide)
- Upgrade procedures (separate "Upgrading" guide)
- Appearance customization, templates, branding (separate "Customizing" guide)
- TechDocs plugin configuration (separate "TechDocs" guide)
- Authentication providers (separate "Authentication" guide)
- RBAC deep configuration (separate "Authorization" guide)

## API Versions Documented

| Resource | apiVersion | Kind |
|----------|-----------|------|
| Backstage CR | `rhdh.redhat.com/v1alpha5` | `Backstage` |
| Backstage CR (older) | `backstage.redhat.com/v1alpha4` | `Backstage` |
| ConfigMap | `v1` | `ConfigMap` |
| Secret | `v1` | `Secret` |

## Related Official Sources

- Red Hat Developer Hub 1.10 "Upgrading" guide — version upgrades
- Red Hat Developer Hub 1.10 "Customizing" guide — appearance, templates
- Red Hat Developer Hub 1.10 "TechDocs" guide — TechDocs plugin
- Red Hat Developer Hub 1.10 "Authentication" guide — auth providers
- Red Hat Developer Hub 1.10 "Authorization" guide — RBAC policies
