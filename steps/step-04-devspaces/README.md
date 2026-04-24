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

| Project | Purpose | Who Uses It |
|---------|---------|-------------|
| `maas` | Model serving — where `LLMInferenceService` models run | Platform (step-03) |
| `coding-assistant` | RHOAI Data Science project — visible in the dashboard for model discovery, API token generation, and Playground | `ai-developer`, `ai-admin` |
| `wksp-ai-developer` | Dev Spaces workspace namespace — contains the running VS Code pod | `ai-developer` |

The `coding-assistant` project is where the developer discovers models in GenAI Studio and generates API tokens. The `wksp-ai-developer` namespace is where the actual coding environment runs. Models are deployed in `maas` and accessed via the MaaS Gateway.

## The Demo

> In this demo, a developer uses a private AI code assistant inside OpenShift Dev Spaces. The model endpoint comes from MaaS (Step 03) and is accessed via an API token — no external AI services involved.

### Act 1: Discover the Model (RHOAI Dashboard)

1. Log in to the RHOAI Dashboard as `ai-developer` (via `demo-htpasswd`)
2. Navigate to **GenAI Studio > AI asset endpoints**
3. Select the **maas** project > **Models as a service** tab
4. Click **View** on the **nemotron-3-nano-30b-a3b** model
5. Copy the **External endpoint URL**
6. Click **Generate API token** — copy the token

### Act 2: Open the Development Environment (Dev Spaces)

1. Open Dev Spaces: `https://devspaces.<cluster>/`
2. Log in as `ai-developer` (same credentials)
3. The pre-provisioned workspace `exercises` is listed
4. Click to start it — VS Code opens in the browser
5. The repo is already cloned at `/projects/exercises/`

### Act 3: Configure the Continue Extension

1. The Continue extension is recommended via `.vscode/extensions.json` — install it
2. Open Continue settings (gear icon in the sidebar)
3. Use the template from `.vscode/config.yaml`:
   - Replace `YOUR_MAAS_ROUTE` with the model endpoint URL from Act 1
   - Replace `YOUR_API_KEY` with the API token from Act 1
4. The Nemotron model appears in the Continue sidebar

### Act 4: AI-Assisted Coding

Three game exercises are available in `steps/step-04-devspaces/coding-exercises/game_starters/`:

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
