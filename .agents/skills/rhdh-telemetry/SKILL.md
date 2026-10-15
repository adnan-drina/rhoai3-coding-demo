---
name: rhdh-telemetry
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when reviewing or changing Red Hat Developer Hub 1.10 telemetry data
  collection in this demo: the default-on analytics-provider-segment plugin,
  disabling or enabling it through the dynamic-plugins-rhdh ConfigMap, and
  customizing the Segment source. Do NOT use for log levels or metrics (use
  rhdh-monitoring), audit events (use rhdh-audit-logs), or in-portal usage
  analytics (use rhdh-adoption-insights).
---

# Developer Hub telemetry

Thin skill: repo decisions and pitfalls here, product behavior in the linked
Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md`.

## When to use

- Someone asks whether the portal sends usage data to Red Hat, or wants it off.
- A change touches the plugin list in
  `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Telemetry is disabled: `analytics-provider-segment` is listed with `disabled: true` (2026-10-15) | `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-instance/dynamic-plugins-configmap.yaml` | [Telemetry data collection][about] |
| Plugins are configured only through the `dynamic-plugins-rhdh` ConfigMap referenced by the `Backstage` CR (Operator path, not Helm) | `.../rhdh-instance/backstage.yaml` (`dynamicPluginsConfigMapName`) | [Disable with the Operator][off-op] |

The component README's alignment table records this decision.

## Procedure

1. To re-enable: set `disabled: false` on the `analytics-provider-segment`
   entry in `dynamic-plugins-configmap.yaml` ([Operator procedure][on-op]);
   to change the destination, follow
   [Customize the Segment source][seg-op]. Never put a write key in Git; use
   `rhdh-secrets` (written by the configure hook) or a new Secret.
2. Sync through the stage: `./stages/070-advanced-app-platform/deploy.sh`,
   then `./stages/070-advanced-app-platform/validate.sh`.
3. Check by hand (read-only, after the OpenShift safety guard in `AGENTS.md`):

   ```bash
   oc get configmap dynamic-plugins-rhdh -n rhdh -o yaml | grep -n -A1 segment
   oc get backstage developer-hub -n rhdh -o jsonpath='{.spec.application.dynamicPluginsConfigMapName}{"\n"}'
   ```

## Pitfalls

- The plugin is default-on: removing the entry from Git turns telemetry back
  on. Review the ConfigMap, not the README, to know the state.
- Expect a portal rollout after a plugin change; with `maxSurge: 0`
  (`backstage.yaml`) the old pod stops first, so the portal is briefly
  unavailable.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| What is collected | [Telemetry data collection][about] |
| Disable | [Disable telemetry][off], [with the Operator][off-op] |
| Enable | [Enable telemetry][on], [with the Operator][on-op] |
| Segment source | [Customize the Segment source][seg], [with the Operator][seg-op] |

## Related skills

`rhdh-dynamic-plugins-install`, `rhdh-adoption-insights`, `rhdh-monitoring`, `rhdh-configure`.

[about]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/telemetry_data_collection_and_analysis/index#telemetry-data-collection-and-analysis_telemetry-data-collection-and-analysis
[off]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/telemetry_data_collection_and_analysis/index#disable-telemetry-data-collection-in-rhdh_telemetry-data-collection-and-analysis
[off-op]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/telemetry_data_collection_and_analysis/index#disable-telemetry-data-collection-using-the-operator_disable-telemetry-data-collection-in-rhdh
[on]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/telemetry_data_collection_and_analysis/index#enable-telemetry-data-collection-in-rhdh_telemetry-data-collection-and-analysis
[on-op]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/telemetry_data_collection_and_analysis/index#enable-telemetry-data-collection-using-the-operator_enable-telemetry-data-collection-in-rhdh
[seg]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/telemetry_data_collection_and_analysis/index#customize-segment-source_telemetry-data-collection-and-analysis
[seg-op]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/telemetry_data_collection_and_analysis/index#customize-segment-source-using-the-operator_customize-segment-source
