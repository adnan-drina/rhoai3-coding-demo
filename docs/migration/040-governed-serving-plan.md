# Stage 040 governed serving and GenAI Studio plan

Status on 2026-10-05: implementation and review in progress; not deployed. No model weights have been downloaded, and no Stage 040 bucket has been created. Stage 030 is fully accepted, including the user's catalog checks. Native readiness and functional acceptance below remain live gates.

## Scope and current source

The historical audit covered 76 files (11 stage files and 65 GitOps files), plus the Application, and rendered 77 resources. That inventory is local ignored evidence in `/private/tmp/stage040-audit-20261005/`. The revised base currently renders 75 resources. Preserve two exclusive L40S workers and the original Qwen model choices, one GPU each. AutoRAG, AutoML, evaluation, time slicing, automatic scaling and additional GPUs are excluded. Basic GenAI Studio consumes these model endpoints; its dashboard-created project storage is native service state, not a second authored database.

The core Stage 010 Application remains at `882f327fb25dd047ca7144058b6cca46e693df3a` on the foundation-omit bridge. Its retained MLflow resources must remain unchanged until Stage 050's separate handoff. Stage 030 remains at `147b6208a694f1cfb38c6d15c165c28e8b776025`. Stage 040 never repoints either prerequisite Application.

## Native ownership and routing

Stage 040 patches only its delegated DSC fields: AIGateway Managed, modelsAsAService Managed, batchGateway Removed, and OGX Managed. The old `kserve.modelsAsService` transition is blocked by the served 3.5.1 schema. Dashboard flags are limited to native MaaS and GenAI Studio enablement. The separate guarded delegation helper merges exact ignore paths into the retained core Application using resourceVersion preconditions; it changes no source revision or retained resources. Fresh Stage 010 publishes the same delegation contract.

One Gateway has three HTTPS listeners: `maas.<apps-domain>` for the API/external models, `qwen3-6-maas.<apps-domain>` and `qwen3-8-maas.<apps-domain>` for the private models. Immutable Application Kustomize patches derive these hosts from guarded native ingress configuration. The API listener accepts routes only from `redhat-ai-gateway-infra` and project-owned `external-models`; model listeners accept only `models-as-a-service`. Each LLMInferenceService selects its listener using `sectionName`.

This route separation is the project's qualification candidate for INFERENG-6962, not an official claim that the issue is fixed. Generated route attachments, native Gateway-level governance and actual EPP scheduler behavior must be verified. A successful inference response alone does not establish EPP execution.

Native MaaS creates its default tenant and infrastructure namespace. Do not author a competing legacy Tenant/AITenant. Provider, ExternalModel, provider Secret and MaaSModelRef reside together in `external-models`. Governance policies stay in the default tenant namespace and refer to model namespaces explicitly. ModelRef `tenantRef` is `models-as-a-service`; explicit `endpointOverride` uses the API hostname because the shipped external handler otherwise selects the first Gateway listener.

## Artifact disposition

