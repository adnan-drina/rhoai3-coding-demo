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
5. Keep discovery and runtime evidence separate. Stage 060 owns MCP server
   lifecycle, registry registration and agent launch/lifecycle; Stage 040 owns
   parser-compatible governed model execution. Neither card presence nor a
   Ready condition completes those functional requirements.
6. Verify repeated sync preserves registry CR/namespace/native PVC and DB
   credential UIDs, default catalogs and the retained model records.

Relevant product procedures: [catalog discovery DP](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes),
[dashboard configuration](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard),
[native MCP lifecycle](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/enabling-mcp-lifecycle-management).
