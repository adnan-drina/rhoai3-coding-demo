# RHOAI 3.5 feature completion

This tracker records configuration and acceptance separately. The user authorized scoped implementation and bounded validation on 2026-10-08. A ready Pod, enabled flag or completed audit does not close an entry. AutoRAG and AutoML remain excluded. Native owners and retained data must survive reconciliation; existing GPU/model capacity must not be expanded.

| Entry | Owner | Status | Required exit evidence |
|---|---|---|---|
| Roles | 010 | Pending qualification | Existing default project roles and administrator assignment boundaries work; no unnecessary custom roles or escalation |
| Connection test | 010 | Pending implementation | Models/Workbench connections use native metadata; valid/invalid bounded tests; no credentials in annotations/logs; reconciliation preserves claims/data |
| External models | 040 | Pending completion | Native registration and UI/project visibility, provider TLS/auth references, governed positive/negative functional receipts |
| MaaS settings | 040 | Blocked functionally | Existing governance preserved; governed JSON and generated-token streaming work; own/foreign/key-revocation checks pass |
| llm-d routing configurations | 040 | Pending implementation | Native reusable single-node router appears and reconciles; effective scheduler/baseRefs verified |
| llm-d topology configurations | 040 | Pending implementation | Native single-node topology configuration works with current hardware; unsupported costly topologies stay unavailable |
| LLM accelerator configurations | 040 | Pending qualification | Existing available templates, compatible NVIDIA selection and support annotations verified; no new capacity |
| Tool calling | 030/040/060 | Pending qualification | Catalog/parser metadata and bounded real read-only tool/result loop; forbidden tool denied |
| Agent Catalog | 030/060 | Pending completion | Native source/schema and custom OpenCode/Hermes entries; authorized discovery and executable instructions |
| Deploy agents | 060 | Partial | Both standalone agents, real workspace lifecycle/authorization, bounded task verification; catalog integration |
| MCP servers | 040/060 | Partial | Preserve current endpoint; native lifecycle and authenticated read-only tool plus foreign/write denial |
| MCP registry | 030/060 | Unknown contract | Exact installed native API/store/schema; authorized registration/version/discovery/persistence |
| MCP catalog sources | 030 | Pending qualification | Native administrative source contract and validation; default sources retained; consumer access |
| Safety/security insights | 030 | Pending qualification | Packaged default-model metadata and legitimate no-result model verified under developer access |
| AutoRAG | 010 | Excluded | Explicit disabled policy preserved; no backend deployment |
| Guardrails | 040/050 | Pending implementation | Native Studio configuration/auto-created controller resources; bounded safe/violation checks and ownership |
| Agent configuration management | 040 | Pending implementation | Native save/load/variant/conflict persistence and project authorization; no credential storage |
| Gen AI tracing | 010/040/050 | Unknown integration | Documented opt-in producer→collector→MLflow path established with correlated trace, content policy and tenant isolation |
| Load prompts | 040/050 | Pending implementation | Native approved prompt/version and authorized load; persisted registry and variable handling |
| Global prompts: user | 040/050 | Pending implementation | Curated global prompt read, project-copy boundary and foreign write denial |
| Global prompts: administration | 040/050 | Pending implementation | Native single global workspace/label/read binding, administrator-only curation and redeploy persistence |

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
