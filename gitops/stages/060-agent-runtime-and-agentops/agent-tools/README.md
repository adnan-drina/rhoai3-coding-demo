# Agent tools: OpenShift MCP servers (`060-agent-tools`)

This Application runs the Red Hat OpenShift MCP Server 0.4 from the OpenShift AI MCP Catalog as two native
`MCPServer` resources in the `mcp-servers` project ("MCP servers"). The read-only server is in-cluster and
token-less; the read-write companion is published on an HTTPS Route and acts only with the caller's own OpenShift
token. Gen AI Studio playground users, the OpenShift Ops Assistant and Dev Spaces workspaces call these servers as
agent tools.

| | |
|---|---|
| Argo CD Application | `060-agent-tools` ([manifest](../../../argocd/app-of-apps/060-agent-runtime-and-agentops/agent-tools.yaml)) |
| Deployed by | [`stages/060-agent-runtime-and-agentops/deploy-native-mcp.sh <branch>`](../../../../stages/060-agent-runtime-and-agentops/deploy-native-mcp.sh) (own deploy script). It runs the preflight and applies the Application pinned to the SHA; the exact-revision sync is a separate manual step. `--publish-studio` runs Stage 040 `publish-catalog-mcp.py`. |
| Validated by | [`stages/060-agent-runtime-and-agentops/validate-native-mcp.py`](../../../../stages/060-agent-runtime-and-agentops/validate-native-mcp.py) (Application Synced at the expected revision; ownership of every customer object; hosting project metadata and `ai-admin` binding; per server: Route presence or absence, effective `config.toml` policy, image pin, `Ready` condition, operator-owned Deployment/Service/NetworkPolicy, ServiceAccount, running pod image digest). Protocol and caller isolation are qualified separately by Stage 040 `qualify-catalog-mcp.py`. |
| Sync | Manual. Annotation `compare-options: ServerSideDiff=true`; sync option `RespectIgnoreDifferences=true` (no `ignoreDifferences` defined). The Application carries `sync-wave: "60"`, which has no effect because no parent Application manages it. |
| Depends on | `060-mcp-platform` (MCPServer API and lifecycle operator). Namespaces `demo-sandbox`, `internal-models`, `external-models`, `models-as-a-service` for the read-only RoleBindings (Stages 030/040). |
| Used by | Stage 040 `040-genai-studio`: discovery entries `OpenShift-MCP` and `OpenShift-MCP-ReadWrite` in ConfigMap `gen-ai-aa-mcp-servers`, written by `publish-catalog-mcp.py`, and the OpenShift Ops Assistant agent profile. Stage 070 Dev Spaces workspaces (in-cluster read-only URL). MLflow MCP Registry entry, written by `publish-mcp-registry.py`. |

## Why

The MCP Catalog in OpenShift AI 3.5 deploys catalog servers as `MCPServer` resources handled by the MCP Lifecycle
Operator, which creates the Deployment, Service and NetworkPolicy and cleans them up on delete [1], [2]. Using the
native resource instead of hand-written Deployments keeps the server lifecycle (upgrade, scale, remove, health) on
the documented path [2]. The image is the catalog's Red Hat OpenShift MCP Server 0.4, pinned by digest; its catalog
record carries version 0.4.0 and the source tag `3ba1f65` [6].

Two servers exist because inspection and change need different trust:

- **Read-only, token-less, in-cluster.** Tools that only read cluster state are useful to the playground and to
  agents without asking each user for a token. Without a bearer the server acts as its own bounded ServiceAccount.
  It has no Route, because the operator's NetworkPolicy admits any cluster peer.
- **Read-write, token required, HTTPS Route.** Create, update, scale and delete run only with the caller's token, so
  the Kubernetes API authorizes every action as the caller. The server's own ServiceAccount has no permissions.

The catalog's default deployment grants the server ServiceAccount `view`; that grant is replaced by caller
authentication (read-write) or by an explicit, narrow RoleBinding set (read-only).

The MCP Catalog is a Technology Preview in the dashboard configuration and a Developer Preview for its administrative
interface; the lifecycle operator is a Technology Preview, and the served `mcp.x-k8s.io/v1alpha1` API has no
backwards-compatibility commitment [1], [3], [4].

## What

