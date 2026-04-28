# Step 04: Dev Spaces and AI Code Assistant
**"AI-assisted coding in a governed environment"** — Deploy OpenShift Dev Spaces and configure the Continue extension to connect to the private NVIDIA Nemotron model for AI-assisted software development.

## Overview

Developers need AI coding assistance inside their existing tools, not a separate workflow. This step deploys **OpenShift Dev Spaces** — Red Hat's containerized cloud-native IDE running on OpenShift — and demonstrates how the **Continue** extension connects to the private model endpoint deployed in Step 03. The result is a private, governed AI code assistant that runs entirely within the organization's infrastructure.

### What Gets Deployed

```text
Dev Spaces & AI Code Assistant
├── Dev Spaces Operator          → Manages containerized IDE workspaces
├── CheCluster Instance          → Dev Spaces platform (open-vsx.org, no-idle, 1200s timeout)
├── Per-User Workspaces (3 users)
│   ├── wksp-kubeadmin            → Namespace + RoleBinding + DevWorkspace
│   ├── wksp-ai-admin             → Namespace + RoleBinding + DevWorkspace
│   └── wksp-ai-developer         → Namespace + RoleBinding + DevWorkspace
└── Exercises Repo Clone         → adnan-drina/coding-exercises
    ├── devfile.yaml              → Auto-configures Continue via postStart
    ├── coding-exercises/         → 3 game starters + solutions
    ├── .vscode/extensions.json   → Recommends Continue extension
    └── .vscode/config.yaml       → Continue model config template
```

