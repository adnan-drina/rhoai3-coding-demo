# Stage 060: AI-Assisted Development

## Why This Matters

AI-assisted development is useful when it appears where developers already work: IDEs, terminals, tests, and review workflows. The enterprise concern is how to offer that experience without personal provider keys, unmanaged plugins, or local machine drift.

Stage 060 is the first rung of the maturity ladder, and it runs entirely on platform rails: the developer **enters through the portal catalog** — the `coolstore-inventory-service` component is the single entry point, a deployed brownfield Quarkus service discovered in Developer Hub, with links straight into its governed Dev Spaces workspace — extends the service with Kilo Code ("vibe coding" a new component), and **exits through the pipeline** (every push to `main` runs coolstore's own `app-push` pipeline in `coolstore-dev`, with a SonarQube gate that fails on any new issue or under-tested new code). One-shot prompting shows its power — and its limits, which motivate Stage 070.

## Architecture

## What This Stage Adds

This is a workflow-only stage: the infrastructure below is owned by Stage 050 (`devspaces`, `coolstore`, `pipelines`, and `rhdh` components); this stage owns the developer experience that runs on it.

- Red Hat OpenShift Dev Spaces deployed via the `stable` operator channel with automatic InstallPlan approval.
- 9 pre-provisioned DevWorkspaces (3 per persona: `kubeadmin`, `ai-developer`, `ai-admin`) for onboarding, Coolstore inventory engineering, and MCA Coolstore modernization.
- **Kilo Code 7.4.8** installed as a default extension and configured for MaaS-published OpenAI-compatible endpoints. Config at `~/.config/kilo/kilo.json` (OpenCode-schema JSON) with four providers: Qwen3.6 (default), local Nemotron, qwen3-235b (16K-context external), and minimax-m2 (196K-context external). Governance rules at `~/.config/kilo/AGENTS.md`. MCP `openshift` server at `http://openshift-mcp.rhoai-mcp.svc:8080/mcp`.
- **One tool per stage by design:** 060 workspaces are Kilo-only, 070 workspaces are OpenCode-only — never both configured in the same workspace. The project's `.opencode/` directory is the paradigm signal: present selects OpenCode, absent selects Kilo. The init script removes the other tool's config on every start.
- A `devspace-ai-tools-init` ConfigMap with a centralized init script that renders tool configuration from MaaS environment variables at workspace startup.
- Java 21 configured as the default workspace shell and Maven runtime for the Quarkus demo exercises.
- MTA VS Code extensions scoped only to the `mca-coolstore` workspace through `DEFAULT_EXTENSIONS`.

## What To Notice And Why It Matters

Stage 060 turns governed model access into a developer experience.

- Workspaces are reproducible and isolated by OpenShift identity and namespace.
- Kilo Code and OpenCode use MaaS endpoints instead of personal provider keys.
- Local models keep source-code prompts inside the OpenShift platform boundary.
- Approved external models can use the same workflow only when provider-side processing is allowed.
- The MTA workspace gets modernization extensions without polluting the onboarding or inventory workspaces.
- The tooling image is `che-incubator/cli-ai-tools` (community incubator image, documented as a workaround in BACKLOG until an official Red Hat UDI variant includes the required CLI tooling).
- MaaS API key provisioning uses a `devspace-maas-key-provisioner` ServiceAccount authorized on the Stage 040 developer subscription — keys are minted per-developer at deploy, stored in a workspace namespace Secret, and consumed by the init script at startup.
- The MCP URL in rendered Kilo Code/OpenCode config depends on Stage 040 deploying the OpenShift MCP server to `rhoai-mcp` namespace on port 8080. The init script uses environment variables from the ConfigMap to render the correct cluster-internal endpoint.
- **Demo notes:** the first fresh workspace start downloads a 111 MB Kilo Code VSIX from Open VSX (the skip-guard in the init script makes restarts instant after the first download). The `minimax-m2` provider emits `<think>` reasoning blocks through LiteLLM — the presenter should know this appears in Kilo Code output and is expected behavior, not an error. The coolstore workspace is Kilo-only (OpenCode lives in Stage 070's scaffolded workspaces).

This matters because regulated enterprises need AI coding assistance to fit existing controls for identity, network access, approved tooling, credential handling, and data residency.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift Dev Spaces provides Kubernetes-based cloud development environments built on Eclipse Che and DevWorkspace. Red Hat OpenShift supplies OAuth, routing, namespace isolation, RBAC, and runtime controls. Red Hat OpenShift AI MaaS supplies the governed OpenAI-compatible model endpoint and API key pattern.

Kilo Code and OpenCode can consume standard OpenAI-compatible endpoints, so the workflow remains tool-flexible while platform teams keep workspace configuration and model access centralized.

## Trust Boundaries

Dev Spaces keeps workspaces, source access, tool configuration, and MaaS credentials under platform control, but the selected model still determines where prompts and code are processed. Local models stay inside OpenShift. External models are governed through MaaS but processed by the provider.

Real keys are never committed to Git. Kilo Code terminal execution is not treated as validated unless the tool returns captured output; for shell evidence, use the tooling-container terminal or the later OpenCode workflow.

## Red Hat Products Used

- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides managed cloud development environments.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides MaaS model endpoints and API key governance.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides identity, routing, namespace isolation, and runtime controls.

## Open Source Projects To Know

- [Eclipse Che](https://www.eclipse.org/che/) is the upstream cloud development environment behind Dev Spaces.
- [DevWorkspace Operator](https://github.com/devfile/devworkspace-operator) provides Kubernetes-native workspace orchestration.
- [Kilo Code](https://kilocode.ai/) provides the IDE AI assistant workflow (chat, edits, code assistance).
- [OpenCode](https://opencode.ai/) provides terminal-based AI coding workflows for agentic development.
- [OpenShift Toolkit](https://developers.redhat.com/products/openshift-ide-extensions) provides IDE-integrated OpenShift and Kubernetes resource workflows.

## Deploy And Validate

This is a workflow-only stage: it deploys no cluster resources of its own. The Dev Spaces platform, persona workspaces, and MaaS key provisioning is owned by [Stage 050: Advanced Application Platform](../050-advanced-app-platform/README.md) (`devspaces` component). Deploy stage 050 first, then validate this stage's prerequisites read-only:

```bash
./stages/060-ai-assisted-development/validate.sh
```

Manifests: [`gitops/stages/050-advanced-app-platform/base/devspaces/`](../../gitops/stages/050-advanced-app-platform/base/devspaces/)

## References

| Resource | Link |
|----------|------|
| Red Hat OpenShift Dev Spaces documentation | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/ |
| Dev Spaces 3.28 Administration guide | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html-single/administration_guide/index |
| MaaS code assistant quickstart | https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant |
| AI code assistants with Dev Spaces | https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces |
| OpenCode for OpenShift Dev Spaces | https://developers.redhat.com/articles/2026/04/22/opencode-model-neutral-ai-coding-assistant-openshift-dev-spaces |
| Kilo Code | https://kilocode.ai/ |
| rhpds/mca-devspaces | https://github.com/rhpds/mca-devspaces |

## Demo Script

### Part 1 — Self-service in: discover a running service in the catalog

**Know.** The first rung starts brownfield: a real service, already deployed, already wired to CI — discovered in the portal, not assembled from a wiki page. The platform team put it there; the developer consumes it.

**Show.**
- Open Developer Hub → Catalog → **Coolstore Inventory Service** (the only component — that is deliberate; this is the single developer entry point).
- Walk the component page: the **Topology** tab shows the service running in `coolstore-dev`; the **CI** tab shows its own `app-push` pipeline history (green); the **API** tab shows `inventory-api`; the deployed-app link answers at `/api/inventory`.
- Say: "This isn't a scaffold — it's the team's service, live in its dev environment, with its own pipeline in its own namespace. Whatever the AI writes next lands against a SonarQube gate that fails on any new issue."
- **What they should notice:** catalog entry, running dev deployment, CI wiring, and quality baseline all existed before the developer wrote a line — and the pipeline belongs to this project, not to a central queue.

### Part 2 — Kilo Code in the governed workspace: the one-shot high

**Know.** One-shot prompting is the entry drug of AI coding: brilliant for scaffolding, unreliable for production-shaped work. The demo does not hide this — the limitation IS the lesson.

**Show.**
- From the component page, click the **Dev Spaces** link — the workspace opens on the `coolstore-inventory-service` repository; start dev mode via **Tasks: Run Task → devfile → 2. Start Development mode (Hot reload)**.
- Show Kilo Code's MaaS configuration: base URL, platform-issued key, token limits, usage telemetry. No provider console, no raw key.
- Ask Kilo Code for the new endpoint using [`demo-assets/kilo-code-prompts.md`](demo-assets/kilo-code-prompts.md) — the deliberately flawed spec makes the smells deterministic, so live generation is the reliable path. Hot reload: `/api/inventory/stats` answers instantly.
- **What they should notice:** the code *works*. It also carries `System.out.println`, an empty catch block, and field injection — plausible code that ignores the team's standards.

### Part 3 — Trusted delivery out: the gate catches the AI

**Know.** The platform does not rely on the developer noticing. Every push to `main` exits through the project's own pipeline in `coolstore-dev`, and the quality gate fails on any new issue and on new code below 80% test coverage — deliberately, deterministically. (The generation prompt asks for unit tests up front, so the red gate is about the smells, not coverage.)

**Show.**
- Commit and push to `main`. Watch the PipelineRun appear on the component's **CI** tab: clone → build → **sonar-scan FAILS** on the intentional smells.
- Open SonarQube: the new issues on exactly the new code — the instructed smells plus pre-existing debt in the touched repository file (the gate reviews everything you change, not just what you meant to write).
- Back in the workspace, ask Kilo Code to fix them (proper logging, constructor injection, logged exception). Push again → pipeline green → `tag-latest` republishes `:latest`, so the running dev deployment picks the endpoint up on its next rollout.
- Close: "Self-service in, trusted delivery out. The AI wrote the code; the platform proved it. But notice what *we* had to do — spot the smells, know the standards, prompt the fix. Teaching the agent our standards so we don't have to is Stage 070."

### Optional — A developer's first hour (onboarding workspace)

The onboarding flow using the `getting-started-ai-coding` workspace has been retired in favor of the hands-on coding exercise below, which covers the same concepts within the golden-path loop.

## Demo Exercise: AI-Assisted Development on the Golden Path

The [coding exercise](coding-exercise.md) is the hands-on user guide for the full golden-path loop: discover a service in the catalog, extend it with Kilo Code, push through a SonarQube quality gate, read the failure report, fix the code with a stronger model, and push until the pipeline goes green. Use it for live demos, workshops, and self-paced developer onboarding.

## Next Stage

[Stage 070: Agentic Development](../070-ai-agentic-development/README.md) replaces one-shot prompts with OpenCode agents guided by AGENTS.md and reusable skills that encode enterprise Quarkus standards.
