# Official Doc Extraction

## Purpose And Decision Boundary

Models-as-a-Service provides a governance layer between users and LLM serving
infrastructure. Use it when access must be centralized across teams, quota and
token limits must be enforced, usage must be tracked, or model access policy
must be managed declaratively.

Use standard model serving when a model is deployed for a single team, a
single user, or a prototype where the governance layer is unnecessary.

In RHOAI 3.4, MaaS uses subscription-based quota management through custom
resources. Do not recreate older tier-based guidance from RHOAI 3.3.

## Support Posture

- vLLM runtime support with MaaS is Technology Preview.
- External models through MaaS are Technology Preview.
- External OIDC authentication for MaaS is Technology Preview.
- The MaaS observability dashboard is Technology Preview.
- Classify API support posture with `rhoai-api-tiers` before treating MaaS CRs
  or API endpoints as durable contracts.

## Custom Resources

The guide defines these MaaS custom resource responsibilities:

| Resource | Responsibility |
|----------|----------------|
| `Tenant` | Tenant settings, including API key expiration limits, external OIDC authentication, telemetry options, and gateway references |
| `MaaSModelRef` | References the inference backend exposed through MaaS, such as `LLMInferenceService` or `ExternalModel` |
| `ExternalModel` | Defines external provider model configuration and provider credential reference |
| `MaaSSubscription` | Grants users or groups quota for model refs, token rate limits, priority, and optional cost metadata |
| `MaaSAuthPolicy` | Authorizes users or groups to access model endpoints through the API gateway |

Subscriptions control quota. Authorization policies control gateway access.
Users need both to consume a governed model.

The RHOAI 3.4 guide has an API-group discrepancy that must be resolved through
the installed CRDs before GitOps authoring. The verification section lists
CRDs such as `maasmodelrefs.maas.opendatahub.io`, while several YAML examples
use `apiVersion: models.opendatahub.io/v1alpha1`. For the active
`rhoai3-demo` cluster, `oc api-resources`, `oc get crd`, and `oc explain`
confirm `maas.opendatahub.io/v1alpha1` as the served group/version for
`Tenant`, `MaaSModelRef`, `ExternalModel`, `MaaSSubscription`, and
`MaaSAuthPolicy`. Recheck this after any RHOAI or RHCL upgrade.

## Prerequisites

Before deploying MaaS, verify:

- OpenShift is at the active baseline and at least the MaaS guide minimum.
- Cluster-admin access is available for operators and cluster-scoped
  resources.
- Ingress is functional and externally reachable with valid TLS certificates.
- `oc` is available.
- Red Hat OpenShift AI is installed at the active baseline.
- `DataScienceCluster.spec.components.kserve.managementState` is `Managed`.
- User Workload Monitoring is enabled; without it MaaS can report `Degraded`.
- Red Hat Connectivity Link Operator is installed in `openshift-operators`.
- A `Kuadrant` custom resource exists in `kuadrant-system` and is ready.
- If llm-d models are published through MaaS, llm-d authentication and
  authorization prerequisites are complete.
- If vLLM models are published through MaaS, the dashboard vLLM MaaS feature
  flag is enabled and the Technology Preview posture is documented.
- PostgreSQL 14 or later is reachable for API key lifecycle data. OpenShift AI
  does not provide this database.
- Gateway API resources for MaaS exist and have the official required
  annotations.

## Database Secret

MaaS requires a Secret named `maas-db-config` in `redhat-ods-applications`.
The documented key is `DB_CONNECTION_URL` and the connection string format is
PostgreSQL. Store credentials only in a Kubernetes Secret or approved secret
store.

Use `sslmode=require` where the official guide requires a TLS-protected
database connection. Do not commit database URLs or credentials.

## Gateway, Kuadrant, And Authorino

The official guide requires a Gateway API path for MaaS:

- `GatewayClass` for the OpenShift Gateway Controller
- `Gateway` named `maas-default-gateway` in `openshift-ingress`
- `opendatahub.io/managed: "false"` annotation
- `security.opendatahub.io/authorino-tls-bootstrap: "true"` annotation

Authorino TLS setup includes:

- adding a serving certificate annotation to the Authorino authorization
  service in `kuadrant-system`
- patching the `Authorino` custom resource TLS listener to use the generated
  certificate Secret
- setting trust-bundle environment variables on the Authorino deployment so
  outbound TLS verification uses the service CA bundle

Use the official guide for exact commands, and verify installed resource names
before converting them into GitOps.

The official setup path does not direct the demo to mutate generated Kuadrant
`AuthPolicy` or EnvoyFilter resources. Treat generated gateway-policy failures
as product compatibility or support-version issues unless Red Hat documentation
or support guidance provides a specific corrective change.

## MaaS Enablement And Dashboard Flags

Enable MaaS through `DataScienceCluster`:

- `spec.components.kserve.modelsAsService.managementState: Managed`

Use dashboard feature flags when the corresponding user/admin feature is
required:

- `modelAsService: true` for MaaS dashboard access
- `genAiStudio: true` when user-facing Gen AI studio features are needed
- `maasAuthPolicies: true` for administration of authorization policies
- `observabilityDashboard: true` when the MaaS observability dashboard is used
- the vLLM MaaS feature flag when vLLM runtime support is used with MaaS

Enable `llamastackoperator` only when Gen AI studio/Llama Stack functionality
is actually part of the MaaS-facing workflow.

## Publishing Models

Publish local or external models by creating a `MaaSModelRef`.

