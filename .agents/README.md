# Agent Guidance

This directory contains tool-neutral shared agent guidance.

## Layout

| Path | Purpose |
|------|---------|
| `hooks/` | Shared reusable hook implementations |
| `rules/*.md` | Short tool-neutral domain rules |
| `skills/*/SKILL.md` | Canonical shared skills following the Agent Skills layout |
| `references/` | Shared reference maps and supporting data |

Keep tool-specific hooks, settings, and subagents in their native directories
only when the tool requires that format.

## Tool-Specific Directories

- `.cursor/` should contain only Cursor hook configuration and Cursor-specific
  hook scripts that cannot be shared. It should not contain shared rules,
  skills, agents, or worktree state.
