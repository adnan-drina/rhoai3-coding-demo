# Validation Checklist

Use this checklist before accepting model management, monitoring, or
autoscaling documentation, runbooks, or GitOps changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official guide URL uses the active `/3.4/` baseline path.
- The work is about deployed-model operations, monitoring, autoscaling,
  runtime administration, or NIM model/metrics operations.
- Platform enablement and runtime design are delegated to
  `rhoai-model-serving-platform`.
- General RHOAI observability stack setup is delegated to `rhoai-observability`.
- GPU enablement is delegated to `rhoai-nvidia-gpu-accelerators`.
- TrustyAI fairness, drift, and bias monitoring are not claimed as covered.

## Runtime And Timeout Review

- Custom runtime support boundary is documented.
- Runtime image provenance is checked.
- Custom runtime protocol is REST or gRPC.
- Required custom runtime `env` entries are documented and secret-safe.
- KServe progress deadline is set under `spec.predictor.annotations`.
- Timeout value matches observed pull/startup behavior for large models or node
  autoscaling.

## Multi-Node vLLM Review

- Technology Preview status is labeled.
- NVIDIA GPU resource is verified as `nvidia.com/gpu`.
- KServe and GPU prerequisites are ready.
- Only one head pod is configured.
- `min_replicas` and `max_replicas` are not used to create additional head
  pods.
- PVC-backed deployments use RWX storage.
- OCI-backed deployments use verified image references and pull secrets.
- `ServingRuntime` and `InferenceService` GPU types match.
- `workerSpec.tensorParallelSize` is at least `1` when set.
- `workerSpec.pipelineParallelSize` is at least `2` when set.
- Current demo hardware supports the requested multi-node topology.

## Kueue Review

- LocalQueue exists in the target namespace.
- `InferenceService.metadata.labels.kueue.x-k8s.io/queue-name` points to the
  target `LocalQueue`.
- Namespace and queue policies are managed with `rhoai-kueue-workload-management`.
- `oc describe localqueue` shows admitted workload state when the model starts.

## Performance And Autoscaling Review

- SLOs identify whether latency, throughput, or cost per million tokens is the
  primary objective.
- Load tests use realistic prompt and output token distributions.
- TTFT/ITL metrics are preferred for high-variance workloads.
- End-to-end latency is used only when sequence lengths are reasonably uniform.
- `vllm:num_requests_waiting` is used for throughput-focused queue scaling.
- Sliding window length follows the selected metric behavior.
- KEDA/CMA Technology Preview status is documented.
- `ScaledObject` scale-down stabilization is reviewed for cold-start and cost
  tradeoffs.

## Monitoring Review

- User Workload Monitoring is enabled for user-defined projects.
- Prometheus retention is intentionally configured.
- `monitoring-rules-view` is assigned to monitoring users.
- Service Mesh monitoring resources are applied only when Service Mesh and
  Knative/KServe are installed.
- Model runtime emits the metric names used by dashboards or autoscaling.
- Grafana dashboards filter on the correct namespace and model name.
- NVIDIA GPU dashboards are enabled before claiming GPU metrics visibility.

## NVIDIA NIM Review

- NIM is an approved demo capability before adding NIM model selection.
- NGC model IDs are verified from NGC Catalog or NGC CLI.
- NIM `Account` CR name and namespace are confirmed.
- model list ConfigMap is in the same namespace as the `Account` CR.
- `Account.spec.modelListConfig.name` points to the ConfigMap.
- Existing upgraded NIM deployments have graph-generation annotation on
  `ServingRuntime` when graphs are required.
- Existing upgraded NIM deployments have Prometheus path and port annotations
  on `InferenceService` when metrics are required.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get servingruntime -A
oc get inferenceservice -A
oc get localqueue -A
oc describe localqueue <local-queue-name> -n <project-namespace>
oc get scaledobject -A
oc get configmap user-workload-monitoring-config -n openshift-user-workload-monitoring -o yaml
oc get configmap cluster-monitoring-config -n openshift-monitoring -o yaml
oc get servicemonitor,podmonitor -A
oc get account -A
```

Schema checks:

```bash
oc explain inferenceservice.spec.predictor.annotations
oc explain inferenceservice.metadata.labels
oc explain scaledobject.spec
```

## GitOps Review

- Long-lived `InferenceService`, `ServingRuntime`, `ScaledObject`,
  `ServiceMonitor`, `PodMonitor`, ConfigMap, and Grafana dashboard resources
  are managed through ArgoCD once active GitOps exists.
- Official CLI patch examples are converted to GitOps when the desired state
  should persist.
- Demo READMEs label Technology Preview features.
- Operations docs record autoscaling thresholds, Grafana dashboards, and NIM
  model list decisions when implemented.
- README claims match implemented metrics and dashboards.

## Fail Conditions

- KServe timeout annotation is placed outside `spec.predictor.annotations`.
- Multi-node vLLM is presented as production supported.
- Additional head pods are configured for multi-node vLLM.
- Kueue label references a missing `LocalQueue`.
- Autoscaling thresholds are copied from examples without load testing.
- Grafana dashboards are presented before UWM and runtime metrics are ready.
- NIM model IDs or account namespace are guessed.
- NIM credentials or API keys are committed.
