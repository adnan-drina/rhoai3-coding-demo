# Official Doc Extraction

## Purpose And Decision Boundary

Distributed Inference with llm-d is a Kubernetes-native framework for serving
large language models at scale. Use it when the demo needs distributed LLM
serving behavior such as prefix-cache-aware routing, disaggregated serving,
Endpoint Picker scheduling, autoscaling model-server variants, or priority
queuing for mixed workloads.

Do not use llm-d when the task is a simple single-model deployment that can be
served by standard KServe/vLLM.

## Support Posture

- Gateway discovery for Distributed Inference with llm-d is Technology Preview.
- Distributed Inference with llm-d monitoring is Developer Preview.
- `LLMInferenceService`, scheduler, WVA, flow-control, and Gateway Inference
  Extension APIs use alpha API surfaces in the official guide. Use
  `rhoai-api-tiers` and installed CRD schema checks before treating them as
  durable contracts.

## Base Prerequisites

Before deploying llm-d:

- model serving platform is enabled
- OpenShift meets the active baseline and official guide minimum
- OpenShift Service Mesh v2 is not installed in the cluster
- a `GatewayClass` exists
- a Gateway named `openshift-ai-inference` exists in `openshift-ingress` for
  the default shared Gateway path
- shared Gateways are used only across trusted namespaces
- LeaderWorkerSet Operator is installed
- bare-metal clusters have an external entry point for the Gateway service
- authentication has been configured through Red Hat Connectivity Link

The guide notes that the Inference Gateway uses `LoadBalancer` by default. If a
cluster lacks LoadBalancer support, use the documented OpenShift load-balancing
path rather than inventing a routing workaround.

## LLMInferenceService

`LLMInferenceService` replaces the default `InferenceService` for distributed
inference. The official example includes:

- `apiVersion: serving.kserve.io/v1alpha1`
- `kind: LLMInferenceService`
- `spec.replicas`
- `spec.model.uri`
- `spec.model.name`
- `spec.router.route`
- `spec.router.gateway`
- `spec.router.scheduler`
- `spec.router.template.containers[].resources` with CPU, memory, and GPU
  requests/limits

The guide lists model URI patterns:

- `s3://<bucket-name>/<object-key>`
- `pvc://<claim-name>/<pvc-path>`
- `oci://<registry_host>/<org_or_username>/<repository_name><tag_or_digest>`
- `hf://<model>/<optional-hash>`

Use GitOps only after the active CRD schema confirms the fields for the target
RHOAI version.

## Gateway Discovery And Selection

Gateway discovery lets users discover and select existing Kubernetes Gateways
from the model deployment UI. It is disabled by default and must be enabled by
an administrator through `OdhDashboardConfig`:

- `spec.dashboardConfig.llmGatewayField: true`

A Gateway appears only when:

- the user has RBAC permission to create `LLMInferenceService` resources in
  the target namespace
- the Gateway listener accepts routes from the target namespace

The official guide warns that the system does not validate a specific
`GatewayClass` controller. The default OpenShift Gateway controller provides
all llm-d features; third-party controllers might be incompatible.

Gateway selection does not support MaaS Gateways. Use `rhoai-maas-governance`
for MaaS gateway behavior.

YAML Gateway selection uses `spec.router.gateway.refs[]` with Gateway name and
namespace. Multiple Gateway refs require YAML; the model deployment wizard only
shows the first Gateway if an existing deployment has multiple refs.

## Connectivity Link And Authorino

Red Hat Connectivity Link provides authentication and authorization for llm-d
inference endpoints. It works with the Gateway to intercept traffic before it
reaches vLLM and validates requests based on tokens and authorization policy.

The official setup includes:

- Red Hat Connectivity Link version 1.1.1 or later
- `Kuadrant` custom resource in `kuadrant-system`
- readiness wait for `Kuadrant`
- serving certificate annotation on
  `svc/authorino-authorino-authorization`
- `Authorino` custom resource with TLS listener enabled and
  `certSecretRef.name: authorino-server-cert`
- ready Authorino pods
- controller restart if OpenShift AI was installed before Connectivity Link
  and Kuadrant

Use the exact official commands or GitOps equivalents only after verifying
installed resource names and API versions.

## Authentication And Requests

In OpenShift AI 3.0 and later, authentication and authorization are
automatically enabled for `LLMInferenceService` resources when Connectivity
Link is configured.

Use `security.opendatahub.io/enable-auth: "true"` to explicitly enable auth or
to re-enable it after disabling.

