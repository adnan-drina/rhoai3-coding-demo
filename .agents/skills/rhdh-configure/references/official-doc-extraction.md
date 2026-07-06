# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Configuring Red Hat Developer Hub
Captured: 2026-07-06

---

## 1. Configuration Files

### Cluster-Provisioned Files

| File | Purpose | Operator | Helm |
|------|---------|----------|------|
| `app-config.yaml` | App URLs, auth, catalog, DB, plugins | ConfigMap in `spec.application.appConfig.configMaps` | `upstream.backstage.appConfig` or `extraAppConfig` |
| Secrets | Credentials, BACKEND_SECRET, DB passwords | `spec.application.extraEnvs.secrets` | `upstream.backstage.extraEnvVarsSecrets` |
| `dynamic-plugins.yaml` | Enable/disable plugins | `spec.application.dynamicPluginsConfigMapName` | `global.dynamic.plugins` |
| `rbac-policy.csv` | Permission policies (Casbin) | ConfigMap mounted, path in `permission.rbac.policies-csv-file` | Same |
| `rbac-conditional-policies.yaml` | Conditional policies | ConfigMap mounted, path in `permission.rbac.conditionalPoliciesFile` | Same |

### Application-Consumed Files (from Git)

| File | Purpose | Consumed by |
|------|---------|-------------|
| `catalog-info.yaml` | Entity descriptors | Software Catalog |
| `template.yaml` | Software template scaffolding | Software Templates |
| `mkdocs.yml` | TechDocs build config | TechDocs plugin |

---

## 2. Application Configuration (app-config.yaml)

Key sections:
- `app` — frontend settings (title, baseUrl)
- `backend` — backend URL, CORS, database, auth, cache
- `auth` — authentication provider configuration
- `catalog` — Software Catalog locations and providers
- `techdocs` — TechDocs builder and storage
- `proxy` — proxy endpoints for external services
- `permission` — RBAC framework

Supports `${VAR_NAME}` syntax resolved from environment variables at runtime.

### Base URL configuration

```yaml
app:
  title: Red Hat Developer Hub
  baseUrl: https://<my_developer_hub_domain>

backend:
  auth:
    externalAccess:
      - type: legacy
        options:
          subject: legacy-default-config
          secret: "${BACKEND_SECRET}"
  baseUrl: https://<my_developer_hub_domain>
  cors:
    origin: https://<my_developer_hub_domain>
```

---

## 3. Secrets

Create secrets with environment variable format:

```bash
oc create secret generic my-rhdh-secrets \
  --from-file=secrets.txt --namespace=my-rhdh-project
```

Common secrets:
- `BACKEND_SECRET` — service-to-service authentication
- Database passwords and TLS certificates (optional)

---

## 4. Dynamic Plugins Configuration

```yaml
includes:
  - dynamic-plugins.default.yaml
plugins:
  - package: ./dynamic-plugins/dist/backstage-plugin-catalog-backend-module-github
    disabled: false
  - package: ./dynamic-plugins/dist/backstage-community-plugin-rbac
    disabled: false
```

Provisioning:
- Operator: ConfigMap referenced in `spec.application.dynamicPluginsConfigMapName`
- Helm: inline via `global.dynamic.plugins`

---

## 5. Backstage Custom Resource (Operator)

### Minimal CR

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: my-rhdh-custom-resource
spec:
  application:
    appConfig:
      mountPath: /opt/app-root/src
      configMaps:
         - name: my-rhdh-app-config
    extraEnvs:
      secrets:
         - name: <my_product_secrets>
    extraFiles:
      mountPath: /opt/app-root/src
    route:
      enabled: true
  database:
    enableLocalDb: true
```

### Full CR with plugins, RBAC, and external DB

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: <my-rhdh-custom-resource>
spec:
  application:
    appConfig:
      mountPath: /opt/app-root/src
      configMaps:
         - name: my-rhdh-app-config
         - name: rbac-policies
    dynamicPluginsConfigMapName: dynamic-plugins-rhdh
    extraEnvs:
      secrets:
         - name: <my_product_secrets>
         - name: my-rhdh-database-secrets
    extraFiles:
      mountPath: /opt/app-root/src
      secrets:
        - name: my-rhdh-database-certificates-secrets
          key: postgres-crt.pem, postgres-ca.pem, postgres-key.key
    route:
      enabled: true
  database:
    enableLocalDb: false
```

### Key Backstage CR fields

| Field | Purpose |
|-------|---------|
| `spec.application.appConfig.configMaps` | app-config ConfigMap references |
| `spec.application.dynamicPluginsConfigMapName` | dynamic plugins ConfigMap |
| `spec.application.extraEnvs.secrets` | inject secrets as env vars |
| `spec.application.extraEnvs.envs` | inline env vars (e.g., proxy) |
| `spec.application.extraFiles.secrets` | mount secrets as files (TLS certs) |
| `spec.application.route.enabled` | enable OpenShift Route |
| `spec.database.enableLocalDb` | true for local PG, false for external |
| `spec.deployment.patch` | strategic merge patch for Deployment |

---

## 6. Helm Chart Configuration

```yaml
upstream:
  backstage:
    extraAppConfig:
      - configMapRef: my-rhdh-app-config
        filename: app-config.yaml
    extraEnvVarsSecrets:
      - my-rhdh-secrets
```

---

## 7. Default Configuration (Operator)

Default ConfigMap: `rhdh-default-config` in `rhdh-operator` namespace.

Resources created automatically:
- `backstage-{cr-name}` Deployment and Service (mandatory)
- `backstage-psql-{cr-name}` StatefulSet, Service, Secret (if `enableLocalDb=true`)
- `backstage-{cr-name}` Route (OpenShift only)
- ConfigMaps and Secrets for app-config, plugins, env vars, files

---

## 8. Provisioning Commands

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

---

## 9. Proxy Configuration

```yaml
spec:
  application:
    extraEnvs:
      envs:
        - name: HTTP_PROXY
          value: 'http://10.10.10.105:3128'
        - name: HTTPS_PROXY
          value: 'http://10.10.10.106:3128'
        - name: NO_PROXY
          value: 'localhost,example.org'
```

---

## 10. Configuration Precedence Rules

1. Multiple app-config.yaml files deep-merge (later overrides earlier)
2. Object values merge recursively; array values replace entirely
3. `${VAR_NAME}` resolves at runtime; missing vars cause startup failure
4. Dynamic plugins merge by package name between custom and includes lists
5. Operator merges multiple pre-configured settings (Orchestrator, Lightspeed)
