# Step 04: Dev Spaces and AI Code Assistant
**"AI-assisted coding in a governed environment"** — Deploy OpenShift Dev Spaces and configure the Continue extension to connect to the private NVIDIA Nemotron model for AI-assisted software development.

## Overview

Developers need AI coding assistance inside their existing tools, not a separate workflow. This step deploys **OpenShift Dev Spaces** — Red Hat's containerized cloud-native IDE running on OpenShift — and demonstrates how the **Continue** extension connects to the private model endpoint deployed in Step 03. The result is a private, governed AI code assistant that runs entirely within the organization's infrastructure.

### What Gets Deployed

```text
Dev Spaces & AI Code Assistant
├── Dev Spaces Operator          → Manages containerized IDE workspaces
├── CheCluster Instance          → Dev Spaces platform (openshift-devspaces)
├── Per-User Workspaces
│   ├── wksp-ai-admin            → Namespace + RoleBinding + DevWorkspace
│   └── wksp-ai-developer        → Namespace + RoleBinding + DevWorkspace
└── Coding Exercises             → 3 game starters + solutions for "code with AI" demo
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

1. The **Dev Spaces dashboard** (`https://devspaces.<cluster>`) authenticates the user via OpenShift OAuth
2. It looks for a `DevWorkspace` CR in the user's pre-provisioned namespace (`wksp-<username>`)
3. The **DevWorkspace Operator** creates a pod with 2 containers:
   - `tooling-container` — the UDI image with VS Code server, tools, and the cloned repo
   - `che-gateway` — a Traefik sidecar that routes browser traffic to VS Code
4. The pod runs in the **user's workspace namespace** (e.g., `wksp-ai-developer`), on a regular worker node
5. A `claim-devworkspace` PVC persists workspace data across restarts
6. The VS Code UI is accessed through the Dev Spaces URL: `https://devspaces.<cluster>/<username>/exercises/3100/`

## Projects Involved

| Project | Purpose | Who Uses It | Visible in RHOAI Dashboard |
|---------|---------|-------------|---------------------------|
| `maas` | Model serving — where `LLMInferenceService` models run | `ai-admin` only | Yes (`ai-admin`) |
| `coding-assistant` | Developer's home project — model discovery, API token generation, Playground | `ai-developer`, `ai-admin` | Yes (both users) |
| `wksp-ai-developer` | Dev Spaces workspace — contains the running VS Code pod | `ai-developer` | No (OpenShift only) |

The `coding-assistant` project is the developer's entry point in the RHOAI dashboard. From there, `ai-developer` sees MaaS models across the cluster (they appear in the **Models as a service** tab regardless of which project is selected). The `wksp-ai-developer` namespace only exists in OpenShift — it is not visible in the RHOAI dashboard.

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
5. The [MaaS Code Assistant quickstart](https://github.com/rh-ai-quickstart/maas-code-assistant) repo is cloned at `/projects/maas-code-assistant/`
6. VS Code recommends the **Continue** extension (from `.vscode/extensions.json`) — install it

### Act 3: Configure the Continue Extension

1. Continue installs from the public Open VSX registry (configured in the CheCluster)
2. Open a terminal in VS Code and copy the config template:
   ```bash
   cp /projects/maas-code-assistant/.vscode/config.yaml ~/.continue/config.yaml
   ```
3. Open `~/.continue/config.yaml` and replace the placeholders:
   - Replace `YOUR_MAAS_ROUTE` with the model endpoint URL from Act 1
   - Replace `YOUR_API_KEY` with the API token from Act 1
4. In the Continue sidebar, select **Local Config** from the dropdown
5. The Nemotron model appears in the model selector

> **Note:** The DevWorkspace has a `postStart` command that attempts to copy this config automatically, but due to a race condition with the git clone, it may not execute on the first workspace start. The manual `cp` step above is a reliable fallback.

### Act 4: AI-Assisted Coding

Three game exercises are available in `coding-exercises/game_starters/` (from the quickstart repo):

| Exercise | What to Ask Continue |
|----------|---------------------|
| `rock_paper_scissors/` | "Make this code enterprise-grade: add type hints, validation, logging, testability" |
| `simple_quiz/` | Follow the prompts in the file — ask Continue to generate a quiz game from scratch |
| `word_scramble/` | Follow the prompts in the file — ask Continue to generate a word scramble game |

Each starter file contains ready-to-use prompts and enhancement ideas. Solutions are in `game_solutions/` for reference.

**Demo flow:**
1. Open `game_starters/rock_paper_scissors/rock_paper_scissors.py`
2. Select the code, right-click > **Continue: Edit** or use the chat sidebar
3. Paste the prompt from the file header
4. Watch the model rewrite the code with improvements
5. Optionally run it in the terminal to verify

## Key Takeaways

**For business stakeholders:**

- Developers get AI coding assistance without sending code to external services
- All AI interactions stay within organizational boundaries — data sovereignty by design
- Usage is tracked and governed through MaaS tiers from Step 03

**For technical teams:**

- OpenShift Dev Spaces provides reproducible, containerized workspaces on the same cluster
- Continue is open-source and works with any OpenAI-compatible endpoint
- Model endpoints are reusable — the same Nemotron model serves Playground, MaaS API, and IDE

## References

- [OpenShift Dev Spaces Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [Continue — Open-Source AI Code Assistant](https://www.continue.dev/)
- [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