All objects are in `hosting/`.

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `mcp-servers` | — | Display name "MCP servers", label `opendatahub.io/dashboard: "true"`. Wave 0. |
| RoleBinding | `mcp-host-admin` | `mcp-servers` | `admin` for the exact user `ai-admin`. `ai-developer` has no access to the hosting project. Wave 1. |
| ServiceAccount | `openshift-mcp-server` | `mcp-servers` | Read-write server identity. No RoleBindings. Token mounted only because in-cluster discovery needs the CA and token files. Wave 1. |
| ServiceAccount | `openshift-mcp-server-ro` | `mcp-servers` | Read-only server identity for requests without a bearer. Wave 1. |
| ClusterRole, ClusterRoleBinding | `openshift-mcp-server-ro` | — | get/list on namespaces, nodes, projects, and `metrics.k8s.io` pods/nodes. Wave 1. |
| RoleBinding | `openshift-mcp-server-ro-view` | `demo-sandbox`, `internal-models`, `external-models`, `mcp-servers` | `view` for the read-only ServiceAccount. Wave 1. |
| Role, RoleBinding | `openshift-mcp-server-ro-subscriptions` | `models-as-a-service` | get/list `maassubscriptions` only (outside `view`; the Ops Assistant reports who may use which model). Wave 1. |
| ConfigMap | `openshift-mcp-server` | `mcp-servers` | Read-only `config.toml`. Wave 1. |
| ConfigMap | `openshift-mcp-server-rw` | `mcp-servers` | Read-write `config.toml`. Wave 1. |
| MCPServer | `openshift-mcp-server` | `mcp-servers` | Pinned image, port 8080, path `/mcp`, config mounted read-only, 64Mi `/tmp`, one replica, restricted security context, ServiceAccount `openshift-mcp-server-ro`, `stateless: true`. Wave 2, `SkipDryRunOnMissingResource=true`. |
| MCPServer | `openshift-mcp-server-rw` | `mcp-servers` | Same, with ConfigMap `openshift-mcp-server-rw` and ServiceAccount `openshift-mcp-server`. Wave 2. |
| Route | `openshift-mcp-server-rw` | `mcp-servers` | Edge TLS, `insecureEdgeTerminationPolicy: Redirect`, to Service port 8080. Wave 3. |

`catalog-source.json` is not rendered. It records the catalog identity (source `rh_mcp_servers`, id 15, version
`0.4`), the local registry name `io.github.openshift/openshift-mcp-server` with strict version `0.4.0` required by
the MLflow registry API, the image and amd64 digest, and the source revision. `validate-native-mcp.py` reads the
amd64 digest from it.

Objects created by the lifecycle operator (owner reference to the MCPServer, not in Git): Deployments, Services and
NetworkPolicies `openshift-mcp-server` and `openshift-mcp-server-rw`. Objects written by scripts: the Studio discovery
keys in `redhat-ods-applications/gen-ai-aa-mcp-servers` (Stage 040 helper) and the MLflow MCP Registry entry
(workspace `mcp-servers`).

## How

### Server configuration

Both `config.toml` files set: `stateless = true`, `cluster_provider_strategy = "in-cluster"`,
`cluster_auth_mode = "passthrough"`, `skip_jwt_verification = true`, `disable_dynamic_client_registration = true`,
`require_tls = false`, `toolsets = ["core", "config"]`, a `[[denied_resources]]` entry for `v1/Secret`, and HTTP limits
(10 s header timeout, 1 MiB body, 2 requests/s, burst 4).

| Field | Read-only | Read-write | Why |
|---|---|---|---|
| `read_only` | `true` | `false` | Read-only exposes only tools marked read-only [7]. |
| `disable_destructive` | (no effect when read-only [7]) | `false` | Callers may delete and update within their own RBAC. |
| `require_oauth` | `false` | `true` | Read-only is token-less by design; read-write rejects requests without a bearer [7]. |
| ServiceAccount | `openshift-mcp-server-ro` (bounded grants) | `openshift-mcp-server` (no grants) | Passthrough falls back to the pod identity when no bearer is sent [7]. |
| Exposure | Service only: `http://openshift-mcp-server.mcp-servers.svc.cluster.local:8080/mcp` | HTTPS Route plus Service | See transport boundary. |

Notes on the security-relevant fields:

- `cluster_auth_mode = "passthrough"` forwards the caller's `Authorization` header to the Kubernetes API and falls back
  to the pod's credentials when there is none [7]. On the read-write server `require_oauth` blocks the fallback, so
  the permission-less ServiceAccount is never used for tools. Each request builds its client from the API-server
  trust settings and that request's bearer token only.
