---
name: rhdh-configure
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when adding custom config maps, secrets, and configuring Red Hat Developer
  Hub to work in your IT ecosystem. Covers app-config.yaml, dynamic plugins,
  RBAC policies, Backstage CR, Helm values, external PostgreSQL, HA, proxy,
  TLS certificates, deployment patches, and front-end system migration. Do NOT
  use for appearance customization (use rhdh-customize), TechDocs setup (use
  rhdh-techdocs-config), or upgrade procedures (use rhdh-upgrade).
---

# RHDH Configure

Use this skill to configure Red Hat Developer Hub 1.10 grounded in official
product documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers configuration files,
provisioning, Operator and Helm deployment methods, default configuration,
front-end system migration, predefined Operator configurations, external
PostgreSQL, HA, proxy, TLS, dynamic plugin cache, and deployment customization.

## Configuration Files Overview

| File | Purpose | Provisioning |
|------|---------|-------------|
| `app-config.yaml` | Main application config (URLs, auth, catalog, DB, plugins) | ConfigMap via Operator or Helm |
| Secrets (`my-rhdh-secrets`) | Credentials, BACKEND_SECRET, DB passwords | Secret via `extraEnvs.secrets` or `extraEnvVarsSecrets` |
| `dynamic-plugins.yaml` | Enable/disable/configure dynamic plugins | ConfigMap via `dynamicPluginsConfigMapName` or `global.dynamic.plugins` |
| `rbac-policy.csv` | RBAC permission policies (Casbin format) | ConfigMap mounted as file |
| `rbac-conditional-policies.yaml` | Conditional RBAC policies | ConfigMap mounted as file |

## Backstage Custom Resource (Operator)

- **apiVersion:** `rhdh.redhat.com/v1alpha5`
- **kind:** `Backstage`
- **Key fields:**
  - `spec.application.appConfig.configMaps` — app-config references
  - `spec.application.dynamicPluginsConfigMapName` — plugins ConfigMap
  - `spec.application.extraEnvs.secrets` — inject secrets as env vars
  - `spec.application.extraFiles.secrets` — mount secrets as files
  - `spec.application.route.enabled` — route configuration
  - `spec.database.enableLocalDb` — local or external PostgreSQL
  - `spec.deployment.patch` — strategic merge patch for Deployment

## Helm Chart Key Values

- `upstream.backstage.appConfig` — inline app config
- `upstream.backstage.extraAppConfig` — external config map references
- `upstream.backstage.extraEnvVarsSecrets` — secret injection
- `global.dynamic.plugins` — dynamic plugin configuration

## Configuration Precedence

1. Multiple `app-config.yaml` files deep-merge; later overrides earlier
2. Arrays replace entirely (not append)
3. `${VAR_NAME}` resolves at runtime from environment variables
4. Dynamic plugins merge with base `includes` list by package name
5. Operator merges multiple pre-configured settings automatically

## Provisioning Steps (Operator)

```bash
oc create namespace my-rhdh-project
oc create configmap my-rhdh-app-config \
  --from-file=app-config.yaml --namespace=my-rhdh-project
oc create configmap dynamic-plugins-rhdh \
  --from-file=dynamic-plugins.yaml --namespace=my-rhdh-project
oc create secret generic my-rhdh-secrets \
  --from-file=secrets.txt --namespace=my-rhdh-project
oc apply -f my-rhdh-custom-resource.yaml --namespace=my-rhdh-project
```

## Provisioning Steps (Helm)

```yaml
upstream:
  backstage:
    extraAppConfig:
      - configMapRef: my-rhdh-app-config
        filename: app-config.yaml
    extraEnvVarsSecrets:
      - my-rhdh-secrets
```

## Key Configuration Areas

1. **External PostgreSQL** — Disable local DB, configure connection via secrets
2. **High availability** — Multiple replicas configuration
3. **Corporate proxy** — HTTP_PROXY, HTTPS_PROXY, NO_PROXY via `extraEnvs`
4. **TLS certificates** — NODE_EXTRA_CA_CERTS for corporate CA trust
5. **Dynamic plugins cache** — Performance optimization for plugin loading
6. **Front-end system migration** — Blueprint-based dynamic routing
7. **Deployment patches** — Strategic merge patches for advanced customization
8. **HTTP server timeouts** — Backend timeout configuration
9. **Mount paths** — Custom mount paths for secrets and PVCs

## Workflow

1. Read `references/official-doc-extraction.md` for exact YAML patterns.
2. Identify the configuration task (provisioning, plugins, DB, proxy, TLS, etc.).
3. Use the correct provisioning method (Operator CR or Helm values).
4. Apply configuration following documented steps.
5. Verify RHDH starts successfully with the new configuration.

## Related Skills

- `rhdh-upgrade` — Upgrade procedures
- `rhdh-customize` — Appearance, templates, and branding customization
- `rhdh-techdocs-config` — TechDocs plugin configuration

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
