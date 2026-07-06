# Official Doc Extraction

Use this extraction to keep Connectivity Link observability content grounded in
the official RHCL 1.4 documentation. When implementation needs exact CR fields,
tracing configuration, or dashboard setup, verify the active cluster schema
before authoring manifests.

## Observability Features

Connectivity Link uses metrics from Connectivity Link components, Gateway API
state metrics, and standard Envoy metrics (from OpenShift Service Mesh) to
build template dashboards and alerts.

Community-based templates are available from the Kuadrant Operator GitHub
repository for integration with Grafana, Prometheus, and Alertmanager. Secure
images are available in the Red Hat Catalog.

## Enabling Observability

Set `spec.observability.enable: true` in the `Kuadrant` CR:

```yaml
apiVersion: kuadrant.io/v1beta1
kind: Kuadrant
metadata:
  name: kuadrant-sample
spec:
  observability:
    enable: true
```

This creates `ServiceMonitor` and `PodMonitor` CRDs in the Connectivity Link
namespace and in each gateway namespace. Monitors also scrape the corresponding
gateway system namespace (generally `istio-system`).

Verification:

```bash
oc get servicemonitor,podmonitor -A -l kuadrant.io/observability=true
```

## Monitoring Stack Setup

Prerequisites: Connectivity Link installed, Prometheus configured, Grafana
installed, user workload monitoring enabled.

Verify user workload monitoring:

```bash
oc get configmap cluster-monitoring-config -n openshift-monitoring \
  -o jsonpath='{.data.config\.yaml}' | grep enableUserWorkload
```

Install metrics and configuration:

```bash
oc apply -k https://github.com/Kuadrant/kuadrant-operator/config/install/configure/observability?ref=v1.2.0
```

Configure example dashboards:

```bash
oc apply -k https://github.com/Kuadrant/kuadrant-operator/examples/dashboards?ref=v1.4.0
```

## Grafana Dashboards

Three persona-specific dashboards:

- **Platform engineer**: policy compliance, resource consumption, error rates,
  latency/throughput, multi-window multi-burn alert templates, multicluster.
- **Application developer**: latency/throughput per API, requests and error
  rates by API path.
- **Business user**: requests per second per API, rate increase/decrease over
  time.

Importable dashboard IDs: 21538, 20982, 20981, 22695.

For dashboard panels to work correctly, `HTTPRoute` resources must include
`service` and `deployment` labels matching the routed service and deployment
names.

Automated provisioning: use `GrafanaDashboard` resource referencing a
`ConfigMap`, or add JSON files to a `ConfigMap` mounted at
`/etc/grafana/provisioning/dashboards`.

## Prometheus Alerts

Integrate example alerts as `PrometheusRule` resources. SLO alerts generated
via the Sloth project integrate with the SLO Grafana dashboard using generated
labels.

## Tracing

### Control-Plane Tracing

Enabled by setting OpenTelemetry environment variables on operator deployments:

