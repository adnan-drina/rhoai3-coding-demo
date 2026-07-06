# Official Doc Extraction

Use this extraction to keep MCP server registration and auth policy content
grounded in official sources. Verify exact fields with `oc explain` before
writing manifests.

## On-Prem MCPServerRegistration

First create an HTTPRoute to your backend MCP server:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: <mcp_server_route>
  namespace: <mcp_ns>
  labels:
    mcp-server: 'true'
spec:
  parentRefs:
    - name: <mcp_gateway>
      namespace: <gateway_ns>
  hostnames:
    - 'server-name.mcp.local'
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: <mcp_server_service>
          port: 9090
```

Then register:

```yaml
apiVersion: mcp.kuadrant.io/v1alpha1
kind: MCPServerRegistration
metadata:
  name: <mcp_server_one>
  namespace: <mcp_ns>
spec:
  prefix: <serverone>_
  targetRef:
    group: "gateway.networking.k8s.io"
    kind: "HTTPRoute"
    name: "<mcp_server_route>"
    namespace: "<mcp_ns>"
  credentialRef:
    name: <server_secret>
    key: api-key
```

MCPServerRegistration spec fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `spec.targetRef` | TargetReference | Yes | HTTPRoute pointing to MCP server |
| `spec.prefix` | String | No | Tool/prompt name prefix (a-z, 0-9, _) |
| `spec.path` | String | No | MCP endpoint path, default `/mcp` |
| `spec.credentialRef.name` | String | No | Secret with backend credentials |
| `spec.credentialRef.key` | String | No | Key in secret, default `token` |

Prefix constraints: lowercase letters, digits, underscore only. Must start with
letter or digit. Immutable after creation.

## Credential Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: <server_secret>
  namespace: <mcp_ns>
  labels:
    mcp.kuadrant.io/secret: "true"
type: Opaque
stringData:
  api-key: "<credential_value>"
```

The label `mcp.kuadrant.io/secret: "true"` is required for the MCP gateway
controller to discover the secret.

## Verifying Registration

```bash
oc get mcpsr -A
oc get mcpsr <name> -n <ns> -o yaml
```

Status shows `status.discoveredTools` count and conditions:
- `type: Ready`, `status: "True"` means server registered and tools discovered.

Session verification:

```bash
curl -s -D /tmp/mcp_headers -X POST http://<gateway_url>/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'

SESSION_ID=$(grep -i "mcp-session-id:" /tmp/mcp_headers | cut -d' ' -f2 | tr -d '\r')

curl -X POST http://<gateway_url>/mcp \
  -H "Content-Type: application/json" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}'
```

## External MCP Server Registration

Requires Istio for ingress control. Create in order:

1. **ServiceEntry** (register in Istio service registry):

```yaml
apiVersion: networking.istio.io/v1beta1
kind: ServiceEntry
metadata:
  name: <external_server>
  namespace: <mcp_ns>
spec:
  hosts:
    - <api.external-mcp.com>
  ports:
    - number: 443
      name: https
      protocol: HTTPS
  location: MESH_EXTERNAL
  resolution: DNS
```

2. **DestinationRule** (TLS settings):

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: <external_server>
  namespace: <mcp_ns>
spec:
  host: <api.external-mcp.com>
  trafficPolicy:
    tls:
      mode: SIMPLE
      sni: <api.external-mcp.com>
```

3. **HTTPRoute** (with URLRewrite filter):

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: <external_server>
  namespace: <mcp_ns>
spec:
  parentRefs:
    - group: gateway.networking.k8s.io
      kind: Gateway
      name: <mcp_gateway>
      namespace: <gateway_ns>
  hostnames:
    - external.mcp.local
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /mcp
      filters:
        - type: URLRewrite
          urlRewrite:
            hostname: <api.external-mcp.com>
      backendRefs:
        - name: <api.external-mcp.com>
          kind: Hostname
          group: networking.istio.io
          port: 443
```

4. **Secret** and **MCPServerRegistration** (same as on-prem pattern).

5. **AuthPolicy** (optional, for OAuth pass-through):

```yaml
apiVersion: kuadrant.io/v1
kind: AuthPolicy
metadata:
  name: <mcps_auth_policy>
  namespace: <mcp_ns>
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: <external_server>
  rules:
    response:
      success:
        headers:
          authorization:
            plain:
              expression: 'request.headers["authorization"]'
```

## MCPVirtualServer

```yaml
apiVersion: mcp.kuadrant.io/v1alpha1
kind: MCPVirtualServer
metadata:
  name: <dev_tools>
  namespace: <mcp_system>
spec:
  description: "Development and debugging tools"
  tools:
    - mcpserver1_devtool1
    - mcpserver2_headers1
  prompts:
    - test2_data_summary
```

Access with header: `X-Mcp-Virtualserver: <namespace>/<name>`

Virtual server filtering is the intersection of identity-based filtering
(from AuthPolicy) and virtual server tool list.

Verify:

```bash
oc get mcpvirtualserver -A

curl -X POST http://<gateway_url>/mcp \
  -H "Content-Type: application/json" \
  -H "mcp-session-id: $SESSION_ID" \
  -H "X-Mcp-Virtualserver: <namespace>/<name>" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

## MCP Gateway Authentication (JWT/OAuth)

AuthPolicy targeting Gateway listener for JWT validation:

```yaml
apiVersion: kuadrant.io/v1
kind: AuthPolicy
metadata:
  name: mcp-jwt-auth
  namespace: <gateway_ns>
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: <mcp_gateway>
    sectionName: <mcp_listener>
  defaults:
    when:
      - predicate: "!request.path.contains('/.well-known')"
    rules:
      authentication:
        'keycloak':
          jwt:
            issuerUrl: http://keycloak.example.com/realms/mcp
      response:
        unauthenticated:
          code: 401
          headers:
            'WWW-Authenticate':
              value: Bearer resource_metadata=http://mcp.example.com/.well-known/oauth-protected-resource
          body:
            value: |
              {"error": "Unauthorized", "message": "Authentication required."}
```

OAuth environment variables for MCP broker:

- `OAUTH_RESOURCE_NAME`: Human-readable MCP server name
- `OAUTH_RESOURCE`: Canonical URI for token audience validation
- `OAUTH_AUTHORIZATION_SERVERS`: Authorization server URL
- `OAUTH_BEARER_METHODS_SUPPORTED`: `header`, `body`, or `query`
- `OAUTH_SCOPES_SUPPORTED`: Comma-separated scopes

## User-Based Tool Filtering

When AuthPolicy injects identity info, the `x-mcp-authorized` header controls
which tools a user sees based on `resource_access` roles in their JWT claims.
Combined with MCPVirtualServer, the result is the intersection of both filters.
