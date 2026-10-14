---
name: rhcl-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhcl
  docs-version: "1.4"
  skill-group: "Connectivity Link"
description: >
  Use when checking which Connectivity Link 1.4 release fixes or breaks
  something the demo depends on: the 1.4.0 deprecation, the 1.4.1-1.4.3
  z-stream fixes (wasm-shim host matching, EnvoyFilter targeting, operator
  memory leak, large request bodies, AuthConfig v1beta3), Technology Preview
  status (MCP gateway, GRPCRoute), and known issues. Do NOT use for concepts
  (use rhcl-about), the update procedure (use rhcl-update), or MCP gateway
  architecture (use rhcl-mcp-gateway).
---

# Connectivity Link release notes

Thin skill: what matters to this demo, with links to the 1.4 release notes.
Re-read the notes themselves before acting; they are updated per z-stream.

## When to use

- Deciding whether to raise the qualified minimum in
  `scripts/platform/check-operator-policy.py`.
- A MaaS Gateway symptom might match a fixed or known issue.

## Relevant to this demo

| Release | Item (Jira) | Why it matters here | Section |
|---|---|---|---|
| 1.4.0 | Deprecated (auth failures, API-key errors, gateway instability, memory pressure) | The policy minimum is 1.4.3; never qualify 1.4.0 | [About this release][about] |
| 1.4.1 | AuthConfig `v1beta3` served, `v1beta2` removed (CONNLINK-1131) | Upgrades no longer blocked by CEL predicates | [1.4.1][z141] |
| 1.4.2 | Request bodies over 1 MB corrupted next to other body filters (CONNLINK-1311) | Large prompts through the MaaS Gateway | [1.4.2][z142] |
| 1.4.3 | Case-insensitive host matching in wasm-shim (CONNLINK-1448); EnvoyFilter `workloadSelector` instead of namespace-wide `targetRef` (CONNLINK-1510); operator reconcile loop causing OOMKills and 503 (CONNLINK-1567) | The installed baseline; gateway stability | [1.4.3][z143] |
| known issue | First request after a Limitador restart with Redis storage is not limited (CONNLINK-856) | Applies only with Redis storage; Git sets no Limitador storage (the operator creates `limitador` from the `Kuadrant` CR) | [Known issues][known] |
| Tech Preview | MCP gateway, GRPCRoute policy attachment | Neither is used by the demo | [Technology Preview][tp] |

Not in the release notes but affecting this demo: 1.4.3 ships wasm-shim
0.14.2, which holds responses lacking `usage.total_tokens` open
(Kuadrant/wasm-shim#425, fixed in 0.14.3). See
`docs/TROUBLESHOOTING.md#maas-gateway-holds-a-response-open-until-the-client-times-out`.

## Procedure

1. Open the [z-stream list][zstream] and compare it with the installed CSV
   (`rhcl-update` has the command).
2. Record any fix the repo depends on next to the minimum in the
   operator-policy change and in the Stage 040 README.

## Related skills

`rhcl-update`, `rhcl-troubleshoot`, `rhoai-maas-governance`.

[about]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index#rhcl-relnotes-about_rhcl-release-notes
[tp]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index#rhcl-relnotes-tech-preview_rhcl-release-notes
[known]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index#rhcl-relnotes-known-issues_rhcl-release-notes
[zstream]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index#rhcl-relnotes-z-stream_rhcl-release-notes
[z141]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index#rhcl-relnotes-1.4.1-z-stream_rhcl-release-notes
[z142]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index#rhcl-relnotes-1.4.2-z-stream_rhcl-release-notes
[z143]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index#rhcl-relnotes-1.4.3-z-stream_rhcl-release-notes
