---
name: rhdh-openshift-ai-connector
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone asks about the OpenShift AI Connector for Red Hat Developer
  Hub 1.10 (Developer Preview): mapping OpenShift AI model registry and catalog
  assets to catalog entities, setup, metadata enrichment and troubleshooting.
  Not used in this repo. Do NOT use for the model registry itself (use
  rhoai-model-registry) or MaaS model access (use rhoai-maas-governance).
---

# OpenShift AI Connector for Developer Hub

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- Someone wants OpenShift AI models to appear as Developer Hub catalog entities.

## Not used in this repo

The Developer Hub catalog in this repo is generated from
`gitops/stages/070-advanced-app-platform/rhdh/catalog/all.yaml` and lists no
AI model entities; the connector is not installed. Models are published
through MaaS (Stage 040). Developer Preview in 1.10.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| AI assets in the catalog | [AI assets in the catalog][l1] |
| Set up the connector | [Set up the connector][l2] |
| Enrich model metadata | [Enrich model metadata][l3] |
| Troubleshooting | [Troubleshooting][l4] |

## Related skills

`rhoai-model-registry`, `rhoai-maas-governance`, `rhdh-dynamic-plugins-install`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/accelerate_ai_development_with_openshift_ai_connector_for_red_hat_developer_hub/index#understand-how-ai-assets-map-to-the-rhdh-catalog_accelerating-ai-development-with-openshift-ai-connector-for-rhdh
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/accelerate_ai_development_with_openshift_ai_connector_for_red_hat_developer_hub/index#set-up-with_accelerating-ai-development-with-openshift-ai-connector-for-rhdh
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/accelerate_ai_development_with_openshift_ai_connector_for_red_hat_developer_hub/index#enrich-ai-model-metadata-for-enhanced-rhdh-experience_accelerating-ai-development-with-openshift-ai-connector-for-rhdh
[l4]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/accelerate_ai_development_with_openshift_ai_connector_for_red_hat_developer_hub/index#troubleshoot-connector-functionality_accelerating-ai-development-with-openshift-ai-connector-for-rhdh
