# Stage 060: AI-Assisted Development

## Why This Matters

AI-assisted development is useful when it appears where developers already work: IDEs, terminals, tests, and review workflows. The enterprise concern is how to offer that experience without personal provider keys, unmanaged plugins, or local machine drift.

Stage 060 is the first rung of the maturity ladder, and it runs entirely on
platform rails: the developer **enters through the portal** (the
`assisted-quarkus-feature` golden-path template provisions a personal copy of
the Parasol Insurance application), codes with Continue in a governed Dev
Spaces workspace, and **exits through the pipeline** (every push to `main`
runs the shared build with a SonarQube gate that fails on any new issue).
One-shot prompting shows its power — and its limits, which motivate Stage
070.

## Architecture

![Stage 060 layered capability map](../../docs/assets/architecture/stage-060-capability-map.svg)

## What This Stage Adds

This is a workflow-only stage: the infrastructure below is owned by Stage
050 (`devspaces` component and golden-path templates); this stage owns the
developer experience that runs on it.

- Red Hat OpenShift Dev Spaces deployed via the `stable` operator channel with automatic InstallPlan approval.
- 9 pre-provisioned DevWorkspaces (3 per persona: `kubeadmin`, `ai-developer`, `ai-admin`) for onboarding, Coolstore inventory engineering, and MCA Coolstore modernization.
- Continue v1.3.38 installed as a default extension and configured for MaaS-published OpenAI-compatible endpoints.
- OpenCode configured for the same MaaS endpoints via rendered `opencode.json`.
- A `devspace-ai-tools-init` ConfigMap with a centralized init script that renders tool configuration from MaaS environment variables at workspace startup.
- Java 21 configured as the default workspace shell and Maven runtime for the Quarkus demo exercises.
- MTA VS Code extensions scoped only to the `mca-coolstore` workspace through `DEFAULT_EXTENSIONS`.

## What To Notice And Why It Matters

Stage 060 turns governed model access into a developer experience.

- Workspaces are reproducible and isolated by OpenShift identity and namespace.
- Continue and OpenCode use MaaS endpoints instead of personal provider keys.
- Local models keep source-code prompts inside the OpenShift platform boundary.
- Approved external models can use the same workflow only when provider-side processing is allowed.
- The MTA workspace gets modernization extensions without polluting the onboarding or inventory workspaces.
- The tooling image is `che-incubator/cli-ai-tools` (community incubator image, documented as a workaround in BACKLOG until an official Red Hat UDI variant includes the required CLI tooling).
- MaaS API key provisioning uses a `devspace-maas-key-provisioner` ServiceAccount authorized on the Stage 040 developer subscription — keys are minted per-developer at deploy, stored in a workspace namespace Secret, and consumed by the init script at startup.
- The MCP URL in rendered Continue/OpenCode config depends on Stage 040 deploying the OpenShift MCP server to `rhoai-mcp` namespace on port 8080. The init script uses environment variables from the ConfigMap to render the correct cluster-internal endpoint.

This matters because regulated enterprises need AI coding assistance to fit existing controls for identity, network access, approved tooling, credential handling, and data residency.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift Dev Spaces provides Kubernetes-based cloud development environments built on Eclipse Che and DevWorkspace. Red Hat OpenShift supplies OAuth, routing, namespace isolation, RBAC, and runtime controls. Red Hat OpenShift AI MaaS supplies the governed OpenAI-compatible model endpoint and API key pattern.

Continue and OpenCode can consume standard OpenAI-compatible endpoints, so the workflow remains tool-flexible while platform teams keep workspace configuration and model access centralized.

## Trust Boundaries

Dev Spaces keeps workspaces, source access, tool configuration, and MaaS credentials under platform control, but the selected model still determines where prompts and code are processed. Local models stay inside OpenShift. External models are governed through MaaS but processed by the provider.

Real keys are never committed to Git. Continue terminal execution is not treated as validated unless the tool returns captured output; for shell evidence, use the tooling-container terminal or the later OpenCode workflow.

## Red Hat Products Used

- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides managed cloud development environments.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides MaaS model endpoints and API key governance.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides identity, routing, namespace isolation, and runtime controls.

## Open Source Projects To Know

