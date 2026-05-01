---
name: demo-operations-docs
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  rhoai-version: "3.4"
  ocp-version: "4.20"
description: >
  Maintain the operational documentation for the RHOAI coding demo. Use when
  creating or updating docs/OPERATIONS.md, docs/TROUBLESHOOTING.md, deployment
  instructions, validation guidance, ArgoCD operational notes, or known failure
  recovery procedures. Also use when deciding whether content belongs in a
  README, operations guide, troubleshooting guide, deploy script, or validate
  script. Do NOT use for rewriting educational README narrative (use the README
  rules), live cluster troubleshooting (use rhoai-troubleshoot), or resource
  scaling (use manage-resources).
---

# Demo Operations Docs

Use this skill to maintain the runbook layer of the repository.

## Content Placement

| Content | Belongs in |
|---------|------------|
| Architecture value, Red Hat product story, open source education | README files |
| Deployment order, validation strategy, GitOps operations | `docs/OPERATIONS.md` |
| Known symptoms, diagnosis, recovery | `docs/TROUBLESHOOTING.md` |
| Exact deploy behavior | `deploy.sh` scripts |
| Exact health checks | `validate.sh` scripts |

## Workflow

1. Read `.cursor/rules/22-operations-docs.mdc`.
2. Inspect the relevant `deploy.sh` and `validate.sh` scripts before documenting behavior.
3. Inspect `gitops/argocd/app-of-apps/` before documenting Argo CD app names or sync behavior.
4. Keep commands copy-pastable and scoped.
5. Prefer diagnostic commands before recovery commands.
6. Run `git diff --check` after edits.

## Writing Guidelines

- Be practical and concise.
- Use tables for stage mappings and exit codes.
- Use fenced `bash` blocks for commands.
- Do not duplicate long script bodies.
- Do not bury important warnings in prose.
- Keep destructive commands out unless there is a clear safety note and no safer option.

## Troubleshooting Entry Template

````markdown
## Symptom

**Affected stage:** Stage NNN

**Likely cause:** Explain the most common cause.

**Diagnose:**
```bash
oc get ...
```

**Recover:**
```bash
oc ...
```
````

## Verification Checklist

After editing operational docs:

- `docs/OPERATIONS.md` references every current step.
- `docs/TROUBLESHOOTING.md` entries are symptom-driven.
- Commands reference real namespaces and resource names.
- READMEs remain educational and are not overloaded with runbook content.
- `git diff --check` passes.
