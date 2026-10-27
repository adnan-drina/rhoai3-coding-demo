---
name: ocp-lightspeed-configure
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_lightspeed
  docs-version: "1.0"
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
- Cluster interaction and MCP servers let the assistant read live cluster
  state with the user's identity; read [cluster interaction][cluster] and
  [authentication flow][introspection-auth] before enabling them on the demo.
- A provider behind a private CA needs the trusted-CA configuration; see
  [trusted CA for the LLM][trusted-ca].

## Official documentation (OpenShift Lightspeed, "1.0" set)

| Topic | Section |
|---|---|
| Credentials and custom resource | [Secret (CLI)][secret-cli], [custom resource (CLI)][cr-cli] |
| TLS | [Trusted CA for the LLM][trusted-ca], [custom TLS certificates][tls] |
| Access | [RBAC framework][rbac], [route and user access][route] |
| Data redaction | [Filtering and redacting information][filters] |
| Custom knowledge | [Custom documentation (BYO knowledge)][byok] |
| Cluster interaction, MCP | [Live cluster state][cluster], [custom MCP server][mcp], [tool approvals][approvals] |
| Quotas | [Token quota limits][quotas] |
| Persistence | [Conversation history][postgres] |
| Field reference | [OLSConfig API][api], [`.spec.llm.providers[]`][api-providers] |
| Audit | [Audit logging and tracing][audit] |

## Related skills

`ocp-lightspeed-about`, `ocp-lightspeed-troubleshoot`, `rhoai-maas-governance`,
`ocp-security-rbac-scc`.

[configure]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-configuring-openshift-lightspeed
[secret-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-creating-the-credentials-secret-using-cli_ols-configuring-openshift-lightspeed
[cr-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-creating-lightspeed-custom-resource-file-using-cli_ols-configuring-openshift-lightspeed
[trusted-ca]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-configuring-lightspeed-with-a-trusted-ca-certificate-for-the-llm_ols-configuring-openshift-lightspeed
[tls]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#configuring-custom-tls-certificates_ols-configuring-openshift-lightspeed
[verify]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-verifying-openshift-lightspeed-deployment_ols-configuring-openshift-lightspeed
[rbac]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-about-lightspeed-and-role-based-access-control_ols-configuring-openshift-lightspeed
[route]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-proc-expose-the-ols-service-by-using-a-route_ols-configuring-openshift-lightspeed
[filters]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-filtering-and-redacting-information_ols-configuring-openshift-lightspeed
[byok]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#about-the-byo-knowledge-tool_ols-configuring-openshift-lightspeed
[cluster]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#about-cluster-interaction_ols-configuring-openshift-lightspeed
[mcp]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-enabling-mcp-server_ols-configuring-openshift-lightspeed
[introspection-auth]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-con-authentication-flow-for-cluster-introspection_ols-configuring-openshift-lightspeed
[approvals]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-about-operation-approvals_ols-configuring-openshift-lightspeed
[quotas]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-tokens-and-token-quota-limits_ols-configuring-openshift-lightspeed
[postgres]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#about-postgresql-persistence_ols-configuring-openshift-lightspeed
[api]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#olsconfig-api
[api-providers]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#spec-llm-providers-2
[audit]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/configure/index#ols-configuring-audit-logging-tracing