| Variable | Description | Default |
|----------|-------------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Collector endpoint (rpc://, http://, https://) | Tracing disabled |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Override for traces specifically | Uses main endpoint |
| `OTEL_EXPORTER_OTLP_INSECURE` | Skip TLS verification | `true` |
| `OTEL_SERVICE_NAME` | Service name for traces | `kuadrant-operator` |
| `OTEL_SERVICE_VERSION` | Service version | Empty |

### Data-Plane Tracing

Requires Istio `Telemetry` CR, Istio extension provider configuration, and
`Kuadrant` CR configuration.

Istio Telemetry CR for tracing:

```yaml
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: mesh-default
  namespace: gateway-system
spec:
  tracing:
  - providers:
    - name: tempo-otlp
    randomSamplingPercentage: 100
```

Istio CR extension provider:

```yaml
spec:
  values:
    meshConfig:
      enableTracing: true
      extensionProviders:
      - name: tempo-otlp
        opentelemetry:
          port: 4317
          service: tempo.tempo.svc.cluster.local
```

Kuadrant CR data-plane tracing:

```yaml
apiVersion: kuadrant.io/v1beta1
kind: Kuadrant
metadata:
  name: kuadrant
  namespace: kuadrant-system
spec:
  observability:
    dataPlane:
      defaultLevels:
        - debug: "true"
      httpHeaderIdentifier: x-request-id
    tracing:
      defaultEndpoint: rpc://tempo.tempo.svc.cluster.local:4317
      insecure: true
```

Optional separate tracing for Authorino and Limitador CRs using
`spec.tracing.endpoint` and `spec.tracing.insecure`.

Important: trace IDs do not propagate to WebAssembly modules in OpenShift
Service Mesh. Limitador requests lack parent trace IDs unless initiation is
outside the mesh.

### Rate-Limit Logging with Trace IDs

Set `spec.verbosity: 3` or higher in the `Limitador` CR to get request logging
with `traceparent` fields.

## Access Logs

### Enabling Access Logs

Use the Istio Telemetry API for mesh-wide or workload-scoped access logs:

```yaml
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: access-logs
  namespace: gateway-system
spec:
  accessLogging:
    - providers:
      - name: envoy
```

### JSON-Formatted Access Logs

Configure via Istio CR `meshConfig`:

```yaml
spec:
  values:
    meshConfig:
      accessLogFile: /dev/stdout
      accessLogEncoding: JSON
      accessLogFormat: |
        {
          "start_time": "%START_TIME%",
          "method": "%REQ(:METHOD)%",
          "path": "%REQ(X-ENVOY-ORIGINAL-PATH?:PATH)%",
          "response_code": "%RESPONSE_CODE%",
          "request_id": "%REQ(X-REQUEST-ID)%",
          "route_name": "%ROUTE_NAME%"
        }
```

### Filtering Access Logs

CEL-based filters in `Telemetry` CR `filter.expression`:

- Errors only: `"response.code >= 400"`
- API paths only: `'request.url_path.startsWith("/api/")'`
- Exclude health checks: `'!request.url_path.startsWith("/healthz")'`

### Request Correlation

Key fields for correlation:

- `request_id` (`%REQ(X-REQUEST-ID)%`): unique Envoy request identifier
- `start_time` (`%START_TIME%`): time-based correlation
- `route_name` (`%ROUTE_NAME%`): policy debugging

Enable cross-component correlation via
`spec.observability.dataPlane.httpHeaderIdentifier: x-request-id` in the
`Kuadrant` CR.

## MCP Gateway Observability

### OpenTelemetry Collector

Deploy an `OpenTelemetryCollector` CR (`opentelemetry.io/v1beta1`) in the MCP
gateway namespace with OTLP receivers (HTTP 4318, gRPC 4317) and exporters to
Tempo.

Set environment variables on the `mcp-gateway` deployment:

```bash
oc set env deployment/mcp-gateway \
  OTEL_EXPORTER_OTLP_ENDPOINT="http://<collector>-collector.<ns>.svc.cluster.local:4318" \
  OTEL_EXPORTER_OTLP_INSECURE="true" \
  OTEL_SERVICE_NAME="mcp-gateway"
```

### MCP Router Spans

| Span | When | Description |
|------|------|-------------|
| `mcp-router.process` | Every ext_proc stream | Root span |
| `mcp-router.route-decision` | Request body parsed | Routing decision |
| `mcp-router.broker-passthrough` | Non-tool-call requests | Pass-through to broker |
| `mcp-router.tool-call` | tools/call requests | Full tool call handling |
| `mcp-router.broker.get-server-info` | Inside tool-call | Resolve backend server |
| `mcp-router.session-cache.get` | Inside tool-call | Look up existing session |
| `mcp-router.session-init` | Cache miss | Hairpin initialize request |
| `mcp-router.session-cache.store` | After session-init | Store new session |

Attributes follow OpenTelemetry MCP Semantic Conventions: `mcp.method.name`,
`gen_ai.tool.name`, `mcp.session.id`, `mcp.server`, `http.request_id`, etc.

### MCP Gateway Audit Trail

MCP Gateway sets routing headers on every request: `x-mcp-method`,
`x-mcp-toolname`, `x-mcp-servername`, `mcp-session-id`.

Configure `AuthPolicy` CRs for both `mcp` and `mcps` listeners to inject
`x-auth-identity` header from JWT `preferred_username` claim.

Configure Istio `MeshConfig` `extensionProviders` with `mcp-json-access-log`
provider capturing MCP routing headers and identity header.

Create a `Telemetry` CR scoped to the MCP gateway pods via
`gateway.networking.k8s.io/gateway-name` label selector.

Verify audit trail:

```bash
oc logs -n <gateway_namespace> \
  -l gateway.networking.k8s.io/gateway-name=<mcp_gateway> \
  --since=30s | grep '"mcp_method"' | tail -1 | jq .
```

## Demo-Specific Notes

The following are project constraints, not claims from the official docs:

- RHCL is held at `rhcl-operator.v1.3.4` per `docs/PLATFORM_BASELINE.md`.
  Observability features described here are from the 1.4 documentation and may
  require the 1.4 operator version.
- Do not commit collector endpoints, tracing credentials, or identity provider
  secrets.
- Do not claim observability features are configured until the corresponding
  manifests, dashboards, and validation commands exist.
- Keep Connectivity Link observability separate from OCP-level observability
  and RHOAI model observability.
