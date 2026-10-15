---
name: rhdh-install-airgapped
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone asks how to install Red Hat Developer Hub 1.10 in a fully or
  partially disconnected (air-gapped) environment with the Operator or the Helm
  chart, including image and plugin mirroring. Not used in this repo: the demo
  cluster is connected and pulls OCI plugins from ghcr.io. Do NOT use for the
  repo's connected install (use rhdh-install-ocp) or plugin configuration (use
  rhdh-dynamic-plugins-install).
---

# Developer Hub in an air-gapped environment

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- A disconnected or mirrored-registry install of Developer Hub is discussed.

## Not used in this repo

The demo cluster is connected: the Operator comes from `redhat-operators` and
the Tekton and Argo CD plugins are digest-pinned OCI packages pulled from
ghcr.io
(`gitops/stages/070-advanced-app-platform/rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`).
A disconnected variant would need those plugin images mirrored.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Air-gapped environment overview | [Air-gapped environment overview][l1] |
| Operator, fully disconnected | [Operator, fully disconnected][l2] |
| Operator, partially disconnected | [Operator, partially disconnected][l3] |
| Helm chart on OpenShift | [Helm chart on OpenShift][l4] |
| Helm chart on other Kubernetes | [Helm chart on other Kubernetes][l5] |

## Related skills

`rhdh-install-ocp`, `rhdh-dynamic-plugins-install`, `ocp-image-registry-and-mirroring`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_in_an_air-gapped_environment/index#air-gapped-environment_installing-rhdh-in-an-air-gapped-environment
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_in_an_air-gapped_environment/index#install-rhdh-in-a-fully-disconnected-environment-with-the-operator_install-rhdh-in-an-air-gapped-environment-with-the-operator
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_in_an_air-gapped_environment/index#install-rhdh-in-a-partially-disconnected-environment-with-the-operator_install-rhdh-in-an-air-gapped-environment-with-the-operator
[l4]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_in_an_air-gapped_environment/index#install-rhdh-on-ocp-in-an-air-gapped-environment-with-the-helm-chart_installing-rhdh-in-an-air-gapped-environment
[l5]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_in_an_air-gapped_environment/index#install-rhdh-on-a-supported-kubernetes-platform-in-an-air-gapped-environment-with-the-helm-chart_installing-rhdh-in-an-air-gapped-environment
