# Stage 030: Private Model Serving

**Theme:** Production GenAI and Private Data
**Concept:** Prove that a real LLM can be served on governed GPU capacity before
evaluating or exposing it as a shared enterprise service.

---

## Why This Matters

GPU capacity is useful only after the platform can turn it into a working model
endpoint. For a regulated European enterprise, this is the point where raw
accelerator infrastructure becomes a controlled GenAI capability: model
artifacts, runtime selection, endpoint exposure, authentication, and resource
strategy all need to be explicit before teams can trust the service.

Red Hat positions production inference as a core Red Hat AI 3 capability:
efficient serving with vLLM, distributed inference with llm-d when scale
requires it, governed MaaS access, and accelerator-aware operations. This stage
uses the smallest useful slice of that story. It enables the standard
KServe-based model serving platform, ensures Nemotron can be served with vLLM
on the GPU profiles created in Stage 020, and adds lightweight GuideLLM and
Grafana evidence before MaaS governance is introduced.

The stage does not yet turn the model into a governed shared service. That is
deliberate. First we prove the platform can host a GPU-backed LLM endpoint;
then this stage captures a simple GuideLLM/Grafana serving baseline, and Stage
220 publishes validated access through Models-as-a-Service.

---

## What Enables It

| Technology | Role in this stage | Source |
|------------|-------------------|--------|
| Red Hat OpenShift AI `DataScienceCluster` | Enables the KServe model serving component through the existing Stage 010 shared owner. | [RHOAI 3.4 - Installing and deploying OpenShift AI](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install) |
| KServe model serving platform | Provides the standard per-model runtime server pattern used for production-oriented LLM serving in this demo. | [RHOAI 3.4 - Configuring your model-serving platform](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/configuring_your_model-serving_platform/index) |
| vLLM NVIDIA GPU ServingRuntime | Runtime family used for GPU-backed generative model serving, including OpenAI-compatible inference endpoints. | [RHOAI 3.4 - Configuring your model-serving platform](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/configuring_your_model-serving_platform/index) |
| RHOAI Deploy a model workflow | User-facing dashboard workflow for deploying Nemotron from a model source, selecting a GPU hardware profile, choosing route/auth settings, and testing the endpoint. | [RHOAI 3.4 - Deploying models](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/deploying_models/index) |
| OCI modelcar artifact | Preferred reproducible model artifact pattern for the Nemotron vLLM endpoint and later MaaS deployment. | [RHOAI 3.4 - Deploying models](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/deploying_models/index) |
| Model Registry | Stores the governed model metadata record, model version, and OCI model artifact pointer used by the demo deployment path. | [RHOAI 3.4 - Managing model registries](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/managing_model_registries/index) |
| Stage 020 GPU profiles | Provide the governed `nvidia.com/gpu` capacity that the model deployment consumes. | [RHOAI 3.4 - Working with accelerators](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_accelerators/index) |
| OpenShift user workload monitoring | Scrapes model-serving metrics exposed through the RHOAI/KServe-generated `ServiceMonitor`. Configures `prometheus.retention: 15d` for the user workload Prometheus instance. | [OCP 4.20 - Monitoring](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/monitoring/index) |
| OpenShift Alertmanager receivers | Configures the platform Alertmanager with three receivers (Default, Watchdog, Critical) routing to a demo-local webhook Deployment (`rhoai-demo-alert-webhook` in `openshift-monitoring`). Inhibit rules suppress lower-severity duplicates. | [OCP 4.20 - Configuring alert notifications](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/postinstallation_configuration/configuring-alert-notifications) |
| Grafana Operator | Provides demo dashboards for vLLM latency, queue, throughput, KV cache, and GPU signals. This is a community-operator demo exception, not a Red Hat product dependency. | [Grafana Operator API reference](https://grafana.github.io/grafana-operator/docs/api/) |
| GuideLLM | Runs an on-demand shared-prefix workload benchmark against the internal vLLM `/v1` endpoint to observe queue saturation and establish a serving baseline. | [Red Hat Developer - GuideLLM: Evaluate LLM deployments](https://developers.redhat.com/articles/2025/06/20/guidellm-evaluate-llm-deployments-real-world-inference) |
| llm-d showroom Module 2 | Provides the benchmark pattern this stage partially replicates: `benchmark-data` PVC, `prompts.csv`, GuideLLM concurrent `32,64` profile, and `llm-performance` Grafana dashboard. | [llm-d showroom - Observe Single-GPU Behaviour](https://rhpds.github.io/llm-d-showroom/modules/workshop/llm-d/04-module-02.html) |
| Red Hat AI services llm-d reference | Provides the concrete shared-prefix prompt data and Grafana dashboard JSON adapted into this stage. | [rh-aiservices-bu/rhaoi3-llm-d](https://github.com/rh-aiservices-bu/rhaoi3-llm-d) |
| Red Hat AI MaaS code assistant quickstart | Provides a Red Hat-maintained implementation reference for Nemotron 3 Nano on AWS `g6e.2xlarge`/L40S infrastructure, including vLLM arguments, resource sizing, MaaS `LLMInferenceService`, tiered access, and Grafana usage patterns. | [rh-ai-quickstart/maas-code-assistant](https://github.com/rh-ai-quickstart/maas-code-assistant) |

This stage uses direct model serving, not Models-as-a-Service and not llm-d.
MaaS governance and external OpenAI `gpt-4o-mini` registration belong to
Stage 040. Distributed inference with llm-d remains a later scale-out option.

> **Lifecycle note:** the direct Nemotron `InferenceService` deployed here is a
> serving baseline, not a permanent resident. Stage 040's deploy retires it to
> free its GPU for the MaaS-published models — so between the Stage 040 cleanup
> and the MaaS models becoming Ready, the platform intentionally shows no
> deployed model for a few minutes. Validation evidence for this stage is
> captured before that handover.
EvalHub, MLflow, LMEval, judge-based evaluation, and risk assessment remain
deferred to later MLOps/evaluation stages.

The RH Brain search found Red Hat source material for Nemotron 3 Nano as a
validated model and strong GuideLLM/vLLM/llm-d baseline guidance. The
Red Hat-maintained MaaS code assistant quickstart adds a concrete
implementation reference that was tested with L40S GPUs on AWS `g6e.2xlarge`
instances. Stage 030 adapts the direct serving subset of that configuration:
one Nemotron endpoint, one GPU, `2` CPU and `16Gi` memory requested, `4` CPU and
`24Gi` memory limited, and the Nemotron-specific vLLM flags for usage
reporting, access-log reduction, prefix caching, context length, batched-token
scheduling, tool calling, trusted remote code, and reasoning parser support.
After the first saturation run, Stage 030 uses an `8192` token serving context
as the default chat/RAG operating envelope for one GPU. Larger context windows
must be justified by RAG-specific benchmark evidence before being exposed
through MaaS.
The quickstart's MaaS `LLMInferenceService`, gateway, tier, and RBAC patterns
remain Stage 040 input.

The quickstart deploys a sample modelcar URI for its scenario. This demo keeps
the Red Hat registry artifact
`oci://registry.redhat.io/rhai/modelcar-nvidia-nemotron-3-nano-30b-a3b-fp8:3.0`
as the preferred model source and uses live vLLM metrics plus GuideLLM results
to tune from evidence.

For GuideLLM token accounting, the benchmark script uses the public Hugging
Face processor ID `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8`, while the served
model ID remains `nemotron-3-nano-30b-a3b`. The benchmark data is a
GitOps-managed `benchmark-data` PVC populated with a `prompts.csv` file adapted
from the Red Hat AI services llm-d reference implementation.

### Capacity benchmark and business planning

`benchmark-guidellm.sh` targets the live Nemotron `LLMInferenceService`
workload Service directly (bypassing MaaS quotas so the model itself is
measured) and, after the run, produces `capacity-report.md` via
`scripts/analyze-guidellm.py`. Profiles (`RHOAI_GUIDELLM_PROFILE`):

- `users` (default) — stepped concurrent levels `1,2,4,8,16,32,64,128` to find
  the **maximum stable concurrency** and the **breaking point**.
- `sweep` — GuideLLM synchronous-to-throughput sweep to find the **optimal-load
  knee** and the throughput envelope.
- `custom` — raw `RHOAI_GUIDELLM_RATE_TYPE` / `RHOAI_GUIDELLM_RATE` passthrough.

The report converts raw latency and throughput into planning numbers against
configurable SLOs (default: TTFT p95 ≤ 2000 ms, ITL p95 ≤ 200 ms, error rate
≤ 1%): optimal load, max stable concurrency, breaking point, sustained token
capacity per hour/day, answers per hour, and the **concurrent RAG-chatbot
user** capacity. The chatbot figure discounts guardrail amplification — a
single governed answer costs three model calls (self-check input, generation,
self-check output), tunable with `--calls-per-turn`. Pass
`--gpu-cost-per-hour` to add cost per 1M tokens (the cost metric the RHOAI
managing-and-monitoring-models guide calls out). Un-park the environment
before running; results land in gitignored `runs/stage-030-guidellm/<id>/`.

---

## Architecture

```text
Stage 010 RHOAI shared owner
  DataScienceCluster default-dsc
        |
        | Stage 030 patch
        v
  kserve.managementState: Managed
        |
        v
KServe model serving platform
        |
        v
vLLM NVIDIA GPU ServingRuntime
        |
        v
Nemotron registry metadata and endpoint in demo-sandbox
        |
        v
GPU hardware profile from Stage 020
        |
        v
OpenAI-compatible inference endpoint
        |
        v
ServiceMonitor + user workload monitoring
        |
        v
GuideLLM benchmark script + Grafana baseline dashboard
        |
        v
OpenShift Console application menu link to the llm-performance dashboard
  (ConsoleLink patched at sync time from the live Grafana route via hook Job)
        |
        v
Policy benchmark data (prepare-policy-benchmark-data.sh seeds chat + RAG profiles)
```

- New in this stage: KServe model serving platform enablement and the
  dashboard-ready or script-created vLLM deployment path.
- Already available: OpenShift GitOps, ODF MCG object storage, RHOAI Dashboard,
  Model Registry, `demo-sandbox`, NFD, NVIDIA GPU Operator, Kueue queues, and
  GPU hardware profiles.
- Argo CD visibility: open `010-openshift-ai-platform-foundation` to confirm the
  KServe `DataScienceCluster` patch, and open
  `030-private-model-serving` to confirm user workload monitoring and
  Grafana resources. Stage 030 still does not own a second
  `DataScienceCluster`.
- Value of the integration: GPU capacity becomes usable by a model endpoint,
  while MaaS exposure stays separated into the next stage.

For repeatable redeployments, the deploy script uses an idempotent
discover-or-create flow:

1. Use `demo-registry` when it already exists; otherwise rely on the Stage 010
   GitOps desired state to create it.
2. Use the existing Nemotron model/version/artifact metadata when present;
   otherwise create metadata through the Model Registry REST API.
3. Use the existing Nemotron `InferenceService` when present; otherwise create
   the vLLM runtime and endpoint from the active RHOAI template and OCI
   modelcar source.
4. Reconcile the existing or newly created endpoint to the curated Nemotron
   vLLM argument and resource profile.

## Validation Evidence

Validated on `cluster-klvxt` on 2026-06-12:

- `030-private-model-serving/deploy.sh` converged Stage 010 and Stage
  210 Argo CD Applications to `Synced/Healthy`.
- `030-private-model-serving/validate.sh` passed 49 checks after
  reconciling the curated Nemotron vLLM args, resource sizing, structured
  tool-call validation, Grafana datasource access, and dashboard metric
  alignment.
- A direct `/v1/chat/completions` smoke test returned assistant content,
  reasoning metadata, and usage tokens through the vLLM endpoint after the
  curated configuration was applied.
- A forced tool-call smoke test returned a structured `get_weather` tool call
  with `city: Amsterdam`, confirming the Nemotron tool-calling parser path.
- A short GuideLLM smoke run with one concurrent request and a 10-second window
  completed with 11 successful requests and zero errors. The observed p95 TTFT
  was about 71 ms, p95 ITL about 7.1 ms, p95 end-to-end request latency about
  0.98 seconds, and mean output throughput about 132 output tokens/second.
- After reducing the default serving context to `8192` tokens, a policy
  benchmark tested short chat and 4k-context RAG profiles. Short chat remains a
  good fit for an initial `8` concurrent-user service lane on one GPU. RAG-style
  requests should start with a stricter `2` concurrent-user lane because the
  `4` concurrent run showed a p95 latency spike.

These numbers are smoke-test evidence for the harness and endpoint, not a
production capacity claim. Use the recorded chat/RAG policy profiles in
`docs/OPERATIONS.md` as the first input for Stage 040 MaaS quotas and rerun
them whenever the model, runtime, GPU shape, or prompt profile changes.

---

## Demo

![Stage 030 walkthrough](../../docs/assets/demos/stage-030/stage-030-demo.gif)

| Screenshot | What it shows |
|------------|---------------|
| ![Grafana folder](../../docs/assets/demos/stage-030/01-grafana-dashboards.png) | RHOAI Demo Grafana folder with LLM Performance and vLLM Baseline dashboards |
| ![LLM Performance](../../docs/assets/demos/stage-030/02-llm-performance-dashboard.png) | Live LLM Inference Performance: TTFT (P50 ~67ms), ITL (P50 ~5ms), KV Cache metrics |
| ![Nemotron pods](../../docs/assets/demos/stage-030/03-nemotron-pods-running.png) | Nemotron 3 Nano 30B pods running in models-as-a-service (7.5 GiB VRAM) |
| ![Deployments](../../docs/assets/demos/stage-030/04-model-deployments.png) | RHOAI AI Hub Deployments tab showing active KServe model serving |

---

## References

| Source | Role |
|--------|------|
| [Red Hat AI 3.4 blog](https://www.redhat.com/en/blog/inference-agentic-ai-scaling-enterprise-foundation-red-hat-ai-34) | Production inference, MaaS, llm-d, evaluation, and agentic platform narrative |
| [Red Hat Developer - Why vLLM is the best choice for AI inference today](https://developers.redhat.com/articles/2025/10/30/why-vllm-best-choice-ai-inference-today) | vLLM value and OpenShift AI integration narrative |
| [Red Hat Developer - GuideLLM: Evaluate LLM deployments for real-world inference](https://developers.redhat.com/articles/2025/06/20/guidellm-evaluate-llm-deployments-real-world-inference) | GuideLLM methodology, workload-shaped benchmarking, latency, throughput, TTFT, ITL, and SLO framing |
| [Red Hat Developer - How to deploy and benchmark vLLM with GuideLLM on Kubernetes](https://developers.redhat.com/articles/2025/12/24/how-deploy-and-benchmark-vllm-guidellm-kubernetes) | Kubernetes Job pattern for in-cluster GuideLLM benchmarking against a vLLM endpoint |
| [Red Hat Developer - Autoscaling vLLM with OpenShift AI model serving](https://developers.redhat.com/articles/2025/11/26/autoscaling-vllm-openshift-ai-model-serving) | vLLM model-serving performance validation and Grafana/Prometheus signal selection |
| [Red Hat Developer - 5 steps to triage vLLM performance](https://developers.redhat.com/articles/2026/03/09/5-steps-triage-vllm-performance) | vLLM triage signals: TTFT, ITL, queue depth, KV cache, prefix cache, and sequence lengths |
| [Red Hat - Redefining LLM observability with llm-d](https://www.redhat.com/en/blog/tokens-caches-how-llm-d-improves-llm-observability-red-hat-openshift-ai-3.0) | Grafana and Prometheus observability narrative for vLLM/llm-d metrics |
| [llm-d showroom Module 2](https://rhpds.github.io/llm-d-showroom/modules/workshop/llm-d/04-module-02.html) | Benchmark workflow partially replicated in Stage 030: vLLM metrics, Grafana, `benchmark-data`, and GuideLLM concurrent load |
| [rh-aiservices-bu/rhaoi3-llm-d](https://github.com/rh-aiservices-bu/rhaoi3-llm-d) | Concrete `llm-performance` Grafana dashboard JSON and shared-prefix GuideLLM prompt dataset adapted into Stage 030 |
| [Red Hat - Predictable AI validated model batches](https://www.redhat.com/en/blog/predictable-ai-announcing-january-and-february-validated-model-batches) | Nemotron 3 Nano validated model context |
| [Red Hat - Using containers to bring software engineering rigor to AI workloads](https://www.redhat.com/en/blog/using-containers-bring-software-engineering-rigor-ai-workloads) | ModelCar/OCI artifact governance narrative |
| [Red Hat AI quickstart - MaaS code assistant](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant) | Nemotron 3 Nano on AWS `g6e.2xlarge`/L40S implementation reference and MaaS architecture narrative |
| [rh-ai-quickstart/maas-code-assistant](https://github.com/rh-ai-quickstart/maas-code-assistant) | Source repository for Nemotron vLLM args, resource sizing, `LLMInferenceService`, MaaS tier, RBAC, and Grafana examples |
| [RHOAI 3.4 - Configuring your model-serving platform](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/configuring_your_model-serving_platform/index) | Product authority for KServe, ServingRuntime, and platform enablement |
| [RHOAI 3.4 - Deploying models](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/deploying_models/index) | Product authority for model deployment workflows and inference requests |
| [RHOAI 3.4 - Managing model registries](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/managing_model_registries/index) | Product authority for registry provisioning and access |
| [Kubeflow Model Registry REST API v1alpha3](https://www.kubeflow.org/docs/components/hub/reference/rest-api/) | API shape for idempotent metadata checks and creation |
| [redhat-cop/gitops-catalog - openshift-ai](https://github.com/redhat-cop/gitops-catalog/tree/main/openshift-ai) | Curated GitOps layout pattern for operator, instance, component, and overlay separation |
| [redhat-ai-services/modelcar-catalog](https://github.com/redhat-ai-services/modelcar-catalog) | Example ModelCar implementation catalog; not product API authority |
| `docs/PLATFORM_BASELINE.md` | Active product version targets |
