---
name: rhoai-model-registry-workflows
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when registering or reading records in `demo-registry`: the Stage 040
  deploy.sh registry entries for the private Qwen 3.8 checkpoints and
  their `modelregistry.opendatahub.io/*` labels on the LLMInferenceService,
  the Stage 050 `evalhub.*` evaluation custom properties on a model
  version, registry API calls through the authenticated route, or dashboard
  registry tasks (versions, metadata, transfer jobs, archive, restore). Do NOT
  use for the registry service, database or permissions (use
  rhoai-model-registry), deploying models (use rhoai-model-deployment), or
  catalog discovery (use rhoai-model-catalog-workflows).
---

# RHOAI Model Registry Workflows

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/040-governed-models-as-a-service/040-local-models/README.md`
(registry linkage) and `stages/050-model-evaluation/README.md` (evaluation
records).

## When to use

- A deployed private model is missing from the registry, or its deployment
  is not linked to its registry entry.
- Recording a completed EvalHub job on a model version.
- Adding a model format, or archiving an old checkpoint.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Records are written by scripts through the registry API (`/api/model_registry/v1alpha3`, caller's token, CA-verified route `demo-registry-https`), not the dashboard | `stages/040-governed-models-as-a-service/deploy.sh` | [Register a model][register] |
| One registered model per checkpoint (name = repository, e.g. `Qwen3.8-27B-NVFP4`), one version per immutable revision (`source-<sha>`), one artifact with the pinned `hf://` URI; idempotent, never overwrites a differing artifact | same script | [Register a model version][version] |
| Prepared format alternates (`040-local-models/components/qwen38-fp8`) are registered without deployment linkage | `gitops/stages/040-governed-models-as-a-service/040-local-models/components/` | [View registered models][view] |
| Every model the demo serves has a record: Stage 040 registers Qwen, its alternates and the showback dedicated Mistral (linked once the optional showback component creates its stopped deployment); Stage 050 registers the risk assessment helper `gemma-2-9b-abliterated` and links its InferenceService | `stages/040-governed-models-as-a-service/deploy.sh`, `stages/050-model-evaluation/deploy.sh` | [Register a model][register] |
| Model labels and properties are declared in Git (`model-registry-metadata.json` beside each model manifest, keyed by registered model name). A label is a string custom property with an empty value, the form the dashboard shows and searches. Vocabulary: role (`shared`, `dedicated`, `production`, `onboarding-candidate`, `evaluation-helper`), capability (`coding`, `tool-calling`, `text-generation`, the catalog's task names) and caveats (`no-safety-alignment`, `risk-assessment`). Properties: `model_type` (the dashboard's model type field), `provider`, `license`, `owner_stage`. Deploy makes the labels exactly the declared set and sets declared properties; other properties (evaluation results) stay | `gitops/stages/040-governed-models-as-a-service/040-local-models/model-registry-metadata.json` and peers | [Edit model metadata][editmodel] |
| Deployment linkage via labels `modelregistry.opendatahub.io/registered-model-id` and `model-version-id` stamped on the LLMInferenceService; Git sets only `modelregistry.opendatahub.io/name: demo-registry` and delegates the id labels | `gitops/stages/040-governed-models-as-a-service/040-local-models/qwen38-27b-llminferenceservice.yaml` | not product guidance |
| The registry controller in odh-model-controller (`ModelRegistryInferenceService`) records only `serving.kserve.io` InferenceServices (serving environment = namespace, record `<name>/<uid>`, label `modelregistry.opendatahub.io/inference-service-id`); it ignores llm-d `LLMInferenceService`s. Stage 040 `deploy.sh` writes the same record for each LLMInferenceService (`runtime: llm-d`, `desiredState` UNDEPLOYED while parked) and stamps the label, so the registry API lists every deployment. The dashboard's registry Deployments column still shows `-` for llm-d models: it counts only Kubernetes objects of kind `InferenceService` carrying `registered-model-id` (odh-dashboard `packages/model-serving/modelRegistry/DeploymentsColumn.tsx`) | `stages/040-governed-models-as-a-service/deploy.sh` | not product guidance (observed on 3.5.2) |
| Evaluation evidence lands as `evalhub.*` custom properties on the model version, entered in the dashboard model version **Properties**, because the dashboard renders version properties (or written by `stages/050-model-evaluation/evaluation/record.sh`) | — | [Edit model version metadata][editversion] |
| Models are deployed from GitOps, not from the registry's Deploy action | `gitops/stages/040-governed-models-as-a-service/040-local-models/` | [Deploy a model version][deploy] (not used) |

