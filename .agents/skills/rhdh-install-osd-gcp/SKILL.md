---
name: rhdh-install-osd-gcp
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone asks how to install Red Hat Developer Hub 1.10 on OpenShift
  Dedicated on Google Cloud with the Operator or the Helm chart. Not used in
  this repo: the demo runs on self-managed OpenShift Container Platform. Do NOT
  use for the repo's install (use rhdh-install-ocp) or portal configuration (use
  rhdh-configure).
---

# Developer Hub on OpenShift Dedicated on Google Cloud

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- A question is about OpenShift Dedicated on Google Cloud.

## Not used in this repo

This repo targets self-managed OpenShift Container Platform and installs
Developer Hub with the Operator from
`gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-operator/`.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Install with the Operator | [Install with the Operator][l1] |
| Install with the Helm chart | [Install with the Helm chart][l2] |

## Related skills

`rhdh-install-ocp`, `rhdh-helm-reference`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_dedicated_on_google_cloud/index#install-rhdh-on-on-using-the-operator_installing-rhdh-on-osd-on-gcp
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_dedicated_on_google_cloud/index#install-rhdh-on-on-using-the-helm-chart_installing-rhdh-on-osd-on-gcp
