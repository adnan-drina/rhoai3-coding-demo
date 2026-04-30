# Step 05: AI-Assisted Application Modernization with MTA
**"AI-powered application modernization at enterprise scale"** — Deploy Migration Toolkit for Applications 8.1 with Red Hat Developer Lightspeed to automate Java application modernization using the same private MaaS models from Step 03.

## Overview

Application modernization at scale requires more than manual code refactoring. This step deploys the **Migration Toolkit for Applications (MTA) 8.1** with **Red Hat Developer Lightspeed** — an AI-assisted code resolution engine that uses the governed MaaS models to generate precise migration-specific code fixes.

Unlike generic AI coding assistants, MTA combines static code analysis (2400+ Red Hat-maintained rules) with LLM-powered code generation. MTA identifies exactly what needs to change through analysis, then uses the MaaS endpoint to generate targeted code fixes — not generic suggestions, but migration-specific transformations.

> The same private Nemotron model that developers use in Dev Spaces (Step 04) is also used by MTA for automated code modernization — all governed through MaaS.

### What Gets Deployed

```text
AI-Assisted App Modernization (MTA 8.1)
├── MTA Operator                    → openshift-mta namespace
├── Tackle CR                       → MTA instance with AI config
│   ├── kai_llm_proxy_enabled       → LLM proxy for centralized key management
│   ├── kai_solution_server_enabled → RAG-based learning from past migrations
│   ├── kai_llm_provider: openai    → OpenAI-compatible API (MaaS Gateway)
│   ├── kai_llm_model               → nemotron-3-nano-30b-a3b (default, configurable)
│   └── kai_llm_baseurl             → MaaS Gateway endpoint
├── kai-api-keys Secret             → MaaS API key (OPENAI_API_KEY + OPENAI_API_BASE)
├── kai-db                          → Solution Server database (5Gi RWO)
├── RHBK (Keycloak)                 → MTA authentication
└── Post-deploy Job                 → Patches cluster-specific MaaS URL
```

Manifests: [`gitops/step-05-mta/base/`](../../gitops/step-05-mta/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-05-mta/deploy.sh
./steps/step-05-mta/validate.sh
```

</details>

## How MTA + AI Works

```text
Developer opens legacy Java app in VS Code
        |
        v
MTA Extension runs static code analysis (2400+ rules)
        |
        v
Issues identified (e.g., "javax.* must migrate to jakarta.*")
        |
        v
Developer requests AI fix → Red Hat Developer Lightspeed
        |
        v
LLM Proxy authenticates with MaaS Gateway (sk-oai-* key)
        |
        v
Nemotron model generates migration-specific code fix
        |
        v
Developer reviews diff, accepts/rejects changes
        |
        v
Agent AI re-analyzes → fewer issues → iterate until clean
```

### Two AI Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **Solution Server** | RAG-based: learns from past migrations, improves over time | Large migration waves with similar apps |
| **Agent AI** | Agentic loop: plans, fixes, compiles, re-analyzes automatically | Individual app modernization |

## The Demo

### Act 1: Access MTA UI

1. Get the MTA route: `oc get route -n openshift-mta`
2. Log in with `admin` / `Passw0rd!` (change on first login)
3. The MTA dashboard shows the migration workspace

### Act 2: Import a Sample Application

1. In MTA UI, go to **Migration > Applications**
2. Click **Create new** and import a legacy Spring Boot application
3. Provide the Git repository URL of the sample app

### Act 3: Run Analysis

1. Select the application and click **Analyze**
2. Choose target: **Quarkus** (or **cloud-readiness**)
3. MTA applies default rules and identifies migration issues
4. Review the analysis report — issues, effort estimates, affected files

### Act 4: AI-Assisted Code Fixes (VS Code Extension)

1. Open the application in **Dev Spaces** (or local VS Code)
2. Install the **MTA Extension** from the VS Code marketplace
3. Configure a profile: target **Quarkus**, enable default rules
4. Configure the LLM provider in `provider-settings.yaml`:
   ```yaml
   models:
     maas-nemotron: &active
       provider: "ChatOpenAI"
       environment:
         OPENAI_API_KEY: "YOUR_MAAS_API_KEY"
       args:
         model: "nemotron-3-nano-30b-a3b"
         configuration:
           baseURL: "https://maas.<cluster>/maas/nemotron-3-nano-30b-a3b/v1"
   ```
5. Run analysis in VS Code — issues appear in the MTA Issues pane
6. Click the **solutions icon** on an issue to request an AI fix
7. Review the generated code changes in the diff view
8. Accept or reject — Agent AI re-analyzes and iterates

### Act 5: Verify Migration Progress

1. Re-run analysis — fewer issues reported
2. Each accepted fix improves the Solution Server's knowledge
3. Future analyses of similar apps get better suggestions

## Key Takeaways

**For business stakeholders:**
- Accelerate large-scale application modernization with AI-assisted code changes
- The same governed AI models serve both developers (coding) and platform teams (migration)
- Migration knowledge accumulates across the organization via the Solution Server

**For technical teams:**
- MTA's static analysis provides precise context — the LLM knows exactly what to fix
- Model-agnostic: switch between Nemotron (private) and GPT-4o (external) via MaaS
- No model fine-tuning needed — RAG-based context from the Solution Server handles it
- The LLM proxy centralizes API key management — administrators rotate keys without touching developer configs

## Supported LLM Providers

MTA supports any OpenAI-compatible endpoint. In this demo, it connects to MaaS:

| Provider | Model | Configuration |
|----------|-------|---------------|
| MaaS (default) | nemotron-3-nano-30b-a3b | `kai_llm_provider: openai`, `kai_llm_baseurl: MaaS endpoint` |
| MaaS | gpt-4o | Change `kai_llm_model` and `kai_llm_baseurl` in Tackle CR |
| MaaS | gpt-4o-mini | Same as above (fast, cheaper) |
| OpenAI direct | gpt-4o | `kai_llm_provider: openai`, direct OpenAI API key |
| Ollama (local) | llama3.1, codellama | `kai_llm_provider: ollama` |

## References

- [MTA 8.1 Installation Guide](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/installing_the_migration_toolkit_for_applications/index)
- [Red Hat Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index)
- [MTA 8 Blog: Bringing modernized applications to market faster](https://www.redhat.com/en/blog/migration-toolkit-applications-8-bringing-modernized-applications-market-faster)
- [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)

## Next Steps

- Configure the MTA VS Code extension in Dev Spaces workspaces
- Import enterprise Java applications for migration assessment
- Build a Solution Server knowledge base from initial migrations
