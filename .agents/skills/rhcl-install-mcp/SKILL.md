---
name: rhcl-install-mcp
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Install and configure the MCP gateway component of Red Hat Connectivity Link
  1.3 on single or multiple OpenShift Container Platform clusters. Use when
  installing the MCP gateway Operator, creating Gateway objects with MCP
  listeners, deploying MCPGatewayExtension CRs, configuring cross-namespace
  ReferenceGrants, custom HTTPRoutes, or verifying MCP endpoint accessibility.
  Do NOT use for registering MCP servers or creating auth policies (use
  rhcl-mcp-config). Do NOT use for RHCL core installation (use rhcl-install).
---

# Red Hat Connectivity Link 1.3 — MCP Gateway Installation

## Technology Preview notice

MCP gateway is a Technology Preview feature. It is not supported with Red Hat
production SLAs and might not be functionally complete.

## When to use

- Installing the MCP gateway Operator via OLM
- Creating a Gateway object with MCP listeners
- Configuring MCP gateway listeners (HTTP, HTTPS, MCP)
- Applying MCPGatewayExtension CR to finish deployment
- Creating ReferenceGrant for cross-namespace isolation
- Creating custom HTTPRoute objects (CORS, OAuth paths)
- DNS management for MCP gateway hostnames
- Verifying MCP endpoint accessibility

## Key facts

- Operator: `mcp-gateway`, channel: `preview`, source: `redhat-operators`
- MCPGatewayExtension API: `mcp.kuadrant.io/v1alpha1`
- Broker service port: 8080
- MCP endpoint path: `/mcp`
- MCP protocol version: `2025-11-25`
- One MCPGatewayExtension per namespace; one per Gateway object
- Auto-creates HTTPRoute named `mcp-gateway-route` (unless disabled)
- sectionName in MCPGatewayExtension must match Gateway listener name

## Installation — CLI

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

## Validation — operator install

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

## Gateway object with MCP listener

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
```

## MCPGatewayExtension CR

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

## Validation — MCPGatewayExtension ready

```bash
oc wait --for=condition=Ready mcpgatewayextension/mcp-gateway-ext \
  -n mcp-system --timeout=60s
oc get httproute mcp-gateway-route -n mcp-system
```

## Cross-namespace ReferenceGrant

```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-mcp-system
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

## Verify MCP endpoint

```bash
curl -X POST http://mcp.example.com:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize"}'
```

Expected: `{"jsonrpc":"2.0","id":1,"result":{...,"serverInfo":{"name":"Kuadrant MCP Gateway","version":"0.6.0"}}}`

## References

- `references/source-capture.md` — source provenance
- `references/official-doc-extraction.md` — full extraction
- Official: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html-single/installing_the_mcp_gateway/index
