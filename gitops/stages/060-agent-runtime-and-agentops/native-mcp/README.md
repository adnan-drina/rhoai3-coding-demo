# Catalog OpenShift MCP Server

This component uses the MCP Lifecycle Operator included in OpenShift AI 3.5.1.
The operator owns the Deployment, Service and generated NetworkPolicy; GitOps
owns only the MCPServer and its customer configuration. The existing Stage 040
server remains active until this replacement's protocol and access tests pass.

The server is hosted in `mcp-servers`, displayed as **MCP servers**, with project administration granted to the exact `ai-admin` user. `ai-developer` has no hosting-project or Registry access. Caller tool permissions remain those of the caller's workload project. The superseded native deployment in `demo-sandbox` is retired through exact owned-resource cleanup after replacement qualification and targeted consumer inventory; the older Stage 040 Studio server remains available.

Registry publication targets the hosting workspace. Caller tool permissions remain those of the user's workload project, including `demo-sandbox`; the hosting namespace is not substituted into developer-positive tool tests. Developer consumption through the governed endpoint and global nonsecret Studio discovery is a separate authorization contract, with a genuine per-session user token and no hosting project binding.

The installed catalog's Red Hat OpenShift MCP Server 0.4 is pinned to its OCI
digest and image-bound source in `catalog-source.json`. The catalog's default
service-account `view` grant is replaced by supported caller authentication
and the catalog's core/config read-only toolsets. Secret resources are explicitly
denied through the documented GVK policy. The pinned server uses documented OpenShift opaque-token
passthrough. `require_oauth=true` rejects missing bearer credentials; the native
derived-client path also rejects absent tokens before any bootstrap fallback.
`skip_jwt_verification=true` is **not token validation**. The Kubernetes API
validates the caller's forwarded token and authorizes every pod request. The
mounted service-account token is needed for native in-cluster configuration;
the server SA receives no RoleBindings. Each request creates a separate client
from only API-server trust settings and that request's bearer token.

The native generated NetworkPolicy allows ingress from any source on the MCP
port. An additional Kubernetes NetworkPolicy cannot subtract that allowance.
The service therefore requires authenticated transport and downstream caller
authorization. The explicitly approved transport boundary is HTTPS at the
OpenShift Route and HTTP, including the forwarded bearer, from router to
server and for cluster peers. The selected RHOAI 3.5.1 controller hard-codes
an HTTP MCP handshake. The edge Route redirects public HTTP to HTTPS;
clients must verify the ingress certificate and hostname. This is not
end-to-end TLS or a central MCP gateway. No extra policy is claimed to
subtract the operator's ingress allowance.

Required acceptance before switching consumers:

- current MCPServer conditions and native controller-owned workload/service;
- verified HTTPS edge, HTTP redirect, MCP initialize and tools/list;
- missing bearer rejected and invalid bearer pod request denied;
- each genuine persona's authorized namespace allowed, foreign namespace denied;
- alternating persona requests cannot reuse another caller's authority;
- catalog core/config read tools are listed; bounded pod reads pass and write/Secret requests are refused;
- server SA has no pod, Secret, RBAC or workload mutation permissions;
- restart, scale and deletion act through the native CR with UID-bound cleanup.

No access or functional pass is implied by a Ready condition or a catalog card.
Registry registration uses the existing tenant-aware native MLflow store;
catalog discovery and runtime lifecycle remain separate contracts.
The catalog version remains `0.4` in provenance. Native Registry registration
uses the equivalent strict semantic version `0.4.0` required by its API.

Source pins:

- lifecycle operator: `cc66894be8cd87d35064e67ec02dbc6e5b5c3c89` in
  [the installed Red Hat source](https://github.com/red-hat-data-services/mcp-lifecycle-operator/tree/cc66894be8cd87d35064e67ec02dbc6e5b5c3c89);
- catalog server: [image-bound configuration and caller authorization](https://github.com/openshift/openshift-mcp-server/tree/3ba1f65aca7a8a23dc3744a57f3723d4a7699772),
  the Red Hat 0.4 image identified in `catalog-source.json`;
- [RHOAI 3.5 native lifecycle procedure](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_the_mcp_catalog/enabling-mcp-lifecycle-management).
