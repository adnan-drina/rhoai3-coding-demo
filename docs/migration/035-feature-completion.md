# RHOAI 3.5 feature completion

This tracker records configuration and acceptance separately. The user authorized scoped implementation and bounded validation on 2026-10-08. A ready Pod, enabled flag or completed audit does not close an entry. AutoRAG and AutoML remain excluded. Native owners and retained data must survive reconciliation; existing GPU/model capacity must not be expanded.

| Entry | Owner | Status | Required exit evidence |
|---|---|---|---|
| Roles | 010 | Qualified: native defaults and authorization | Native role-management defaults retained; genuine administrator project-role authority and ordinary-developer/cluster-escalation denial verified. Custom roles are optional; browser rendering is separate |
| Connection test | 010 | Qualified: native API and storage | Models/Workbench and retained connection passed verified-TLS developer tests with valid/invalid credentials; repeat reconciliation and UID/data checks passed. Browser rendering and actual Workbench mounting remain separate consumption checks |
| External models | 040 | MiniMax qualified; GPT entitlement pending | Governed MiniMax JSON completion and revoked-key denial passed. Native registration and provider TLS/auth references retained; GPT credit availability and functional acceptance remain separate |
| MaaS settings | 040 | Streaming and external JSON qualified; local JSON blocked | Bounded governed SSE text/terminal marker and MiniMax JSON passed with key revocation; local Qwen non-streaming HTTP200 still has no body. Full OpenCode integration, broader governance acceptance and a supported local non-streaming remedy remain required |
| llm-d routing configurations | 040 | Pending implementation | Native reusable single-node router appears and reconciles; effective scheduler/baseRefs verified |
| llm-d topology configurations | 040 | Pending implementation | Native single-node topology configuration works with current hardware; unsupported costly topologies stay unavailable |
| LLM accelerator configurations | 040 | Pending qualification | Existing available templates, compatible NVIDIA selection and support annotations verified; no new capacity |
| Tool calling | 030/040/060 | Pending qualification | Catalog/parser metadata and bounded real read-only tool/result loop; forbidden tool denied |
| Agent Catalog | 030/060 | Discovery qualified; agent task gates pending | Both genuine personas read default/custom cards and launch instructions; standalone Hermes/model tasks remain separate runtime exits |
| Deploy agents | 060 | Developer Preview console discovery qualified; runtime tasks paused | Persistent agentOps flag; genuine dashboard API own-workspace typed empty list and foreign-workspace denial passed. Sandbox creation/update/deletion remain denied; authenticated OpenShell CLI owns launch/lifecycle. Positive instance detail, both standalone agents and bounded agent tasks remain separate exits |
| MCP servers | 040/060 | Native catalog deployment and caller-auth protocol qualified; governed consumer pending | Catalog OpenShift MCP Server 0.4 runs through the native operator with a pinned Red Hat artifact and 13 read-only core/config tools. Both personas read their permitted project; foreign, write, Secret and missing/invalid-token requests were denied. Verified HTTPS edge, redirect, current native image/ownership and unprivileged server service account passed. Old Stage 040 endpoint and consumer remain unchanged; Studio/governed endpoint integration is pending |
| MCP registry | 030/050/060 | Technology Preview metadata and qualified direct endpoint published | Both personas read the active native version, its 13 tool schemas and one verified HTTPS access endpoint through the existing MLflow Registry integration. Catalog provenance retains version 0.4; native strict-SemVer version is 0.4.0. Native project editor authority and prior known foreign-record denial remain qualified. Browser rendering and governed MCP endpoint integration remain separate |
| MCP catalog sources | 030 | Native API qualified | Administrator create/read/update/delete and developer denied writes/no change; default sources and customer ConfigMap identity preserved. Browser rendering is separate |
| Safety/security insights | 030 | Native no-result path qualified; positive data absent | Genuine developer received typed empty results; current packaged sources contain no positive security-scan metadata. Do not invent scan data or infer a disabled feature |
| AutoRAG | 010 | Excluded | Explicit disabled policy preserved; no backend deployment |
| Guardrails | 040/050 | Pending implementation | Native Studio configuration/auto-created controller resources; bounded safe/violation checks and ownership |
| Agent configuration management | 040 | Native API qualified | Base/variant save-load persistence and foreign-project denial passed with no model calls; browser rendering remains separate |
| Gen AI tracing | 010/040/050 | Native contract known; preservation pending | Existing Studio state must survive native reconfiguration; then qualify opt-in producer→collector→MLflow with a correlated trace, content policy and tenant isolation |
| Load prompts | 040/050 | Pending implementation | Native approved prompt/version and authorized load; persisted registry and variable handling |
| Global prompts: user | 040/050 | Pending implementation | Curated global prompt read, project-copy boundary and foreign write denial |
| Global prompts: administration | 040/050 | Configuration deployed; functional checks pending | Native single global workspace/label/read binding deployed; administrator-only curation and redeploy persistence qualification in progress |

