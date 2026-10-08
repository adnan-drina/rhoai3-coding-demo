# Stage 030 catalog integration — native 3.5.1 contract

Implementation slice; publication and live acceptance are coordinated with the
platform deployment owner. Existing registry data/default catalog sources stay
in place. Custom cards do not confer runtime support or authorize execution.

## Immutable native contracts

| Component | Installed source | Contract |
|---|---|---|
| Catalog backend | model-registry `efda7af48b15e63626f7dcd030c2dda23306da4c` | native customer `agent-catalog-sources` and `mcp-catalog-sources` ConfigMaps, `sources.yaml`; relative YAML paths resolve within the source CM mount |
| Dashboard/BFF | odh-dashboard `f4a81e89bf8a1fb0bbe3dfdc7b10eaa39b3d7439` | `/api/v1/agent_catalog/agents`, detail/artifacts; `/api/v1/mcp_catalog/mcp_servers`, detail/tools/converter; `/api/v1/settings/mcp_catalog/source_configs` admin source operations |
| MCP registry | MLflow `5a77fbe26b7fb022efbfec4eb6e1280984368a2b` | `/api/3.0/mlflow/mcp-servers`, version/access-endpoint CRUD, native SQL store and workspace authorization; embedded registry requires MLflow, MCP catalog and registry flags |
| MCP runtime | mcp-lifecycle-operator `cc66894be8cd87d35064e67ec02dbc6e5b5c3c89` | `mcp.x-k8s.io/v1alpha1 MCPServer`; customer CR owns native Deployment/Service/NetworkPolicy |

These pins are bound to installed Red Hat image catalog labels, not floating
upstream HEAD. MCP Registry support in the installed MLflow fork is present
despite upstream version-number differences; it is not inferred from 3.6 EA.

## Source ownership and data protection

Stage 030 retains the registry and catalog service. The native customer agent
source ConfigMap is currently unowned/untracked and contains an empty custom
list. Its adoption must require exactly that clean initial shape, or an exact
existing Stage 030 tracking identity; foreign ownership or additional custom
content is a pre-write blocker, not permission to overwrite it. Default sources
are never adopted, removed or replaced. The catalog process already mounts the
customer CM; no generated Deployment or metadata image patch is needed.

The two custom cards accurately describe OpenCode and Hermes. They expose no
credentials and do not publish a generic Sandbox launch template that bypasses
the hardened OpenShell gateway. Hermes remains clearly pending until its full
runtime gates pass; the card must be updated with actual qualified image and
launch instructions after that proof, not hidden from the accepted scope.

An existing discovery update requires the reconciled Stage030 Application and
ready native KServe/GPU installation, including every currently scheduled GPU
validator/exporter instance. It does not start deliberately parked capacity;
first-time installation retains the complete infrastructure prerequisite.

## Acceptance before this slice is complete

1. Render the native YAML source shape and validate the exact source/image pins.
2. Read back current catalog CM ownership and existing content before adoption.
3. Require both custom agent IDs and full README/artifact content through the
   genuine administrator and developer BFF sessions, while retaining every
   default source/card. Reject duplicate IDs, malformed source content and
   missing file references before publication.
4. Verify MCP source administration through the native BFF contract: admin
   mutation authorization and ordinary-user denial, without changing default
   sources. Custom MCP publication is optional; native default MCP metadata and
   tool inventories must remain usable.
5. Keep discovery and runtime evidence separate. Stage 030 owns native MCP registry metadata access and registration;
   Stage 050 supplies the retained MLflow backend. Stage 060 owns MCP server
   lifecycle and agent launch/lifecycle; Stage 040 owns
   parser-compatible governed model execution. Neither card presence nor a
   Ready condition completes those functional requirements.
6. Verify repeated sync preserves registry CR/namespace/native PVC and DB
   credential UIDs, default catalogs and the retained model records.

Relevant product procedures: [catalog discovery DP](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes),
[dashboard configuration](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard),
[native MCP lifecycle](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/enabling-mcp-lifecycle-management).

## MCP registry metadata authorization

The installed MLflow 3.14 product fork includes MCP registry APIs. Its pinned
Kubernetes authentication plugin maps MCP metadata operations to the virtual
`mlflow.kubeflow.org/mcpservers` resource. Native MLflow operator roles aggregate
metadata permissions into the existing OpenShift `admin` and `edit` roles.
The existing `rhods-admins-admin` and `rhoai-developers-edit` bindings therefore
allow the approved personas to manage metadata in `demo-sandbox`. Adding a
reader Role does not restrict those existing project-editor permissions.

Live qualification demonstrated administrator draft server/version creation,
developer own-project search/direct-ID/version reads and metadata update. An
isolated administrator-only namespace demonstrated developer filtered-empty
search and HTTP 403 for a known record, version and update. Both uniquely owned
fixtures were removed and existing project identities and roles preserved.
These are metadata permissions, not MCP runtime workload or tool permissions.
Global MCP catalog source administration remains a separate administrator
boundary: native admin create/read/update/delete passed and developer writes
left catalog data unchanged. Native write failures surfaced as server errors;
the update-denial receipt does not retain its exact numeric status.

Search filters unauthorized records and may return HTTP 200 with an empty
collection; known-record direct-ID/write tests establish the tenant boundary.
MCP REST `created_by` and `last_updated_by` were null in this backend; genuine
request identities were independently verified and must not be inferred from
those nullable metadata fields. Backend readiness, registry publication,
source administration and tool execution remain distinct acceptance checks.

## Safety and security insights: installed data boundary

The genuine developer can read the native safety-artifact API. Six existing
public default/validated model variants returned HTTP 200 with typed empty
artifact collections, qualifying the documented no-result path. No scan was
started and no security score was fabricated for the private Qwen models.

The active native YAML catalog provider is pinned to model-registry commit
`efda7af48b15e63626f7dcd030c2dda23306da4c`. It reads inline model artifacts from
its configured catalog YAMLs. All three installed default catalog files contain
zero `security-metrics` entries. Their native data images are:

- Metadata collection: `registry.redhat.io/rhoai/odh-model-metadata-collection-rhel9@sha256:85789e4e19c13df2644ae98dfcd6dbcf84a077c6e9c97a7ac7166a7fd571942b`.
- Performance data: `registry.redhat.io/rhoai/odh-model-performance-data-rhel9@sha256:15f2b8272db2d61d4a1b9c83690b9fa786fe8cb82a4728f97ed2b37311d83c7c`.

Configuration, authenticated API access and no-result handling are qualified;
positive published scan evidence is absent in this shipped dataset. This is a
data-coverage limit, not an authorization failure. A future positive test must
use a real published evaluation artifact with the documented customer catalog
format. Do not override a source arbitrarily, synthesize scores or infer the
private models' security from another model's precomputed result.
