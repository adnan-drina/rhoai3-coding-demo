---
name: ocp-lightspeed-configure
metadata:
  author: rhoai3-coding-demo
  version: 3.0.0
  product: ocp_lightspeed
  docs-version: "2.0"
  skill-group: "OpenShift Platform"
description: >
  Use when someone wants to change OpenShift Lightspeed's OLSConfig on the demo
  cluster: LLM provider and credentials Secret, user access (RBAC), query
  filters, custom knowledge (RAG), cluster interaction and MCP servers, token
  quotas, conversation persistence, or audit logging. Do NOT use for concepts
  (use ocp-lightspeed-about), installation (use ocp-lightspeed-install), or an
  unready service (use ocp-lightspeed-troubleshoot).
---

# OpenShift Lightspeed configuration

Thin skill: repo decisions here, OLSConfig fields and procedures in the linked
sections. Take field names from the OLSConfig API reference, never from memory.

## When to use

- A request to point Lightspeed at another provider or model.
- Granting users access, or limiting what Lightspeed sends or can do.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| The OLSConfig is in Git since 2026-10-27 (`040-openshift-lightspeed`); the provisioner still owns the operator and the Azure credentials Secret `azure-api-keys` | `gitops/stages/040-governed-models-as-a-service/040-openshift-lightspeed/olsconfig.yaml` | [Configuring and deploying][configure] |
| Provider credentials are corrected only by their owner through the native Secret path; never rotated blindly or committed | `docs/TROUBLESHOOTING.md` (Lightspeed API unready) | [Create the credentials secret (CLI)][secret-cli] |
| Default provider `qwen-maas`: type `rhoai_vllm`, `https://maas.<cluster-domain>/v1` (patched by Stage 040 `deploy.sh`), model `publishers/internal-models/models/qwen3-8-27b`, Secret `qwen-maas-api-keys` key `apitoken` minted by a Sync-hook Job on MaaS subscription `openshift-lightspeed`; the gateway certificate is publicly trusted, so no CA ConfigMap. Azure stays as a second provider, its endpoint read from the live OLSConfig, never committed | `040-openshift-lightspeed/`, `040-model-access/openshift-lightspeed-access.yaml` | [OLSConfig `.spec.llm.providers[]`][api-providers] |
| Fallback `nemotron-maas` (`rhoai_vllm`, same URL, model `nemotron-3-ultra-550b-a55b`, same subscription and key, copied by the Job into its own Secret `nemotron-maas-api-keys`). Lightspeed has one default and no failover, so `stages/040-governed-models-as-a-service/lightspeed/select-model.sh nemotron\|qwen` moves the default by patching the Argo CD Application (self-heal reverts a direct OLSConfig edit); deploy returns to Qwen. GPT-6 Luna is not usable: `rhoai_vllm` always sends `top_p` (Luna 400), `openai` uses the Responses API the Luna MaaS route lacks | `040-openshift-lightspeed/olsconfig.yaml`, `stages/040-governed-models-as-a-service/lightspeed/` | [Configuring and deploying][configure], [`.spec.llm.providers[]`][api-providers] |

## Procedure

1. Confirm who owns the change: anything in the OLSConfig is the
   provisioner's unless a decision moves Lightspeed into Git
   (`ocp-lightspeed-install`).
2. For a sanctioned change, follow the linked section and the API reference;
   then verify per [Verifying the deployment][verify].
3. Treat provider credentials, RBAC and MCP server settings as sensitive
   (`AGENTS.md`, Security and privacy): placeholders only in Git and chat.

## Pitfalls

- Access is not granted to every authenticated user; see the
  [RBAC framework][rbac] before announcing Lightspeed to workshop users.
- Cluster interaction (`introspectionEnabled: true` here) lets the assistant
  read live cluster state with the user's identity; read
  [cluster interaction][cluster] and [authentication flow][introspection-auth].
  Since 2.0.1 the OpenShift MCP server also offers write tools; the 2.0
  [security defaults][security-defaults] keep human approval for non-read
  operations (`spec.ols.toolsApprovalConfig`) and
  [tool-result safety inspection][tool-inspection] on. Keep both.
