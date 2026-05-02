---
name: maintain-rules-and-skills
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  rhoai-version: "3.4"
  ocp-version: "4.20"
description: >
  Manage the Cursor platform configuration for this project — rules, skills,
  hooks, and subagents. Use when the user asks to create a rule, update a skill,
  audit rules, review skills, add a hook, create a subagent, or asks about
  .cursor/ configuration. Also use when discussing what type of component
  (rule vs skill vs hook vs subagent) is appropriate for a given need, or when
  deciding whether guidance should be a rule, skill, documentation, PR checklist,
  or local/private workflow. Do NOT use for deploying the demo (use deploy.sh),
  troubleshooting cluster issues (use rhoai-troubleshoot), or manifest review
  (use manifest-reviewer agent).
---

# Maintain Rules, Skills, Hooks & Subagents

Structured workflow for creating, updating, and auditing the four Cursor
platform components in this project.

## Decision Framework: Which Component Type?

| Need | Component | Why |
|------|-----------|-----|
| Persistent coding guidance for specific file types | **Rule** (`.cursor/rules/*.mdc`) | Scoped by glob, always in context when editing matching files |
| Persistent guidance for ALL files | **Rule** with `alwaysApply: true` | Budget carefully — track total always-apply lines |
| Multi-step workflow with domain knowledge | **Skill** (`.cursor/skills/*/SKILL.md`) | Progressive disclosure; agent invokes when relevant |
| Destructive or sensitive workflow | **Skill** with `disable-model-invocation: true` | Only invoked explicitly via `/skill-name` |
| Complex multi-step task needing context isolation | **Subagent** (`.cursor/agents/*.md`) | Own context window; parallel execution; readonly option |
| Automated validation after file edits | **Hook** (`.cursor/hooks.json`) | Runs scripts automatically; no agent decision needed |
| Gate risky shell commands | **Hook** (`beforeShellExecution`) | Blocks or warns before dangerous operations |

## Design Decision: Where Should This Guidance Live?

When asked to create guidance, first determine the right home:

| Guidance type | Put it in | When to use |
|---------------|-----------|-------------|
| Always-on behavior constraint | **Rule** (`.cursor/rules/*.mdc`) | Agent must consistently enforce it |
| Repeatable workflow with steps and output | **Skill** (`.cursor/skills/*/SKILL.md`) | Task-specific, invoked when relevant |
| Explanatory context or policy | **Documentation** (`docs/`, `AGENTS.md`, `CONTRIBUTING.md`) | Informational, not enforced by agent |
| Single confirmation during review | **PR template checklist** | Only needed at PR time |
| Personal preferences or local setup | **Local/private** (`~/.cursor/`) | Applies to one person only |
| No change needed | — | Existing rules/skills already cover it |

Before proposing a new shared rule or skill, inspect existing files to avoid duplication:
- `.cursor/rules/` (all existing rules)
- `.cursor/skills/` (all existing skills)
- `AGENTS.md`
- `CONTRIBUTING.md`
- `docs/AI_COLLABORATION.md`

## Recommendation Output Format

When evaluating whether to create a new rule or skill, produce:

```markdown
## Recommendation
Rule, skill, documentation, PR checklist, local/private, or no change.

## Reason
Why this is the right home.

## Proposed file
Path:

## Draft content

## Risks
Could this confuse agents, duplicate guidance, leak private details, or over-constrain contributors?

## Validation
How the team should review or test this change.
```

## Current Inventory

| Type | Count | Location |
|------|-------|----------|
| Rules | 11 | `.cursor/rules/*.mdc` |
| Skills | 13 | `.cursor/skills/*/SKILL.md` |
| Hooks | 4 | `.cursor/hooks.json` |
| Subagents | 3 | `.cursor/agents/*.md` |

## Instructions

### Before Creating Any Component

1. Read `references/conventions.md` for detailed patterns
2. Check for overlaps — does an existing rule/skill already cover this?
3. Decide the component type using the decision framework above

### Creating a Rule

- Use `.mdc` extension with YAML frontmatter (`description`, `globs`, `alwaysApply`)
- If `alwaysApply: true`, check the budget (track total lines for always-apply rules)
- Include a References section with official Red Hat doc links for RHOAI/OCP-specific rules
- Include an Agent Behavior section if the rule requires post-edit verification
- Reference files with `@filename` instead of copying content into the rule

### Creating a Skill

- `name` in frontmatter MUST match the parent folder name
- Include `metadata` with `version`, `rhoai-version`, `ocp-version`
- Write "pushy" descriptions: enumerate specific scenarios, not generic triggers
- Include negative triggers: "Do NOT use for X (use Y instead)"
- Use `disable-model-invocation: true` for destructive operations
- Keep SKILL.md under 500 lines; use `references/` for detailed knowledge
- If the skill has a companion rule, reference it instead of duplicating content

### Creating a Subagent

- Place in `.cursor/agents/` with `.md` extension
- Set `readonly: true` for information-gathering agents
- Use `model: fast` for high-volume search/verification tasks
- Use `model: inherit` for tasks needing the same reasoning as the parent
- Write focused descriptions — avoid generic "helper" agents

### Creating a Hook

- Define in `.cursor/hooks.json` (project-level)
- Scripts go in `.cursor/hooks/` (paths relative to project root)
- Use matchers to filter by file pattern or command
- Test hooks manually before relying on them

### Auditing All Components

Run this audit periodically (monthly or after major changes):

1. Read every rule and skill file
2. Check for content duplication between rules and skills
3. Check for stale references (removed steps, renamed files)
4. Verify skill `name` fields match folder names
5. Verify always-apply budget hasn't crept up
6. Check Red Hat doc links still resolve

For detailed conventions and patterns, read `references/conventions.md`.
