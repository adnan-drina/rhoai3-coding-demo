---
name: rhcl-configure
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhcl
  docs-version: "1.4"
  skill-group: "Connectivity Link"
description: >
  Use when reading, reviewing, or debugging Connectivity Link policies on the
  MaaS Gateway: the MaaS-generated AuthPolicy and TokenRateLimitPolicy objects,
  how TokenRateLimitPolicy meters usage.total_tokens, policy status conditions,
  default-deny, and when a hand-written AuthPolicy, RateLimitPolicy,
  TLSPolicy, DNSPolicy, GRPCRoute or PlanPolicy would be appropriate. Do NOT
  use for operator installation (use rhcl-install), MaaS subscriptions and
  API keys (use rhoai-maas-governance), or MCP server policies (use
  rhcl-mcp-config).
---

# Connectivity Link policies

Thin skill: repo decisions and pitfalls here, product behavior in the linked
Connectivity Link 1.4 sections.

## When to use

- A model call is denied, unmetered, or limited unexpectedly.
- Someone proposes writing a policy object into Git.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| No policy objects in Git: the OpenShift AI MaaS controller generates `AuthPolicy maas-gateway-auth` and `TokenRateLimitPolicy` objects (`gateway-default-deny`, `maas-trlp-<model>`) from MaaS subscriptions | not in Git; `gitops/stages/040-governed-models-as-a-service/maas-operators/README.md` ("Objects not in Git") | [TokenRateLimitPolicy][trlp]; see `rhoai-maas-governance` |
| Limits are expressed as `MaaSSubscription` token limits, not RateLimitPolicy | `gitops/stages/040-governed-models-as-a-service/model-access/` | see `rhoai-maas-governance` |
| Every external model uses `apiFormat: openai-chat` so responses carry `usage.total_tokens` for metering | `gitops/stages/040-governed-models-as-a-service/external-models/` | [How token rate limiting works][trlp-how] |
| The MaaS Gateway terminates TLS with the cert-manager ingress certificate; no TLSPolicy, no DNSPolicy | `gitops/stages/040-governed-models-as-a-service/gateway-governance/gateway/` | [Set a TLS policy][tls] (not used) |

## Procedure

1. Inspect, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get authpolicy,tokenratelimitpolicy -A
   oc get tokenratelimitpolicy <name> -n <ns> -o jsonpath='{.status.conditions}'
   oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.status.conditions}'
   ```

   Healthy policies report `Accepted` and `Enforced`; the Gateway reports
   `Accepted` and `Programmed`.
2. To change who may call a model or how much, change the MaaS objects
   (`rhoai-maas-governance`), never the generated policies; the controller
   overwrites them.
3. A hand-written policy needs a README decision first. Use `kuadrant.io/v1`
   for AuthPolicy, RateLimitPolicy, TLSPolicy and DNSPolicy and
   `kuadrant.io/v1alpha1` for TokenRateLimitPolicy, as in the
   [deploy guide][deploy]; check the schema with `oc explain`.

## Pitfalls

- Connectivity Link 1.4.3 ships wasm-shim 0.14.2: a response without OpenAI
  `usage.total_tokens` (Anthropic Messages, error bodies, some SSE streams) is
  held open until the client times out. See
  `docs/TROUBLESHOOTING.md#maas-gateway-holds-a-response-open-until-the-client-times-out`.
- 429 from the gateway is usually an exhausted subscription budget:
  `docs/TROUBLESHOOTING.md#maas-gateway-returns-429`.
- GRPCRoute policy attachment is Technology Preview in 1.4 and excludes
  TokenRateLimitPolicy ([GRPCRoute][grpc]).

## Official documentation (Connectivity Link 1.4)

| Topic | Section |
|---|---|
| Default deny AuthPolicy | [Set the default AuthPolicy][authdeny] |
| Default rate limit | [Set a default rate-limit policy][rlp] |
| Token-based rate limiting | [About TokenRateLimitPolicy][trlp], [How it works][trlp-how] |
| Routes and overrides | [Connect and secure APIs][connect] |
| GRPCRoute (TP) | [GRPCRoute policy attachment][grpc] |
| Tiered plans (not used) | [PlanPolicy][plan] |
| API management console (not used) | [Develop APIs with the web console][webconsole] |

## Related skills

`rhoai-maas-governance`, `rhcl-observability`, `rhcl-troubleshoot`, `ocp-ingress-gateway-routes`.

[deploy]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploy_red_hat_connectivity_link/index
[authdeny]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploy_red_hat_connectivity_link/index#proc-set-default-auth-policy_rhcl-config-deploy-gateway-policies
[rlp]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploy_red_hat_connectivity_link/index#proc-set-default-rate-limit-policy_rhcl-config-deploy-gateway-policies
[trlp]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploy_red_hat_connectivity_link/index#con-about-token-based-rate-limiting_rhcl-config-deploy-gateway-policies
[trlp-how]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploy_red_hat_connectivity_link/index#rhcl-token-rate-limiting_rhcl-config-deploy-gateway-policies
[tls]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploy_red_hat_connectivity_link/index#proc-set-tls-policy_rhcl-config-deploy-gateway-policies
[connect]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploy_red_hat_connectivity_link/index#connect-secure-apis-services
[grpc]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploy_red_hat_connectivity_link/index#con-about-grpc-support_connect-secure-apis-services
[plan]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploy_red_hat_connectivity_link/index#rhcl-planpolicy
[webconsole]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/develop_apis_with_the_web_console/index