## Integration sequence

### Targeted registry and AgentOps configuration — 2026-10-08

The [RHOAI 3.5 dashboard configuration procedure](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard) enables `mcpRegistry` (Technology Preview) and `agentOps` (Developer Preview) explicitly. Stage 030 owns registry visibility; Stage 050 supplies the native MLflow backend. A separate `agent-console` component owns only dashboard visibility and each persona's own-workspace Sandbox/Service read access. It does not change the gateway, operator, identities, runtime images or launch policy.

Both scoped components reconciled successfully and one repeat reconciliation retained their flags and authorization boundaries. Only four previously added redundant MCP metadata Roles/Bindings were pruned; original native project admin/edit grants remain. The genuine AgentOps dashboard API returned own-workspace empty lists and rejected foreign-workspace reads. Registry reads used its actual embedded MLflow service contract, not an invented dashboard BFF endpoint. Empty agent lists do not qualify positive instance details or generic wizard deployment. The console wizard does not route through authenticated OpenShell policy enforcement, so no human Sandbox write permissions were added.

Manual verification remains user-owned: **AI hub → MCP servers → Registry**, select the intended project; **AI hub → Agents → Deployments**, select the persona's own workspace. Launch agents through the authenticated OpenShell CLI. The broader paused evaluation, model, runtime-task, tracing, recovery and native MCP endpoint work was not resumed.

### Native MCP prerequisites and Register-action hold — 2026-10-08

The separate `mcp-platform` component now enables the [native RHOAI MCP Lifecycle Operator](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/enabling-mcp-lifecycle-management). Actual ownership is DataScienceCluster → native MCPLifecycleOperator component → current controller Deployment. The reviewed RHOAI 3.5.1 image and served `mcp.x-k8s.io/v1alpha1` API are ready. Both genuine personas received native catalog availability and typed empty deployment lists. This establishes prerequisites, not a deployed or registered tool endpoint.

