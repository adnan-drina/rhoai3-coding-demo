# Stage 050: AI-Assisted Development

## Why This Matters

AI-assisted development is useful when it appears where developers already work: IDEs, terminals, tests, and review workflows. The enterprise concern is how to offer that experience without personal provider keys, unmanaged plugins, or local machine drift.

Stage 050 moves the coding experience into Red Hat OpenShift Dev Spaces. Developers still use familiar IDE and terminal workflows, while model access flows through MaaS and workspace configuration is managed by the platform.

## Architecture

![Stage 050 layered capability map](../../docs/assets/architecture/stage-050-capability-map.svg)

## What This Stage Adds

This stage adds a governed cloud development workspace layer.

- Red Hat OpenShift Dev Spaces deployed through operator-managed resources.
- Pre-provisioned DevWorkspace definitions for the demo personas.
- Single-repository workspaces for onboarding, Coolstore inventory engineering, and MCA Coolstore modernization.
- Continue installed as a Che Code default extension and configured for MaaS-published OpenAI-compatible endpoints.
- OpenCode configuration for MaaS-published OpenAI-compatible endpoints.
- `vscode-editor-configurations` for editor recommendations and bash terminal defaults.
- Java 21 configured as the default workspace shell and Maven runtime for the
  Quarkus demo exercises.
- MTA VS Code extensions scoped only to the `mca-coolstore` workspace through `DEFAULT_EXTENSIONS`.
- A workspace namespace Secret with MaaS API keys for the `ai-developer` workflow.

The workspace, repositories, tools, and model access pattern are platform-managed instead of assembled on each developer laptop.

## What To Notice And Why It Matters

Stage 050 turns governed model access into a developer experience.

- Workspaces are reproducible and isolated by OpenShift identity and namespace.
- Continue and OpenCode use MaaS endpoints instead of personal provider keys.
- Local models keep source-code prompts inside the OpenShift platform boundary.
- Approved external models can use the same workflow only when provider-side processing is allowed.
- The MTA workspace gets modernization extensions without polluting the onboarding or inventory workspaces.

This matters because regulated enterprises need AI coding assistance to fit existing controls for identity, network access, approved tooling, credential handling, and data residency.

## Developer Workspace Setup

After deployment, the developer opens Red Hat OpenShift Dev Spaces from the selected Developer Hub component:

- `getting-started-ai-coding` for Stage 050 onboarding and MaaS client checks.
- `coolstore-inventory-service` for AI-assisted engineering and delivery.
- `mca-coolstore` for migration and modernization.

Stage deployment creates MaaS API keys for the demo models and stores them in `Secret/wksp-ai-developer/maas-devspace-api-keys`. Workspace startup installs the Continue VSIX through `DEFAULT_EXTENSIONS` and renders:

- `~/.continue/config.yaml`
- `~/.config/opencode/opencode.json`
- the OpenCode compatibility path under `~/.opencode/`

The tooling container also sets Java 21 as the shell default in fresh
workspaces. This keeps the Stage 050 Red Hat build of Quarkus prompt focused on
the app while the platform owns the runtime contract. Validate fresh workspaces
with `java -version` and `mvn -v`; both should report Java 21 before running
the Quarkus build.

Real keys are never committed to Git. Use the private local model for sensitive code. Use approved external models only when the demo policy allows provider-side processing.

Continue is the IDE assistant path for chat, explanations, edits, and code assistance. OpenCode is the terminal-based agent path for later workflow stages. Continue terminal execution is not treated as validated unless the tool returns captured output; for shell evidence, use `Terminal > New Terminal (Select a Container) > tooling-container` or the later OpenCode workflow.

Detailed user steps are in [`docs/DEVELOPER_WORKSPACE_GUIDE.md`](../../docs/DEVELOPER_WORKSPACE_GUIDE.md).

## How Red Hat And Open Source Make It Work

Red Hat OpenShift Dev Spaces provides Kubernetes-based cloud development environments built on Eclipse Che and DevWorkspace. Red Hat OpenShift supplies OAuth, routing, namespace isolation, RBAC, and runtime controls. Red Hat OpenShift AI MaaS supplies the governed OpenAI-compatible model endpoint and API key pattern.

Continue and OpenCode can consume standard OpenAI-compatible endpoints, so the workflow remains tool-flexible while platform teams keep workspace configuration and model access centralized.

