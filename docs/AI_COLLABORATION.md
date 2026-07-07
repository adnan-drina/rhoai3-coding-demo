# AI-Assisted Collaboration Model

This document defines how AI tools are used in this repository.

## Operating principle

AI tools (Cursor, Claude, GPT, Continue, OpenCode) are treated as accelerated collaborators, not autonomous maintainers. Every change must be owned by a human contributor.

The contribution flow:

> Human-defined task → AI-assisted plan → focused branch → full human diff review → explicit validation → PR with AI disclosure → human-owned merge.

This model fits the project because the demo itself is about governed AI development: private and external models through MaaS, controlled developer tooling, GitOps repeatability, and clear trust boundaries. The repo should practice the same governance pattern that it demonstrates.

## Architecture: tool-neutral by design

All project governance — rules, skills, hooks, and reference data — lives in
`.agents/`. Tool-specific configuration is kept to the minimum needed for each
tool to discover and invoke the shared layer.

```
.agents/                        # canonical, tool-neutral (tracked in git)
├── rules/*.md                  # always-on behavior constraints
├── skills/*/SKILL.md           # invocable workflows
├── hooks/                      # shared hook implementations
│   ├── guard-openshift-command.py
│   ├── session-init.sh
│   ├── check-docs-consistency.sh
│   └── validate-yaml.sh
└── references/                 # shared reference maps

AGENTS.md                       # root agent contract (tool-neutral)

.cursor/                        # thin Cursor bridge (tracked in git)
├── hooks.json                  # wires Cursor events to .agents/hooks/
└── agents/*.md                 # Cursor subagent stubs → shared skills

.claude/                        # gitignored — local Claude Code config
.codex/                         # gitignored — local Codex config
```

### Adding support for a new tool

To add a new AI tool (e.g. Copilot, Continue, Windsurf):

1. The tool reads `AGENTS.md` for the project contract.
2. If the tool has a hook/plugin system, create a thin bridge file that points
   to `.agents/hooks/` implementations.
3. Do not duplicate rules, skills, or hook logic into the tool-specific folder.

## Rules and skills policy

### Shared project rules

Rules live in `.agents/rules/*.md`. They define project-wide always-on behavior
constraints: repository structure, GitOps expectations, security boundaries,
validation expectations, and PR requirements.

The root `AGENTS.md` is the tool-neutral entry point that all tools should read.

Rules should be stable, short, and applicable to all contributors.

### Shared project skills

Skills live in `.agents/skills/*/SKILL.md`. They define repeatable project
workflows such as reviewing GitOps changes, validating demo stages, updating
documentation, preparing PR summaries, and reviewing workarounds.

A skill may be shared when it is useful to all contributors, contains no
secrets, and represents a workflow that should be performed consistently.

### Local/private rules and skills

Contributors may maintain private rules and skills for personal workflows in
their user-level tool configuration (e.g. `~/.cursor/rules/`). These must not
be committed if they include:

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

## Skill taxonomy

Skills use a flat folder structure under `.agents/skills/` with a
`metadata.skill-group` taxonomy for organization. See `AGENTS.md` for the
complete skill inventory table.

| Category | Example skills | Purpose |
|----------|---------------|---------|
| Review and delivery | `review-gitops-change`, `review-manifest-compliance`, `review-doc-alignment`, `prepare-pr-summary` | Review changes, explain risk, and prepare PR output |
| Validation and documentation | `validate-demo-step`, `update-demo-docs`, `demo-operations-docs` | Keep stage behavior, docs, and operations material aligned |
| Live operations | `rhoai-troubleshoot`, `inspect-cluster`, `manage-devspaces`, `manage-resources`, `resume-gpu-demo` | Diagnose or intentionally change live cluster resources |
| RHOAI platform | `rhoai-*` skills | Official-doc-backed RHOAI component guidance |
| OCP platform | `ocp-*` skills | Official-doc-backed OCP infrastructure guidance |
| Deliverables | `red-hat-quick-deck` | Create Red Hat-aligned presentation artifacts |
| Governance | `maintain-rules-and-skills` | Add, update, audit, or retire shared AI guidance |

## Skill quality bar

Shared skills should:

- have a `name` matching the parent folder
- include metadata with version and platform targets when project-specific
- have a specific trigger description and negative triggers
- keep `SKILL.md` under 500 lines when practical
- move large detail into `references/`
- avoid duplicating companion rules
- avoid secrets, local paths, private URLs, and local cluster assumptions
- mark destructive or expensive workflows with `disable-model-invocation: true`

## Automation hooks

Shared hook implementations live in `.agents/hooks/`. Tool-specific bridge
files (e.g. `.cursor/hooks.json`) wire tool events to the shared
implementations.

| Hook | Trigger | What it does | Failure behavior |
|------|---------|--------------|-----------------|
| `validate-yaml.sh` | After editing a `gitops/**/*.yaml` file | Runs `kustomize build` on the nearest base; warns if it fails | Adds a warning to agent context; does not block the edit |
| `check-docs-consistency.sh` | After editing `gitops/stages/**` or `stages/**` | Tracks edits per session; reminds if manifest was changed without README or vice versa | Adds a reminder to agent context; does not block |
| `guard-openshift-command.py` | Before running mutating `oc`/`kubectl` commands or deploy scripts | Verifies `RHOAI_EXPECTED_API_SERVER` matches the active cluster; blocks if no guard is set or cluster doesn't match | Blocks the command with an error message |
| `session-init.sh` | On session start | Checks `oc whoami` and injects cluster login status into agent context | Warns "Not logged in" if oc is unavailable or not authenticated |

**Recovering from a false positive:** Hooks do not hard-block file edits. If a hook produces an incorrect warning (e.g., `kustomize build` fails due to a CRD not yet installed), acknowledge the warning and proceed. For `guard-openshift-command.py`, set `RHOAI_ALLOW_UNGUARDED_CLUSTER=true` in `.env` to bypass the guard when explicitly confirmed.

**Hook logs:** Hooks write to stdout/stderr which appears in the agent context. The `check-docs-consistency.sh` hook tracks edits per session in `/tmp/cursor-edit-track-*.log` (cleaned by OS temp policy).

Before any live OpenShift operation:

- open this repo as its own project, not a parent directory
- load the repo-local `.env`
- require `RHOAI_EXPECTED_API_SERVER` or an explicitly approved override
- do not read credentials from another repo by default

## Simple rule of thumb

- If it protects the project, share it.
- If it standardizes the demo workflow, share it.
- If it helps only one person, keep it local.
- If it contains secrets or local environment assumptions, keep it private.
- If it changes how agents behave for everyone, review it through PR.
