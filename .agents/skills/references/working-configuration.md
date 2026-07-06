# Working Configuration And Design Decisions

Use this reference before changing or rebuilding the rhoai3-demo
Models-as-a-Service stage. It captures the configuration that was validated in
the live RHOAI 3.4 demo environment and the implementation traps discovered
during Stage 220.

## Validated Demo Configuration

Validated on `cluster-klvxt` for Stage 220 on 2026-06-12 and refreshed on
`cluster-xgg8t` during fresh-environment redeploy on 2026-06-29:

| Area | Working decision |
|------|------------------|
| RHOAI enablement | `DataScienceCluster.spec.components.kserve.managementState: Managed` and `spec.components.kserve.modelsAsService.managementState: Managed` |
| Gen AI dashboard path | `DataScienceCluster.spec.components.llamastackoperator.managementState: Managed` when Gen AI Studio, Playground, and AI asset endpoints are in scope |
| Dashboard flags | `modelAsService`, `vLLMDeploymentOnMaaS`, `genAiStudio`, `maasAuthPolicies`, and `observabilityDashboard` are enabled only when the stage validates those surfaces |
| MaaS API group | `maas.opendatahub.io/v1alpha1` for `Tenant`, `MaaSModelRef`, `ExternalModel`, `MaaSSubscription`, and `MaaSAuthPolicy` on the active RHOAI 3.4 cluster |
| Tenant namespace | `models-as-a-service` |
| Gateway | `maas-default-gateway` in `openshift-ingress`, with `opendatahub.io/managed: "false"` and `security.opendatahub.io/authorino-tls-bootstrap: "true"` |
| Gateway TLS | stable `maas-gateway-tls` Secret in `openshift-ingress`, generated from the active OpenShift ingress certificate by deploy automation |
| Connectivity Link | `rhcl-operator.v1.3.4`, manual InstallPlan approval, with the approval job accepting only the pinned CSV |
| Connectivity Link dependencies | GitOps-managed Authorino, DNS, and Limitador Subscriptions with manual approval and validated 1.3.x `startingCSV` values |
| Kuadrant and Authorino | `Kuadrant` and `Authorino` are managed in `kuadrant-system`; Authorino TLS and service CA trust are configured through GitOps |
| PostgreSQL | demo-local PostgreSQL 16 StatefulSet in `models-as-a-service-db`, outside the Kueue-managed MaaS model namespace |
| MaaS DB Secret | `maas-db-config` in `redhat-ods-applications`, with key `DB_CONNECTION_URL`; generated from local secrets and never committed; for this demo it must point to `maas-postgres.models-as-a-service-db.svc.cluster.local` |
| Local model backend | Nemotron `LLMInferenceService` in `models-as-a-service`, then `MaaSModelRef` in the same namespace with `spec.modelRef.kind: LLMInferenceService` |
| External OpenAI model | `ExternalModel.metadata.name: gpt-4o-mini`, `ExternalModel.spec.targetModel: gpt-4o-mini`, and matching `MaaSModelRef.metadata.name: gpt-4o-mini` |
| Provider credential | `openai-provider-api-key` Secret in `models-as-a-service`, with data key `api-key` and label `inference.networking.k8s.io/bbr-managed=true`; generated or copied by deploy automation, not committed |
| External GPT tool calling | `gpt-4o-mini` supports standard OpenAI-compatible Chat Completions function calling through the MaaS Gateway when called with a MaaS API key |
| Access policy | Users need both `MaaSSubscription` quota and `MaaSAuthPolicy` gateway authorization before model access is claimed |
| Developer access | `ai-developer` does not get direct namespace access to `models-as-a-service`; the user path is AI asset endpoints, MaaS API keys, and OpenAI-compatible MaaS endpoints |
| Admin access | `ai-admin` maps to `rhods-admins` and can administer the MaaS namespace and MaaS dashboard policy surfaces |
| Gen AI Playground | dashboard-created `LlamaStackDistribution` in `demo-sandbox`; validate product-generated model discovery and responses for Nemotron and external `gpt-4o-mini` before using any diagnostic repair helper |
| OpenShift MCP | read-only OpenShift MCP server in `rhoai-mcp`, discovered through `redhat-ods-applications/gen-ai-aa-mcp-servers` as `OpenShift-MCP`; config sets `read_only = true`, `list_output = "table"`, `toolsets = ["core", "config"]`, an `enabled_tools` allowlist for namespace-scoped pod, known-pod, and node inspection, and denies `Secret`, `ConfigMap`, and RBAC resources |

## Design Decisions

