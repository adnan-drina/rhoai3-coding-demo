---
name: maintain-rules-and-skills
metadata:
  author: rhoai3-coding-demo
  version: 3.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Project Structure"
description: >
  Manage shared agent guidance for this project — AGENTS.md, shared rules,
  shared skills, hooks, and tool bridges. Use when the user asks to
  create a rule, update a skill, audit rules, review skills, add a hook, create
  a subagent, or asks about .agents/ or .cursor/ configuration. Also use when
  discussing what type of component (rule vs skill vs hook vs subagent) is
  appropriate for a given need, or when deciding whether guidance should be a
  rule, skill, documentation, PR checklist, or local/private workflow.
  Do NOT use for deploying the demo (use deploy.sh), troubleshooting
  cluster issues (use rhoai-troubleshoot), or manifest review (use
  review-gitops-change).
---

# Maintain Rules, Skills, and Hooks

Structured workflow for creating, updating, and auditing shared agent guidance and tool bridges in this project.

## Decision Framework: Which Component Type?

| Need | Component | Why |
|------|-----------|-----|
| Tool-neutral project contract | **AGENTS.md** | Applies across agents and should stay concise |
| Short tool-neutral guidance for a file family or domain | **Rule** (`.agents/rules/*.md`) | Small constraints that should apply across tools |
| Persistent guidance for ALL files | **AGENTS.md** | Keep always-on instructions concise and tool-neutral |
| Multi-step workflow with domain knowledge | **Skill** (`.agents/skills/*/SKILL.md`) | Progressive disclosure; agent invokes when relevant |
| Destructive or sensitive workflow | **Skill** with `disable-model-invocation: true` | Only invoked explicitly via `/skill-name` |
| Complex multi-step task needing context isolation | **Subagent** only when tool-specific isolation is required | Own context window; parallel execution; readonly option |
| Automated validation after file edits | **Tool hook config + script** | Runs scripts automatically; no agent decision needed |
| Gate risky shell commands | **Shared hook implementation** (`.agents/hooks/`) | Reusable safety logic called by tool-specific configs |

## Design Decision: Where Should This Guidance Live?

| Guidance type | Put it in | When to use |
|---------------|-----------|-------------|
| Always-on behavior constraint | **Rule** (`.agents/rules/*.md`) | Agent must consistently enforce it |
| Repeatable workflow with steps and output | **Skill** (`.agents/skills/*/SKILL.md`) | Task-specific, invoked when relevant |
| Explanatory context or policy | **Documentation** (`docs/`, `AGENTS.md`) | Informational, not enforced by agent |
| Single confirmation during review | **PR template checklist** | Only needed at PR time |
| Personal preferences or local setup | **Local/private** | Applies to one person only |

## Skill Groups

Keep folders flat and use the prefix plus frontmatter `metadata.skill-group` for logical ownership:

| Group | Prefix | Purpose |
|-------|--------|---------|
| Project Structure | `project-*` | Repo layout, demo stage authoring, GitOps authoring, documentation structure, RHOAI docs-to-skill generation, manifest review, Red Hat source alignment, and shared AI guidance |
| Demo Environment | (none) | Live demo deployment, validation, troubleshooting, shutdown, recovery, and redeploy |
| RHOAI Platform | `rhoai-*` | Official-doc-backed active-baseline RHOAI component installation, configuration, and usage |
| OpenShift Platform | `ocp-*` | Official-doc-backed OpenShift Container Platform guidance for infrastructure, networking, auth, monitoring, GitOps, cluster, and storage integration |
| OpenShift Data Foundation | `odf-*` | Official-doc-backed OpenShift Data Foundation storage, object storage, Ceph, NooBaa, storage class, and data-service integration guidance |
| Assets & Miscellaneous | (none) | Visual, deck, and presentation assets |

Use `project-red-hat-doc-skill-authoring` for new `rhoai-*`, `ocp-*`, and `odf-*` skills generated from official Red Hat docs, and use `.agents/references/red-hat-doc-map.yaml` to route Red Hat product documentation categories and books to flat skills.

## Instructions

### Before Creating Any Component

1. Read `AGENTS.md`, `.agents/rules/*.md`, and this skill for current governance, taxonomy, and inventory
2. Read `references/conventions.md` for detailed patterns
3. Check for overlaps — does an existing rule/skill already cover this?
4. Decide the component type using the decision framework above
5. If `AGENTS.md` or a rule references a canonical repo skill that exists under
   `.agents/skills/` but is missing from the runtime-discovered skill list, read the on-disk skill as project guidance and record the discovery gap in the work summary or backlog.

