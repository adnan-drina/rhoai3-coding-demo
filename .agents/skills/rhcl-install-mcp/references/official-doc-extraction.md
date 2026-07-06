# Official Doc Extraction

Use this extraction to keep MCP gateway installation content grounded in
official sources. Verify exact fields with `oc explain` before writing
manifests.

## MCP Gateway Operator Install

```bash
oc create ns <mcp_system>
oc apply -n <mcp_system> -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: mcp-gateway
spec:
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  name: mcp-gateway
  channel: preview
---
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: mcp-gateway
spec:
  targetNamespaces:
  - <mcp_system>
EOF
```

Verify:

```bash
oc wait --for=jsonpath={.status.installPlanRef.name} subscription mcp-gateway -n <mcp_system> --timeout=10s
ip=$(oc get subscription mcp-gateway -n <mcp_system> -o=jsonpath={.status.installPlanRef.name})
oc wait --for=condition=Installed installplan -n <mcp_system> ${ip} --timeout=60s
oc wait csv -n <mcp_system> -l operators.coreos.com/mcp-gateway.<mcp_system>="" --for=jsonpath='{.status.phase}'=Succeeded --timeout=5m
```

## Gateway Object with MCP Listener

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: mcp-gateway
  namespace: gateway-namespace
spec:
  gatewayClassName: openshift-default
  listeners:
    - name: mcps
      hostname: mcp.example.com
      port: 8080
      protocol: HTTP
      allowedRoutes:
        namespaces:
          from: All
    - name: https
      hostname: mcp.apps.openshift.example.com
      port: 443
      protocol: HTTPS
      allowedRoutes:
        namespaces:
          from: All
      tls:
        certificateRefs:
          - group: ''
            kind: Secret
            name: default-ingress-cert
        mode: Terminate
```

The `spec.listeners[].name` value must match `MCPGatewayExtension`
`spec.targetRef.sectionName`.

## MCPGatewayExtension CR

```yaml
apiVersion: mcp.kuadrant.io/v1alpha1
kind: MCPGatewayExtension
metadata:
  name: <mcp_gateway_one>
  namespace: <mcp_system>
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: <mcp_gateway>
    namespace: <gateway_system>
    sectionName: mcps
  httpRouteManagement: Enabled
```

Key fields:

| Field | Required | Description |
|-------|----------|-------------|
| `spec.targetRef.sectionName` | Yes | Listener name on Gateway |
| `spec.httpRouteManagement` | No | `Enabled` (default) or `Disabled` |
| `spec.publicHost` | No | Override public hostname |
| `spec.privateHost` | No | Override internal hair-pin host |
| `spec.backendPingIntervalSeconds` | No | 10–7200, default 60 |
| `spec.trustedHeadersKey.secretName` | No | PEM public key secret |
| `spec.trustedHeadersKey.generate` | No | `Enabled` or `Disabled` |
| `spec.sessionStore.secretName` | No | Redis connection string secret |
| `spec.urlElicitation` | No | `Enabled` or `Disabled` |

Verify:

```bash
oc wait --for=condition=Ready mcpgatewayextension/<name> -n <mcp_system>
oc get httproute mcp-gateway-route -n <mcp_system>
oc get envoyfilter -n <gateway_namespace> -l app.kubernetes.io/managed-by=mcp-gateway-controller
```

## Session Store Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-session-store
  namespace: <mcp_system>
  labels:
    mcp.kuadrant.io/secret: "true"
type: Opaque
stringData:
  CACHE_CONNECTION_STRING: "redis://<password>@<host>:<port>/<db>"
```

## ReferenceGrant (Cross-Namespace)

Required when MCPGatewayExtension and Gateway are in different namespaces:

```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-mcp-extension
  namespace: <gateway_namespace>
spec:
  from:
    - group: mcp.kuadrant.io
      kind: MCPGatewayExtension
      namespace: <mcp_system>
  to:
    - group: gateway.networking.k8s.io
      kind: Gateway
```

## Constraints

- Each namespace can have only one MCPGatewayExtension CR.
- Each Gateway can have only one MCPGatewayExtension targeting it.
- If multiple target the same Gateway, the oldest wins; newer ones are
  marked conflicted.
- MCP gateway is Technology Preview (not production-supported).
