# Stage 060: MCP Context Integrations

## Why This Matters

Model access is only part of an AI coding platform. Assistants also need controlled access to context: cluster state, logs, documentation, tickets, source code, chat history, web data, and other tools.

Model Context Protocol (MCP) gives AI applications a standard way to discover and use tools or context providers. That does not remove the underlying data boundary. It makes the boundary easier to inventory, configure, and govern.

## Architecture

![Stage 060 layered capability map](../../docs/assets/architecture/stage-060-capability-map.svg)

## What This Stage Adds

This stage adds a controlled MCP context layer beside MaaS model access.

- A required read-only OpenShift MCP server for platform-owned cluster context.
- ServiceAccount and RBAC configuration that scopes how the OpenShift MCP server reads cluster state.
- OpenShift AI GenAI Playground discovery configuration for platform-managed MCP servers.
- Optional Slack and BrightData MCP entries for credential-gated external context.
- Credential provisioning hooks that do not commit real tokens to Git.
- Validation that required platform context is running and optional external context remains gated.

OpenShift MCP is required because it represents platform-owned context. Slack and BrightData are optional because they introduce external service boundaries and separate credential approval.

## What To Notice And Why It Matters

Stage 060 separates context governance from model governance.

- MCP does not replace inference or change where a model runs; model access remains governed by MaaS.
- OpenShift AI discovers MCP servers through platform-managed configuration rather than per-user settings.
- OpenShift MCP gives assistants a read-only path to cluster context through ServiceAccount RBAC.
- Optional external MCP providers can be listed without becoming active until credentials and approval exist.

This matters because every context source expands the data surface. Regulated environments should choose trusted servers, scope permissions, manage credentials centrally, and document whether context remains inside OpenShift or moves to an external service.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift AI provides the GenAI Playground surface for configured MCP servers. In Red Hat OpenShift AI 3.4, GenAI Playground and MCP server integration are documented as Technology Preview, so this stage is an early platform pattern rather than production guidance.

Red Hat OpenShift supplies namespaces, ServiceAccounts, RBAC, Secrets, Services, and network boundaries. MCP supplies the open protocol for connecting AI applications to tools and context.

## Future Hardening

This stage demonstrates read-only OpenShift MCP and credential-gated optional providers. Future implementations should evaluate stronger controls before exposing write-capable tools or systems of record:

- identity-based tool filtering;
- OAuth or OIDC token exchange;
- gateway authorization with Kuadrant or Authorino-style policy;
- network isolation and runtime limits around MCP servers;
- audit logs for prompts, tool calls, model calls, MCP invocations, and human approvals.

TODO: Select the supported MCP Gateway hardening path before promoting write-capable MCP tools into the live demo.

## Trust Boundaries

MCP context must be governed separately from model access because tools can expose cluster state, logs, chat data, web data, documents, or actions against other systems. The required OpenShift MCP path is read-only platform context; Slack and BrightData are optional external boundaries.

## Red Hat Products Used

- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides the GenAI Playground integration point.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides workload hosting, ServiceAccounts, RBAC, Secrets, Services, namespaces, and cluster policy boundaries.
- **[Red Hat OpenShift GitOps](https://www.redhat.com/en/technologies/cloud-computing/openshift/gitops)** manages MCP services and discovery configuration.

## Open Source Projects To Know

- [Model Context Protocol](https://modelcontextprotocol.io/) defines the client/server protocol for tools, resources, and external services.
- [Kubernetes MCP server](https://github.com/containers/kubernetes-mcp-server) provides the OpenShift/Kubernetes context server pattern used by this demo.

## Deploy And Validate

```bash
./stages/060-mcp-context-integrations/deploy.sh
./stages/060-mcp-context-integrations/validate.sh
```

Optional providers use environment variables from [`env.example`](../../env.example):

- `SLACK_BOT_TOKEN`
- `BRIGHTDATA_API_TOKEN`

Manifests: [`gitops/stages/060-mcp-context-integrations/base/`](../../gitops/stages/060-mcp-context-integrations/base/)

## References

- [Red Hat: What is Model Context Protocol (MCP)?](https://www.redhat.com/en/topics/ai/what-is-model-context-protocol-mcp)
- [MCP servers for Red Hat OpenShift AI](https://www.redhat.com/en/products/ai/openshift-ai/mcp-servers)
- [Red Hat OpenShift AI 3.4: Experimenting with models in the GenAI Playground](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/experimenting_with_models_in_the_gen_ai_playground/index)
- [Advanced authentication and authorization for MCP Gateway](https://developers.redhat.com/articles/2025/12/12/advanced-authentication-authorization-mcp-gateway)
- [MCP security: Implementing robust authentication and authorization](https://www.redhat.com/en/blog/mcp-security-implementing-robust-authentication-and-authorization)
- [MCP security: Containerization and Red Hat OpenShift integration](https://www.redhat.com/en/blog/mcp-security-containerization-and-red-hat-openshift-integration)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [OpenShift documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/)

## Next Stage

[Stage 070: Controlled Developer Workspaces](../070-controlled-developer-workspaces/README.md) shows developers consuming governed model and context capabilities from Red Hat OpenShift Dev Spaces.
