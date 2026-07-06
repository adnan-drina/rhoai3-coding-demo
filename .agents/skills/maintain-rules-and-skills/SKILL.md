---
name: maintain-rules-and-skills
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Project Structure"
description: >
  Manage shared agent guidance for this project — rules, skills, hooks, and
  tool bridges. Use when the user asks to create a rule, update a skill, audit
  rules, review skills, add a hook, or asks about .agents/ or .cursor/
  configuration. Also use when discussing what type of component (rule vs skill
  vs hook vs subagent) is appropriate for a given need, or when deciding whether
  guidance should be a rule, skill, documentation, PR checklist, or local/private
  workflow. Do NOT use for deploying the demo (use deploy.sh), troubleshooting
  cluster issues (use rhoai-troubleshoot), or manifest review (use
  review-gitops-change).
---

# Maintain Rules, Skills, and Hooks

Structured workflow for creating, updating, and auditing shared agent guidance
in this project.

## Decision Framework: Which Component Type?

| Need | Component | Why |
|------|-----------|-----|
| Tool-neutral project contract | **AGENTS.md** | Applies across agents and should stay concise |
| Short tool-neutral guidance for a file family or domain | **Rule** (`.agents/rules/*.md`) | Small constraints that apply across tools |
| Persistent guidance for ALL files | **AGENTS.md** | Keep always-on instructions concise and tool-neutral |
| Multi-step workflow with domain knowledge | **Skill** (`.agents/skills/*/SKILL.md`) | Progressive disclosure; agent invokes when relevant |
| Destructive or sensitive workflow | **Skill** with `disable-model-invocation: true` | Only invoked explicitly |
| Complex multi-step task needing context isolation | **Subagent** | Own context window; parallel execution; readonly option |
| Automated validation after file edits | **Tool hook config + script** | Runs scripts automatically |
| Gate risky shell commands | **Shared hook** (`.agents/hooks/`) | Reusable safety logic called by tool-specific configs |

## Design Decision: Where Should This Guidance Live?

| Guidance type | Put it in | When to use |
|---------------|-----------|-------------|
| Always-on behavior constraint | **Rule** (`.agents/rules/*.md`) | Agent must consistently enforce it |
| Repeatable workflow with steps and output | **Skill** (`.agents/skills/*/SKILL.md`) | Task-specific, invoked when relevant |
| Explanatory context or policy | **Documentation** (`docs/`, `AGENTS.md`) | Informational, not enforced by agent |
| Single confirmation during review | **PR template checklist** | Only needed at PR time |
| Personal preferences or local setup | **Local/private** | Applies to one person only |

## Current Inventory

| Type | Count | Location |
|------|-------|----------|
| Shared rules | 4 | `.agents/rules/*.md` |
| Shared skills | 13 | `.agents/skills/*/SKILL.md` |
| Shared hook scripts | 1 | `.agents/hooks/` |
| Cursor hook bridge | 1 config, 2 scripts | `.cursor/hooks.json`, `.cursor/hooks/` |

Canonical governance: `AGENTS.md`, `.agents/rules/*.md`, and this skill.

## Instructions

### Before Creating Any Component

1. Read `AGENTS.md` and `.agents/rules/*.md` for current governance and taxonomy
2. Check for overlaps — does an existing rule/skill already cover this?
3. Decide the component type using the decision framework above

### Creating a Rule

- Use `.md` extension under `.agents/rules/`
- Keep rules short, tool-neutral, and focused on one domain
- Include YAML frontmatter with `name` and `applies-to` patterns
- Point to `.agents/skills/` instead of duplicating workflow content

### Creating a Skill

- `name` in frontmatter MUST match the parent folder name
- Include `metadata` with `version`, `platform-family`, `platform-baseline`, `ocp-baseline`, and `skill-group`
- Write "pushy" descriptions: enumerate specific scenarios, not generic triggers
- Include negative triggers: "Do NOT use for X (use Y instead)"
- Use `disable-model-invocation: true` for destructive operations
- Keep SKILL.md under 500 lines; use `references/` for detailed knowledge

### Creating a Hook

- Put reusable hook logic in `.agents/hooks/`
- Define tool-specific wiring in `.cursor/hooks.json`
- Cursor-only scripts go in `.cursor/hooks/`
- Use matchers to filter by file pattern or command
- Test hooks manually before relying on them

### Auditing All Components

1. Read every rule and skill file
2. Check for content duplication between rules and skills
3. Check for stale references (removed steps, renamed files)
4. Verify skill `name` fields match folder names
5. Check Red Hat doc links still resolve
6. Update `AGENTS.md` when inventory or taxonomy changes

## Tool Bridges

This project keeps shared guidance in tool-neutral locations:

### Canonical shared sources

- **Project contract**: `AGENTS.md`
- **Rules**: `.agents/rules/*.md`
- **Skills**: `.agents/skills/*/SKILL.md`
- **Reusable hook implementations**: `.agents/hooks/`

### Tool-specific bridges

- `.cursor/` contains only hook configuration and Cursor-specific hook scripts
- Do not add tool-specific rule copies; prefer improving `.agents/rules/` or a shared skill

## Shared Versus Local

A shared rule or skill may be committed only when it:
- applies to all contributors
- contains no secrets or private environment details
- is stable enough to maintain
- can be reviewed by another contributor

## Quality Bar

Rules should be: short, specific, durable, enforceable, non-duplicative.

Skills should include: when to use, required inputs, files to inspect, steps to
follow, validation commands, expected output, things the agent must not do.
