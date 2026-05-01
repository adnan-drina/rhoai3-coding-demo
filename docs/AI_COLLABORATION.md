# AI-Assisted Collaboration Model

This document defines how AI tools are used in this repository.

## Operating principle

AI tools (Cursor, Claude, GPT, Continue, OpenCode) are treated as accelerated collaborators, not autonomous maintainers. Every change must be owned by a human contributor.

The contribution flow:

> Human-defined task → AI-assisted plan → focused branch → full human diff review → explicit validation → PR with AI disclosure → human-owned merge.

This model fits the project because the demo itself is about governed AI development: private and external models through MaaS, controlled developer tooling, GitOps repeatability, and clear trust boundaries. The repo should practice the same governance pattern that it demonstrates.

## Rules and skills policy

This repository uses shared AI-agent rules and skills to make Cursor-based collaboration consistent and safe.

### Shared project rules

Shared rules live in:

- `AGENTS.md` — tool-neutral agent guidance (read by Cursor, Copilot, and other agents)
- `.cursor/rules/*.mdc` — Cursor-specific behavior rules

These files define project-wide behavior for agents and contributors. They include repository structure, GitOps expectations, security boundaries, validation expectations, and PR requirements.

Rules should be stable, short, and applicable to all contributors.

### Shared project skills

Shared skills live in:

- `.cursor/skills/*/SKILL.md`

Shared skills define repeatable project workflows such as reviewing GitOps changes, validating demo steps, updating documentation, preparing PR summaries, and reviewing workarounds.

A skill may be shared when it is useful to all contributors, contains no secrets, and represents a workflow that should be performed consistently.

### Local/private rules and skills

Contributors may maintain private rules and skills for personal workflows at `~/.cursor/rules/` and `~/.cursor/skills/`. These must not be committed if they include:

- personal credentials
- local cluster names or URLs
- kubeconfig paths
- private API keys
- private customer or employer information
- personal model preferences
- experimental workflows not yet reviewed by the team

### Promotion from local to shared

A local skill can be promoted to the repo when:

1. At least one contributor has used it successfully.
2. It solves a recurring project problem.
3. It contains no private or machine-specific information.
4. It has clear inputs, steps, and expected output.
5. Another contributor reviews it in a PR.

Do not promote a local skill just because it is clever. Promote it when it creates repeatable project value.

## Decision rule: local or shared?

### Share a rule or skill when all are true

- It applies to every contributor.
- It improves consistency or safety.
- It does not expose secrets or private infrastructure.
- It is stable enough to maintain.
- It is specific to this project or workflow.
- It can be reviewed like code.

### Keep it local/private when any are true

- It contains personal tokens, paths, aliases, or credentials.
- It depends on your local cluster setup.
- It reflects personal coding style rather than project policy.
- It is experimental or unstable.
- It uses private customer/company knowledge.
- It configures a paid model/API key unique to one person.
- It automates destructive operations.
- It would confuse new contributors.

## Rules versus skills

| Put in rules when... | Put in skills when... |
|----------------------|-----------------------|
| It is always-on behavior | It is an invoked workflow |
| It constrains what to do or not do | It describes how to perform a task |
| It is short and durable | It has inputs, steps, and output |
| Example: "Do not bypass MaaS" | Example: "Review a GitOps change" |

## Governance process

### Adding rules and skills

Treat rules and skills as source code. A PR changing rules or skills should explain:

- Why this rule/skill is needed.
- Who it applies to.
- Whether it changes agent behavior.
- Whether it could block or confuse contributors.
- How it was tested.

### Periodic review

Review shared rules and skills after major repo changes. Look for:

- Stale commands or obsolete workarounds.
- Rules that are too broad or conflict with each other.
- Skills that duplicate AGENTS.md guidance.
- Local-only assumptions accidentally committed.

### Rule quality bar

Bad rules (too vague):

- "Always write perfect code."
- "Use best practices."
- "Be secure."

Good rules (specific and actionable):

- "Do not commit secrets, kubeconfigs, API keys, or real tokens."
- "Do not bypass MaaS unless the issue explicitly requests and documents an exception."
- "For changes under `gitops/`, include validation notes and rollback guidance in the PR."

## Shared skills in this repo

| Skill | When to use |
|-------|-------------|
| `review-gitops-change` | Reviewing changes under `gitops/` or platform YAML |
| `validate-demo-step` | After changing a step's deploy, manifests, or validate script |
| `update-demo-docs` | After any change that might affect documentation consistency |
| `prepare-pr-summary` | Before opening a pull request |
| `workaround-review` | When touching known RHOAI, MaaS, or gateway workarounds |
| `demo-operations-docs` | When writing or updating OPERATIONS.md or TROUBLESHOOTING.md |
| `rhoai-troubleshoot` | When diagnosing live cluster failures |
| `manage-devspaces` | When managing Dev Spaces workspaces |
| `maintain-rules-and-skills` | When adding or modifying rules/skills/hooks |

## Cursor hooks

Hooks provide automated enforcement beyond prose rules. They are defined in `.cursor/hooks.json` and run automatically at specific events.

| Hook | Trigger | What it does | Failure behavior |
|------|---------|--------------|-----------------|
| `validate-yaml.sh` | After editing a `gitops/**/*.yaml` file | Runs `kustomize build` on the nearest base; warns if it fails | Adds a warning to agent context; does not block the edit |
| `check-docs-consistency.sh` | After editing `gitops/step-*/**` or `steps/step-*/**` | Tracks edits per session; reminds if manifest was changed without README or vice versa | Adds a reminder to agent context; does not block |
| `guard-oc-commands.py` | Before running `oc delete`, `oc scale`, or `oc patch` | If the command targets a protected namespace (`redhat-ods-applications`, `redhat-ods-operator`, `openshift-gitops`, `openshift-operators`), asks user for confirmation | Prompts "ask" permission; agent must confirm with user |
| `session-init.sh` | On session start | Checks `oc whoami` and injects cluster login status into agent context | Warns "Not logged in" if oc is unavailable or not authenticated |

**Recovering from a false positive:** Hooks do not hard-block operations. If a hook produces an incorrect warning (e.g., `kustomize build` fails due to a CRD not yet installed), acknowledge the warning and proceed. For `guard-oc-commands.py`, the user can confirm destructive operations when prompted.

**Bypassing hooks:** Hooks cannot be bypassed per-invocation. If a hook is consistently wrong for your workflow, disable it by commenting the entry in `.cursor/hooks.json` and propose a fix via PR.

**Hook logs:** Hooks write to stdout/stderr which appears in the agent context. The `check-docs-consistency.sh` hook tracks edits per session in `/tmp/cursor-edit-track-*.log` (cleaned by OS temp policy).

## Simple rule of thumb

- If it protects the project, share it.
- If it standardizes the demo workflow, share it.
- If it helps only one person, keep it local.
- If it contains secrets or local environment assumptions, keep it private.
- If it changes how agents behave for everyone, review it through PR.
