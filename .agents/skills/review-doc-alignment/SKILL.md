---
name: review-doc-alignment
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "GitOps & Manifests"
description: >
  Verify that GitOps manifests align with official Red Hat documentation for
  the platform baseline. Use when creating or modifying CRs, operator
  configurations, InferenceServices, ServingRuntimes, or any RHOAI-managed
  resource. Also use for periodic alignment audits across stages. Do NOT use
  for label/YAML compliance (use review-manifest-compliance), live cluster
  troubleshooting (use inspect-cluster), or workflow-level reviews (use
  review-gitops-change).
---

# Review Documentation Alignment

Verify that manifests match the official Red Hat documentation — not just that
they are valid YAML.

## When to invoke

- Creating or modifying CRs, operator configurations, or RHOAI-managed
  resources
- Periodic alignment audit across stages
- After platform baseline version changes

## Preparation

1. Read `docs/PLATFORM_BASELINE.md` to confirm the active product versions.
2. Read `.agents/rules/rhoai.md` and `.agents/rules/ocp.md` for domain
   guardrails.
3. Consult the relevant `rhoai-*` or `ocp-*` skills for the resource type.

## What to check for each manifest

### 1. API version correctness

- Is the `apiVersion` the one documented for this resource in the active
  platform baseline version?

### 2. CR field validity

- Are all spec fields documented for this CR version?
- Are there fields that look invented or copied from a different version?
- Consult the matching `rhoai-*` or `ocp-*` skill for the resource kind and
  verify each top-level spec field.

### 3. Operator configuration

- Do Subscription channels match what the platform baseline version expects?
- Are operator names and catalog sources correct?

### 4. Annotation correctness

- Dashboard annotations (`opendatahub.io/template-name`, etc.) — do the values
  match actual platform templates?
- ArgoCD annotations — are sync-wave values reasonable for the stage order?

### 5. Image references

- Do container images reference Red Hat registry (`registry.redhat.io`) or
  approved sources?
- Are image tags pinned (not `:latest` for production-grade components)?

### 6. Referenced documentation

- Does the manifest's README reference the correct doc section for the active
  platform baseline?
- Are the doc links still valid (not pointing to older versions)?

## How to review a stage

1. Read all YAML files in `gitops/stages/NNN-name/base/`
2. For each CR, consult the matching `rhoai-*` or `ocp-*` skill and compare
   fields
3. For each operator Subscription, verify the channel and source against docs
4. Check the stage README References section for correct doc links
5. Report findings

## Key RHOAI resource types

| Resource | Skill to consult |
|----------|-----------------|
| DataScienceCluster | `rhoai-dsci-dsc-configuration` |
| DSCInitialization | `rhoai-dsci-dsc-configuration` |
| HardwareProfile | `rhoai-hardware-profiles` |
| InferenceService | `rhoai-model-deployment` |
| ServingRuntime | `rhoai-model-serving-platform` |
| ModelRegistry | `rhoai-model-registry` |
| DataSciencePipelinesApplication | `rhoai-ai-pipelines` |

## Output format

For each stage reviewed:

```
Stage: NNN-name
Files reviewed: N

Doc-Aligned:
  - subscription.yaml: channel matches platform baseline docs
  - datasciencecluster.yaml: spec fields match installation guide

Misaligned:
  - [API] guardrails.yaml: apiVersion should be X per docs, found Y
  - [FIELD] config.yaml: field 'foo' not documented
  - [DOC-REF] README.md: references a different version than platform baseline

Summary: X aligned, Y misaligned
```

## Related skills

- `review-manifest-compliance` — label, selector, YAML standards compliance
- `review-gitops-change` — workflow-level review with security and MaaS impact
- `inspect-cluster` — gather live cluster state