To make authenticated requests:

- create a ServiceAccount
- grant a Role with `get` permission on the target `LLMInferenceService`
- bind the Role to the ServiceAccount
- generate a JWT token with `oc create token`
- send inference requests with `Authorization: Bearer ${TOKEN}`

OIDC tokens can also be used when integrated with an identity provider.

## vLLM Arguments

The guide includes a vLLM argument reference and examples for llm-d:

- single-node GPU deployment
- multi-node deployment
- intelligent inference scheduler with KV cache routing
- uvicorn access logs

Keep vLLM runtime arguments tied to documented behavior. Do not invent vLLM
arguments in GitOps; verify them against the official guide, runtime docs, and
installed `LLMInferenceService` schema.

## Scheduler And Endpoint Picker

The Endpoint Picker selects endpoints for requests and can be configured inline
in `LLMInferenceService` under `spec.router.scheduler` or through ConfigMap
references.

Official scheduler areas include:

- Endpoint Picker architecture
- complete request path
- default scheduler plugins
- inline `EndpointPickerConfig`
- ConfigMap-based `EndpointPickerConfig`
- plugin references and selection
- prefix cache routing behavior

Use the official scheduler examples for field placement and verify CRD schema
before implementation.

## Workload Variant Autoscaler

The Workload Variant Autoscaler (WVA) scales llm-d model deployments by
observing saturation signals such as KV cache utilization, queue length, and
spare capacity.

Prerequisites include:

- DSCI and DSC CRDs exist
- `kserve.managementState: Managed`
- KServe, LLMISVC, and WVA controller managers exist
- WVA is enabled through `DataScienceCluster.spec.components.kserve.wva`
- the namespace contains only one Distributed Inference with llm-d inference
  stack for WVA use

The official guide shows `VariantAutoscaling` resources and saturation-scaling
ConfigMaps. Defaults and thresholds should be reviewed against active GPU
capacity.

## Saturation Scaling ConfigMap

The WVA saturation-scaling ConfigMap is named
`workload-variant-autoscaler-saturation-scaling-config`.

It contains:

- a `default` entry for global parameters
- optional model-specific override entries

Key fields include:

- `kvCacheThreshold`
- `queueLengthThreshold`
- `kvSpareTrigger`
- `queueSpareTrigger`
- `enableLimiter`
- override `model_id`
- override `namespace`

Keep thresholds conservative for small GPU demo clusters. Do not claim
autoscaling behavior without load testing and metrics evidence.

## Flow Control And Priority Queuing

Flow control enables priority-based queuing for multitenant llm-d workloads.

The official flow-control path requires:

- llm-d with Inference Gateway and Endpoint Picker
- authentication and authorization enabled
- cluster administrator access
- Endpoint Picker flow-control feature gate
- `saturationDetector` settings
- `InferenceObjective` resources for priority tiers

`InferenceObjective` uses
`apiVersion: inference.networking.x-k8s.io/v1alpha2` in the official example.
It defines priority and `poolRef` for the target `InferencePool`.

Priority values:

- higher integers dispatch first
- zero is default priority
- negative values are lower priority

Flow-control settings include:

- `maxBytes`
- `defaultRequestTTL`
- `priorityBands[].priority`
- `priorityBands[].orderingPolicyRef`
- `priorityBands[].fairnessPolicyRef`

The guide recommends round-robin fairness for equitable tenant distribution;
the default global strict fairness can result in starvation.

## Observability

Distributed Inference with llm-d monitoring is Developer Preview.

The guide describes Prometheus metrics for:

- vLLM engine performance and resource use
- Endpoint Picker and inference scheduler routing decisions
- inference objective SLO signals
- prefix cache indexer behavior
- inference pool state

On OpenShift, the controller automatically creates `PodMonitor` and
`ServiceMonitor` resources for `LLMInferenceService` deployments. Do not claim
production monitoring readiness from Developer Preview metrics alone.

## Troubleshooting Signals

Prefer readonly checks first:

- `LLMInferenceService` Ready condition
- Gateway reference under `spec.router.gateway`
- Gateway listener `allowedRoutes`
- service account Role and RoleBinding
- unauthenticated request returns `401 Unauthorized`
- authenticated request returns successful chat completion
- KServe, LLMISVC, and WVA controller pods are ready
- `VariantAutoscaling`, `ScaledObject`, and HPA resources exist for autoscaled
  deployments
- flow-control queue metrics change only under sustained saturation
- Developer Preview metrics are present only when monitoring resources are
  created and scraped