- Use the native RHOAI 3.4 MaaS `ExternalModel` path for OpenAI provider
  registration. Red Hat Developer LiteLLM examples can inform narrative and
  model selection, but they do not replace the product-documented MaaS CRs.
- For Stage 220 MCP context, use the newer OpenShift MCP server source and Red
  Hat preview guidance. Register it through the RHOAI Gen AI Playground MCP
  discovery ConfigMap, keep it read-only, keep sensitive resources denied, and
  allowlist only the small set of demo inspection tools. Use compact table
  output and namespace-scoped or known-resource tools; avoid cluster-wide
  namespace, pod, event, or log listing in the Stage 220 Playground path. Do
  not use MCP as a back door around MaaS model governance or OpenShift RBAC.
- Publish the local Nemotron model from `models-as-a-service`, not
  `demo-sandbox`. MaaS-published models must have the `MaaSModelRef` in the
  backend namespace, and the demo needs a clean separation between provider
  administration and user consumption.
- Remove stale direct Nemotron deployments from `demo-sandbox` during Stage
  220 deployment. A fresh environment might not have manual dashboard-created
  resources, but a reused environment often will.
- Keep PostgreSQL outside the Kueue-managed MaaS namespace. Kueue should manage
  model workloads, not long-lived support infrastructure with immutable
  workload labels.
- Restart `deployment/maas-api` after changing `maas-db-config` in a cluster
  where MaaS is already managed. CR readiness and model discovery can pass while
  API key storage still fails against an old database hostname until the API
  process reloads the configuration.
- The demo-local PostgreSQL connection uses an internal cluster service and
  `sslmode=disable`. Treat this as a demo exception only. For production-like
  MaaS guidance, follow the official database-secret posture with a managed
  PostgreSQL 14+ service and TLS-protected connection, typically
  `sslmode=require`.
- Treat generated Kuadrant resources as controller output. GitOps owns the
  source MaaS, Kuadrant, Authorino, Gateway, and RHCL configuration; it should
  not patch generated `AuthPolicy`, `TokenRateLimitPolicy`, or `EnvoyFilter`
  resources unless official Red Hat documentation or support guidance requires
  that exact change.
- Treat dashboard-created Gen AI Playground resources as product-generated
  project resources that still need validation. MaaS CR readiness, dashboard
  model listing, and direct MaaS inference do not prove the Llama Stack
  playground can use the models.
- Treat dashboard model-selection changes as Playground regeneration events.
  Checking or unchecking a MaaS model can recreate the project
  `LlamaStackDistribution`, ConfigMap, and generated deployment. Revalidate
  the product-generated model list and response path after each regeneration.
- Pin RHCL until the end-to-end RHOAI/RHCL/Gateway path is validated on a
  newer CSV. Automatic operator upgrades are normal for many demo components,
  but MaaS Gateway policy generation is a compatibility boundary. On the
  active baseline, use `rhcl-operator.v1.3.4` as the latest supported 1.3.z
  compatibility hold because RHCL 1.4.0 is deprecated in the official release
  notes.
- Do not approve RHCL dependency upgrades just because OLM offers them. RHCL,
  Authorino, DNS, and Limitador must be represented as GitOps-owned
  Subscriptions with manual approval and pinned `startingCSV` values on the
  active baseline. On `cluster-xgg8t`, RHCL `1.3.4` installed cleanly, but the
  combined dependency plan for DNS Operator `1.3.1`, Service Mesh `3.3.5`, and
  Authorino CRD changes failed because existing generated MaaS `AuthConfig`
  resources did not validate against the stricter Authorino schema. Treat this
  as an operator compatibility boundary and rerun full MaaS validation before
  accepting any newer dependency set.
- Enable `Tenant.spec.telemetry.metrics.captureUser` only as an explicit demo
  choice. The official guide defaults user capture off for privacy and
  cardinality reasons.

## Traps That Delayed Stage 220

- The official RHOAI 3.4 MaaS guide contains an API group inconsistency: the
  verification sections list `*.maas.opendatahub.io` CRDs, while some YAML
  examples use `models.opendatahub.io/v1alpha1`. The installed CRD schema is
  authoritative for GitOps authoring on the target cluster.
- Dotted external model IDs are not safe Kubernetes resource names. The MaaS
  controller creates Kubernetes networking resources from the `ExternalModel`
  name, so prefer an upstream model ID that is already DNS-safe for
  Playground-facing demos. If the upstream ID is not DNS-safe, use a DNS-safe
  resource alias and keep the provider model ID in `spec.targetModel`.
