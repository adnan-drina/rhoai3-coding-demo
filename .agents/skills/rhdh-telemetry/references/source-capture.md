# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product | Red Hat Developer Hub |
| Product version | 1.10 |
| Book title | Telemetry data collection and analysis |
| Book URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/telemetry_data_collection_and_analysis/index |
| Documentation category | Observability |
| Retrieved date | 2026-07-06 |
| Sections used | Chapter 1. Telemetry data collection and analysis; Chapter 2. Disable telemetry data collection; Chapter 3. Enable telemetry data collection; Chapter 4. Customize Segment source |

## Supporting Red Hat Sources

| Source | Role |
|--------|------|
| Red Hat Developer Hub dynamic plugins documentation | Dynamic plugin ConfigMap structure and `dynamicPluginsConfigMapName` field |

## Source Boundaries

- Product configuration truth: official Red Hat Developer Hub 1.10 Telemetry
  Data Collection and Analysis book above.
- Web analytics: Segment-based, tracking page visits, clicks, system info,
  anonymous IP (`0.0.0.0`), and anonymous username hashes.
- System observability: OpenTelemetry-based, tracking CPU, memory, performance
  metrics, traces, and logs.
- Plugin package path:
  `./dynamic-plugins/dist/backstage-community-plugin-analytics-provider-segment`
  is the documented dynamic plugin for Segment analytics.
- `SEGMENT_WRITE_KEY` environment variable is the documented mechanism for
  custom Segment source configuration.
- Not authoritative: upstream Segment SDK internals, OpenTelemetry Collector
  configuration beyond what the RHDH docs describe, or Backstage analytics
  plugin internals.

## Unresolved Or Environment-Specific Items

- Custom Segment write key is environment-specific.
  Verification: obtain approved Segment source and write key before
  customizing.
- In air-gapped environments, disabling telemetry avoids outbound requests.
  Verification: confirm network policy and outbound connectivity requirements
  before deciding to enable or disable.
- Data collection notice: when customizing the Segment source, a custom
  data collection notice must be created for application users. This is an
  organizational policy decision.
