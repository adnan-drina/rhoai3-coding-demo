# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation version | 1.10 |
| Documentation category | Get started |
| Official guide | Setting up and configuring your first Red Hat Developer Hub instance |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Setting up and configuring your first Red Hat Developer Hub instance:

- Chapter 1: Checklist to run your first RHDH instance in production
  (resiliency, performance, security, environment adaptation)
- Chapter 2: Install the Red Hat Developer Hub Operator
  (prerequisites, OCP 4.18–4.21, update channels fast/fast-1.10, namespace,
  installation mode)
- Chapter 3: Prepare your external services
  (PostgreSQL, Redis, GitHub App registration, identity provider credentials)
- Chapter 4: Provision your custom Red Hat Developer Hub configuration
  (app-config.yaml, dynamic-plugins.yaml, secrets, config maps, namespace)
- Chapter 5: Enable authentication in Red Hat Developer Hub
  - 5.1 User provisioning and authentication concepts
  - 5.2 Guest login enable/disable
  - 5.3 Share secret with RHBK
  - 5.4 Import users/groups from RHBK (keycloakOrg catalog provider)
  - 5.5 Enable authentication with RHBK (OIDC provider)
  - 5.6 Share secrets with GitHub (integration + authentication apps)
  - 5.7 Import users/groups from GitHub (githubOrg catalog provider)
  - 5.8 Enable authentication with GitHub
  - 5.9 Share secret with Microsoft Azure
  - 5.10 Import users/groups from Azure (microsoftGraphOrg catalog provider)
  - 5.11 Enable authentication with Microsoft Azure
- Chapter 6: Use the RHDH Operator to run Developer Hub with custom config
  (Backstage CR: apiVersion rhdh.redhat.com/v1alpha5, kind Backstage)
- Chapter 7: Switch theme mode (light, dark, auto)
- Chapter 8: Manage RBAC using the RHDH Web UI
  (create, edit, delete roles; assign permissions)

## Source Boundaries

This skill covers the "Setting up and configuring your first Red Hat Developer
Hub instance" guide only. It provides:

- Production readiness checklist
- Operator installation
- External service preparation
- Custom configuration provisioning
- Authentication setup (RHBK, GitHub, Microsoft Azure)
- Backstage CR creation
- Theme switching
- RBAC management via Web UI

It does not cover:

- Day-1 developer navigation and onboarding (separate guide)
- Dynamic plugin development or advanced plugin configuration
- TechDocs authoring and publishing
- Software template creation
- API registration
- Advanced RBAC policy authoring beyond Web UI

## API Versions Documented

| Resource | API Version |
|----------|-------------|
| Backstage | `rhdh.redhat.com/v1alpha5` |

## Related Official Sources

- Navigate Red Hat Developer Hub on your first day (RHDH 1.10)
