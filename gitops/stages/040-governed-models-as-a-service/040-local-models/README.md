# Local Models (`040-local-models`)

This Application serves the private coding model `qwen3-8-27b` (Qwen 3.8 27B) on the cluster with Distributed Inference
with llm-d (`LLMInferenceService`) and publishes it to Models-as-a-Service (MaaS) with a `MaaSModelRef`. It also owns the
`internal-models` project, its Kueue LocalQueues and two reusable deployment templates for the dashboard. Developers,
Dev Spaces workspaces, agents, the Gen AI playground and Stage 050 evaluations consume the model only through the MaaS
gateway, never through the pod.

| | |
|---|---|
| Argo CD Application | `040-local-models` ([manifest](../../../applications/040-local-models.yaml)) |
| Deployed by | `stages/040-governed-models-as-a-service/deploy.sh` (deploy-order 5, together with `040-external-models`) |
| Validated by | `stages/040-governed-models-as-a-service/validate.sh --readiness` (runs `validate-native.sh`: model spec equals Git except delegated `replicas`, Ready condition unless parked, owned workloads, route listener set and canonical model header, `MaaSModelRef` Ready/GovernanceAttached/RuntimeReady, template spec and labels); `scripts/shared/stage_apps.py status` (Synced and Healthy at the deployed revision) |
| Sync | Automated, `prune` and `selfHeal`. Sync options `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences` (and a `ServerSideDiff=true` sync option that has no effect). Compare option `ServerSideDiff=true` (annotation). `ignoreDifferences` on the `LLMInferenceService`: `/spec/replicas` and the three `modelregistry.opendatahub.io/*` id labels |
| Depends on | Stage 010 (OpenShift AI with KServe and the `rhods-admins` group), Stage 020 (`gpu-rtxpro6000` hardware profile, `cq-gpu-rtxpro6000` and `cq-gpu-reserved-demo` ClusterQueues, GPU MachineSet), `040-maas-platform` (MaaS enabled), `040-gateway-governance` (Gateway `maas-default-gateway` with listeners `api` and `qwen3-8`) |
| Used by | `040-model-access` (every subscription lists `qwen3-8-27b`), `040-genai-studio` (OpenShift Ops Assistant agent), Stage 050 evaluations, Stage 060 agent runtime subscriptions, Stage 070 Dev Spaces and MTA, `register-model-cards.sh` (Model Registry entries) |

## Why

OpenShift AI 3.5 deploys large language models with Distributed Inference with llm-d. The `LLMInferenceService`
resource gives the model an inference scheduler (endpoint picker), an `InferencePool` and Gateway API routes, and
OpenShift AI enables authentication on it through Red Hat Connectivity Link [1]. MaaS then publishes the model through a
`MaaSModelRef`, so that subscriptions, API keys and token limits apply to it [2]. This keeps sensitive code on a private
model that runs inside the cluster, behind the same governed gateway as the approved external models.

The model, its MaaS reference and the project are one Application because they change together: switching the checkpoint
or the serving arguments syncs only this component. Access policies are a separate Application (`040-model-access`),
so changing who may use the model does not touch the serving deployment.

The two `LLMInferenceServiceConfig` objects are administrator topology templates for the deployment wizard's topology
selector [1, chapter 2]: one single-node workload template with one exclusive NVIDIA GPU, and one router template with
queue-based scoring. The Git-managed model does not reference them; they are offered to dashboard users who deploy their
own models.

## What

### Project and access

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `internal-models` | cluster | Project for private models. Labels: `opendatahub.io/dashboard`, `kueue.openshift.io/managed`, `maas-gateway-access=true` (admitted by the Gateway `api` and `qwen3-8` listeners), Pod Security `restricted` audit/warn. Wave 1, `Prune=false,Delete=false` |
| RoleBinding | `rhods-admins-internal-models-admin` | `internal-models` | ClusterRole `admin` for group `rhods-admins` (hosting administrators). Wave 3 |
| LocalQueue | `lq-gpu-rtxpro6000` | `internal-models` | Queue for the RTX PRO 6000 flavor (ClusterQueue `cq-gpu-rtxpro6000`). Used by the model. Wave 8 |
| LocalQueue | `lq-gpu-reserved-demo` | `internal-models` | Queue for the L40S flavor (ClusterQueue `cq-gpu-reserved-demo`), used by the `gpu-reserved-demo` hardware profile. No model in Git uses it. Wave 8 |