| Source family or entrypoint | Implemented disposition and ownership | Required exit |
|---|---|---|
| Application and base composition | Immutable reviewed revision, native ServerSideDiff, exact data/replica/registry-label ignores. Optional Slack/BrightData components inactive. | Published source equals reviewed checkout; successful native operation at exact revision/path. |
| RHCL prerequisites | Persistent Manual subscriptions: RHCL 1.4.3, Authorino 1.4.3, DNS 1.4.2, Limitador 1.4.2 and Service Mesh 3.4.2. Reuse existing global OperatorGroup. | Native owned InstallPlan family and selected CSVs verified; no deletion or CSV/operand patch. |
| LWS prerequisites | Manual stable-v1.0, leader-worker-set.v1.0.1, retained advanced-stack baseline. | Native availability; no multi-node workload implied by these single-GPU models. |
| Database | Existing project PostgreSQL identities, pinned Red Hat PG16 image, explicit 5Gi gp3 storage and retention. Namespace-scoped ingress policy. | Reuse credentials; reject partial storage/configuration; native current StatefulSet and Bound PVC. |
| Access | Existing intended project groups and service-account access retained. | Genuine persona access and negative authorization checks; no cluster-admin grant. |
| Gateway | One native Gateway, separate listeners, source-defined infrastructure resources. Credential-free TLS skeleton; exact native ingress certificate copied through UID/RV/tracking-bound stdin patch. | Accepted/Programmed listeners, verified TLS, secure route graph; no foreign namespace attachment. |
| Kuadrant/Authorino | Native customer CRs. Authorino TLS uses native service certificate; exact owner-bound hook requests only the documented Service annotation. Injected CA ConfigMap projects through native `spec.volumes` at `/etc/pki/tls/certs`, preserving the operator’s TLS certificate directory. | Current owned workload, populated CA/certificate, trusted Authorino-to-MaaS HTTPS. No Deployment env patch or insecure fallback. |
| Local models | Qwen 3.6 FP8 revision `57d986c3ab0397a811e5150190eff67f76fab6e0`; Qwen 3.8 INT4 revision `7fb3aaca2d21c0db4716572945208db40cef9966`. Native runtime, one GPU each. | Actual model load and bounded inference; historical fit measurements do not establish this runtime's capacity. |
| Tenant | Obsolete authored legacy Tenant removed; native bootstrap owns defaults. | Current native default tenant and API/database configuration. |
| External models | New native ExternalProvider/ExternalModel flow replaces GPT-4o Mini. GPT-6 Luna approved; exact ID available to configured account. | Governed bounded chat/tool-call/auth validation. Conditional Red Hat-hosted MiniMax requires native gateway incremental SSE plus usage proof before acceptance. |
| Policies | Personal policies refer to the new external namespace; private coding subscriptions preserve existing quotas/model identities. | Genuine key lifecycle, access denial and quota enforcement; native attached governance. |
| MCP | Required read-only OpenShift consumer endpoint preserved at `openshift-mcp.rhoai-mcp.svc:8080/mcp`; official upstream v0.0.67 image pinned to amd64 digest `604fa25a8c823da42cb86b6030a6249500317466db94bb2031e099f337b6a7d9`. | Streamable HTTP/tools compatibility and read-only RBAC. Upstream origin does not imply Red Hat product support. |
| Jobs | Named, bounded native configuration hooks; additive Console plugin patch and private certificate stdin patch. Old generated-controller restart/patch hooks removed. | Owner/RV failure tests and real native reconciliation; no unrelated plugin removal. |
| Monitoring | Native collection and dashboards retained; generated workload/PodMonitor patches removed. | Actual request/token/latency/DCGM signals; user visual checks separate. |
| Deploy/runtime helpers | Shared guard, ownership/data preflight, own immutable Application as first write, reviewed Manual InstallPlans and private credential reuse. | Fresh and retained paths safe; exact current native conditions and operation. |
| Registry/Studio helpers | Idempotent verified-TLS model-card registration; Studio helper provides native dashboard instructions and read-only readiness. | Real registry IDs; no historical benchmark assertions or generated playground patches. |
| Documentation/obsolete artifacts | Educational README updated; obsolete PLAN, old screenshots and unreferenced optional 35B variant removed. History remains in Git at `1a856bb`. | Current links/reference checks; no active consumer depends on retired files. |

RHCL 1.4 documentation supports OCP 4.22 with Service Mesh 3.3/3.4 and requires RHCL 1.4.1 or later. These selected catalog versions are authoring candidates until actual InstallPlan and served-schema qualification; they are not a claimed fixed Red Hat-tested tuple. `startingCSV` selects initial installation, not a permanent upgrade lock. Documented `AUTH_SERVICE_TIMEOUT=2s` belongs to RHCL's Subscription config, not an Authorino operand patch.

## Credentials, storage and protocols

Runtime credentials never enter Git, command arguments, annotations or logs. Database credentials are reused; a missing Secret with retained storage/configuration is a stop condition. The native MaaS DB connection Secret belongs in `redhat-ai-gateway-infra`; any old configuration must match before native migration. Plaintext PostgreSQL is an explicit namespace-scoped demo boundary, not a claim of database TLS.

Existing provider credentials are reused without rotation. A native-generated provider Secret is not invented from human-readable keys. The configured OpenAI account returned verified-HTTPS 200 for exact model ID `gpt-6-luna`; local evidence is `/private/tmp/stage040-gpt6-entitlement.json`. Chat Completions function calling requires `reasoning_effort=none`; Responses built-in tools are outside the native `openai-chat` registration.

