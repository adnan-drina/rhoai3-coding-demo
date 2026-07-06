# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Upgrade |
| Official guide | Upgrading Red Hat Developer Hub |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/upgrading_red_hat_developer_hub/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/upgrading_red_hat_developer_hub/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Upgrade the Red Hat Developer Hub Operator
  - Prerequisites (OCP web console, Operator installed, roles configured)
  - Procedure (Subscription page, approve InstallPlan)
  - Verification (Upgrade status "Up to date")
- Chapter 2: Upgrade the Red Hat Developer Hub Helm chart
  - OpenShift Container Platform web console method
  - CLI method (`helm upgrade`)
  - Version skip policy (direct upgrade, review intermediate release notes)
- Chapter 3: Upgrade RHDH from 1.8 to 1.10 using the Helm chart
  - Affected fields: extraVolumeMounts, extraVolumes, initContainers
  - Mandatory new defaults: extensions-catalog volume and init container env vars
  - Verification (application initializes successfully)

## Source Boundaries

This source is authoritative for upgrading Red Hat Developer Hub from any
earlier version to 1.10 using either the Operator or Helm chart. It covers
Operator subscription-based upgrades, Helm CLI and web console upgrades, and
the specific 1.8-to-1.10 migration path for custom values.yaml overrides.

It does **not** cover:
- Initial installation of RHDH (separate "Installing" guide)
- Configuration of app-config, secrets, or dynamic plugins (separate "Configuring" guide)
- Customization of appearance, templates, or features (separate "Customizing" guide)
- TechDocs plugin setup (separate "TechDocs" guide)

## API Versions Documented

| Resource | apiVersion | Kind |
|----------|-----------|------|
| Backstage CR | `rhdh.redhat.com/v1alpha5` | `Backstage` |
| Subscription | `operators.coreos.com/v1alpha1` | `Subscription` |

## Related Official Sources

- Red Hat Developer Hub 1.10 "Configuring" guide — config maps, secrets, plugins
- Red Hat Developer Hub 1.10 "Customizing" guide — appearance, templates, branding
- Red Hat Developer Hub 1.10 "TechDocs" guide — TechDocs plugin configuration
- Red Hat Developer Hub Life Cycle page — support timelines
