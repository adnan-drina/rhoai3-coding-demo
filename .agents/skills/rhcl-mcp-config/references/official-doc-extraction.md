# Official Doc Extraction — rhcl-mcp-config

Source: Red Hat Connectivity Link 1.3 — Registering MCP servers and creating policies

## Registering on-prem MCP servers

### Prerequisites

- MCP gateway installed
- Gateway object configured with listeners
- MCPGatewayExtension CR applied
- ReferenceGrant if cross-namespace
- cluster-admin role

### HTTPRoute to MCP server

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: mcp-api-key-server-route
  namespace: mcp-test
  labels:
    mcp-server: 'true'
spec:
  parentRefs:
  - name: mcp-gateway
    namespace: gateway-system
  hostnames:
  - 'api-key-server.mcp.local'
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: mcp-api-key-server
      port: 9090
```

### MCPServerRegistration CR

```yaml
apiVersion: mcp.kuadrant.io/v1alpha1
kind: MCPServerRegistration
metadata:
  name: mcp-server-one
  namespace: mcp-test
spec:
  toolPrefix: serverone_
  targetRef:
    group: "gateway.networking.k8s.io"
    kind: "HTTPRoute"
    name: "mcp-api-key-server-route"
    namespace: "mcp-test"
  credentialRef:
    name: mcp-server-one-secret
    key: api-key
```

### MCPServerRegistration spec

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `spec.targetRef.group` | String | No | `gateway.networking.k8s.io` | Target resource group |
| `spec.targetRef.kind` | String | No | `HTTPRoute` | Target resource kind |
| `spec.targetRef.name` | String | Yes | — | Name of target HTTPRoute |
| `spec.targetRef.namespace` | String | No | Same namespace | Namespace of target |
| `spec.toolPrefix` | String | No | — | Prefix for tools (immutable, alphanumeric + `-` + `_`) |
| `spec.path` | String | No | `/mcp` | MCP endpoint path |
| `spec.credentialRef.name` | String | Yes (if used) | — | Name of Secret CR |
| `spec.credentialRef.key` | String | No | `token` | Key within Secret |

### Credential Secret requirements

- Must have label: `mcp.kuadrant.io/secret: "true"`
- Without this label, the MCP gateway controller cannot see the Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-backend-auth
  namespace: mcp-test
  labels:
    mcp.kuadrant.io/secret: "true"
    app.kubernetes.io/part-of: mcp-gateway
type: Opaque
stringData:
  api-key: "mcp_prod_12abC34..."
```

### Verification

```bash
oc get mcpsr -A
# Output columns: NAMESPACE, NAME, PREFIX, TARGET, PATH, READY, TOOLS, CREDENTIALS, AGE

oc get mcpsr -A -o yaml
# Check status.conditions[].type=="Ready" and status.discoveredTools
```

### Verify tools via curl

```bash
# Initialize session
curl -s -D /tmp/mcp_headers -X POST http://example.com/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}'

# Extract session ID
SESSION_ID=$(grep -i "mcp-session-id:" /tmp/mcp_headers | cut -d' ' -f2 | tr -d '\r')

# List tools
curl -X POST http://example.com/mcp \
  -H "Content-Type: application/json" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

## Registering external MCP servers (Istio)

### Resources needed (in order)

1. **ServiceEntry** — register external host
2. **DestinationRule** — TLS settings (SIMPLE default)
3. **HTTPRoute** — route with URLRewrite filter
4. **Secret** — backend API key
5. **AuthPolicy** — pass-through Authorization header (optional, for OAuth)
6. **MCPServerRegistration** — register with gateway

### ServiceEntry

```yaml
apiVersion: networking.istio.io/v1beta1
kind: ServiceEntry
metadata:
  name: mcp-external-server
  namespace: mcp-test
spec:
  hosts:
  - api.githubcopilot.com
  ports:
  - number: 443
    name: https
    protocol: HTTPS
  location: MESH_EXTERNAL
  resolution: DNS
```

### DestinationRule

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: mcp-external-server
  namespace: mcp-test
spec:
  host: api.githubcopilot.com
  trafficPolicy:
    tls:
      mode: SIMPLE
      sni: api.githubcopilot.com
```

### HTTPRoute for external server

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: mcp-external-server
  namespace: mcp-test
spec:
  parentRefs:
  - group: gateway.networking.k8s.io
    kind: Gateway
    name: mcp-gateway
    namespace: gateway-system
  hostnames:
  - example.mcp.local
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /mcp
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.externalhostname.com
    backendRefs:
    - name: api.example.com
      kind: Hostname
      group: networking.istio.io
      port: 443
```

### AuthPolicy for external (OAuth pass-through)

```yaml
apiVersion: kuadrant.io/v1
kind: AuthPolicy
metadata:
  name: mcps-auth-policy
  namespace: mcp-test
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: mcp-external-server
  rules:
    response:
      success:
        headers:
          authorization:
            plain:
              expression: 'request.headers["authorization"]'
```

## MCPVirtualServer

### Purpose

- Curate tool subsets from aggregated servers
- Reduce LLM tool overload
- Group tools by function
- Access via `X-Mcp-Virtualserver: namespace/name` header
- Filters `tools/list` only; does not change `tools/call` routing

### CR example

```yaml
apiVersion: mcp.kuadrant.io/v1alpha1
kind: MCPVirtualServer
metadata:
  name: dev-tools
  namespace: mcp-system
