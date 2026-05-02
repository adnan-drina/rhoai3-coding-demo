# Stage 060: MCP Context Integrations

## Why This Matters

Model access and tool access are separate trust boundaries. MCP integrations can give AI workflows useful context, but each server can expose or move different data. This stage makes that boundary visible before developers consume the integrations from workspaces.

The message is not that every context source should be enabled. The message is that context integrations need the same platform thinking as model access: inventory, credentials, scope, and policy.

## Architecture

![Stage 060 layered capability map](../../docs/assets/architecture/stage-060-capability-map.svg)

## What This Stage Adds

- A read-only OpenShift MCP server in the `coding-assistant` namespace.
- Slack MCP and BrightData MCP components registered with GenAI Playground.
- The `gen-ai-aa-mcp-servers` ConfigMap used by the Red Hat OpenShift AI GenAI Playground.
- Optional credential provisioning from `SLACK_BOT_TOKEN` and `BRIGHTDATA_API_TOKEN`.

Missing Slack or BrightData credentials produce validation warnings, not failures. The OpenShift MCP server is required and runs read-only.

## What To Notice In The Demo

Show that tool context has its own approval model:

1. OpenShift context is available through a read-only MCP service.
2. Slack and BrightData are discoverable but credential-gated.
3. GenAI Playground can discover MCP servers through platform-managed configuration.
4. Validation warns about optional context providers without blocking the platform path.

The proof point is separation. A model may be approved, but each context source still needs its own data boundary decision.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift AI provides the GenAI Playground surface that can discover configured MCP servers. Red Hat OpenShift provides the runtime, namespace, service, ConfigMap, Secret, and RBAC boundaries used to host and expose those integrations.

MCP provides the open protocol pattern for tool and context integration. This demo uses OpenShift context as the required platform example and includes Slack and BrightData as optional integrations to show how external context sources can be credential-gated.

## Red Hat Products Used

- **Red Hat OpenShift AI** provides the GenAI Playground integration point.
- **Red Hat OpenShift** provides workload hosting, RBAC, Secret management, and service discovery.
- **Red Hat OpenShift GitOps** manages the MCP services and discovery configuration.

## Open Source Projects To Know

- [Model Context Protocol](https://modelcontextprotocol.io/) defines the tool and context integration pattern.
- OpenShift MCP exposes cluster context through a controlled server process.
- Slack and BrightData MCP servers demonstrate optional external context integrations that require their own credentials and data review.

## Trust Boundaries

MCP context must be evaluated separately from model access. The base deployment includes a required read-only OpenShift MCP server. Slack and BrightData are optional because they introduce external service boundaries and require `SLACK_BOT_TOKEN` or `BRIGHTDATA_API_TOKEN`.

Missing optional credentials should not fail the stage. They should produce warnings so operators can distinguish a platform failure from an intentionally disabled external integration.

## Why This Is Worth Knowing

AI assistants become more useful when they can inspect tools, tickets, docs, or cluster state, but that usefulness expands the data boundary. This stage gives the demo a vocabulary for approving context sources with the same care used for model providers.

## Where This Fits In The Full Platform

| Earlier capability | How this stage uses it |
|--------------------|------------------------|
| Stage 010 platform foundation | Uses OpenShift namespaces, RBAC, ConfigMaps, and Secrets |
| Stage 040 MaaS | Complements governed model access with governed context discovery |

| Later capability | What this stage provides |
|------------------|--------------------------|
| Stage 070 Dev Spaces | Supplies context integrations that developer tools can consume |
| Stage 090 Developer Hub | Provides context services that can later be documented as platform resources |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./stages/060-mcp-context-integrations/deploy.sh
./stages/060-mcp-context-integrations/validate.sh
```

Manifests: [`gitops/stages/060-mcp-context-integrations/base/`](../../gitops/stages/060-mcp-context-integrations/base/)

## References

- [Red Hat OpenShift AI documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [OpenShift documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/)

## Next Stage

[Stage 070: Controlled Developer Workspaces](../070-controlled-developer-workspaces/README.md) shows developers consuming governed model and context capabilities from Red Hat OpenShift Dev Spaces.
