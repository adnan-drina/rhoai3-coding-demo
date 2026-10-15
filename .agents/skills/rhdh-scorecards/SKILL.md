---
name: rhdh-scorecards
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone asks about Red Hat Developer Hub 1.10 Scorecards: metric
  providers (GitHub, Jira, OpenSSF, Dependabot, file checks), thresholds,
  aggregated KPIs, RBAC and homepage cards. Not used in this repo. Do NOT use
  for SonarQube quality gates in the project pipeline (see
  gitops/stages/070-advanced-app-platform/070-sonarqube/README.md) or RBAC in
  general (use rhdh-authorization).
---

# Developer Hub Scorecards

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- Someone wants component health or compliance scores in the catalog.

## Not used in this repo

No Scorecards plugin is enabled. Code quality in this repo is the SonarQube
gate in each project's Tekton pipeline
(`gitops/stages/070-advanced-app-platform/070-sonarqube/`).

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Scorecards overview | [Scorecards overview][l1] |
| Metric providers and IDs | [Metric providers and IDs][l2] |
| Enable Scorecards | [Enable Scorecards][l3] |
| RBAC by CSV file | [RBAC by CSV file][l4] |
| Metric thresholds | [Metric thresholds][l5] |

## Related skills

`rhdh-authorization`, `rhdh-dynamic-plugins-install`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/evaluate_project_health_using_scorecards/index#component-health-and-compliance-monitoring-using-scorecards_evaluate-project-health-using-scorecards
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/evaluate_project_health_using_scorecards/index#available-scorecard-metric-providers-and-metric-ids_evaluate-project-health-using-scorecards
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/evaluate_project_health_using_scorecards/index#enable-scorecards_set-up-scorecards-to-monitor-your-project-health
[l4]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/evaluate_project_health_using_scorecards/index#configure-rbac-for-scorecards-by-using-the-rbac-csv-file_set-up-scorecards-to-monitor-your-project-health
[l5]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/evaluate_project_health_using_scorecards/index#scorecard-metric-thresholds_evaluate-project-health-using-scorecards
