---
name: hermes-configuration
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when designing or reviewing Hermes Agent configuration for stage 080:
  config.yaml locations and precedence, main and auxiliary model wiring,
  context_length and max_tokens, compression settings, provider options,
  fallback chains, and profiles. Do NOT use for admin-tier pins or secrets
  (use hermes-managed-scope), event hooks (use hermes-hooks), memory config
  (unassigned — flag it), or the scaffold's in-workspace skill content under
  stages/080-*/scaffold-repo/ (governed by its own .hermes rules).
---

# Hermes Configuration

Use this skill for any change touching Hermes Agent configuration in stage
080 harness assets: model wiring, compression, providers, fallbacks, and
profiles.

## Source Grounding

Read `references/source-capture.md` for the capture provenance and
`references/official-doc-extraction.md` for the full validated extraction
(normative quotes, complete key tables, verbatim official examples).
Official Hermes Agent documentation (Nous Research) is the product
authority; every configuration claim in a PR must cite its section.

## Key Concepts

### Precedence

Settings resolve highest-priority first: **CLI arguments >
`~/.hermes/config.yaml` > `~/.hermes/.env` > built-in defaults**. Rule of
thumb (official): secrets (API keys, bot tokens, passwords) go in `.env`;
everything else — model, compression, toolsets — goes in `config.yaml`.
Admin-tier Managed Scope pins sit above all of this on a separate page —
defer to `hermes-managed-scope`, do not restate its rules here.

### The `model:` block

A fresh install has the sentinel `model: ""`; `hermes setup` / `hermes
model` upgrades it to a mapping:

```yaml
model:
  provider: openrouter
  default: anthropic/claude-opus-4.7
  base_url: ''
  api_mode: chat_completions  # chat_completions | codex_responses | anthropic_messages
  # context_length: 64000     # explicit override; otherwise auto-detected
  # max_tokens: 8192          # output cap per single response
```

`api_mode` is auto-detected from `base_url` when left empty (e.g. paths
ending in `/anthropic` → `anthropic_messages`); set it explicitly when the
heuristic can't classify the endpoint. The same three-value enum applies to
`delegation.api_mode` and to optional `api_mode` overrides on
`fallback_providers:` entries.

- `context_length` resolves through a multi-source chain: config override →
  custom provider per-model settings → persistent cache → endpoint
  `/models` query → provider metadata → registry → fallback default (128K).
  Hermes requires **at least 64,000 tokens** of context for agent use with
  tools; smaller windows are rejected at startup.
- `max_tokens` is the **output cap** — the maximum tokens the model may
  generate in a single response. It has nothing to do with conversation
  history length (that is `context_length`). Server-side defaults can be
  low (e.g. SGLang: 128) — set `model.max_tokens` or the server's
  `--default-max-tokens` when responses truncate.

### Universal provider/model/base_url pattern

Every auxiliary task block, `auxiliary.compression:`, and
`fallback_providers:` entries share the same three knobs: `provider`
(default `"auto"`), `model`, and optional `base_url` (overrides provider).
`provider: "main"` ("use whatever my main agent uses") is valid ONLY in
those places — never as top-level `model.provider`.

### Compression is two blocks

`compression:` holds thresholds and timers (`threshold: 0.50` ratio
default, `threshold_tokens: null` absolute cap — fires at the lower of the
two, clamped to the model's context length). `auxiliary.compression:`
selects which model/provider does the summarizing. Never conflate them.
All compression settings live in `config.yaml` — there are no environment
variables for them, and none for `fallback_providers` either (deliberate,
per the docs).

### Profiles

A profile is a complete separate Hermes home (`config.yaml`, `.env`,
`SOUL.md`, memories, sessions, skills, cron, state db) selected via
`HERMES_HOME`. A profile is NOT a sandbox: on the local backend the agent
keeps your user account's filesystem access, and `SOUL.md` does not enforce
boundaries. Host profiles share OS-user CLI credentials by default; set
`terminal.home_mode: profile` for strict per-profile CLI identity.

## Workflow

1. Classify the value: secret → `.env`; setting → `config.yaml` (official
   rule of thumb).
2. Open `references/official-doc-extraction.md` and find the exact key,
   type, and default before writing it; keys not in the extraction get
   verified against the live official page first.
3. Wire main models with the full `model:` mapping (never a bare string);
   set `context_length` explicitly for custom/self-hosted endpoints and
   `max_tokens` when the server's output default is low.
4. Wire auxiliary tasks with the universal pattern; leave
   `provider: "auto"` unless there is a concrete cost/latency reason.
5. Before pointing `auxiliary.compression` at a cheaper model, verify its
   context window is ≥ the main model's — otherwise summarization fails
   and middle turns drop silently (official warning).
6. One agent process per profile, always; pass `--description` at
   `hermes profile create` time for kanban-routed workers; set
   `terminal.cwd` explicitly rather than relying on launch-directory
   inference.
7. Cite the official section in the PR (stage 080 official-first rule).

## Validation

```shell
hermes config get model --json   # resolved main-model config
hermes status                    # what the CLI will actually use now
hermes config get <key>          # any resolved value vs documented default
hermes config check              # missing options after an update
hermes profile show <name>       # per-profile effective state
hermes fallback                  # effective fallback chain (interactive)
```

## Pitfalls

- `provider: main` under top-level `model:` is invalid — auxiliary,
  compression, and fallback entries only.
- `fallback_providers` entries missing `provider` or `model` are silently
  ignored; `fallback_providers` (list) beats legacy `fallback_model` when
  both are set.
- Mid-session model switches and fallback activation both reset the prompt
  cache — the next request re-reads the whole history at full input price.
- `terminal.cwd: "."` means the launch directory, NOT the profile
  directory.
- Two agent processes on one profile compound each other's memory writes —
  never share a Hermes home.
- `compression.summary_model`/`summary_provider` and top-level
  `custom_providers:` are legacy, auto-migrated shapes — don't author new
  configs with them.
- Undefined `${VAR}` references stay verbatim with a warning (no silent
  empty expansion); only `${env:NAME}` SecretRef syntax resolves inline.
- Model alias names are case-insensitive and user aliases shadow built-in
  short names (`sonnet`, `opus`, …) — avoid alias names that collide with
  built-ins unless shadowing is intended; `model_aliases:` (top-level) wins
  over `model.aliases:` on name collision.

## Related Skills

- `hermes-managed-scope` — admin pins, secrets, precedence above user seats.
- `hermes-cli` — full command reference behind the validation commands.
- `hermes-kanban` — behavior of kanban-related auxiliary tasks.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
