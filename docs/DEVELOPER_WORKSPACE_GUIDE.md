# Developer Workspace Guide

This guide is for demo users working in Stage 070 and later. It explains how to open the pre-provisioned Red Hat OpenShift Dev Spaces workspace and connect the developer tools to MaaS without using personal provider credentials.

## What Is Already Prepared

Stage 070 creates the Dev Spaces environment and pre-provisions an `exercises` workspace for the demo personas. The workspace includes:

- The `coding-exercises` repository with Continue and OpenCode configuration templates.
- The `coolstore` application source for the `ai-admin` and `ai-developer` personas.
- Continue for IDE-based AI coding assistance.
- OpenCode for terminal-based AI coding workflows.
- MTA VS Code extensions in the `ai-admin` and `ai-developer` workspaces for later modernization exercises.

The platform owns the workspace definition, tooling image, source repositories, and model access path. The user still needs to create a MaaS API key and place it into the local tool configuration inside the workspace.

## Open The Workspace

1. Log in to Red Hat OpenShift Dev Spaces with the assigned demo user.
2. Start the pre-provisioned `exercises` workspace.
3. Wait for the IDE to open and for the workspace startup command to finish.

During startup, the workspace copies the Continue template from `/projects/coding-exercises/.vscode/config.yaml` to `~/.continue/config.yaml`. The OpenCode template is available at `/projects/coding-exercises/.opencode/opencode.json`.

## Create A MaaS API Key

Use the OpenShift AI dashboard to generate a MaaS-issued API key for the approved demo subscription. In this demo, the subscription is `demo-models-subscription`, which includes the private local models and any approved external models added in Stage 050.

Copy the key only into the workspace tool configuration. Do not commit it, paste it into README files, or store it in Git. MaaS keys are platform-issued credentials and should be treated as secrets.

## Choose The Model Endpoint

Use a model endpoint that matches the exercise and data policy:

| Model ID | Typical use |
|----------|-------------|
| `nemotron-3-nano-30b-a3b` | Default private model for sensitive code and enterprise demo tasks |
| `gpt-oss-20b` | Alternative private local model |
| `gpt-4o` | Approved external model when provider-side processing is allowed |
| `gpt-4o-mini` | Lower-cost approved external model when provider-side processing is allowed |

The OpenAI-compatible MaaS endpoint shape is:

```text
https://<maas-gateway-host>/maas/<model-id>/v1
```

If the OpenShift AI dashboard gives you the full model endpoint, use that value directly for the selected model. If you are updating the templates for several models, replace `YOUR_MAAS_ROUTE` with only the gateway base URL, such as `https://<maas-gateway-host>`.

## Configure Continue

Continue is used for IDE-based chat, code explanation, edits, and code generation. It is useful when the developer wants assistance while reading or changing files in the browser-based IDE.

Open `~/.continue/config.yaml` and replace the placeholders:

- Replace `YOUR_MAAS_ROUTE` with the MaaS gateway base URL, or replace the full `apiBase` value with a complete model endpoint.
- Replace `YOUR_API_KEY` with the MaaS API key generated for the demo subscription.
- Keep the `model` value aligned with the selected MaaS model ID.

The source template lives in `/projects/coding-exercises/.vscode/config.yaml`. After editing the local config, select **Local Config** in the Continue sidebar.

## Configure OpenCode

OpenCode is used for terminal-based AI coding workflows. It is useful for reviewing project structure, working with diffs, asking for multi-file changes, and running command-line development tasks from the same controlled workspace.

From the workspace terminal, open `/projects/coding-exercises/.opencode/opencode.json` and replace the placeholders:

- Replace `YOUR_MAAS_ROUTE` with the MaaS gateway base URL, or replace the full `baseURL` value with a complete model endpoint.
- Replace `YOUR_API_KEY` with the same MaaS API key.
- Keep the default model on a private local model unless the exercise explicitly calls for an approved external model.

Run `opencode` from the workspace terminal when the configuration is in place.

## MTA Extensions

The MTA VS Code extensions are included so the same controlled workspace can support the modernization workflow introduced in Stage 080. They help developers review MTA analysis findings and act on modernization issues without leaving Dev Spaces.

Stage 070 only prepares the IDE side of that workflow. Stage 080 deploys Migration Toolkit for Applications, Red Hat Developer Lightspeed for MTA, and the server-side MaaS-backed LLM proxy configuration. Do not put MaaS API keys directly into the MTA extension configuration unless a later exercise explicitly instructs you to do so.

## Validation Checklist

- Dev Spaces opens the `exercises` workspace.
- Continue appears in the IDE and uses `~/.continue/config.yaml`.
- Continue can send a request to the selected MaaS model.
- `opencode` starts from the terminal and uses the configured MaaS model.
- No MaaS API key or provider key is committed to Git.
- External models are used only when the demo policy allows provider-side processing.

