---
name: rhoai-model-serving-platform
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing or changing how this repo enables and configures the
  OpenShift AI model-serving platform: the Stage 030 hook Job that sets the
  DataScienceCluster kserve component Managed, the vllm-cuda-runtime
  ServingRuntime instance in evaluated-models, runtime support levels, custom
  or tested-and-verified runtimes, NVIDIA NIM, vLLM runtime parameters, the
  cluster default deployment strategy, model caching, and the serving
  dashboard flags (vLLMDeploymentOnMaaS, llmdTemplates). Do NOT use for
  deploying or querying a model (use rhoai-model-deployment), the llm-d
  LLMInferenceService qwen3-8-27b (use rhoai-distributed-inference-llmd), or
  deployed-model metrics (use rhoai-model-management-monitoring).
---

# Model-serving platform

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/030-private-model-serving/030-private-model-serving/README.md`.

## When to use

- A change touches `gitops/stages/030-private-model-serving/030-private-model-serving/dsc-enablement/`.
- Someone proposes a new `ServingRuntime`, a custom or tested-and-verified
  runtime, NVIDIA NIM, model caching, or a cluster default deployment strategy.
- KServe is not Ready after a Stage 030 sync.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Stage 010 creates `default-dsc` with `kserve` `Removed`; Stage 030 turns it on with a Sync-hook Job that merge-patches only `spec.components.kserve.managementState: Managed` (a delegated field) | `gitops/stages/030-private-model-serving/030-private-model-serving/dsc-enablement/enable-job.yaml` | [Enable the model serving platform][enable] |
| KServe sub-fields (`nim`, `rawDeploymentServiceConfig`, `modelsAsService`, `wva`) are left to operator defaults or Stage 040 | component README ("Delegated fields") | see `rhoai-dsci-dsc-configuration` |
| NVIDIA NIM is not enabled; no NGC credentials exist in the repo | — | [NIM serving platform][nim], [Enable NIM][nim-enable] |
| No custom and no tested-and-verified runtimes; the private model uses the platform-supplied vLLM runtime of llm-d with no image override | `gitops/stages/040-governed-models-as-a-service/040-local-models/qwen38-27b-llminferenceservice.yaml` | [Custom runtime][custom], [Tested and verified runtime][tested], [vLLM support levels][vllm-levels] |
| One `ServingRuntime` `vllm-cuda-runtime` in `evaluated-models`, instantiated from the platform template `vllm-cuda-runtime-template` with a pinned image digest, for the Stage 050 candidate and risk assessment `InferenceService`s | `gitops/stages/050-model-evaluation/050-model-qualification/serving-runtime.yaml` | [Supported runtimes][supported], [ServingRuntime][sr] |
| vLLM parameters are set in the manifest `args`, not through the dashboard runtime-parameter form | the two manifests above | [Customize vLLM runtime][vllm-custom], [Runtime parameters][params] |
| Stage 010 sets `vLLMDeploymentOnMaaS: false`; the Stage 040 MaaS enablement Job turns it and `llmdTemplates` on | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/odhdashboardconfig.yaml`, `gitops/stages/040-governed-models-as-a-service/040-maas-platform/jobs/enable-maas-job.yaml` | [Limited-support runtime visibility][limited] |
| No cluster default deployment strategy in Git (dashboard setting left at its default) | — | [Default deployment strategy][strategy] |
| No model caching (`LocalModelCache`) | — | [Model cache][cache] |

## Procedure

1. Deploy: `./stages/030-private-model-serving/deploy.sh` (pins the
   Application to the published SHA, checks the Stage 010 delegation).
2. Validate: `./stages/030-private-model-serving/validate.sh` (DSC `Ready` and
   `KserveReady`, `default-kserve` `Ready`, owned controller Deployments).
3. Inspect, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.kserve.managementState}{"\n"}'
   oc get kserve default-kserve -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
   oc get servingruntime -A
   oc get templates -n redhat-ods-applications | grep -i runtime
   ```

4. A new runtime needs a README decision recording its support level before it
   goes into Git; instantiate from the platform template and pin the digest,
   as the Stage 050 runtime does.

## Pitfalls

- Never put `kserve` settings in the Stage 010 DSC manifest; Stage 010
  delegates the field and Argo CD ignores it there. Change the hook Job.
- Red Hat does not support custom runtimes, and tested-and-verified runtimes
  are not directly supported ([Custom runtime][custom], [Tested and verified][tested]).
- A pinned runtime image digest does not follow platform upgrades; recheck
  `vllm-cuda-runtime` against the template after each OpenShift AI update.
- `vLLMDeploymentOnMaaS` gates limited-support configurations and is a preview
  feature; see [Limited-support runtime visibility][limited].

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| Platforms | [Model-serving platforms][platforms], [Model serving platform][msp], [NIM][nim] |
| Runtimes | [ServingRuntime][sr], [InferenceService][isvc], [vLLM support levels][vllm-levels], [Accelerators][accel], [Supported][supported], [Tested and verified][tested] |
| Configure | [Enable the platform][enable], [Speculative decoding and multi-modal][specdec], [Custom runtime][custom], [Limited-support via GitOps][limited-gitops] |
| Customize deployments | [Runtime parameters][params], [vLLM runtime][vllm-custom], [Default deployment strategy][strategy] |
| Model cache (not used) | [Model cache][cache], [Enable model caching][cache-enable] |

## Related skills

`rhoai-model-deployment`, `rhoai-distributed-inference-llmd`,
`rhoai-dsci-dsc-configuration`, `rhoai-dashboard-customization`,
`rhoai-hardware-profiles`, `rhoai-nvidia-gpu-accelerators`,
`rhoai-model-management-monitoring`.

[platforms]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#configuring-your-model-serving-platform_rhoai-admin
[msp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#model_serving_platform
[nim]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#nvidia_nim_model_serving_platform
[sr]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#servingruntime
[isvc]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#inferenceservice
[vllm-levels]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#understanding-vllm-support-levels_rhoai-admin
[limited]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#unsupported-runtime-visibility_rhoai-admin
[accel]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#model-serving-runtimes-for-accelerators_rhoai-admin
[supported]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#supported-model-serving-runtimes_rhoai-admin
[tested]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#tested-verified-runtimes_rhoai-admin
[enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#enabling-the-model-serving-platform_rhoai-admin
[specdec]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#enabling-speculative-decoding-and-multi-modal-inferencing_rhoai-admin
[custom]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#adding-a-custom-model-serving-runtime_rhoai-admin
[limited-gitops]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#enabling-unsupported-serving-runtimes-gitops_rhoai-admin
[nim-enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#enabling-the-nvidia-nim-model-serving-platform_rhoai-admin
[params]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#customizing-parameters-serving-runtime_rhoai-admin
[vllm-custom]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#Customizing-the-vllm-runtime_rhoai-admin
[strategy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#setting-a-default-cluster-wide-deployment-strategy_rhoai-admin
[cache]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#model-cache-overview_rhoai-admin
[cache-enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/configuring_your_model-serving_platform/index#enabling-model-caching_rhoai-admin
