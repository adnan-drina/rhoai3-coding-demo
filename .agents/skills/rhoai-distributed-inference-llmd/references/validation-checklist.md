# Validation Checklist

Use this checklist when authoring docs, GitOps, runbooks, or troubleshooting
notes for Distributed Inference with llm-d.

## Source And Scope

- The work references `docs/PLATFORM_BASELINE.md` and the RHOAI 3.4 llm-d
  guide, not an unversioned latest documentation path.
- The use case genuinely needs distributed inference, scheduler behavior,
  autoscaling variants, or priority queuing.
- Gateway discovery is labeled Technology Preview.
- llm-d monitoring is labeled Developer Preview.
- Alpha APIs are reviewed with `rhoai-api-tiers` and installed CRD schema
  checks before durability claims are made.

## Prerequisites

- Model serving platform is enabled.
- OpenShift Service Mesh v2 is not installed.
- Gateway API resources exist.
- A trusted Gateway such as `openshift-ai-inference` exists in
  `openshift-ingress`, or a namespace-scoped Gateway is documented.
- Shared Gateways are used only across trusted namespaces.
- LeaderWorkerSet Operator is installed.
- Red Hat Connectivity Link and `Kuadrant` are installed and ready.
- Authorino TLS is configured and Authorino pods are ready.
- Dashboard flags are enabled only for features the demo actually uses.

## Resource Review

- `LLMInferenceService` manifests use fields confirmed by official docs or
  installed CRD schema.
- Model URI source is one of the documented forms: S3, PVC, OCI, or Hugging
  Face.
- GPU requests and limits use the active accelerator identifier from
  `rhoai-nvidia-gpu-accelerators`.
- Gateway references match actual Gateway names, namespaces, and listener
  `allowedRoutes`.
- Gateway selection does not point at MaaS Gateways.
- Auth is enabled for shared demo endpoints.
- ServiceAccount Role grants only the required `get` access to the target
  `LLMInferenceService`.
- vLLM arguments are traceable to official docs or runtime documentation.
- Scheduler and Endpoint Picker settings are verified against the installed
  schema.
- WVA is enabled only when cluster GPU capacity can support the configured
  `minReplicas` and `maxReplicas`.
- Flow-control priority bands match the `InferenceObjective` priorities.

## Readonly Verification Commands

Run only after the OpenShift safety guard in `AGENTS.md` is satisfied:

```bash
oc get gatewayclass
oc get gateway openshift-ai-inference -n openshift-ingress -o yaml
oc get pods -n kuadrant-system
oc get kuadrant kuadrant -n kuadrant-system
oc get pods -n redhat-ods-applications -l 'app.kubernetes.io/name in (kserve-controller-manager,llmisvc-controller-manager,workload-variant-autoscaler)'
oc get llminferenceservices -A
oc get llminferenceservice <llm-service-name> -n <namespace> -o yaml
oc get llminferenceservice <llm-service-name> -n <namespace> -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'
oc get variantautoscaling -A
oc get scaledobject -A
oc get inferenceobjective -A
```

Use schema checks before durable GitOps authoring:

```bash
oc explain llminferenceservices.serving.kserve.io.spec
oc explain variantautoscalings.serving.kserve.io.spec
oc explain inferenceobjectives.inference.networking.x-k8s.io.spec
oc explain odhdashboardconfig.spec.dashboardConfig
```

## Functional Checks

- Unauthenticated requests to an authenticated `LLMInferenceService` return
  `401 Unauthorized`.
- Authenticated chat completion requests with a valid JWT succeed.
- Gateway dropdown is populated only when RBAC and listener conditions are met.
- `spec.router.gateway.refs` contains the expected Gateway references for
  YAML-managed deployments.
- WVA load tests show expected replica changes before autoscaling claims are
  made.
- Flow-control load tests create queue depth before priority differentiation is
  claimed.
- Prometheus metrics exist before observability claims are made, and Developer
  Preview status is documented.

## Failure Conditions

Do not approve a llm-d change when:

- a simple standard model serving path is being replaced by llm-d without a
  scale, scheduler, or priority-queuing requirement
- shared Gateways cross untrusted namespaces
- auth is disabled on shared endpoints without a documented exception
- ServiceAccount tokens or provider credentials are committed
- third-party Gateway controllers are assumed compatible without verification
- WVA settings exceed available GPU capacity
- monitoring is described as production-supported despite Developer Preview
  status
- exact CR fields are copied from memory instead of official docs or installed
  schema
