# Official Doc Extraction

Use this extraction to keep MTA Developer Lightspeed content grounded in
official Red Hat sources. When implementation needs exact CR fields, verify
against the installed Operator CRDs with `oc explain` or `oc get crd` before
authoring GitOps manifests.

## Support Posture

Developer Lightspeed for MTA and the Solution Server are Technology Preview
features. Not supported with Red Hat production SLAs. Do not use in production.
Requires a Red Hat Advanced Developer Suite (RHADS) subscription for support.

## Prerequisites

- MTA Operator 8.0.0 or later installed.
- LLM API key for a supported provider.
- Language Support for Java by Red Hat VS Code extension.
- Java 17 or later.
- Maven 3.9.9 or later.
- Git added to `$PATH`.
- (Solution Server) 5 Gi RWO persistent volume.

## Supported LLM Providers and Models

| Provider (Tackle CR value) | Example models |
|-----------------------------|---------------|
| OpenShift AI platform | OpenAI-compatible API models deployed on-cluster |
| OpenAI (`openai`) | `gpt-4`, `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo` |
| Azure OpenAI (`azure_openai`) | `gpt-4`, `gpt-35-turbo` |
| Amazon Bedrock (`bedrock`) | `anthropic.claude-3-5-sonnet-20241022-v2:0`, `meta.llama3-1-70b-instruct-v1:0` |
| Google Gemini (`google`) | `gemini-2.0-flash-exp`, `gemini-1.5-pro` |
| Ollama (`ollama`) | `llama3.1`, `codellama`, `mistral` |

## Workflow Options

### Agent AI Without LLM Proxy

Administrator:
1. Create `kai-api-keys` Secret in `openshift-mta` namespace.
2. Configure `kai_llm_provider` and `kai_llm_model` in Tackle CR.

Migrator:
1. Enable GenAI in MTA extension settings.
2. Configure analysis profile (target technologies, custom rules).
3. Activate LLM provider in `provider-settings.yaml` (move `&active` anchor).
4. Enable Agent AI and run analysis.

### LLM Proxy With Optional Solution Server

Administrator:
1. Create `kai-api-keys` Secret in `openshift-mta` namespace.
2. In Tackle CR, set `kai_llm_proxy_enabled: true`.
3. Optionally set `kai_solution_server_enabled: true`.
4. Configure `kai_llm_provider` and `kai_llm_model`.

Migrator (Solution Server mode):
1. Connect to MTA Hub and run analysis using a profile downloaded from Hub.
2. Apply code resolutions suggested by the Solution Server.

Migrator (Agent AI mode via proxy):
1. Enable GenAI and Agent mode in extension settings.
2. Run analysis; agent iterates automatically.

## LLM API Key Secret Configuration

### OpenAI-compatible providers

```shell
oc create secret generic kai-api-keys -n openshift-mta \
  --from-literal=OPENAI_API_BASE='https://example.openai.com/v1' \
  --from-literal=OPENAI_API_KEY='<YOUR_OPENAI_KEY>'
```

Base URL can alternatively be set as `kai_llm_baseurl` in the Tackle CR.

### Azure OpenAI

```shell
oc create secret generic kai-api-keys -n openshift-mta \
  --from-literal=AZURE_OPENAI_API_KEY='<YOUR_AZURE_OPENAI_API_KEY>'
```

### Amazon Bedrock

```shell
oc create secret generic aws-credentials \
  --from-literal=AWS_ACCESS_KEY_ID=<YOUR_AWS_ACCESS_KEY_ID> \
  --from-literal=AWS_SECRET_ACCESS_KEY=<YOUR_AWS_SECRET_ACCESS_KEY>
```

### Google Gemini

```shell
oc create secret generic kai-api-keys -n openshift-mta \
  --from-literal=GEMINI_API_KEY='<YOUR_GOOGLE_API_KEY>'
```

### Force Reconcile (Optional)

```shell
kubectl patch tackle tackle -n openshift-mta --type=merge -p \
  '{"metadata":{"annotations":{"konveyor.io/force-reconcile":"'"$(date +%s)"'"}}}'
```

## Tackle CR With LLM Proxy and Solution Server

```yaml
kind: Tackle
apiVersion: tackle.konveyor.io/v1alpha1
metadata:
  name: mta
  namespace: openshift-mta
spec:
  kai_llm_proxy_enabled: true
  kai_solution_server_enabled: true
  kai_llm_provider: <provider-name>
  kai_llm_model: <model-name>
```

### Validation

```shell
oc get deploy,svc -n openshift-mta | grep -E 'kai-(api|db|importer)'
```

When Solution Server is enabled, the API endpoint is served through the MTA
Hub. No additional Route creation is required.

## provider-settings.yaml Configuration

Access via VS Code Command Palette: `MTA: Open the Gen AI model provider
configuration file`.

Select a provider by moving the `&active` anchor to the desired block.