### Dashboard deployment templates (`redhat-ods-applications`)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| LLMInferenceServiceConfig | `single-node-exclusive-gpu` | `redhat-ods-applications` | `opendatahub.io/config-type: workload-single-node`: one replica, 2-4 CPU, 16-24 GiB, one `nvidia.com/gpu`. Wave 15 |
| LLMInferenceServiceConfig | `single-node-queue-router` | `redhat-ods-applications` | `opendatahub.io/config-type: router`, `opendatahub.io/supported-topologies: ["workload-single-node"]`: endpoint picker with `queue-scorer` and `max-score-picker`. Wave 15 |

### Model serving and MaaS publication

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| LLMInferenceService (`serving.kserve.io/v1alpha2`) | `qwen3-8-27b` | `internal-models` | vLLM serving of `RedHatAI/Qwen3.8-27B-NVFP4` at a pinned Hugging Face revision on one RTX PRO 6000 (hardware profile `gpu-rtxpro6000`, queue `lq-gpu-rtxpro6000`). Routes on Gateway `maas-default-gateway` listeners `qwen3-8` and `api`. Wave 16 |
| MaaSModelRef | `qwen3-8-27b` | `internal-models` | Publishes the model to MaaS. Clients use the canonical id `publishers/internal-models/models/qwen3-8-27b` on the common `/v1` base. Wave 17 |

### Optional Kustomize component `components/qwen38-fp8`

Not rendered by default. When listed under `components:` in `kustomization.yaml`, it patches the same two objects:
checkpoint `Qwen/Qwen3.8-27B-FP8` (pinned revision), label `demo.rhoai.io/quantization: fp8`, display name and
description, and the container environment variable `VLLM_USE_DEEP_GEMM=0`. The model id `qwen3-8-27b`, GPU and serving
arguments stay the same, so clients and subscriptions do not change.

### `monitoring/`: serving health

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| PrometheusRule | `vllm-serving-health` | `internal-models` | Recording rules for p95 time to first token, p95 inter-token latency, KV cache use. Alerts `VLLMHighTimeToFirstToken` (p95 > 2 s for 10 min), `VLLMRequestQueueBacklog` (> 8 waiting for 10 min), `VLLMKVCachePressure` (> 90% for 10 min), `VLLMModelServingDown` (no metrics for 15 min, severity `info`) (wave 20) |
| RoleBinding | `rhoai-demo-monitoring-rules-view` | `internal-models` | ClusterRole `monitoring-rules-view` for Groups `rhoai-developers` and `rhods-admins` (wave 20) |

### Objects not in Git

| Object | Owner |
|---|---|
| Deployments `qwen3-8-27b-kserve` (vLLM, owner of the GPU) and `qwen3-8-27b-kserve-router-scheduler` (endpoint picker), Services, `InferencePool`, HTTPRoute `qwen3-8-27b-kserve-route` | OpenShift AI KServe controller, from the `LLMInferenceService` |
| Auth and rate-limit policies on the model route | MaaS and Connectivity Link controllers, from `MaaSModelRef`, subscriptions and auth policies |
| Labels `modelregistry.opendatahub.io/registered-model-id` and `model-version-id` on the `LLMInferenceService` | `stages/040-governed-models-as-a-service/register-model-cards.sh` (links the deployment to its Model Registry entry) |
| `spec.replicas` at runtime | Operators (`oc scale`/patch, `scripts/platform/resume-gpu-demo.sh`); Argo CD ignores it |

## How

**Ordering.** The Application has Argo CD wave 4 and deploy-order 5. Inside it: namespace (1), RoleBinding (3),
LocalQueues (8), templates (15), `LLMInferenceService` (16), `MaaSModelRef` (17). Every custom resource carries
`SkipDryRunOnMissingResource=true` so a first sync does not fail before the CRDs exist [5].

**Model artifact.** `spec.model.uri` is `hf://RedHatAI/Qwen3.8-27B-NVFP4:<40-character revision>`. The revision pin makes
the artifact immutable. No Red Hat OCI modelcar exists for this checkpoint, so the Hugging Face URI is the source. This is
a compatibility deployment, not a Red Hat validated model (see `BACKLOG.md`, "RHOAI 3.4 watch items").

