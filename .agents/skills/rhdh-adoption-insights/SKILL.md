---
name: rhdh-adoption-insights
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone asks about the Red Hat Developer Hub 1.10 Adoption Insights
  plugin: enabling, disabling or customizing it, and reading active users, top
  templates, catalog entities, TechDocs and searches. Not used in this repo. Do
  NOT use for telemetry sent to Red Hat (use rhdh-telemetry) or platform metrics
  (use rhdh-monitoring).
---

# Developer Hub Adoption Insights

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- Someone wants portal usage analytics inside Developer Hub.

## Not used in this repo

No Adoption Insights plugin is enabled in
`gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Overview | [Overview][l1] |
| Enable the plugin | [Enable the plugin][l2] |
| Disable the plugin | [Disable the plugin][l3] |
| Customize the plugin | [Customize the plugin][l4] |
| Use Adoption Insights | [Use Adoption Insights][l5] |

## Related skills

`rhdh-telemetry`, `rhdh-dynamic-plugins-install`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/adoption_insights_in_red_hat_developer_hub/index#adoption-insights-overview_adoption-insights-in-rhdh
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/adoption_insights_in_red_hat_developer_hub/index#enable-the-adoption-insights-plugin_adoption-insights-in-rhdh
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/adoption_insights_in_red_hat_developer_hub/index#disable-the-adoption-insights-plugin_adoption-insights-in-rhdh
[l4]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/adoption_insights_in_red_hat_developer_hub/index#customize-the-adoption-insights-plugin-in-rhdh_adoption-insights-in-rhdh
[l5]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/adoption_insights_in_red_hat_developer_hub/index#use-adoption-insights-in-rhdh_adoption-insights-in-rhdh
