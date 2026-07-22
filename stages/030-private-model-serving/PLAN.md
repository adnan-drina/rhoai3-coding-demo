# Stage 030: Model Serving Baseline with vLLM Plan

## Intent

- Stage identifier: `210`
- Stage family: `2xx Production GenAI and Private Data`
- Stage slug: `030-private-model-serving`
- Concept introduced: Standard model serving baseline for a GPU-backed LLM.
- Target audience: Platform engineer, solution architect, data scientist.
- Enterprise value: Converts governed GPU capacity into a usable, measurable model endpoint path before shared-service governance is introduced.
- Depends on: `010-openshift-ai-platform-foundation` and `020-gpu-infrastructure-private-ai`.
- New components: KServe model serving platform through the RHOAI `DataScienceCluster`, vLLM NVIDIA GPU runtime availability, idempotent `demo-registry` and Nemotron metadata readiness, a deployment path for `nemotron-3-nano-30b-a3b`, user workload monitoring, a GitOps-managed Grafana dashboard, and an on-demand GuideLLM benchmark runner.
- Existing components reused: Stage 010 OpenShift GitOps, RHOAI Dashboard, `demo-sandbox`, ODF MCG, Model Registry, and Stage 020 GPU hardware profiles.
- Non-goals:
  - MaaS governance, subscriptions, quotas, external OpenAI model registration, or API-key issuance; deferred to `040-governed-models-as-a-service`.
  - EvalHub, MLflow, LMEval, LLM-as-judge, risk assessment, or formal model quality evaluation; deferred to later MLOps/evaluation stages.
  - llm-d distributed inference; later scale-out option only.
  - Curated MaaS service configuration; deferred until baseline decisions are captured.
  - NVIDIA NIM enablement.

## Acceptance Criteria

- [x] README explains Why and What without runbook detail.
- [x] Why and business value are grounded in Red Hat narrative sources from `rh-brain/`.
- [x] KServe/model serving enablement is grounded in active-baseline RHOAI official docs and verified live schema.
- [x] Red Hat-linked GitHub reference implementations are captured as patterns, not API authority.
- [x] GitOps ownership model is explicit: Stage 010 remains the sole `DataScienceCluster` owner.
- [x] Stage 030 carries a focused GitOps hook that patches the shared DSC KServe component.
- [x] Deploy script applies the shared owner Application and triggers Argo CD reconciliation.
- [x] Validate script proves the model serving platform is enabled, vLLM is available, `demo-registry` is available, Nemotron metadata exists, and the Nemotron `InferenceService` is ready with the curated vLLM argument and resource profile.
- [x] Fresh-environment deploy path discovers existing manual/dashboard state and creates missing registry metadata and endpoint resources when absent.
- [x] Lightweight GuideLLM benchmark script is added for baseline throughput and latency evidence.
- [x] Grafana dashboard resources are added for vLLM/KServe/GPU metrics.
- [x] Manifest and Red Hat source-alignment reviews pass for the KServe enablement slice.

## Source Capture

