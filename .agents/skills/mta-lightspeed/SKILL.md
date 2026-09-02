---
name: mta-lightspeed
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "mta"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Application Modernization"
description: >
  Use when configuring or using Red Hat Developer Lightspeed for MTA to
  modernize applications with AI assistance, including LLM provider
  configuration, code migration suggestions, and AI-assisted analysis. Do NOT
  use for installing MTA (use mta-install) or non-AI tool usage (use
  mta-cli/mta-ui).
---

# MTA Developer Lightspeed

Use this skill for configuring and using Red Hat Developer Lightspeed for
Migration Toolkit for Applications (MTA) 8.2 — the AI-assisted code migration
component that integrates LLMs with MTA static analysis.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat docs are product authority. This skill covers LLM provider
configuration, Solution Server setup, Agent AI mode, VS Code extension settings,
and AI-assisted code resolution workflows.

## Support Posture

> **Important:** Developer Lightspeed for MTA and the Solution Server are
> Technology Preview features. They are not supported with Red Hat production
> SLAs and might not be functionally complete. Do not use them in production.

## Concepts

### Developer Lightspeed for MTA

Starting from MTA 8.0.0, the VS Code extension integrates with LLMs through the
Developer Lightspeed component. It applies LLM-driven code changes to resolve
issues found through static code analysis of Java applications, using Retrieval
Augmented Generation (RAG) for context-based resolutions.

### Solution Server

An optional component that builds collective memory of source code changes
across analyses. It stores solved examples, computes success metrics (confidence
levels), and improves migration hints over successive migration waves. Requires
the LLM proxy service and a 5 Gi RWO persistent volume.

### Agent AI

An automated analysis mode that plans context, selects sub-agents, and iterates
through code fixes. Accepts changes, recompiles, and re-analyzes in a loop
until all issues are resolved or a maximum of two attempts per issue is reached.

## Supported LLM Providers

| Provider (Tackle CR value) | Example models |
|-----------------------------|---------------|
| OpenShift AI platform | OpenAI-compatible models deployed on-cluster |
| OpenAI (`openai`) | `gpt-4`, `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo` |
| Azure OpenAI (`azure_openai`) | `gpt-4`, `gpt-35-turbo` |
| Amazon Bedrock (`bedrock`) | `anthropic.claude-3-5-sonnet-*`, `meta.llama3-1-70b-instruct-*` |
| Google Gemini (`google`) | `gemini-2.0-flash-exp`, `gemini-1.5-pro` |
| Ollama (`ollama`) | `llama3.1`, `codellama`, `mistral` |

## Workflow

1. Read `references/source-capture.md` and confirm the product baseline.
2. Read `references/official-doc-extraction.md` for detailed procedures.
3. Select a deployment workflow:
   - **Agent AI without LLM proxy** — direct LLM connection via
     `provider-settings.yaml`.
   - **LLM proxy with optional Solution Server** — centralised key management
     via Tackle CR proxy service.
4. Configure LLM API key Secret in `openshift-mta` namespace.
5. Configure Tackle CR with provider and model settings.
6. Configure the VS Code extension (`provider-settings.yaml`, GenAI settings).
7. Run analysis and request AI-assisted code resolutions.

### LLM API Key Secret

```shell
oc create secret generic kai-api-keys -n openshift-mta \
  --from-literal=OPENAI_API_KEY='<YOUR_KEY>'
```

Provider-specific variants exist for Azure, Bedrock, Google, and
OpenShift AI. See `references/official-doc-extraction.md`.

### Tackle CR Configuration

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

## Data Privacy

Code snippets are transmitted intact to the configured LLM. No automatic
sanitisation or redaction is performed. Organisations with strict IP protection
should deploy self-managed models on OpenShift AI or RHEL AI and point
Developer Lightspeed at the private endpoint.

## VS Code Extension Settings

Key settings in `Extensions > MTA`:

| Setting | Purpose |
|---------|---------|
| Gen AI: Enabled | Enable AI-assisted code fixes (default: true) |
| Gen AI: Agent mode | Enable automated agentic analysis loop |
| Gen AI: Excluded diagnostic sources | Skip specific diagnostic sources in Agent AI |
| Cache directory | Store cached LLM responses |
| Trace enabled / Trace directory | Trace MTA–LLM communication for debugging |

## Debugging

- Extension logs: `Developer: Open Extension Logs Folder` >
  `redhat.mta-vscode-extension/extension.log`.
- Output panel: select `Red Hat Developer Lightspeed for MTA`.
- Archive logs: `MTA: Generate Debug Archive` in Command Palette.

## Related Skills

- `mta-cli` — CLI-based application analysis and migration.
- `mta-ui` — web UI analysis and assessment workflows.
- `mta-install` — MTA Operator installation and Tackle CR management.
- `mta-vscode` — VS Code extension non-AI features.
- `mta-intellij` — IntelliJ IDEA plugin workflows.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
