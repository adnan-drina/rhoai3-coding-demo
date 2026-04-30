# Step 05: AI-Assisted EAP/Java EE Modernization to Quarkus
**Modernize a representative slice of the Coolstore Java EE application toward Quarkus** using MTA analysis, Developer Lightspeed, and a MaaS-governed Nemotron model. The demo shows the repeatable workflow: assess, analyze, generate AI-assisted fixes, review, apply, rebuild, and re-analyze.

## Overview

This step deploys the **Migration Toolkit for Applications (MTA) 8.1** with **Red Hat Developer Lightspeed** and demonstrates an end-to-end modernization workflow against the [konveyor-ecosystem/coolstore](https://github.com/konveyor-ecosystem/coolstore) — a Java EE 7 monolith originally running on JBoss EAP.

MTA combines static code analysis (2400+ Red Hat-maintained rules) with LLM-powered code generation. It identifies exactly what needs to change through analysis, then uses the MaaS endpoint to generate targeted migration-specific code fixes — not generic suggestions, but context-aware transformations informed by the rule engine.

> The same private Nemotron model that developers use in Dev Spaces (Step 04) is also used by MTA for automated code modernization — all governed through MaaS.

### Reference Application

| Branch | Purpose |
|--------|---------|
| [`main`](https://github.com/konveyor-ecosystem/coolstore/tree/main) | Legacy Java EE / JBoss EAP starting point (`javax.*`, JPA, CDI, JAX-RS) |
| [`quarkus`](https://github.com/konveyor-ecosystem/coolstore/tree/quarkus) | Completed Quarkus migration (reference target architecture) |

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

### Act 1: Platform Readiness

Verify the platform is ready before the demo:

```bash
./steps/step-05-mta/validate.sh
```

Show the audience:
- MTA 8.1 installed and healthy (`oc get tackle mta -n openshift-mta`)
- OpenShift OAuth login works — click **Log in with OpenShift** on the MTA login page
- ConsoleLink opens MTA from the OpenShift launcher menu
- Tackle CR configured with LLM proxy, Solution Server, and MaaS model
- `kai-api-keys` contains a real `sk-oai-*` MaaS key (validation confirms this)
- MaaS model refs are ready (4 models in the MaaS tab)

### Act 2: Architect View (MTA UI)

Log in as `ai-admin` / `<demo-password>` via **Log in with OpenShift**.

1. Go to **Migration > Applications**
2. Click **Create new** and register the Coolstore application:
   - Name: `coolstore`
   - Repository type: Git
   - URL: `https://github.com/konveyor-ecosystem/coolstore.git`
   - Branch: `main`
3. Create or select a **Quarkus** migration target profile
4. Select the coolstore application and click **Analyze**
5. Review the analysis report:
   - **Incidents** — migration issues found by the rule engine
   - **Effort/story points** — estimated migration cost
   - **Affected files** — which source files need changes
   - **Migration categories** — `javax.*` namespace, CDI, JAX-RS, JPA, configuration

Explain to the audience: static analysis gives the LLM precise context about what needs to change. This is why MTA + AI produces better results than generic "modernize this code" prompting.

### Act 3: Developer Workspace (Dev Spaces)

Log in as `ai-developer` / `<demo-password>`.

1. Open **Dev Spaces** from the OpenShift launcher
2. The ai-developer workspace has the Coolstore `main` branch pre-cloned
3. Confirm the **MTA extension** is installed (pre-installed via `DEFAULT_EXTENSIONS`)
4. Connect the MTA extension to the MTA Hub:
   - Hub URL: `https://<mta-route>` (get from `oc get route mta -n openshift-mta`)
   - Authentication: enabled (uses OpenShift/Keycloak login)
   - Solution Server: enabled
   - Profile sync: enabled
5. Select the Quarkus migration profile synced from the Hub

### Act 4: IDE Analysis

From the MTA VS Code extension:

1. Run analysis against the Coolstore source code
2. Issues appear in the **MTA Issues** pane within the IDE
3. Pick a narrow issue class for the live demo:
   - `javax.*` -> `jakarta.*` namespace migration
   - CDI / JAX-RS modernization patterns
   - Persistence or configuration changes
4. Do not attempt to migrate the entire application live — focus on a representative slice

### Act 5: AI-Assisted Fix Through MaaS

Request a Developer Lightspeed / Solution Server fix for a selected issue.

Narrate the key architectural point:

> The developer does not enter a MaaS API key. The MTA extension authenticates to MTA via Keycloak. The LLM proxy uses the administrator-managed `kai-api-keys` Secret to authenticate with the MaaS Gateway. The MaaS Gateway enforces model access and rate limits. Nemotron generates the suggested patch.

Then:
1. Click the **solutions icon** on an issue to request an AI fix
2. Review the generated diff
3. Apply the selected fix
4. Run `mvn test` or `mvn package` to verify the build
5. Re-run MTA analysis from the extension
6. Show reduced incidents or changed issue profile

### Act 6: Reference Completion

Switch to or compare with the [`quarkus` branch](https://github.com/konveyor-ecosystem/coolstore/tree/quarkus):

```bash
cd /projects/coolstore
git fetch origin quarkus
git diff main..origin/quarkus -- src/
```

Position this for the audience:

> "This branch represents the completed target architecture. In a real migration wave, teams repeat the analyze-fix-build-reanalyze loop until the application reaches this state. The Solution Server learns from each accepted fix, so similar issues across the portfolio get progressively better suggestions."

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
3. Both demo users are pre-created in Keycloak with their roles and linked to the OpenShift IdP using their OpenShift user UIDs
4. On login, the user clicks **Log in with OpenShift**, authenticates with HTPasswd, and Keycloak matches the existing linked account — no profile prompts

> Other OpenShift users can also authenticate via the OpenShift login, but they will not have MTA roles pre-assigned. An MTA admin can assign roles to additional users from the RHBK admin console.

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

- [Coolstore Sample Application](https://github.com/konveyor-ecosystem/coolstore) — Java EE monolith (`main`) with completed Quarkus migration (`quarkus` branch)
- [MTA 8.1 Installation Guide](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/installing_the_migration_toolkit_for_applications/index)
- [Developer Lightspeed for MTA 8.1](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index)
- [MTA VS Code Extension 8.1](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index)
- [MTA UI Guide 8.1](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index)
- [MTA Rules Guide 8.1](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_rules_for_an_mta_analysis/index)
- [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)

## Next Steps

- Automate Coolstore registration and Quarkus profile creation via the MTA Hub API (Phase 2)
- Add custom rulesets for organization-specific migration patterns
- Build a Solution Server knowledge base from initial migrations
- Import enterprise Java applications for portfolio-scale assessment
