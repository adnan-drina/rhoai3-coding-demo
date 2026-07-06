# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Helm Chart configuration reference |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/helm_chart_configuration_reference/index |
| Documentation category | Reference / Helm Chart configuration reference |
| Retrieved date | 2026-07-06 |
| Sections used | Preface; 1 Helm Chart configuration reference (1.1 Display values with Helm CLI, 1.2 Root namespace value, 1.3 Global namespace values, 1.4 Orchestrator namespace values, 1.5 Route namespace values, 1.6 Test namespace values, 1.7 Upstream namespace values, 1.8 Additional upstream Backstage Chart values); 2 Helm Chart Orchestrator infrastructure reference (2.1 Display values, 2.2 Values) |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/dynamic_plugins_reference/index | Plugin names and versions referenced in dynamic plugin configuration |
| https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index | Plugin configuration procedures |
| https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index | Installation context for Helm-based deployment |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHDH baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |

## Source Boundaries

- Product authority: the official Red Hat Developer Hub 1.10 Helm Chart
  configuration reference guide above.
- This skill defines Helm Chart values, defaults, types, and hierarchical
  structure.
- It does not define individual plugin configuration procedures. Use
  `rhdh-dynamic-plugins-configure` for that.
- It does not define the catalog of available plugins. Use
  `rhdh-dynamic-plugins-reference` for that.
