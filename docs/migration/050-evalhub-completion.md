# EvalHub workflows and configuration — completion record

This stage uses the existing `evalhub` service and `demo-sandbox` tenant. Loading
provider/collection catalogs does not run benchmarks. A small real run qualifies
the platform; it does not establish full-suite model quality or coding-agent
success. AutoRAG and AutoML remain excluded.

The requested [3.4 evaluation guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/evaluating_ai_systems/index)
is mapped below to the installed-version [3.5 guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index).
The 3.5 guide adds local mode, Kueue, PVC datasets, dashboard comparisons and
native coding-agent MCP/skills integration. API examples must be checked against
the installed OpenAPI: its collection/job benchmark field is `id`, while some
documentation examples use `benchmark_id`.

Source identities: EvalHub `90648741f29f5421f24601d8b2c32909852bc365`, TrustyAI
Operator `e43cdff198b90289167f2d7cd5678821b21d8643`, and LM Evaluation Harness
adapter `7b2e4ad17c3d1b5d6b1286dfd68cffbd079fe90d`, from Red Hat image provenance.
Operator-owned workloads/configuration must not be patched directly.

## Requested chapter coverage

`Foundation` means configuration and existing service checks, not a completed
evaluation. `Prepared` means source awaits publication/deployment and native
functional evidence. Other rows are explicit remaining exits, not completion.

| 3.4 section | 3.5 equivalent | Required contract / current coverage | Acceptance still required |
|---|---|---|---|
| 2.1 Concepts | 2.1 | Jobs, providers, benchmarks, collections and weighted thresholds; documented | A real bounded result with score/threshold interpretation; sample 0.6 is a demonstration threshold, not a coding release criterion |
| 2.2 Architecture | 2.2 | Native tenant Jobs, credential-protecting sidecar, PostgreSQL; foundation | Verify actual Job containers, tenant and sidecar callbacks |
| 2.3 Deployment | 2.3 | Managed TrustyAI, native v1 EvalHub CR, retained PostgreSQL and service TLS; foundation | Reconcile selected catalogs, preserve database identity |
| 2.4 SDK / CLI | 2.4 | Python >=3.11, native client/CLI, protected identity and tenant configuration | Pin compatible SDK; health/discovery and job read through SDK/CLI |
| 2.5 Multi-tenancy | 2.7 | `X-Tenant`, TokenReview and resource-specific SAR; existing tenant Role | Persona positive and foreign-tenant negative native API checks |
| 2.6 Providers / benchmarks | 2.9 | All nine verified native provider catalogs prepared | Verify actual IDs, image pins and benchmark parameters after reconciliation |
| 2.7 Submit job | 2.10 | Explicit endpoint identity, protected auth reference and bounded parameters | Two-example real run, one concurrent benchmark, bounded output/time |
| 2.8 Track/results | 2.11 | Existing read-only verifier can correlate native job and MLflow run | Completed job/events/metrics; repeat-read after service reconciliation |
| 2.9 Cancel/delete | 2.12 | Native DELETE cancels; `hard_delete=true` is permanent | Own disposable job cancellation and deletion, retained result unaffected |
| 2.10 Built-in collections | 2.13 | All nine verified native collection catalogs prepared | Browse definitions; do not silently execute full collection |
| 2.11 Custom collection | 2.14 | `evalhub-workflows.py` creates/loads a retained two-example IFEval definition | Native persona create/read, repeat-run refusal on incompatible existing data |
| 2.12 API-key auth | 2.15 | Tenant Secret `api-key`, model `auth.secret_ref` | Governed endpoint request through native sidecar; no adapter-visible raw key |
| 2.13 SA model auth | 2.16 | Alternative for KServe RBAC-protected endpoint, with explicit model grant | Qualify only if selected endpoint supports this mechanism; no MaaS bypass |
| 2.14 S3 datasets | 2.17 | Public/synthetic fixture in existing bucket, dedicated prefix and protected refs | Init download, fixture checksum and adapter consumption; no new bucket |
| 2.15 OCI export | 2.19 | OCI registry destination plus tenant dockerconfigjson reference | Own export digest, authenticated pull/read and retention; registry auth first |
| 2.16 MLflow | 2.20 | Existing TLS URI, operator CA/projected token and retained MLflow storage | Exact experiment/run metrics/artifact read; tenant access and isolation |
| 2.17 Provider API | 2.21 | Native custom provider registry; reviewed existing adapter may be reused | Own registration/read/update/delete metadata without changing built-ins |
| 2.18 Provider ConfigMap | 2.22 | Operator loads referenced customer provider configuration | One reviewed native configuration import; pinned image, CPU limits |
| 2.19 Collection ConfigMap | 2.23 | Operator loads referenced collection configuration | One bounded customer collection import and authoritative API read |
| 2.20 SDK adapter | 2.24 | Optional extension; not required to duplicate working native harness | Review interface/example; build/run only for an actual unmet demo task |
| 2.21 API reference | 2.25 | Installed OpenAPI governs resource/list/status schemas | Health, catalogs, own CRUD and lifecycle status contracts exercised |
| 2.22 Configuration | 2.26 | CR/database/MLflow configured; operator owns generated config | Effective safe fields match authored CR; persistent database remains same |
| 2.23 RBAC isolation | 2.27 | Tenant SQL filtering, namespace Jobs and native SAR | Positive persona + forbidden foreign read/write; no guessed custom role |
| 2.24 Tenant namespace | 2.28 | Existing namespace tenant label and native job identity | Operator job SA/status-event grant and network path verified |
| 2.25 Access grants | 2.29 | Existing project groups bind evaluation virtual resources | ai-developer evaluation creation and allowed results; unrelated user denial |
| 2.26 Roles | 2.30 | Native view/evaluator/admin/integration roles have distinct purposes | Compare actual granted verbs to chosen workflow; sidecar cannot administer |
| 2.27 Resources | 2.31 | Follow exact installed source/doc references | Keep image/schema/SDK provenance with sanitized receipts |