### Creating a Rule

- Use `.md` extension under `.agents/rules/`
- Keep rules short, tool-neutral, and focused on one domain or file family
- Include YAML frontmatter with `name` and optional `applies-to` patterns
- Point to `.agents/skills/<skill>/SKILL.md` and specific references instead
  of copying workflow content
- Put always-on project instructions in `AGENTS.md`
- Put multi-step procedures in `.agents/skills/`

### Creating a Skill

- `name` in frontmatter MUST match the parent folder name
- Include `metadata` with `version`, `platform-family`, `platform-baseline`, `ocp-baseline`, and `skill-group`
- Write "pushy" descriptions: enumerate specific scenarios, not generic triggers
- Include negative triggers: "Do NOT use for X (use Y instead)"
- Use `disable-model-invocation: true` for destructive operations
- Keep SKILL.md under 500 lines; use `references/` for detailed knowledge
- If the skill has a companion rule, reference it instead of duplicating content
- Create and edit skills only under `.agents/skills/`; update tool bridges only
  when skill folders are added, renamed, or removed

### Creating a Product Documentation Skill

For skills backed by official Red Hat documentation (RHOAI, OCP, ODF):

1. Use `project-red-hat-doc-skill-authoring` for the full generation workflow
2. Use `project-rhoai-doc-chapter-skill-authoring` for RHOAI chapter-level skills
3. Route documentation to the matching flat skill using
   `.agents/references/red-hat-doc-map.yaml`
4. Do not create nested skill folders that mirror Red Hat documentation categories
5. Include `references/official-doc-extraction.md` for the source material
6. Include `references/validation-checklist.md` for verification steps
7. Include `references/source-capture.md` for provenance tracking

### Creating a Subagent

- Prefer a shared skill first. Add a tool-specific subagent only when normal
  skill invocation does not provide enough context isolation or parallelism.
- Set `readonly: true` for information-gathering agents
- Write focused descriptions — avoid generic "helper" agents

### Creating a Hook

- Put reusable hook logic in `.agents/hooks/`
- Define tool-specific wiring in the tool's hook config
- Cursor-only scripts go in `.cursor/hooks/` when they depend on Cursor payloads
- Use matchers to filter by file pattern or command
- Use `failClosed: true` for security-critical hooks
- Test hooks manually before relying on them

### Auditing All Components

Run this audit periodically or after major changes:

1. Read every rule and skill file
2. Check for content duplication between rules and skills
3. Check for stale references (removed steps, renamed files)
4. Verify skill `name` fields match folder names
5. Verify always-apply budget hasn't crept up
6. Check Red Hat doc links still resolve
7. Update `AGENTS.md`, `.agents/rules/*.md`, and this skill when inventory or taxonomy changes

For detailed conventions and patterns, read `references/conventions.md`.

### Documentation Alignment Loop

When a rules/skills/agent update changes how GitOps manifests or stage READMEs are authored, keep the product-documentation loop current:

1. Check whether the change affects a GitOps-managed component, ArgoCD app, or
   stage README.
2. For scoped follow-up on a single stage, run `update-demo-docs` for that
   stage only.
3. Update `docs/OPERATIONS.md` if deployment or validation behavior changes.
4. Update `docs/TROUBLESHOOTING.md` if a failure mode or recovery path changes.

## Tool Bridges

This project keeps shared guidance in tool-neutral locations where possible, then exposes that guidance to tools through small bridge files only when needed.

### Canonical shared sources

- **Project contract**: `AGENTS.md`
- **Rules**: `.agents/rules/*.md`
- **Skills**: `.agents/skills/*/SKILL.md`
- **Reference maps**: `.agents/references/*.yaml`
- **Reusable hook implementations**: `.agents/hooks/`
- **Platform baseline**: `docs/PLATFORM_BASELINE.md`

### Tool-specific bridges

- `.cursor/` contains hook configuration and Cursor-specific hook scripts
- Do not add tool-specific rule copies unless there is a proven tool-only gap
- Prefer improving `AGENTS.md`, `.agents/rules/`, or a shared skill first

Shared `.agents/` and `.cursor/` files in this repo are project guidance and should be reviewed like source. Personal or machine-specific guidance belongs in home-directory config, not the repo.

## Shared Versus Local

A shared rule or skill may be committed only when it:
- applies to all contributors
- contains no secrets or private environment details
- is stable enough to maintain
- can be reviewed by another contributor

## Quality Bar

Rules should be: short, specific, durable, enforceable, non-duplicative.

Skills should include: when to use, required inputs, files to inspect, steps to follow, validation commands, expected output, things the agent must not do.