- [Eclipse Che](https://www.eclipse.org/che/) is the upstream cloud development environment behind Dev Spaces.
- [DevWorkspace Operator](https://github.com/devfile/devworkspace-operator) provides Kubernetes-native workspace orchestration.
- [Continue](https://www.continue.dev/) provides the IDE AI assistant workflow (chat, edits, code assistance).
- [OpenCode](https://opencode.ai/) provides terminal-based AI coding workflows for agentic development.
- [OpenShift Toolkit](https://developers.redhat.com/products/openshift-ide-extensions) provides IDE-integrated OpenShift and Kubernetes resource workflows.

## Deploy And Validate

This is a workflow-only stage: it deploys no cluster resources of its own.
The Dev Spaces platform, persona workspaces, and MaaS key provisioning is owned by
[Stage 050: Advanced Application Platform](../050-advanced-app-platform/README.md)
(`devspaces` component). Deploy stage 050 first, then validate this stage's
prerequisites read-only:

```bash
./stages/060-ai-assisted-development/validate.sh
```

Manifests: [`gitops/stages/050-advanced-app-platform/base/devspaces/`](../../gitops/stages/050-advanced-app-platform/base/devspaces/)

Detailed user steps for workspace onboarding: [`docs/DEVELOPER_WORKSPACE_GUIDE.md`](../../docs/DEVELOPER_WORKSPACE_GUIDE.md)

## References

| Resource | Link |
|----------|------|
| Red Hat OpenShift Dev Spaces documentation | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/ |
| Dev Spaces 3.28 Administration guide | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html-single/administration_guide/index |
| MaaS code assistant quickstart | https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant |
| AI code assistants with Dev Spaces | https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces |
| OpenCode for OpenShift Dev Spaces | https://developers.redhat.com/articles/2026/04/22/opencode-model-neutral-ai-coding-assistant-openshift-dev-spaces |
| Continue | https://www.continue.dev/ |
| rhpds/mca-devspaces | https://github.com/rhpds/mca-devspaces |

## Demo Script

### Part 1 — Self-service in: one field, a full environment

**Know.** Every rung of the ladder starts the same way: not a ticket, not a
wiki page — a golden-path template in Developer Hub. The platform team
defined it; the developer consumes it.

**Show.**
- Open Developer Hub → Create → **AI-Assisted Development: Parasol Insurance
  workspace**. Fill the one field (repository name, e.g.
  `parasol-insurance-alice`) and run it.
- Show the output links: a fresh GitHub repository (their own copy of the
  Parasol app — golden repos are never mutated) and the new catalog
  component.
- Say: "That initial commit already ran the pipeline once — the SonarQube
  baseline for this repo is seeded. Whatever the AI writes next is *new
  code* against a gate that fails on any new issue."
- **What they should notice:** one field. Repo, catalog entry, CI wiring,
  and quality baseline all existed before the developer wrote a line.

### Part 2 — Continue in the governed workspace: the one-shot high

**Know.** One-shot prompting is the entry drug of AI coding: brilliant for
scaffolding, unreliable for production-shaped work. The demo does not hide
this — the limitation IS the lesson.

**Show.**
- Open the new repository in Dev Spaces (`<Dev Spaces URL>/#<repo URL>`);
  run **Start Development mode** and open the Parasol dashboard.
- Show `.continue/config.yaml`: MaaS base URL, platform-issued key, token
  limits, usage telemetry. No provider console, no raw key.
- Ask Continue for the new endpoint using
  [`demo-assets/continue-prompts.md`](demo-assets/continue-prompts.md) — or
  paste the prepared
  [`demo-assets/ClaimsStatsResource-with-smells.java`](demo-assets/ClaimsStatsResource-with-smells.java)
  (the reliable path; live generation is the bonus). Hot reload: the
  `/api/claims/stats` endpoint works instantly.
- **What they should notice:** the code *works*. It also carries
  `System.out.println`, an empty catch block, and field injection — plausible
  code that ignores the team's standards.

### Part 3 — Trusted delivery out: the gate catches the AI

**Know.** The platform does not rely on the developer noticing. Every push
exits through the shared pipeline, and the quality gate fails on any new
issue — deliberately, deterministically.

**Show.**
- Commit and push to `main`. Watch the PipelineRun: clone → build →
  **sonar-scan FAILS** on the intentional smells.
- Open SonarQube: the three new issues, on exactly the new code.
- Back in the workspace, ask Continue to fix them (proper logging,
  constructor injection, logged exception —
  [`demo-assets/ClaimsStatsResource-fixed.java`](demo-assets/ClaimsStatsResource-fixed.java)
  is the reference). Push again → pipeline green.
- Close: "Self-service in, trusted delivery out. The AI wrote the code; the
  platform proved it. But notice what *we* had to do — spot the smells, know
  the standards, prompt the fix. Teaching the agent our standards so we
  don't have to is Stage 070."

### Optional — A developer's first hour (onboarding workspace)

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

## Demo Exercise: One-Shot Vibe Coding (optional deep-dive)

The [vibe-coding exercise](vibe-coding-exercise.md) is an optional hands-on
onboarding walkthrough using the `getting-started-ai-coding` workspace. The
stage's primary demo is the golden-path flow above; the exercise remains
useful for workshops where each attendee codes along, and its human-review
discipline applies from the first prompt onward.

## Next Stage

[Stage 070: Agentic Development](../070-ai-agentic-development/README.md)
replaces one-shot prompts with OpenCode agents guided by AGENTS.md and
reusable skills that encode enterprise Quarkus standards.
