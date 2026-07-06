---
name: rhdh-openshift-ai-connector
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when installing, configuring, or troubleshooting OpenShift AI Connector
  for Red Hat Developer Hub to accelerate AI development. Covers AI asset
  mapping (InferenceService to Component, Model Registry to Resource, API specs,
  TechDocs model cards), RBAC setup, sidecar containers, dynamic plugin
  installation, metadata enrichment, and diagnostic procedures. Do NOT use for
  model serving itself (use rhoai-model-serving-platform). Do NOT use for RHDH
  installation or Git integration.
---

# RHDH OpenShift AI Connector

Install and configure the OpenShift AI Connector for Red Hat Developer Hub
1.10 to automatically discover and surface AI models, model servers, and APIs
from Red Hat OpenShift AI in the RHDH Software Catalog.

## When to Use

- Installing the OpenShift AI Connector dynamic plugins
- Configuring ServiceAccount and RBAC for RHOAI access
- Setting up sidecar containers (rhoai-normalizer, storage-rest, location)
- Mapping RHOAI artifacts to Backstage entity kinds
- Enriching AI model metadata (API spec, owner, lifecycle, TechDocs)
- Troubleshooting connector data sync issues
- Configuring entity provider in `catalog.providers.modelCatalog`

## Key Concepts

### Support Status

- **Developer Preview** — not production-ready, not supported by Red Hat SLA
- Requires RHOAI 2.25 for model card TechDocs propagation
- RHOAI 2.20+ for other features

### RHOAI-to-Backstage Entity Mapping

| RHOAI Artifact | Backstage Kind | Type | Purpose |
|----------------|---------------|------|---------|
| InferenceService | Component | `model-server` | Running AI model endpoint |
| Model Registry Version | Resource | `ai-model` | AI model artifact |
| Model Server API | API | `openapi` | REST endpoint specification |
| Model Cards | TechDocs | N/A | Model documentation |

### Architecture

Three sidecar containers alongside `backstage-backend`:
- **rhoai-normalizer**: Kubernetes controller normalizing RHOAI metadata
- **storage-rest**: ConfigMap-based storage bridge
- **location**: Location service providing data to RHDH Entity Provider

## Prerequisites

- RHDH 1.10 deployed (Helm)
- RHOAI 2.25 (recommended) or 2.20+ on same cluster
- Model Registry enabled in RHOAI
- Cluster administrator privileges

## Validation

```bash
# Verify dynamic plugins installed
oc logs -c install-dynamic-plugins deployment/<rhdh> | grep "model-catalog"

# Check sidecar containers running
oc get pod -l app=backstage -o jsonpath='{.items[*].spec.containers[*].name}'

# Verify location service
oc rsh -c backstage-backend deployment/<rhdh> curl http://localhost:9090/list

# Check ConfigMap with cached data
oc get configmap bac-import-model -o json | jq '.binaryData | keys'

# Check backstage-backend logs for entity provider
oc logs deployment/<rhdh> -c backstage-backend | grep "ModelCatalog"
```

## Boundaries

- Developer Preview — not for production workloads
- Model cards from RHOAI < 2.25 registrations do not transfer as TechDocs
- Helm-based deployment only (sidecar container approach)
- `baseUrl: http://localhost:9090` is the only supported value for
  Developer Preview
- API spec must be manually populated via Model Registry Properties

## References

- `references/source-capture.md` — source ledger
- `references/official-doc-extraction.md` — extracted procedures and config