- The AI asset endpoints MaaS tab displays the MaaS model resource id. For
  `gpt-4o-mini`, that resource id intentionally matches the upstream provider
  model ID, which avoids the Playground alias split that broke the previous
  dotted-name experiment. Confirm the target with
  `ExternalModel.spec.targetModel: gpt-4o-mini` and confirm Playground
  readiness through the Llama Stack and dashboard BFF model lists.
- MaaS dashboard visibility can fail even when CRs look ready. Validate the
  real dashboard API and Gateway API paths with demo user tokens.
- A subscription alone is not enough. A matching `MaaSAuthPolicy` is required;
  otherwise users can receive `403 Forbidden` even with quota.
- Dashboard and `/maas-api/v1/subscriptions` checks do not prove inference is
  ready. A complete MaaS validation creates a temporary `sk-oai-*` API key,
  calls the OpenAI-compatible Nemotron endpoint, calls the external OpenAI model
  endpoint, verifies token usage and structured tool-call output for both, and
  revokes the key.
- Raw OpenShift OAuth tokens are not the inference credential. They can be valid
  for discovery paths such as `/v1/models`, but `/v1/chat/completions` must use
  a MaaS API key for this demo policy.
- Dashboard-created Gen AI Playground Llama Stack deployments can contain
  placeholder MaaS tokens such as `fake`. That can make the UI load while model
  prompts receive `401 Unauthorized` from the MaaS Gateway. Bind the
  `LlamaStackDistribution` token env vars to a project Secret that contains a
  real MaaS API key, then validate `/v1/responses` from inside the Llama Stack
  pod.
- A recreated dashboard Playground can leave an existing project Secret and
  persistent MaaS API key behind. Before creating the replacement
  `genai-playground-<project>` key, search and revoke old active keys with the
  same name; then store only the newly issued key in the project Secret.
- The Llama Stack operator can fail to merge `valueFrom` Secret refs over
  existing literal placeholder env values in the generated deployment. If the
  `LlamaStackDistribution` is correct but the deployment still has literal
  token values, delete the generated deployment and let the operator recreate
  it from the corrected spec.
- Llama Stack registered model entries use `provider_model_id` for the provider
  target model ID in the validated RHOAI 3.4 demo environment. Do not use
  guessed fields such as `provider_resource_id` without checking the installed
  schema or product code path.
- For external OpenAI models whose API accepts the standard Chat Completions
  `max_tokens` field, the dashboard-generated Playground provider can remain
  on the product-generated MaaS route. If a future OpenAI model requires a
  different payload shape, validate the official RHOAI/Llama Stack path before
  adding any repair helper.
- For external models whose Kubernetes-safe MaaS resource alias differs from
  the provider target model, use the alias only in MaaS resource names and
  Gateway URL paths. For `gpt-4o-mini`, the MaaS resource name and provider
  target are intentionally identical.
- Llama Stack `/v1/models` exposes provider-qualified model IDs such as
  `maas-vllm-inference-2/gpt-4o-mini`; the generated provider number depends
  on dashboard model selection order, so use the IDs returned by `/v1/models`
  in Playground `/v1/responses` checks.
- If a diagnostic repair helper patches a project `LlamaStackDistribution`,
  preserve dashboard-created provider IDs. A browser session can keep sending
  an old provider-qualified model ID after the backend is corrected. Refresh
  the page or reselect the GPT model after repair.
- The durable validation gate is that dashboard
  `/gen-ai/api/v1/lsd/models?namespace=<project>` lists the external model as
  a selectable provider-qualified ID and `/gen-ai/api/v1/lsd/responses`
  succeeds with that listed model ID.
- MCP readiness requires more than the discovery ConfigMap. Validate from the
  project Llama Stack server that `/v1/responses` can receive an
  `mcp_list_tools` result from `OpenShift-MCP`. If the claim is model-driven
  tool use, require an actual `mcp_call`; otherwise present MCP as available
  context, not as a completed agent action.
- GPT tool calling and GPT MCP are separate validation gates. A direct MaaS
  Chat Completions request to `gpt-4o-mini` can return `tool_calls`, proving
  provider function-calling support, while a Playground MCP request can still
  fail if the MCP tool schema or tool result makes the external-provider
  request too large.
- If Llama Stack logs for `maas-vllm-inference-*/gpt-4o-mini` show
  `Request too large`, `rate_limit_exceeded`, or `tokens per min`, reduce the
  MCP tool selection, prompt, and output budget. Do not re-register the model
  or bypass MaaS unless model discovery or direct inference also fails.
- For the MaaS-published Nemotron model, do not leave the Playground vLLM
  provider default output budget at 4096 for MCP demos. MCP tool schemas and
  server instructions consume context; use a smaller default such as 512
  tokens even though the Stage 220 backend is served with a 131072-token
  context window for MCP headroom.
