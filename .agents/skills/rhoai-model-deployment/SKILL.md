---
name: rhoai-model-deployment
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when deploying, stopping, or querying a model in this repo outside the
  llm-d path: the Stage 050 candidate InferenceService qwen3-8-27b-int4 in
  evaluated-models (RawDeployment, Recreate, token auth, stop annotation),
  model storage choice (pinned Hugging Face URI vs OCI modelcar, PVC, S3),
  hardware profile and Kueue labels on a deployment, the Deploy a model wizard
  and AI asset endpoints, deployment strategy, and token or endpoint lookup.
  Do NOT use for enabling KServe or adding runtimes (use
  rhoai-model-serving-platform), the LLMInferenceService qwen3-8-27b (use
  rhoai-distributed-inference-llmd), MaaS access to models (use
  rhoai-maas-governance), or metrics (use rhoai-model-management-monitoring).
---

# Model deployment

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/050-model-evaluation/050-model-qualification/README.md` (candidate
`InferenceService`); the llm-d model is in `rhoai-distributed-inference-llmd`.

## When to use

- A change touches `candidate-qwen3-8-27b-int4.yaml` or adds a model
  deployment to Git.
- Someone deploys a model from the dashboard into `demo-sandbox` or
  `internal-models` and asks which storage, profile or runtime to pick.
- A deployed model does not start, does not get a GPU, or does not appear in a
  dashboard form.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Model deployments are Git manifests, not wizard output: Stage 040 `LLMInferenceService` for the served model, Stage 050 `InferenceService` (`serving.kserve.io/v1beta1`) for the evaluation candidate | `gitops/stages/040-governed-models-as-a-service/040-local-models/`, `gitops/stages/050-model-evaluation/050-model-qualification/candidate-qwen3-8-27b-int4.yaml` | [Deploy on the model serving platform][deploy] |
| Model source is a URI pinned to a 40-character Hugging Face revision (`hf://RedHatAI/...:<sha>`); no Red Hat OCI modelcar exists for these checkpoints | both manifests (`storageUri`, `spec.model.uri`) | [Storing models][storing], [OCI model storage][oci] |
| Candidate: `serving.kserve.io/deploymentMode: RawDeployment`, `deploymentStrategy.type: Recreate`, one replica | candidate manifest | [KServe deployment modes][modes], [Deployment strategies][strategies] |
| Candidate runs stopped in Git (`serving.kserve.io/stop: "true"`) so it holds no GPU; Argo CD reports it `Suspended` | candidate manifest; model-qualification README ("Why the Application is Suspended") | — (Argo CD health check) |
| Token authentication on (`security.opendatahub.io/enable-auth: "true"`) with a project-scoped client ServiceAccount token; no external route of its own | `candidate-qwen3-8-27b-int4.yaml`, `candidate-model-auth.yaml` | [Token for a deployed model][token], [Inference endpoint][endpoint] |
| GPU placement by hardware-profile annotations plus the `kueue.x-k8s.io/queue-name` label (`gpu-reserved-demo`/`lq-gpu-reserved-demo` for the candidate, `gpu-rtxpro6000`/`lq-gpu-rtxpro6000` for the served model) | both manifests; profiles in `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/` | [Hardware profile matching][hw-match]; see `rhoai-kueue-workload-management` |
| Developers and tools reach models only through MaaS, never the deployment endpoint; `opendatahub.io/genai-asset: "true"` marks the served model for Gen AI studio | `040-local-models/qwen38-27b-llminferenceservice.yaml` | [Deploy on the model serving platform][deploy] (AI asset endpoint); see `rhoai-maas-governance` |

## Procedure

1. Pick the path: an llm-d model behind MaaS goes to
   `rhoai-distributed-inference-llmd`; a project-local `InferenceService`
   follows the Stage 050 candidate pattern (template-instantiated runtime,
   pinned revision, Recreate, auth on, hardware profile, queue label).
