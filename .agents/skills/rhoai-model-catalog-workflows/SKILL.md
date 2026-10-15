---
name: rhoai-model-catalog-workflows
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when a user or demo script browses the OpenShift AI Model Catalog in
  this repo: finding a model, reading its card, operational metrics,
  performance view or tensor variants, safety and security insights, then
  registering it into `demo-registry` or deploying it from the catalog into a
  project such as `internal-models` with the Stage 040 hardware profile, queue
  and llm-d templates. Do NOT use for catalog sources and the Agent Catalog
  (use rhoai-model-catalog-sources), registry records (use
  rhoai-model-registry-workflows), the GitOps-managed `qwen3-8-27b` deployment
  (use rhoai-model-deployment), or EvalHub runs (use rhoai-evaluation).
---

# RHOAI Model Catalog Workflows

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/030-private-model-serving/030-private-model-serving/README.md`
("model-discovery") and
`gitops/stages/040-governed-models-as-a-service/040-local-models/README.md`.

## When to use

- Walking the "discover, compare, register, deploy" story in the dashboard.
- A catalog model registers or deploys into the wrong place, or the deploy
  wizard offers no hardware profile, queue or topology.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Catalog and registry turned on by Stage 030 (`modelregistry` Managed, `disableModelCatalog: false`, `disableModelRegistry: false`) | `gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/enable-job.yaml` | [Model catalog and model registries][overview] |
| One registry, `demo-registry` in `rhoai-model-registries`; both persona groups bound to `registry-user-demo-registry` | `gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/registry/` | [Register a model from the catalog][register] |
| The production model `qwen3-8-27b` is deployed from Git (`LLMInferenceService`), not from the catalog; catalog deployment is a user demonstration | `gitops/stages/040-governed-models-as-a-service/040-local-models/qwen38-27b-llminferenceservice.yaml` | [Deploy a model from the catalog][deploy] |
| Catalog deployments into `internal-models` use hardware profile `gpu-rtxpro6000` or `gpu-reserved-demo`, LocalQueues `lq-gpu-rtxpro6000` / `lq-gpu-reserved-demo`, and the llm-d templates `single-node-exclusive-gpu` + `single-node-queue-router` | `gitops/stages/040-governed-models-as-a-service/040-local-models/` | [Deploy a model from the catalog][deploy] |
| Safety and security insights need the EvalHub `get evaluations` grant in `rhoai-model-registries` | `gitops/stages/050-model-evaluation/050-evalhub/tenant/catalog-insights-role.yaml` | [Safety and security insights][safety] |

## Procedure

1. Check discovery is up (after the OpenShift safety guard in `AGENTS.md`):

   ```bash
   ./stages/030-private-model-serving/validate-model-discovery.sh
   oc get modelregistry demo-registry -n rhoai-model-registries
   ```

2. In the dashboard: find the model, compare variants by tensor type and the
   performance view, check safety insights, then register it into
   `demo-registry` and deploy into a project you own.
3. To publish a catalog-deployed model to developers, move it to Git and MaaS
   (`MaaSModelRef`, subscription) instead of keeping a dashboard-only
   deployment; see `rhoai-model-deployment` and `rhoai-maas-governance`.

## Pitfalls

- A dashboard deployment in `internal-models` competes with `qwen3-8-27b`
  for the GPU queues; check quota with `rhoai-kueue-workload-management`
  before deploying.
- A catalog-deployed model is not governed until it has a `MaaSModelRef`;
  clients must not call its pod or route directly.
- Validated-model performance data describes Red Hat's test hardware, not
  this cluster's g7e/g6e nodes; measure with `run-guidellm-load-test`.
- Safety insights show nothing without the EvalHub Role:
  `rhoai-model-catalog-sources` and `rhoai-evaluation`.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Concepts | [Model catalog and model registries][overview] |
| Discover | [Discover models][discover], [Operational metrics][opmetrics] |
| Performance | [Performance view][perfview], [Validated model performance][perfdata] |
| Variants | [Tensor types and variants][tensor], [Filter by tensor type][tensorfilter] |
| Safety | [Safety and security insights][safety], [View insights][viewsafety], [Filter results][filtersafety] |
| Register, deploy | [Register a model][register], [Deploy a model][deploy] |

## Related skills

`rhoai-model-catalog-sources`, `rhoai-model-registry`,
`rhoai-model-registry-workflows`, `rhoai-model-deployment`,
`rhoai-maas-governance`, `rhoai-evaluation`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#overview-of-model-registries_working-model-catalog
[discover]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#viewing-models-in-the-catalog_working-model-catalog
[opmetrics]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#about-model-catalog-operational-metrics_working-model-catalog
[perfview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#about-the-model-performance-view_working-model-catalog
[perfdata]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#viewing-performance-data-for-validated-models_working-model-catalog
[tensor]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#about-tensor-type-model-variants_working-model-catalog
[tensorfilter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#filtering-model-catalog-tensor-type_working-model-catalog
[safety]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#about-safety-and-security-insights_working-model-catalog
[viewsafety]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#viewing-safety-and-security-insights_working-model-catalog
[filtersafety]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#filtering-safety-and-security-evaluation-results_working-model-catalog
[register]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#registering-a-model-from-the-model-catalog_working-model-catalog
[deploy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_the_model_catalog/index#deploying-a-model-from-the-model-catalog_working-model-catalog
