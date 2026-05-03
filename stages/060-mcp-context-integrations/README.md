# Stage 060: MCP Context Integrations

## Why This Matters

Stage 050 completed the model access story: private models and approved external models can both be exposed through a governed MaaS path. Stage 060 adds the next layer that AI coding assistants need to become useful in real enterprise workflows: controlled access to context.

Model Context Protocol (MCP) gives AI applications a standardized way to connect to tools, data sources, and services. Without that kind of standard interface, every AI assistant integration can become a custom API project with its own configuration, credential handling, and risk profile. MCP does not replace those underlying APIs. It provides a common protocol above them so an AI application can discover what a server offers and request the right context or tool action through a consistent pattern.

That matters for this demo because governed model access is only half of the enterprise AI problem. A model can generate useful responses only when it has enough task-relevant context. For a developer workflow, that context might be cluster state, logs, documentation, tickets, source code, chat history, or web data. Each source has its own data boundary and approval model.

Stage 060 makes that boundary visible before developer tools consume the integrations. It shows a required, read-only OpenShift MCP server as the platform-native context example, and it includes Slack and BrightData as credential-gated external context examples. The point is not to enable every possible context source. The point is to show that context integrations should be inventoried, scoped, credentialed, and governed with the same care as model providers.

## Architecture

![Stage 060 layered capability map](../../docs/assets/architecture/stage-060-capability-map.svg)

## What This Stage Adds

This stage adds a controlled MCP context layer beside governed model access.

- A required read-only OpenShift MCP server for platform-owned cluster context.
- ServiceAccount and RBAC configuration that scopes how the OpenShift MCP server reads cluster state.
- Red Hat OpenShift AI GenAI Playground discovery configuration for platform-managed MCP servers.
- Optional Slack and BrightData MCP entries that demonstrate credential-gated external context providers.
- Credential provisioning hooks for optional providers without committing real tokens to Git.
- Validation that required platform context is running and optional external context remains gated.

OpenShift MCP is required because it represents platform context owned by the demo. Slack and BrightData are intentionally optional because they introduce external service boundaries and require separate credential approval. Missing optional credentials produce validation warnings, not failures.

## What To Notice And Why It Matters

Stage 060 adds controlled context discovery beside governed model access. The required read-only OpenShift MCP server is deployed as platform-owned context, while Slack and BrightData MCP entries remain credential-gated external integrations.

The essential proof point is that context has its own trust boundary:

- MCP does not replace inference or change where a model runs; model access remains governed by MaaS.
- Red Hat OpenShift AI discovers MCP servers through platform-managed configuration rather than per-user tool settings.
- OpenShift MCP gives assistants a controlled, read-only path to cluster context through ServiceAccount RBAC.
- Optional external MCP providers demonstrate how context sources can be inventoried without becoming active until credentials and approval exist.

This matters because AI assistants become useful when they can reach relevant enterprise context, but every context source expands the data surface. For regulated environments, MCP should be treated as an integration governance pattern: choose trusted servers, scope permissions, manage credentials centrally, and document whether context remains inside the OpenShift boundary or moves to an external service.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift AI provides the GenAI Playground surface where users can experiment with foundation models and configured MCP servers before those patterns move into applications or developer tools. In Red Hat OpenShift AI 3.4, GenAI Playground and MCP server integration are documented as Technology Preview, so this demo treats the capability as an early platform direction rather than production guidance.

Red Hat also publishes a Red Hat OpenShift AI MCP servers collection. That page presents MCP servers as a way for AI engineers to integrate enterprise tools and resources into AI applications and agents, and it highlights partner-provided containers built with Red Hat Universal Base Images as a reliable foundation for OpenShift AI environments. This demo is smaller than that full ecosystem: it uses one required OpenShift/Kubernetes MCP example and two optional external context examples to teach the operating model.

Red Hat OpenShift provides the hosting and policy substrate: namespaces, ServiceAccounts, RBAC, Secrets, Services, network boundaries, and GitOps reconciliation. Red Hat OpenShift GitOps keeps the MCP server deployment and discovery configuration reproducible.

MCP provides the open protocol pattern. In MCP terms, an AI application acts as a client, infrastructure hosts the connection, and MCP servers expose specific tools, resources, or capabilities. The initial handshake lets the client and server discover what each side supports. After that, dynamic discovery allows the application to request task-relevant context instead of packing unrelated data into the prompt up front.