- External OpenAI requests for `gpt-4o-mini` use the standard
  `max_tokens` Chat Completions field.
- The real dashboard BFF path is a separate validation gate. Direct
  `http://127.0.0.1:8321/v1/responses` calls from the Llama Stack pod can pass
  while the Playground backend still fails because of auth-header shape or a
  stale provider-qualified model id. Validate the BFF with both
  `Authorization: Bearer <user-token>` and `x-forwarded-access-token:
  <user-token>`.
- If Playground MCP appears to hang or return no visible answer, inspect
  Llama Stack for context-length errors and inspect the MCP pod for OOMKills.
  The observed failure mode on the fresh environment was a combination of
  broad MCP tool-list context, a 4096-token vLLM output default, and an MCP pod
  memory limit that was too low for repeated tool-list requests.
- If external inference returns `provider 'openai' credentials not found`, check
  that the provider Secret has both data key `api-key` and label
  `inference.networking.k8s.io/bbr-managed=true`.
- If API key creation logs an old hostname such as
  `maas-postgres.models-as-a-service.svc.cluster.local`, the DB Secret and
  `maas-api` process are out of sync even when `maas-db-config` now contains
  the corrected `models-as-a-service-db` hostname.
- Generated Gateway resources can be stale after model renames or failed
  operator versions. Validate source CR status and functional user paths rather
  than relying on one generated `EnvoyFilter` name as a durable contract.
- A newer RHCL CSV can generate Gateway WASM configuration rejected by the
  OpenShift gateway Envoy. Fix the operator lifecycle boundary first instead of
  papering over generated-resource failures.
- A newer dependency InstallPlan can also fail before the new operators become
  active if existing generated Authorino `AuthConfig` resources do not validate
  against the incoming CRD schema. If OLM reports
  `InstallComponentFailed` for `authconfigs.authorino.kuadrant.io`, do not
  patch generated `AuthConfig` resources as the durable fix. Hold the working
  operator set, record the failed CSVs, and wait for Red Hat guidance or a
  validated replacement operator set.
- On the active RHOAI 3.4 build, the generated `maas-api-key-cleanup` CronJob
  can point to `http://maas-api:8080` while the generated `maas-api` Service
  and Deployment expose HTTPS on `8443`. The generated
  `maas-api-cleanup-restrict` NetworkPolicy can also restrict cleanup pods to
  the wrong port. If recurring cleanup Jobs fail with timeouts, verify the
  generated Service, CronJob, and NetworkPolicy before blaming RHCL. For live
  demo recovery, suspend the broken generated CronJob and create a clearly
  annotated replacement CronJob that calls
  `https://maas-api:8443/internal/v1/api-keys/cleanup` with `curl -k`; remove
  that replacement after Red Hat fixes the generated resources.
- Argo CD health for a manually pinned OLM `Subscription` can be misleading
  when newer InstallPlans remain unapproved. The meaningful gate is that
  `status.installedCSV` equals the pinned `spec.startingCSV`, plus CRD and
  functional validation.
- Legacy namespace labels matter. If an old `kueue-managed=true` label remains
  on a namespace, automation can re-add `kueue.openshift.io/managed=true` and
  mutate workloads unexpectedly.
- Argo CD sync waves can deadlock when a Service that needs endpoints is in an
  earlier wave than the workload that creates those endpoints. Keep
  `service/maas-postgres` and `statefulset/maas-postgres` in the same sync wave
  so Argo CD can create both before evaluating Service health.
- A fresh llm-d `LLMInferenceService` can take several minutes after MaaS
  policy resources are healthy because the generated router/scheduler
  deployment pulls the modelcar image, the inference scheduler image, and the
  tokenizer image on a non-GPU worker. Validation must wait for
  `LLMInferenceService.status.conditions[Ready=True]`, not only for model
  access through the Gateway. A transient registry `ImagePullBackOff` can
  recover on retry; inspect events before changing manifests.
- Stage 220 validation depends on multiple OpenShift API reads. If CRDs,
  Gateway hostnames, or `LLMInferenceService` readiness appear missing during
  validation but manual `oc get` checks show them healthy, treat that as a
  transient read first. Retry critical CRD and JSONPath reads, and derive the
  MaaS Gateway host from `MaaSModelRef.status.endpoint` if the Gateway listener
  hostname read is empty. Do not patch generated MaaS, Kuadrant, Gateway, or
  Llama Stack resources until retried checks and manual inspection show a real
  product-resource defect.
- Stage scope was broad: prerequisites, operator lifecycle, Gateway, DB,
  dashboard flags, local model, external model, subscriptions, auth policies,
  user RBAC, and validation all changed together. Future stages should split
  prerequisite enablement, model publication, and user experience validation
  unless the dependency chain forces one rollout.

