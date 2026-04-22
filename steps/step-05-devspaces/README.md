# Step 05: Dev Spaces and AI Code Assistant
**"AI-assisted coding in a governed environment"** — Deploy OpenShift Dev Spaces and configure the Continue extension to connect to the private NVIDIA Nemotron model for AI-assisted software development.

## Overview

Developers need AI coding assistance inside their existing tools, not a separate workflow. This step deploys **OpenShift Dev Spaces** — Red Hat's containerized cloud-native IDE running on OpenShift — and demonstrates how the **Continue** extension connects to the private model endpoint deployed in Step 03. The result is a private, governed AI code assistant that runs entirely within the organization's infrastructure.

### What Gets Deployed

```text
Dev Spaces & AI Code Assistant
├── Dev Spaces Operator          → Manages containerized IDE workspaces
├── CheCluster Instance          → Dev Spaces platform (openshift-devspaces)
└── Coding Exercises             → Python starter code for "improve this" demo
```

Manifests: [`gitops/step-05-devspaces/base/`](../../gitops/step-05-devspaces/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-05-devspaces/deploy.sh
./steps/step-05-devspaces/validate.sh
```

</details>

## The Demo

> In this demo, a developer uses a private AI code assistant inside OpenShift Dev Spaces. The model endpoint comes from MaaS (Step 03) and is accessed via an API token — no external AI services involved.

### Setting Up the Code Assistant

> The developer opens their Dev Spaces workspace, installs the Continue extension, and connects it to the private Nemotron model.

1. Open the Dev Spaces dashboard URL printed by `deploy.sh`
2. Create a new workspace from the coding exercises in this repository
3. In VS Code, install the **Continue** extension from the marketplace
4. Configure Continue with the MaaS model endpoint:
   - Open Continue settings (gear icon)
   - Add a new model provider with the Nemotron endpoint URL from Step 03
   - Set the API key to the token generated from the RHOAI dashboard

**Expect:** Continue extension shows the Nemotron model as available in the sidebar.

> The developer is now connected to a private, governed AI model. No data leaves the cluster, no external API keys, no third-party dependencies.

### AI-Assisted Code Improvement

> With the code assistant configured, the developer demonstrates the experience by asking the model to improve starter code.

1. Open `coding-exercises/rock_paper_scissors.py`
2. Select the entire `play()` function
3. Ask Continue: "Make this code more enterprise-grade: add type hints, input validation, error handling, logging, and make it testable"
4. Review the AI-generated improvements

**Expect:** The model returns an improved version with proper typing, validation, structured logging, and a testable design.

> This is private AI coding assistance at work. The developer gets the same experience as cloud-hosted AI tools, but the model runs on their organization's GPUs, governed by MaaS policies, with full observability through Grafana.

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