- `skip_jwt_verification = true` is **not token validation**: the server forwards the bearer without checking it [7].
  The Kubernetes API validates the forwarded OpenShift token and authorizes every request. A request with an invalid
  bearer is therefore rejected on the first real resource call, not at MCP initialize or tool listing.
- The Secret GVK is denied on both servers [7]. The read-only ServiceAccount's grants are `view`, which does not allow
  viewing Secrets [13], plus the listings above; no RBAC objects and no writes. Widen deliberately, per project.

### Transport and network boundary

The operator-generated NetworkPolicy allows ingress from any source on port 8080. NetworkPolicies are additive, so
another policy cannot subtract that allowance [8]. The accepted boundary is HTTPS at the OpenShift Route (edge
termination at the Ingress Controller, HTTP redirected to HTTPS [9]) and plain HTTP, including the forwarded bearer,
from the router to the pod and between cluster peers. The RHOAI 3.5.1 lifecycle controller [12] uses an HTTP MCP
handshake. This is not end-to-end TLS and not a central MCP gateway. Clients must verify the ingress certificate and
host name.

Consequence for the read-only server: any pod in the cluster that can reach the Service gets the read-only
ServiceAccount's permissions without a token. Keep its grants limited to non-sensitive read access.

### Ownership and lifecycle

- GitOps owns only the MCPServers and their customer configuration (ConfigMaps, ServiceAccounts, RBAC, Route). The
  lifecycle operator owns the workloads. Restart, scale and delete go through the MCPServer (UID-bound cleanup) [2].
- `deploy-native-mcp.sh` refuses unpublished source, runs `validate-native-mcp.py --preflight` (never adopts an
  existing Service without an MCPServer), then applies the Application at the exact SHA. Sync it explicitly at that
  revision, then run the validator.
- Registry: the RHOAI 3.5.1 catalog has no Register action next to Deploy, so `publish-mcp-registry.py` registers the
  server through the installed MLflow MCP registry API, in workspace `mcp-servers`. Catalog discovery, registry entry
  and runtime lifecycle are separate contracts; there is no automatic catalog-to-registry-to-Studio sync.
- Studio publication: Stage 040 `publish-catalog-mcp.py` writes the `OpenShift-MCP` (read-only, no token) and
  `OpenShift-MCP-ReadWrite` (caller token) keys into the documented `gen-ai-aa-mcp-servers` ConfigMap [10]. Stage 040's
  Application must already delegate those data keys. In the playground, users authorize the read-write entry with
  their own OpenShift token, not a MaaS key; no shared token is stored. This path does not use MaaS keys or quotas.
- Caller scope: tool permissions are those of the caller in its workload project (for example `demo-sandbox`). The
  hosting project is never substituted into developer tests.
- Known issue RHOAIENG-82694 (lifecycle operator informer memory on large clusters) applies; no workaround is
  configured here.
- Keep image, installed schema and tests together when changing product versions. Some accepted `MCPServer`
  fields are validated against the installed schema but not described in the catalog deployment guide.

### Required acceptance before switching consumers

- current MCPServer conditions and operator-owned workload and Service;
- verified HTTPS edge, HTTP redirect, MCP initialize and tools/list on the read-write Route;
- missing bearer rejected (read-write) and invalid bearer denied on a resource request;
- each persona's authorized namespace allowed, a foreign namespace denied;
- alternating persona requests cannot reuse another caller's authority;
- core/config read tools listed; bounded pod reads pass; write and Secret requests refused on the read-only server;
- read-write ServiceAccount has no pod, Secret, RBAC or workload permissions;
- restart, scale and deletion act through the MCPServer.

A `Ready` condition or a catalog card does not prove access or function.

### Secrets and cluster values

No credential is stored by this component or in Studio discovery. The Route host is assigned by the cluster; no host
name is committed.

## Validation

```bash
RHOAI_STAGE060_EXPECTED_REVISION=<deployed-sha> python3 stages/060-agent-runtime-and-agentops/validate-native-mcp.py
oc get mcpserver -n mcp-servers
```