## Required Regression Gates

Before declaring MaaS ready in a new or upgraded environment:

1. Confirm the active product baseline and rerun schema checks:

   ```bash
   oc api-resources | grep -i maas
   oc get crd tenants.maas.opendatahub.io \
     maasmodelrefs.maas.opendatahub.io \
     externalmodels.maas.opendatahub.io \
     maassubscriptions.maas.opendatahub.io \
     maasauthpolicies.maas.opendatahub.io
   oc explain maasmodelrefs.maas.opendatahub.io.spec
   oc explain externalmodels.maas.opendatahub.io.spec
   oc explain maassubscriptions.maas.opendatahub.io.spec
   oc explain maasauthpolicies.maas.opendatahub.io.spec
   oc explain tenants.maas.opendatahub.io.spec
   ```

2. Confirm RHCL compatibility and dependency holds:

   ```bash
   oc get subscription rhcl-operator -n openshift-operators \
     -o jsonpath='{.spec.installPlanApproval}{" "}{.spec.startingCSV}{" "}{.status.installedCSV}{"\n"}'
   oc get subscription -n openshift-operators \
     authorino-operator-stable-redhat-operators-openshift-marketplace \
     dns-operator-stable-redhat-operators-openshift-marketplace \
     limitador-operator-stable-redhat-operators-openshift-marketplace \
     -o custom-columns=NAME:.metadata.name,APPROVAL:.spec.installPlanApproval,STARTINGCSV:.spec.startingCSV,INSTALLED:.status.installedCSV
   ```

3. Confirm Kueue and database namespace separation:

   ```bash
   oc get namespace models-as-a-service -o jsonpath='{.metadata.labels.kueue\.openshift\.io/managed}{"\n"}'
   oc get namespace models-as-a-service-db -o jsonpath='{.metadata.labels.kueue\.openshift\.io/managed}{"\n"}'
   oc get statefulset maas-postgres -n models-as-a-service-db
   oc get secret maas-db-config -n redhat-ods-applications \
     -o jsonpath='{.data.DB_CONNECTION_URL}' | base64 -d
   ```

   The PostgreSQL Service and StatefulSet must be created in the same Argo CD
   sync wave to avoid waiting for Service endpoints before the StatefulSet
   exists.

4. Confirm model-publication and access-policy resources:

   ```bash
   oc get tenant,maasmodelref,externalmodel,maassubscription,maasauthpolicy -n models-as-a-service
   oc get authpolicy,tokenratelimitpolicy -n models-as-a-service
   ```

5. Confirm functional access with real users:

   - Dashboard AI asset endpoint listing as `ai-developer`.
   - Gateway `/maas-api/v1/subscriptions` as `ai-developer`.
   - Dashboard model listing from the MaaS project as `ai-admin`.
   - MaaS-local Nemotron `LLMInferenceService` `Ready=True`.
   - Temporary MaaS API key creation as `ai-developer`.
   - Nemotron `/v1/chat/completions` through the MaaS Gateway with the temporary
     `sk-oai-*` key, including structured tool-call output and token usage.
   - External OpenAI `/v1/chat/completions` through the MaaS Gateway with the
     same temporary `sk-oai-*` key, `max_tokens`, and token usage.
   - If a Gen AI Playground exists, Secret-backed Llama Stack MaaS tokens,
     provider/model mapping for Nemotron and external GPT, Llama Stack
     `/v1/models` discovery, and `/v1/responses` completions for both models.
   - Unauthenticated Nemotron inference returns `401`.
   - Temporary MaaS API key revocation.
   - An unauthorized subject receives a controlled denial.

6. Confirm no generated Gateway-policy rejection:

   ```bash
   oc logs -n openshift-ingress \
     -l gateway.networking.k8s.io/gateway-name=maas-default-gateway --since=10m
   oc logs -n redhat-ods-applications deploy/maas-api --since=10m
   ```

## Upgrade And Redeploy Notes

- Re-run the schema checks after every RHOAI, RHCL, OpenShift, Gateway API, or
  Kuadrant upgrade.
- Keep quickstarts and blogs as implementation evidence, not API authority.
- If the provider model ID changes, choose a DNS-safe Kubernetes alias first
  and then set the exact provider model ID in `ExternalModel.spec.targetModel`.
- If model, prompt, GPU shape, vLLM arguments, or provider limits change,
  re-run the Stage 210/220 benchmark and update MaaS token limits from measured
  behavior.
- After each live issue, add the reusable lesson here before closing the stage.
