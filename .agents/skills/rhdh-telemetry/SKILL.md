---
name: rhdh-telemetry
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when configuring web analytics and system observability telemetry data
  collection in Red Hat Developer Hub 1.10. Covers Segment-based web analytics,
  OpenTelemetry system observability, enabling and disabling telemetry via
  Operator and Helm, and customizing the Segment source write key. Do NOT use
  for application log levels, ServiceMonitor metrics, or cloud provider
  monitoring; use rhdh-monitoring. Do NOT use for audit log configuration or
  RBAC audit events; use rhdh-audit-logs.
---

# RHDH Telemetry

Use this skill to configure web analytics and system observability telemetry
data collection in Red Hat Developer Hub 1.10.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is the product authority. This skill adapts
the official Telemetry Data Collection and Analysis guide for this repo's
demo posture.

## Scope

RHDH collects two types of telemetry data by default:

### Web Analytics (Segment)

Tracks user behavior and interactions:

- Page visits and link/button clicks
- System information (locale, time zone, user agent)
- Page information (title, category, extension name, URL, path, referrer)
- Anonymous IP addresses (recorded as `0.0.0.0`)
- Anonymous username hashes (unique user count only)

### System Observability (OpenTelemetry)

Tracks RHDH performance:

- CPU usage, memory usage, and performance indicators
- System component information
- Traces and logs for system process monitoring

## Demo Policy

For this repo:

- Telemetry is enabled by default in RHDH.
- In air-gapped or restricted environments, disable telemetry to avoid
  outbound requests that affect responsiveness.
- Do not commit real Segment write keys.
- When customizing the Segment source, create a data collection notice for
  application users.
- Use `SEGMENT_WRITE_KEY` environment variable to point to a custom source.

## Workflow

### Disable Telemetry

#### Operator

1. Create or update the `dynamic-plugins-rhdh` ConfigMap with the
   `analytics-provider-segment` plugin set to `disabled: true`.
2. Set `spec.application.dynamicPluginsConfigMapName: dynamic-plugins-rhdh`
   in the Backstage CR.

#### Helm Chart

Add to `values.yaml`:

```yaml
global:
  dynamic:
    plugins:
      - package: './dynamic-plugins/dist/backstage-community-plugin-analytics-provider-segment'
        disabled: true
```

### Enable Telemetry

Same configuration as disable, but set `disabled: false`.

### Customize Segment Source

#### Operator

Set `SEGMENT_WRITE_KEY` in the Backstage CR:

```yaml
spec:
  application:
    extraEnvs:
      envs:
        - name: SEGMENT_WRITE_KEY
          value: <segment_key>
```

#### Helm Chart

Set in `values.yaml`:

```yaml
upstream:
  backstage:
    extraEnvVars:
      - name: SEGMENT_WRITE_KEY
        value: <segment_key>
```

## Key Configuration

| Configuration | Plugin Package | Default |
|---------------|----------------|---------|
| Web Analytics | `./dynamic-plugins/dist/backstage-community-plugin-analytics-provider-segment` | Enabled |
| Dynamic plugins ConfigMap | `dynamic-plugins-rhdh` | Must be created |
| Segment write key | `SEGMENT_WRITE_KEY` env var | Points to Red Hat source |

## Verification Commands

```bash
oc get configmap dynamic-plugins-rhdh -n <rhdh-namespace> -o yaml
oc get backstage -n <rhdh-namespace> -o yaml
oc logs deployment/<rhdh-deployment> -n <rhdh-namespace> | grep -i segment
```

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
