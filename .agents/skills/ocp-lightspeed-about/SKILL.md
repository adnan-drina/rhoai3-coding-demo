---
name: ocp-lightspeed-about
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or explaining OpenShift Lightspeed concepts,
  architecture, AI assistant capabilities, and supported LLM providers from the
  official OpenShift Lightspeed 1.0 documentation. Do NOT use for installing
  (use ocp-lightspeed-install), configuring (use ocp-lightspeed-configure),
  operations (use ocp-lightspeed-operate), or troubleshooting
  (use ocp-lightspeed-troubleshoot).
---

# OCP Lightspeed About

Use this skill to ground OpenShift Lightspeed conceptual guidance in the
official Red Hat OpenShift Lightspeed 1.0 about guide for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## What Is OpenShift Lightspeed

Red Hat OpenShift Lightspeed is a generative AI service that provides
context-aware recommendations for OpenShift Container Platform. It runs as a
virtual assistant inside the OpenShift web console, accepting plain English
queries from developers and administrators.

The service answers questions using official OCP documentation. For products not
fully covered by OCP docs (GitOps, Pipelines, Service Mesh 3.x, ACS, ACM,
Quay, and others), the configured LLM generates answers directly.

## Supported Interfaces

- **REST API** (`/v1/`): stable, supported interface for programmatic use.
- **Gradio UI** (`/ui`) and internal endpoints: development and debugging only;
  unstable and unsupported for programmatic use.

## Supported LLM Providers

The service does not include an LLM. You must configure one before installing
the operator.

**SaaS providers:**
- OpenAI
- Microsoft Azure OpenAI
- IBM watsonx

**Self-hosted providers:**
- Red Hat OpenShift AI (single-model serving platform, vLLM runtime, vLLM 0.8.4+)
- Red Hat Enterprise Linux AI (OpenAI API-compatible, vLLM 0.8.4+)

Both self-hosted options are OpenAI API-compatible. When running in a different
cluster than the Lightspeed deployment, expose via route or secure endpoint.

## Resource Requirements

| Component | Min CPU | Min Memory | Max Memory |
|-----------|---------|------------|------------|
| Application server | 0.5 cores | 1 GB | 4 Gi |
| PostgreSQL database | 0.3 cores | 300 Mi | 2 Gi |
| OCP web console | 0.1 cores | 50 Mi | 100 Mi |
| Lightspeed operator | 0.1 cores | 64 Mi | 256 Mi |

## Platform Requirements

- Architecture: x86_64
- FIPS mode supported
- Disconnected clusters supported (mirror images with `oc mirror`)

## Data Handling and Telemetry

Lightspeed adds cluster and environment details to user messages before sending
to the LLM. A redaction layer filters data before sharing or logging.

- Transcripts sent to Red Hat every two hours by default (via Red Hat Insights)
- Opt-in feedback collection (score, text, query, LLM response)
- Disable via `OLSConfig` CR (`feedbackDisabled`, `transcriptsDisabled`)
- Full opt-out requires disabling cluster remote health monitoring

## OLSConfig CR

The only CR documented in the About guide:

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
```

Key data-collection fields under `spec.ols.userDataCollection`:
- `feedbackDisabled`: stops feedback collection
- `transcriptsDisabled`: stops transcript collection

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the relevant concept (LLM providers, data handling, requirements).
4. For GitOps manifests involving OLSConfig, verify fields against the
   extraction before committing.
5. For live operations, use the repo environment guard.
6. Validate with `references/source-capture.md` boundaries.

## Related Skills

- Use `ocp-lightspeed-install` for installing the operator and deploying the service.
- Use `ocp-lightspeed-configure` for OLSConfig CR configuration and LLM setup.
- Use `ocp-lightspeed-operate` for day-2 operations and administration.
- Use `ocp-lightspeed-troubleshoot` for diagnosing and resolving issues.
- Use `rhoai-model-serving-platform` for RHOAI single-model serving (self-hosted LLM).
- Use `rhoai-model-deployment` for deploying models on RHOAI (self-hosted LLM).

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
