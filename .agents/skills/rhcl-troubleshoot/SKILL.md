---
name: rhcl-troubleshoot
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhcl
  docs-version: "1.4"
  skill-group: "Connectivity Link"
description: >
  Use when the MaaS Gateway or its Connectivity Link components misbehave:
  responses held open, timeouts on every path, 429s, gateway memory pressure,
  Kuadrant operator restarts, missing usage metrics, AuthPolicy or
  TokenRateLimitPolicy not enforced, and — if adopted later — MCP gateway pods,
  routing, registration, authentication and authorization failures. Do NOT use
  for installing or upgrading (use rhcl-install or rhcl-update), or for model
  serving failures behind the gateway (use rhoai-troubleshoot).
---

# Connectivity Link troubleshooting

Thin skill: a routing table. The Connectivity Link 1.4 troubleshooting book
covers only the MCP gateway; MaaS Gateway failures seen in this demo are
documented in `docs/TROUBLESHOOTING.md`.

## When to use

- A MaaS consumer (Dev Spaces, playground, evaluations, migration workers)
  gets hangs, 4xx/5xx, or no metering.

## Symptom → where to look

| Symptom | Repo runbook (`docs/TROUBLESHOOTING.md#…`) | Official section |
|---|---|---|
| Response body arrives, connection never closes | `maas-gateway-holds-a-response-open-until-the-client-times-out` | [Release notes][relnotes] (wasm-shim fix not yet shipped in 1.4.3) |
| Every path times out; gateway OOMKills | `maas-gateway-times-out-on-every-path-rhcl-14x-drift` (historical 1.3 era) | [1.4.3 fixes][z143] |
| 429 | `maas-gateway-returns-429` | [TokenRateLimitPolicy][trlp] |
| Gateway near its memory limit | `maas-gateway-approaches-its-memory-limit` | — |
| Gateway not reachable | `maas-gateway-is-not-reachable` | — |
| Kuadrant controller restarts, new policies not enforced | `kuadrant-operator-controller-restarts-until-probes-time-out` | — |
| Usage panels show zeros | `usage-dashboard-shows-zeros-or-gaps-limitador-podmonitor-churn` | [Enable observability monitoring][obs] |
| External model stream resets | `external-model-streaming-resets-through-the-maas-gateway-connection-reset-by-server` | — |
| MCP gateway problems (not deployed today) | — | [Troubleshoot the MCP gateway][mcp-ts], [Isolated deployments][mcp-iso] |

## Procedure

1. Run the OpenShift safety guard in `AGENTS.md`; work read-only first.
2. Check policy and gateway status:

   ```bash
   oc get authpolicy,tokenratelimitpolicy -A
   oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.status.conditions}'
   oc get pods -n kuadrant-system
   oc get csv -n openshift-operators | grep -E 'rhcl|authorino|limitador|dns-operator'
   ```

3. Match the symptom to the table and follow that runbook's Diagnose/Recover.
4. A new failure mode goes into `docs/TROUBLESHOOTING.md` (symptom, cause,
   diagnose, recover), not into this skill.

## Pitfalls

- Generated MaaS policies are overwritten by the MaaS controller; fix the
  MaaS objects, not the policy (`rhcl-configure`).
- Exact-timeout disconnects usually point at a client, gateway or ELB timeout,
  not at the model; compare the duration with each configured timeout.

## Related skills

`rhcl-configure`, `rhcl-observability`, `rhcl-update`, `rhoai-maas-governance`, `rhoai-troubleshoot`.

[relnotes]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index
[z143]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index#rhcl-relnotes-1.4.3-z-stream_rhcl-release-notes
[trlp]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploy_red_hat_connectivity_link/index#con-about-token-based-rate-limiting_rhcl-config-deploy-gateway-policies
[obs]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/observability/index#rhcl-enable-observability-monitor_rhcl-observability
[mcp-ts]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/troubleshoot/index#mcp-gateway-troubleshooting
[mcp-iso]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/troubleshoot/index#mcp-gateway-ts-isolated-deployment
