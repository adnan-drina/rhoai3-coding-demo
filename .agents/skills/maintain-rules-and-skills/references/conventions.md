# Project Conventions for Cursor Platform Components

## Table of Contents

- [Rule Conventions](#rule-conventions)
- [Skill Conventions](#skill-conventions)
- [Hook Patterns](#hook-patterns)
- [Subagent Patterns](#subagent-patterns)
- [Anti-Patterns](#anti-patterns)
- [Audit Checklist](#audit-checklist)

## Rule Conventions

### Frontmatter

```yaml
---
description: One-line description shown in rule picker and used by agent to decide relevance
globs: "gitops/**/*.yaml"   # or comma-separated: "*.py,*.sh"
alwaysApply: false           # true only for project-wide behavioral rules
---
```

### Four rule types in Cursor

| Type | Frontmatter | When it activates |
|------|-------------|-------------------|
| Always Apply | `alwaysApply: true`, no globs | Every chat session |
| Apply to Specific Files | `alwaysApply: false`, globs set | When matching files are in context |
| Apply Intelligently | `alwaysApply: false`, no globs | When agent decides based on description |
| Apply Manually | `alwaysApply: false`, no globs, no description | Only when @-mentioned |

### Naming convention

`XX-descriptive-name.mdc` where XX is a priority number:
- `00-09`: Project identity and core principles
- `10-19`: Repository structure and GitOps
- `20-29`: Documentation standards
- `30-39`: Security and secrets
- `40-49`: Manifest and YAML standards
- `50-59`: Cross-cutting conventions (labels, pipelines, change output)
- `60-79`: Step-specific development patterns
- `99`: Plan documents

### Red Hat documentation alignment

Every rule that references RHOAI 3.4 or RHOCP 4.20 features should:
- Include a References section with official doc URLs
- Use `docs.redhat.com` as the primary source
- Note version-specific behavior: `> **Note (RHOAI 3.4):** ...`

### Deduplication principle

Each piece of guidance should have ONE canonical location:
- If guidance appears in both a rule and a skill, the rule is the guardrail (brief),
  the skill is the workflow (detailed), and the skill references the rule
- If guidance appears in two rules, the more specific (glob-scoped) rule is canonical;
  the broader rule references it

### Reference files instead of copying

Use `@filename` in rules to include file contents in context:
```markdown
Follow the patterns in @stages/010-openshift-ai-platform-foundation/deploy.sh
```
This prevents rules from becoming stale when the referenced code changes.

### Agent Behavior sections

Only add to rules that require post-edit verification. Pattern:
```markdown
## Agent Behavior

After modifying [specific file type]:
- [Verification step 1]
- [Verification step 2]
```

## Skill Conventions

### Frontmatter

```yaml
---
name: skill-name                    # MUST match parent folder name
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  rhoai-version: "3.4"
  ocp-version: "4.20"
description: >
  What this skill does. Use when [specific scenarios]. Also use when
  [additional triggers]. Do NOT use for [X] (use [Y] instead).
disable-model-invocation: false     # true for destructive operations
---
```

### Description writing

Descriptions should be "pushy" — enumerate specific scenarios:
- Bad: "Use when deploying the demo"
- Good: "Use when deploying the demo, setting up a new environment, re-deploying
  a specific step, checking deployment status, or when ArgoCD apps are OutOfSync"

### Negative triggers

Every skill must say what NOT to use it for, naming the correct alternative:
```
Do NOT use for chatbot changes (use chatbot-customization) or
model evaluation (use model-evaluation).
```
This creates a routing mesh that reduces mis-triggering.

### Progressive disclosure

```
SKILL.md          # Workflow (~100-150 lines)
references/
  detail-a.md     # Deep knowledge (loaded on demand)
  detail-b.md     # Deep knowledge (loaded on demand)
scripts/
  validate.sh     # Executable scripts
```

Keep SKILL.md under 500 lines. References should have a Table of Contents if over 300 lines.

## Hook Patterns

### Recommended hooks for this project

| Hook | Trigger | Purpose |
|------|---------|---------|
| `afterFileEdit` | `gitops/**/*.yaml` | Auto-run `kustomize build` on the containing base dir |
| `afterFileEdit` | stage files | Warn if code/docs not both edited |
| `beforeShellExecution` | `oc delete\|oc scale` | Warn before destructive cluster operations |
| `sessionStart` | Always | Inject project context (cluster URL from oc whoami) |

### Hook script conventions

- Scripts receive JSON on stdin, return JSON on stdout
- Exit code 0 = success
- Use matchers to avoid running on every file edit / every command
- Python for structured parsing, Bash for simple checks

## Subagent Patterns

### When to use a subagent vs a skill

| Subagent | Skill |
|----------|-------|
| Multi-step investigation with many tool calls | Single-purpose repeatable action |
| Generates verbose intermediate output | Compact, focused workflow |
| Benefits from context isolation | Runs in main chat context |
| Can run in parallel with other work | Sequential execution |

### Model selection

| Value | When to use |
|-------|-------------|
| `fast` | Search, verification, high-volume queries (cheaper, faster) |
| `inherit` | Complex reasoning, code review, architectural decisions |

## Anti-Patterns

| Anti-pattern | Better approach |
|-------------|-----------------|
| Copying code into rules | Use `@filename` to reference the canonical source |
| Always-apply for niche guidance | Use glob-scoped or "Apply Intelligently" |
| Duplicating content between rule and skill | Skill references the rule |
| Generic subagent descriptions ("helps with coding") | Specific: "reviews manifests for label compliance" |
| 50+ hooks on every event | Use matchers to scope hooks narrowly |
| Hook scripts that modify files | Hooks should validate/audit; let the agent make edits |

## Audit Checklist

### Rules
- [ ] All rules have correct frontmatter (description, globs or alwaysApply)
- [ ] Always-apply budget is reasonable
- [ ] No content duplicated between rules
- [ ] RHOAI/OCP-specific rules have References sections with doc URLs
- [ ] Rules with post-edit checks have Agent Behavior sections
- [ ] No stale file references or removed stage numbers

### Skills
- [ ] All `name` fields match parent folder names
- [ ] All skills have `metadata` (version, rhoai-version, ocp-version)
- [ ] All skills have negative triggers ("Do NOT use for...")
- [ ] No content duplicated between skill and companion rule
- [ ] SKILL.md files are under 500 lines

### Hooks
- [ ] `.cursor/hooks.json` has `"version": 1`
- [ ] Hook scripts are executable (`chmod +x`)
- [ ] Matchers are specific enough to avoid false triggers

### Subagents
- [ ] Each agent has a focused, single responsibility
- [ ] Information-gathering agents use `readonly: true`
- [ ] Descriptions are specific enough for agent to decide when to delegate
