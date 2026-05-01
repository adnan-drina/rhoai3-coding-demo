# Contributing to rhoai3-coding-demo

This repository is maintained by a small team using Cursor IDE with Claude and GPT models.

AI assistance is welcome, but human contributors remain responsible for all changes.

For the full AI collaboration model including rules/skills governance, local vs shared boundaries, and promotion workflows, see [docs/AI_COLLABORATION.md](docs/AI_COLLABORATION.md).

## Contribution model

Use this workflow:

1. Create or select an issue.
2. Define acceptance criteria.
3. Ask the AI agent for a short plan.
4. Review the plan.
5. Let the agent make a focused change.
6. Review the full diff manually.
7. Run relevant validation.
8. Open a pull request.
9. Have another human review the PR when practical.
10. Merge only after the risk and validation are clear.

## AI-assisted contributions

AI tools may be used for:

- reading and explaining code
- drafting scripts
- editing YAML
- writing documentation
- generating tests or validation steps
- troubleshooting
- preparing PR summaries

AI tools must not be treated as maintainers or accountable authors.

By opening a PR, the human contributor confirms that they have:

- reviewed the full diff
- checked for secrets and credentials
- checked for licensing or copied-code concerns
- validated the change or explained why validation was not possible
- disclosed material AI assistance
- accepted responsibility for the contribution

## Required AI disclosure

Every PR must include one of:

```text
AI assistance: none
```

or:

```text
AI assistance: Cursor with Claude/GPT
Scope: planning, code edits, documentation, troubleshooting, or validation
Human review: full diff reviewed by <name>
Validation: <commands run>
```

## Branch naming

Use short descriptive branches:

```text
docs/update-agent-rules
fix/step-03-validation
demo/devspaces-continue-config
gitops/maas-policy-update
```

## Commit style

Use conventional commits: `type(scope): description`

- **Types:** `feat`, `fix`, `docs`, `refactor`, `chore`, `ci`
- **Scope:** Use the step number when the change is step-specific (e.g., `feat(step-01): add hardware profiles`)
- **Scope:** Use the component name for cross-cutting changes (e.g., `fix(gitops): switch all apps to rhoai-demo project`)
- Keep the subject line under 72 characters

## Pull request expectations

Each PR should include:

- summary
- reason for change
- changed files
- validation evidence
- risk
- rollback notes
- AI assistance disclosure

## Validation

Use the most specific validation available.

For script-only changes:

```bash
bash -n scripts/*.sh
bash -n steps/*/*.sh
```

For step changes, run the relevant step validation if a live cluster is available:

```bash
./steps/step-01-rhoai-platform/validate.sh
./steps/step-02-gpu-infra/validate.sh
./steps/step-03-llm-serving-maas/validate.sh
./steps/step-04-devspaces/validate.sh
./steps/step-05-mta/validate.sh
./steps/step-06-developer-hub/validate.sh
```

If live validation is not possible, say:

> Not validated against a live OpenShift cluster. Static review only.

## Security rules

Never commit:

- tokens
- kubeconfigs
- real passwords
- private keys
- cloud credentials
- model provider API keys
- private customer data

Use `env.example` for placeholders and `.env` for local values. `.env` must not be committed.

## Demo integrity rules

This repository teaches a governed enterprise AI platform pattern. Do not make changes that weaken the central story:

- model access should go through MaaS
- private and external model paths must remain clearly distinguished
- GitOps should remain the source of truth
- documentation should explain both platform value and operational steps
- workarounds should be tracked in `BACKLOG.md` until they are truly obsolete

## Division of responsibility

### Contributor role

The contributor may use Cursor with Claude or GPT to:

- research the repo
- propose a plan
- edit files
- generate docs
- update manifests
- prepare validation steps

The contributor must:

- review the full diff
- run validation where possible
- fill out the PR template
- disclose AI assistance
- explain risk and rollback

### Reviewer role

The reviewer should focus on:

- whether the change matches the issue
- whether the demo story still makes sense
- whether GitOps behavior is preserved
- whether security boundaries are preserved
- whether validation is honest
- whether docs and troubleshooting are updated

### Sensitive areas requiring review

For these areas, require review from another person even if the team is small:

- MaaS gateway routing
- Authorino and Kuadrant policies
- RBAC
- NetworkPolicy
- API keys and external model credentials
- Dev Spaces workspace permissions
- MCP permissions