## Trust Boundaries

Dev Spaces keeps workspaces, source access, tool configuration, and MaaS credentials under platform control, but the selected model still determines where prompts and code are processed. Local models stay inside OpenShift. External models are governed through MaaS but processed by the provider.

## Red Hat Products Used

- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides managed cloud development environments.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides MaaS model endpoints.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides identity, routing, namespace isolation, and runtime controls.

## Open Source Projects To Know

- [Eclipse Che](https://www.eclipse.org/che/) is the upstream cloud development environment behind Dev Spaces.
- [DevWorkspace](https://github.com/devfile/devworkspace-operator) provides Kubernetes-native workspace orchestration.
- [Continue](https://www.continue.dev/) provides the IDE AI assistant workflow.
- [OpenCode](https://opencode.ai/) provides terminal-based AI coding workflows.
- [OpenShift Toolkit](https://developers.redhat.com/products/openshift-ide-extensions) provides IDE-integrated OpenShift and Kubernetes resource workflows.

## Deploy And Validate

```bash
./stages/050-ai-assisted-development/deploy.sh
./stages/050-ai-assisted-development/validate.sh
```

Manifests: [`gitops/stages/050-ai-assisted-development/base/`](../../gitops/stages/050-ai-assisted-development/base/)

## References

- [Red Hat OpenShift Dev Spaces documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [Red Hat OpenShift Dev Spaces 3.27 Administration guide](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.27/html-single/administration_guide/index)
- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces)
- [OpenCode: Model-neutral AI coding assistant for OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/04/22/opencode-model-neutral-ai-coding-assistant-openshift-dev-spaces)
- [Continue](https://www.continue.dev/)
- [rhpds/mca-devspaces](https://github.com/rhpds/mca-devspaces)

## Demo Script

### Part 1 — A developer's first hour (governed workspace)

**Know.** Coolstore's engineering team is under pressure to adopt AI coding
tools. Developers were already pasting code into public chatbots; security
wants that stopped without blocking productivity. Onboarding a developer to a
correctly configured AI toolchain used to mean days of local setup and a
personal API key nobody tracked.

**Show.**
- Log in to the RHOAI dashboard as `ai-developer` and open Dev Spaces; start
  the `getting-started-ai-coding` workspace.
- While it starts, say: "No local setup, no personal model keys. The
  platform team provisioned this workspace — the AI assistant inside it is
  already connected to company-approved models through governed endpoints."
- When the IDE opens, show Continue in the sidebar and open
  `~/.continue/config.yaml`: point at the MaaS base URL and the fact that
  the API key was issued by the platform, scoped to this developer, with
  token limits and full usage telemetry.
- **What they should notice:** the developer never saw a provider console,
  never handled a raw key, and the first AI-assisted line of code happens
  minutes after joining.

### Part 2 — One-shot vibe coding: the possibilities and the wall

**Know.** One-shot prompting is the entry drug of AI coding: brilliant for
scaffolding and exploration, unreliable for production-shaped work. The demo
does not hide this — the limitation IS the lesson that motivates Stage 060.

**Show.** Run the [vibe-coding exercise](vibe-coding-exercise.md): ask
Continue for the small Quarkus app, watch it scaffold in seconds, then review
like a senior engineer. Let the audience find the gaps with you (naming,
missing tests, no docs alignment). Close with: "The model is not wrong — it
just doesn't know how WE build software. Teaching it that is the next stage."

## Demo Exercise: One-Shot Vibe Coding

The [vibe-coding exercise](vibe-coding-exercise.md) is the hands-on part of
this stage: a developer opens the governed workspace and builds with Continue
using one-shot prompts — the most basic form of AI-assisted coding. Run it to
see both sides:

- what one-shot prompting does well: scaffolding, boilerplate, explanation,
  and quick exploration with private models;
- where it falls short: project standards, multi-file consistency, hidden
  requirements, and repeatability — the limits that motivate the agentic
  workflow in Stage 060.

Human review discipline applies from the first prompt; the exercise includes
the review gates that stay mandatory through Stages 060 and 070.

## Next Stage

[Stage 060: Agentic Development](../060-ai-agentic-development/README.md)
replaces one-shot prompts with OpenCode agents guided by AGENT.md and
reusable skills that encode enterprise Quarkus standards.
