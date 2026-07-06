# Official Documentation Extraction

This extraction is derived from the official RHDH 1.10 guide captured in
`source-capture.md`.

## Helm CLI Commands

Pull the chart:

```bash
helm pull redhat-developer-hub \
  --repo https://charts.openshift.io \
  --version 1.10.1 \
  --untar
```

View values:

```bash
helm show values redhat-developer-hub
helm show values redhat-developer-hub/charts/backstage
helm show values redhat-developer-hub/charts/backstage/charts/postgresql
```

## Value Hierarchy

The chart uses five main configuration namespaces:

1. **Root** (e.g., `nameOverride`)
2. **Global** (`global.*`)
3. **Orchestrator** (`orchestrator.*`)
4. **Route** (`route.*`)
5. **Test** (`test.*`)
6. **Upstream** (`upstream.*`) — passed to the upstream Backstage Helm chart

## Root Namespace

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `nameOverride` | string | `"developer-hub"` | Customize resource names |

## Global Namespace

### Authentication

| Key | Type | Default |
|-----|------|---------|
| `global.auth.backend.enabled` | bool | `true` |
| `global.auth.backend.existingSecret` | string | `""` |
| `global.auth.backend.value` | string | `""` |

### Catalog Index

| Key | Type | Default |
|-----|------|---------|
| `global.catalogIndex.image.registry` | string | `"registry.redhat.io"` |
| `global.catalogIndex.image.repository` | string | `"rhdh/plugin-catalog-index@sha256"` |

### Dynamic Plugins

| Key | Type | Default |
|-----|------|---------|
| `global.dynamic.includes` | list | `["dynamic-plugins.default.yaml"]` |
| `global.dynamic.plugins` | list | `[]` |

### Networking

| Key | Type | Default |
|-----|------|---------|
| `global.clusterRouterBase` | string | `"apps.example.com"` |
| `global.host` | string | `""` |

## Route Namespace (OpenShift)

| Key | Type | Default |
|-----|------|---------|
| `route.enabled` | bool | `true` |
| `route.host` | string | `"{{ .Values.global.host }}"` |
| `route.path` | string | `"/"` |
| `route.tls.enabled` | bool | `true` |
| `route.tls.termination` | string | `"edge"` |
| `route.tls.insecureEdgeTerminationPolicy` | string | `"Redirect"` |
| `route.wildcardPolicy` | string | `"None"` |

## Orchestrator Namespace

| Key | Type | Default |
|-----|------|---------|
| `orchestrator.enabled` | bool | `false` |
| `orchestrator.serverlessLogicOperator.enabled` | bool | `true` |
| `orchestrator.sonataflowPlatform.monitoring.enabled` | bool | `true` |
| `orchestrator.sonataflowPlatform.resources.limits.cpu` | string | `"500m"` |
| `orchestrator.sonataflowPlatform.resources.limits.memory` | string | `"1Gi"` |
| `orchestrator.sonataflowPlatform.resources.requests.cpu` | string | `"250m"` |
| `orchestrator.sonataflowPlatform.resources.requests.memory` | string | `"64Mi"` |

## Test Namespace

| Key | Type | Default |
|-----|------|---------|
| `test.enabled` | bool | `true` |
| `test.image.registry` | string | `"quay.io"` |
| `test.image.repository` | string | `"curl/curl"` |
| `test.image.tag` | string | `"latest"` |
| `test.injectTestNpmrcSecret` | bool | `false` |

## Upstream Backstage Namespace

### Image Configuration

| Key | Type | Default |
|-----|------|---------|
| `upstream.backstage.image.registry` | string | `"registry.redhat.io"` |
| `upstream.backstage.image.repository` | string | `"rhdh/rhdh-hub-rhel9@sha256"` |
| `upstream.backstage.replicas` | int | `1` |
| `upstream.backstage.installDir` | string | `"/opt/app-root/src"` |

### Resources

