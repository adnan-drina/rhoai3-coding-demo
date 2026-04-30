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
├── OAuthClient/mta-keycloak        → OpenShift OAuth federation
├── PostSync Job (MaaS)             → Patches cluster-specific MaaS URL
└── PostSync Job (Auth)             → Configures OpenShift IdP in RHBK
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

The LLM proxy is central to how Developer Lightspeed integrates with MaaS. Developers never handle API keys — authentication is managed centrally by the platform.

```text
Developer (MTA UI or VS Code Extension)
        |
        v
MTA Hub (orchestrates analysis + AI requests)
        |
        v
LLM Proxy (llm-proxy pod, LlamaStack-based)
  - Authenticates with MaaS Gateway using kai-api-keys Secret
  - Administrators rotate the sk-oai-* key without touching developer configs
        |
        v
MaaS Gateway (rate-limited, governed)
        |
        v
Nemotron model generates migration-specific code fix
        |
        v
Developer reviews diff, accepts/rejects changes
```

### Two AI Modes

| Mode | How It Works | Best For |
|------|-------------|----------|
| **Solution Server** | RAG-based: learns from past migrations, improves over time. Accessed through the MTA UI or VS Code extension — all LLM calls go through the proxy. | Large migration waves with similar apps |
| **Agent AI** | Agentic loop: plans, fixes, compiles, re-analyzes automatically. Also uses the proxy for all LLM calls. | Individual app modernization |

## The Demo

### Act 1: Access MTA UI

1. Get the MTA route: `oc get route -n openshift-mta`
2. Click **Log in with OpenShift** and authenticate as `ai-admin` / `redhat123`
3. The MTA dashboard shows the migration workspace

### Act 2: Import a Sample Application

1. In MTA UI, go to **Migration > Applications**
2. Click **Create new** and import a legacy Spring Boot application
3. Provide the Git repository URL of the sample app

### Act 3: Run Analysis (MTA UI)

1. Select the application and click **Analyze**
2. Choose target: **Quarkus** (or **cloud-readiness**)
3. MTA applies default rules and identifies migration issues
4. Review the analysis report — issues, effort estimates, affected files

### Act 4: AI-Assisted Code Fixes (VS Code Extension + Solution Server)

The developer works in **Dev Spaces** (or local VS Code) with the MTA extension. The extension connects to MTA Hub, which routes all LLM calls through the proxy — no API key needed by the developer.

1. Open the application in **Dev Spaces** (or local VS Code)
2. Install the **MTA Extension** from the VS Code marketplace
3. Configure an MTA server connection (the extension connects to the MTA Hub)
4. Create an analysis profile: target **Quarkus**, enable default rules
5. Run analysis in VS Code — issues appear in the **MTA Issues** pane
6. Click the **solutions icon** on an issue to request an AI fix
7. The Solution Server queries the LLM proxy, which authenticates with MaaS and forwards the request to Nemotron
8. Review the generated code changes in the diff view
9. Accept or reject the change — accepted fixes are stored in the Solution Server database, improving future suggestions

### Act 5: Agent AI (Automated Fix Loop)

**Agent AI** mode automates the fix-compile-reanalyze cycle. It uses the same LLM proxy path.

1. In the MTA extension, select multiple issues and choose **Agent AI**
2. The agent plans fixes, applies them, recompiles, and re-analyzes
3. If new issues arise from the fix, the agent iterates automatically
4. Review the final set of changes as a single diff

### Act 6: Verify Migration Progress

1. Re-run analysis — fewer issues reported
2. Each accepted fix improves the Solution Server's knowledge
3. Future analyses of similar apps get better suggestions

<details>
<summary>Alternative: Direct LLM provider (bypassing the proxy)</summary>

If you need to bypass the LLM proxy and connect the VS Code extension directly to a model provider, configure `provider-settings.yaml` in the extension settings:

```yaml
models:
  maas-nemotron: &active
    provider: "ChatOpenAI"
    environment:
      OPENAI_API_KEY: "<your sk-oai-* key from MaaS>"
    args:
      model: "nemotron-3-nano-30b-a3b"
      configuration:
        baseURL: "https://maas.<cluster>/maas/nemotron-3-nano-30b-a3b/v1"
```

This approach requires each developer to manage their own MaaS API key. The proxy-based flow (Acts 4-5) is recommended for production use because it centralizes key management and enables administrator-controlled key rotation.

</details>

## Federated Login with OpenShift

MTA is configured to use **OpenShift OAuth** as an identity provider via the Keycloak `openshift-v4` provider. Users log into MTA with their existing cluster credentials — no separate MTA accounts needed.

| OpenShift User | MTA Role | Access |
|---|---|---|
| `ai-admin` | `tackle-admin` | Full admin: manage applications, credentials, rules, users |
| `ai-developer` | `tackle-migrator` | Run analysis, request AI fixes, view reports |

**How it works:**
1. A PostSync Job creates an `openshift-v4` identity provider in the MTA Keycloak realm
2. An `OAuthClient/mta-keycloak` is registered with the OpenShift OAuth server
3. All OpenShift-authenticated users get the `tackle-migrator` role by default
4. `ai-admin` is pre-created in Keycloak with the `tackle-admin` role and linked to the OpenShift IdP
5. On first login, the user clicks **Log in with OpenShift**, authenticates with HTPasswd, and is redirected back to MTA with the correct role

> The default MTA admin account (`admin` / auto-generated password) remains available in the RHBK realm for emergency access.

## Key Takeaways

**For business stakeholders:**
- Accelerate large-scale application modernization with AI-assisted code changes
- The same governed AI models serve both developers (coding) and platform teams (migration)
- Migration knowledge accumulates across the organization via the Solution Server

**For technical teams:**
- MTA's static analysis provides precise context — the LLM knows exactly what to fix
- Model-agnostic: switch between Nemotron (private) and GPT-4o (external) via MaaS
- No model fine-tuning needed — RAG-based context from the Solution Server handles it
- The LLM proxy centralizes API key management — administrators rotate the `kai-api-keys` Secret without touching developer configs or redeploying the extension

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
