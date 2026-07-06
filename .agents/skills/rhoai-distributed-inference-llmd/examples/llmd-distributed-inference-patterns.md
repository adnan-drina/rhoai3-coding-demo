# llm-d Distributed Inference Patterns

These snippets are review patterns derived from the official llm-d guide.
Before committing GitOps, verify exact installed CRD schemas with `oc explain`
and the OpenShift safety guard in `AGENTS.md`.

The namespace examples below use `example-model-namespace` as a placeholder.
For the rhoai3-demo Stage 220 MaaS implementation, the local Nemotron
`LLMInferenceService` belongs in `models-as-a-service`.

## Basic LLMInferenceService Pattern

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: LLMInferenceService
metadata:
  name: nemotron-llmd
  namespace: example-model-namespace
  annotations:
    security.opendatahub.io/enable-auth: "true"
spec:
  replicas: 2
  model:
    uri: oci://registry.redhat.io/rhai/modelcar-nvidia-nemotron-3-nano-30b-a3b-fp8:3.0
    name: nemotron-3-nano-30b-a3b
  router:
    route: {}
    gateway: {}
    scheduler: {}
    template:
      containers:
        - name: main
          resources:
            requests:
              cpu: "2"
              memory: 16Gi
              nvidia.com/gpu: "1"
            limits:
              cpu: "4"
              memory: 32Gi
              nvidia.com/gpu: "1"
```

Review points:

- verify the OCI modelcar source is approved for the demo before use
- keep authentication enabled for shared endpoints
- confirm the active CRD accepts the chosen `model` and `router` shape
- confirm GPU capacity before setting replicas above one

## YAML Gateway Reference Pattern

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: LLMInferenceService
metadata:
  name: nemotron-llmd
  namespace: example-model-namespace
spec:
  modelSource:
    storageUri: oci://registry.example.com/org/modelcar:tag
  runtime:
    name: vllm-runtime
  router:
    gateway:
      refs:
        - name: openshift-ai-inference
          namespace: openshift-ingress
```

Review points:

- listener `allowedRoutes` must accept the model namespace
- third-party Gateway controllers may be incompatible
- Gateway selection does not support MaaS Gateways
- verify whether the active CRD expects `model` or `modelSource` for the
  selected deployment path

## ServiceAccount JWT Access Pattern

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: llm-user
  namespace: example-model-namespace
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: llm-inference-viewer
  namespace: example-model-namespace
rules:
  - apiGroups:
      - serving.kserve.io
    resources:
      - llminferenceservices
    verbs:
      - get
    resourceNames:
      - nemotron-llmd
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: llm-user-binding
  namespace: example-model-namespace
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: llm-inference-viewer
subjects:
  - kind: ServiceAccount
    name: llm-user
    namespace: example-model-namespace
```

```bash
TOKEN=$(oc create token llm-user -n example-model-namespace --duration=1h)
curl -k -X POST "https://<inference-endpoint-url>/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "model": "nemotron-3-nano-30b-a3b",
    "messages": [
      {"role": "user", "content": "What is Red Hat OpenShift AI?"}
    ]
  }'
```

Review points:

- Role scope is limited to `get` on the named `LLMInferenceService`
- use short-lived tokens for demos
- never commit generated JWTs

## WVA Saturation Scaling Pattern

```yaml
apiVersion: datasciencecluster.opendatahub.io/v2
kind: DataScienceCluster
metadata:
  name: default-dsc
spec:
  components:
    kserve:
      managementState: Managed
      rawDeploymentServiceConfig: Headed
      wva:
        managementState: Managed
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: workload-variant-autoscaler-saturation-scaling-config
  namespace: redhat-ods-applications
data:
  default: |
    kvCacheThreshold: 0.80
    queueLengthThreshold: 5
    kvSpareTrigger: 0.10
    queueSpareTrigger: 0.10
    enableLimiter: true
```

Review points:

- WVA needs controller pods to be running
- each namespace should contain a single llm-d inference stack for WVA use
- thresholds must be validated with load tests and GPU capacity

## Flow Control Priority Pattern

```yaml
apiVersion: inference.networking.x-k8s.io/v1alpha2
kind: InferenceObjective
metadata:
  name: premium-users
  namespace: example-model-namespace
spec:
  priority: 100
  poolRef:
    group: inference.networking.k8s.io
    kind: InferencePool
    name: nemotron-llmd-inference-pool
```

Review points:

- Endpoint Picker flow-control feature gate must be enabled
- priority bands in scheduler config must include matching priority values
- use load testing to create sustained queue depth before claiming priority
  behavior