| Key | Type | Default |
|-----|------|---------|
| `upstream.backstage.resources.requests.cpu` | string | `"250m"` |
| `upstream.backstage.resources.requests.memory` | string | `"1Gi"` |
| `upstream.backstage.resources.limits.cpu` | string | `"1000m"` |
| `upstream.backstage.resources.limits.memory` | string | `"2.5Gi"` |
| `upstream.backstage.resources.limits.ephemeral-storage` | string | `"5Gi"` |

### Container Security

```yaml
upstream.backstage.containerSecurityContext:
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
  runAsNonRoot: true
  seccompProfile:
    type: RuntimeDefault
```

### Probes

| Probe | Path | Port | Period | Timeout |
|-------|------|------|--------|---------|
| Liveness | `/.backstage/health/v1/liveness` | backend | 10s | 4s |
| Readiness | `/.backstage/health/v1/readiness` | backend | 10s | 4s |
| Startup | `/.backstage/health/v1/liveness` | backend | 20s | 4s |

Startup probe has `initialDelaySeconds: 30`.

### Dynamic Plugins Volume

```yaml
upstream.backstage.extraVolumes:
  - name: dynamic-plugins-root
    ephemeral:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: "5Gi"
```

### Container Ports

Default backend port: `7007`. Metrics port: `9464`.

### App Config

Default `upstream.backstage.appConfig` generates a ConfigMap with:
- `app.baseUrl` and `backend.baseUrl` using the RHDH hostname
- `backend.database.connection` with PostgreSQL credentials
- `backend.auth.externalAccess` with legacy default config

### Autoscaling

Disabled by default. `maxReplicas: 100`, `minReplicas: 1`,
`targetCPUUtilizationPercentage: 80`.

## Upstream PostgreSQL

| Key | Type | Default |
|-----|------|---------|
| `upstream.postgresql.enabled` | bool | `true` |
| `upstream.postgresql.architecture` | string | `"standalone"` |
| `upstream.postgresql.auth.username` | string | `"bn_backstage"` |
| `upstream.postgresql.auth.secretKeys.adminPasswordKey` | string | `"postgres-password"` |
| `upstream.postgresql.image.registry` | string | `"registry.redhat.io"` |
| `upstream.postgresql.image.repository` | string | `"rhel9/postgresql-15@sha256"` |

External database is recommended for production.

## Upstream Service

| Key | Type | Default |
|-----|------|---------|
| `upstream.service.type` | string | `"ClusterIP"` |
| `upstream.service.ports.backend` | int | `7007` |
| `upstream.service.ports.name` | string | `"http-backend"` |
| `upstream.service.sessionAffinity` | string | `"None"` |

## Upstream Ingress

Disabled by default (`upstream.ingress.enabled: false`). Route is preferred
on OpenShift.

## Upstream Metrics

ServiceMonitor disabled by default. Path: `/metrics`, port: `http-metrics`.

## Upstream NetworkPolicy

Disabled by default (`upstream.networkPolicy.enabled: false`).

## Orchestrator Infrastructure Helm Chart

Separate chart for Orchestrator infrastructure:

```bash
helm pull redhat-developer-hub-orchestrator-infra \
  --repo https://charts.openshift.io \
  --version 1.10.1
```

| Key | Type | Default |
|-----|------|---------|
| `serverlessLogicOperator.enabled` | bool | `true` |
| `serverlessLogicOperator.subscription.namespace` | string | `"openshift-serverless-logic"` |
| `serverlessLogicOperator.subscription.spec.channel` | string | `"alpha"` |
| `serverlessLogicOperator.subscription.spec.installPlanApproval` | string | `"Manual"` |
| `serverlessLogicOperator.subscription.spec.startingCSV` | string | `"logic-operator.v1.38.0"` |
| `serverlessOperator.enabled` | bool | `true` |
| `serverlessOperator.subscription.namespace` | string | `"openshift-serverless"` |
| `serverlessOperator.subscription.spec.channel` | string | `"stable"` |