**Runtime.** No image override: the OpenShift AI operator supplies the supported vLLM image. The manifest sets
`command` and the full `args` list. A custom `args` list replaces the platform default list [1, chapter 8], so the
manifest repeats the TLS arguments (`--ssl-certfile`, `--ssl-keyfile`, `--enable-ssl-refresh`). Non-default arguments
and their reasons:

| Argument | Reason |
|---|---|
| `--max-model-len=262144`, `--kv-cache-dtype=fp8`, `--gpu-memory-utilization=0.90` | Full context window for coding agents; FP8 KV cache fits about six full-window requests on the 96 GB GPU (serving study, `docs/OPERATIONS.md`, "Model serving study and default model (2026-10-13)") |
| `--speculative-config={"method":"mtp","num_speculative_tokens":3}`, `--max-num-batched-tokens=16384`, `--async-scheduling` | Measured study profile: 776 ms time to first token on 8K-token prompts with 8 agents, 302.6 output tokens/s |
| `--max-num-seqs=16` | A Stage 050 evaluation request with 16 samples decodes in one batch |
| `--enable-prefix-caching`, `--mamba-cache-mode=align` | Prefix caching for the hybrid model; this runtime rejects mode `all` |
| `--override-generation-config=...`, `--default-chat-template-kwargs={"enable_thinking":false}` | Qwen's recommended non-thinking sampling (temperature 0.7, top_p 0.8, top_k 20, presence_penalty 1.5) together with non-thinking mode [9]. Requests can override both |
| `--reasoning-parser=qwen3`, `--enable-auto-tool-choice`, `--tool-call-parser=qwen3_xml` | Tool calling for coding agents. The product docs add these flags through `VLLM_ADDITIONAL_ARGS` [1, chapter 9]; this manifest puts them in the `args` list it already owns |
| `--language-model-only`, `--enable-force-include-usage` | Text-only serving; usage in every response so MaaS token metering works |

Probes use HTTPS `/health` with a 600 s liveness delay and up to 10 minutes of readiness failures, for the model
download and load. Resources: 2-4 CPU, 16-24 GiB memory, one GPU, and a 2 GiB in-memory `/dev/shm`.

**Scheduling.** The hardware profile `gpu-rtxpro6000` (Stage 020) is a queue-type profile that names `lq-gpu-rtxpro6000`;
the Kueue resource flavor places the pod on the RTX PRO 6000 node. The `kueue.x-k8s.io/queue-name` label on the model and
`kueue.openshift.io/managed=true` on the namespace follow the documented Kueue enforcement [3]. The template adds GPU
tolerations (`nvidia.com/gpu`, `nvidia-gpu-only`).

**Router.** The endpoint picker uses an inline `EndpointPickerConfig` with `queue-scorer` (weight 2) and
`max-score-picker`, with `failureMode: FailOpen`. The documented default profile also scores prefix-cache hits and KV
cache utilization [1, chapter 10]; those scorers only help with more than one replica, and this model runs one.

**Gateway and authentication.** `router.gateway.refs` attaches the route to listener `qwen3-8` (the dedicated
compatibility hostname) and `api` (the shared `/v1` hostname with body-based model routing).
`security.opendatahub.io/enable-auth: "true"` keeps platform authentication on explicitly [1, chapter 5].

**Delegated fields.** `ignoreDifferences` with `RespectIgnoreDifferences=true` [6][5] hands two things to runtime owners:
- `/spec/replicas`: the model is parked at 0 to save GPU cost and resumed by an operator. Git says 1. Because the
  rollout uses `maxSurge`, a serving change with both GPUs busy needs the old workload pod deleted first (comment in the
  manifest).
- The three `modelregistry.opendatahub.io/*` id labels: `register-model-cards.sh` stamps them after it registers the
  checkpoint. Git only sets `modelregistry.opendatahub.io/name: demo-registry`.

**Switching to FP8.** Add `components: [components/qwen38-fp8]` to `kustomization.yaml`, publish, re-pin Stage 040 and
run `register-model-cards.sh` [7]. The component sets `VLLM_USE_DEEP_GEMM=0` because vLLM's DeepGEMM warm-up has no FP8
recipe for this GPU (sm120) and aborts startup. `register-model-cards.sh` also registers every prepared component's
checkpoint without deployment linkage, so the registry lists both builds.