### OpenShift AI Model

```yaml
models:
  openshift-example-model: &active
    environment:
      CA_BUNDLE: "<Server's CA Bundle path>"
    provider: "ChatOpenAI"
    args:
      model: "my-model"
      configuration:
        baseURL: "https://<serving-name>-<project>.apps.example.com/v1"
```

### OpenAI

```yaml
OpenAI: &active
    environment:
      OPENAI_API_KEY: "<your-API-key>"
    provider: ChatOpenAI
    args:
      model: gpt-4o
```

### Azure OpenAI

```yaml
AzureChatOpenAI: &active
    environment:
      AZURE_OPENAI_API_KEY: ""
    provider: AzureChatOpenAI
    args:
      azureOpenAIApiDeploymentName: ""
      azureOpenAIApiVersion: ""
```

### Amazon Bedrock

```yaml
AmazonBedrock: &active
    environment:
      AWS_ACCESS_KEY_ID: ""
      AWS_SECRET_ACCESS_KEY: ""
      AWS_DEFAULT_REGION: ""
    provider: ChatBedrock
    args:
      model: meta.llama3-70b-instruct-v1:0
```

### Google Gemini

```yaml
GoogleGenAI: &active
    environment:
      GOOGLE_API_KEY: ""
    provider: ChatGoogleGenerativeAI
    args:
      model: gemini-2.5-pro
```

### Ollama

```yaml
models:
  ChatOllama: &active
    provider: "ChatOllama"
    args:
      model: "granite-code:8b-instruct"
      baseUrl: "127.0.0.1:11434"
```

### Podman Desktop

```yaml
podman_mistral: &active
    provider: "ChatOpenAI"
    environment:
      OPENAI_API_KEY: "unused value"
    args:
      model: "ibm-granite/granite-3.3-8b-instruct-GGUF"
      configuration:
        baseURL: "http://localhost:56885/v1"
```

Podman Desktop models may be insufficient for production-quality code fixes.

## VS Code Extension Settings

| Setting | Description |
|---------|-------------|
| Gen AI: Enabled | Enable AI code fixes (default: true) |
| Gen AI: Agent mode | Enable agentic AI automated analysis loop |
| Gen AI: Excluded diagnostic sources | Exclude specific diagnostic sources from Agent AI |
| Auto Accept on Save | Auto-save accepted code changes (default: true) |
| Cache directory | Directory for cached LLM responses |
| Trace enabled | Enable tracing MTA–LLM communication |
| Trace directory | Directory for saved LLM interaction traces |
| Demo mode | Use cached LLM responses for analysis |

## Profile Configuration

Access via `MTA: Manage Analysis Profile` in Command Palette:

- **Profile Name**: reusable profile identifier
- **Target Technologies**: e.g. `quarkus`
- **Custom Rules**: optional rules beyond defaults
- **Configure generative AI**: opens `provider-settings.yaml`

## Code Resolution Workflow

1. Run analysis: `MTA: Open Analysis View` or click the book icon.
2. Review issues in Analysis Results (All / Files / Issues tabs).
3. Click solutions icon on an issue to request AI fix suggestion.
4. Review diff of updated code vs original.
5. Accept, reject, or edit suggested changes.
6. Click Continue for follow-up analysis (detects new diagnostic issues).
7. Repeat until all issues are resolved.

### Agent AI Mode

When `mta-vscode-extension.genai.agentMode` is `true`:

1. Planning agent creates context and selects sub-agent.
2. Sub-agent streams reasoning transcript and file changes.
3. User reviews preview and approves/rejects.
4. Agent re-analyses, fixes diagnostic issues, iterates.
5. Maximum two attempts per issue.

## Data Privacy

- Code snippets are transmitted intact to the LLM; no automatic redaction.
- For IP-sensitive code, deploy self-managed models on OpenShift AI or RHEL AI.
- Configure `provider-settings.yaml` to point at the private endpoint.

## Debugging

- Logs: `Developer: Open Extension Logs Folder` >
  `redhat.mta-vscode-extension/` (`extension.log`, `analyzer.log`).
- Output panel: select `Red Hat Developer Lightspeed for MTA`.
- Webview logs: `Open Webview Developer Tools` in Command Palette.
- Archive: `MTA: Generate Debug Archive` — creates zip with logs, redacted
  provider config, model arguments, and optional LLM traces.
- Log rotation: `extension.log` max 10 MB, 3 files retained.
  `analyzer.log` — no rotation.

## Boundaries

- This extraction covers AI-assisted analysis configuration and usage only.
- MTA Operator installation belongs in a separate skill.
- CLI-only analysis without AI features belongs in `mta-cli`.
- Web UI analysis belongs in `mta-ui`.
- Custom rule authoring belongs in a separate skill.
- Detailed OpenShift AI model serving setup is out of scope; see `rhoai-*`
  skills.
