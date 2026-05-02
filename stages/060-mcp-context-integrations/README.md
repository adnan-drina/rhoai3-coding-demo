# Stage 060: MCP Context Integrations

## Why This Matters

Stage 050 completed the model access story: private models and approved external models can both be exposed through a governed MaaS path. Stage 060 adds the next layer that AI coding assistants need to become useful in real enterprise workflows: controlled access to context.

Model Context Protocol (MCP) gives AI applications a standardized way to connect to tools, data sources, and services. Without that kind of standard interface, every AI assistant integration can become a custom API project with its own configuration, credential handling, and risk profile. MCP does not replace those underlying APIs. It provides a common protocol above them so an AI application can discover what a server offers and request the right context or tool action through a consistent pattern.

That matters for this demo because governed model access is only half of the enterprise AI problem. A model can generate useful responses only when it has enough task-relevant context. For a developer workflow, that context might be cluster state, logs, documentation, tickets, source code, chat history, or web data. Each source has its own data boundary and approval model.

Stage 060 makes that boundary visible before developer tools consume the integrations. It shows a required, read-only OpenShift MCP server as the platform-native context example, and it includes Slack and BrightData as credential-gated external context examples. The point is not to enable every possible context source. The point is to show that context integrations should be inventoried, scoped, credentialed, and governed with the same care as model providers.

## Architecture

![Stage 060 layered capability map](../../docs/assets/architecture/stage-060-capability-map.svg)

## What This Stage Adds

Stage 060 adds a small MCP context layer to the trusted AI development platform.

- A required read-only OpenShift MCP server in the `coding-assistant` namespace.
- A dedicated `openshift-mcp` ServiceAccount and `openshift-mcp-view` ClusterRoleBinding.
- A cluster-internal `openshift-mcp` Service exposed to Red Hat OpenShift AI through the MCP discovery ConfigMap.
- The `gen-ai-aa-mcp-servers` ConfigMap in `redhat-ods-applications`, used by the Red Hat OpenShift AI GenAI Playground to discover configured MCP servers.
- Slack MCP and BrightData MCP discovery entries that demonstrate optional external context providers.
- Slack and BrightData MCP deployments and Services held at zero replicas in the base deployment so missing credentials do not make Argo CD unhealthy.
- Optional credential provisioning from `SLACK_BOT_TOKEN` and `BRIGHTDATA_API_TOKEN` into the `coding-assistant` namespace.
- Validation that the OpenShift MCP server is running and that optional providers are discoverable but credential-gated.

OpenShift MCP is required because it represents platform context owned by the demo. Slack and BrightData are intentionally optional because they introduce external service boundaries and require separate credential approval. Missing optional credentials produce validation warnings, not failures.

## What To Notice In The Demo

Show MCP as the bridge between governed model access and real workflow context.

1. The model path remains governed by MaaS. MCP does not replace inference or change where a model runs.
2. OpenShift MCP gives the assistant a controlled way to inspect cluster context through a read-only server.
3. Red Hat OpenShift AI discovers MCP servers through platform-managed configuration rather than each user hand-editing tool settings.
4. Slack and BrightData are visible as possible context integrations, but their runtimes stay disabled until credentials and approval exist.
5. Validation treats optional context providers differently from required platform context.
6. The trust boundary moves with the MCP server. OpenShift context stays inside the cluster, while Slack or BrightData would introduce external data paths.

The proof point is controlled context discovery. A model may be approved, and a developer may have a governed API key, but the assistant should still receive only the context sources that the platform team has made visible and scoped.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift AI provides the GenAI Playground surface where users can experiment with foundation models and configured MCP servers before those patterns move into applications or developer tools. In Red Hat OpenShift AI 3.4, GenAI Playground and MCP server integration are documented as Technology Preview, so this demo treats the capability as an early platform direction rather than production guidance.

Red Hat also publishes a Red Hat OpenShift AI MCP servers collection. That page presents MCP servers as a way for AI engineers to integrate enterprise tools and resources into AI applications and agents, and it highlights partner-provided containers built with Red Hat Universal Base Images as a reliable foundation for OpenShift AI environments. This demo is smaller than that full ecosystem: it uses one required OpenShift/Kubernetes MCP example and two optional external context examples to teach the operating model.

Red Hat OpenShift provides the hosting and policy substrate: namespaces, ServiceAccounts, RBAC, Secrets, Services, network boundaries, and GitOps reconciliation. Red Hat OpenShift GitOps keeps the MCP server deployment and discovery configuration reproducible.

MCP provides the open protocol pattern. In MCP terms, an AI application acts as a client, infrastructure hosts the connection, and MCP servers expose specific tools, resources, or capabilities. The initial handshake lets the client and server discover what each side supports. After that, dynamic discovery allows the application to request task-relevant context instead of packing unrelated data into the prompt up front.

MCP and inference are related, but they are not the same thing. Inference is the model generating tokens. MCP is the way an AI application can reach tools and context that may inform that generation. Stage 030 and Stage 040 built the inference and model access path. Stage 060 adds a controlled context path beside it.

## Why This Is Worth Knowing

Enterprise AI assistants become much more useful when they can inspect the systems people actually work with. For developers, that can mean cluster state, logs, pull requests, tickets, documentation, incident channels, application inventory, or modernization findings. But every added context source increases the potential data surface.

MCP gives teams a common integration pattern, which helps avoid a long tail of one-off assistant connectors. The enterprise lesson is that standardization does not remove the need for governance. It makes governance easier to apply consistently: choose trusted servers, scope their permissions, manage credentials centrally, validate what is discoverable, and document what data can move through each path.

This stage also prepares the reader for later developer workflows. In Stage 070, developer workspaces can consume governed model access. In later iterations, those workspaces can also consume approved MCP context. The important pattern is that both model access and context access are platform capabilities, not private tool configuration hidden on a developer laptop.

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