## Procedure

1. Register after Stage 040 reconciles (after the OpenShift safety guard in
   `AGENTS.md`):

   ```bash
   ./stages/040-governed-models-as-a-service/deploy.sh
   ```

   Add evaluation results as `evalhub.*` custom properties in the dashboard
   model version **Properties**.

2. Inspect read-only:

   ```bash
   oc get llminferenceservice qwen3-8-27b -n internal-models --show-labels
   oc get route demo-registry-https -n rhoai-model-registries -o jsonpath='{.spec.host}{"\n"}'
   ```

## Pitfalls

- Registration refuses until Stage 040 is reconciled at the reviewed SHA and
  the active model is Ready (a parked model registers metadata only).
- The registry's REST route is disabled; scripts call the kube-rbac-proxy
  route `demo-registry-https` with a bearer token
  (`rhoai-model-registry` owns that decision).
- Deployment of URI-registered models is supported only for public OCI
  repositories ([Register a model][register]); the `hf://` entries here are
  records, not deployable sources.
- Models with deployed versions cannot be archived; delete deployments first
  ([Archive a model][archive]).
- The registry API also accepts metric artifacts and experiment runs, but the
  3.5 dashboard does not render them; use version custom properties.

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| Overview | [Work with model registries][work] |
| Register | [Register a model][register], [Register a version][version], [Register as OCI image][oci] |
| Transfer jobs | [Monitor][transfer], [Retry][retry], [Delete][deljob] |
| View and edit | [View models][view], [View versions][viewversions], [Edit model metadata][editmodel], [Edit version metadata][editversion] |
| Deploy | [Deploy a version][deploy], [Edit deployment][editdeploy], [Delete deployment][deldeploy] |
| Archive, restore | [Archive model][archive], [Archive version][archiveversion], [Restore model][restore], [Restore version][restoreversion] |

## Related skills

`rhoai-model-registry`, `rhoai-model-deployment`, `rhoai-evaluation`,
`rhoai-model-catalog-workflows`, `rhoai-maas-governance`.

[work]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#working-with-model-registries_model-registry
[register]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#registering-a-model_model-registry
[version]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#registering-a-model-version_model-registry
[oci]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#registering-model-as-oci-image_model-registry
[transfer]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#monitoring-model-transfer-jobs_model-registry
[retry]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#retrying-failed-model-transfer-job_model-registry
[deljob]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#deleting-model-transfer-job_model-registry
[view]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#viewing-registered-models_model-registry
[viewversions]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#viewing-registered-model-versions_model-registry
[editmodel]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#editing-model-metadata-in-a-model-registry_model-registry
[editversion]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#editing-model-version-metadata-in-a-model-registry_model-registry
[deploy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#deploying-a-model-version-from-a-model-registry_model-registry
[editdeploy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#editing-the-deployment-properties-of-a-model-deployed-by-using-the-model-serving-platform_model-registry
[deldeploy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#deleting-a-deployed-model-version-from-a-model-registry_model-registry
[archive]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#archiving-a-model_model-registry
[archiveversion]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#archiving-a-model-version_model-registry
[restore]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#restoring-a-model_model-registry
[restoreversion]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_model_registries/index#restoring-a-model-version_model-registry
