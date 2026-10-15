---
name: rhdh-mcp-tools
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone asks about the Red Hat Developer Hub 1.10 Model Context
  Protocol server and tool plugins (Developer Preview): installing them, tokens
  and client endpoints, catalog, TechDocs and scaffolder MCP tools, and
  troubleshooting. Not used in this repo. Do NOT use for the platform MCP
  gateway (use rhcl-mcp-gateway) or Developer Lightspeed (use
  rhdh-developer-lightspeed).
---

# Developer Hub MCP tools

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- Someone wants AI clients to query or drive Developer Hub through MCP.

## Not used in this repo

No MCP server or tool plugin is enabled in
`gitops/stages/070-advanced-app-platform/rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`.
The feature is Developer Preview in 1.10.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Model Context Protocol | [Model Context Protocol][l1] |
| Install the MCP server and tool plugins | [Install the MCP server and tool plugins][l2] |
| Tokens and endpoints | [Tokens and endpoints][l3] |
| Software Catalog tools | [Software Catalog tools][l4] |
| Scaffolder tools | [Scaffolder tools][l5] |
| Troubleshooting | [Troubleshooting][l6] |

## Related skills

`rhdh-developer-lightspeed`, `rhcl-mcp-gateway`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_model_context_protocol_tools_for_red_hat_developer_hub/index#model-context-protocol_interacting-with-model-context-protocol-tools-for-rhdh
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_model_context_protocol_tools_for_red_hat_developer_hub/index#install-mcp-server-and-tool-plugins-to-expose-portal-capabilities-to-the-ai_interacting-with-model-context-protocol-tools-for-rhdh
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_model_context_protocol_tools_for_red_hat_developer_hub/index#configure-mcp-tokens-and-endpoints-to-authorize-client-access_interacting-with-model-context-protocol-tools-for-rhdh
[l4]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_model_context_protocol_tools_for_red_hat_developer_hub/index#enable-software-catalog-mcp-tools-to-allow-the-ai-to-query-component-metadata_interacting-with-model-context-protocol-tools-for-rhdh
[l5]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_model_context_protocol_tools_for_red_hat_developer_hub/index#automate-software-templates-by-using-scaffolder-mcp-tools_interacting-with-model-context-protocol-tools-for-rhdh
[l6]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/interacting_with_model_context_protocol_tools_for_red_hat_developer_hub/index#troubleshoot-mcp-server-and-client-problems_interacting-with-model-context-protocol-tools-for-rhdh
