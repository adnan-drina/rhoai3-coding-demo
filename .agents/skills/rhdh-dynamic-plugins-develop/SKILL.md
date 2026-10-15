---
name: rhdh-dynamic-plugins-develop
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone wants to write a custom Red Hat Developer Hub 1.10 plugin,
  convert a Backstage plugin into a dynamic plugin, package it, or test it
  locally. Not used in this repo: only Red Hat packaged and
  rhdh-plugin-export-overlays OCI plugins are enabled. Do NOT use for enabling
  existing plugins (use rhdh-dynamic-plugins-install) or configuring them (use
  rhdh-dynamic-plugins-configure).
---

# Developing dynamic plugins

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- A custom plugin or a conversion to a dynamic plugin is proposed.

## Not used in this repo

The repo builds no plugins. It enables bundled plugins and digest-pinned OCI
packages from `rhdh-plugin-export-overlays` in
`gitops/stages/070-advanced-app-platform/rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Dynamic plugins | [Dynamic plugins][l1] |
| Prepare the development environment | [Prepare the development environment][l2] |
| Determine the RHDH version | [Determine the RHDH version][l3] |
| Develop a new plugin | [Develop a new plugin][l4] |
| Convert a custom plugin | [Convert a custom plugin][l5] |
| Add a dynamic plugin to RHDH | [Add a dynamic plugin to RHDH][l6] |
| Verify plugins locally | [Verify plugins locally][l7] |

## Related skills

`rhdh-dynamic-plugins-install`, `rhdh-dynamic-plugins-configure`, `rhdh-dynamic-plugins-reference`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/develop_and_deploy_dynamic_plugins_in_red_hat_developer_hub/index#dynamic-plugins_develop-and-deploy-plugins-in-rhdh
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/develop_and_deploy_dynamic_plugins_in_red_hat_developer_hub/index#prepare-your-development-environment_develop-and-deploy-plugins-in-rhdh
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/develop_and_deploy_dynamic_plugins_in_red_hat_developer_hub/index#determine-rhdh-version_develop-a-new-plugin
[l4]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/develop_and_deploy_dynamic_plugins_in_red_hat_developer_hub/index#develop-a-new-plugin_develop-and-deploy-plugins-in-rhdh
[l5]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/develop_and_deploy_dynamic_plugins_in_red_hat_developer_hub/index#convert-a-custom-plugin-into-a-dynamic-plugin_develop-and-deploy-plugins-in-rhdh
[l6]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/develop_and_deploy_dynamic_plugins_in_red_hat_developer_hub/index#add-a-dynamic-plugin-to-rhdh_deployment-configurations
[l7]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/develop_and_deploy_dynamic_plugins_in_red_hat_developer_hub/index#verify-plugins-locally_develop-and-deploy-plugins-in-rhdh
