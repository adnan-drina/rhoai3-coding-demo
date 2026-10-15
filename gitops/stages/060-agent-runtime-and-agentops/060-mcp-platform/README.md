# MCP platform (`060-mcp-platform`)

This Application turns on the OpenShift AI MCP Lifecycle Operator. A Sync hook Job sets the `mcplifecycleoperator`
component of the shared DataScienceCluster to `Managed`; the RHOAI operator then deploys the lifecycle operator and
serves the `MCPServer` API (`mcp.x-k8s.io/v1alpha1`). It deploys no MCP server itself. `060-agent-tools` consumes the
API to run the OpenShift MCP servers.

| | |
|---|---|
| Argo CD Application | `060-mcp-platform` ([manifest](../../../applications/060-mcp-platform.yaml)) |
| Deployed by | [`stages/060-agent-runtime-and-agentops/deploy-mcp-platform.sh [--revision REF]`](../../../../stages/060-agent-runtime-and-agentops/deploy-mcp-platform.sh) (own deploy script) |
| Validated by | [`stages/060-agent-runtime-and-agentops/validate-mcp-platform.sh`](../../../../stages/060-agent-runtime-and-agentops/validate-mcp-platform.sh) (Application at its pinned revision; DSC component `Managed`; `MCPLifecycleOperatorReady`; component CR owned by the DSC and Ready; one operator Deployment owned by the component, ready, running the image in `operator-source.json`; CRD `mcpservers.mcp.x-k8s.io` established and serving `v1alpha1`) |
| Sync | Manual (documented exception in `.agents/rules/gitops.md`). The script pins it to the selected published SHA and starts a hook-strategy sync through `scripts/shared/stage_apps.py`. Sync option `RespectIgnoreDifferences=true`. |
| Depends on | `010-rhoai-platform`: owns DSC `default-dsc` and delegates `/spec/components/mcplifecycleoperator` through `ignoreDifferences`; dashboard flag `mcpCatalog` must already be `true`, set by the Stage 030 model-discovery hook (the deploy script refuses otherwise). |
| Used by | `060-agent-tools` (`MCPServer` resources in `mcp-servers`); the dashboard MCP Catalog deploy action. |

## Why

The MCP Lifecycle Operator is the RHOAI 3.5 component that deploys, configures and manages MCP servers, and the MCP
Catalog's deploy action depends on it [1], [3]. It is a Technology Preview; the component defaults to `Removed` and is
enabled by setting `spec.components.mcplifecycleoperator.managementState` to `Managed` on the DataScienceCluster [1].
Using the RHOAI component, rather than installing the upstream operator, keeps the operator image and API version
coupled to the installed RHOAI release (`v3.5.1`, image recorded in [`operator-source.json`](operator-source.json)
and matching the Red Hat catalog record [5]).

The DataScienceCluster is a single shared object owned by Stage 010. This component changes only the one delegated
field, so it is a Job and not a second owner of the DSC. Keeping it in its own Application lets the MCP API be
enabled, validated and disabled independently of the agent runtime and of the MCP servers.

## What

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `enable-mcp-platform` | `redhat-ods-applications` | Job identity. Wave 1. |
| ClusterRole | `enable-mcp-platform` | — | `get`, `patch` on `datascienceclusters` named `default-dsc` only. Wave 1. |
| ClusterRoleBinding | `enable-mcp-platform` | — | Binds the role to the ServiceAccount. Wave 1. |
| Job | `enable-mcp-platform` | `redhat-ods-applications` | Sync hook, wave 5, `BeforeHookCreation`. Merge-patches `mcplifecycleoperator.managementState: Managed` and reads it back. Pinned `ose-cli` image by digest, restricted security context, 120 s deadline, `backoffLimit: 1`. |

`operator-source.json` is not rendered. It records the expected operator image, its amd64 digest and the source
revision `cc66894b` [4]; `validate-mcp-platform.sh` compares the running image with it.

