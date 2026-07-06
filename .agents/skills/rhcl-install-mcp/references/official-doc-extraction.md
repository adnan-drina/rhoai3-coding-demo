# Official Doc Extraction — rhcl-install-mcp

Source: Red Hat Connectivity Link 1.3 — Installing the MCP gateway

## Technology Preview

MCP gateway is a Technology Preview feature only. Not supported with production
SLAs. Not functionally complete.

## Prerequisites

- OpenShift Container Platform installed
- OpenShift CLI (`oc`) installed
- cluster-admin privileges

## Installation via OLM (CLI)

```bash
oc create ns mcp-system

oc apply -n mcp-system -f - <<EOF
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
  - mcp-system
EOF
```

### Verify install

```bash
oc wait --for=jsonpath={.status.installPlanRef.name} \
  subscription mcp-gateway -n mcp-system --timeout=10s
ip=$(oc get subscription mcp-gateway -n mcp-system \
  -o=jsonpath={.status.installPlanRef.name})
oc wait --for=condition=Installed installplan -n mcp-system ${ip} --timeout=60s
oc wait csv -n mcp-system \
  -l operators.coreos.com/mcp-gateway.mcp-system="" \
  --for=jsonpath='{.status.phase}'=Succeeded --timeout=5m
```

## Gateway object

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: mcp-gateway
  namespace: gateway-namespace
spec:
  gatewayClassName: openshift-default
  listeners:
    - name: http
      port: 80
      protocol: HTTP
      allowedRoutes:
        namespaces:
          from: All
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

On OCP, `spec.listeners.tls.certificateRefs` can specify the Secret containing
the default wildcard certificate for the OpenShift Ingress controller.

## Configuring listeners

### MCP listener

```bash
oc patch gateway mcp-gateway -n gateway-namespace --type='json' -p='[
  {
    "op": "add",
    "path": "/spec/listeners/-",
    "value": {
      "name": "mcps",
      "hostname": "mcp.example.com",
      "port": 8080,
      "protocol": "HTTP",
      "allowedRoutes": { "namespaces": { "from": "All" } }
    }
  }
]'
```

### HTTPS listener

```bash
oc patch gateway mcp-gateway -n gateway-namespace --type='json' -p='[
  {
    "op": "add",
    "path": "/spec/listeners/-",
    "value": {
      "name": "https",
      "hostname": "mcp.example.com",
      "port": 443,
      "protocol": "HTTPS",
      "tls": {
        "mode": "Terminate",
        "certificateRefs": [{"name": "mcp-tls-secret", "kind": "Secret"}]
      },
      "allowedRoutes": { "namespaces": { "from": "All" } }
    }
  }
]'
```

## MCPGatewayExtension CR

### Key constraints

- One MCPGatewayExtension per namespace
- One MCPGatewayExtension per Gateway object
- Oldest wins if conflict; newer ones marked as conflicted
- `spec.targetRef.sectionName` must match Gateway listener name
- Auto-creates HTTPRoute `mcp-gateway-route` routing `/mcp` to broker port 8080

```yaml
apiVersion: mcp.kuadrant.io/v1alpha1
kind: MCPGatewayExtension
metadata:
  name: mcp-gateway-ext
  namespace: mcp-system
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: mcp-gateway
    namespace: gateway-namespace
    sectionName: mcps
  httpRouteManagement: Enabled
```

### Apply and verify

```bash
oc apply -f mcp-gateway-ext.yaml
oc wait --for=condition=Ready mcpgatewayextension/mcp-gateway-ext \
  -n mcp-system --timeout=60s
oc get httproute mcp-gateway-route -n mcp-system
oc get envoyfilter -n gateway-namespace \
  -l app.kubernetes.io/managed-by=mcp-gateway-controller
```

## Auto-created HTTPRoute

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: mcp-gateway-route
  namespace: mcp-system
spec:
  parentRefs:
  - name: mcp-gateway
    namespace: gateway-namespace
    sectionName: mcps
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /mcp
    backendRefs:
    - name: mcp-gateway
      port: 8080
```

## Cross-namespace ReferenceGrant

Required when MCPGatewayExtension is in a different namespace than the Gateway.

```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-team-a
  namespace: gateway-namespace
spec:
  from:
    - group: mcp.kuadrant.io
      kind: MCPGatewayExtension
      namespace: mcp-system
  to:
    - group: gateway.networking.k8s.io
      kind: Gateway
```

## Custom HTTPRoute (CORS, OAuth)

Disable auto-route first:

```bash
oc patch mcpgatewayextension mcp-gateway-ext -n mcp-system \
  --type merge -p '{"spec":{"httpRouteManagement":"Disabled"}}'
```

Then create a custom route with CORS headers and OAuth well-known path:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: mcp-route-custom
  namespace: mcp-system
spec:
  parentRefs:
    - name: mcp-gateway
      namespace: gateway-namespace
      sectionName: mcps
  hostnames:
    - mcp.example.com
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /mcp
      filters:
        - type: ResponseHeaderModifier
          responseHeaderModifier:
            add:
              - name: Access-Control-Allow-Origin
                value: "*"
              - name: Access-Control-Allow-Methods
                value: "GET, POST, PUT, DELETE, OPTIONS, HEAD"
      backendRefs:
        - name: mcp-gateway
          port: 8080
    - matches:
        - path:
            type: PathPrefix
            value: /.well-known/oauth-protected-resource
      backendRefs:
        - name: mcp-gateway
          port: 8080
```

## DNS management

Options for hostname resolution:
- OCP Cluster Ingress Operator (cloud DNS, Gateway in `openshift-ingress` ns)
- MetalLB + ExternalDNS Operator (non-cloud environments)
- Connectivity Link DNSPolicy CR targeting the Gateway

## Verify MCP endpoint

```bash
curl -X POST http://mcp.example.com:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize"}'
```

Expected response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-11-25",
    "capabilities": {"tools": {"listChanged": true}},
    "serverInfo": {"name": "Kuadrant MCP Gateway", "version": "0.6.0"}
  }
}
```

## Known issue (v0.6.0)

When using OAuth, set `spec.httpRouteManagement: Disabled` in the
MCPGatewayExtension CR and create a custom HTTPRoute. See Connectivity Link
1.3.3 release notes for details.
