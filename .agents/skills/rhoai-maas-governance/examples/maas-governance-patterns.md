# MaaS Governance Patterns

These snippets are review patterns derived from the official MaaS guide. Before
committing GitOps, verify exact installed CRD schemas with `oc api-resources`,
`oc get crd`, and `oc explain` under the OpenShift safety guard in `AGENTS.md`.

The official RHOAI 3.4 guide shows some YAML examples with
`apiVersion: models.opendatahub.io/v1alpha1`, but its CRD verification section
lists MaaS CRDs under `*.maas.opendatahub.io`. The active `rhoai3-demo`
cluster exposes MaaS resources as `maas.opendatahub.io/v1alpha1`; use that
group/version after confirming it with `oc api-resources`.

## Phase-Gated GitOps Pattern

When MaaS CRDs are not present yet, do not commit all model and policy CRs in
one pass. Use this sequence:

1. Verify cert-manager as a platform prerequisite, then install or verify Red
   Hat Connectivity Link.
2. Create `Kuadrant`, `Authorino`, the Authorino service certificate
   annotation, and the MaaS Gateway API resources.
3. Provide `maas-db-config` in `redhat-ods-applications`, backed by a
   PostgreSQL 14+ database. For this demo, an in-cluster PostgreSQL 16 database
   is acceptable only as demo posture.
4. Enable `DataScienceCluster.spec.components.kserve.modelsAsService` and the
   required dashboard flags through the shared DSC/dashboard owner.
5. Wait for MaaS CRDs, then run `oc api-resources`, `oc get crd`, and
   `oc explain` before committing `MaaSModelRef`, `ExternalModel`,
   `MaaSSubscription`, or `MaaSAuthPolicy`.

Review points:

- This pattern avoids guessing resource fields before the installed RHOAI
  controller exposes its CRDs.
- Keep provider credentials, database passwords, and API keys outside Git.
- Use sync waves and `SkipDryRunOnMissingResource=true` only where controller
  CRDs genuinely appear after prerequisite reconciliation.
- If a MaaS `Gateway` terminates TLS with the OpenShift ingress certificate,
  create a stable same-namespace Secret such as `maas-gateway-tls` before the
  `Gateway` sync wave. Do not point the initial `Gateway` at a placeholder
  certificate Secret and rely on a later patch hook; Argo CD can mark the
  Gateway degraded before the later hook runs.
- If Argo CD uses `RespectIgnoreDifferences=true`, do not ignore the Gateway
  certificate reference while trying to repair a bad certificate reference
  through GitOps. Ignored fields are not applied during sync.
- Prefer setting environment-specific Gateway hostnames through the Argo CD
  Application source or a generated overlay before sync. Use post-sync Gateway
  patch hooks only for fields that cannot block Gateway health.
- Do not patch generated Kuadrant `AuthPolicy` or EnvoyFilter resources from
  GitOps to force MaaS header injection. If generated gateway policy fails,
  validate the supported RHOAI, RHCL, Kuadrant, and OpenShift Service Mesh
  version path instead.

## Local Model Reference Pattern

```yaml
apiVersion: maas.opendatahub.io/v1alpha1
kind: MaaSModelRef
metadata:
  name: nemotron-3-nano-30b-a3b
  namespace: models-as-a-service
spec:
  modelRef:
    kind: LLMInferenceService
    name: nemotron-3-nano-30b-a3b
```

Review points:

- underlying `LLMInferenceService` must be ready before MaaS exposure
- namespace must match the namespace that contains the model-serving backend;
  this repo uses `models-as-a-service` for the MaaS-owned Nemotron backend
- vLLM with MaaS is Technology Preview if this backend uses vLLM

## Demo Nemotron MaaS Implementation Reference

The Red Hat-maintained `rh-ai-quickstart/maas-code-assistant` chart provides a
useful Stage 220 reference for publishing Nemotron 3 Nano through MaaS. The
working `rhoai3-coding-demo` implementation adds the concrete llm-d scheduler,
prefix-caching, and tool-calling settings this project should preserve:

