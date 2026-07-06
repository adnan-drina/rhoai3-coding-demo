# Official Doc Extraction

Use this extraction to ground Connectivity Link troubleshooting in official
sources. Follow diagnostic commands in order for each symptom.

## MCP Gateway Pods Not Starting

Common pod states and actions:

| State | Action |
|---|---|
| `ImagePullBackOff` | Check image repository access and credentials |
| `CrashLoopBackOff` | Check logs for application errors |
| `Pending` | Check resource availability and node capacity |
| Init Container Failure | Check RBAC permissions |

```bash
oc get pods -n <mcp_system>
oc describe pod -n <mcp_system> <pod_name>
oc logs -n <mcp_system> <pod_name>
```

## Gateway Listener Troubleshooting

Symptom: Connection Refused/Timeout — port not open, load balancer has not
assigned an IP, or TLS handshake failing.

```bash
oc get gateway -A
oc describe gateway <gateway_name> -n <gateway_system>
oc get gateway <gateway_name> -n <gateway_system> -o yaml | grep -A 10 listeners
oc get gateway <gateway_name> -n <gateway_system> -o jsonpath='{range .spec.listeners[*]}{.name}{"\t"}{.hostname}{"\t"}{.port}{"\n"}{end}'
oc get pods -n <gateway_system> -l gateway.istio.io/managed=istio.io-gateway-controller
oc get gateway -A -o yaml | grep "port:"
```

Ensure Gateway has `Accepted` and `Programmed` conditions set to `True`.
Verify `hostname` in Listener matches DNS or hosts configuration.

## Traffic Not Reaching Backend MCP Server

Symptom: HTTP 404 when HTTPRoute exists.

```bash
oc get httproute -A
oc describe httproute <route_name> -n <namespace>
oc get httproute <route_name> -n <namespace> -o yaml | grep -A 5 parentRefs
oc get gateway <gateway_name> -n <gateway_namespace> -o jsonpath='{range .spec.listeners[*]}{.name}{": "}{.allowedRoutes.namespaces.from}{"\n"}{end}'
```

Check that `allowedRoutes.namespaces` in Gateway allows the HTTPRoute namespace.

## Requests Failing or Bypassing the Router

Symptom: 503 errors or policies bypassed — EnvoyFilter not applied properly.

EnvoyFilter is auto-created by MCP gateway controller when MCPGatewayExtension
is Ready. Do not manually edit or delete it.

If EnvoyFilter is absent: Gateway CR status is not Programmed, labels mismatch,
or MCP controller is crashing.

```bash
oc get gateway -A
oc get mcpgatewayextension -A
oc get referencegrant <name> -n <gateway_system> -o yaml
oc describe httproute <name> -n <namespace>
oc logs -n <mcp_system> deployment/mcp-gateway-controller
oc get envoyfilter -n <gateway_namespace> -l app.kubernetes.io/managed-by=mcp-gateway-controller
oc describe envoyfilter -n <gateway_namespace> -l app.kubernetes.io/managed-by=mcp-gateway-controller
oc get pods -n <gateway_namespace> --show-labels
```

Verify workloadSelector labels match Gateway pods.

Check filter chain binding:

```bash
oc port-forward deploy/<gateway_deployment_name> -n <gateway_system> 15000:15000
curl -s localhost:15000/listeners
```

Force configuration reload:

```bash
oc rollout restart deployment/<gateway_name>-istio -n <gateway_namespace>
```

## MCPGatewayExtension Not Ready

Common conditions:

| Condition | Cause | Fix |
|---|---|---|
| `InvalidMCPGatewayExtension` | `targetRef` points to nonexistent Gateway or typo in kind/group | Fix targetRef |
| `ReferenceGrantRequired` | Extension in different namespace than Gateway | Apply ReferenceGrant in Gateway namespace |
| `Conflict` | Another extension already targets the Gateway | Remove duplicate |

```bash
oc get mcpgatewayextension -n <namespace>
oc get mcpgatewayextension -A
oc get gateway -n <gateway_namespace>
oc describe mcpsr <mcpsr_name> -n <mcpsr_namespace>
```

Only one MCPGatewayExtension per Gateway is allowed.

## On-Prem MCP Server Registration Issues

Symptom: tools not appearing in `tools/list`.

```bash
oc get mcpsr -A
oc describe mcpserverregistration <name> -n <namespace>
oc get mcpserverregistration <name> -n <namespace> -o jsonpath='{.spec.targetRef.name}{"\n"}{.spec.targetRef.namespace}{"\n"}'
oc get httproute <httproute_name> -n <httproute_namespace>
oc get mcpserverregistration <name> -n <namespace> -o jsonpath='{.status.conditions[?(@.type=="Accepted")]}'
```

Check backend health:

```bash
oc get pods -n <mcpsr_namespace>
oc get svc -n <namespace> <service_name>
oc get endpoints <service_name> -n <namespace>
oc describe httproute <route_name>
```

Test backend directly:

```bash
oc debug deployment/<mcpsr_name> -it
curl -X POST https://localhost:<port>/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

Check tool prefix:

```bash
oc get mcpsr <name> -n <namespace> -o yaml | grep toolPrefix
oc logs -n <mcp_system> deployment/mcp-gateway-controller | grep prefix
```

If `failed to generate prefix` appears, there is an error in MCPServerRegistration
metadata or a conflict.

Restart broker after MCPServerRegistration changes:

```bash
oc rollout restart deployment/<mcp_gateway> -n <mcp_system>
```

## External MCP Server Connectivity Issues

Symptom: 502 Bad Gateway or 403 Forbidden.

```bash
oc get serviceentry -n <namespace>
oc describe serviceentry <name> -n <namespace>
oc get destinationrule -n <namespace>
oc describe destinationrule <name> -n <namespace>
```

Ensure DestinationRule `host` values match ServiceEntry hosts exactly.

Test DNS and connectivity:

```bash
oc run -it --rm debug --image=<image> --restart=Never -- nslookup <external_hostname>
oc run -it --rm debug --image=<image> --restart=Never -- curl -v https://<external_hostname>
```

## External MCP Server Authentication Issues

Symptom: 401 or 403 from external server.

```bash
oc get secret <name> -n <namespace> --show-labels
oc get secret <name> -n <namespace> -o yaml
oc get mcpsr <name> -n <namespace> -o yaml | grep -A 3 credentialRef
oc logs -n <mcp_system> deployment/mcp-gateway | grep -i auth
```

Ensure Secret has label `mcp.kuadrant.io/secret: "true"`.
Ensure HTTPRoute has `URLRewrite` filter for external hostname.

## MCP Gateway Authentication Issues

### OAuth Discovery Not Working

```bash
curl https://<mcp_hostname>/.well-known/oauth-protected-resource
oc get httproute <route_name> -n <mcp_system> -o json | jq -r '.spec.rules[].matches[].path.value | select(. == "/.well-known/oauth-protected-resource")'
oc describe authpolicy <name> -n <namespace>
curl -o /dev/null -s -w "%{https_code}\n" https://<mcp_hostname>/.well-known/oauth-protected-resource
```

Response codes:

- `200`: exclusion exists and matches
- `401`: AuthPolicy still demanding token for this path
- `404`: exclusion may work but HTTPRoute does not route this path

### JWT Validation Failing (Valid Tokens Rejected with 401)

```bash
oc get authpolicy -A
oc describe authpolicy <name> -n <namespace>
oc logs -n <kuadrant_system> -l authorino-resource=authorino
echo "<token>" | cut -d. -f2 | base64 -d | jq
oc exec -n <kuadrant_system> deployment/authorino -- curl -s https://auth.provider.com/realms/mcp/.well-known/openid-configuration
```

### WWW-Authenticate Header Missing on 401

Means AuthPolicy is not properly configured. Test with verbose output:

```bash
curl -v https://<mcp_hostname>/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

## MCP Gateway Authorization Issues

### Authenticated User Getting 403

```bash
oc get authpolicy <name> -n <namespace> -o yaml | grep -A 20 authorization
oc logs -n <kuadrant_system> -l authorino-resource=authorino | grep -i authz
```

### Authorization Checks Not Enforced

```bash
oc describe authpolicy <name> -n <namespace>
oc get authpolicy <name> -n <namespace> -o yaml | grep -A 5 targetRef
```

Verify AuthPolicy `targetRef` matches Gateway name and namespace:

```bash
echo "--- AuthPolicy Targets ---" && \
oc get authpolicy -n <mcp_system> -o jsonpath='{range .items[*]}{.metadata.name}{"\t targets -> \t"}{.spec.targetRef.kind}{"/"}{.spec.targetRef.name}{"\n"}{end}' && \
echo "--- Actual Gateways ---" && \
oc get gateway -n <mcp_system> -o custom-columns=NAME:.metadata.name
```

Check `sectionName` matches Gateway listener name.

Verify Kuadrant Operator pods are running:

```bash
oc get pods -n <kuadrant_system>
```

Expected pods: `authorino-*`, `dns-operator-controller-manager-*`,
`kuadrant-operator-controller-manager-*`, `limitador-*`.

- `authorino-*` in CrashLoopBackOff: cannot reach OIDC issuer or invalid config
- `kuadrant-operator-controller-manager-*` down: AuthPolicy changes not reconciled

### CEL Evaluation Errors

```bash
oc logs -n <kuadrant_system> -l authorino-resource=authorino | grep -i cel
```
