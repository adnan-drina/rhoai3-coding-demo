# Stage 050: Approved External Model Access

## Why This Matters

Some organizations approve external frontier models for selected workloads. This stage shows that external model access can be exposed through the same governed Models-as-a-Service path without distributing provider credentials to every developer or tool.

## What This Stage Adds

- OpenAI-backed `ExternalModel` resources for `gpt-4o` and `gpt-4o-mini`.
- External model `MaaSModelRef`, authorization, and subscription resources.
- `OPENAI_API_KEY` provisioning into the `openai-api-key` Secret when the value exists in `.env`.

Governed external access is not private model serving. Prompts are still processed by the external provider and must be allowed by policy.

## Deploy And Validate

```bash
./stages/050-approved-external-model-access/deploy.sh
./stages/050-approved-external-model-access/validate.sh
```

Manifests: [`gitops/stages/050-approved-external-model-access/base/`](../../gitops/stages/050-approved-external-model-access/base/)

## Next Stage

[Stage 060: MCP Context Integrations](../060-mcp-context-integrations/README.md) adds tool-context integrations with their own data boundaries.