Red Hat-hosted MiniMax is conditional. Direct upstream incremental SSE with `include_usage=true` passed a 64-token bounded probe; `/private/tmp/stage040-minimax-upstream-stream-usage.json` is not proof of the MaaS path. Native gateway streaming and final usage must pass without a non-streaming fallback.

No Stage 040 OBC is required for HF model sources or basic Studio. Preserve the generic sandbox bucket, shared storage consumers and accepted `rhoai-mlflow-artifacts` unchanged. No pipelines bucket and no destructive bucket replacement.

## Deployment and acceptance sequence

1. Independent source/render/schema and ownership/privacy fault checks, then selective publication excluding held Stage 010 drafts.
2. Guarded retention-safe core delegation, preserving core source and all unrelated ignore paths; verify readback.
3. Own Stage 040 Application first, reviewed native OLM approval, owned namespaces and safe runtime Secrets. A wave-7 metadata-only credential barrier precedes PostgreSQL/storage wave 8; the runtime helper supplies credentials, releases that barrier, then waits for the wave-14 native infrastructure namespace to supply the DB connection Secret. No retained-PVC exception permits rotation. Verify installed selected schemas before claiming qualification.
4. Native MaaS/Authorino/Gateway readiness, secure route graph, current database and operator conditions; then actual pinned model loading and legitimate registry registration.
5. Explicit bounded functional checks: genuine persona key creation, missing/invalid/unauthorized denial, local chat and incremental streaming, external tool-call/streaming compatibility when enabled, tiny quota proof, metrics and own-key revocation. Do not create benchmarks or evaluation workloads.
6. Native GenAI Studio enablement and endpoint discovery; the user creates and checks their project playground. Browser validation is exclusively user-owned. RAG remains unexercised.

Stop on a preservation, owner, schema, authorization or model-fit failure. Do not silently change models, contexts, topology or GPU capacity to produce a green result.

## Primary references

- [OpenShift AI 3.5 MaaS guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/index)
- [OpenShift AI 3.5 known issues](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/known-issues_relnotes)
- [RHCL 1.4 installation and supported platform](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/install_connectivity_link/rhcl-install-on-ocp)
- [Authorino native volume API](https://docs.kuadrant.io/1.0.x/authorino-operator/#volumesspec)
- [GPT-6 Luna API model](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [Pinned MCP source](https://github.com/containers/kubernetes-mcp-server/tree/v0.0.67)

Selected Authorino 1.4.3 native CRD evidence is local ignored `/private/tmp/stage040-authorino-bundle/`. Exact shipped RHOAI schemas and pinned MaaS/IPP sources are local ignored evidence under `/Users/adrina/Sandbox/rhoai3-coding-demo/tmp/platform-migration/schema-20261005/` and `/private/tmp/stage040-audit-20261005/`; they are not implementation-worktree relative paths or newly claimed live acceptance.

The injected outbound CA uses the Go/RHEL trust directory `/etc/pki/tls/certs`, preserving the native operator’s TLS certificate subPath at `/etc/ssl/certs/tls.crt`. Mounting the projected CA directory over `/etc/ssl/certs` prevented the new TLS pod from starting; the old plaintext pod remained available during the stalled rollout. Deployment validation now requires rollout completion. Runtime TLS and authenticated API checks remain acceptance gates. [Go Linux trust-directory source](https://go.dev/src/crypto/x509/root_linux.go).

### Conditional external qualification checkpoint

Both private Qwen models passed bounded governed completion, incremental SSE with usage, missing/invalid-key denial, and native vLLM traffic checks. Their temporary test key was revoked. GPT-6 Luna direct upstream returned `credit_balance_exhausted` / `insufficient_quota`; account credits must be restored before further GPT testing, with project quotas unchanged. MiniMax M2 on the existing Red Hat endpoint is registered initially with an ai-admin-only qualification policy and subscription. Normal personal/workspace model lists remain unchanged until governed incremental SSE, final usage, and key revocation pass. The private endpoint and credential come from existing local runtime inputs, never Git. EPP request processing, quota enforcement, and project Studio interaction remain separate acceptance gates.