The validator prints `[PASS] Exact source/native MCP ownership and readiness; protocol/caller isolation NOT
qualified by this check`. Both MCPServers should show `READY True`.

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Deployment method | Catalog deploy creates an `MCPServer`; operator provisions Deployment and Service [2] | MCPServers in Git, operator-owned workloads | Aligned |
| Prerequisite | Lifecycle operator enabled first [1] | `060-mcp-platform`; validator checks DSC and CRD | Aligned |
| Service account | Add `runtime.security.serviceAccountName` when the server needs one; it must exist first [2] | Both set; ServiceAccounts in wave 1, MCPServers wave 2 | Aligned |
| Statefulness | Operator defaults to `ClientIP` affinity; `stateless: true` only for stateless servers [2] | Server `stateless = true`, MCPServer `mcp.stateless: true`, one replica | Aligned |
| Health | `Ready` condition `True` [2] | Validator requires current `Ready` | Aligned |
| Authentication and policy | Lifecycle operator provides no access control or rate limiting; MCP gateway Operator is the governed entry point [1], [11] | Per-server: caller-token passthrough, Secret denial, local rate limit; no MCP gateway | Gap (no central MCP gateway; documented as blocked) |
| Network exposure | Operator creates NetworkPolicies [1]; policies are additive [8] | Accepted: read-only in-cluster only, read-write behind edge Route | Deviation (justified: operator policy admits all peers; HTTP inside the cluster) |
| Server options | `read_only`, `require_oauth`, `cluster_auth_mode`, `denied_resources`, `skip_jwt_verification` as documented [7] | Set as in the table above | Aligned |
| Studio discovery | `gen-ai-aa-mcp-servers` ConfigMap in `redhat-ods-applications`, one JSON value per key [10] | Written by Stage 040 helper | Aligned |
| Support level | MCP Catalog Technology/Developer Preview; lifecycle operator Technology Preview [3], [4], [5] | Stated above | Aligned |

## References

1. Red Hat OpenShift AI Self-Managed 3.5, Working with the MCP catalog, "Enable MCP server lifecycle management". https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/enabling-mcp-lifecycle-management
2. Red Hat OpenShift AI Self-Managed 3.5, Working with the MCP catalog, "Deploy and manage MCP servers". https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/deploying-and-managing-mcp-servers
3. Red Hat OpenShift AI Self-Managed 3.5, Managing resources, "Customizing the dashboard" (`mcpCatalog` Technology Preview). https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard
4. Red Hat OpenShift AI Self-Managed 3.5, Release notes, "Developer Preview features" (MCP Catalog administrative interface; MCP Catalog for enterprise management of MCP servers). https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes
5. Red Hat OpenShift AI Self-Managed 3.5, Release notes, "Technology Preview features" (MCP Lifecycle Operator). https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes
6. Red Hat Ecosystem Catalog, image record `openshift-mcp-tech-preview/openshift-mcp-server-rhel9` 0.4.0. https://catalog.redhat.com/api/containers/v1/images/id/6ac3e9901df7f5523e993caf
7. openshift/openshift-mcp-server at `3ba1f65`, `docs/configuration.md` (upstream source of the image). https://github.com/openshift/openshift-mcp-server/blob/3ba1f65aca7a8a23dc3744a57f3723d4a7699772/docs/configuration.md
8. OpenShift Container Platform 4.22, Network security, "Network policy" (About network policy). https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/network_security/network-policy
9. OpenShift Container Platform 4.22, Ingress and load balancing, "Routes" (Securing routes). https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/ingress_and_load_balancing/routes
10. Red Hat OpenShift AI Self-Managed 3.5, Experimenting with models in the Gen AI playground, "Configuring Model Context Protocol (MCP) servers". https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/experimenting_with_models_in_the_gen_ai_playground/playground-prerequisites_rhoai-user#configuring-model-context-protocol-servers_rhoai-user
11. Red Hat OpenShift AI Self-Managed 3.5, Working with the MCP catalog, "Set up the MCP gateway Operator as a prerequisite for MCP management". https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/assembly-mcp-gateway-operator-prerequisites_mcp-gateway-operator
12. red-hat-data-services/mcp-lifecycle-operator at `cc66894b` (upstream source of the installed operator). https://github.com/red-hat-data-services/mcp-lifecycle-operator/tree/cc66894be8cd87d35064e67ec02dbc6e5b5c3c89
13. Kubernetes, "Using RBAC Authorization" (User-facing roles: `view`) (upstream). https://kubernetes.io/docs/reference/access-authn-authz/rbac/
