---
name: rhcl-install-mcp
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhcl
  docs-version: "1.4"
  skill-group: "Connectivity Link"
description: >
  Use when planning to add the Connectivity Link MCP gateway to this demo: the
  mcp-gateway operator Subscription, the Gateway listener, the
  MCPGatewayExtension custom resource, ReferenceGrant, a custom HTTPRoute, and
  isolated gateway instances, as a GitOps component. Do NOT use for
  registering MCP servers or MCP auth policies (use rhcl-mcp-config), the
  Connectivity Link core operator (use rhcl-install), or deciding whether to
  adopt it (use rhcl-mcp-gateway).
---

# Connectivity Link MCP gateway install

Thin skill: the MCP gateway is not part of the demo today. This skill says how
an adoption must be shaped here and where the official procedure is.

## When to use

- A stage decides to adopt the MCP gateway (record that in its README first).

## Repo constraints for an adoption

| Constraint | Where | Official section |
|---|---|---|
| A new GitOps component with its own Argo CD Application, README (why/what/how, alignment table) and validate step | `.agents/rules/gitops.md`, `stages/<stage>/validate.sh` | — |
| The Subscription follows the operator policy: add `mcp-gateway` with its channel and minimum to `scripts/platform/check-operator-policy.py` | `scripts/platform/check-operator-policy.py` | [Install with OLM][olm] |
| Reuse the MaaS-style Gateway pattern (OpenShift Gateway controller, TLS terminate) rather than a second ingress design | `gitops/stages/040-governed-models-as-a-service/gateway-governance/gateway/` | [Create a Gateway][gateway], [Configure listeners][listeners] |

## Facts to verify against the docs at adoption time

- Package `mcp-gateway` from `redhat-operators` on the `preview` channel,
  with a single-namespace OperatorGroup ([Install with OLM][olm]).
- `MCPGatewayExtension` (`mcp.kuadrant.io/v1alpha1`): one per namespace and
  one per Gateway; the oldest wins a conflict ([About the extension][ext]).
- `spec.httpRouteManagement` defaults to `Enabled` and creates
  `mcp-gateway-route` for `/mcp`; set `Disabled` to own the route
  ([Custom HTTPRoute][route]).
- Cross-namespace Gateways need a ReferenceGrant ([ReferenceGrant][refgrant]).

## Procedure (verification after install)

Use the verification section of the guide ([Verify the endpoint][verify]);
check CSV `Succeeded`, `MCPGatewayExtension` `Ready`, the route, and the
EnvoyFilter, after the OpenShift safety guard in `AGENTS.md`.

## Official documentation (Connectivity Link 1.4)

| Topic | Section |
|---|---|
| OLM install | [Install the MCP gateway with OLM][olm] |
| Gateway and listeners | [Create a Gateway][gateway], [Configure listeners][listeners] |
| Extension CR | [About the extension][ext] |
| Routes and grants | [Custom HTTPRoute][route], [ReferenceGrant][refgrant] |
| Isolated instances | [Isolated MCP gateway instances][isolated] |
| Verify | [Verify the endpoint][verify] |

## Related skills

`rhcl-mcp-gateway`, `rhcl-mcp-config`, `rhcl-troubleshoot`.

[olm]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_the_mcp_gateway/index#proc-mcp-gateway-install-olm_mcp-gateway-install
[gateway]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_the_mcp_gateway/index#proc-config-mcp-gateway-gateway_mcp-gateway-install
[listeners]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_the_mcp_gateway/index#proc-config-mcp-gateway-listener_mcp-gateway-install
[ext]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_the_mcp_gateway/index#con-mcp-gateway-install-olm-ext-cr_mcp-gateway-install
[route]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_the_mcp_gateway/index#proc-mcp-gateway-custom-route_mcp-gateway-install
[refgrant]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_the_mcp_gateway/index#proc-mcp-gateway-referencegrant_mcp-gateway-install
[isolated]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_the_mcp_gateway/index#mcp-gateway-isolated-deployment
[verify]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_the_mcp_gateway/index#proc-mcp-gateway-config-verify_mcp-gateway-install