The adjacent catalog **Register MCP server** action is absent from the selected RHOAI 3.5.1 host/model-registry and separately deployed MLflow federation module; it is not repaired by another feature-flag change. The actual MLflow module is bound to [source revision 569409a](https://github.com/red-hat-data-services/odh-dashboard/tree/569409addd97818d9c4b7aac4760f14401d565b0). The configured 3.5 channel currently offers the same installed 3.5.1 bundle. The offered 3.6 Early Access 1 bundle's coherent host/model-registry/MLflow images contain the [Register integration](https://github.com/opendatahub-io/odh-dashboard/pull/9190); that is published source/artifact evidence, not live qualification or upgrade approval. Individual image or UI patches were not applied.

At that earlier checkpoint, the user prioritized the native Register action before catalog deployment. Existing MCP runtime and Studio discovery remained unchanged; no catalog metadata, access endpoint or replacement MCPServer had been created. Runtime deletion, registration and deployment were held pending the whole-platform version/preservation decision. The accepted HTTPS-edge/internal-HTTP boundary did not authorize a platform upgrade or shared service-account tool authority.

### Catalog server registration and deployment — 2026-10-08

The user chose to stay on RHOAI 3.5.1 and authorized native API registration despite the absent catalog Register action. The actual packaged `rh_mcp_servers` catalog entry is OpenShift MCP Server 0.4. Its Red Hat image is pinned to index `855466299c3178f7d9f96a1511005ca6161b8cc6b294df9907c234ce8ecfd0f2`, with actual Ready Pod amd64 image `506a127d725c6d0cbff11a9616775e5b499bcf68276b83971cff2ac81596758a`; both are bound to [source 3ba1f65](https://github.com/openshift/openshift-mcp-server/tree/3ba1f65aca7a8a23dc3744a57f3723d4a7699772).

Native Registry metadata was created before deployment, using the explicitly local reverse-DNS identity `io.github.openshift/openshift-mcp-server`. Catalog version `0.4` is retained in full JSON provenance; Registry version `0.4.0` satisfies its strict semantic-version contract. Its bounded source field carries a compact catalog/source reference, while full provenance resides in `server_json._meta`. An HTTPS access endpoint and active status were published only after current runtime/protocol acceptance. Independent genuine-persona reads confirmed the native Deployment, active version, full 13-tool inventory and exact endpoint.

One repeat Application reconciliation retained current policy, ownership and actual runtime image. Final native Registry repeat publication accepted the same owned record/version/endpoint without creation or activation writes. The helper compares immutable endpoint fields separately from the native API's computed version/tool enrichment and rejects foreign or changed content.

The customer policy keeps the catalog's read-only core/config toolsets, explicitly denies Secret resources and requires each request's OpenShift bearer token. Image-bound source clears bootstrap authentication from the derived request client; the server service account has no pod, Secret or workload write authority. Both personas' allowed reads and foreign/write/Secret negatives passed, as did missing/invalid bearer rejection, alternating callers, HTTPS verification and HTTP redirect. The accepted boundary remains HTTPS at ingress and HTTP with bearer tokens inside the cluster; the operator's ingress rule permits cluster peers. No end-to-end TLS or MaaS-key authorization is claimed.

The old MCP runtime and Studio discovery entry remain intact. The newly requested governed MCP endpoint is under separate native integration assessment; Studio's additive discovery entry and per-session Authorize proof are held to avoid a second endpoint cutover. No model calls, platform upgrade, OGX reconfiguration or old-server deletion occurred. Broader paused feature gates remain paused.

1. Qualify the additive Models/Workbench storage component and repair the existing connection writer without touching retained buckets or core foundation source.
2. Review and deploy Stage040 shared visibility/configuration and native serving fixes. Resolve the governed empty response before model-backed agent acceptance.
3. Review and deploy Stage050 evaluation visibility, prompt/global workspace and verified tracing integration.
4. Review and deploy Stage060 agent/MCP work after catalog contracts and shared prerequisites are established.

Code preparation may proceed in parallel with disjoint file ownership. Shared DSC/dashboard fields, delegation, commits and deployment remain serialized. Each slice requires source review, narrow offline checks, guarded positive/negative functional acceptance and repeated-reconciliation preservation. Browser rendering is user-owned.

## Evidence baseline

The read-only audit identified missing implementation beyond dashboard flags. Genuine OpenShell personas and the PR4150 host capability passed; model-backed OpenCode qualification remains blocked by a governed HTTP200 empty body, while a verified-TLS direct backend request succeeded. The cause is not established. Existing native recovery backups are retained. No audit proposed a generated-operand patch, anonymous gateway, security relaxation or external hosting.

Evidence links and statuses will be updated only after the corresponding acceptance actually runs. Private receipts and credentials remain outside Git.

## Connection credential annotation exception

Native repeated reconciliation demonstrated that client-side apply with `RespectIgnoreDifferences` copied runtime connection data into `kubectl.kubernetes.io/last-applied-configuration`. The initial credential-free skeleton annotation was harmless; the later serialized runtime data was not. Only the two connection Secret skeletons therefore opt into `ServerSideApply=true`, and their component uses `ClientSideApplyMigration=false` as supported by Argo CD 3.4.7. This is a narrowly scoped credential-handling exception, not a change to repository-wide apply policy. No Replace or global SSA is enabled. Existing annotation removal requires exact component tracking, UID/resourceVersion tests and same-data readback; subsequent native reconciliation must retain Secret/claim UIDs and credential hashes without recreating the annotation.

## Connection acceptance: 2026-10-08

The additive storage component reconciled successfully with the scoped apply exception. Both new connections passed native bucket binding, generated-resource ownership, credential mapping and metadata validation. UID/resourceVersion/data-tested annotation removal preserved the connection data. A completed second reconciliation followed by an independent read confirmed that the credential annotation did not return. The retained connection received only a protocol metadata repair and annotation removal; its Secret UID, credential bytes and original bucket claim UID/spec were unchanged.

Using the genuine developer identity and verified native service TLS, the dashboard connection-test API passed a read-only S3 bucket check for Models, Workbench and the retained connection. Each deliberately invalid credential returned an unsuccessful result. The owned diagnostic forward was closed. These are native API/storage checks; they do not claim browser rendering or an actual Workbench mount.

Genuine administrator and developer native authorization checks also qualified the existing project-role boundary. The administrator can manage project roles and bindings; the developer can use project workloads but cannot administer roles/bindings. Both identities are denied cluster-role-binding creation. The installed dashboard source defaults role management and project RBAC to enabled; the CR intentionally does not restate those defaults. No new custom role or privilege grant was required.

## Governed response comparison: 2026-10-08

Two bounded requests distinguished the native response paths. The non-streaming request returned HTTP200 with JSON content type and chunked transfer, but no body. The streaming counterpart returned four valid SSE records, assistant text and a terminal marker. Both short-lived owned keys were revoked and rejected afterwards. This qualifies the bounded governed streaming path, not full OpenCode generation/cancellation or normal JSON completion. Processor framing remains under investigation; an upstream passthrough issue is relevant evidence, not a proven diagnosis or permission to patch generated gateway configuration.

A bounded governed MiniMax comparison returned a valid JSON chat completion with eight completion tokens. The short-lived key was revoked and rejected afterwards. The empty-body defect is therefore not universal to non-streaming MaaS requests; local Qwen remains blocked. MiniMax success does not establish GPT entitlement or acceptance.

## Shared configuration rollout: 2026-10-08

The catalog, MaaS/Studio and evaluation slices reconciled serially. Both genuine personas can read the retained default and custom coding-agent catalog cards. The native source-administration API passed a disposable source lifecycle and denied developer writes without changing source data. Evaluation and global-prompt flags, the shared MLflow curated workspace, native TLS/database/artifact configuration and authenticated EvalHub health/providers/collections passed. A completed real evaluation, Studio recreation/tracing and prompt consumer acceptance remain independent gates.
