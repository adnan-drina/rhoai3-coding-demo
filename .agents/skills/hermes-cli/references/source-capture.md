# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | v0.20.0 "The Herald Release", tag v2026.8.3 (2026-08-03), via the docs-linked GitHub releases page; no doc page carries its own version marker |
| Chapter or page title | CLI Commands Reference; Slash Commands Reference; Profile Commands Reference; Environment Variables; CLI Interface; TUI; Security (approvals CLI); Updating & Uninstalling; Quickstart; Hooks / Photon (supplements) |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/cli-commands |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/slash-commands |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/profile-commands |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/environment-variables |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/cli |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/tui |
| Source URL | https://hermes-agent.nousresearch.com/docs/getting-started/updating (update/uninstall flags absent from the reference) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/security (hermes approvals suggest) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/messaging/photon (hermes photon — absent from the CLI reference entirely) |
| Documentation category | Reference / Using Hermes / Getting Started |
| Capture date | 2026-08-12 |
| Capture method | Research-agent dossier (`source-analysis/hermes/hermes-cli-capture.md`); BOTH reference pages read in full (no grep shortcuts — prior captures' CLI tables were grep subsets); reviewer re-verified the -z/usage-file quotes, the --accept-hooks absence from the Global options table, the gateway exit-75 contract, send exit codes, the COMMAND_REGISTRY statement, admin-gating default, Slack-thread rule, and prefix-resolution rule verbatim against live pages on 2026-08-12; cross-checked against six sibling skills' previously verified CLI fragments (consistent — the reference page's kanban/hooks sections are subsets of the feature pages' fuller CLI blocks, matching what those captures reported) |

## Captured Sections

- CLI Commands Reference (full read): global entrypoint syntax, 13-flag
  global options table, ~60-family top-level command table, per-family
  sections with usage/options/examples, maintenance recap.
- Slash Commands Reference (full read): shared COMMAND_REGISTRY,
  admin/user permission gating, interactive-CLI registry (sectioned),
  messaging registry, cross-surface availability notes, destructive-
  command confirmation modal, quick commands, model aliases, prefix/alias
  resolution.
- Profile Commands Reference: full `hermes profile` tree incl.
  distribution install/update/info and `distribution.yaml` schema;
  `hermes -p`; `hermes completion` (profile-name-aware).
- Environment Variables: CLI-relevant vars with flag equivalences;
  explicit "no env vars for" statements (compression, fallback, routing).
- CLI/TUI guides: keybindings, `!` shell mode (CLI-only), quiet mode,
  background sessions, TUI launch precedence, TUI-owned slash commands.
- Supplements: update `--branch/--force/--force-venv`; `hermes approvals
  suggest`; `--accept-hooks`; `hermes photon`.

## Documented incompleteness of the canonical reference (verified)

- `hermes photon` family absent from the CLI reference entirely (only on
  the Photon messaging guide, prose-only).
- `--accept-hooks` absent from the reference's Global options table
  (hooks feature page + env-vars page only).
- `hermes update --branch/--force/--force-venv` absent from the
  reference's update options table (updating guide only; `--force` and
  `--force-venv` are DISTINCT Windows escape hatches).
- `hermes approvals suggest` flags documented only on the Security page.
- Feature pages (kanban, hooks) carry fuller CLI blocks than the
  reference's own sections.

## Source Boundaries

This skill owns the command SURFACE (names, flags, aliases, surfaces,
exit behavior). Subsystem semantics belong to the owning skill:
`hermes-configuration` (config/auth/model/fallback/moa/portal/migrate),
`hermes-managed-scope` (secrets, egress), `hermes-kanban`,
`hermes-skills` (skills/bundles/curator), `hermes-hooks`,
`hermes-sessions` (sessions/checkpoints — ownership confirmed by
reviewer).

## Known Open Items

- Exit codes undocumented for all but `send`/`update`/gateway-75.
- `hermes approvals`: completeness beyond `suggest` unconfirmed.
- `hermes whatsapp`/`whatsapp-cloud`: interactive-only assumed (no flags
  documented); no non-interactive pairing path stated.
- Plugin-registered slash commands make the registry non-exhaustive at
  runtime (`/help` is the only enumeration).
- Custom cron provider plugin shape referenced but undocumented.
- Taxonomy gaps (no owning `hermes-*` skill): mcp, memory, plugins, cron
  command-family semantics — consistent with gaps flagged by prior
  captures (cron, plugins, delegation).
- FAQ "Profiles section" not separately read (profile-commands page
  treated as exhaustive).
