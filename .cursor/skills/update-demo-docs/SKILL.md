---
name: update-demo-docs
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
description: >
  Check and update documentation consistency after a change. Use when scripts,
  manifests, or demo flow change and documentation might be stale. Inspects
  README.md, stage READMEs, OPERATIONS.md, TROUBLESHOOTING.md, and BACKLOG.md
  for consistency with the current implementation. Do NOT use for writing
  operational docs from scratch (use demo-operations-docs skill), rewriting
  educational narrative (use README rules), or troubleshooting (use
  rhoai-troubleshoot).
---

# Update Demo Docs

Use this skill after any behavior change to ensure documentation stays
consistent with the implementation.

## When to invoke

- After changing deploy scripts, validate scripts, or GitOps manifests
- After adding, removing, or modifying a demo stage
- After resolving or adding a workaround
- After changing model serving, MaaS, or gateway behavior
- After changing Dev Spaces, MTA, or Developer Hub configuration
- When a PR touches code but no docs

## Documents to check

| Document | Check for |
|----------|-----------|
| `README.md` | Stage table accuracy, product map, trust boundaries, deploy commands |
| `stages/NNN-*/README.md` | Demo storyline continuity, architecture claims, "What This Stage Adds", trust boundary language |
| `docs/assets/architecture/*.svg` and `scripts/generate-architecture-diagrams.mjs` | Root/stage diagram synchronization, canonical capability labels, product-layer colors |
| `docs/OPERATIONS.md` | Deployment order, validation strategy, Argo CD app names, commands |
| `docs/TROUBLESHOOTING.md` | Affected symptoms, recovery steps, diagnostic commands |
| `BACKLOG.md` | Workaround status, new limitations, resolved items |

## Consistency checks

### 1. Stage table matches reality

Verify the root README stage table matches:
- Actual directories under `stages/`
- Actual Argo CD applications under `gitops/argocd/app-of-apps/`
- Stage numbering and names

### 2. Deploy commands match scripts

Verify commands in README and OPERATIONS.md match what the scripts actually do.

### 3. Trust boundary language is accurate

After model-serving or gateway changes:
- Private model claims still hold
- External model descriptions are accurate
- MaaS role is correctly described

### 4. Product and version references

After operator or version changes:
- Product versions in README match manifests
- Official doc links are for the correct version
- No stale version references

### 5. Workaround documentation

After resolving or adding a workaround:
- `BACKLOG.md` reflects the current state
- `docs/TROUBLESHOOTING.md` has relevant entries
- Workaround code has comments explaining why

### 6. Cross-references

- Stage READMEs link to next/previous stages correctly
- Operations doc references real namespaces and resource names
- Troubleshooting entries reference real commands

### 7. Stage README narrative style

When checking a stage README:
- The opening should lead with this repository's demo storyline, not with a summary of an external article, blog, or product document.
- Red Hat blogs and documentation should appear as alignment, implementation baseline, or reference material after the stage's role in the workshop is clear.
- The stage should connect the previous stage, the capability being introduced, and the later stages that depend on it.
- The section order should follow rule `20-readme-standard.mdc`, including `Why This Is Worth Knowing` immediately after `How Red Hat And Open Source Make It Work`.
- The README should explain why the capability matters before listing YAML, resources, or commands.

### 8. Architecture diagram consistency

When checking architecture diagrams:
- Treat `scripts/generate-architecture-diagrams.mjs` as the source of truth for root and stage SVGs.
- Verify root and stage SVGs share the same product rail, logical layers, and capability labels.
- Verify stage SVGs only change capability visual state: new in stage, previously introduced with product-layer lightest fill tint, and not introduced yet.
- Preserve the agreed dark transparent Layout B visual design: purple Advanced Developer Suite, teal OpenShift AI, red OpenShift, dark neutral table, gray borders, and white text.
- Keep capability labels logical and product-aligned rather than manifest-internal.

## Workflow

1. Identify the behavior change (from git diff or task context).
2. Check each document in the table above for staleness.
3. For each stale section, determine the correct content from manifests/scripts.
4. Update the document following its rules:
   - READMEs: educational, blog-like (rule `20-readme-standard.mdc`)
   - OPERATIONS.md: operational, copy-pastable (rule `22-operations-docs.mdc`)
   - TROUBLESHOOTING.md: symptom-driven (rule `22-operations-docs.mdc`)
   - BACKLOG.md: status tracking with removal conditions
5. Run `git diff --check` after edits.

## Output format

```markdown
## Documentation consistency check

### Changed behavior
- [describe what changed]

### Documents updated
- [list of files updated with brief description]

### Documents verified (no update needed)
- [list of files checked and confirmed current]

### Documents that could not be verified
- [any docs requiring live cluster confirmation]
```

## What this skill must never do

- Turn READMEs into runbooks (operational content belongs in OPERATIONS.md)
- Claim capabilities that are not backed by manifests/scripts
- Remove workaround documentation without confirmed resolution
- Add operational detail to stage READMEs (use OPERATIONS.md)