**Secrets.** None. The Hugging Face checkpoints are public and are fetched by the KServe storage initializer.

**Cluster-specific values.** None in this component. Gateway hostnames are patched into `040-gateway-governance` by
`deploy.sh`.

## Validation

`validate.sh --readiness` checks that the live `LLMInferenceService` contains the rendered spec (except delegated
`replicas`), that it is Ready unless parked (replicas 0 with the delegation in place), that its workloads are owned and
complete, that its single route attaches to exactly the `qwen3-8` and `api` listeners with the canonical
`x-gateway-model-name` match on `/v1/chat/completions`, that the `MaaSModelRef` is Ready with its governance and runtime
conditions current, and that both templates match Git and are owned by this Application. Inference, streaming and quota
are checked only by `validate.sh --functional` with a persona kubeconfig.

By hand (read-only):

```bash
oc get llminferenceservice qwen3-8-27b -n internal-models \
  -o jsonpath='{.spec.replicas}{" "}{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
oc get maasmodelref qwen3-8-27b -n internal-models
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Serving API | llm-d deployments use `LLMInferenceService` [1] | `serving.kserve.io/v1alpha2` `LLMInferenceService` | Aligned |
| Support status | The topology selector and Gateway discovery are Technology Preview; core MaaS governance is generally available, while external models and vLLM deployment on MaaS are Technology Preview [1][4] | Demo platform, not production | Aligned |
| Runtime image | Platform-supplied vLLM runtime [1] | No image override | Aligned |
| vLLM arguments | Tool-calling flags through `VLLM_ADDITIONAL_ARGS`; a custom `args` list overrides the platform default [1, chapters 8-9] | Full `command` and `args` list in the manifest | Deviation (justified: every argument is a measured serving choice; the cost is that new platform default arguments in an upgrade are not picked up) |
| Request routing | Default profile with queue, KV-cache, prefix-cache and no-hit-LRU scorers; inline config allowed [1, chapter 10] | Inline `queue-scorer` + `max-score-picker` | Deviation (justified: single replica, prefix scoring has no effect) |
| Authentication | Enabled by default with Connectivity Link; annotation `security.opendatahub.io/enable-auth` [1, chapter 5] | Annotation set to `"true"` | Aligned |
| MaaS publication | Publish with a `MaaSModelRef` in the model's namespace [2] | `MaaSModelRef` `qwen3-8-27b` in `internal-models` | Aligned |
| Kueue | Managed namespace label, `kueue.x-k8s.io/queue-name` label, dashboard model servers use a hardware profile with a local queue [3] | All three present | Aligned |
| Topology templates | Administrators create `LLMInferenceServiceConfig` templates with `opendatahub.io/config-type`; router templates declare `opendatahub.io/supported-topologies` [1, chapter 2] | Two templates with these labels/annotation | Aligned |
| Model validation | Red Hat validated models are listed per release | `RedHatAI/Qwen3.8-27B-NVFP4` is not in that list; recorded in `BACKLOG.md` | Gap (compatibility only, not validated) |
| Model artifact | Immutable model source | Pinned Hugging Face revision; no OCI modelcar available | Aligned |
| GitOps delegation | `ignoreDifferences` JSON pointers with `RespectIgnoreDifferences` [6][5] | `replicas` and registry id labels only | Aligned |
| Optional variant | Kustomize Components are switched on with `components:` [8] | `components/qwen38-fp8`, off by default | Aligned |

## References

1. Deploy models using Distributed Inference with llm-d, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index
2. Govern LLM access with Models-as-a-Service, "Deploy and manage Models-as-a-Service", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service
3. Managing OpenShift AI, "Managing workloads with Kueue", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-workloads-with-kueue
4. Release notes, "Technology Preview features", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes
5. Argo CD, "Sync Options" (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
6. Argo CD, "Diffing Customization" (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/
7. Repository: `docs/OPERATIONS.md`, "Model serving study and default model (2026-10-13)".
8. Kustomize, "Kustomize Components" (upstream). https://kubectl.docs.kubernetes.io/guides/config_management/components/
9. Qwen3.8-27B model card, "Best Practices" (upstream). https://huggingface.co/Qwen/Qwen3.8-27B
