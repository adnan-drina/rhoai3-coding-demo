# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | no version marker on doc pages; config schema versions v12/v17 referenced in migration notes |
| Chapter or page title | Configuration; Configuring Models; Profiles; Fallback Providers; AI Providers |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/configuration |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/profiles |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers |
| Source URL | https://hermes-agent.nousresearch.com/docs/integrations/providers |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/slash-commands (alias schema subsection only; rest is `hermes-cli` territory) |
| Documentation category | Using Hermes / Features / Integrations / Reference |
| Capture date | 2026-08-12 |
| Capture method | Two independent research-agent dossiers (`source-analysis/hermes/hermes-configuration-capture.md` + `-independent.md`); shared surface corroborated identical; reviewer re-verified key quotes and all deltas verbatim against live pages on 2026-08-12; `context_length`/`max_tokens` gap resolved from the AI Providers page |

## Captured Sections

- Configuration: directory structure, `hermes config` subcommands,
  precedence, env-var substitution, provider timeouts, context compression
  (full `compression:` + `auxiliary.compression:` reference), context
  engine, auxiliary models, reasoning effort.
- Configuring Models: `model:` schema (sentinel → 4-key mapping), dashboard
  write shapes, per-provider options (`extra_headers`, `discover_models`),
  aliases and precedence, `/model` variants, take-effect timing.
- Profiles: definition, lifecycle, `-p`/aliases, profiles-vs-sandboxing,
  `HERMES_HOME` vs `HOME`, `terminal.home_mode`, distributions.
- Fallback Providers: `fallback_providers` vs legacy `fallback_model`,
  entry requirements, trigger conditions, turn-scoped semantics,
  auxiliary-task fallback, prompt-cache reset.
- AI Providers: `model.context_length` (64K minimum, multi-source
  resolution chain, 128K fallback default), `model.max_tokens` (output
  cap per response, distinct from context length), optional `api_mode`
  override on `fallback_providers:` entries, legacy `custom_providers:`
  field-name mapping.
- Slash Commands (partial): custom model alias schema — full form with
  `base_url`, case-insensitivity, user aliases shadow built-in short names.
- `api_mode` enum (`chat_completions`/`codex_responses`/
  `anthropic_messages`) confirmed as a direct quote via the Configuration
  page's Delegation section; auto-detected from `base_url` when empty.

## Source Boundaries

This skill captures: config file locations and precedence, main model
configuration (`provider`, `default`, `base_url`, `api_mode`,
`context_length`, `max_tokens`), auxiliary model wiring, compression
settings, per-provider options, fallback chains, and profiles.

Out of scope: Managed Scope pins and secrets (`hermes-managed-scope`),
hooks (`hermes-hooks`), skills governance keys (`hermes-skills`), kanban
workflow behavior (`hermes-kanban`), full CLI reference (`hermes-cli`),
terminal backend configuration and memory configuration (unassigned — flag
to the maintainer if needed).

## Known Open Items

- Subagent fallback inheritance: the pinned Fallback Providers page says
  subagents inherit the parent fallback chain; an unfetched developer-guide
  search snippet appeared to say otherwise. Pinned user-guide page treated
  as authoritative; resolve when researching developer-guide pages.
- `auxiliary.compression.max_concurrency` has no documented hard default.