For locally served vLLM or llm-d models, the official guide uses
`kind: LLMInferenceService` inside `spec.modelRef`.

For external providers, create an `ExternalModel` and reference it from a
`MaaSModelRef` with `kind: ExternalModel`. The external model route uses
MaaS API keys for user access and a provider API key stored in a Secret for
provider-side authentication.

If `endpointOverride` is used on a `MaaSModelRef`, verify it with the installed
CRD schema before committing.

## Subscriptions

`MaaSSubscription` resources define which users or groups have quota for which
models. Each model in a subscription needs at least one token rate limit.

Priority controls which subscription applies when a user matches multiple
subscriptions for the same model. Higher priority numbers take precedence.
Use metering metadata on authorization policies when the demo needs showback,
cost-center, or organization attribution.

The subscription resource name is immutable. Treat renames as delete and
recreate operations and document access impact.

Deleting a subscription removes the corresponding quota. Users retain access
only if another subscription and authorization policy still cover them.

## Authorization Policies

`MaaSAuthPolicy` resources authorize users or groups to reach MaaS model
endpoints through the API gateway. They do not provide quota.

Keep authorization policy subjects aligned with subscriptions. If a
subscription changes, update any corresponding auth policy intentionally.

Removing a group from an auth policy revokes gateway access for that group and
can produce `403 Forbidden`. Deleting an auth policy revokes gateway access
even if a subscription still exists.

When a user is removed from a group and immediate revocation is required,
revoke that user's existing MaaS API keys because key-time group membership can
continue to influence access until keys are recreated.

## API Keys

Administrators can create and manage API keys for users. Users can create,
list, and revoke their own keys for subscriptions they can access.

Important lifecycle rules:

- user-created keys use the `sk-oai-` prefix
- plaintext keys are displayed only once at creation time
- default key expiration is 30 days in the user workflow
- users can select 1 to 365 days, but the `Tenant` max expiration constrains
  the allowed value
- if no tenant max is set, the default maximum is 90 days
- group membership is captured when the API key is created
- revoke and recreate keys after group membership changes when access must be
  updated immediately

Use an approved secret store for persistent client API keys. Do not put API
keys into notebooks, manifests, or repository files.

## MaaS API And Inference Endpoints

The guide documents these MaaS API endpoints:

- `GET /maas-api/health`
- `GET /maas-api/v1/models`
- `POST /maas-api/v1/api-keys`
- `POST /maas-api/v1/api-keys/search`
- `GET /maas-api/v1/api-keys/{id}`
- `DELETE /maas-api/v1/api-keys/{id}`
- `POST /maas-api/v1/api-keys/bulk-revoke`
- `GET /maas-api/v1/subscriptions`
- `GET /maas-api/v1/model/{model-id}/subscriptions`

MaaS inference uses OpenAI-compatible paths:

- `POST /llm/{model-name}/v1/completions`
- `POST /llm/{model-name}/v1/chat/completions`
- `POST /llm/{model-name}/v1/embeddings`

Use `Authorization: Bearer <maas-api-key>` for API and inference calls.

## Observability

MaaS observability covers subscription-level token consumption, request counts,
and rate-limit violations. It supports internal usage tracking and showback,
not billing-grade external invoicing.

The documented observability path requires:

- User Workload Monitoring
- Kuadrant observability enabled
- `Tenant.spec.telemetry.enabled: true`
- telemetry metric capture settings appropriate for the demo privacy posture
- dashboard observability flag enabled when using the product dashboard

Prometheus metrics include rate-limiting and authorized-call signals. Usage
data can be exported for cost attribution.

## External OIDC

External OIDC authentication for MaaS lets users access MaaS without OpenShift
accounts. Access still depends on group-based policy, subscriptions,
authorization policies, and API key lifecycle.

External OIDC users create API keys through the MaaS API/curl path, not the
OpenShift AI dashboard.

## External Models

External models route inference requests to providers such as OpenAI,
Anthropic, AWS Bedrock, Azure OpenAI, or Google Vertex AI through the MaaS
gateway.

Use two-tier authentication:

- users authenticate to MaaS with a MaaS API key
- MaaS authenticates to the provider with a provider API key stored in a Secret

Provider-level limits are shared by all MaaS users routed through that
provider key. MaaS subscription limits do not prevent the external provider
key from hitting its own aggregate limit.

When an `ExternalModel` is created, the MaaS controller creates networking
resources for external provider routing. If routing fails, verify the generated
`Service`, `HTTPRoute`, `ServiceEntry`, and `DestinationRule` resources in the
model namespace.

## User Workflow

Users find MaaS-published models in Gen AI studio -> AI asset endpoints when
they have matching subscription and authorization policy access.

The published endpoint dialog provides:

- the MaaS badge
- the API endpoint URL
- subscription selection
- temporary API key generation
- link to the API keys page

Users can test models from a notebook, through curl, or in the Gen AI
playground. Keep notebooks free of persistent secrets.

## Troubleshooting Signals

Use these official diagnostic areas:

- MaaS component enablement and `Tenant` readiness
- dashboard visibility flags
- model visibility and `MaaSModelRef`
- `403 Forbidden` from missing auth policy, stale groups, or no quota
- subscription access-control mismatches
- subscription management failures and failed phases
- `401 Unauthorized` from missing, expired, revoked, or malformed API keys
- `404` model-not-found from unavailable model refs or missing access
- token-limit responses from exceeded quota
- persistent token-limit errors from subscription or priority problems

Prefer readonly `oc get`, `oc describe`, jsonpath checks, and controller logs
before mutation.
