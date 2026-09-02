# Official Doc Extraction — hermes-configuration

Validated research dossier (capture date 2026-08-12). Reviewer validation:
precedence, rule-of-thumb, compression-default, and profile-safety quotes
re-verified verbatim against live pages; §8 gap 1 resolved in the Addendum
at the end of this file. Original dossier:
`source-analysis/hermes/hermes-configuration-capture.md`.

---

# hermes-configuration — Source Capture Dossier

## Executive Summary (read first)

- **Captured**: config file locations/precedence, `hermes config` CLI, env-var substitution,
  full `compression:`/`auxiliary.compression:` reference, the universal `provider`/`model`/`base_url`
  auxiliary pattern, the `fallback_providers` chain (via one-hop follow from the Configuration page),
  and full `hermes profile` lifecycle/precedence semantics. All with verbatim quotes and section anchors.
- **Confidence**: High for what's captured — every normative statement below is a direct quote from
  the three pinned pages plus one one-hop follow (`Fallback Providers`, explicitly cross-referenced
  by name from the Configuration page). Low for `model.context_length` / `max_tokens` specifically —
  see next line.
- **Biggest gap**: The pinned pages do **not** document `model.context_length` or `max_tokens` as a
  schema (type/default/description). The only textual evidence is one passing mention that editing
  `model.context_length` on a running gateway hot-reloads — no definition of the key itself, its
  default, or where it's set appears on any of the three pinned pages. This must be sourced from the
  "AI Providers" page (out of this skill's boundary) or flagged as an open question.
- **Contradicts the placeholder?** No factual contradiction. The placeholder's framing ("config.yaml
  locations and precedence, provider and model wiring, compression/memory settings, profiles") matches
  what the docs actually cover. One nuance: precedence is documented as CLI args > `config.yaml` >
  `.env` > built-in defaults — the placeholder's `hermes-configuration` vs `hermes-managed-scope`
  boundary line ("managed scope > user seat") is correct per `hermes-managed-scope`'s own scope but is
  **not itself documented on any page pinned to this skill** — that precedence claim's citation lives
  outside this capture's boundary (Managed Scope docs) and should be verified there, not assumed here.
- **Suggested next skill**: `hermes-managed-scope` (gates config precedence above the level captured
  here) or `hermes-cli` (documents `hermes config get/set` verification commands referenced throughout
  this capture).

---

## 1. Capture Header

| Field | Value |
|---|---|
| Product | Hermes Agent (Nous Research) |
| Version marker | No version marker on any of the three pinned pages. The Configuration page references internal **config schema** versions in passing ("config version 17", "config v12") for migration behavior — these are config-file schema versions, not product/doc versions. |
| Capture date | 2026-08-12 |
| Capture method | `WebFetch` tool against live URLs |

### URLs actually read

| URL | Status | Role |
|---|---|---|
| https://hermes-agent.nousresearch.com/docs/user-guide/configuration | 200 OK — full content retrieved (1888 lines) | Pinned |
| https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models | 200 OK — full content retrieved | Pinned |
| https://hermes-agent.nousresearch.com/docs/user-guide/profiles | 200 OK — full content retrieved | Pinned |
| https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers | 200 OK — full content retrieved | One-hop follow: the Configuration page's Context Compression section explicitly says "The primary fallback chain uses a top-level `fallback_providers:` list — see Fallback Providers", and the configuring-models page cross-references `fallback_providers:`/legacy `fallback_model:` as valid `auxiliary`/`compression`/primary-fallback provider values. In-boundary (provider/model configuration) and same domain. |

### Pinned URLs that 404'd or redirected

None. All three pinned URLs resolved on first fetch.

### Links noticed but NOT followed (out of scope or beyond one hop)

- "AI Providers" page (linked by name, not URL, from both the Configuration and configuring-models
  pages) — covers main-model provider credential setup; explicitly out of this skill's captured scope
  (provider *auth*, not provider *config wiring*), and not reachable via a resolvable href in the
  fetched markdown (the fetch tool renders link text without preserving `href` attributes for this
  page, so I could not confirm the exact URL without a second lookup — recorded as a gap, not guessed).
- "Custom model aliases" full reference page (linked by name from configuring-models's Alternative
  methods section) — same href-loss issue; in-boundary content (model aliasing) but not captured
  verbatim here. Recorded as a gap.
- `Managed Scope` page (linked by name from the Configuration page's "Org deployments" note) —
  explicitly out of boundary per assignment (belongs to `hermes-managed-scope`). Not followed.
- Developer-guide page `docs/developer-guide/provider-runtime` — surfaced only via an external web
  search while chasing the Fallback Providers URL, **not** via an in-page link from a pinned page.
  Per the "one level deep from pinned pages only" method constraint, this was deliberately **not**
  fetched or cited as a source for this dossier, even though it appears to document fallback
  implementation details. Recorded as a gap/lead for whoever researches `hermes-cli` or a future
  developer-facing skill.

---

## 2. Page Maps

### Page: `user-guide/configuration`

Very large single reference page. Only sections within this skill's boundary (config file
locations/precedence, provider/model config, compression thresholds, profiles are on their own
page) are captured in detail; the rest of the page (terminal backends, TTS, STT, memory, tool-output
truncation, security, checkpoints, etc.) is **out of boundary** for `hermes-configuration` per the
source-capture boundary notes and is not detailed here beyond heading names, for completeness of the
page map.

In-boundary sections, in document order:

| Heading | Covers |
|---|---|
| Directory Structure | The `~/.hermes/` layout: `config.yaml`, `.env`, `auth.json`, `SOUL.md`, `memories/`, `skills/`, `cron/`, `sessions/`, `logs/` |
| Managing Configuration | `hermes config` subcommands: view/edit/get/set/unset/check/migrate |
| Configuration Precedence | The 4-level resolution order (CLI args > config.yaml > .env > built-in defaults) and the secrets-vs-settings rule of thumb |
| Runtime Limits | `runtime.nofile_soft_limit` — file-descriptor soft limit for long-running server surfaces (out of this skill's provider/model/compression/profile scope but sits directly under top-level config, noted for completeness) |
| Environment Variable Substitution | `${VAR_NAME}` and `${env:VAR_NAME}` syntax in `config.yaml`, undefined-variable behavior, and unresolved SecretRef prefixes (`${file:...}` etc.) |
| — Provider Timeouts (h3 under Env Var Substitution) | `providers.<name>.request_timeout_seconds`, `providers.<name>.models.<model>.timeout_seconds`, `stale_timeout_seconds` — provider-level timeout config, in-boundary as provider configuration |
| Context Compression | Full `compression:` block reference, `auxiliary.compression:` model/provider block, per-key behavior descriptions, common setups, the 3-knob interaction table, and the summary-model context-length caveat |
| Context Engine | `context.engine` (`compressor` built-in vs plugin engines like `lcm`) |
| Context Pressure Warnings | User-facing progress-bar/notification behavior tied to the compression threshold — no config keys, informational only |
| Auxiliary Models | Full `auxiliary.*` reference: universal provider/model/base_url pattern, per-task tables, reasoning_effort per task, fallback_chain per task, stream-only endpoints |
| Reasoning Effort | `agent.reasoning_effort` and `agent.reasoning_overrides` — global/per-model "thinking" level knobs. Borderline in-boundary: it's main-model behavior wiring but not explicitly named in the skill's pinned scope (context_length/max_tokens/compression); included because it is a config key that shapes model behavior and the skill description says "provider and model wiring" |
| Skill Settings | `skills.config.<skillname>.*` — **out of boundary** (skill authoring, not model/provider config); noted only for page-map completeness |

Out-of-boundary sections present on the same page (Terminal Backend Configuration and all its
subsections, Memory Configuration, Context File Truncation, File Read Safety, Tool Output Truncation
Limits, Global Toolset Disable, Git Worktree Isolation, Gateway Turn Lease Timeout, Session Stall
Watchdog, Gateway Agent Cache, Iteration Budget, Verify-on-Stop, Standing Goals, API Timeouts,
Credential Pool Strategies, Prompt caching, Tool-Use Enforcement, Tool-Loop Guardrails, TTS
Configuration, Display Settings, Privacy, Speech-to-Text, Voice Mode, Streaming, Group Chat Session
Isolation, Unauthorized DM Behavior, Quick Commands, Human Delay, Code Execution, Web Search
Backends, Browser, Timezone, Discord, Security, Website Blocklist, Smart Approvals, Checkpoints,
Delegation, Clarify, Context Files, Working Directory, Network, Onboarding, Dashboard) — not
extracted; belong to other skills or are out of scope entirely for `hermes-*` skill coverage.

### Page: `user-guide/configuring-models`

| Heading | Covers |
|---|---|
| (intro) | Main model vs. 11 auxiliary model slots; `hermes setup --portal` fast path |
| `model:` schema — empty string vs. mapping | New-install sentinel `model: ""` vs. the upgraded mapping form with `provider`/`default`/`base_url`/`api_mode` |
| The Models page | Dashboard UI: Model Settings panel + Usage analytics |
| Setting the main model | Picker UX, what gets written, scope (new sessions only) |
| — Mid-session switches and context warnings | Preflight compression estimate on `/model` switch; prompt-cache reset behavior |
| Setting auxiliary models | Dashboard "Show auxiliary" UI, the 11 task slots, `auto` semantics and per-task override |
| — Common override patterns | Table of when to override which auxiliary task |
| — Per-task override / Reset all to auto | Dashboard controls |
| The "Use as" shortcut | Dashboard quick-assign UI |
| What gets written to config.yaml | Verbatim `model:` and `auxiliary.*` YAML shapes as saved by the dashboard |
| Per-provider request options | `providers.<name>.extra_headers` and `providers.<name>.discover_models` |
| When does it take effect? | CLI/gateway/dashboard-chat-tab timing semantics for model changes |
| Troubleshooting | Picker/auxiliary/provider-switch troubleshooting notes |
| Alternative methods | CLI slash command (`/model ... --global`, `--once`), custom aliases (`model_aliases:` vs `model.aliases.*`), `hermes model` subcommand, direct config edit, REST API |

### Page: `user-guide/profiles`

| Heading | Covers |
|---|---|
| What are profiles? | Profile = separate Hermes home directory; explicit warning against pointing two agents at one profile |
| Quick start | `hermes profile create`, resulting command alias |
| Creating a profile | Blank / `--clone` / `--clone-all` / `--clone-from` variants |
| Using profiles | Command aliases, `-p` flag, `hermes profile use` sticky default, active-profile display |
| Profiles vs workspaces vs sandboxing | Explicit distinction: profile ≠ working directory (`terminal.cwd`) ≠ sandbox |
| Running gateways | Per-profile gateway processes, bot tokens, token locks, persistent services |
| Configuring profiles | Per-profile `config.yaml`/`.env`/`SOUL.md`; dashboard profile switcher |
| Updating | `hermes update` syncs bundled skills to all profiles; user-modified skills never overwritten |
| Managing profiles | `list`/`show`/`rename`/`export`/`import` |
| Deleting a profile | `hermes profile delete`, cannot delete default profile |
| Tab completion | Shell completion setup |
| How it works | `HERMES_HOME` env var mechanics, distinction from OS `HOME`, `terminal.home_mode` |
| Sharing profiles as distributions | `hermes profile install`/`update` from a git repo |

### Page: `user-guide/features/fallback-providers` (one-hop follow)

| Heading | Covers |
|---|---|
| (intro) | Three resilience layers: credential pools, primary model fallback, auxiliary task fallback |
| Primary Model Fallback / Configuration | `hermes fallback` CLI, top-level `fallback_providers:` list, `fallback_providers` vs legacy `fallback_model` precedence |
| Supported Providers | Full provider-value/env-var table for fallback entries |
| Custom Endpoint Fallback | `provider: custom` with `base_url`/`key_env` |
| When Fallback Triggers | HTTP-status-driven trigger conditions |
| Examples | Verbatim YAML examples pairing `model:` + `fallback_providers:` |
| Where Fallback Works | Table: CLI/gateway/subagents/cron/auxiliary support |
| Auxiliary Task Fallback | Per-task independent provider resolution; auto-detection chain order |
| Configuring Auxiliary Providers | Verbatim `auxiliary.*` YAML block |
| Provider Options for Auxiliary Tasks | `auto`/`openrouter`/`nous`/`codex`/`main`/`anthropic` values table |
| Direct Endpoint Override | `base_url` precedence over `provider` |
| Auxiliary Capacity-Error Fallback | 4-step fallback ladder for explicit (non-auto) auxiliary providers |
| Context Compression Fallback | Compression-specific fallback behavior; degrade-without-summary on total failure |
| Delegation Provider Override / Cron Job Providers | Subagent and cron provider/model override keys |
| Summary | Table mapping every feature to its config location |

---

## 3. Normative Statements

| Exact quote | Page + section | Why it matters for stage 080 |
|---|---|---|
| "Settings are resolved in this order (highest priority first): 1. CLI arguments... 2. `~/.hermes/config.yaml`... 3. `~/.hermes/.env`... 4. Built-in defaults" | configuration / Configuration Precedence | This is the exact precedence chain a stage 080 skill review must cite before claiming "config.yaml wins" or "env wins" — CLI args beat both. |
| "Secrets (API keys, bot tokens, passwords) go in `.env`. Everything else (model, terminal backend, compression settings, memory limits, toolsets) goes in `config.yaml`. When both are set, `config.yaml` wins for non-secret settings." | configuration / Configuration Precedence (Rule of Thumb) | Directly defines the config.yaml-vs-.env split the skill's "When to Use" section already assumes; confirms compression settings are non-secret and belong in config.yaml. |
| "An administrator can pin specific config and secret values that a standard user cannot override, via a system-level managed directory. See Managed Scope." | configuration / Configuration Precedence (Org deployments) | Confirms the managed-scope precedence layer exists and is documented on a **separate** page — this skill must not restate managed-scope precedence rules as its own fact; defer to `hermes-managed-scope`. |
| "You can reference environment variables in `config.yaml` using `${VAR_NAME}` syntax... If a referenced variable is not set, the placeholder is kept verbatim (`${UNDEFINED_VAR}` stays as-is) and a warning is logged. Bare `$VAR` is not expanded." | configuration / Environment Variable Substitution | Precise, quotable behavior for undefined vars — prevents a stage 080 skill from claiming silent failure or expansion-to-empty. |
| "Cursor-style SecretRef syntax is also accepted: `${env:VAR_NAME}` resolves exactly like `${VAR_NAME}`... Other SecretRef sources (`${file:...}`, `${vault:...}`, `${bitwarden:...}`) are not resolved inline... reference them as `${env:NAME}` instead; unknown prefixes warn once and stay verbatim." | configuration / Environment Variable Substitution | Important for anyone porting Cursor/Claude MCP config snippets into a Hermes `config.yaml` — only `env:` resolves inline. |
| "All compression settings live in `config.yaml` (no environment variables)." | configuration / Context Compression | Rules out `HERMES_COMPRESSION_*`-style env overrides as a valid claim in any PR touching compression config. |
| "Older configs with `compression.summary_model`, `compression.summary_provider`, and `compression.summary_base_url` are automatically migrated to `auxiliary.compression.*` on first load (config version 17). No manual action needed." | configuration / Context Compression (Legacy config migration) | Anyone reviewing an old scaffold config referencing `compression.summary_model` must know it is legacy and auto-migrated, not a currently-documented key. |
| "`threshold_tokens` sets an optional absolute token cap for the compression trigger. When set, compression fires at the lower of the ratio-based `threshold` and this absolute count... The cap is clamped to the model's context length, so setting it higher than the model supports is safe... Default `null` (disabled — ratio-based threshold only)." | configuration / Context Compression | Exact default + precedence-with-ratio-threshold behavior for `compression.threshold_tokens`. |
| "As of recent releases, editing `model.context_length` or any `compression.*` key in `config.yaml` on a running gateway takes effect on the next message — no gateway restart, no `/reset`, no session rotation required." | configuration / Context Compression (Gateway hot-reload note) | The **only** textual evidence on any pinned page that `model.context_length` exists as a key; no schema/default is given anywhere else. Flagged as a gap (see §8). |
| "Summary model context length requirement: The summary model must have a context window at least as large as your main agent model's... if that model's context window is smaller than the main model's, the summarization call will fail with a context length error. When this happens, the middle turns are dropped without a summary, losing conversation context silently." | configuration / Context Compression | Operational warning that must be cited if a stage 080 review recommends pointing `auxiliary.compression` at a cheaper/smaller-context model. |
| "`\"main\"` provider option means \"use whatever provider my main agent uses\" — it's only valid inside `auxiliary:`, `compression:`, and primary fallback entries (`fallback_providers:` or legacy `fallback_model:`). It is not a valid value for your top-level `model.provider` setting." | configuration / Auxiliary Models | A precise, easy-to-get-wrong constraint: `provider: main` cannot appear under top-level `model:`. |
| "On a brand-new install the bundled default config has `model: \"\"` (an empty string sentinel meaning \"not configured yet\"). The first time you run `hermes setup` or `hermes model`, that key is upgraded in-place to a mapping with `provider`, `default`, `base_url`, and `api_mode` sub-keys." | configuring-models / `model:` schema | Defines the exact `model:` schema shape (`provider`, `default`, `base_url`, `api_mode`) — the four sub-keys a stage 080 harness config must set. |
| "Pick a model, hit Switch, and Hermes writes it to `~/.hermes/config.yaml` under the `model` section. This applies to new sessions only — any chat tab you already have open keeps running whatever model it started with." | configuring-models / Setting the main model | Scope-of-effect claim: model.yaml changes are not retroactive to open sessions. |
| "Mid-session switches reset the prompt cache: Prompt caches are keyed to the model serving the request, so any mid-conversation model change... means the next message re-reads the entire conversation at full input-token price instead of the cached (~75–90% discounted) rate." | configuring-models / Mid-session switches and context warnings | Cost-relevant caveat for any stage 080 doc recommending frequent `/model` switching. |
| "`extra_headers` — a mapping of extra HTTP headers attached to every LLM request routed to that provider's base URL. They are applied last, after URL/profile defaults and user header overrides, so they survive credential swaps and client rebuilds... Header values routinely carry credentials — Hermes never logs them. `extra_headers` applies to OpenAI-compatible routes; the `anthropic_messages` and `bedrock_converse` API modes do not use it." | configuring-models / Per-provider request options | Exact scope limitation (OpenAI-compatible only) that a MaaS-gateway wiring guide must respect. |
| "`discover_models` — set to `false` (default `true`) to skip querying the endpoint's `/models` listing and use only the `models` you configured on the entry." | configuring-models / Per-provider request options | Documents the default (`true`) and the override key precisely. |
| "Older configs used a top-level `custom_providers:` list (with `base_url` instead of `api`). It still works and is auto-migrated to the `providers:` dict on `hermes update` (config v12)." | configuring-models / Per-provider request options (Legacy format) | Confirms `custom_providers:` is legacy but still functional — relevant if a scaffold or PR touches an older-style provider block. |
| "Entries declared in `model_aliases:` take precedence over `model.aliases:` entries with the same name." | configuring-models / Custom aliases | Exact precedence rule between the two alias syntaxes. |
| "`hermes config get model --json` and `hermes status`" [to inspect what the CLI will actually use right now] | configuring-models / `hermes model` subcommand | Verification commands — candidates for this skill's "Validation" section. |
| "A profile is a separate Hermes home directory. Each profile gets its own directory containing its own `config.yaml`, `.env`, `SOUL.md`, memories, sessions, skills, cron jobs, and state database." | profiles / What are profiles? | Core definition — precise list of what is profile-scoped. |
| "Never point two agent processes at the same profile (the same Hermes home). Both write memory automatically, and each loads the other's writes into its system prompt at session start — so two writers on one home compound each other's state until it stops being anything you configured." | profiles / What are profiles? (Give every agent its own profile) | Hard safety rule for any stage 080 multi-agent harness design that considers sharing a Hermes home across worker processes. |
| "A profile does not stop it from accessing folders outside the profile directory." / "On the default `local` terminal backend, the agent still has the same filesystem access as your user account." | profiles / Profiles vs workspaces vs sandboxing | Directly refutes any assumption that profiles = sandboxing; critical for a security-sensitive stage 080 review. |
| "Using `cwd: \".\"` on the local backend means \"the directory Hermes was launched from\", not \"the profile directory\"." | profiles / Profiles vs workspaces vs sandboxing | Precise, easy-to-misread semantics of `terminal.cwd: "."`. |
| "`SOUL.md` can guide the model, but it does not enforce a workspace boundary." | profiles / Profiles vs workspaces vs sandboxing | Reinforces that persona files are not an access-control mechanism. |
| "Asking the model \"what directory are you in?\" is not a reliable isolation test. If you need a predictable starting directory for tools, set `terminal.cwd` explicitly." | profiles / Profiles vs workspaces vs sandboxing | Directly actionable validation guidance — self-report is not a valid check. |
| "`HERMES_HOME` is the profile boundary. It controls Hermes config, `.env`, memory, sessions, skills, logs, cron jobs, gateway state, and other Hermes data." / "`HOME` is the operating-system/user home that external CLIs expect. On host installs, Hermes keeps it as the real user home by default so tools like `git`, `ssh`, `gh`, `az`, `npm`, Claude Code, and Codex find the same credentials they use in your normal shell." | profiles / How it works | The precise HERMES_HOME-vs-HOME distinction, directly relevant to any stage 080 harness that runs multiple Hermes profiles expecting isolated tool credentials. |
| "The tradeoff is that host profiles share normal user-level CLI state by default. If you need separate CLI identities per profile, set `terminal.home_mode: profile` in that profile's `config.yaml`." | profiles / How it works | Actionable remediation for the shared-credential tradeoff. |
| "You cannot delete the default profile (`~/.hermes`). To remove everything, use `hermes uninstall`." | profiles / Deleting a profile | Hard constraint on profile lifecycle management. |
| "`hermes update` pulls code once (shared) and syncs new bundled skills to all profiles automatically... User-modified skills are never overwritten." | profiles / Updating | Precise update-safety guarantee for skill content across profiles. |
| "`fallback_providers` (plural, list) is the current config shape and supports multiple fallbacks tried in order. `fallback_model` (singular) is the legacy single-fallback key... When both are set, `fallback_providers` takes priority." | fallback-providers / Primary Model Fallback (Configuration) | Exact precedence between the two fallback key shapes. |
| "Each entry requires both `provider` and `model`. Entries missing either field are ignored." | fallback-providers / Configuration | Validation rule for `fallback_providers:` list entries. |
| "There are no environment variables for the primary fallback chain — configure it exclusively through `config.yaml` or `hermes fallback`. This is intentional: fallback configuration is a deliberate choice, not something a stale shell export should override." | fallback-providers / Configuration (tip) | Explicit, deliberate design constraint — rules out any `HERMES_FALLBACK_*` env var claim. |
| "Fallback is turn-scoped: each new user message starts with the primary model restored. If the primary fails mid-turn, fallback activates for that turn only... Within a single turn, fallback activates at most once." | fallback-providers / Per-Turn, Not Per-Session | Precise scope-of-activation semantics, easy to misstate as session-scoped. |
| "Prompt caches are keyed to the model (and on most providers, the account) serving the request. When fallback fires, the new provider:model has no cached prefix for your conversation, so the next request re-reads the entire history at full input-token price." | fallback-providers / Fallback resets the prompt cache | Cost caveat parallel to the model-switch prompt-cache caveat on the configuring-models page. |
| "Subagent delegation (`tools/delegate_tool.py`): subagents inherit the parent's provider but not the fallback config" — actually corrected by the pinned fallback-providers page: "Subagent delegation ✔ (subagents inherit the parent fallback chain)" | fallback-providers / Where Fallback Works | **Caution**: this exact contradiction was seen between a non-pinned developer-guide search snippet (subagents do NOT inherit fallback) and the pinned fallback-providers page (subagents DO inherit fallback). Only the pinned page's claim is authoritative for this skill; the developer-guide snippet is out of boundary and was not read as a full page — flagged, not resolved, in §8. |
| "When you have multiple API keys or OAuth tokens for the same provider, configure the rotation strategy... Options: `fill_first` (default), `round_robin`, `least_used`, `random`." | configuration / Credential Pool Strategies | Out-of-boundary detail (belongs more to provider auth than this skill's scope) but captured because it's directly adjacent to fallback and referenced by the Fallback Providers page's "layer 1"; recorded for completeness, not asserted as in-scope. |

---

## 4. Reference Tables

### `compression:` block (config.yaml, top-level)

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `true` | Toggle compression on/off |
| `progress_notices` | bool | `false` | Opt-in: deliver routine compression progress notices to chat platforms |
| `threshold` | float (ratio) | `0.50` | Compress at this % of context limit |
| `threshold_tokens` | int or `null` | `null` | Absolute token cap (optional) — takes the lower of ratio vs. absolute; clamped to the model's context length |
| `target_ratio` | float | `0.20` | Fraction of threshold to preserve as recent tail |
| `protect_last_n` | int | `20` | Min recent messages to keep uncompressed |
| `protect_first_n` | int | `3` | Non-system head messages pinned across compactions (`0` = pin nothing) |
| `in_place` | bool | `true` | Compact on the same session id (no rotation) |
| `idle_compact_after_seconds` | int | `0` | Opt-in idle compaction (`0` = disabled) |
| `hygiene_hard_message_limit` | int | `5000` | Gateway-only pre-compression safety valve (message-count floor) |
| `hygiene_timeout_seconds` | int (seconds) | `30` | Max seconds of NO summary-model output before hygiene compression is cut off |
| `hygiene_total_ceiling_seconds` | int (seconds) | `600` | Absolute cap on the hygiene wait even while tokens are still streaming; clamped to at least `hygiene_timeout_seconds` |
| `hygiene_failure_cooldown_seconds` | int (seconds) | `300` | First rung of the per-session hygiene-failure backoff (escalates ×1/×3/×9, capped at 1h) |
| `context_timeout_seconds` | int (seconds) | `120` | Inactivity budget for in-agent `compress_context` (loop `/compress`/preflight); `0` disables |
| `context_total_ceiling_seconds` | int (seconds) | `600` | Absolute cap on the pre-commit in-agent compress_context wait; clamped to at least `context_timeout_seconds` |
| `proactive_prune_tokens` | int | `0` (off) | Opt-in tokens trigger for the no-LLM tool-result prune; docs suggest trying `48000` to enable |
| `proactive_prune_min_result_chars` | int | `8000` | Prune's summarize pass only touches tool results larger than this (clamped ≥ 200) |
| `proactive_prune_min_reclaim_tokens` | int | `4096` | Prune only commits when it reclaims at least this many tokens |

### `auxiliary.compression:` block (model/provider routing for the summarizer)

| Key | Type | Default | Description |
|---|---|---|---|
| `model` | string | `""` (empty = use main chat model) | e.g. `"google/gemini-3-flash-preview"` for cheaper/faster compression |
| `provider` | string | `"auto"` | `"auto"`, `"openrouter"`, `"nous"`, `"codex"`, `"main"`, etc. |
| `base_url` | string or `null` | `null` | Custom OpenAI-compatible endpoint (overrides provider) |
| `timeout` | int (seconds) | `120` | LLM API call timeout for the summarization call |
| `reasoning_effort` | string | not set (provider default) | `none`/`minimal`/`low`/`medium`/`high`/`xhigh`/`max`/`ultra` — per-task counterpart of `agent.reasoning_effort` |
| `fallback_chain` | list of `{provider, model, base_url?, api_key?, timeout?}` | not set | Task-specific fallback policy tried before the top-level `fallback_providers` chain |
| `max_concurrency` | int | undocumented (example shown as `2` in a comment, not stated as a hard default) | Cap simultaneous compression LLM calls so multiple sessions don't pile retries on a degraded provider |

### `model:` top-level schema (main model)

| Key | Type | Default | Description |
|---|---|---|---|
| `provider` | string | `undocumented` on pinned pages (sentinel empty string `""` before first setup) | Main model provider, e.g. `openrouter`, `anthropic`, `minimax-oauth`, `custom` |
| `default` | string | `undocumented` (empty before setup) | Model ID, e.g. `anthropic/claude-opus-4.7` |
| `base_url` | string | `''` (cleared on provider switch) | Custom endpoint override |
| `api_mode` | string | `chat_completions` (shown in dashboard-written example) | Wire protocol: `chat_completions`, `codex_responses`, or `anthropic_messages` (values inferred from the `delegation.api_mode` description on the same doc site's Configuration page, which lists the same three values explicitly) |
| `context_length` | `undocumented` — **not defined on any pinned page** | `undocumented` | Only mentioned once, in passing, re: gateway hot-reload behavior. No type, default, or set-location documented on pinned pages. **Gap** — see §8. |
| `aliases` | mapping (`model.aliases.<name>: "provider/model"`) | not set | Short-string alias form; `model_aliases:` (top-level, canonical) takes precedence over `model.aliases:` for same-named entries |

**`max_tokens`**: not found as a documented key anywhere on any of the three pinned pages (grep-verified against the full text of the Configuration page, 1888 lines). **Gap** — see §8.

### `providers.<name>:` per-provider options

| Key | Type | Default | Description |
|---|---|---|---|
| `api` | string (URL) | none | Provider base API endpoint (replaces legacy `base_url` key under `custom_providers:`) |
| `api_key` | string | none | Provider API key |
| `extra_headers` | mapping | not set | Extra HTTP headers attached to every LLM request; applied last; OpenAI-compatible routes only (not `anthropic_messages`/`bedrock_converse`) |
| `discover_models` | bool | `true` | `false` skips querying `/models`; uses only the configured `models` list |
| `models` | list of strings | not set | Explicit model list, used when `discover_models: false` |
| `request_timeout_seconds` | int (seconds) | legacy default `1800` (`HERMES_API_TIMEOUT`) if unset | Provider-wide request timeout |
| `stale_timeout_seconds` | int (seconds) | legacy default `90` (`HERMES_API_CALL_STALE_TIMEOUT`); auto-disabled for local endpoints when left implicit | Non-streaming stale-call detector timeout |
| `models.<model>.timeout_seconds` | int (seconds) | inherits provider-level | Per-model timeout override |
| `models.<model>.stale_timeout_seconds` | int (seconds) | inherits provider-level | Per-model stale-timeout override |

### `fallback_providers:` (top-level list)

| Key (per entry) | Type | Required? | Description |
|---|---|---|---|
| `provider` | string | Required | Any supported provider value (large table on the fallback-providers page — 30+ providers) |
| `model` | string | Required | Model ID for that provider |
| `base_url` | string | Optional | Custom endpoint (only meaningful with `provider: custom`) |
| `key_env` | string | Optional | Env var name containing the API key, for `provider: custom` |

Legacy equivalent: `fallback_model:` (singular dict, same two required fields). `fallback_providers` wins when both are set.

### `hermes profile create` flags

| Flag | Type | Default | Description |
|---|---|---|---|
| `--description "<text>"` | string | not set | Description used by the kanban orchestrator for routing; can also be set/auto-generated later via `hermes profile describe` |
| `--clone` | flag | off | Copies current profile's `config.yaml`, `.env`, `SOUL.md`, and skills into the new profile |
| `--clone-all` | flag | off | Copies everything including memories, skills, cron jobs, plugins (excludes session history/state.db/backups/state-snapshots/checkpoints) |
| `--clone-from <profile>` | string | not set | Selects the source profile directly; implies config/skills/SOUL clone; combine with `--clone-all` for a full copy |

### `terminal.home_mode` (profile-adjacent; referenced from profiles page)

| Value | Host installs | Containers | Description |
|---|---|---|---|
| `auto` (default) | Keep real OS-user `HOME` | Use `{HERMES_HOME}/home` | "Recommended default. Host CLIs keep working; container state persists." |
| `real` | Force real OS-user `HOME` | Force real OS-user `HOME` if visible | For when a parent process accidentally started with `HOME` pointed at a profile home |
| `profile` | Use `{HERMES_HOME}/home` when it exists | Use `{HERMES_HOME}/home` when it exists | Strict per-profile CLI config isolation; requires manually initializing `~/.ssh`, `~/.gitconfig`, etc. inside the profile home |

### Universal auxiliary-task config pattern (applies to every `auxiliary.<task>` block, `compression:`, and `fallback_providers`/`fallback_model` entries)

| Key | What it does | Default |
|---|---|---|
| `provider` | Which provider to use for auth and routing | `"auto"` |
| `model` | Which model to request | provider's default |
| `base_url` | Custom OpenAI-compatible endpoint (overrides provider) | not set |
| `reasoning_effort` (auxiliary blocks only) | Thinking level for that task's LLM calls: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra` | not set (provider default) |

---

## 5. Official Examples (verbatim)

### Main model as written by the dashboard (configuring-models / What gets written to config.yaml)

```yaml
model:
  provider: openrouter
  default: anthropic/claude-opus-4.7
  base_url: ''        # cleared on provider switch
  api_mode: chat_completions
```

### Auxiliary override example — vision on gemini-flash (configuring-models)

```yaml
auxiliary:
  vision:
    provider: openrouter
    model: google/gemini-2.5-flash
    base_url: ''
    api_key: ''
    timeout: 120
    extra_body: {}
    download_timeout: 30
```

### Auxiliary on auto / default (configuring-models)

```yaml
auxiliary:
  compression:
    provider: auto
    model: ''
    base_url: ''
    # ... other fields unchanged
```

### Task-specific fallback chain example (configuring-models)

```yaml
auxiliary:
  title_generation:
    provider: auto
    model: ''
    fallback_chain:
      - provider: openrouter
        model: inclusionai/ring-2.6-1t:free
```

### Per-provider `extra_headers` (configuring-models)

```yaml
providers:
  my-gateway:
    api: https://llm.internal.example.com/v1
    api_key: sk-...
    extra_headers:
      CF-Access-Client-Id: "xxxx.access"
      CF-Access-Client-Secret: "yyyy"
```

### Per-provider `discover_models: false` (configuring-models)

```yaml
providers:
  my-gateway:
    api: https://llm.internal.example.com/v1
    discover_models: false
    models:
      - my-finetune-v2
      - my-finetune-v1
```

### Custom model aliases — canonical form (configuring-models)

```yaml
# ~/.hermes/config.yaml
model_aliases:
  fav:
    model: claude-sonnet-4.6
    provider: anthropic
  grok:
    model: grok-4
    provider: x-ai
```

### Custom model aliases — short string form (configuring-models)

```bash
hermes config set model.aliases.fav anthropic/claude-opus-4.6
hermes config set model.aliases.grok x-ai/grok-4
```

### `/model` slash command variants (configuring-models)

```text
/model gpt-5.4 --provider openrouter             # session-only
/model gpt-5.4 --provider openrouter --global    # also persists to config.yaml
/model claude-opus-4.6 --once                    # next turn only, then auto-restores
```

### `compression:` full reference block (configuration / Context Compression)

```yaml
compression:
  enabled: true                                     # Toggle compression on/off
  progress_notices: false                           # Opt-in: deliver routine compression progress notices to chat platforms
  threshold: 0.50                                   # Compress at this % of context limit
  threshold_tokens: null                            # Absolute token cap (optional) — takes lower of ratio vs absolute
  target_ratio: 0.20                                # Fraction of threshold to preserve as recent tail
  protect_last_n: 20                                # Min recent messages to keep uncompressed
  protect_first_n: 3                                # Non-system head messages pinned across compactions (0 = pin nothing)
  in_place: true                                    # Compact on the same session id (no rotation)
  idle_compact_after_seconds: 0                     # Opt-in idle compaction (0 = disabled)
  hygiene_hard_message_limit: 5000                  # Gateway safety valve
  hygiene_timeout_seconds: 30                       # Max seconds of NO summary-model output before hygiene compression is cut off
  hygiene_total_ceiling_seconds: 600                # Absolute cap on the hygiene wait even while tokens are still streaming
  hygiene_failure_cooldown_seconds: 300             # First rung of the per-session hygiene-failure backoff (x1/x3/x9, capped at 1h)
  context_timeout_seconds: 120                      # Inactivity budget for in-agent compress_context
  context_total_ceiling_seconds: 600                # Absolute cap on the pre-commit in-agent compress_context wait
  proactive_prune_tokens: 0                         # Opt-in tokens trigger for the no-LLM tool-result prune (0 = off)
  proactive_prune_min_result_chars: 8000            # Prune's summarize pass only touches tool results larger than this
  proactive_prune_min_reclaim_tokens: 4096          # Prune only commits when it reclaims at least this many tokens

# The summarization model/provider is configured under auxiliary:
auxiliary:
  compression:
    model: ""                                       # Empty = use main chat model.
    provider: "auto"                                # Provider: "auto", "openrouter", "nous", "codex", "main", etc.
    base_url: null                                   # Custom OpenAI-compatible endpoint (overrides provider)
```

### Compression common setups (configuration)

```yaml
# Default (auto-detect) — no configuration needed
compression:
  enabled: true
  threshold: 0.50
```

```yaml
# Force a specific provider (OAuth or API-key based)
auxiliary:
  compression:
    provider: nous
    model: gemini-3-flash
```

```yaml
# Custom endpoint (self-hosted, Ollama, zai, DeepSeek, etc.)
auxiliary:
  compression:
    model: glm-4.7
    base_url: https://api.z.ai/api/coding/paas/v4
```

### Fallback providers (fallback-providers page)

```yaml
# Basic
fallback_providers:
  - provider: openrouter
    model: anthropic/claude-sonnet-4
```

```yaml
# Custom endpoint fallback
fallback_providers:
  - provider: custom
    model: my-local-model
    base_url: http://localhost:8000/v1
    key_env: MY_LOCAL_KEY            # env var name containing the API key
```

```yaml
# OpenRouter as fallback for Anthropic native
model:
  provider: anthropic
  default: claude-sonnet-4-6
fallback_providers:
  - provider: openrouter
    model: anthropic/claude-sonnet-4
```

```yaml
# Nous Portal as fallback for OpenRouter
model:
  provider: openrouter
  default: anthropic/claude-opus-4
fallback_providers:
  - provider: nous
    model: nous-hermes-3
```

```yaml
# Local model as fallback for cloud
fallback_providers:
  - provider: custom
    model: llama-3.1-70b
    base_url: http://localhost:8000/v1
    key_env: LOCAL_API_KEY
```

```yaml
# Codex OAuth as fallback
fallback_providers:
  - provider: openai-codex
    model: gpt-5.3-codex
```

### Profiles quick start (profiles page)

```bash
hermes profile create coder       # creates profile + "coder" command alias
coder setup                       # configure API keys and model
coder chat                        # start chatting
```

```bash
hermes profile create researcher --description "Reads source code and external docs, writes findings."
```

```bash
hermes profile create work --clone
hermes profile create backup --clone-all
hermes profile create work --clone-from coder
hermes profile create work-backup --clone-from coder --clone-all
```

```bash
coder chat                    # chat with the coder agent
coder setup                   # configure coder's settings
coder gateway start           # start coder's gateway
coder doctor                  # check coder's health
coder skills list             # list coder's skills
coder config set model.default anthropic/claude-sonnet-4
```

```bash
hermes -p coder chat
hermes --profile=coder doctor
hermes chat -p coder -q "hello"    # works in any position
```

```bash
hermes profile use coder
hermes chat                   # now targets coder
hermes tools                  # configures coder's tools
hermes profile use default    # switch back
```

```yaml
terminal:
  backend: local
  cwd: /absolute/path/to/project
```

```bash
hermes profile list           # show all profiles with status
hermes profile show coder     # detailed info for one profile
hermes profile rename coder dev-bot   # rename (updates alias + service)
hermes profile export coder   # export to coder.tar.gz
hermes profile import coder.tar.gz   # import from archive
```

```bash
hermes profile delete coder
hermes profile delete coder --yes
```

---

## 6. Recommendations Found

- "The easiest path is the interactive manager: `hermes fallback`" — fallback-providers, Configuration.
  (Docs phrase the CLI-picker path as the easiest, over hand-editing YAML.)
- "Never point two agent processes at the same profile (the same Hermes home)." — profiles, callout
  box titled "Give every agent its own profile."
- "If you want this profile to work in a specific project by default, also set its own `terminal.cwd`"
  — profiles, Configuring profiles. (Recommends pairing profile creation with an explicit `terminal.cwd`
  rather than relying on launch-directory inference.)
- "Quickest setup: run `hermes setup --portal` inside the new profile to wire up models + tools at once."
  — profiles, Creating a profile (tip callout).
- "If you plan to use this profile as a kanban worker (or want the kanban orchestrator to route work to
  it), pass `--description \"...\"` at create time so the orchestrator knows what it's good at." —
  profiles, Blank profile.
- "Prefer doing it early in a conversation or right after starting a fresh session" [re: mid-session
  model switches, to minimize prompt-cache re-read cost] — configuring-models, Mid-session switches and
  context warnings (Prompt-cache cost callout).
- "If you override the model, verify its context length meets or exceeds your main model's." —
  configuration, Context Compression (Summary model context length requirement).
- "Use `docker_forward_env` for tokens and `docker_env` for static knobs the container needs." —
  configuration, Docker Backend (out of this skill's boundary — terminal config — noted only because
  it's an explicit recommendation pattern on the same page; not to be restated as an in-scope fact for
  `hermes-configuration`).
- "If you intentionally want strict per-profile tool-config isolation, set: `terminal.home_mode:
  profile`" — profiles, How it works.

---

## 7. Boundary Notes (content belonging to a sibling skill)

- **Managed Scope / admin pins**: The Configuration page's "Org deployments" callout ("An administrator
  can pin specific config and secret values that a standard user cannot override, via a system-level
  managed directory. See Managed Scope.") belongs entirely to `hermes-managed-scope`. Not detailed here
  beyond the one-line existence quote already captured in §3.
- **Secrets handling (`.env`, API keys, tokens)**: Precedence rule ("secrets go in `.env`") is captured
  here because it defines the config.yaml/`.env` split, but the actual secret *values*, credential
  pools, and OAuth flows belong to provider-auth docs ("AI Providers", not pinned) and arguably
  `hermes-managed-scope` for admin-pinned secrets.
- **Hooks**: No hook configuration content was encountered on any of the three pinned pages or the
  one-hop fallback-providers page. `session:compress` is mentioned once ("Hooks see the mode via the
  `in_place` field on the `session:compress` event") — this is a pointer into `hermes-hooks` territory,
  not detailed further here.
- **Kanban**: `auxiliary.triage_specifier` and `auxiliary.kanban_decomposer` are auxiliary-task config
  blocks that route Kanban-specific LLM calls (`hermes kanban specify`, task decomposition). The keys
  themselves are in-boundary (auxiliary provider/model config, captured in §4's auxiliary tables), but
  their *behavioral* documentation (what the kanban triage/decomposition workflow actually does) belongs
  to `hermes-kanban`.
- **Skills**: `skills.config.<skillname>.*` (Skill Settings section) and `skills.guard_agent_created`/
  `skills.write_approval` are skill-authoring/governance config, not provider/model/compression/profile
  config — belongs to `hermes-skills`.
- **CLI reference**: `hermes config get/set/unset/check/migrate` and `hermes model`/`hermes fallback`/
  `hermes profile` subcommand syntax are captured here only as much as needed to describe config
  mechanics; the authoritative full CLI command reference belongs to `hermes-cli`.
- **Terminal backend configuration** (Docker/SSH/Modal/Daytona/Vercel/Singularity, `terminal.*` keys):
  Present on the same Configuration page but not part of this skill's pinned scope (provider/model/
  compression/profiles). Not extracted beyond the page map in §2. If a future skill covers execution
  sandboxing, this is its source page.
- **Memory Configuration** (`memory.*`): Present on the same page, out of this skill's pinned scope
  (description mentions "compression/memory settings" for the skill, but the source-capture boundary
  file explicitly scopes this skill to "config file locations and precedence, provider and model
  configuration ... profiles" — memory is not listed). Flagged as a possible scope mismatch between the
  SKILL.md description and the source-capture boundary file — see §8.

---

## 8. Gaps & Open Questions

1. **`model.context_length` and `max_tokens` are not documented on any pinned page.** The
   source-capture boundary file explicitly names these as in-scope ("provider and model configuration
   (context_length, max_tokens, compression thresholds)"), but neither key appears with a type, default,
   or set-location on `configuration`, `configuring-models`, or `profiles`. The only textual trace is
   the passing mention that editing `model.context_length` hot-reloads on a running gateway. **This
   needs a follow-up fetch of the "AI Providers" page** (linked by name from both pinned pages but not
   resolvable to a URL from the fetched markdown) before the skill can state anything normative about
   these two keys. Do not guess a schema for `model.context_length`/`max_tokens` from memory.
2. **SKILL.md description vs. source-capture boundary mismatch on "memory".** The placeholder SKILL.md
   description says "compression/memory settings", implying memory config (`memory.memory_enabled`,
   `memory.write_approval`, etc.) is in scope, but the source-capture boundary file's explicit list
   ("config file locations and precedence, provider and model configuration ..., profiles") does not
   mention memory. The Memory Configuration section exists on the pinned Configuration page (captured
   as an out-of-boundary page-map entry only, §2/§7) but was not extracted in detail per this run's
   assignment. The reviewer should decide whether to fold Memory Configuration into this skill (matching
   the SKILL.md description) or explicitly narrow the SKILL.md description to match the source-capture
   boundary file (which is the pinned authority for this run).
3. **`auxiliary.compression.max_concurrency` default is not explicitly stated as a hard default** — the
   full config reference block shows it only as a commented-out example (`# max_concurrency: 2`) with
   descriptive text, not a stated default value applied when absent. Marked `undocumented` in §4.
4. **`api_mode` values are not enumerated directly under the `model:` schema section** — the three values
   (`chat_completions`, `codex_responses`, `anthropic_messages`) are only enumerated explicitly under the
   unrelated `delegation.api_mode` key on the Configuration page, and inferred to apply identically to
   `model.api_mode` by cross-reference (both pages describe the same wire-protocol concept). This is a
   PARAPHRASE/INFERENCE, not a direct quote against `model.api_mode` — flagged for the reviewer to verify
   against a primary-model-focused source (likely "AI Providers") before treating as fact for `model:`.
5. **"Custom model aliases" full reference page was not fetched** (href could not be resolved from the
   rendered markdown of configuring-models). The canonical/short-string alias forms and their precedence
   are captured from the configuring-models page itself, but a dedicated reference page may add
   additional keys/behavior not seen here.
6. **Possible contradiction on subagent-fallback-inheritance found via out-of-boundary search snippet**
   (see §3, last row and §1 URL table) — a `developer-guide/provider-runtime` search snippet claims
   subagents do NOT inherit fallback, while the pinned `fallback-providers` user-guide page explicitly
   states they DO ("Subagent delegation ✔ (subagents inherit the parent fallback chain)"). Per the
   method's "official docs are the only authority" and "one hop from pinned pages only" rules, the
   pinned user-guide page's claim is treated as authoritative here, and the developer-guide claim is
   **not** cited as fact anywhere in this dossier — it is flagged only so the reviewer is aware of the
   discrepancy and can decide whether `hermes-cli` or a future developer-facing skill should resolve it
   by reading the full developer-guide page.
7. **`runtime.nofile_soft_limit`** and a handful of other top-level keys (Credential Pool Strategies,
   Prompt caching `cache_ttl`) sit directly under `config.yaml` next to in-boundary keys but are not
   named in the source-capture boundary list. Captured only in the page map / recommendations sections,
   not asserted as core content, pending reviewer decision on final scope.

---

## 9. Suggested SKILL.md Inputs

Each line cites the normative statement or table row it derives from.

**Key concepts:**
- Config resolution order is CLI args > `config.yaml` > `.env` > built-in defaults, and secrets always
  belong in `.env` while everything else (including compression and model wiring) belongs in
  `config.yaml` — derives from §3 rows 1–2 (Configuration Precedence quotes).
- `model:` is a 4-key mapping (`provider`, `default`, `base_url`, `api_mode`); a fresh install starts
  with the sentinel `model: ""` until `hermes setup`/`hermes model` upgrades it — derives from §3 row
  "On a brand-new install..." and §4 `model:` table.
- Every auxiliary task, `compression:`, and the primary `fallback_providers` chain follow the same
  three-knob pattern (`provider`/`model`/`base_url`), with `provider: "main"` valid only in those three
  places, never at top-level `model.provider` — derives from §3 row `"main"` provider option and §4
  universal auxiliary pattern table.
- Compression is governed by two separate blocks: `compression:` (thresholds/timers) and
  `auxiliary.compression:` (which model/provider does the summarizing) — derives from §4 compression
  tables and §5 full-reference example.
- A profile is a full separate Hermes home (`config.yaml`, `.env`, `SOUL.md`, memory, sessions, skills,
  cron, state db) and is explicitly NOT a sandbox or workspace boundary — derives from §3 profiles rows
  ("A profile is a separate Hermes home directory...", "A profile does not stop it from accessing
  folders outside the profile directory.").
- Two agent processes must never share one profile (Hermes home) — derives from §3 "Never point two
  agent processes at the same profile" quote.

**Workflow steps:**
1. Before setting or reviewing a config key, identify whether it's a secret (→ `.env`) or a setting
   (→ `config.yaml`) per the Rule of Thumb — derives from §3 row 2.
2. When wiring the main model, use the 4-key `model:` mapping shape shown in §5's dashboard-written
   example, not a bare string — derives from §4 `model:` table and §5 example.
3. When wiring an auxiliary task (vision, web_extract, compression, title_generation, etc.), use the
   provider/model/base_url pattern from §4's universal table; leave `provider: "auto"` unless a
   specific cost/latency reason requires overriding — derives from §3 "Why 'auto' uses your main model"
   paraphrase and §4 universal pattern table.
4. When configuring compression thresholds, edit the top-level `compression:` block; when configuring
   which model summarizes, edit `auxiliary.compression:` — never conflate the two — derives from §4
   compression tables (two separate tables) and §5 full-reference example comment
   ("The summarization model/provider is configured under auxiliary:").
5. Before overriding `auxiliary.compression.model` to a cheaper model, verify its context window is ≥
   the main model's — derives from §3 "Summary model context length requirement" quote.
6. When creating a profile intended for kanban/multi-agent routing, always pass `--description` at
   creation time — derives from §6 recommendation ("If you plan to use this profile as a kanban
   worker...").
7. Never point two Hermes profiles/processes at the same `HERMES_HOME` — derives from §3 "Give every
   agent its own profile" quote.
8. Do not assume `terminal.cwd: "."` means the profile directory — it means the launch directory;
   set `terminal.cwd` explicitly for predictable per-profile working directories — derives from §3
   "Using `cwd: '.'`..." quote.

**Validation commands (candidates):**
- `hermes config get model --json` and `hermes status` — verify resolved main-model config — derives
  from §3 row citing configuring-models / `hermes model` subcommand.
- `hermes config get <key>` — verify any resolved config value against documented defaults in §4 —
  derives from §2 Managing Configuration page-map entry.
- `hermes config check` — check for missing options after an update — derives from §2 Managing
  Configuration page-map entry.
- `hermes profile show <name>` — verify a profile's effective model/path/gateway status — derives from
  §5 profiles example (`hermes profile show coder`).
- `hermes fallback list` (alias `hermes fallback` with no subcommand) — verify the effective
  `fallback_providers` chain — derives from §3 "The easiest path is the interactive manager" and §4
  `fallback_providers` table.

**Gaps to resolve before finalizing (do not implement until addressed):**
- `model.context_length` / `max_tokens` schema — needs the "AI Providers" page (see §8, item 1).
- Whether Memory Configuration belongs in this skill's final scope (see §8, item 2).

---

## Addendum (reviewer, 2026-08-12): `model.context_length` / `model.max_tokens`

Resolved from the AI Providers page the dossier could not reach:
https://hermes-agent.nousresearch.com/docs/integrations/providers
(page title "AI Providers"; sections: Inference Providers, Custom &
Self-Hosted LLM Providers, Optional API Keys, OpenRouter Provider Routing,
OpenRouter Pareto Code Router, Fallback Providers).

### `model.context_length`

- Set in `config.yaml` under the `model:` block; integer token count.
- Official example:

```yaml
model:
  default: qwen2.5-coder:32b
  provider: custom
  base_url: http://localhost:11434/v1
  context_length: 64000
```

- Multi-source resolution chain (highest first): config override
  (`model.context_length`) → custom provider per-model settings →
  persistent cache from prior discoveries → endpoint `/models` API query →
  Anthropic `/v1/models` → OpenRouter API metadata → Nous Portal suffix
  matching → models.dev community registry → fallback default (128K).
- QUOTE: "Hermes requires at least 64,000 tokens of context for agent use
  with tools." Smaller windows are rejected at startup.

### `model.max_tokens`

- Set in `config.yaml` under the `model:` block.
- QUOTE: controls "the output cap — the maximum number of tokens the model
  may generate in a single response."
- QUOTE: "It has nothing to do with how long your conversation history can
  be." (that is `context_length`)
- No global default documented; behavior is server/model-dependent. The
  page notes low server-side output defaults (e.g. SGLang 128 tokens per
  response) — remedy via `model.max_tokens` in config.yaml or the server's
  `--default-max-tokens`.

### Scope decision (dossier §8 gap 2)

Reviewer resolution: memory configuration (`memory.*`) is OUT of this
skill's scope. The SKILL.md description was narrowed to match the
source-capture boundary; memory config remains unassigned across the
`hermes-*` family and should be flagged to the maintainer when needed.

---

## Addendum 2 (reviewer, 2026-08-12): independent corroboration run + merged deltas

A second, independently-run research dossier
(`source-analysis/hermes/hermes-configuration-capture-independent.md`)
corroborated the shared surface of this extraction verbatim (precedence,
compression schema, universal provider pattern, fallback semantics, profile
mechanics). The following deltas from that run were reviewer-verified
against the live pages and merged into SKILL.md v1.1.0:

### `api_mode` enum — now a direct QUOTE (was inference)

QUOTE (configuration / Delegation): "Wire protocol (`api_mode`): Hermes
auto-detects the wire protocol from `delegation.base_url` (e.g. paths
ending in `/anthropic` → `anthropic_messages`...). For endpoints the
heuristic can't classify... set `delegation.api_mode` explicitly to one of
`chat_completions`, `codex_responses`, or `anthropic_messages`."
The same enum applies to `model.api_mode` and `fallback_providers[].api_mode`.

### `fallback_providers[].api_mode` optional override

Verified on integrations/providers (Fallback Providers example):
`# api_mode: chat_completions           # optional override`

### Legacy `custom_providers:` field-name mapping

QUOTE (integrations/providers / Named Custom Providers, legacy format):
"Field names differ slightly in the dict format: legacy `model` is
`default_model`, and legacy `api_mode` is `transport`."
(Carried verbatim — the sentence's direction is ambiguous; do not
paraphrase which format uses which name without re-reading the page.)

### Custom model aliases — full schema (reference/slash-commands#custom-model-aliases)

- Full form supports `base_url` per alias (e.g. an `ollama-qwen` alias with
  `provider: custom` and a localhost base_url).
- QUOTE: "Alias names are case-insensitive."
- QUOTE: "User aliases take precedence over built-in short names, so naming
  an alias `sonnet`, `kimi`, `opus`, etc. will shadow the built-in."

### Left open (deliberately)

Subagent-fallback-inheritance discrepancy remains as recorded in Addendum 1
sources and `source-capture.md` — needs a developer-guide-focused pass.
