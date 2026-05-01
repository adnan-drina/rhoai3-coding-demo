---
name: prepare-pr-summary
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
description: >
  Prepare a pull request summary following the project template. Use before
  opening a PR to generate the summary, risk assessment, rollback plan, and AI
  disclosure. Reads the git diff and produces structured output matching
  .github/pull_request_template.md. Do NOT use for making code changes (use
  other skills/rules), reviewing manifests (use review-gitops-change), or
  validating steps (use validate-demo-step).
---

# Prepare PR Summary

Use this skill to generate a complete PR summary before opening a pull request.

## When to invoke

- Before running `gh pr create`
- When the user asks to "prepare a PR" or "write a PR summary"
- After completing a set of changes that will be submitted as a PR

## Inputs needed

- The current branch diff (`git diff main...HEAD` or similar)
- List of commits on the branch
- Whether validation was run against a live cluster
- Which AI tools were used during the work

## Workflow

1. Run `git diff main...HEAD --stat` to understand scope.
2. Run `git log main..HEAD --oneline` to see commit history.
3. Read the changed files to understand the purpose.
4. Identify security-sensitive changes (RBAC, gateway, auth, secrets, MaaS).
5. Check if docs were updated alongside behavior changes.
6. Determine risk level.
7. Write rollback instructions.
8. Produce the PR summary.

## Output format

Use the structure from `.github/pull_request_template.md`:

```markdown
## Summary

[1-3 sentences describing what changed]

## Why

[Why this change is needed — the problem or improvement]

## Changed files

- [file path]: [what changed]
- [file path]: [what changed]

## Validation

Commands run:

\`\`\`bash
[actual commands run]
\`\`\`

Result:

\`\`\`text
[actual output or summary]
\`\`\`

[If not validated: "Not validated against a live OpenShift cluster. Static review only."]

## Risk

- [x] Low / Medium / High

Risk notes: [explain what could go wrong]

## Rollback

[How to revert: git revert, Argo CD sync, manual steps]

## Security and governance checklist

- [x] No secrets or credentials committed
- [x] No unintended RBAC expansion
- [x] No unintended model access change
- [x] No direct bypass of MaaS unless explicitly documented
- [x] Trust boundary language remains accurate
- [x] Docs updated where needed

## AI assistance

- [x] AI assistance used

- Tool/model: [e.g., Cursor with Claude]
- Scope of assistance: [e.g., planning, code edits, documentation]
- Human review performed: [e.g., full diff reviewed by <name>]
- Validation performed: [e.g., bash -n, kustomize build, validate.sh]
```

## Risk assessment guidelines

| Risk level | When to use |
|------------|-------------|
| Low | Docs-only, typo fixes, comment changes, non-functional additions |
| Medium | New manifests, script changes, configuration changes with validation |
| High | RBAC changes, gateway/auth policy changes, model access changes, workaround removal, operator version changes |

## What this skill must never do

- Claim validation that was not performed
- Omit AI assistance disclosure
- Mark security checklist items as checked without verification
- Produce a summary that doesn't match the actual diff