- Autonomous agents (`agentic.openshift.io` LLMProvider, Agent and
  ApprovalPolicy; Technology Preview) need OpenShift 5.0, see
  [autonomous agents][agentic]. On this 4.22 cluster the operator's agentic
  console stays unready with `UnsupportedOCPVersion`; the demo configures no
  agents.
- A provider behind a private CA needs the trusted-CA configuration; see
  [trusted CA for the LLM][trusted-ca].
- Two providers cannot share one `credentialsSecretRef`: the operator mounts
  one volume per provider Secret and its Deployment update fails with a
  duplicate volume name. Give each provider its own Secret.
- The readiness probe calls the default model: a parked or failing default makes
  `ApiReady=False` and the console panel silent, whatever other providers exist.
- A provider type fixes the request shape: `rhoai_vllm`/`rhelai_vllm` add
  `top_p 0.95` and `frequency_penalty 1.03`; `openai` uses the Responses API
  (no OLSConfig switch). Probe a candidate model with that exact shape first.

## Official documentation (OpenShift Lightspeed, "2.0" set)

| Topic | Section |
|---|---|
| Credentials and custom resource | [Secret (CLI)][secret-cli], [custom resource (CLI)][cr-cli] |
| TLS | [Trusted CA for the LLM][trusted-ca], [custom TLS certificates][tls] |
| Access | [RBAC framework][rbac], [route and user access][route] |
| Data redaction | [Filtering and redacting information][filters] |
| Custom knowledge | [Custom documentation (BYO knowledge)][byok] |
| Cluster interaction, MCP | [Live cluster state][cluster], [custom MCP server][mcp], [tool approvals][approvals] |
| Security defaults | [Defaults by deployment mode][security-defaults], [tool-result safety inspection][tool-inspection] |
| Autonomous agents (OpenShift 5.0) | [Deploying autonomous agents][agentic] |
| Quotas | [Token quota limits][quotas] |
| Persistence | [Conversation history][postgres] |
| Field reference | [OLSConfig API][api], [`.spec.llm.providers[]`][api-providers] |
| Audit | [Audit logging and tracing][audit] |

## Related skills

`ocp-lightspeed-about`, `ocp-lightspeed-troubleshoot`, `rhoai-maas-governance`,
`ocp-security-rbac-scc`.

[configure]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-configuring-openshift-lightspeed
[secret-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-creating-the-credentials-secret-using-cli_ols-configuring-openshift-lightspeed
[cr-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-creating-lightspeed-custom-resource-file-using-cli_ols-configuring-openshift-lightspeed
[trusted-ca]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-configuring-lightspeed-with-a-trusted-ca-certificate-for-the-llm_ols-configuring-openshift-lightspeed
[tls]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#configuring-custom-tls-certificates_ols-configuring-openshift-lightspeed
[verify]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-verifying-openshift-lightspeed-deployment_ols-configuring-openshift-lightspeed
[rbac]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-about-lightspeed-and-role-based-access-control_ols-configuring-openshift-lightspeed
[route]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-proc-expose-the-ols-service-by-using-a-route_ols-configuring-openshift-lightspeed
[filters]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-filtering-and-redacting-information_ols-configuring-openshift-lightspeed
[byok]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#about-the-byo-knowledge-tool_ols-configuring-openshift-lightspeed
[cluster]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#about-cluster-interaction_ols-configuring-openshift-lightspeed
[mcp]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-enabling-mcp-server_ols-configuring-openshift-lightspeed
[introspection-auth]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-con-authentication-flow-for-cluster-introspection_ols-configuring-openshift-lightspeed
[approvals]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-about-operation-approvals_ols-configuring-openshift-lightspeed
[quotas]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-tokens-and-token-quota-limits_ols-configuring-openshift-lightspeed
[postgres]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#about-postgresql-persistence_ols-configuring-openshift-lightspeed
[api]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#olsconfig-api
[api-providers]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#spec-llm-providers-2
[audit]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-configuring-audit-logging-tracing
[security-defaults]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-security-defaults-by-deployment-mode_ols-configuring-openshift-lightspeed
[tool-inspection]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-ref-tool-result-safety-inspection_ols-configuring-openshift-lightspeed
[agentic]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-configuring-deploying-agentic-lightspeed
