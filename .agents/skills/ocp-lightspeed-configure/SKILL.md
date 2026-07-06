---
name: ocp-lightspeed-configure
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when configuring Red Hat OpenShift Lightspeed 1.0, including OLSConfig
  customization, LLM provider settings, conversation history, telemetry,
  TLS certificates, RBAC, and user access controls. Do NOT use for concepts
  (use ocp-lightspeed-about), installing (use ocp-lightspeed-install),
  operations (use ocp-lightspeed-operate), or troubleshooting
  (use ocp-lightspeed-troubleshoot).
---

# OCP Lightspeed Configure

Use this skill to configure Red Hat OpenShift Lightspeed 1.0 grounded in
official product documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers OLSConfig CR
customization, LLM provider credential and endpoint setup, TLS configuration,
RBAC, query filtering, RAG databases, cluster interaction (MCP), token quotas,
and PostgreSQL persistence.

## Key Configuration Areas

1. **Credentials secrets** — API token secrets per LLM provider in
   `openshift-lightspeed` namespace (OpenAI, RHOAI, RHELAI, Azure, watsonx,
   Google Vertex AI).
2. **OLSConfig CR** — Single cluster-scoped resource (`ols.openshift.io/v1alpha1`,
   name: `cluster`) that drives the entire service deployment.
3. **LLM provider configuration** — Provider type, URL, models, and
   credential references under `spec.llm.providers[]`.
4. **TLS certificates** — Custom TLS for the backend endpoint
   (`spec.ols.tlsConfig`) and trusted CA for LLM providers
   (`spec.ols.additionalCAConfigMapRef`).
5. **RBAC and user access** — ClusterRole `lightspeed-operator-query-access`
   bound to users or groups.
6. **Query filters** — Regex-based sensitive data redaction before LLM
   submission (`spec.ols.queryFilters`).
7. **BYO Knowledge (RAG)** — Custom RAG databases via container images
   (`spec.ols.rag`).
8. **Cluster interaction (MCP)** — Observability MCP server for cluster
   introspection (`spec.ols.introspectionEnabled`), custom MCP servers
   (`spec.mcpServers`, feature gate `MCPServer`).
9. **Token quotas** — Per-user and per-cluster token limits
   (`spec.ols.quotaHandlersConfig`).
10. **PostgreSQL persistence** — Conversation history storage
    (`spec.ols.storage`).
11. **Google Vertex AI** — `google_vertex` and `google_vertex_anthropic`
    provider types with GCP service account authentication.
12. **Tool filtering** — Query-based tool selection for MCP
    (`spec.olsConfig.toolFilteringConfig`, feature gate `ToolFiltering`).

## OLSConfig CR Summary

- **apiVersion:** `ols.openshift.io/v1alpha1`
- **kind:** `OLSConfig`
- **metadata.name:** `cluster` (singleton, cluster-scoped)
- **Required spec fields:** `spec.llm` and `spec.ols`
- **Key spec.ols fields:** `defaultModel`, `defaultProvider`,
  `additionalCAConfigMapRef`, `byokRAGOnly`, `conversationCache`,
  `deployment`, `introspectionEnabled`, `logLevel`, `proxyConfig`,
  `queryFilters`, `quotaHandlersConfig`, `rag`, `storage`, `tlsConfig`,
  `tlsSecurityProfile`, `userDataCollection`

See `references/official-doc-extraction.md` for complete field reference and
YAML examples.

## LLM Provider Configuration

Supported provider types:
- `openai` — OpenAI API
- `azure_openai` — Microsoft Azure OpenAI (supports Entra ID auth)
- `watsonx` — IBM watsonx (requires `projectID`)
- `rhelai_vllm` — Red Hat Enterprise Linux AI vLLM
- `rhoai_vllm` — Red Hat OpenShift AI vLLM
- `google_vertex` — Google Vertex AI (Gemini)
- `google_vertex_anthropic` — Anthropic on Google Vertex AI

All providers require a credentials Secret in namespace `openshift-lightspeed`.
The secret key is always `apitoken` (except Google Vertex AI which uses a GCP
service account JSON key via `credentialKey`).

## RBAC and Access Control

OpenShift Lightspeed RBAC is binary — the Operator creates a ClusterRole
`lightspeed-operator-query-access`. Grant access via:

```bash
oc adm policy add-cluster-role-to-user lightspeed-operator-query-access <user>
oc adm policy add-cluster-role-to-group lightspeed-operator-query-access <group>
```

The `kubeadmin` account always has access. Cluster introspection uses MCP
server authentication (file-based secrets or Kubernetes passthrough).

## Workflow

1. Read `references/official-doc-extraction.md` for exact YAML patterns.
2. Identify the configuration task:
   - Initial OLSConfig creation for a specific LLM provider
   - Adding/changing TLS certificates
   - Granting user or group access (RBAC)
   - Configuring query filters for data redaction
   - Enabling BYO Knowledge RAG databases
   - Enabling/disabling cluster interaction (MCP)
   - Configuring token quotas
   - Enabling PostgreSQL persistence
   - Exposing the service via a Route
   - Configuring Google Vertex AI
3. Use the exact `apiVersion`, field names, and namespace from the extraction.
4. Validate with the verification commands documented per section.
5. Never invent CR fields not documented in the OLSConfig API reference.

## Related Skills

- `ocp-lightspeed-about` — OpenShift Lightspeed concepts and architecture
- `ocp-lightspeed-install` — Operator installation procedures
- `ocp-lightspeed-operate` — Day-2 operations and maintenance
- `ocp-lightspeed-troubleshoot` — Diagnostics and recovery
- `ocp-lightspeed-upgrade` — Upgrade procedures
- `ocp-lightspeed-uninstall` — Removal procedures

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
