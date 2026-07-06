# Official Doc Extraction

Use this reference when authoring or reviewing RHDH monitoring and logging
content.

## Component Purpose

Red Hat Developer Hub monitoring and logging provides application-level log
management, metrics collection via ServiceMonitor, and integration with cloud
monitoring services. The guide covers OpenShift, AWS, and AKS deployment
targets plus Red Hat Build of Keycloak plugin metrics.

## Log Level Configuration

### Operator

Set `LOG_LEVEL` in the Backstage CR:

```yaml
spec:
  application:
    extraEnvs:
      envs:
        - name: LOG_LEVEL
          value: debug
```

### Helm Chart

Set `LOG_LEVEL` in `values.yaml`:

```yaml
upstream:
  backstage:
    extraEnvVars:
      - name: LOG_LEVEL
        value: debug
```

### Supported Values

| Value | Description |
|-------|-------------|
| `debug` | Detailed information for troubleshooting |
| `info` | General operational information (default) |
| `warn` | Potential issues requiring attention |
| `error` | Non-critical errors during operation |
| `critical` | Unrecoverable errors requiring immediate action |

## OCP Metrics with ServiceMonitor

### Operator Installation

Set `spec.monitoring.enabled: true` in the Backstage CR:

```yaml
spec:
  monitoring:
    enabled: true
```

The Operator automatically creates a `ServiceMonitor` CR named
`metrics-<cr_name>` with correct `app.kubernetes.io/instance` and
`app.kubernetes.io/name` labels.

### Helm Installation

Configure in `values.yaml`:

```yaml
upstream:
  metrics:
    serviceMonitor:
      enabled: true
      path: /metrics
```

### Prerequisites

- Monitoring for user-defined projects must be enabled on the OCP cluster.

### Verification

1. OpenShift web console > Observe > Dashboard tab.
2. Verify metrics for RHDH pods are displayed.
3. Check `backstage-developer-hub` service labels under Project > Services.

## AWS Integration

### Amazon Prometheus

Pod annotations for Prometheus scraping:

```yaml
prometheus.io/scrape: 'true'
prometheus.io/path: '/metrics'
prometheus.io/port: '9464'
prometheus.io/scheme: 'http'
```

For Operator: add annotations to `spec.template.metadata.annotations` in the
`backstage-default-config` ConfigMap `deployment.yaml` key.

For Helm: add to `upstream.backstage.podAnnotations` in `values.yaml`.

Verification:

```bash
kubectl --namespace=prometheus port-forward deploy/prometheus-server 9090
```

Monitor metrics such as `process_cpu_user_seconds_total`.

### Amazon CloudWatch

Log group naming:

```
/aws/containerinsights/<cluster_name>/application
```

Query example:

```
fields @timestamp, @message, kubernetes.container_name
| filter kubernetes.container_name in ["install-dynamic-plugins", "backstage-backend"]
```

## AKS Integration

### Enable Azure Monitor Metrics

```bash
az aks create/update \
  --resource-group <your_resource_group> \
  --name <your_cluster> \
  --enable-azure-monitor-metrics
```

### Pod Annotations

Same Prometheus annotations as AWS:

```yaml
prometheus.io/scrape: 'true'
prometheus.io/path: '/metrics'
prometheus.io/port: '9464'
prometheus.io/scheme: 'http'
```

### Live Logs

Navigate to Azure Portal > resource group > AKS cluster > Kubernetes
resources > Workloads > select deployment > Live Logs.

### Real-Time Log Data

Navigate to Azure Portal > resource group > AKS cluster > Monitoring >
Insights > Containers tab > select `backend-backstage` container.

## Red Hat Build of Keycloak Metrics

The RHBK backend plugin supports OpenTelemetry metrics for monitoring
fetch operations.

### Available Counters

| Metric | Description |
|--------|-------------|
| `backend_keycloak_fetch_task_failure_count_total` | Fetch task failures where no data was returned |
| `backend_keycloak_fetch_data_batch_failure_count_total` | Partial data batch failures; plugin continues fetching other batches |

### Labels

All counters include `taskInstanceId` to trace failures to individual task
executions.

### PromQL Examples

Failures for a specific task:

```
backend_keycloak_fetch_data_batch_failure_count_total{taskInstanceId="<id>"} 1
```

Failures during the last hour:

```
sum(backend_keycloak_fetch_data_batch_failure_count_total)
  - sum(backend_keycloak_fetch_data_batch_failure_count_total offset 1h)
```

### Exporting Metrics

Export using any OpenTelemetry-compatible backend such as Prometheus.

## Verification Commands

```bash
oc get servicemonitor -n <rhdh-namespace>
oc get backstage -n <rhdh-namespace> -o yaml
oc get pods -l app.kubernetes.io/name=developer-hub -n <rhdh-namespace>
```