## Additional applicable 3.5 exits

| Capability | Scope and acceptance |
|---|---|
| Local mode, 2.5–2.6 | Optional workstation development alternative; not a replacement for native tenant Jobs. No extra server deployment required. |
| Kueue, 2.8 | Technology Preview scheduling option. Qualify only with an intentionally selected existing queue; not required for a tiny CPU adapter pilot. |
| PVC data, 2.18 | Alternative to S3. Existing retained test-data PVC only; explicit claim/subpath and read-only adapter mount. |
| Dashboard, chapter3 | Submit/view own evaluation; compare two compatible qualified runs. Browser confirmation is human-owned; backend IDs/results must be proven first. |
| Coding agents, chapter4 | Native EvalHub MCP tools/resources/prompts use explicit demo-sandbox delegated service identity with short-lived credentials; they do not impersonate downstream users. REST/SDK retain genuine caller identity. Coordinate registry ownership with Stage060. |
| MCP deployment | Exact installed operator resolves the pinned EvalHub server image, which includes `/app/evalhub-mcp`. Native proxy authenticates the inbound caller; the downstream token and tenant are explicitly delegated and fixed. Confirm effective image, named proxy access and delegated scope. |
| Agent metadata | Read native provider/benchmark/collection agent metadata; custom metadata only on owned registrations. No claim that discovery implies autonomous evaluation. |

## Boundaries and independent evidence

The existing harness adapter uses non-streaming text completions. A successful
streamed MaaS response does not qualify this path. Real evaluation execution
must wait for the governed non-streaming endpoint or an explicitly reviewed
native adapter alternative. Catalog and custom-collection qualification can
proceed without model calls.

Evaluation MLflow metrics/artifacts, EvalHub operational OTEL spans and Studio
prompt/response traces are separate evidence paths. Do not invent an MLflow
OTLP endpoint or equate collector readiness with captured evaluation content.
Optional providers, custom SDK adapters, local mode and storage alternatives
need explained availability and prerequisites; completeness does not require
running every framework or a costly benchmark sweep.

All qualification records must distinguish source/static checks, live service
readiness, actual API persistence and completed evaluation results. Retain
existing results and buckets. Cancel/delete only newly created disposable test
jobs, never unrelated evaluation history.