- `LLMInferenceService` with `alpha.maas.opendatahub.io/tiers`
- Gateway reference to `maas-default-gateway` in `openshift-ingress`
- vLLM command and TLS args for OpenAI-compatible serving
- model-specific Nemotron vLLM args for usage reporting, context length, tool
  calling, trusted remote code, prefix caching, batched-token scheduling, and
  reasoning parser support
- per-tier RBAC allowing `system:serviceaccounts:maas-default-gateway-tier-*`
  groups to read the model resource
- llm-d single-GPU-per-replica labels and scheduler pool shape

Review points:

- Use the quickstart as implementation evidence, not as product API authority.
- Verify RHOAI 3.4 CRD schemas before committing `LLMInferenceService`, MaaS
  tiers, Gateway, or RBAC resources.
- The quickstart uses a sample modelcar URI for its scenario; this demo should
  keep the Red Hat registry Nemotron modelcar unless the model source decision
  changes explicitly.
- For the full reusable Nemotron direct-serving and MaaS examples, use
  `../../rhoai-model-serving-platform/examples/nemotron-vllm-configurations.md`.

## External OpenAI Model Pattern

```yaml
apiVersion: maas.opendatahub.io/v1alpha1
kind: ExternalModel
metadata:
  name: gpt-4o-mini
  namespace: models-as-a-service
spec:
  provider: openai
  endpoint: api.openai.com
  targetModel: gpt-4o-mini
  credentialRef:
    name: openai-provider-api-key
---
apiVersion: maas.opendatahub.io/v1alpha1
kind: MaaSModelRef
metadata:
  name: gpt-4o-mini
  namespace: models-as-a-service
spec:
  modelRef:
    kind: ExternalModel
    name: gpt-4o-mini
```

Review points:

- `openai-provider-api-key` is a Secret, not a committed value
- for the current RHOAI 3.4 MaaS path, `ExternalModel` and `MaaSModelRef`
  names must be DNS-1035 compatible; when possible, select an upstream provider
  model ID that is also a valid Kubernetes name
- if an upstream model ID is not DNS-safe, use a DNS-safe resource alias and
  keep the exact provider model ID in `spec.targetModel`
- the `ExternalModel` controller creates Kubernetes Services from the resource
  name, so dotted provider IDs are invalid as resource names
- external models through MaaS are Technology Preview
- provider-level rate limits apply across all users sharing the provider key
- users still need a MaaS API key, subscription, and authorization policy

## Subscription And Auth Policy Pattern

```yaml
apiVersion: maas.opendatahub.io/v1alpha1
kind: MaaSSubscription
metadata:
  name: enterprise-ai-builders
  namespace: models-as-a-service
spec:
  owner:
    groups:
      - name: enterprise-ai-builders
  modelRefs:
    - name: nemotron-3-nano-30b-a3b
      namespace: models-as-a-service
      tokenRateLimits:
        - limit: 100000
          window: "1h"
    - name: gpt-4o-mini
      namespace: models-as-a-service
      tokenRateLimits:
        - limit: 20000
          window: "1h"
  priority: 100
---
apiVersion: maas.opendatahub.io/v1alpha1
kind: MaaSAuthPolicy
metadata:
  name: enterprise-ai-builders
  namespace: models-as-a-service
spec:
  subjects:
    groups:
      - name: enterprise-ai-builders
  modelRefs:
    - name: nemotron-3-nano-30b-a3b
      namespace: models-as-a-service
    - name: gpt-4o-mini
      namespace: models-as-a-service
  meteringMetadata:
    organizationId: acme-eu
    costCenter: ai-platform
    labels:
      environment: demo
```

Review points:

- subscription and auth policy are both required
- every model has at least one token limit
- token limits include a supported time window such as `1h` or `24h`
- priority matters when users belong to overlapping groups
- cost metadata supports showback, not billing-grade invoicing

## Client Request Pattern

```bash
curl -k -X POST "https://<maas-gateway-url>/llm/<model-name>/v1/chat/completions" \
  -H "Authorization: Bearer <maas-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<model-name>",
    "messages": [
      {"role": "user", "content": "Summarize the current demo architecture."}
    ]
  }'
```

Review points:

- `<maas-api-key>` is a MaaS key with the `sk-oai-` prefix
- key owner must have matching subscription and authorization policy access
- use `-k` only when the demo environment uses self-signed certificates
