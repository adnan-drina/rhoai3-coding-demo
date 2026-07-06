---
name: rhdh-getting-started-setup
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when setting up a first Red Hat Developer Hub 1.10 instance, preparing
  infrastructure, installing the RHDH Operator, connecting external services
  (PostgreSQL, Redis, GitHub, identity providers), provisioning custom
  configuration, creating the Backstage CR, enabling authentication (RHBK,
  GitHub, Microsoft Azure), or managing RBAC via the Web UI. Do NOT use for
  navigating the RHDH interface or day-1 developer workflows (use
  rhdh-getting-started-navigate).
---

# RHDH Getting Started — Setup

Use this skill to ground first-instance setup guidance in the official Red Hat
Developer Hub 1.10 documentation for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority.

## Production Readiness Checklist

The default RHDH configuration runs with a minimal feature set. Production use
requires additional configuration:

- **Resiliency**: external PostgreSQL database, high-availability replicas
- **Performance**: external Redis cache for assets caching
- **Security**: TLS connections to external services, user provisioning with
  authentication, RBAC via the Web UI
- **Environment**: GitHub repository discovery, appearance customization

## Operator Installation

- Install from OperatorHub or software catalog in the OCP web console.
- Update channel: `fast` or `fast-1.10` (z-stream only).
- Installation mode: All namespaces (specific namespace not supported).
- Recommended namespace: `rhdh-operator`.
- Supported OCP versions: 4.18 through 4.21.
- Architecture: AMD64 / Intel 64 (`x86_64`).

## External Services

Before deploying RHDH, prepare:

1. **PostgreSQL** — connection strings, port, credentials, TLS certificates.
2. **Redis** — for plugin and TechDocs asset caching.
3. **GitHub App** — fine-grained permissions, short-lived tokens; prefer GitHub
   App over OAuth for integration and authentication (separate apps recommended
   for least-privilege).
4. **Identity Provider** — RHBK, GitHub, or Microsoft Azure.

## Custom Configuration

Provision config maps and secrets on OCP before creating the Backstage CR:

- `app-config.yaml` — main RHDH configuration (baseUrl, auth, catalog providers).
- `dynamic-plugins.yaml` — plugin enablement (GitHub discovery, RBAC, Keycloak
  catalog provider, Microsoft Graph, etc.).
- `secrets` — environment variable secrets (`my-rhdh-secrets`).

## Backstage CR

The Operator creates and manages RHDH instances via the Backstage custom
resource:

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: <my-rhdh-custom-resource>
spec:
  application:
    appConfig:
      configMaps:
        - name: my-rhdh-app-config
    dynamicPluginsConfigMapName: dynamic-plugins-rhdh
    extraEnvs:
      secrets:
        - name: my-rhdh-secrets
    replicas: 2
  database:
    enableLocalDb: false
```

Key fields: `appConfig.configMaps`, `dynamicPluginsConfigMapName`,
`extraEnvs.secrets`, `extraFiles.secrets`, `replicas`, `database.enableLocalDb`.

## Authentication

RHDH supports three identity providers with independent user provisioning and
authentication:

| Provider | Catalog plugin | Auth provider | Sign-in page |
|----------|---------------|---------------|--------------|
| RHBK | `keycloakOrg` | `oidc` | `oidc` |
| GitHub | `githubOrg` | `github` | `github` |
| Microsoft Azure | `microsoftGraphOrg` | `microsoft` | `microsoft` |

Guest access: set `auth.environment: development` (non-production only).
Production: set `auth.environment: production` to disable guest login.

## RBAC via Web UI

Policy administrators can create, edit, and delete roles and assign permissions
through Administration > RBAC in the Developer Hub interface. Policies from
`policy.csv` or ConfigMap cannot be edited via the Web UI.

## Workflow

1. Confirm the active RHDH baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md` for detailed field references.
3. Install the RHDH Operator via OperatorHub.
4. Prepare external services (PostgreSQL, GitHub App, identity provider).
5. Provision custom config maps and secrets.
6. Create the Backstage CR referencing custom configuration.
7. Enable authentication with the chosen provider.
8. Configure RBAC policies.
9. Verify the deployment.

## Validation

```bash
oc get backstage -n my-rhdh-project
oc get pods -n my-rhdh-project -l app.kubernetes.io/component=backstage
oc get route -n my-rhdh-project
```

- Healthy: Backstage CR status is ready, pods running, route accessible.
- Failure: check operator logs, config map references, secret mounts.

## Related Skills

- Use `rhdh-getting-started-navigate` for navigating the RHDH interface, login,
  and developer onboarding.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