spec:
  description: "Development and debugging tools"
  tools:
  - mcpserver1_devtool1
  - mcpserver2_headers1
  - mcpserver3_debug1
```

### Authorization intersection

When auth + virtual server filtering are both active:
1. Identity-based filtering via `x-authorized-tools` header
2. Virtual server filtering via `X-Mcp-Virtualserver` header
Result: intersection of both filters

### Verification

```bash
oc get mcpvirtualserver -A

curl -X POST http://example.com/mcp \
  -H "Content-Type: application/json" \
  -H "mcp-session-id: $SESSION_ID" \
  -H "X-Mcp-Virtualserver: mcp-system/dev-tools" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq '.result.tools[].name'
```

## Authentication

### OAuth 2.0 Protected Resource Metadata

MCP gateway broker exposes `/.well-known/oauth-protected-resource` for MCP
client discovery.

### Environment variables

| Variable | Purpose |
|----------|---------|
| `OAUTH_RESOURCE_NAME` | Human-readable MCP server name |
| `OAUTH_RESOURCE` | Canonical URI for token audience validation |
| `OAUTH_AUTHORIZATION_SERVERS` | Authorization server URL |
| `OAUTH_BEARER_METHODS_SUPPORTED` | Supported bearer token methods |
| `OAUTH_SCOPES_SUPPORTED` | OAuth scopes supported |

### AuthPolicy for JWT validation

Target: `mcp` listener (public traffic)

```yaml
apiVersion: kuadrant.io/v1
kind: AuthPolicy
metadata:
  name: mcp-jwt-auth-policy
  namespace: gateway-system
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: mcp-gateway
    sectionName: mcp
  defaults:
    when:
    - predicate: "!request.path.contains('/.well-known')"
    rules:
      authentication:
        'keycloak':
          jwt:
            issuerUrl: http://keycloak.example.com:8002/realms/mcp
      response:
        unauthenticated:
          code: 401
          headers:
            'WWW-Authenticate':
              value: Bearer resource_metadata=http://mcp.example.com:8001/.well-known/oauth-protected-resource
          body:
            value: |
              {"error":"Unauthorized","message":"Authentication required."}
```

## Authorization — tool-level

Target: `mcps` listener (internal tools/call routing)

### JWT claim structure

```json
{
  "resource_access": {
    "mcp-ns/arithmetic-mcp-server": {
      "roles": ["add", "sum", "multiply", "divide"]
    }
  }
}
```

Client ID = `{namespace}/{MCPServerRegistration name}`

### AuthPolicy with CEL

```yaml
apiVersion: kuadrant.io/v1
kind: AuthPolicy
metadata:
  name: mcp-tool-auth-policy
  namespace: gateway-system
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: mcp-gateway
    sectionName: mcps
  rules:
    authentication:
      'sso-server':
        jwt:
          issuerUrl: https://keycloak.example.com/realms/mcp
    authorization:
      'tool-access-check':
        patternMatching:
          patterns:
          - predicate: |
              request.headers['x-mcp-toolname'] in (has(auth.identity.resource_access) && auth.identity.resource_access.exists(p, p == request.headers['x-mcp-servername']) ? auth.identity.resource_access[request.headers['x-mcp-servername']].roles : [])
    response:
      unauthenticated:
        headers:
          'WWW-Authenticate':
            value: Bearer resource_metadata=http://mcp.example.com:8001/.well-known/oauth-protected-resource
        body:
          value: |
            {"error":"Unauthorized","message":"MCP Tool Access denied: Authentication required."}
      unauthorized:
        body:
          value: |
            {"error":"Forbidden","message":"MCP Tool Access denied: Insufficient permissions for this tool."}
```

### CEL expression breakdown

- `request.headers['x-mcp-toolname']`: requested tool name (stripped from prefix)
- `request.headers['x-mcp-servername']`: namespaced MCPServerRegistration name
- `auth.identity.resource_access`: JWT claim with allowed tools grouped by server

## Revocation

### Mechanism

- Remove role from user/group in identity provider (e.g., Keycloak)
- New tokens lack the role; `tools/call` returns error
- Existing sessions: access until token expires
- Reduce token lifespan for faster revocation

### Filtering from tools/list

Requires wristband JWT with `x-authorized-tools` header:

1. Generate ECDSA key pair (ES256)
2. Store private key in Authorino namespace as Secret
3. Store public key in MCP gateway namespace as Secret
4. Create AuthPolicy with OPA rule extracting `resource_access` roles
5. Configure wristband response with `customClaims.allowed-tools`
6. Patch MCPGatewayExtension with `trustedHeadersKey.secretName`

### MCPGatewayExtension patch for trusted headers

```bash
oc patch mcpgatewayextension mcp-gateway-ext -n mcp-system --type='merge' \
  -p='{"spec":{"trustedHeadersKey":{"secretName":"trusted-headers-public-key"}}}'
```

## Verification commands

```bash
# All registered servers
oc get mcpsr -A

# All virtual servers
oc get mcpvirtualserver -A

# Auth policy enforcement
oc get authpolicy -n gateway-system \
  -o jsonpath='{.items[*].status.conditions[?(@.type=="Enforced")].status}'

# MCP gateway logs
oc logs -n mcp-system -l app.kubernetes.io/name=mcp-gateway
```
