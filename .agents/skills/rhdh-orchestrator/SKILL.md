---
name: rhdh-orchestrator
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone asks about the Red Hat Developer Hub 1.10 Orchestrator:
  serverless workflows (SonataFlow, OpenShift Serverless Logic), Orchestrator
  plugins, their Operator or Helm installation, CloudEvents triggers, RBAC and
  workflow troubleshooting. Not used in this repo: self-service runs through
  Software Templates. Do NOT use for Software Templates or the scaffolder (use
  rhdh-develop) or plugin wiring in general (use
  rhdh-dynamic-plugins-configure).
---

# Developer Hub Orchestrator

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- Someone proposes serverless workflows or the Orchestrator plugins for Developer Hub.

## Not used in this repo

Self-service in this repo uses Software Templates
(`gitops/stages/070-advanced-app-platform/rhdh/templates/`) and the
scaffolder; no Orchestrator plugin, SonataFlow or OpenShift Serverless Logic
is installed.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| About Orchestrator | [About Orchestrator][l1] |
| Compatibility guide | [Compatibility guide][l2] |
| Plugin dependencies for the Operator | [Plugin dependencies for the Operator][l3] |
| Install with the Operator | [Install with the Operator][l4] |
| Plugin permissions (RBAC) | [Plugin permissions (RBAC)][l5] |
| Build and deploy workflows | [Build and deploy workflows][l6] |
| Troubleshooting | [Troubleshooting][l7] |

## Related skills

`rhdh-develop`, `rhdh-dynamic-plugins-configure`, `rhdh-authorization`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/orchestrator_in_red_hat_developer_hub/index#about-orchestrator-in-rhdh_orchestrator-in-rhdh
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/orchestrator_in_red_hat_developer_hub/index#compatibility-guide-for-orchestrator_about-orchestrator-in-rhdh
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/orchestrator_in_red_hat_developer_hub/index#orchestrator-plugin-dependencies-for-operator-installation_about-orchestrator-in-rhdh
[l4]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/orchestrator_in_red_hat_developer_hub/index#install-rhdh-with-orchestrator-by-using-the-rhdh-operator_orchestrator-in-rhdh
[l5]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/orchestrator_in_red_hat_developer_hub/index#manage-orchestrator-plugin-permissions-using-rbac-policies_install-rhdh-with-orchestrator-by-using-the-rhdh-operator
[l6]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/orchestrator_in_red_hat_developer_hub/index#build-and-deploy-serverless-workflows_orchestrator-in-rhdh
[l7]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/orchestrator_in_red_hat_developer_hub/index#diagnose-and-resolve-serverless-workflow-issues_orchestrator-in-rhdh
