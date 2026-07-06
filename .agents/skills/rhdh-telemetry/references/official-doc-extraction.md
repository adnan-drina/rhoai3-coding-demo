# Official Doc Extraction

Use this reference when authoring or reviewing RHDH telemetry configuration
content.

## Component Purpose

Red Hat Developer Hub collects and analyzes telemetry data by default to
improve user experience. Two types of telemetry are supported:

1. **Web Analytics** — Segment-based user behavior tracking
2. **System Observability** — OpenTelemetry-based performance monitoring

## Web Analytics (Segment)

Tracks user behavior and interactions:

- Events: page visits, link clicks, button clicks
- System info: locale, time zone, user agent (browser and OS details)
- Page info: title, category, extension name, URL, path, referrer, search
  parameters
- Privacy: IP addresses recorded as `0.0.0.0`; username hashes are anonymous
  identifiers used solely for unique user count

## System Observability (OpenTelemetry)

Tracks RHDH performance:

- Key system metrics: CPU usage, memory usage, performance indicators
- System component info: locale, time zone, user agent
- Traces and logs for monitoring system processes and troubleshooting

## Disabling Telemetry

Disable by setting the `analytics-provider-segment` plugin to `disabled: true`.

### Operator Method

Create a ConfigMap:

```yaml
kind: ConfigMap
apiVersion: v1
metadata:
  name: dynamic-plugins-rhdh
data:
  dynamic-plugins.yaml: |
    includes:
      - dynamic-plugins.default.yaml
    plugins:
      - package: './dynamic-plugins/dist/backstage-community-plugin-analytics-provider-segment'
        disabled: true
```

Reference in the Backstage CR:

```yaml
spec:
  application:
    dynamicPluginsConfigMapName: dynamic-plugins-rhdh
```

### Helm Method

Add to `values.yaml`:

```yaml
global:
  dynamic:
    plugins:
      - package: './dynamic-plugins/dist/backstage-community-plugin-analytics-provider-segment'
        disabled: true
```

### Air-Gapped Note

In air-gapped environments, disabling telemetry avoids outbound requests that
can affect RHDH application responsiveness.

## Enabling Telemetry

Telemetry is enabled by default. To re-enable after disabling, use the same
configuration with `disabled: false`.

### Operator Method

```yaml
kind: ConfigMap
apiVersion: v1
metadata:
  name: dynamic-plugins-rhdh
data:
  dynamic-plugins.yaml: |
    includes:
      - dynamic-plugins.default.yaml
    plugins:
      - package: './dynamic-plugins/dist/backstage-community-plugin-analytics-provider-segment'
        disabled: false
```

### Helm Method

```yaml
global:
  dynamic:
    plugins:
      - package: './dynamic-plugins/dist/backstage-community-plugin-analytics-provider-segment'
        disabled: false
```

## Customizing Segment Source

By default, web analytics data is sent to Red Hat. Configure a custom Segment
source using the `SEGMENT_WRITE_KEY` environment variable.

### Operator Method

```yaml
spec:
  application:
    extraEnvs:
      envs:
        - name: SEGMENT_WRITE_KEY
          value: <segment_key>
```

### Helm Method

```yaml
upstream:
  backstage:
    extraEnvVars:
      - name: SEGMENT_WRITE_KEY
        value: <segment_key>
```

Replace `<segment_key>` with the unique identifier for the custom Segment
source.

### Data Collection Notice

When configuring a custom Segment source, create a web analytics data
collection notice for application users.

## Key Artifacts

| Artifact | Purpose |
|----------|---------|
| `dynamic-plugins-rhdh` ConfigMap | Dynamic plugin configuration for Operator installs |
| `dynamic-plugins.default.yaml` | Base plugin list included by the ConfigMap |
| `backstage-community-plugin-analytics-provider-segment` | Segment analytics dynamic plugin |
| `SEGMENT_WRITE_KEY` env var | Points analytics to a custom Segment source |
| `dynamicPluginsConfigMapName` field | Backstage CR field referencing the plugins ConfigMap |

## Verification Commands

```bash
oc get configmap dynamic-plugins-rhdh -n <rhdh-namespace> -o yaml
oc get backstage -n <rhdh-namespace> -o jsonpath='{.spec.application.dynamicPluginsConfigMapName}'
oc get backstage -n <rhdh-namespace> -o jsonpath='{.spec.application.extraEnvs}'
oc logs deployment/<rhdh-deployment> -n <rhdh-namespace> | grep -i segment
oc logs deployment/<rhdh-deployment> -n <rhdh-namespace> | grep -i analytics
```
