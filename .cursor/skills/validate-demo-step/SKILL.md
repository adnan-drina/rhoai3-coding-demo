---
name: validate-demo-step
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
description: >
  Validate a demo step after changes. Use when a step's deploy script,
  validate script, GitOps manifests, or Argo CD application changes. Produces
  static validation commands, step-specific checks, and a clear statement of
  what was or was not validated against a live cluster. Do NOT use for
  troubleshooting failures (use rhoai-troubleshoot) or reviewing manifest
  quality (use manifest-reviewer agent or review-gitops-change skill).
---

# Validate Demo Step

Use this skill after changing a demo step to verify the change is correct
and complete.

## When to invoke

- A step's `deploy.sh` or `validate.sh` changes
- GitOps manifests under `gitops/step-XX-name/` change
- The step's Argo CD application definition changes
- A step README claims new behavior that needs verification

## Inputs needed

- Step number (01-06)
- List of changed files
- Whether a live OpenShift cluster is available

## Validation workflow

### Phase 1: Static validation (always possible)

```bash
# Script syntax check
bash -n steps/step-XX-name/deploy.sh
bash -n steps/step-XX-name/validate.sh

# Kustomize render check
kustomize build gitops/step-XX-name/base/

# Dry-run against cluster (requires oc login)
kustomize build gitops/step-XX-name/base/ | oc apply --dry-run=server -f -
```

### Phase 2: Step-specific validation (requires live cluster)

| Step | Validation script | Key checks |
|------|-------------------|------------|
| 01 | `./steps/step-01-rhoai-platform/validate.sh` | RHOAI operator, DSC, DSCI, dashboard |
| 02 | `./steps/step-02-gpu-infra/validate.sh` | GPU nodes, NFD, NVIDIA operator |
| 03 | `./steps/step-03-llm-serving-maas/validate.sh` | InferenceServices, MaaS API, models, gateway |
| 04 | `./steps/step-04-devspaces/validate.sh` | Dev Spaces operator, workspaces, coding tools |
| 05 | `./steps/step-05-mta/validate.sh` | MTA operator, Tackle, Developer Lightspeed |
| 06 | `./steps/step-06-developer-hub/validate.sh` | RHDH operator, Backstage CR, catalog |

### Phase 3: Cross-step verification

- Does this change affect downstream steps?
- Are Argo CD sync waves still ordered correctly?
- Does the step table in `README.md` still match?

## Completeness checklist

After validation, verify:

- [ ] `deploy.sh` applies the Argo CD Application as its first cluster-modifying action
- [ ] `validate.sh` uses `validate-lib.sh` with `check` and `validation_summary`
- [ ] Argo CD Application has `project: rhoai-demo`
- [ ] Argo CD Application has required labels and annotations
- [ ] `kustomization.yaml` lists all resource files
- [ ] No orphaned manifests in the directory
- [ ] README explains the step's value (not just commands)
- [ ] `docs/OPERATIONS.md` reflects any new operational behavior
- [ ] `docs/TROUBLESHOOTING.md` covers new failure modes if applicable

## Output format

```markdown
## Step validation: step-XX-name

### Static validation
- bash -n: [PASS/FAIL]
- kustomize build: [PASS/FAIL]
- dry-run: [PASS/FAIL/SKIPPED — no cluster]

### Step validation script
- [PASS/FAIL/SKIPPED — no cluster]

### Completeness
- [checklist results]

### Live cluster status
- [Validated against live cluster / Not validated — static review only]

### Issues found
- [list, or "None"]
```

## Honesty requirement

If a live OpenShift cluster is required and not available, say:

> Not validated against a live OpenShift cluster. Static review only.

Do not claim validation passed based on static checks alone when the change
involves runtime behavior (model serving, operator reconciliation, gateway
routing, workspace creation).
