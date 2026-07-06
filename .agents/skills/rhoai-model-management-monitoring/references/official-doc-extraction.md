# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 guide captured in
`source-capture.md`.

## Custom Model-Serving Runtimes

Administrators can add and enable custom model-serving runtimes from the
OpenShift AI dashboard.

Dashboard path:

```text
OpenShift AI dashboard -> Settings -> Model resources and operations -> Serving runtimes
```

Important behavior:

- custom runtimes can be created by duplicating an existing runtime or adding a
  new runtime
- supported protocol selection is REST or gRPC
- runtime YAML can be uploaded or entered directly in the embedded editor
- many custom runtimes require custom `env` parameters in the
  `ServingRuntime` spec
- a newly added custom runtime is automatically enabled
- Red Hat does not support custom runtimes; the customer owns licensing,
  configuration, and maintenance

Use `rhoai-model-serving-platform` for broader runtime design and support
posture.

## KServe Progress Deadline

KNative Serving defaults `progress-deadline` to 10 minutes. Large model
deployments or deployments that wait for node autoscaling can exceed that time
and be marked as failed.

Official field placement:

```yaml
spec:
  predictor:
    annotations:
      serving.knative.dev/progress-deadline: 30m
```

The annotation must be under `spec.predictor.annotations` so KServe copies the
setting to the Knative Service object.

## Multi-Node vLLM Deployments

Multi-node inferencing is Technology Preview in the captured guide. It uses the
`vllm-multinode-runtime` custom runtime and can serve models across multiple
GPU nodes.

Prerequisites and constraints:

- cluster administrator privileges
- GPU Operator and accelerator prerequisites are enabled
- NVIDIA GPU resource is `nvidia.com/gpu`
- KServe is enabled
- only one head pod is used
- do not adjust `min_replicas` or `max_replicas` in the `InferenceService`
  because additional head pods can be excluded from the Ray cluster
- PVC deployments require RWX access mode
- OCI deployments require model image and image pull secret when the registry
  is private
- GPU type in `ServingRuntime` and `InferenceService` must match; mismatches
  can assign both GPU types and cause errors

Official runtime creation pattern:

```bash
oc process vllm-multinode-runtime-template -n redhat-ods-applications | oc apply -n <namespace> -f -
```

Official `InferenceService` field areas:

- `metadata.annotations.serving.kserve.io/deploymentMode: RawDeployment`
- `metadata.annotations.serving.kserve.io/autoscalerClass: external`
- `spec.predictor.model.modelFormat.name: vLLM`
- `spec.predictor.model.runtime: vllm-multinode-runtime`
- `spec.predictor.model.storageUri`
- `spec.predictor.workerSpec`
- optional `workerSpec.tensorParallelSize`
- optional `workerSpec.pipelineParallelSize`

Storage URI patterns:

- PVC: `pvc://<pvc_name>/<model_path>`
- OCI image: `oci://<registry_host>/<org_or_username>/<repository_name><tag_or_digest>`

## Kueue Routing For InferenceService

Inference services can be routed to a Kueue `LocalQueue` by adding a label to
the `InferenceService` metadata:

```yaml
metadata:
  labels:
    kueue.x-k8s.io/queue-name: <local-queue-name>
```

Verification:

- workload is submitted to the named `LocalQueue`
- workload starts when required cluster resources are available and admitted by
  the queue
- `oc describe localqueue <local-queue-name> -n <project-namespace>` shows the
  admitted workload state

Use `rhoai-kueue-workload-management` for queue design and namespace
enforcement.

## Spyre InferenceService Configuration

IBM Spyre AI Accelerator support on x86 is Technology Preview in OpenShift AI
3.4. This demo uses NVIDIA GPUs by default, so Spyre guidance is source
knowledge only unless the baseline changes.

The guide requires post-deployment `InferenceService` YAML edits when a
hardware profile relies on Spyre schedulers because the UI does not currently
provide a custom scheduler option.

Official field areas:

```yaml
spec:
  predictor:
    schedulerName: spyre-scheduler
    tolerations:
    - effect: NoSchedule
      key: ibm.com/spyre_pf
      operator: Exists
```

For IBM Z, the guide notes:

- continuous batching is required
- required runtime args include `--max_model_len`, `--max-num-seqs`, and
  `--tensor-parallel-size`
- IBM Z uses the VF toleration key `ibm.com/spyre_vf`

## Performance And Tuning

Key inference performance metrics:

- latency, including Time to First Token and Inter-Token Latency
- throughput, measured as tokens per second or requests per second
- cost per million tokens

Performance is affected by model size, GPU memory, input sequence length, KV
cache size, quantization, tensor parallelism, and workload type.

GPU memory guidance from the guide:

- 16-bit model weights require roughly two bytes per model parameter
- 1B-8B parameter models generally fit on a GPU with 24GB of memory for a
  small number of concurrent users
- models under 20B parameters require at least 48GB GPU memory
- models between 20B and 34B parameters require 80GB or more memory in one GPU
- 70B models may require multiple GPUs and tensor parallelism

For text summarization and RAG:

- input and output sequence length strongly influence latency
- larger context windows increase KV cache pressure
- realistic tests should use representative prompt and completion lengths

## Metrics-Based Autoscaling

Metrics-based autoscaling is Technology Preview in the captured guide.

Prerequisites:

- OpenShift Service Mesh and Knative Serving instances are created
- KServe is installed
- user workload monitoring is enabled
- cert-manager Operator is installed
- OpenShift Custom Metrics Autoscaler Operator is installed
- model is deployed by using RawDeployment mode
- model-serving runtime emits the selected metrics

Official areas used for KEDA/CMA scaling:

- `serving.kserve.io/autoscalerClass: keda`
- `spec.predictor.autoscaling.metrics`
- Prometheus metric backend server address
- metric query, such as `vllm:num_requests_waiting`
- target value
- authentication reference such as `inference-prometheus-auth`
- KEDA `ScaledObject` verification

Autoscaling guidance:

- TTFT and ITL are useful for high-variance workloads
- end-to-end latency is useful for more uniform input and output sequence
  lengths
- for throughput-focused scaling, `vllm:num_requests_waiting > 0.1` avoids a
  zero threshold and scales when requests queue
- use 1-2 minute windows for TTFT and ITL
- use 4-5 minute windows for end-to-end latency
- avoid windows shorter than 30 seconds
- use `stabilizationWindowSeconds` on the KEDA `ScaledObject` to tune HPA
  scale-down behavior

## Monitoring The Model Serving Platform

The model serving platform includes metrics for supported KServe runtimes.
KServe does not generate its own metrics; available metrics depend on the
underlying model-serving runtime.

Service Mesh metrics can also be collected to understand dependencies and
traffic between mesh components.

User Workload Monitoring setup in the guide includes:

- `user-workload-monitoring-config` ConfigMap in
  `openshift-user-workload-monitoring`
- recommended Prometheus retention value of 15 days
- `cluster-monitoring-config` ConfigMap in `openshift-monitoring`
- `enableUserWorkload: true`
- `ServiceMonitor` for `istiod` in `istio-system`
- `PodMonitor` for Istio proxies in `istio-system`
- `monitoring-rules-view` role for users who monitor metrics

## Grafana Dashboards And Metrics

Grafana dashboards can visualize model-serving runtime and hardware
accelerator metrics. The guide references overlays for User Workload Monitoring
dashboards and dashboard examples for OVMS, vLLM, and accelerator metrics.

Dashboard inputs:

- `NAMESPACE`: namespace where the model is deployed
- `MODEL_NAME`: model name as defined in the `InferenceService`

GPU dashboard note:

- NVIDIA GPU metrics require the NVIDIA GPU monitoring dashboard.

Common metric families from the guide:

- accelerator metrics: GPU utilization, memory usage, temperature, throttling
- CPU utilization and CPU/GPU bottlenecks
- vLLM GPU and CPU cache utilization
- running requests
- waiting requests
- prefix cache hit rates
- request success count by finished reason
- end-to-end latency
- Time to First Token latency
- Time Per Output Token latency
- prompt token throughput
- generation token throughput
- total generated tokens

## NVIDIA NIM Model Selection And Metrics

The NVIDIA NIM platform can be customized to show a preferred list of models in
the Deploy model dialog.

Official model list resource shape:

- ConfigMap named such as `nvidia-nim-enabled-models`
- `data.models` contains a JSON list of NGC model IDs
- ConfigMap is deployed in the same namespace as the NIM `Account` CR
- `Account.spec.modelListConfig.name` points to the ConfigMap

Existing NIM deployments upgraded to 3.4 can require manual metrics enablement.
New deployments from the referenced release behavior have NIM metrics and
graphs automatically enabled.

Graph generation annotation on `ServingRuntime`:

```yaml
metadata:
  annotations:
    runtimes.opendatahub.io/nvidia-nim: "true"
```

Metrics collection annotations on `InferenceService`:

```yaml
spec:
  predictor:
    annotations:
      prometheus.io/path: /metrics
      prometheus.io/port: "8000"
```

## Out Of Scope For This Guide

This guide does not define:

- RHOAI installation and KServe enablement
- GPU Operator and NFD installation
- full TrustyAI fairness, drift, and bias monitoring
- model quality evaluation and benchmark governance
- production Grafana operations beyond the referenced dashboard patterns
- MaaS governance or llm-d distributed inference; use
  `rhoai-maas-governance` or `rhoai-distributed-inference-llmd`
