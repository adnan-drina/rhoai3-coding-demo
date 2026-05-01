---
name: review-gitops-change
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
description: >
  Review GitOps and platform manifest changes for safety, consistency, and
  completeness. Use when a contributor changes anything under gitops/, platform
  YAML, or Argo CD applications. Complements the manifest-reviewer subagent
  with a workflow-level review that includes security impact, MaaS implications,
  and PR-ready output. Do NOT use for educational README writing (use README
  rules), live troubleshooting (use rhoai-troubleshoot), or deep manifest
  schema validation (use manifest-reviewer agent).
---

# Review GitOps Change

Use this skill when reviewing changes to files under `gitops/`, Argo CD
applications, or any Kubernetes/OpenShift YAML in the repository.

## When to invoke

- A PR or change touches `gitops/**/*.yaml`
- Argo CD application definitions change
- Kustomize structure changes (new resources, patches, overlays)
- RBAC, NetworkPolicy, AuthPolicy, or gateway resources change
- Model-serving or MaaS resources change

## Inputs needed

- List of changed files (from `git diff --name-only`)
- Whether a live cluster is available for validation

## Review checklist

### 1. Argo CD application structure

- Application uses `project: rhoai-demo`
- Required labels present: `app.kubernetes.io/part-of`, `demo.rhoai.io/step`
- `manifest-generate-paths` annotation matches the source directory
- Sync waves are ordered correctly relative to other steps
- No destructive `resources-finalizer.argocd.argoproj.io` finalizer

### 2. Kustomize structure

- `kustomization.yaml` lists all resource files in the directory
- No orphaned YAML files (listed in directory but not in kustomization)
- `kustomize build <path>` renders without errors
- Components vs resources used appropriately

### 3. Security-sensitive changes

Flag and describe any changes to:

- RBAC (Role, ClusterRole, RoleBinding, ClusterRoleBinding)
- NetworkPolicy
- AuthPolicy or RateLimitPolicy
- TokenRateLimitPolicy
- Gateway, HTTPRoute, or EnvoyFilter
- Secrets or credential references
- ExternalModel resources
- ServiceAccount permissions
- MCP server configurations

### 4. MaaS and model access impact

- Does the change bypass MaaS? (should not unless explicitly documented)
- Does it change model routing or gateway behavior?
- Does it affect trust boundaries (private vs external model paths)?
- Are ExternalModel credentials handled safely?

### 5. Namespace and naming

- Namespaces are explicit (not relying on defaults)
- Resource names preserved (renaming breaks Argo CD tracking)
- Labels consistent with `50-kubernetes-labels.mdc` conventions

### 6. Workaround awareness

- Check `BACKLOG.md` for relevant workarounds
- If removing workaround code, confirm the platform gap is resolved
- If adding a workaround, document it in `BACKLOG.md`

### 7. Documentation impact

- Does this change require updates to `docs/OPERATIONS.md`?
- Does this change require updates to `docs/TROUBLESHOOTING.md`?
- Does it change the stage README architecture story?

## Validation commands

```bash
kustomize build gitops/stages/NNN-name/base/
kustomize build gitops/stages/NNN-name/base/ | oc apply --dry-run=server -f -
bash -n stages/NNN-name/deploy.sh
bash -n stages/NNN-name/validate.sh
```

## Output format

Produce this structured output:

```markdown
## GitOps review

### Changed resources
- [list of resources changed with kind/name/namespace]

### Security-sensitive changes
- [list, or "None"]

### MaaS or model-access impact
- [describe impact, or "No MaaS impact"]

### Workaround status
- [any BACKLOG.md items affected, or "No workarounds affected"]

### Documentation updates needed
- [list of docs that need updating, or "None"]

### Validation required
- [commands to run, or "Static review only — no live cluster available"]

### Risk
- [Low/Medium/High with explanation]

### Rollback
- [how to revert this change safely]
```

## What this skill must never do

- Approve changes to security-sensitive resources without flagging them
- Ignore MaaS bypass without explicit justification
- Claim validation passed without evidence
- Remove workaround documentation without confirming resolution
