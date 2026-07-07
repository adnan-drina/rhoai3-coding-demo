---
name: review-manifest-compliance
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "GitOps & Manifests"
description: >
  Review GitOps manifests for cross-resource consistency, label compliance,
  security posture, and YAML standards. Use when reviewing manifest changes,
  adding new stages, or running a periodic compliance check. Complements
  review-gitops-change (workflow-level review) with systematic manifest-level
  checks. Do NOT use for doc-alignment validation (use review-doc-alignment)
  or live cluster troubleshooting (use inspect-cluster or rhoai-troubleshoot).
---

# Review Manifest Compliance

Systematically review GitOps manifests against project standards. Read the
rules, read the manifests, report findings. Do not modify any files.

## When to invoke

- A PR or change touches `gitops/**/*.yaml`
- A new stage is being added
- Periodic compliance audit

## Review checklist

### 1. Cross-resource consistency

Per `.agents/rules/gitops.md`:

- Service selectors match Pod template labels (exact character match)
- ConfigMap/Secret names in volumes/envFrom resolve to existing resources
- ServiceAccount names resolve to ServiceAccount resources
- Route/Ingress backends point to existing Services
- Port numbers are consistent (Service targetPort = container port)

### 2. Label compliance

Per `.agents/rules/gitops.md`:

- `app.kubernetes.io/part-of` is set (using functional names, not stage numbers)
- `app.kubernetes.io/name` is set
- `app.kubernetes.io/component` is set (using standard values)
- `app.openshift.io/runtime` is set on visible resources
- ArgoCD Applications have `demo.rhoai.io/stage` label

### 3. YAML standards

Per `.agents/rules/gitops.md`:

- 2-space indentation
- Key ordering: apiVersion > kind > metadata > spec
- Comments explain WHY, not WHAT
- No title comments restating the kind
- No decorative section headers

### 4. Security posture

Per `.agents/rules/project.md`:

- No `privileged: true`
- No `hostPath` volumes
- Demo secrets have DEMO VALUES ONLY header
- No real credentials in manifests

## How to review a stage

1. Read all YAML files in `gitops/stages/NNN-name/base/`
2. Read the `kustomization.yaml` to understand which resources are included
3. Apply the checklist above to each resource
4. Cross-reference between resources (selectors, names, ports)

## Output format

For each stage reviewed:

```
Stage: NNN-name
Files reviewed: N
Findings:
  - [LABEL] deployment.yaml: missing app.kubernetes.io/component
  - [SELECTOR] service.yaml: selector 'app: foo' doesn't match pod label 'app: bar'
  - [SECURITY] secret.yaml: missing DEMO VALUES ONLY header
  - [YAML] configmap.yaml: title comment restates kind

Summary: X findings (Y labels, Z selectors, W security, V yaml)
```

## Related skills

- `review-gitops-change` — workflow-level review including security, MaaS, and
  PR output
- `review-doc-alignment` — verify manifests match official Red Hat documentation
- `inspect-cluster` — gather live cluster state for validation