Manifests: [`gitops/step-04-devspaces/base/`](../../gitops/step-04-devspaces/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-04-devspaces/deploy.sh
./steps/step-04-devspaces/validate.sh
```

</details>

## How It Works Under the Hood

When a user navigates from the RHOAI dashboard to Dev Spaces:

1. The **Dev Spaces dashboard** authenticates the user via OpenShift OAuth
2. It looks for a `DevWorkspace` CR in the user's pre-provisioned namespace (`wksp-<username>`)
3. The **DevWorkspace Operator** creates a pod with 2 containers:
   - `tooling-container` — the UDI image (4Gi memory) with VS Code server, tools, and the cloned repo
   - `che-gateway` — a Traefik sidecar that routes browser traffic to VS Code
4. The pod runs in the user's workspace namespace on a regular worker node
5. A `claim-devworkspace` PVC persists workspace data across restarts

## Projects Involved

| Project | Purpose | Who Uses It | Visible in RHOAI Dashboard |
|---------|---------|-------------|---------------------------|
| `maas` | Model serving — where `LLMInferenceService` models run | `ai-admin` only | Yes (`ai-admin`) |
| `coding-assistant` | Developer's home project — model discovery, API token generation, Playground | `ai-developer`, `ai-admin` | Yes (both users) |
| `wksp-*` | Dev Spaces workspace — contains the running VS Code pod | Each user | No (OpenShift only) |

## The Demo

> In this demo, a developer uses a private AI code assistant inside OpenShift Dev Spaces. The model endpoint comes from MaaS (Step 03) and is accessed via an API token — no external AI services involved.

### Act 1: Discover the Model (RHOAI Dashboard)

1. Log in to the RHOAI Dashboard as `ai-developer` (via `demo-htpasswd`)
2. Navigate to **GenAI Studio > AI asset endpoints**
3. Select the **Coding Assistant** project from the dropdown
4. Click the **Models as a service** tab — both models appear with MaaS badges
5. Click **View** on the **nemotron-3-nano-30b-a3b** model
6. Copy the **External endpoint URL**
7. Click **Generate API token** — copy the token

### Act 2: Open the Development Environment (Dev Spaces)

1. Open Dev Spaces: `https://devspaces.<cluster>/`
2. Log in as `ai-developer` (same credentials)
3. The pre-provisioned workspace `exercises` is listed
4. Click to start it — VS Code opens in the browser
5. The [coding exercises](https://github.com/adnan-drina/coding-exercises) repo is cloned (includes `devfile.yaml`)

### Act 3: Configure the Continue Extension

1. Install the Continue extension (recommended via `.vscode/extensions.json`, available from open-vsx.org)
2. Copy the config template to Continue's config directory:
   ```bash
   cp /projects/coding-exercises/.vscode/config.yaml ~/.continue/config.yaml
   ```
3. Open `~/.continue/config.yaml` and configure the connection:
   - **Provider:** Already set to `openai` (OpenAI Compatible)
   - **Model:** Already set to `nemotron-3-nano-30b-a3b` (model deployment name)
   - **apiBase:** Replace `YOUR_MAAS_ROUTE` with the endpoint URL from Act 1, append `/v1`
     (e.g., `https://maas.<cluster>/maas/nemotron-3-nano-30b-a3b/v1`)
   - **apiKey:** Replace `YOUR_API_KEY` with the API token from Act 1
4. In the Continue sidebar, select **Local Config** from the dropdown
5. The Nemotron model appears in the model selector

### Act 4: AI-Assisted Coding

Three game exercises are available in `coding-exercises/game_starters/`:

| Exercise | What to Ask Continue |
|----------|---------------------|
| `rock_paper_scissors/` | "Make this code enterprise-grade: add type hints, validation, logging, testability" |
| `simple_quiz/` | Follow the prompts in the file — ask Continue to generate a quiz game from scratch |
| `word_scramble/` | Follow the prompts in the file — ask Continue to generate a word scramble game |

Each starter file contains ready-to-use prompts and enhancement ideas. Solutions are in `game_solutions/` for reference.

## Privacy and Data Sovereignty

A key advantage of this approach over cloud-hosted AI services: **no code or data leaves the cluster**. The model runs on the organization's GPUs, the Dev Spaces workspace runs on the same cluster, and the API calls between Continue and the Nemotron model stay within the cluster network via the MaaS Gateway. You can verify this by opening the browser's Network tab — all requests go to `maas.<cluster-domain>`, not to any external service.

This addresses the common concern with AI coding assistants: organizations can provide developers with AI-powered tooling while maintaining full control over data, privacy, and intellectual property.

## Key Takeaways

**For business stakeholders:**

- Developers get AI coding assistance without sending code to external services
- All AI interactions stay within organizational boundaries — data sovereignty by design
- Usage is tracked and governed through MaaS tiers from Step 03

**For technical teams:**

- OpenShift Dev Spaces provides reproducible, containerized workspaces on the same cluster
- Dev Spaces acts as an **AI guardrail** — if an AI agent generates bad code or corrupts a config, you can instantly revert to a clean slate by restarting the workspace from the devfile
- Continue is open-source and works with any OpenAI-compatible endpoint
- Model endpoints are reusable — the same Nemotron model serves Playground, MaaS API, and IDE
- Unlike cloud-hosted AI services (GitHub Copilot, etc.), this approach keeps all code and data on-prem with full control over privacy, security, and IP
- Unlike local-model approaches (e.g., Ollama sidecar), MaaS provides centralized GPU management, rate limiting, and usage tracking across all developers

## References

- [OpenShift Dev Spaces Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [Continue — Open-Source AI Code Assistant](https://www.continue.dev/)
- [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces) — cloud vs on-prem models, code assistant comparison
- [OpenCode: Model-neutral AI coding assistant for Dev Spaces](https://developers.redhat.com/articles/2026/04/22/opencode-model-neutral-ai-coding-assistant-openshift-dev-spaces) — terminal-based agentic AI, works with MaaS endpoints
- [Red Hat Developer: Private AI Coding Assistant with Dev Spaces](https://developers.redhat.com/learn/openshift-ai/integrate-private-ai-coding-assistant-your-cde-using-ollama-continue-openshift-dev-spaces) — alternative approach using Ollama + local models
