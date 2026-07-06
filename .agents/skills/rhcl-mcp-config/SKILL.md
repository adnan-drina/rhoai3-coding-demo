---
name: rhcl-mcp-config
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Register MCP servers and create authentication/authorization policies for the
  Red Hat Connectivity Link 1.3 MCP gateway. Covers MCPServerRegistration for
  on-prem and external servers, MCPVirtualServer for curated tool collections,
  AuthPolicy for OAuth/JWT authentication, tool-level authorization with CEL
  expressions, and tool access revocation. Use when registering MCP servers,
  configuring auth for MCP gateway, creating virtual servers, or revoking tool
  access. Do NOT use for MCP gateway installation (use rhcl-install-mcp). Do
  NOT use for general RHCL policy configuration (use rhcl-configure).
---

# Red Hat Connectivity Link 1.3 — MCP Server Registration and Policies

## When to use

- Registering on-prem MCP servers with MCPServerRegistration
- Registering external MCP servers (ServiceEntry + DestinationRule + HTTPRoute)
- Creating credential secrets for MCP servers
- Setting up OAuth/JWT authentication for MCP gateway
- Configuring tool-level authorization with AuthPolicy + CEL
- Creating MCPVirtualServer for curated tool collections
- Revoking tool access for users/groups

## Key APIs

| Kind | apiVersion | Purpose |
|------|-----------|---------|
| MCPServerRegistration | `mcp.kuadrant.io/v1alpha1` | Register MCP server |
| MCPVirtualServer | `mcp.kuadrant.io/v1alpha1` | Curated tool subset |
| AuthPolicy | `kuadrant.io/v1` | Auth/authz on MCP gateway |
| HTTPRoute | `gateway.networking.k8s.io/v1` | Route to MCP server |

## MCPServerRegistration — on-prem

```yaml
apiVersion: mcp.kuadrant.io/v1alpha1
kind: MCPServerRegistration
metadata:
  name: my-mcp-server
  namespace: mcp-test
spec:
  toolPrefix: myserver_
  targetRef:
    group: "gateway.networking.k8s.io"
    kind: "HTTPRoute"
    name: "mcp-server-route"
    namespace: "mcp-test"
  credentialRef:
    name: mcp-server-secret
    key: api-key
```

### Spec fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `targetRef.name` | Yes | — | HTTPRoute pointing to MCP server |
| `toolPrefix` | No | — | Prefix for tools (immutable, alphanumeric/`-`/`_`) |
| `path` | No | `/mcp` | MCP endpoint path |
| `credentialRef.name` | No | — | Secret with credentials |
| `credentialRef.key` | No | `token` | Key within Secret |

### Credential secret

Must have label `mcp.kuadrant.io/secret: "true"`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-server-secret
  namespace: mcp-test
  labels:
    mcp.kuadrant.io/secret: "true"
type: Opaque
stringData:
  api-key: "your-api-key-here"
```

## MCPServerRegistration — external servers

Requires Istio. Resources needed in order:

1. **ServiceEntry** — register external host (`networking.istio.io/v1beta1`)
2. **DestinationRule** — TLS settings (SIMPLE/MUTUAL)
3. **HTTPRoute** — URLRewrite filter to external hostname
4. **Secret** — backend API key with `mcp.kuadrant.io/secret: "true"` label
5. **AuthPolicy** — pass-through Authorization header (if OAuth)
6. **MCPServerRegistration** — register with gateway

See `references/official-doc-extraction.md` for full YAML examples.

## MCPVirtualServer — curated tool collections

```yaml
apiVersion: mcp.kuadrant.io/v1alpha1
kind: MCPVirtualServer
metadata:
  name: dev-tools
  namespace: mcp-system
spec:
  description: "Development and debugging tools"
  tools:
  - server1_devtool
  - server2_debug
```

- Access via header: `X-Mcp-Virtualserver: namespace/name`
- Filters `tools/list` only; does not change `tools/call` routing
- Combined with auth: result is intersection of identity filter + virtual filter

## Authentication — OAuth/JWT

1. Set OAuth env vars on MCP gateway deployment:
   `OAUTH_RESOURCE_NAME`, `OAUTH_RESOURCE`, `OAUTH_AUTHORIZATION_SERVERS`,
   `OAUTH_BEARER_METHODS_SUPPORTED`, `OAUTH_SCOPES_SUPPORTED`

2. Create AuthPolicy on **`mcp` listener** for JWT validation:
   - Target: Gateway sectionName `mcp`
   - Skip `/.well-known` paths
   - Validate JWT via `issuerUrl`
   - Return 401 with `WWW-Authenticate` header pointing to discovery endpoint

3. Broker exposes `/.well-known/oauth-protected-resource` for MCP client discovery

## Authorization — tool-level

Create AuthPolicy on **`mcps` listener** (internal tools/call routing):

- Validates JWT and extracts `resource_access` claims
- CEL expression checks `x-mcp-toolname` header against user's roles
- JWT client ID format: `{namespace}/{MCPServerRegistration name}`
- Roles map to tool names (e.g., `"roles": ["add", "multiply"]`)

Key CEL predicate:
```
request.headers['x-mcp-toolname'] in auth.identity.resource_access[request.headers['x-mcp-servername']].roles
```

See `references/official-doc-extraction.md` for full AuthPolicy examples.

## Revocation

- Remove role from user/group in identity provider (e.g., Keycloak)
- New tokens lack the role; `tools/call` returns error
- Existing sessions: access until token expires (reduce lifespan for faster revocation)
- Filter from `tools/list`: configure wristband JWT (`x-authorized-tools` header)
  via Authorino ECDSA key pair + MCPGatewayExtension `trustedHeadersKey`

## Validation

```bash
oc get mcpsr -A
oc get mcpvirtualserver -A
oc get authpolicy -n gateway-system \
  -o jsonpath='{.items[*].status.conditions[?(@.type=="Enforced")].status}'
```

## References

- `references/source-capture.md` — source provenance
- `references/official-doc-extraction.md` — full extraction with all YAML examples
- Official: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html-single/registering_mcp_servers_and_creating_policies/index
