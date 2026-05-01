# Step 04: AI-Assisted Development In Controlled Workspaces

## Why This Matters

Developers want AI assistance in the tools where they already write, test, and review code. Enterprises need that experience to respect identity, data boundaries, model policy, and workspace controls.

This step shows how AI-assisted development can be delivered from managed OpenShift workspaces instead of unmanaged local toolchains. Developers still get familiar VS Code-style assistance, but model access flows through the MaaS layer created in Step 03.

## What This Step Adds

Step 04 adds the developer workspace and coding assistant layer:

```text
Developer workspace layer
+-- OpenShift Dev Spaces Operator
+-- CheCluster instance
+-- Per-user DevWorkspace resources
+-- Coding exercises repository
+-- Coolstore repository for modernization demos
+-- Continue extension
+-- OpenCode CLI
+-- MTA VS Code extension for ai-admin and ai-developer
```

The `ai-admin` and `ai-developer` workspaces include both coding exercises and the Coolstore Java EE application used in Step 05. The workspace is part of the platform, which means it can be created, governed, reset, and reproduced consistently.

## What To Notice In The Demo

Show the workspace first, then the model configuration. The important moment is that the developer tool is not tied to a single model provider. Continue and OpenCode can use any MaaS-published model that follows the OpenAI-compatible API pattern.

Then show the trust choice:

- Selecting a local model keeps the request inside the platform.
- Selecting an external model uses the same developer workflow, but the prompt is processed by the external provider and must be allowed by policy.

The platform provides flexibility without hiding the data boundary.

## How Red Hat And Open Source Make It Work

OpenShift Dev Spaces provides browser-based development environments running on the cluster. Continue provides the IDE assistant experience. OpenCode provides a terminal-based agent workflow. MaaS provides the model endpoint and API key pattern.

The combination matters because it separates concerns:

- Developers focus on code.
- Platform teams operate workspaces and model access.
- Security teams can reason about which model paths are approved for which data.

## Red Hat Products Used

- **Red Hat OpenShift Dev Spaces** provides the managed cloud development environment.
- **Red Hat OpenShift AI** provides the MaaS model endpoints consumed by the developer tools.
- **Red Hat OpenShift** provides the identity, routing, namespace isolation, and runtime platform for the workspaces.

## Open Source Projects To Know

- [Eclipse Che](https://www.eclipse.org/che/) is the upstream cloud development environment project behind OpenShift Dev Spaces.
- [DevWorkspace](https://github.com/devfile/devworkspace-operator) provides Kubernetes-native workspace orchestration.
- [Continue](https://www.continue.dev/) is an open source AI code assistant that can use OpenAI-compatible model endpoints.
- [OpenCode](https://opencode.ai/) provides terminal-based AI coding workflows that can consume MaaS endpoints.

## Trust Boundaries

| Model path | What happens to prompts and code |
|------------|----------------------------------|
| Local models such as Nemotron and gpt-oss | Requests stay within the OpenShift platform boundary. This is the recommended path for sensitive or regulated code. |
| External models such as GPT-4o and GPT-4o-mini | Requests are proxied through MaaS to OpenAI. Access is centrally governed, but prompt content is processed externally and must be allowed by policy. |

This distinction is the core learning point. A governed external model is useful, but it is not private. The platform makes both options visible and controllable.

## Why This Is Worth Knowing

Many organizations start AI coding experiments with individual developer plugins and personal API keys. That approach does not scale well for enterprise governance.

This step shows a better pattern:

- Developer tools remain familiar.
- Workspaces are reproducible and centrally managed.
- Model keys are issued through a platform layer.
- Private and external model options can coexist.
- The same model access pattern can serve IDE assistants, terminal agents, and later MTA modernization.

## Where This Fits In The Full Platform

| Workflow | Dev Spaces role |
|----------|-----------------|
| AI coding assistant | Developers use Continue against MaaS-published models |
| Terminal agent workflow | Developers use OpenCode with the same MaaS model access pattern |
| Java modernization | Developers analyze Coolstore with the MTA extension |
| Governance story | Model access stays centralized even when tools run in developer workspaces |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./steps/step-04-devspaces/deploy.sh
./steps/step-04-devspaces/validate.sh
```

Manifests: [`gitops/step-04-devspaces/base/`](../../gitops/step-04-devspaces/base/)

## References

- [OpenShift Dev Spaces documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [Continue](https://www.continue.dev/)
- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces)
- [OpenCode: Model-neutral AI coding assistant for OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/04/22/opencode-model-neutral-ai-coding-assistant-openshift-dev-spaces)

## Next Step

[Step 05: AI-Assisted EAP/Java EE Modernization to Quarkus](../step-05-mta/README.md) applies the same governed model access pattern to application modernization.
