---
name: ocp-lightspeed-about
metadata:
  author: rhoai3-coding-demo
  version: 3.0.0
  product: ocp_lightspeed
  docs-version: "2.0"
  skill-group: "OpenShift Platform"
description: >
  Use when explaining what OpenShift Lightspeed is on this demo cluster: the
  console AI assistant preinstalled by the environment provisioner (not managed
  in Git), its relation to the demo's private models and MaaS (Qwen by
  default, Nemotron 3 Ultra as the manual fallback), LLM provider and
  data-handling questions, and which documentation set covers the installed
  2.0.x operator. Do NOT use for installing (use
  ocp-lightspeed-install), OLSConfig changes (use ocp-lightspeed-configure),
  chat or REST API use (use ocp-lightspeed-operate), or failures (use
  ocp-lightspeed-troubleshoot).
---

# OpenShift Lightspeed: what it is here

Thin skill: repo decisions here, product concepts in the linked OpenShift
Lightspeed documentation. The version lives in
`.agents/references/red-hat-doc-map.yaml` (`products.ocp_lightspeed`).

## When to use

- Someone asks whether Lightspeed is part of the demo or uses its models.
- Deciding whether a Lightspeed question belongs to this repo or to the
  environment provisioner.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| The provisioner installs the operator (no Subscription in Git); Stage 040 `040-openshift-lightspeed` owns the OLSConfig | `gitops/stages/040-governed-models-as-a-service/040-openshift-lightspeed/` | [OpenShift Lightspeed overview][overview] |
| The only Git touch point is the plugin name `lightspeed-console-plugin` in the Console `spec.plugins` list | `gitops/stages/010-openshift-ai-platform-foundation/010-console-observability/console-plugins.yaml` | [Supported interfaces][interfaces] |
| Lightspeed answers on the private production model, Qwen through MaaS, by default; Nemotron 3 Ultra through MaaS is the approved external fallback, selected by hand while Qwen is parked; the provisioner's Azure OpenAI stays as a third provider | `040-openshift-lightspeed/olsconfig.yaml`, `stages/040-governed-models-as-a-service/lightspeed/select-model.sh` | [LLM requirements][llm] |
| The OpenShift AI provider type (`rhoai_vllm`) is used against the MaaS gateway's OpenAI-compatible `/v1` API with a MaaS key | `040-openshift-lightspeed/` | [Red Hat OpenShift AI][llm-rhoai] |

## Pitfalls

- Version naming: the installed operator is 2.0.1 (observed 2026-11-12;
  2.0.0 on 2026-10-27, 1.1.5 on 2026-10-15; channel `stable`, Automatic).
  Red Hat published the "2.0" documentation set on 2026-11-12; until then
  the only set was labelled "1.0" and also carried the 1.1.x and 2.0 notes.
  Link `/2.0/`. Four data-handling anchors in the About book moved to the
  `_ols-model-provider-evaluation-results` suffix in 2.0.
- Operator `Succeeded` is not service health. On the observed cluster the
  OLSConfig was NotReady; see `ocp-lightspeed-troubleshoot`.
- Questions leave the cluster to the configured provider. With Qwen they stay
  on the cluster; with the Nemotron fallback they go to an external provider
  through MaaS. Read [data flow][dataflow] and [how data is used][datause]
  before pointing sensitive demo content at the assistant.

## Official documentation (OpenShift Lightspeed, "2.0" set)

| Topic | Section |
|---|---|
| Overview | [OpenShift Lightspeed overview][overview] |
| Cluster requirements | [OpenShift requirements][ocpreq] |
| LLM providers | [Large language model (LLM) requirements][llm] |
| Disconnected clusters | [Restricted networks][disconnected] |
| Data flow | [Data flow architecture][dataflow] |
| Data use and telemetry | [How your data is used][datause], [telemetry and transcripts][telemetry] |

## Related skills

`ocp-lightspeed-release-notes`, `ocp-lightspeed-configure`,
`ocp-lightspeed-troubleshoot`, `rhoai-maas-governance`, `ocp-web-console`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/about/index#ols-openshift-lightspeed-overview_ols-about-openshift-lightspeed
[interfaces]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/about/index#ols-con-supported-interfaces_ols-about-openshift-lightspeed
[ocpreq]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/about/index#ols-openshift-requirements_ols-about-openshift-lightspeed
[llm]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/about/index#ols-large-language-model-requirements_ols-about-openshift-lightspeed
[llm-rhoai]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/about/index#rhoai_ols-large-language-model-requirements
[disconnected]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/about/index#about-running-openshift-lightspeed-in-disconnected-mode_ols-model-provider-evaluation-results
[dataflow]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/about/index#ols-data-flow-architecture_ols-model-provider-evaluation-results
[datause]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/about/index#ols-about-data-use_ols-model-provider-evaluation-results
[telemetry]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/about/index#ols-about-data-telemetry-transcript-and-feedback-collection_ols-model-provider-evaluation-results