MCP and inference are related, but they are not the same thing. Inference is the model generating tokens. MCP is the way an AI application can reach tools and context that may inform that generation. Stage 030 and Stage 040 built the inference and model access path. Stage 060 adds a controlled context path beside it.

## Red Hat Products Used

- **Red Hat OpenShift AI** provides the GenAI Playground integration point for configured MCP servers.
- **Red Hat OpenShift AI MCP servers** provide the broader Red Hat and partner ecosystem direction for MCP servers built for OpenShift AI use cases.
- **Red Hat OpenShift** provides workload hosting, ServiceAccounts, RBAC, Secrets, Services, namespaces, and cluster policy boundaries.
- **Red Hat OpenShift GitOps** manages the MCP services and discovery configuration.
- **Red Hat OpenShift Dev Spaces** consumes governed model and context capabilities in the next stage.
- **Red Hat Developer Hub** can later document approved context services as discoverable platform capabilities.

## Open Source Projects To Know

- [Model Context Protocol](https://modelcontextprotocol.io/) defines the client/server protocol for connecting AI applications to tools, resources, and external services.
- [Kubernetes MCP server](https://github.com/containers/kubernetes-mcp-server) provides the OpenShift/Kubernetes context server pattern used by this demo container image.
- Slack MCP servers show how team communication platforms can become optional AI context sources when credentials and policy allow.
- BrightData MCP servers show how external web context can be exposed through MCP when an organization explicitly approves that data path.

## Trust Boundaries

MCP context must be evaluated separately from model access.

Private local models can keep prompts and code inside OpenShift. Governed external models can centralize access to an outside provider. MCP servers add a third kind of boundary: tool and context access. A server can expose cluster metadata, logs, chat messages, public web data, internal documents, or actions against another system depending on what it is allowed to do.

The required OpenShift MCP server is configured read-only. That reduces risk, but it is not the same as least-privilege completion. The current demo grants the `openshift-mcp` ServiceAccount the cluster-wide `view` ClusterRole so the server can inspect broad OpenShift state during the workshop. That scope is intentionally tracked in [`BACKLOG.md`](../../BACKLOG.md) as future hardening; a production design should narrow MCP permissions to the minimum namespaces, resources, and verbs required by the intended use case.

Slack and BrightData are optional because they introduce external service boundaries. Their deployments are included at zero replicas and their discovery entries are visible, but runtime use requires approved credentials and an explicit enablement decision. Missing optional credentials should produce warnings so operators can distinguish a platform failure from an intentionally disabled external integration.

Users and platform teams should understand what they authorize when they enable an MCP connection. Trusted servers, credential control, permission review, and periodic access review are part of the operating model.

## Where This Fits In The Full Platform

| Earlier capability | How this stage uses it |
|--------------------|------------------------|
| Stage 010 platform foundation | Uses OpenShift namespaces, RBAC, ConfigMaps, Secrets, and GitOps foundations |
| Stage 040 governed MaaS | Complements governed model access with governed context discovery |
| Stage 050 approved external access | Reinforces that external context sources need explicit provider boundaries just like external models |

| Later capability | What this stage provides |
|------------------|--------------------------|
| Stage 070 Dev Spaces | Supplies context integrations that developer tools can consume after platform approval |
| Stage 080 MTA | Establishes the context-governance pattern needed before modernization tools use richer external context |
| Stage 090 Developer Hub | Provides context services that can later be documented as platform resources |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./stages/060-mcp-context-integrations/deploy.sh
./stages/060-mcp-context-integrations/validate.sh
```

Manifests: [`gitops/stages/060-mcp-context-integrations/base/`](../../gitops/stages/060-mcp-context-integrations/base/)

## References

- [Red Hat: What is Model Context Protocol (MCP)?](https://www.redhat.com/en/topics/ai/what-is-model-context-protocol-mcp)
- [MCP servers for Red Hat OpenShift AI](https://www.redhat.com/en/products/ai/openshift-ai/mcp-servers)
- [Red Hat OpenShift AI 3.4: Experimenting with models in the GenAI Playground](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/experimenting_with_models_in_the_gen_ai_playground/index)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [OpenShift documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/)

## Next Stage

[Stage 070: Controlled Developer Workspaces](../070-controlled-developer-workspaces/README.md) shows developers consuming governed model and context capabilities from Red Hat OpenShift Dev Spaces.
