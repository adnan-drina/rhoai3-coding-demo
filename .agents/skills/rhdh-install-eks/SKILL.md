---
name: rhdh-install-eks
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone asks how to install Red Hat Developer Hub 1.10 on Amazon
  Elastic Kubernetes Service (EKS) with the Operator through OLM or with the
  Helm chart, including the registry pull secret and exposing the instance. Not
  used in this repo: Developer Hub runs only on OpenShift. Do NOT use for the
  repo's OpenShift install (use rhdh-install-ocp) or portal configuration (use
  rhdh-configure).
---

# Developer Hub on EKS

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- A question is about running Developer Hub on EKS rather than OpenShift.

## Not used in this repo

This repo installs Developer Hub only on OpenShift Container Platform, with
the Operator from `redhat-operators`
(`gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-operator/`). No EKS
manifests exist.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Install with the Operator | [Install with the Operator][l1] |
| Install the Operator through OLM | [Install the Operator through OLM][l2] |
| Pull secret for the instance namespace | [Pull secret for the instance namespace][l3] |
| Expose the instance | [Expose the instance][l4] |
| Deploy with the Helm chart | [Deploy with the Helm chart][l5] |

## Related skills

`rhdh-install-ocp`, `rhdh-helm-reference`, `rhdh-monitoring`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_amazon_elastic_kubernetes_service_eks/index#install-rhdh-on-by-using-the-operator_installing-rhdh-on-eks
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_amazon_elastic_kubernetes_service_eks/index#install-the-operator-on-eks-by-using-olm_install-rhdh-on-by-using-the-operator
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_amazon_elastic_kubernetes_service_eks/index#provision-your-pull-secret-to-your-rhdh-instance-namespace_install-rhdh-on-by-using-the-operator
[l4]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_amazon_elastic_kubernetes_service_eks/index#expose-your-operator-based-instance-on-eks_install-rhdh-on-by-using-the-operator
[l5]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_amazon_elastic_kubernetes_service_eks/index#deploy-on-eks-with-the-helm-chart_installing-rhdh-on-eks
