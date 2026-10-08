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
| Deploy agents | 060 | Partial | Both standalone agents, real workspace lifecycle/authorization, bounded task verification; catalog integration |
| MCP servers | 040/060 | Partial | Preserve current endpoint; native lifecycle and authenticated read-only tool plus foreign/write denial |
| MCP registry | 030/060 | Native metadata qualified; endpoint publication pending | Project editors can read/update their own registry metadata under native edit authority; known foreign record/version/write access is denied. Original native RBAC is preserved; endpoint publication, UI enablement and redeploy persistence remain required |
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
