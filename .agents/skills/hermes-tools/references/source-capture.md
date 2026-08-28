# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | no version marker on doc pages (family anchor: v0.20.0, 2026-08-03) |
| Chapter or page title | Tools & Toolsets; Toolsets Reference; Built-in Tools Reference |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/tools |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/toolsets-reference |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/tools-reference |
| Documentation category | Features / Reference |
| Capture date | 2026-08-12 |
| Capture method | Reviewer-direct capture (no separate research dossier — single-domain gap-fill requested by the maintainer): full heading outline of the feature page plus targeted verbatim extraction from all three pages, cross-checked against the kanban capture's toolset facts (zero-schema-footprint, orchestrator restriction pattern) — consistent |

## Captured Sections

- Tools & Toolsets feature page (6 top-level sections): definition,
  Available Tools (9 categories), Using Toolsets (`--toolsets`,
  `hermes tools`), Terminal Backends (7 backends + `terminal.backend` +
  per-backend config subsections), Background Process Management
  (`background=true`, `process` tool actions, `pty`), Sudo Support.
- Toolsets Reference: ~35 named toolsets with descriptions and opt-in
  markers; composites (`coding`, `debugging`, `safe`); platform presets
  (`hermes-cli` default, acp/api-server/webhook/cron/discord/gateway
  variants); dynamic toolsets (`mcp-<server>`, plugin, custom).
- Tools Reference: intro ("built-in tools, grouped by toolset.
  Availability varies by platform, credentials, and enabled toolsets"),
  ~83 tools across 30+ sections; per-tool doc format sampled.

## Source Boundaries

This skill owns the toolset model, inventory, composition, terminal
backend selection, background processes, and sudo. Approval/security
posture and container hardening belong to `hermes-managed-scope`;
`terminal.*`/config wiring to `hermes-configuration`; the CLI surface to
`hermes-cli`; kanban tool semantics to `hermes-kanban`; MCP server
configuration remains an unowned taxonomy gap.

## Known Open Items

- The exact config.yaml key shape for per-platform toolset lists is not
  displayed on the feature page (configure via `hermes tools`; verify
  with `hermes tools --summary`) — recheck the configuration page or a
  live seat before hand-authoring YAML.
- No comprehensive default-enabled list exists beyond the `hermes-cli`
  preset description and explicit opt-in markers (`kanban`, `x_search`,
  `video`).
- Per-tool parameter schemas were sampled, not exhaustively captured —
  the Tools Reference page is the lookup source (~83 tools).