| Purpose | Source | Skill | Notes |
|---------|--------|-------|-------|
| Concept/value | `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/wiki/sources/2026-05-12 - From Inference to Agents Scaling AI in the Enterprise with Red Hat AI 3.4.md` | `project-documentation-authoring` | Positions production inference, MaaS, llm-d, and evaluation as the Red Hat AI 3.4 platform progression. |
| Concept/value | `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/wiki/sources/2025-10-30 - Why vLLM Is the Best Choice for AI Inference Today.md` | `project-documentation-authoring` | Supports vLLM as the private LLM inference runtime narrative. |
| Concept/value and artifact governance | `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/raw/Using containers to bring software engineering rigor to AI workloads.md` | `project-documentation-authoring` | Supports ModelCar/OCI model artifact governance. |
| Concept/value and validated model context | `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/wiki/analyses/2026-05-29 - Red Hat AI Validated Models Timeline.md` | `project-documentation-authoring` | Identifies `NVIDIA-Nemotron-3-Nano-30B-A3B-FP8` as a Red Hat AI validated model from the January 2026 batch. |
| Research finding | `rg -i "nemotron-3-nano|nemotron 3 nano|nvidia-nemotron-3-nano|g6e\\.2xlarge|g6e" /Users/adrina/Sandbox/rh-brain/Red\ Hat\ Brain` | `project-red-hat-doc-alignment-review` | RH Brain did not contain an exact matching article for Nemotron 3 Nano on AWS `g6e.2xlarge`; use the Red Hat-maintained quickstart below as implementation evidence and live GuideLLM/Grafana results for tuning. |
| Implementation reference | [Red Hat AI quickstart - MaaS code assistant](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant) | `project-red-hat-doc-alignment-review`, `rhoai-model-serving-platform`, `rhoai-maas-governance` | Documents the private code assistant architecture, Nemotron 3 Nano, MaaS, vLLM/llm-d, Grafana, 48GB VRAM requirement, and testing on two AWS `g6e.2xlarge` L40S instances. |
| Implementation reference | [rh-ai-quickstart/maas-code-assistant](https://github.com/rh-ai-quickstart/maas-code-assistant) | `project-red-hat-doc-alignment-review`, `rhoai-model-serving-platform`, `rhoai-maas-governance` | Source for the Nemotron vLLM flags, resource requests/limits, `LLMInferenceService` template, MaaS tier annotations, tiered RBAC, and Grafana patterns. Stage 030 adapts the direct serving subset; Stage 040 should reuse the MaaS pattern after RHOAI 3.4 schema checks. |
| Implementation reference | `/Users/adrina/Sandbox/rhoai3-coding-demo/gitops/stages/030-private-model-serving/base/models/nemotron-3-nano-30b.yaml` | `rhoai-model-serving-platform`, `rhoai-maas-governance` | Working sibling-demo configuration for the Red Hat registry modelcar, tool-calling args, reasoning parser args, prefix caching, `--max-num-batched-tokens=8192`, resources, probes, scheduler shape, and `/dev/shm` volume. |
| Benchmark methodology | `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/raw/GuideLLM Evaluate LLM deployments for real-world inference.md` | `rhoai-model-management-monitoring` | GuideLLM purpose, workload shaping, TTFT, ITL, throughput, and SLO framing. |
| Benchmark implementation pattern | `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/raw/How to deploy and benchmark vLLM with GuideLLM on Kubernetes.md` | `rhoai-model-management-monitoring` | Kubernetes Job pattern for in-cluster GuideLLM benchmarking against a vLLM endpoint. |
| Observability methodology | `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/wiki/configurations/vLLM Performance Triage Baseline.md` | `rhoai-model-management-monitoring` | vLLM baseline workflow: TTFT, ITL, request queue, KV cache, prefix cache, sequence length, and topology checks. |
| Observability implementation pattern | `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/raw/Autoscaling vLLM with OpenShift AI model serving Performance validation.md` | `rhoai-model-management-monitoring` | OpenShift AI vLLM performance validation with Prometheus/Grafana signals. |
| Observability triage | `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/raw/5 steps to triage vLLM performance.md` | `rhoai-model-management-monitoring` | PromQL-style triage flow and vLLM signal selection. |
| Benchmark workshop pattern | [llm-d showroom Module 2](https://rhpds.github.io/llm-d-showroom/modules/workshop/llm-d/04-module-02.html) | `rhoai-model-management-monitoring`, `project-demo-stage-authoring` | Source for the Stage 030 single-GPU vLLM baseline pattern: vLLM metrics, `benchmark-data` PVC, `prompts.csv`, GuideLLM concurrent `32,64`, and `llm-performance` dashboard URL. |
| Benchmark implementation reference | [rh-aiservices-bu/rhaoi3-llm-d](https://github.com/rh-aiservices-bu/rhaoi3-llm-d) | `rhoai-model-management-monitoring`, `ocp-grafana-operator` | Concrete shared-prefix prompt dataset and `grafana-dashboard-llm-performance.json` adapted locally for Stage 030. Product fields still come from official RHOAI/OCP docs and active CRDs. |
| Grafana pattern | [redhat-cop/gitops-catalog/grafana-operator](https://github.com/redhat-cop/gitops-catalog/tree/main/grafana-operator) | `ocp-grafana-operator`, `project-red-hat-operator-gitops` | Local-curated Operator/instance/datasource/dashboard layout pattern; community operator exception. |
| Grafana CR API | [Grafana Operator API reference](https://grafana.github.io/grafana-operator/docs/api/) | `ocp-grafana-operator` | `Grafana`, `GrafanaDatasource`, and `GrafanaDashboard` v1beta1 schema references. |
| OCP monitoring | [OCP 4.20 - Monitoring](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/monitoring/index) | `ocp-observability` | User workload monitoring enablement and Prometheus/Thanos access context. |
| Product config | [RHOAI 3.4 - Configuring your model-serving platform](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/configuring_your_model-serving_platform/index) | `rhoai-model-serving-platform` | KServe platform, ServingRuntime, vLLM runtime, deployment strategy. |
| Product workflow | [RHOAI 3.4 - Deploying models](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/deploying_models/index) | `rhoai-model-deployment` | Deploy a model wizard, OCI/modelcar storage, endpoint and token checks. |
| Product config | [RHOAI 3.4 - Managing model registries](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/managing_model_registries/index) | `rhoai-model-registry` | `modelregistry` component, `demo-registry`, generated registry RBAC, default database demo posture. |
| Product workflow | [RHOAI 3.4 - Working with model registries](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_model_registries/index) | `rhoai-model-registry-workflows` | Registering models, model versions, model artifacts, and deployment handoff. |
| API shape | [Kubeflow Model Registry REST API v1alpha3](https://www.kubeflow.org/docs/components/hub/reference/rest-api/) | `rhoai-model-registry-workflows`, `rhoai-api-tiers` | Registry REST endpoints used for idempotent metadata checks and creation. |
| Product config | [RHOAI 3.4 - Working with accelerators](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_accelerators/index) | `rhoai-hardware-profiles`, `rhoai-nvidia-gpu-accelerators` | GPU hardware profile selection and `nvidia.com/gpu` capacity. |
| Schema verification | `oc explain datasciencecluster.spec.components.kserve --api-version=datasciencecluster.opendatahub.io/v2` | `rhoai-dsci-dsc-configuration` | Verified `managementState: Managed|Removed`; active docs say only RawDeployment mode is supported. |
| Pattern | [redhat-cop/gitops-catalog/openshift-ai](https://github.com/redhat-cop/gitops-catalog/tree/main/openshift-ai) | `project-red-hat-operator-gitops` | Operator/instance/components/overlay structure only. |
| Reference implementation | [redhat-ai-services/modelcar-catalog](https://github.com/redhat-ai-services/modelcar-catalog) | `rhoai-model-deployment` | ModelCar examples only; product fields still come from RHOAI docs/schema. |

### `rh-brain` Article Selection

- Candidate articles reviewed: Red Hat AI 3.4 inference-to-agents blog, vLLM inference article, ModelCar/OCI governance article, OpenShift AI vLLM and llm-d inference baseline, GuideLLM articles, vLLM performance triage, and validated model timeline.
- Selected articles: Red Hat AI 3.4 inference-to-agents blog, vLLM article, ModelCar/OCI governance article, GuideLLM benchmark articles, vLLM performance triage, and validated model timeline.
- Reason selected: together they explain why production inference matters, why vLLM is the runtime path, why OCI model artifacts fit enterprise governance, why Nemotron 3 Nano is a reasonable demo model, and how to establish a measured model-serving baseline.
- Links to GitHub/code examples: yes.
- Linked implementation source: `redhat-ai-services/modelcar-catalog` for ModelCar examples; Red Hat CoP `gitops-catalog/openshift-ai` for GitOps layout pattern.

## Skill Routing

- Coordinator: `project-demo-stage-authoring`
- Documentation: `project-documentation-authoring`
- GitOps: `project-gitops-authoring`, `project-red-hat-operator-gitops`
- Product skills: `rhoai-dsci-dsc-configuration`, `rhoai-model-serving-platform`, `rhoai-model-deployment`, `rhoai-model-registry`, `rhoai-model-registry-workflows`, `rhoai-model-management-monitoring`, `rhoai-hardware-profiles`, `rhoai-nvidia-gpu-accelerators`
- Review skills: `project-manifest-review`, `project-red-hat-doc-alignment-review`, `rhoai-api-tiers`
- Environment skills: `openshift-project-safety`, `env-deploy-and-evaluate`, `env-troubleshoot`

## GitOps Ownership

- Ownership model: split shared-owner plus independent observability owner.
- Shared RHOAI owner Application: `010-openshift-ai-platform-foundation`.
- Shared RHOAI source path: `gitops/stages/010-openshift-ai-platform-foundation/base`.
- Stage 030 observability Application: `030-private-model-serving`.
- Stage 030 observability source path: `gitops/stages/030-private-model-serving/base`.
- Shared resources touched: the single `DataScienceCluster` named `default-dsc`; Stage 030 observability does not own or render a second DSC.
- Argo CD sync or ordering requirements:
  - Stage 010 must be installed and healthy first.
  - Stage 020 should be healthy before deploying a GPU model.
  - Stage 030 patches only the KServe component on the shared `DataScienceCluster` through a GitOps hook; no separate Argo CD Application owns the DSC.
  - Stage 030 also applies its own Argo CD Application for user workload monitoring, Grafana, datasource, and dashboards.
  - Argo CD console visibility is split: KServe/DSC in `010-openshift-ai-platform-foundation`; observability in `030-private-model-serving`.
- Secret and credential handling:
  - No model endpoint tokens, registry pull credentials, or provider API keys are committed.
  - The deploy script may copy the cluster pull-secret into `demo-sandbox` as a runtime Kubernetes Secret when the Nemotron modelcar pull secret is absent.
  - Endpoint auth is disabled for the Stage 030 controlled baseline endpoint; MaaS provides governed shared access in Stage 040.

## Manifest Inventory

| File | Kind | Source authority | Validation |
|------|------|------------------|------------|
| `gitops/stages/030-private-model-serving/base/rhoai-dsc/base/patch-dsc-kserve.yaml` | GitOps hook that patches `DataScienceCluster` KServe state | RHOAI 3.4 docs plus live `oc explain` for v2 schema | `kustomize build gitops/stages/030-private-model-serving/base`; `oc get datasciencecluster default-dsc` after sync |
| `gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/registry/base/modelregistry-demo.yaml` | `ModelRegistry` | RHOAI 3.4 managing model registries plus live `oc explain modelregistries.modelregistry.opendatahub.io` | `kustomize build gitops/stages/010-openshift-ai-platform-foundation/base`; `oc get modelregistries.modelregistry.opendatahub.io demo-registry -n rhoai-model-registries` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/registry/base/rolebinding-demo-registry-*.yaml` | `RoleBinding` | RHOAI generated registry RBAC model | `oc get role registry-user-demo-registry -n rhoai-model-registries`; user dashboard access |
| `gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/aggregate/overlays/demo/kustomization.yaml` | Kustomize overlay | Project shared-owner pattern | `kustomize build gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/aggregate/overlays/demo` |
| `gitops/argocd/app-of-apps/030-private-model-serving.yaml` | `Application` | Project Argo CD standards | `oc get applications.argoproj.io 030-private-model-serving -n openshift-gitops` |
| `gitops/stages/030-private-model-serving/base/monitoring/base/cluster-monitoring-config.yaml` | `ConfigMap` | OCP monitoring docs | `oc get configmap cluster-monitoring-config -n openshift-monitoring` |
| `gitops/stages/030-private-model-serving/base/benchmark-data/base/benchmark-data-pvc.yaml` | `PersistentVolumeClaim` | llm-d showroom pattern plus OCP storage docs | `oc get pvc benchmark-data -n demo-sandbox` |
| `gitops/stages/030-private-model-serving/base/benchmark-data/base/benchmark-prompts-configmap.yaml` | `ConfigMap` | `rh-aiservices-bu/rhaoi3-llm-d` prompt dataset | `oc get configmap stage210-guidellm-prompts -n demo-sandbox` |
| `gitops/stages/030-private-model-serving/base/benchmark-data/base/seed-benchmark-data-job.yaml` | `Job` hook | llm-d showroom pre-provisioned PVC pattern | Argo CD hook succeeds; `benchmark-guidellm.sh` can mount `/data/prompts.csv` |
| `gitops/stages/030-private-model-serving/base/grafana/operator/**` | `Namespace`, `OperatorGroup`, `Subscription` | Grafana Operator package metadata plus CoP pattern | `oc get subscription,csv -n rhoai-demo-grafana` |
| `gitops/stages/030-private-model-serving/base/grafana/instance/base/grafana.yaml` | `Grafana` | Grafana Operator API plus OpenShift OAuth proxy pattern | `oc get grafana grafana -n rhoai-demo-grafana` |
| `gitops/stages/030-private-model-serving/base/grafana/instance/base/grafana-viewer-rbac.yaml` | `Role`, `RoleBinding` | OCP RBAC docs plus OpenShift OAuth proxy SAR pattern | `oc auth can-i get services -n rhoai-demo-grafana --as ai-admin --as-group rhods-admins` |
| `gitops/stages/030-private-model-serving/base/grafana/instance/components/openshift-monitoring-datasource/grafana-datasource.yaml` | `GrafanaDatasource` | Grafana Operator API plus OpenShift monitoring datasource pattern | `oc get grafanadatasource prometheus -n rhoai-demo-grafana` |
| `gitops/stages/030-private-model-serving/base/grafana/instance/components/model-serving-dashboards/dashboard-vllm-kserve-gpu.yaml` | `GrafanaDashboard` | Grafana Operator API plus vLLM metric source findings | `oc get grafanadashboard vllm-model-serving-baseline -n rhoai-demo-grafana` |
| `gitops/stages/030-private-model-serving/base/grafana/instance/components/model-serving-dashboards/dashboard-llm-performance.yaml` | `GrafanaDashboard` | `rh-aiservices-bu/rhaoi3-llm-d` dashboard JSON adapted to local datasource UID | `oc get grafanadashboard llm-performance -n rhoai-demo-grafana` |
| `gitops/stages/030-private-model-serving/base/grafana/instance/components/console-link/**` | `ConsoleLink`, RBAC, `Job` hook | OCP ConsoleLink docs plus sibling-demo patch pattern | `oc get consolelink rhoai-demo-grafana -o jsonpath='{.spec.href}'` |

## Script Plan

### `deploy.sh`

- Guard behavior: loads `.env`, verifies `RHOAI_EXPECTED_API_SERVER` against `oc whoami --show-server`, exits on mismatch.
- First action: applies the Stage 010 Argo CD Application with local `GIT_REPO_URL` and `GIT_REPO_BRANCH`.
- Wait/report behavior: requests an Argo CD refresh and waits for Stage 010 to report `Synced` and `Healthy`, then reports the KServe component state.
- Registry behavior:
  - waits for `demo-registry` to become `Available`
  - uses existing Nemotron registered model, model version, and artifact metadata when present
  - creates missing Nemotron metadata through the Model Registry REST API
- Endpoint behavior:
  - uses an existing Nemotron `InferenceService` when present
  - reconciles the Nemotron `InferenceService` to the curated quickstart/coding-demo-backed vLLM argument and resource profile
  - creates the vLLM `ServingRuntime` from the active RHOAI template when absent
  - creates the Nemotron `InferenceService` when absent
  - waits for the endpoint to become `Ready`
- Observability behavior:
  - applies the Stage 030 observability Argo CD Application
  - waits for it to report `Synced` and `Healthy`
  - enables user workload monitoring and installs Grafana resources through GitOps

### `benchmark-guidellm.sh` and `scripts/analyze-guidellm.py`

- Guard behavior: loads `.env`, verifies `RHOAI_EXPECTED_API_SERVER`, and exits on mismatch.
- Capacity benchmark behavior (retargeted 2026-07-05 from the retired `demo-sandbox` InferenceService to the live model):
  - targets the Nemotron `LLMInferenceService` workload Service directly (`<model>-kserve-workload-svc.models-as-a-service.svc:8000`, HTTPS self-signed → GuideLLM `--backend-args '{"verify": false}'`), bypassing MaaS quotas so the model itself is measured; override `RHOAI_GUIDELLM_TARGET` for the governed gateway path
  - runs `ghcr.io/vllm-project/guidellm:v0.5.0` as a Kubernetes Job in `models-as-a-service`, using the FP8 processor for token accounting
  - profiles (`RHOAI_GUIDELLM_PROFILE`): `users` (stepped concurrency — max stable concurrency + breaking point), `sweep` (throughput envelope + optimal knee), `custom` (raw rate-type/rate)
  - default data is GuideLLM synthetic (`prompt_tokens=1200,output_tokens=256`, RAG-turn-shaped); a `/data/*` value mounts the `benchmark-data` PVC instead
  - writes JSON and CSV to `runs/stage-030-guidellm/<timestamp>/`, then runs `scripts/analyze-guidellm.py` to produce `capacity-report.md`: optimal load, max stable concurrency, breaking point, sustained token capacity, answers/hour, concurrent RAG-chatbot users (discounting the 3 model calls a guarded turn costs), and cost per 1M tokens (`--gpu-cost-per-hour`), all against configurable latency SLOs
  - deletes temporary Job, copy Job, and PVC unless `RHOAI_GUIDELLM_KEEP_RESOURCES=true`

### `validate.sh`

- Readiness checks:
  - Stage 010 Argo CD Application is `Synced` and `Healthy`.
  - `DataScienceCluster` is `Ready`.
  - `spec.components.kserve.managementState` is `Managed`.
  - KServe `InferenceService` and `ServingRuntime` CRDs are present.
  - A vLLM `ServingRuntime` is discoverable.
  - Stage 020 GPU hardware profile and GPU capacity are still visible.
  - `demo-registry` is available and has a route host.
  - Nemotron registered model, version, and OCI artifact metadata exist.
  - Nemotron `InferenceService` is `Ready`, has a runtime, and uses the expected OCI modelcar source.
  - Nemotron `InferenceService` uses the curated quickstart/coding-demo-backed vLLM arguments and resource sizing.
  - Stage 030 observability Application is `Synced` and `Healthy`.
  - User workload monitoring is enabled.
  - Grafana Operator, Grafana instance, Prometheus datasource, dashboards, and route are present.
  - OpenShift ConsoleLink points to the `llm-performance` Grafana dashboard.
  - GuideLLM `benchmark-data` PVC is bound and prompt ConfigMap is present.
  - The Nemotron ServiceMonitor exists and the endpoint exposes vLLM metrics.
- Expected success output: all readiness checks print success and exit 0.

## Operations And Troubleshooting

- `docs/OPERATIONS.md` update needed: yes - Stage 030 deployment sequence, validation, and user-led Nemotron dashboard path.
- `docs/TROUBLESHOOTING.md` update needed: yes - model serving component stuck, missing runtime, KServe CRDs missing, GPU profile unavailable.
- `docs/BACKLOG.md` update needed: yes - Stage 030 status and deferred GuideLLM/Grafana baseline work.

## Risks And Deferred Work

| Item | Type | Resolution |
|------|------|------------|
| Runtime template name and enabled state | risk | Verify after KServe is managed; do not hard-code a runtime name before validation. |
| Quickstart version boundary | risk | The MaaS code assistant quickstart is a Red Hat-maintained implementation reference, but it cites an RHOAI 3.3 advanced path. Keep RHOAI 3.4 official docs and live CRD schema as product authority. |
| Quickstart modelcar URI | source boundary | The quickstart uses a sample modelcar URI for its scenario. This demo keeps the Red Hat registry modelcar URI unless a newer official Red Hat artifact is selected and documented. |
| GuideLLM benchmark image | risk | `ghcr.io/vllm-project/guidellm:v0.5.0` is an upstream image used by the Red Hat article pattern, not a Red Hat product image. Keep it on-demand and documented as a benchmark tool. |
| Grafana Operator support posture | risk | Grafana Operator is from `community-operators`; use only as a demo observability UI and document the support boundary. |
| OCI modelcar pull permissions | risk | The Red Hat registry modelcar may require entitlement/pull credentials; keep credentials out of Git. |
| Scarce GPU capacity | risk | Use Recreate strategy and one replica; Stage 020 scale-to-zero remains available. |
| MaaS and external OpenAI | deferred | Stage 040 owns MaaS, including external `gpt-4o-mini`. |

## Review Log

- Local render: passed 2026-06-12. `kustomize build gitops/stages/010-openshift-ai-platform-foundation/base` rendered `kserve.managementState: Managed`.
- Script syntax: passed 2026-06-12. `bash -n 030-private-model-serving/deploy.sh 030-private-model-serving/validate.sh`.
- Red Hat source-alignment review: passed for KServe enablement scope; product fields are from RHOAI 3.4 docs plus live `oc explain datasciencecluster.spec.components.kserve`.
- Live deploy: succeeded on cluster-klvxt 2026-06-12; Argo CD Application `010-openshift-ai-platform-foundation` synced revision `df241586684739f8d1610e8a43bd875d686db896`.
- Live validation: PASSED 2026-06-12 - `030-private-model-serving/validate.sh` 49/49 after adding the llm-d-showroom-style `benchmark-data` PVC, shared-prefix prompt ConfigMap, `llm-performance` Grafana dashboard, OpenShift ConsoleLink, and dashboard metric-alignment checks.
- Direct inference smoke: PASSED 2026-06-12 - `POST /v1/chat/completions` returned assistant content, reasoning metadata, and usage tokens from `nvidia-nemotron-3-nano-30b-a3b` after the curated configuration was applied.
- Tool-calling smoke: PASSED 2026-06-12 - forced `tool_choice` returned a structured `get_weather` tool call with `{"city":"Amsterdam"}`, confirming `--enable-auto-tool-choice`, `--tool-call-parser=qwen3_coder`, and the Nemotron reasoning parser path are active.
- GuideLLM smoke: PASSED 2026-06-12 - ran `./030-private-model-serving/benchmark-guidellm.sh` with `RHOAI_GUIDELLM_RATE=1`, `RHOAI_GUIDELLM_MAX_SECONDS=10`, and `RHOAI_GUIDELLM_OUTPUTS=benchmark-results.json`; the job targeted the internal `/v1` endpoint and read `/data/prompts.csv` from `benchmark-data`. Results stored under gitignored `runs/stage-030-guidellm/20260612131009/`.
- GuideLLM smoke values: completed 5 requests with no errors; observed p95 TTFT about 1.63 seconds, p95 ITL about 6.1 ms, p95 end-to-end latency about 3.0 seconds, and mean output throughput about 126.7 output tokens/second. Treat this as harness proof only, not capacity evidence.
- Serving-context optimization: APPLIED 2026-06-12 - changed the curated Nemotron default from `--max-model-len=131072` to `--max-model-len=8192` for the single-GPU chat/RAG operating envelope. The live `InferenceService` was reconciled through `030-private-model-serving/deploy.sh`, and a guarded read-only check confirmed the active vLLM args include `--max-model-len=8192`, `--max-num-batched-tokens=8192`, prefix caching, auto tool choice, the `qwen3_coder` tool parser, and the Nemotron reasoning parser.
- Policy benchmark data: ADDED 2026-06-12 - `030-private-model-serving/prepare-policy-benchmark-data.sh` seeds `/data/policy-chat.csv` and `/data/policy-rag-4k.csv` into the existing `benchmark-data` PVC for repeatable MaaS-policy-oriented GuideLLM runs.
- GuideLLM policy benchmark: PASSED 2026-06-12 - ran chat concurrency `1,2,4,8,12,16` for 120 seconds per level and 4k-context RAG concurrency `1,2,4,8` for 120 seconds per level. Results are stored under gitignored directories `runs/stage-030-guidellm/20260612152549/` and `runs/stage-030-guidellm/20260612153735/`.
- GuideLLM policy values: short chat stayed usable through `8` concurrent users with p95 TTFT about 4.6 seconds, p95 ITL about 12.6 ms, and p95 end-to-end latency about 6.0 seconds. Chat `12-16` concurrent users is a stress lane, not the first public quota. RAG with about 3.6k input tokens and 512 output tokens should start at `2` concurrent users; `4` concurrent users showed a p95 TTFT spike around 19.3 seconds and p95 end-to-end latency around 22.6 seconds.
- GuideLLM note: HTML output from `ghcr.io/vllm-project/guidellm:v0.5.0` failed on a redirected report-template URL, so the automation defaults to JSON and CSV output and smoke tests can override to JSON-only.
- Regression validation: PASSED 2026-06-12 - Stage 010 `validate.sh` 17/17 and Stage 020 `validate.sh` 23/23 after KServe became `Managed`.
- Manual dashboard validation: user created `demo-registry` in `rhoai-model-registries`, registered Nemotron 3, and manually deployed `nvidia-nemotron-3-nano-30b-a3b` in `demo-sandbox` from `oci://registry.redhat.io/rhai/modelcar-nvidia-nemotron-3-nano-30b-a3b-fp8:3.0`. Guarded read-only check confirmed a ready `serving.kserve.io/v1beta1` `InferenceService` and matching `ServingRuntime` using model format `vLLM`.
- Idempotent deploy validation: PASSED 2026-06-12. `030-private-model-serving/deploy.sh` reused existing `demo-registry`, Nemotron registered model id `1`, version id `2`, artifact id `1`, serving environment id `3`, and the existing `demo-sandbox/nvidia-nemotron-3-nano-30b-a3b` `InferenceService`.
- Expanded live validation: PASSED 2026-06-12 - `030-private-model-serving/validate.sh` 17/17 for KServe, vLLM, registry availability, Nemotron metadata, and endpoint readiness.
- Regression validation after idempotent bootstrap changes: PASSED 2026-06-12 - Stage 010 `validate.sh` 17/17 and Stage 020 `validate.sh` 23/23.
- Grafana OAuth RBAC fix: PASSED 2026-06-12 - replaced the cluster-scoped `get namespaces` OAuth proxy SAR with a namespace-scoped `get services` SAR in `rhoai-demo-grafana`, added `grafana-viewer-demo-users` for `rhods-admins` and `rhoai-developers`, and validated `oc auth can-i get services -n rhoai-demo-grafana --as ai-admin --as-group rhods-admins` and the equivalent `ai-developer` check with `rhoai-developers`.
- Official Grafana Operator validation: PASSED 2026-06-12 - checked the Stage 030 Grafana GitOps setup against the official Grafana Operator docs, Argo CD dashboard guide, Kustomize installation docs, and API reference. Confirmed active OLM package `grafana-operator`, channel `v5`, CSV `grafana-operator.v5.24.0`, `grafana.integreatly.org/v1beta1` CRDs, `GrafanaReady=True`, `DatasourceSynchronized=True`, and `DashboardSynchronized=True` for both Stage 030 dashboards. The install path remains an intentional OpenShift OLM/GitOps adaptation rather than the official Grafana Helm or direct Kustomize install path.
- Grafana dashboard datasource fix: PASSED 2026-06-12 - confirmed the live Grafana datasource name and UID are `Prometheus`, replaced unresolved `${DS_PROMETHEUS}` imports in the performance dashboard with that concrete UID, and renamed dashboard titles to the functional names `vLLM Model Serving Baseline` and `LLM Inference Performance`.