Objects not in Git, created by the RHOAI operator: the `MCPLifecycleOperator` component CR `default`, the
`mcp-lifecycle-operator` Deployment in `redhat-ods-applications`, and the `mcpservers.mcp.x-k8s.io` CRD.

## How

- **Delegation.** Stage 010 writes `mcplifecycleoperator: Removed` in Git and lists the field in its
  `ignoreDifferences`. This Job sets the live value to `Managed`. `deploy-mcp-platform.sh` asserts that the
  delegation exists (`stage_apps.delegated`) before it writes anything.
- **Guards.** The script selects the reviewed commit (`stage_apps.py select`: the stage source is clean and the
  repository advertises the commit), refuses
  a foreign or busy Application and foreign-owned prerequisite objects, and checks the RBAC rules match exactly.
- **Hook lifecycle.** Only `BeforeHookCreation`, so the completed Job and its pod stay until the next sync [6].
- **Dashboard flag.** `mcpCatalog` is required by the docs for the catalog deploy action [1]; it is set by the
  Stage 030 model-discovery hook (`030-private-model-serving`), not here.
- **Disabling.** Setting the component back to `Removed` can delete MCPServer resources; check user namespaces
  first [1]. Pruning this Application does not revert the DSC field.
- **No secrets, no cluster-specific values.**

## Validation

`validate-mcp-platform.sh` (read-only; waits up to 180 s for readiness). By hand:

```bash
oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.mcplifecycleoperator.managementState}{"\n"}'
oc get deploy -n redhat-ods-applications -l app.kubernetes.io/name=mcp-lifecycle-operator
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Enablement | Set `mcplifecycleoperator.managementState: Managed` on the DSC [1] | Hook Job patches exactly that field on `default-dsc` | Aligned |
| Catalog flag | `mcpCatalog: true` required for the deploy action [1], [2] | Required as a precondition, set by Stage 030 | Aligned |
| Prerequisites | RHOAI 3.5 on OpenShift 4.22 or later, cluster-admin [1] | RHOAI 3.5.1 on OpenShift 4.22 | Aligned |
| Verification | Running `mcp-lifecycle-operator` pod and component status [1] | Validator checks Deployment, component Ready, DSC condition and CRD | Aligned |
| Support level | Technology Preview; `v1alpha1` API without compatibility commitment [1], [3] | Stated in the stage README | Aligned |
| Governance | Lifecycle operator has no rate limiting or access control; MCP gateway Operator is separate [1], [7] | No MCP gateway installed; access control is per server (see `060-agent-tools`) | Gap (no central MCP governance; documented as blocked) |
| GitOps ownership | n/a | Job patches a field owned by Stage 010 under explicit delegation | Deviation (justified: single owner for the shared DSC) |

## References

1. Red Hat OpenShift AI Self-Managed 3.5, Working with the MCP catalog, "Enable MCP server lifecycle management". https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/enabling-mcp-lifecycle-management
2. Red Hat OpenShift AI Self-Managed 3.5, Managing resources, "Customizing the dashboard" (dashboard configuration options). https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard
3. Red Hat OpenShift AI Self-Managed 3.5, Release notes, "Technology Preview features" (MCP Lifecycle Operator). https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes
4. red-hat-data-services/mcp-lifecycle-operator at `cc66894b` (upstream source of the installed image). https://github.com/red-hat-data-services/mcp-lifecycle-operator/tree/cc66894be8cd87d35064e67ec02dbc6e5b5c3c89
5. Red Hat Ecosystem Catalog, image record `rhoai/odh-mcp-lifecycle-operator-rhel9` v3.5.1. https://catalog.redhat.com/api/containers/v1/images/id/6ab154fb4ca9d2da808d38ef
6. Argo CD, "Sync Phases and Waves" (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
7. Red Hat OpenShift AI Self-Managed 3.5, Working with the MCP catalog, "Set up the MCP gateway Operator as a prerequisite for MCP management". https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/assembly-mcp-gateway-operator-prerequisites_mcp-gateway-operator