2. Deploy and validate with the owning stage:
   `./stages/050-model-evaluation/deploy.sh` and
   `./stages/050-model-evaluation/validate.sh` (accepts `Suspended` only for a
   stopped `InferenceService`).
3. Start or stop the candidate by the `serving.kserve.io/stop` annotation in
   Git; free the GPU first if the served model needs it
   (`docs/OPERATIONS.md#resuming-gpu-backed-stages-after-shutdown`).
4. Inspect, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get inferenceservice -n evaluated-models
   oc get inferenceservice qwen3-8-27b-int4 -n evaluated-models \
     -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
   oc get workload -n evaluated-models
   ```

## Pitfalls

- The wizard's llm-d runtime defaults to Recreate, but the Git-managed
  `LLMInferenceService` rolls out with `maxSurge` and can deadlock on a full
  GPU queue (`docs/TROUBLESHOOTING.md#qwen-serving-change-never-finishes-rolling-out`).
- Rolling update needs about twice the requested resources during the switch;
  on single-GPU nodes use Recreate ([Choosing a strategy][choose]).
- Canary rollout applies to `InferenceService` in RawDeployment mode only, not
  to `LLMInferenceService` ([Canary limitations][canary-limits]).
- The Start evaluation run form lists `InferenceService` objects only
  (`docs/TROUBLESHOOTING.md#start-evaluation-run-offers-no-model-to-choose`).
- No Kueue Workload means a missing queue label or unmanaged namespace
  (`docs/TROUBLESHOOTING.md#private-models-do-not-produce-kueue-workloads`).
- The `hf://` URI form is proven by the running deployments, not named in the
  3.5 storage chapter; verify after upgrades.

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| Model storage | [Storing models][storing], [OCI model storage][oci], [Upload to a PVC][pvc] |
| Deploy | [KServe deployment modes][modes], [Runtime auto-selection][autoselect], [Hardware profile matching][hw-match], [Deploy on the platform][deploy], [OCI image by CLI][oci-cli] |
| Strategy and rollout | [Deployment strategies][strategies], [Choosing a strategy][choose], [Canary rollout][canary], [Canary limitations][canary-limits] |
| Inference | [Token for a deployed model][token], [Inference endpoint][endpoint], [Inference endpoints by runtime][endpoints] |
| Not used | [NIM deployments][nim], [Precache an LLMInferenceService][precache] |

## Related skills

`rhoai-model-serving-platform`, `rhoai-distributed-inference-llmd`,
`rhoai-maas-governance`, `rhoai-kueue-workload-management`,
`rhoai-hardware-profiles`, `rhoai-evaluation`, `rhoai-model-evaluation`,
`rhoai-gen-ai-playground`, `rhoai-model-registry-workflows`.

[storing]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#deploying-models_rhoai-user
[oci]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#using-oci-containers-for-model-storage_rhoai-user
[pvc]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#uploading-model-files-to-pvc_rhoai-user
[modes]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#about-kserve-deployment-modes_rhoai-user
[autoselect]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#automatic-selection-of-serving-runtimes_rhoai-user
[hw-match]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#hardware_profile_matching
[strategies]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#deployment-strategies-for-resource-optimization_rhoai-user
[choose]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#choosing_a_deployment_strategy
[canary]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#canary-rollout-for-rawdeployment-mode_rhoai-user
[canary-limits]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#known-limitations-for-canary-rollout_rhoai-user
[deploy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#deploying-models-on-the-model-serving-platform_rhoai-user
[oci-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#deploying-model-stored-in-oci-image_rhoai-user
[nim]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#deploying-models-on-the-NVIDIA-NIM-model-serving-platform_rhoai-user
[precache]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#deploying-an-llminferenceservice-with-a-cached-model_rhoai-user
[token]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#accessing-authentication-token-for-deployed-model_rhoai-user
[endpoint]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#accessing-inference-endpoint-for-model_rhoai-user
[endpoints]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index#inference-endpoints_rhoai-user
