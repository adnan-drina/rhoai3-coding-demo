# Stage 060: MCP Context Integrations

## Why This Matters

Model access and tool access are separate trust boundaries. MCP integrations can give AI workflows useful context, but each server can expose or move different data. This stage makes that boundary visible before developers consume the integrations from workspaces.

## What This Stage Adds

- A read-only OpenShift MCP server in the `coding-assistant` namespace.
- Slack MCP and BrightData MCP components registered with GenAI Playground.
- The `gen-ai-aa-mcp-servers` ConfigMap used by the OpenShift AI GenAI Playground.
- Optional credential provisioning from `SLACK_BOT_TOKEN` and `BRIGHTDATA_API_TOKEN`.

Missing Slack or BrightData credentials produce validation warnings, not failures. The OpenShift MCP server is required and runs read-only.

## Deploy And Validate

```bash
./stages/060-mcp-context-integrations/deploy.sh
./stages/060-mcp-context-integrations/validate.sh
```

Manifests: [`gitops/stages/060-mcp-context-integrations/base/`](../../gitops/stages/060-mcp-context-integrations/base/)

## Next Stage

[Stage 070: Controlled Developer Workspaces](../070-controlled-developer-workspaces/README.md) shows developers consuming governed model and context capabilities from Red Hat OpenShift Dev Spaces.
