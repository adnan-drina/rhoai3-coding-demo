# Agent Guidance

This directory contains tool-neutral shared agent guidance. It is the canonical
source for rules, skills, hooks, and reference data. Tool-specific
configuration lives in thin bridge files (e.g. `.cursor/hooks.json`) that point
here.

## Layout

| Path | Purpose |
|------|---------|
| `hooks/` | Shared hook implementations (cluster guard, YAML validation, doc consistency, session init) |
| `rules/*.md` | Short tool-neutral domain rules |
| `skills/*/SKILL.md` | Canonical shared skills following the Agent Skills layout |
| `references/` | Shared reference maps and supporting data |

## Hooks inventory

| Hook | Purpose | Used by |
|------|---------|---------|
| `guard-openshift-command.py` | Block mutating `oc`/`kubectl` commands unless cluster guard matches | `.cursor/hooks.json` (beforeShellExecution) |
| `validate-yaml.sh` | Run `kustomize build` after GitOps YAML edits | `.cursor/hooks.json` (afterFileEdit) |
| `check-docs-consistency.sh` | Remind when manifest edits lack companion README updates | `.cursor/hooks.json` (afterFileEdit) |
| `session-init.sh` | Inject cluster login status on session start | Available for tool bridge wiring |

## Tool-specific directories

- `.cursor/` contains only `hooks.json` (event wiring) and `agents/*.md`
  (thin subagent stubs that point to shared skills). It must not contain
  shared rules, skills, or hook implementations.
- `.claude/` and `.codex/` are gitignored — they hold local runtime preferences
  only.

## Adding a new hook

1. Write the implementation in `.agents/hooks/`.
2. Add a bridge entry in each tool's config file (e.g. `.cursor/hooks.json`).
3. Update this README.
