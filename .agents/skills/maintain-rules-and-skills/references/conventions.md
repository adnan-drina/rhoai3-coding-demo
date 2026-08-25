# Shared Agent Guidance Conventions

Use these conventions when changing `AGENTS.md`, `.agents/`, or tool bridge files (e.g. `.cursor/hooks.json`) in this repository.

## AGENTS.md

`AGENTS.md` is the root, tool-neutral contract for coding agents.

- Keep it concise enough to be useful on every task.
- Use plain Markdown; do not rely on tool-specific include syntax.
- Include project overview, commands, safety constraints, branch/commit rules,
  and pointers to detailed shared rules and skills.
- Add nested `AGENTS.md` files only for genuinely distinct subprojects with
  local instructions that should override root guidance.
- If instructions conflict, the user's current prompt wins; otherwise the
  closest applicable `AGENTS.md` should be treated as more specific.

## Shared Rules

Rules live under `.agents/rules/` and are short, tool-neutral domain guardrails. They are not a replacement for root `AGENTS.md`; they give agents a predictable place to look before work in a specific skill group.

Current rule taxonomy:

| Rule | Skill prefix | Purpose |
|------|--------------|---------|
| `project.md` | `project-` | Repo structure, GitOps authoring, docs, manifest review, Red Hat source alignment, and shared guidance |
| `env.md` | (none) | Live demo environment deployment, validation, troubleshooting, shutdown, recovery, and redeploy |
| `kanban-log-watch.md` | (none) | Dest Hermes Kanban: read the official worker log in the same turn as spawn |
| `ensure-cli-capability.md` | (none) | Stage 080 `ensure_cli` must probe kantra **usability** (`kantra-assert-exec`), not mere presence |
| `gitops.md` | (none) | GitOps authoring, manifests, labels, schema validation |
| `docs.md` | (none) | Documentation standards, README structure, operations docs |
| `rhoai.md` | `rhoai-` | Official-doc-backed RHOAI component behavior and configuration |
| `ocp.md` | `ocp-` | Official-doc-backed OpenShift infrastructure, networking, auth, monitoring, GitOps, and storage integration |
| `odf.md` | `odf-` | Official-doc-backed OpenShift Data Foundation storage, object storage, NooBaa, and storage class guidance |

Rule frontmatter should stay simple:

```yaml
---
name: project
skill-group: Project Structure
skill-prefix: project-
applies-to:
  - AGENTS.md
  - .agents/**
---
```

Keep detailed procedure in skills, not rules. A rule should point to the relevant skills and state the non-negotiable constraints for that domain.

## Shared Skills

Skills live under `.agents/skills/<skill-name>/SKILL.md`.

Skill frontmatter:

```yaml
---
name: skill-name
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Project Structure"
description: >
  Use when [specific scenarios]. Do NOT use for [X] (use [Y] instead).
---
```

Conventions:

- `name` must match the parent folder.
- Folder prefix must match `metadata.skill-group`.
- Use `platform-baseline: "repo"` and `ocp-baseline: "repo"` so the active
  versions stay centralized in `docs/PLATFORM_BASELINE.md`.
- Descriptions should enumerate concrete trigger scenarios and negative
  triggers.
- Keep `SKILL.md` focused; put deeper detail in `references/`, executable
  helpers in `scripts/`, and reusable examples in `examples/` when needed.
- Keep tool-specific copies out of the repo.
- If a canonical repo skill exists on disk but is not listed by the current
  runtime skill discovery output, treat the on-disk skill as project guidance after reading it fully and note the discovery mismatch for follow-up.

### Product documentation skills

Product documentation skills (`rhoai-*`, `ocp-*`, `odf-*`) follow an extended structure:

```
skill-name/
  SKILL.md                              # Workflow and usage guidance
  references/
    official-doc-extraction.md          # Extracted official docs content
    validation-checklist.md             # Verification steps
    source-capture.md                   # Provenance tracking
  examples/
    component-patterns.md              # Reusable configuration patterns
```

Use `project-red-hat-doc-skill-authoring` for the generation workflow and `.agents/references/red-hat-doc-map.yaml` to route documentation topics to skills.

## Shared Hooks

Reusable hook implementations live under `.agents/hooks/`.

- Tool-specific hook config may call shared hook scripts.
- Keep hook logic deterministic and non-secret.
- Hooks should validate, remind, or block; they should not rewrite project files.
- Security-critical hooks should fail closed when the tool supports that mode.
## Tool Bridges

Keep tool-specific directories minimal:

| Directory | Tracked in git? | Contains |
|-----------|----------------|----------|
| `.cursor/` | Yes | `hooks.json` (event wiring) and `agents/*.md` (thin subagent stubs pointing to shared skills) |
| `.claude/` | No (gitignored) | Local Claude Code runtime preferences |
| `.codex/` | No (gitignored) | Local Codex runtime preferences |

Do not reintroduce tool-specific rules, skills, or hook implementations. Tool bridge files should only wire tool events to `.agents/hooks/` and provide thin subagent stubs that delegate to `.agents/skills/`.

### Cursor subagents (`.cursor/agents/`)

Cursor subagents use a YAML frontmatter format specific to Cursor:

```yaml
---
name: agent-name
description: >
  Short description. Thin Cursor wrapper around the shared <skill-name> skill.
model: inherit  # or "fast" for lightweight inspection
readonly: true
---
```

Subagent bodies should be minimal — instruct the subagent to read and follow the shared skill, point to relevant rules, and state safety constraints. Keep the actual checklist content in `.agents/skills/`.

## Red Hat Documentation Alignment

Every rule or skill that references RHOAI or OCP features should:
- Include a References section with official doc URLs
- Use `docs.redhat.com` as the primary source
- Note version-specific behavior: `> **Note (RHOAI 3.4):** ...`

## Anti-Patterns

| Anti-pattern | Better approach |
|-------------|-----------------|
| Copying code into rules | Use `@filename` to reference the canonical source |
| Always-apply for niche guidance | Use glob-scoped or "Apply Intelligently" |
| Duplicating content between rule and skill | Skill references the rule |
| Generic subagent descriptions | Specific: "reviews manifests for label compliance" |
| 50+ hooks on every event | Use matchers to scope hooks narrowly |
| Hook scripts that modify files | Hooks should validate/audit; let the agent make edits |

## Audit Checklist

Run this after major guidance changes:

- [ ] Root `AGENTS.md` is plain Markdown and self-contained enough to orient a
      new agent.
- [ ] `.agents/rules/` has the expected group-level rules unless the skill
      taxonomy changes.
- [ ] Every rule points to the relevant skills instead of duplicating workflows.
- [ ] Every skill `name` matches its folder.
- [ ] Every skill has `metadata.skill-group`, `platform-baseline`, and
      `ocp-baseline`.
- [ ] No active references point to removed paths.
- [ ] Hook scripts pass syntax checks and JSON hook configs parse.
- [ ] `AGENTS.md` and `.agents/rules/README.md` inventories match the filesystem.
