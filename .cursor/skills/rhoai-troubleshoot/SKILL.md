---
name: rhoai-troubleshoot
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  rhoai-version: "3.3-plus-maas-ea"
  ocp-version: "4.20"
description: >
  Diagnose and fix issues with the RHOAI demo deployment. Use when ANY
  deployment step fails, validate.sh reports errors, pods are in
  CrashLoopBackOff/Pending/Error/ImagePullBackOff, ArgoCD shows OutOfSync or
  Degraded, operators are not installing, GPU nodes are not joining,
  InferenceServices are not Ready, or the user reports any problem with their
  OpenShift AI environment. Also use when the user asks "why isn't X working?"
  for any demo component.
  Do NOT use for manifest review (use manifest-reviewer agent) or
  resource scaling (use manage-resources skill).
---

# RHOAI Troubleshooting

Structured diagnostic workflow for resolving issues with the RHOAI demo on OpenShift 4.20. The implemented manifests target OpenShift AI 3.3 with selected early-access MaaS resources where explicitly documented.

## When to Use

- A `validate.sh` script reports failures
- A `deploy.sh` script errors out or hangs
- Pods are stuck in CrashLoopBackOff, Pending, or Error
- ArgoCD shows OutOfSync, ComparisonError, or Degraded
- Operators are not installing or CSV not Succeeded

## Instructions

**Never guess.** Every diagnosis must be backed by official documentation or observable cluster state.

### Step 1: Run the Validation Script

```bash
./steps/step-XX-<name>/validate.sh
```
Check exit code: 0 = pass, 1 = failures, 2 = warnings only.

### Step 2: Consult Official Product Documentation

Use `@RHOAI 3.3` and `@OCP 4.20` docs in Cursor unless the manifest explicitly documents an early-access MaaS behavior. Focus on the relevant section:

| Steps | Doc Section |
|-------|-------------|
| 01 | Installing and Uninstalling |
| GPU/NFD | Managing Resources |
| Model Serving | Deploying Models |
| Pipelines | Working with AI Pipelines |
| Model Registry | Enabling Model Registry |
| Evaluation | Evaluating AI Systems |

### Step 3: Gather Cluster State

Run diagnostic commands from `references/diagnostic-commands.md` for the failing component.

### Step 4: Match to Known Pattern

Check `references/diagnostic-patterns.md` for the symptom. Common patterns cover ArgoCD, operators, pods, and RHOAI-specific issues.

### Step 5: Apply Fix and Verify

Execute the smallest change that fixes the issue. Re-run `validate.sh` to confirm.

### Step 6: Update Knowledge Base

If this was a new issue, update `docs/TROUBLESHOOTING.md` with the symptom, cause, diagnostic commands, and recovery command. Keep step READMEs educational.

## Escalation Protocol

If unresolved after one diagnostic cycle:
1. Document what was tried and observed
2. Include exact error messages and `oc` output
3. Suggest manual checks
4. Report to the user with full context
