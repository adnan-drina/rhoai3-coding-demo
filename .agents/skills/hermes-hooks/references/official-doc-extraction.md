# Official Doc Extraction — hermes-hooks

Validated research dossier (capture date 2026-08-12). Reviewer validation:
the four-system taxonomy, ordering/precedence, non-TTY consent, exit-code-2
scoping, and error-isolation quotes re-verified verbatim against the live
Hooks page; all single-sourced Build-a-Plugin facts verified verbatim
against the guide's markdown source in the product repository
(`website/docs/developer-guide/plugins/index.md` — the rendered page
returns empty to WebFetch-style tools). Original dossier:
`source-analysis/hermes/hermes-hooks-capture.md`.

---

# hermes-hooks — Documentation Research Dossier

## Executive summary (5 lines)

1. Captured: all four hook systems end to end — gateway hooks (`HOOK.yaml`+`handler.py`), plugin hooks (`ctx.register_hook()`, 23 shipped events across directive/control, transform, and observer categories), shell hooks (`hooks:` in `config.yaml`, JSON wire protocol, consent/allowlist model), and outbound webhooks (`hooks.outbound:`, HMAC-signed delivery) — plus registration mechanics, ordering/precedence, and the security posture for each.
2. Confidence: high for plugin-hook and shell-hook mechanics (one authoritative, extremely detailed primary page plus a converging secondary page); medium for the exact plugin-hook event count (see contradiction below).
3. Biggest gap: the Plugins page states "24 lifecycle events currently accepted by `hermes_cli.plugins.VALID_HOOKS`," but the Hooks page's own shipped-hook catalog table lists only 23 distinct event names — the 24th event is not identifiable from any page I could reach.
4. Contradicts the placeholder: the placeholder's single pinned URL (`/docs/user-guide/features/hooks`) covers only the plugin+gateway+shell+outbound-webhook system; it does not mention that gateway hooks, plugin hooks, shell hooks, and outbound webhooks are four **distinct** registration/runtime systems with different capability matrices (block/inject/isolation) — this taxonomy is the organizing fact of the whole topic and should be the skill's lead concept, not a footnote.
5. Suggested next skill to research: `hermes-configuration` (to confirm which parts of the `hooks:` block — `output_spill`, `hooks_auto_accept`, `plugins.enabled`/`disabled` — belong to the general config-key schema vs. hook-specific mechanics captured here), or `hermes-managed-scope` (to check whether admin pins can force-enable/disable specific hooks or plugins fleet-wide).

---

## 1. Capture header

| Field | Value |
| --- | --- |
| Product | Hermes Agent (Nous Research) |
| Product version | No version marker found on any page read (no version banner, no "as of vX.Y" text). The Environment Variables reference mentions "config schema v21+" as a migration threshold for plugin opt-in behavior — this is the only version-like marker encountered, and it is a config-schema version, not a product release version. |
| Capture date | 2026-08-12 |
| Capture agent | Documentation research (this dossier), run against `https://hermes-agent.nousresearch.com` |

### Page inventory

**Read (primary relevance to TOPIC):**

| Page | URL | Why read |
| --- | --- | --- |
| Event Hooks | `/docs/user-guide/features/hooks` | Primary/canonical hooks reference — all four hook systems, full event catalog, shell-hook JSON protocol, outbound webhooks. |
| Gateway Internals | `/docs/developer-guide/gateway-internals` | Gateway-hook-specific implementation detail: `gateway/hooks.py`, `gateway/builtin_hooks/`, discovery, and a second (partially divergent) gateway-event table. |
| Plugins | `/docs/user-guide/features/plugins` | Plugin discovery/opt-in mechanics that gate whether any plugin-registered hook ever runs; the "Available hooks" summary table with hook count and category breakdown. |
| Build a Hermes Plugin | `/docs/guides/build-a-hermes-plugin` | Hook authoring walkthrough with unique normative content not on the Hooks page: `pre_llm_call` context-injection spill/cap config, the `ctx._cli_ref`/`ctx.profile_name`/`ctx.dispatch_tool()` "act from inside a hook" APIs, `plugin.yaml` `provides_hooks` manifest field. |
| Built-in Plugins | `/docs/user-guide/features/built-in-plugins` | Official worked examples of hooks in production (disk-cleanup, security-guidance, observability/langfuse) — real hook-to-behavior mappings, not synthetic examples. |
| Security | `/docs/user-guide/security` | Approval-flow context that `pre_approval_request`/`post_approval_response` hook into; command-allowlist and consent patterns that parallel the shell-hooks allowlist. |
| Environment Variables (reference) | `/docs/reference/environment-variables` | `HERMES_ACCEPT_HOOKS`, `HERMES_SAFE_MODE` exact definitions. |
| CLI Commands (reference) | `/docs/reference/cli-commands` | Canonical `hermes hooks <subcommand>` table and `--safe-mode` flag description — cross-checks the Hooks page's own CLI section. |
| `llms.txt` index | `/docs/llms.txt` | Site navigation map used to enumerate every plausibly relevant page (see below). |

**Enumerated but deprioritized (with reason):**

| Page | Reason deprioritized |
| --- | --- |
| Kanban Multi-Agent / Kanban Tutorial | Kanban-specific task lifecycle and dispatcher/worker split is explicitly owned by `hermes-kanban` per assignment; I only captured the *general* hook mechanics the three `kanban_*` hooks sit on (already present verbatim on the Hooks and Build-a-Plugin pages I read). |
| Skills System / Creating Skills | Skills-system mechanics beyond the `on_skill_lifecycle` hook point are owned by `hermes-skills`. |
| Configuration / Configuring Models | General `config.yaml` schema ownership belongs to `hermes-configuration`; I only read the `hooks:` and `plugins:` keys as they appear directly on hook-mechanics pages. |
| Sessions / Checkpoints & Rollback | Session storage/resumption mechanics owned by `hermes-sessions`; I only captured the session-lifecycle *hook events* (`on_session_start/end/finalize/reset`), not session storage internals. |
| CLI (`/docs/user-guide/cli`), Slash Commands (reference) | Full CLI/slash-command surface owned by `hermes-cli`; Slash Commands reference page was fetched and searched for hook-related entries — no matches found (no `/hooks`-style slash command exists; hook management is CLI-only via `hermes hooks`). |
| Cron Jobs, Delegation, Persistent Goals | Adjacent automation surfaces; `subagent_start`/`subagent_stop` (delegation-hook) content was already fully covered on the Hooks/Build-a-Plugin pages without needing the Delegation page itself. Not chased further per scope. |
| Memory / Memory Providers / Honcho | The Gateway Internals page's "Memory Provider Integration" section documents how `on_session_end` interacts with memory flush — captured that section since it's a hook-timing fact, but did not chase the Memory Providers page itself (provider-specific, not hook-mechanics). |
| MCP, ACP, API Server, Provider Runtime, Adding Providers, Adding Platform Adapters, Model Provider Plugins, Image/Video Generation Provider Plugins, TTS/STT Setup | Listed on the Plugins page's "Pluggable interfaces" table as sibling extension surfaces to hooks; not hook mechanics themselves — recorded as boundary notes only where the Plugins page explicitly contrasts them with hooks. |
| Architecture, Agent Loop, Prompt Assembly, Context Compression & Caching, Session Storage, Adding Tools, Extending the CLI, Contributing | General developer-guide pages with no hooks-specific section found via the `llms.txt` descriptions; not fetched. |
| Tools Reference, Toolsets Reference, MCP Config Reference, Model Catalog, Bundled/Optional Skills Catalog, Profile Commands, FAQ & Troubleshooting | Reference pages for unrelated subsystems; not fetched. |
| All individual messaging-platform setup pages (Telegram, Discord, Slack, etc.) | Platform-specific bot setup, not hook mechanics. The Gateway Internals page's platform-adapter table was read instead for the general adapter/hook relationship. |

**Dead links or redirects:** none encountered — every URL fetched (including the two page leads handed off) resolved successfully on the first attempt.

---

## 2. Recommended source pins

The current placeholder pins only:

> `https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks`

**This single pin is insufficient.** Recommend pinning all of the following, in this priority order:

1. `/docs/user-guide/features/hooks` — **primary**, canonical. Covers gateway hooks, the full plugin-hook catalog (23 events with exact timing/payload/privacy), shell hooks (config schema, JSON wire protocol, consent model, `hermes hooks` CLI), and outbound webhooks (config schema, wire format, delivery semantics).
2. `/docs/guides/build-a-hermes-plugin` — **secondary, load-bearing**. Contains normative facts absent from the primary page: the `pre_llm_call` context-injection character cap (10,000, configurable via `hooks.output_spill`), the overflow-file mechanism, and the `ctx._cli_ref` / `ctx.profile_name` / `ctx.dispatch_tool()` APIs for acting from inside a hook callback (which process-context each is valid in). Also documents the `plugin.yaml` `provides_hooks` manifest field, which the primary Hooks page never mentions.
3. `/docs/user-guide/features/plugins` — **secondary**. Sole source for the "24 lifecycle events" count claim, the three-way hook category taxonomy (directive/control, transform, observer) as a *summary* view, and the plugin discovery/opt-in gating (`plugins.enabled`/`plugins.disabled`) that determines whether a plugin's hooks ever actually register.
4. `/docs/developer-guide/gateway-internals` — **secondary**. Names the actual source files (`gateway/hooks.py`, `gateway/builtin_hooks/`) and states `gateway/builtin_hooks/` is "currently empty in the shipped distribution" with `_register_builtin_hooks()` a no-op stub — useful for anyone about to add a truly built-in gateway hook. **Caution:** its own gateway-event table is a narrower, seemingly-stale subset of the primary page's table (see contradiction in §4) — pin it for the *implementation* facts, not as the authoritative event list.
5. `/docs/user-guide/features/built-in-plugins` — **tertiary**, high value for examples. The only place with worked, production hook implementations (disk-cleanup's `post_tool_call`+`on_session_end` pairing; security-guidance's write-path hook; langfuse's four-hook observability wiring) — useful as canonical "how a real hook-based plugin is built" reference.
6. `/docs/reference/environment-variables` — **tertiary**, narrow but exact. `HERMES_ACCEPT_HOOKS` and `HERMES_SAFE_MODE` exact definitions (§ Agent Behavior).
7. `/docs/reference/cli-commands` — **tertiary**, narrow but exact. Canonical `hermes hooks` subcommand table (§ `hermes hooks`) and `--safe-mode` flag text, useful as a cross-check against the primary page's own CLI section (they agree).

**Pages the current single pin misses entirely:** all of #2–7 above — none of their hook-relevant content is reachable from the `/docs/user-guide/features/hooks` page alone (it doesn't link to Build a Hermes Plugin's context-injection-cap section, doesn't mention Built-in Plugins, and doesn't cross-reference Gateway Internals).

**Pins that proved irrelevant:** none — the placeholder's one pin is a subset of what's needed, not an incorrect page.

---

## 3. Page maps

### `/docs/user-guide/features/hooks` (Event Hooks)

1. Intro — four-hook-system summary table + one-line callback-error/directive-vs-observer note.
2. Gateway Event Hooks
   - Creating a Hook (`HOOK.yaml` + `handler.py` directory layout)
   - `HOOK.yaml` example
   - `handler.py` example + handler rules
   - Available Events (table: 10 gateway events + `command:*` wildcard)
   - Wildcard Matching
   - Examples (Telegram alert, command logger, session webhook)
   - Tutorial: BOOT.md (full worked gateway-hook build, including "why this isn't a built-in" design note)
   - How It Works (5-step `HookRegistry.discover_and_load()` sequence)
3. Plugin Hooks
   - Registration snippet (`ctx.register_hook(...)` for 8 example events incl. 3 kanban ones)
   - General rules for all hooks (kwargs, exception handling, category semantics, correlation-field caveat)
   - Shipped plugin-hook catalog (the master table: 23 rows, columns = Hook / Category / Exact timing and return behavior / Explicit payload fields / Privacy-sensitivity)
   - Per-hook deep-dive sections (one `###` heading each): `pre_tool_call`, `post_tool_call`, `pre_llm_call`, `post_llm_call`, `pre_verify`, `on_session_start`, `on_session_end`, `on_session_finalize`, `on_session_reset`, `subagent_start`, `subagent_stop`, `pre_gateway_dispatch`, `pre_approval_request`, `post_approval_response`, `transform_tool_result`, `transform_terminal_output`, `transform_llm_output`, API-request observer hooks (`pre_api_request`/`post_api_request`/`api_request_error`), `on_skill_lifecycle`, Kanban lifecycle observers.
4. Shell Hooks
   - Comparison at a glance (Shell vs. Plugin vs. Gateway hooks table)
   - Configuration schema (`hooks:` YAML shape)
   - JSON wire protocol (stdin payload, stdout response shapes)
   - Exit code 2 = block
   - Fail-open vs fail-closed (table)
   - Worked examples (4: auto-format, block-rm-rf, inject-cwd-context, log-orchestration)
   - Consent model (allowlist, 3 escape hatches, manual allowlisting)
   - The `hermes hooks` CLI (table: list/test/revoke/doctor)
   - Security (recommendations list)
   - Ordering and precedence
5. Outbound Webhooks
   - Configuration (`hooks.outbound:` YAML shape, 2 example entries)
   - Wire format (JSON body + headers table)
   - Delivery semantics (bullet list of 6 guarantees/non-guarantees)

### `/docs/developer-guide/gateway-internals`

Relevant section only: **Hooks** — a short subsection near the end, with its own "Gateway Hook Events" table (8 rows, narrower than the Hooks page's 10+wildcard) and one paragraph on discovery (`gateway/builtin_hooks/` + `~/.hermes/hooks/`). Also relevant: **Memory Provider Integration** → **Memory Flush Lifecycle** (4-step list that names `on_session_end()` as a firing point), and the **Key Files** table (names `gateway/hooks.py` and `gateway/builtin_hooks/` as the source locations).

### `/docs/user-guide/features/plugins`

Relevant sections: **What plugins can do** (table row: "Add hooks — `ctx.register_hook("post_tool_call", callback)`"), **Available hooks** (one-paragraph statement of the "24 lifecycle events" count + 3-category summary table), **Pluggable interfaces** (table row distinguishing Python-plugin hooks / gateway hooks / shell hooks as three separate authoring paths, each linking to its own guide).

### `/docs/guides/build-a-hermes-plugin`

Relevant sections (this is a long guide; only hook-relevant parts read in full): manifest `provides_hooks` field example; **Register multiple hooks**; **Hook reference** (a second, slightly reworded summary table of the 9 most common hooks + a one-paragraph kanban-hooks note with the exact "fires after the board DB change commits" durability quote); **`pre_llm_call` context injection** (return format, oversized-context spill/cap, how-injection-works rationale, 3 examples, multiple-plugins-join-order note); **Act from inside a hook (profile + tools)** (`ctx._cli_ref`, `ctx.profile_name`, `ctx.dispatch_tool()`); **Gateway event hooks** and **Shell hooks** summary subsections (cross-references back to the primary Hooks page, no new facts beyond an event-name list).

### `/docs/user-guide/features/built-in-plugins`

Relevant sections: **disk-cleanup** (hook table: `post_tool_call` + `on_session_end` behavior), **security-guidance** (prose description of its `write_file`/`patch`/`skill_manage` interception — hook name not explicitly stated but behavior matches `pre_tool_call`/`transform_tool_result` semantics; treated as PARAPHRASE, not quote, since the page itself doesn't name the hook), **observability/langfuse** (hook table: `pre_api_request`/`pre_llm_call`, `post_api_request`/`post_llm_call`, `pre_tool_call`, `post_tool_call` mapped to Langfuse span/generation/observation lifecycle).

### `/docs/user-guide/security`

Relevant sections: **Approvals** config block (`approvals.mode`, `cron_mode`, etc.) — context for `pre_approval_request`/`post_approval_response` hook firing points; command-allowlist persistence pattern (parallels shell-hooks allowlist).

### `/docs/reference/environment-variables`

Relevant section: **Agent Behavior** table — `HERMES_ACCEPT_HOOKS`, `HERMES_SAFE_MODE` rows.

### `/docs/reference/cli-commands`

Relevant section: **`hermes hooks`** (subcommand table) and the `--safe-mode` global-flag row.

---

## 4. Normative statements

| Exact quote | Page + section | Why it matters for stage 080 |
| --- | --- | --- |
| "Hermes has four hook systems that run custom code at key lifecycle points" | Hooks page, intro | Establishes the top-level taxonomy the skill must teach first — choosing the wrong hook system is the most common mistake. |
| "Hook callback errors are isolated and logged rather than crashing the agent. Hooks are not all passive: directive/control hooks can change flow, transforms can replace content, and a shell `pre_tool_call` hook can block or fail closed." | Hooks page, intro | Core safety guarantee (fail-isolated) plus the one exception that must be called out explicitly (shell hooks can fail closed). |
| "Gateway hooks only fire in the gateway (Telegram, Discord, Slack, WhatsApp, Teams). The CLI does not load gateway hooks. For hooks that work everywhere, use plugin hooks." | Hooks page, Gateway Event Hooks | Direct guidance for any stage-080 guard/stamper/watchdog that must also run in CLI sessions — must use plugin or shell hooks, not gateway hooks. |
| "Must be named `handle`" / "Receives `event_type`(string) and `context`(dict)" / "Can be `async def` or regular `def`— both work" / "Errors are caught and logged, never crashing the agent" | Hooks page, `handler.py` handler rules | Exact gateway-hook handler contract — required for writing a conformant `handler.py`. |
| "Handlers registered for `command:*` fire for any `command:` event... Monitor all slash commands with a single subscription." | Hooks page, Wildcard Matching | Only documented wildcard pattern; no other wildcard forms are described anywhere else read. |
| "On gateway startup, `HookRegistry.discover_and_load()` scans `~/.hermes/hooks/`" / "Each subdirectory with `HOOK.yaml`+`handler.py` is loaded dynamically" / "Handlers are registered for their declared events" / "At each lifecycle point, `hooks.emit()` fires all matching handlers" / "Errors in any handler are caught and logged — a broken hook never crashes the agent" | Hooks page, How It Works | The exact 5-step gateway-hook discovery/dispatch algorithm — the canonical mental model. |
| "Callbacks receive keyword arguments. Always accept `**kwargs` for forward compatibility." | Hooks page, Plugin Hooks general rules | MUST-follow authoring rule for every plugin-hook callback, no exceptions documented. |
| "Callback exceptions are logged and skipped; later callbacks continue." | Hooks page, Plugin Hooks general rules | Confirms per-callback isolation (not per-event) — one bad hook does not stop sibling hooks on the same event. |
| "The catalog below is descriptive: observers ignore returns, transforms accept the first valid string replacement, and directive/control hooks consume documented return shapes. Plugin middleware is a separate registry and surface, not another hook category." | Hooks page, Plugin Hooks general rules | Explicitly scopes what "hook" means in this system — middleware is out of scope for this skill (no owning skill exists per assignment; record as gap, don't chase). |
| "Correlation fields such as `turn_id`, `api_request_id`, `task_id`, `session_id`, and `api_call_count` are hook-specific and may be absent. Treat IDs as opaque." | Hooks page, Plugin Hooks general rules | Anti-pattern warning: code must not assume any correlation ID is always present. |
| "Runtime event-name validity comes from `hermes_cli.plugins.VALID_HOOKS`. `hermes hooks list` lists configured shell/outbound hooks, not every available event; `hermes hooks test <event>` reports the valid set only when an invalid event is supplied." | Hooks page, Plugin Hooks general rules | Clarifies a likely diagnostic confusion: `hermes hooks list` is NOT a way to enumerate all possible hook events — only configured shell/outbound ones. |
| "Payload fields below are the exact event-specific fields supplied by each call site. For backward compatibility, `PluginManager` also adds `telemetry_schema_version="hermes.observer.v1"` to every plugin-hook callback. That legacy envelope marker does not mean all hook payloads share one semantic schema; new versioned contracts belong to their concrete event or capability family." | Hooks page, Shipped plugin-hook catalog intro | Important gotcha: presence of `telemetry_schema_version` does not imply a unified payload schema across events. |
| "Fires: In `model_tools.py`, inside `handle_function_call()`, before the tool's handler runs. Fires once per tool call — if the model calls 3 tools in parallel, this fires 3 times." | Hooks page, `pre_tool_call` | Concurrency-relevant: parallel tool calls fire the hook multiple times, not once. |
| "The first valid directive wins. `block` requires a non-empty `message` and short-circuits the tool with that text as the error returned to the model. `approve` escalates the call to the existing human-approval gate; `message` and `rule_key` are optional, and denial, timeout, or gate error fails closed." | Hooks page, `pre_tool_call` | Exact block/approve semantics + the important fail-closed detail on approval-gate errors. |
| "Does not fire if the tool raised an unhandled exception (the error is caught and returned as an error JSON string instead, and `post_tool_call` fires with that error string as `result`)." | Hooks page, `post_tool_call` | Precise firing/non-firing boundary for `post_tool_call` under tool exceptions. |
| "Fires: In `run_agent.py`, inside `run_conversation()`, after context compression but before the main `while` loop. Fires once per `run_conversation()` call (i.e. once per user turn), not once per API call within the tool loop." | Hooks page, `pre_llm_call` | Critical for anyone assuming `pre_llm_call` fires per-API-call — it does not; it fires once per turn. |
| "Where context is injected: Always the user message, never the system prompt. This preserves the prompt cache — the system prompt stays identical across turns, so cached tokens are reused." | Hooks page, `pre_llm_call` | Design-rationale fact directly relevant to any stage-080 hook injecting context (e.g., a guardrails or RAG hook) — informs prompt-cache-aware design. |
| "When multiple plugins return context, their outputs are joined with double newlines in plugin discovery order (alphabetical by directory name)." | Hooks page, `pre_llm_call` | Determinism fact needed if multiple plugins inject context — ordering is directory-name alphabetical, not registration order or config order. |
| "Only fires on successful turns — does not fire if the turn was interrupted." / "Guarded by `if final_response and not interrupted`" | Hooks page, `post_llm_call` | Exact non-firing condition — an interrupted turn (Ctrl+C, `/stop`, iteration limit with no response) never fires `post_llm_call`. |
| "Bounded: consecutive continue directives in one turn are capped by `agent.max_verify_nudges` (default 3), so a hook that always says continue can never trap the loop." | Hooks page, `pre_verify` | Safety bound preventing an infinite verify-nudge loop — important for anyone writing a `pre_verify` policy hook. |
| "Make it idempotent: the hook re-fires after each nudge, so gate on `attempt` (`if attempt: return None`) — otherwise it just nudges until the bound is hit." | Hooks page, `pre_verify` | Direct authoring guidance / common-mistake warning. |
| "Fires once when a brand-new session is created. Does not fire on session continuation (when the user sends a second message in an existing session)." | Hooks page, `on_session_start` | Precise firing condition. |
| "Fires at the very end of every `run_conversation()` call, regardless of outcome. Also fires from the CLI's exit handler if the agent was mid-turn when the user quit." | Hooks page, `on_session_end` | Establishes that `on_session_end` is the reliable "always fires" cleanup hook, unlike `post_llm_call`. |
| "On gateway reset, the order is: create and persist the replacement → `on_session_finalize(old_id)` → `on_session_reset(new_id)` → `on_session_start(new_id)` on the first inbound turn." | Hooks page, `on_session_reset` | Exact firing-order guarantee across three related hooks during a gateway session reset — needed for any hook coordinating state across these three events. |
| "This hook is specific to delegation/subagent lifecycle. It is not a universal 'before any agent invocation' gate for gateway, CLI, cron, batch, MoA, or other runner-originated agent executions." | Hooks page, `subagent_start` | Explicit scope-limiting warning — prevents misuse as a general agent-start gate. |
| "`subagent_start` is useful for delegation observability, but it is not a blocking policy hook. To block delegation before a child is built, use `pre_tool_call` to block the `delegate_task` tool call." | Hooks page, `subagent_start` info-box | Directly actionable pattern: block delegation via `pre_tool_call`, not `subagent_start`. |
| "Fires once per child agent after `delegate_task` finishes... serialised on the parent thread." / "With heavy delegation (e.g. orchestrator roles × 5 leaves × nested depth), `subagent_stop` fires many times per turn. Keep your callback fast; push expensive work to a background queue." | Hooks page, `subagent_stop` | Concurrency/performance guidance: callback is serialized (no thread-safety concerns) but can fire at high volume. |
| "Internal events skip the hook entirely (they are system-generated — background-process completions, etc. — and must not be gate-kept by user-facing policy)." | Hooks page, `pre_gateway_dispatch` | Important scoping fact: this hook never sees internally-generated events. |
| "Exceptions in plugin callbacks are caught and logged; the gateway always falls through to normal dispatch on error." | Hooks page, `pre_gateway_dispatch` | Fail-open-by-default behavior for this specific directive/control hook (contrast with shell `pre_tool_call`'s optional fail-closed). |
| "Return value: ignored. Hooks here are observer-only; they cannot veto or pre-answer the approval. Use `pre_tool_call` to block a tool before it reaches the approval system." | Hooks page, `pre_approval_request` | Clarifies `pre_approval_request`/`post_approval_response` are strictly observational — the actionable blocking point is upstream at `pre_tool_call`. |
| "Applies to every tool. For terminal-only rewriting see `transform_terminal_output` below — it is narrower, runs before `transform_tool_result`, and its replacement is still subject to the terminal tool's final output limit." | Hooks page, `transform_tool_result` | Exact ordering between the two transform hooks that both touch terminal output. |
| "Unlike the tool and terminal transforms, an empty string is not accepted as a replacement." | Hooks page, `transform_llm_output` | Subtle contract difference: `transform_llm_output` treats `""` as "no change," unlike the other two transform hooks which accept `""` as a valid replacement. |
| "This hook is guarded on a non-empty, non-interrupted response — it will not fire on stop-button interrupts or empty turns." | Hooks page, `transform_llm_output` | Firing-condition parity with `post_llm_call`. |
| "Fires after the claim commit in the dispatcher process, immediately before worker spawn." (`kanban_task_claimed`) / "Fires after completion and cleanup, usually in the worker process." (`kanban_task_completed`) / "Fires after a normal blocked transition. The dependency-wait path invokes it before that write transaction exits." (`kanban_task_blocked`) | Hooks page, Kanban lifecycle observers | General hook-firing/process-split facts underlying the three kanban hook names — boundary note: kanban-specific task/board semantics belong to `hermes-kanban`, but this *general mechanic* (durable-state guarantee + process split) is captured here per the assignment's explicit instruction. |
| "The kanban lifecycle hooks fire **after** the board DB change commits, so a callback always sees durable state and can never hold the SQLite write lock." | Build a Hermes Plugin guide, Hook reference | Confirms the durability guarantee mentioned in the assignment context — this is general hook-timing behavior (not kanban-specific board semantics), so it belongs in this dossier; the reviewer flagged this exact seam for verification and it is now CONFIRMED by an independent page (not the kanban page itself). |
| "Declare shell-script hooks in your `~/.hermes/config.yaml` and Hermes will run them as subprocesses whenever the corresponding plugin-hook event fires — in both CLI and gateway sessions. No Python plugin authoring required." | Hooks page, Shell Hooks intro | Establishes shell hooks as strictly a subprocess-dispatch layer over the *same* plugin-hook event set, not a separate event taxonomy. |
| "Shell hooks are registered by calling `agent.shell_hooks.register_from_config(cfg)` at both CLI startup (`hermes_cli/main.py`) and gateway startup (`gateway/run.py`). They compose naturally with Python plugin hooks — both flow through the same dispatcher." | Hooks page, Shell Hooks intro | Implementation-level confirmation that shell hooks and plugin hooks share one dispatcher — relevant to the "Ordering and precedence" quote below. |
| "Event names must be one of the plugin hook events; typos produce a 'Did you mean X?' warning and are skipped. Unknown keys inside a single entry are ignored; missing `command` is a skip-with-warning. `timeout > 300` is clamped with a warning. `fail_closed: true` on an event other than `pre_tool_call` warns and is ignored (only blocking-capable events can fail closed)." | Hooks page, Configuration schema | Exact config-validation behavior — every malformed shell-hook config field degrades gracefully with a warning, never a hard failure. |
| "`tool_name` and `tool_input` are `null` for non-tool events (`pre_llm_call`, `subagent_stop`, session lifecycle). The `extra` dict carries all event-specific kwargs... Unserialisable values are stringified rather than omitted." | Hooks page, JSON wire protocol | Exact stdin payload contract for shell-hook scripts. |
| "Malformed JSON, non-zero exit codes, and timeouts log a warning but never abort the agent loop." | Hooks page, JSON wire protocol | Fail-open default for stdout parsing. |
| "A `pre_tool_call` hook that exits with code 2 blocks the tool call even when its stdout carries no block JSON." | Hooks page, Exit code 2 = block | Claude-Code/Cursor-compatible convention explicitly supported. |
| "For events whose block directive is not honored (everything except `pre_tool_call`), exit 2 is treated like any other non-zero exit: a warning is logged and stdout is still parsed." | Hooks page, Exit code 2 = block | Scopes the exit-2 convention strictly to `pre_tool_call`. |
| "By default shell hooks fail open: a spawn error, timeout, or unparseable stdout logs a warning and the action proceeds... Set `fail_closed: true`... to invert that." | Hooks page, Fail-open vs fail-closed | Core security-posture default + the opt-in inversion mechanism. |
| "`fail_closed` only applies to blocking-capable events (`pre_tool_call` today); setting it on any other event logs a warning at config-parse time and is ignored." | Hooks page, Fail-open vs fail-closed | Confirms scope limit (same fact as the exit-code-2 quote above, stated again for the config key itself). |
| "Each unique `(event, command)` pair prompts the user for approval the first time Hermes sees it, then persists the decision to `~/.hermes/shell-hooks-allowlist.json`. Subsequent runs (CLI or gateway) skip the prompt." | Hooks page, Consent model | Exact consent/allowlist keying — per `(event, command)` pair, not per script file. |
| "Non-TTY runs (gateway, cron, CI) need one of these three [`--accept-hooks`, `HERMES_ACCEPT_HOOKS=1`, `hooks_auto_accept: true`] — otherwise any newly-added hook silently stays un-registered and logs a warning." | Hooks page, Consent model | Critical operational fact for stage-080 headless/CI/cron deployments: a shell hook silently no-ops without one of these three escape hatches. |
| "Script edits are silently trusted. The allowlist keys on the exact command string, not the script's hash, so editing the script on disk does not invalidate consent. `hermes hooks doctor` flags mtime drift so you can spot edits and decide whether to re-approve." | Hooks page, Consent model | Security-relevant gap + the mitigating diagnostic (`hermes hooks doctor`). |
| "The allowlist file is `~/.hermes/shell-hooks-allowlist.json`, and the expected format is an `approvals` array... A path-keyed object with a `sha256` field is not the expected format and will not approve the hook." | Hooks page, Manual allowlisting | Exact file format + an explicit "this other shape does NOT work" warning — prevents a plausible authoring mistake. |
| "Shell hooks run with your full user credentials — same trust boundary as a cron entry or a shell alias. Treat the `hooks:` block in `config.yaml` as privileged configuration" | Hooks page, Security | Core security-posture statement for shell hooks. |
| "If your config.yaml is version-controlled across a team, review PRs that change the `hooks:` section the same way you'd review CI config." | Hooks page, Security | Directly actionable recommendation for a team/repo context (relevant to this repo's own GitOps/PR review culture). |
| "Both Python plugin hooks and shell hooks flow through the same `invoke_hook()` dispatcher. Python plugins are registered first (`discover_and_load()`), shell hooks second (`register_from_config()`), so Python `pre_tool_call` block decisions take precedence in tie cases. The first valid block wins — the aggregator returns as soon as any callback produces `{"action": "block", "message": str}` with a non-empty message." | Hooks page, Ordering and precedence | THE definitive cross-system ordering/precedence rule — Python plugin hooks always get first refusal over shell hooks for the same event. |
| "Outbound webhooks are the push-side mirror of the inbound webhook platform... Configure a list of HTTP endpoints and the lifecycle events they care about, and Hermes POSTs a signed JSON payload to each endpoint whenever a matching event fires — no polling on the receiving end." | Hooks page, Outbound Webhooks intro | Defines outbound webhooks as the fourth, distinct hook system (push notification, not code execution). |
| "Any event from the plugin-hook set is valid... Malformed entries warn and are skipped — a broken webhook never crashes the agent. Changes take effect on the next CLI session / gateway restart." | Hooks page, Outbound Webhooks Configuration | Confirms outbound webhooks reuse the same event namespace as plugin hooks (no separate event vocabulary), plus the reload-on-restart caveat (not hot-reloaded). |
| "Secrets: prefer `secret_env`(the name of an environment variable...) over an inline `secret:` literal, so the config file stays free of credentials. Entries without a secret are delivered unsigned (flagged as `UNSIGNED` by `hermes hooks list`)." | Hooks page, Outbound Webhooks Configuration | Direct security guidance + the diagnostic surface (`hermes hooks list` flags unsigned targets) — highly relevant to this repo's "no secrets in Git" rule. |
| "Because `delivery_id` and `timestamp` live inside the signed body, a verified receiver also gets replay protection for free... Reject stale events by checking `timestamp` against your clock with a tolerance window (5 minutes is the common default)." | Hooks page, Outbound Webhooks Wire format | Concrete receiver-side security recommendation. |
| "Fire-and-forget, off the hot path... A slow or dead endpoint can never stall a tool call or an agent turn." / "Notify-only. Unlike shell hooks, outbound webhooks cannot block tool calls or inject context — the response body is ignored. They observe, never steer." | Hooks page, Outbound Webhooks Delivery semantics | Two of the most important capability-boundary facts distinguishing outbound webhooks from shell/plugin hooks. |
| "Bounded retries. Connection errors and 5xx responses are retried once with backoff; 4xx responses are not retried... Redirects are never followed. A 3xx response is treated as a misconfiguration and logged" | Hooks page, Outbound Webhooks Delivery semantics | Exact retry/redirect contract for any external receiver implementation. |
| "No consent prompt. Outbound targets execute no code on your machine — they receive data at a URL you configured. `HERMES_SAFE_MODE=1` still skips registration, same as plugins and shell hooks." | Hooks page, Outbound Webhooks Delivery semantics | Clarifies outbound webhooks have a different (lower) consent bar than shell hooks, but are still gated by `HERMES_SAFE_MODE`. |
| "Hooks are discovered from `gateway/builtin_hooks/`(an extension point — currently empty in the shipped distribution; `_register_builtin_hooks()` is a no-op stub) and `~/.hermes/hooks/`(user-installed)." | Gateway Internals page, Hooks | Confirms there are currently zero shipped built-in gateway hooks; the directory exists purely as a future extension point. |
| "Plugins can register the 24 lifecycle events currently accepted by `hermes_cli.plugins.VALID_HOOKS`." | Plugins page, Available hooks | The event-count claim that does not reconcile with the primary page's own catalog table (23 rows counted) — flagged in Gaps. |
| "These categories describe current behavior rather than defining future naming rules. Plugin middleware remains a separate registry/surface." | Plugins page, Available hooks | Repeats/reinforces the middleware-is-separate boundary already noted on the Hooks page. |
| "General plugins and user-installed backends are disabled by default — discovery finds them... but nothing with hooks or tools loads until you add the plugin's name to `plugins.enabled` in `~/.hermes/config.yaml`." | Plugins page, Plugins are opt-in | Gate that must be satisfied before ANY plugin-registered hook can ever fire — a hook can be perfectly coded and registered in `register(ctx)` and still never run if the plugin isn't in `plugins.enabled`. |
| "`disabled:` [is an] optional deny-list — always wins if a name appears in both" | Plugins page, Plugins are opt-in (config snippet) | Precedence rule: `disabled` beats `enabled` if a plugin name appears in both lists. |
| "When you upgrade to a version of Hermes that has opt-in plugins (config schema v21+), any user plugins already installed under `~/.hermes/plugins/` that weren't already in `plugins.disabled` are automatically grandfathered into `plugins.enabled`... Bundled standalone plugins are NOT grandfathered — even existing users have to opt in explicitly." | Plugins page, Migration for existing users | Upgrade-safety fact: user plugins keep working across the opt-in migration, bundled ones do not. |
| "Per-hook context is capped at `10,000` characters by default. Anything above the cap is written to `$HERMES_HOME/hook_outputs/<session_id>/<uuid>.txt` and replaced with a head/tail preview plus the saved path." | Build a Hermes Plugin guide, Oversized-context spill | Load-bearing fact absent from the primary Hooks page — critical for any `pre_llm_call` hook injecting large context blobs. |
| "`ctx._cli_ref` is only populated in an **interactive CLI** session. It is `None` in the gateway, in non-interactive `hermes chat -q` runs, and in **kanban-spawned worker sessions** — so any plugin logic that reaches through `_cli_ref` silently no-ops in exactly those contexts." | Build a Hermes Plugin guide, Act from inside a hook | Critical portability warning: code that depends on `ctx._cli_ref` will silently fail in 3 of the most common stage-080 execution contexts (gateway, headless CLI, kanban worker). |
| "`ctx.dispatch_tool(name, args)` — invoke any registered tool (built-in or plugin)... Works from hook callbacks regardless of which process the hook fires in." | Build a Hermes Plugin guide, Act from inside a hook | The recommended, portable alternative to `ctx._cli_ref` for acting from a hook. |
| "For running a full `hermes <subcommand>`... shell out with the `terminal` tool via `ctx.dispatch_tool("terminal", {...})` — there is no in-process slash-command bridge for headless worker sessions" | Build a Hermes Plugin guide, Act from inside a hook | Directly actionable pattern for a hook that needs to run a `hermes` CLI subcommand from within a worker/gateway context. |
| "Auto-approve any unseen shell hooks declared in `config.yaml` without a TTY prompt. Equivalent to `--accept-hooks` or `hooks_auto_accept: true`." | Environment Variables reference, `HERMES_ACCEPT_HOOKS` row | Exact, reference-grade definition (matches the Hooks page's own description, cross-checked). |
| "Troubleshooting mode: disable ALL customizations — skips plugin discovery, MCP server loading, and shell-hook registration. Set automatically by `--safe-mode`" | Environment Variables reference, `HERMES_SAFE_MODE` row | Confirms `HERMES_SAFE_MODE` disables shell-hook registration entirely (and plugin hooks transitively, since plugin discovery is skipped) — the definitive "kill switch" for all hook systems except gateway hooks (not explicitly listed as disabled by safe mode; flagged as a minor gap). |
| "Inspect shell-script hooks declared in `~/.hermes/config.yaml`, test them against synthetic payloads, and manage the first-use consent allowlist at `~/.hermes/shell-hooks-allowlist.json`." | CLI Commands reference, `hermes hooks` | Reference-grade restatement confirming the Hooks page's own CLI table is accurate. |

---

## 5. Reference tables

### 5a. The four hook systems (comparison)

| Dimension | Shell hooks | Plugin hooks | Gateway hooks | Outbound webhooks |
| --- | --- | --- | --- | --- |
| Declared in | `hooks:` block in `~/.hermes/config.yaml` | `register()` in a `plugin.yaml` plugin | `HOOK.yaml`+`handler.py` directory | `hooks.outbound:` list in `~/.hermes/config.yaml` |
| Lives under | `~/.hermes/agent-hooks/` (by convention) | `~/.hermes/plugins/<name>/` | `~/.hermes/hooks/<name>/` | n/a (remote HTTP endpoint) |
| Language | Any (Bash, Python, Go binary, …) | Python only | Python only | n/a (HTTP receiver, any language) |
| Runs in | CLI + Gateway | CLI + Gateway | Gateway only | CLI + Gateway (fires wherever the underlying event fires) |
| Events | `VALID_HOOKS` (incl. `subagent_stop`) | `VALID_HOOKS` | Gateway lifecycle (`gateway:startup`, `agent:*`, `command:*`, `session:*`, `reaction:*`) | Any event from the plugin-hook set |
| Can block a tool call | Yes (`pre_tool_call`, exit code 2 or block JSON) | Yes (`pre_tool_call`) | No | No (notify-only) |
| Can inject LLM context | Yes (`pre_llm_call`) | Yes (`pre_llm_call`) | No | No |
| Consent | First-use prompt per `(event, command)` pair | Implicit (Python plugin trust via `plugins.enabled`) | Implicit (directory trust) | None (but gated by `HERMES_SAFE_MODE=1`) |
| Inter-process isolation | Yes (subprocess) | No (in-process) | No (in-process) | Yes (separate HTTP process/service) |
| Registration order relative to others | Second (`register_from_config()`, after Python plugins) | First (`discover_and_load()`) | n/a (separate `HookRegistry`, gateway-only) | n/a (separate delivery queue) |

Source: Hooks page § Shell Hooks § Comparison at a glance (Shell/Plugin/Gateway columns are a verbatim QUOTE table); Outbound Webhooks column is a PARAPHRASE synthesized from the Outbound Webhooks section, since the page never places webhooks in that comparison table itself.

### 5b. Plugin-hook event inventory (complete — 23 events found; page claims 24, see Gaps §9)

| Event | Category | Exact timing and return behavior | Explicit payload fields | Privacy / sensitivity |
| --- | --- | --- | --- | --- |
| `pre_tool_call` | Directive/control | Once before execution; first valid `block` or `approve` directive wins. | `tool_name`, `args`, `task_id`, `session_id`, `tool_call_id`, `turn_id`, `api_request_id`, `middleware_trace` | Raw arguments may contain user content, paths, commands, or secrets. |
| `post_tool_call` | Observer | After blocked, error, or successful result; return ignored. | `tool_name`, `args`, `result`, `task_id`, `session_id`, `tool_call_id`, `turn_id`, `api_request_id`, `duration_ms`, `status`, `error_type`, `error_message`, `middleware_trace` | Result/error text may contain arbitrary tool or user content and secrets. |
| `transform_tool_result` | Transform | After `post_tool_call`, before conversation append; first string replaces the result. | `tool_name`, `args`, `result`, `task_id`, `session_id`, `tool_call_id`, `turn_id`, `api_request_id`, `duration_ms`, `status`, `error_type`, `error_message` | Exposes the full model-bound result and arguments. |
| `transform_terminal_output` | Transform | After bounded foreground process capture, before final output limiting; first string replaces output. | `command`, `output`, `returncode`, `task_id`, `env_type` | Command/output may contain credentials. |
| `pre_llm_call` | Directive/control | Once per turn before the loop; all valid string/`{"context": ...}` returns are joined and injected into the user message. | `session_id`, `task_id`, `turn_id`, `user_message`, `conversation_history`, `is_first_turn`, `model`, `platform`, `parent_session_id`, `sender_id` | Full user message and conversation history. |
| `post_llm_call` | Observer | Successful, non-interrupted turn finalization; return ignored. | `session_id`, `task_id`, `turn_id`, `user_message`, `assistant_response`, `conversation_history`, `model`, `platform` | Full prompt, response, and history. |
| `transform_llm_output` | Transform | Before `post_llm_call` and final delivery; first non-empty string replaces the response. | `response_text`, `session_id`, `model`, `platform` | Full final assistant text. |
| `pre_verify` | Directive/control | At the bounded edited-code verify gate; first valid continue/block-stop directive keeps the turn going. | `session_id`, `platform`, `model`, `coding`, `attempt`, `final_response`, `changed_paths` | Draft response and changed paths. |
| `pre_api_request` | Observer | Per provider attempt, immediately before the request; return ignored. | `task_id`, `turn_id`, `api_request_id`, `session_id`, `user_message`, `conversation_history`, `platform`, `model`, `provider`, `base_url`, `api_mode`, `api_call_count`, `retry_count`, `request_messages`, `message_count`, `tool_count`, `approx_input_tokens`, `request_char_count`, `max_tokens`, `started_at`, `middleware_trace`, `request` | High sensitivity: legacy `user_message`, `conversation_history`, and `request_messages` are intentionally raw; prefer sanitized `request`. |
| `post_api_request` | Observer | After normalized provider success; return ignored. | `task_id`, `turn_id`, `api_request_id`, `session_id`, `platform`, `model`, `provider`, `base_url`, `api_mode`, `api_call_count`, `api_duration`, `started_at`, `ended_at`, `finish_reason`, `message_count`, `response_model`, `response`, `usage`, `assistant_message`, `assistant_content_chars`, `assistant_tool_call_count` | Sanitized `response` is available, but raw normalized `assistant_message` may contain model/user content; `usage` is accounting data. |
| `api_request_error` | Observer | On each failed provider attempt; return ignored. | `task_id`, `turn_id`, `api_request_id`, `session_id`, `platform`, `model`, `provider`, `base_url`, `api_mode`, `api_call_count`, `api_duration`, `started_at`, `ended_at`, `status_code`, `retry_count`, `max_retries`, `retryable`, `reason`, `error`, `request` | Error text may contain provider/user data; `request` is intended to be sanitized. |
| `on_session_start` | Observer | First turn of a new session; return ignored. | `session_id`, `model`, `platform` | Identifiers and routing metadata only. |
| `on_session_end` | Observer | Canonically at each turn finalization; CLI/TUI exits have additional reduced legacy shapes. Return ignored. | Canonical: `session_id`, `task_id`, `turn_id`, `completed`, `failed`, `interrupted`, `turn_exit_reason`, `model`, `platform`; exit paths may add `reason`/`api_request_id` and omit fields. | IDs, model/platform, and outcome; canonical payload has no message body. |
| `on_session_finalize` | Observer | CLI/TUI/gateway teardown through `finalize_session`; gateway shutdown or expiry may finalize without a reset. Return ignored. | Surface-dependent `session_id`, `platform`, optionally `reason`, `old_session_id`, `new_session_id` | Session and routing identifiers. |
| `on_session_reset` | Observer | CLI/TUI session boundary and gateway after the replacement session exists; return ignored. | CLI: `session_id`, `platform`, `reason`; TUI: `session_id`, `platform`; gateway: those plus `reason`, `old_session_id`, `new_session_id` | Session and routing identifiers. |
| `on_skill_lifecycle` | Observer | After an authoritative skill-usage state change; return ignored. | `action`, `skill_name`, `provenance`, `task_id`, `session_id`, `use_count`, `reused`, `reuse_after_patch` | Exposes the local skill name and provenance. |
| `subagent_start` | Observer | Child constructed and about to run; return ignored. | `parent_session_id`, `parent_turn_id`, `parent_subagent_id`, `child_session_id`, `child_subagent_id`, `child_role`, `child_goal` | Child goal may contain user/project content. |
| `subagent_stop` | Observer | Child exit; return ignored. | `parent_session_id`, `parent_turn_id`, `child_session_id`, `child_role`, `child_summary`, `child_status`, `tool_call_history`, `duration_ms` | Summary and redacted tool-history metadata may reveal project structure. |
| `pre_gateway_dispatch` | Directive/control | Incoming non-internal message before auth/pairing/dispatch; first valid `skip`, `rewrite`, or `allow` controls flow. | `event`, `gateway`, `session_store` | Extremely privileged in-process objects expose inbound user/routing data and host handles. |
| `pre_approval_request` | Observer | Before prompted or smart approval; return ignored. | `command`, `description`, `pattern_key`, `pattern_keys`, `session_key`, `surface`, `turn_id`, `tool_call_id` | Command may contain secrets; smart observer preparation force-redacts, but surfaces do not all have identical redaction. |
| `post_approval_response` | Observer | After a decision, timeout, or gateway notification failure; return ignored. | `command`, `description`, `pattern_key`, `pattern_keys`, `session_key`, `surface`, `turn_id`, `tool_call_id`, `choice`; smart path may add `decided_by` | Same command sensitivity plus decision metadata. |
| `kanban_task_claimed` | Observer | After claim commit, in dispatcher process before worker spawn; return ignored. | `task_id`, `profile_name`, `board`, `assignee`, `run_id` | Board/task/profile/assignee identifiers. |
| `kanban_task_completed` | Observer | After completion and cleanup, usually in worker process; return ignored. | `task_id`, `profile_name`, `board`, `assignee`, `run_id`, `summary` | Summary may contain project/user content. |
| `kanban_task_blocked` | Observer | After a blocked transition; the dependency-wait path fires before its transaction exits. Return ignored. | `task_id`, `profile_name`, `board`, `assignee`, `run_id`, `reason` | Reason may contain project/user content. |

Source: Hooks page § Plugin Hooks § Shipped plugin-hook catalog (verbatim QUOTE table, reproduced in full).

### 5c. Gateway hook events

**Primary source (Hooks page, Available Events table) — treat as authoritative:**

| Event | When it fires | Context keys |
| --- | --- | --- |
| `gateway:startup` | Gateway process starts | `platforms` (list of active platform names) |
| `session:start` | New messaging session created | `platform`, `user_id`, `session_id`, `session_key` |
| `session:end` | Session ended (before reset) | `platform`, `user_id`, `session_key` |
| `session:reset` | User ran `/new` or `/reset` | `platform`, `user_id`, `session_key` |
| `session:compress` | Context compression completed for a session | `platform`, `session_id`, `old_session_id` (empty when compacted in place), `in_place` (bool), `compression_count` |
| `agent:start` | Agent begins processing a message | `platform`, `user_id`, `chat_id`, `thread_id`, `chat_type`, `session_id`, `message` (truncated to 500 chars) |
| `agent:step` | Each iteration of the tool-calling loop | `platform`, `user_id`, `session_id`, `iteration`, `tool_names` |
| `agent:end` | Agent finishes processing | same keys as `agent:start`, plus `response` (truncated to 500 chars) |
| `reaction:added` | Emoji reaction added (Slack adapter currently; requires `reactions:read` scope + `reaction_added` bot event subscription; bot must be channel member) | `platform`, `reaction`, `user_id`, `item_user_id`, `item_type`, `channel_id`, `message_ts`, `team_id`, `event_ts`, `raw_event` |
| `reaction:removed` | Emoji reaction removed (requires `reaction_removed` bot event subscription) | same shape as `reaction:added` |
| `command:*` (wildcard) | Any slash command executed | `platform`, `user_id`, `command`, `args` |

**Secondary source (Gateway Internals page, Gateway Hook Events table) — narrower, appears stale or incomplete relative to the primary table:**

| Event | When fired |
| --- | --- |
| `gateway:startup` | Gateway process starts |
| `session:start` | New conversation session begins |
| `session:end` | Session completes or times out |
| `session:reset` | User resets session with `/new` |
| `agent:start` | Agent begins processing a message |
| `agent:step` | Agent completes one tool-calling iteration |
| `agent:end` | Agent finishes and returns response |
| `command:*` | Any slash command is executed |

This table omits `session:compress`, `reaction:added`, and `reaction:removed` entirely, and describes `session:end` and `agent:step` slightly differently ("completes or times out" vs. "ended (before reset)"; "completes one tool-calling iteration" vs. "each iteration of the tool-calling loop" — the latter pair are equivalent in meaning, the former pair are a substantive difference: "times out" is not mentioned on the primary page). See Gap in §9.

### 5d. Shell-hook config schema fields

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `hooks.<event_name>` | list of entries | — | — | `<event_name>` "must be in `VALID_HOOKS`" |
| `matcher` | regex string | Optional; used for `pre`/`post_tool_call` only | — | undocumented what happens if supplied for a non-tool event beyond general "unknown keys... ignored" rule |
| `command` | string | Required | — | runs via `shlex.split`, `shell=False`; missing → skip-with-warning |
| `timeout` | seconds (number) | Optional | `60` | capped at `300`, clamped with a warning if exceeded |
| `fail_closed` (alias `failClosed`) | bool | Optional | `false` | `pre_tool_call` only; warned+ignored on other events |
| `hooks_auto_accept` | bool | Optional (top-level, not per-entry) | `false` | see "Consent model" |
| `hooks.output_spill.enabled` | bool | Optional | `true` | source: Build a Hermes Plugin guide, not the primary Hooks page |
| `hooks.output_spill.max_chars` | int | Optional | `10000` | per-hook `pre_llm_call` context-injection cap |
| `hooks.output_spill.preview_head` | int | Optional | `500` | chars shown at top of overflow preview |
| `hooks.output_spill.preview_tail` | int | Optional | `500` | chars shown at bottom of overflow preview |
| `hooks.output_spill.directory` | path or `null` | Optional | `$HERMES_HOME/hook_outputs` | overflow file location |

Sources: Hooks page § Shell Hooks § Configuration schema (`hooks.<event>` through `hooks_auto_accept`, QUOTE); Build a Hermes Plugin guide § Oversized-context spill (`hooks.output_spill.*`, QUOTE).

### 5e. Outbound-webhook config schema fields

| Field | Required | Notes |
| --- | --- | --- |
| `name` | Optional | label for logs |
| `url` | Required | target HTTPS endpoint |
| `events` | Required | list, "any event from the plugin-hook set is valid" |
| `secret_env` | Optional (strongly recommended) | env var name holding HMAC secret; preferred over inline `secret:` |
| `secret` | Optional | inline literal — discouraged, keeps config file free of credentials is the stated goal of preferring `secret_env` instead |
| `timeout` | Optional | "per-attempt seconds (1–60)" |
| `matcher` | Optional | regex, "tool-scoped events only" |

Source: Hooks page § Outbound Webhooks § Configuration (QUOTE, config YAML example + prose).

### 5f. `hermes hooks` CLI commands

| Command | What it does | Cross-checked against |
| --- | --- | --- |
| `hermes hooks list` (alias `ls`) | Dump configured hooks with matcher, timeout, and consent status | Hooks page + CLI Commands reference (both agree) |
| `hermes hooks test [--for-tool X] [--payload-file F]` | Fire every matching hook against a synthetic payload and print the parsed response | Hooks page (`--for-tool`/`--payload-file` flags only on Hooks page; CLI reference states the subcommand more tersely as `test <event>`) |
| `hermes hooks revoke <command>` (aliases `remove`, `rm`) | Remove every allowlist entry matching `<command>` (takes effect on next restart) | Hooks page names it "revoke"; CLI Commands reference confirms aliases `remove`/`rm` |
| `hermes hooks doctor` | For every configured hook: check exec bit, allowlist status, mtime drift, JSON output validity, and rough execution time | Hooks page + CLI Commands reference (both agree) |

### 5g. Relevant environment variables

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `HERMES_ACCEPT_HOOKS` | flag (`1`/unset) | unset | "Auto-approve any unseen shell hooks declared in `config.yaml` without a TTY prompt. Equivalent to `--accept-hooks` or `hooks_auto_accept: true`." |
| `HERMES_SAFE_MODE` | flag | unset | "Troubleshooting mode: disable ALL customizations — skips plugin discovery, MCP server loading, and shell-hook registration. Set automatically by `--safe-mode`(which also sets the two flags above)." Gateway hooks are not explicitly listed as disabled by this flag — see Gap §9. |
| `HERMES_ENABLE_PROJECT_PLUGINS` | flag (`true`/`1`) | unset (disabled) | Gates loading of project-local plugins under `./.hermes/plugins/`, which could carry `provides_hooks`. (Source: Plugins page, not Environment Variables reference — the reference page was not searched for this specific var; PARAPHRASE from Plugins page text.) |

### 5h. `plugin.yaml` manifest fields relevant to hooks

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Required | plugin identifier |
| `version` | string | Required (shown in all examples) | e.g. `"1.0.0"` |
| `description` | string | shown in all examples | human-readable summary |
| `provides_tools` | list of strings | Optional | tool names the plugin registers |
| `provides_hooks` | list of strings | Optional | hook event names the plugin registers — example shown: `- post_tool_call` |
| `author` | string | Optional | — |
| `requires_env` | list (simple string or rich object w/ `name`/`description`/`url`/`secret`) | Optional | gates loading on env vars; prompted during `hermes plugins install` |

Source: Build a Hermes Plugin guide § Step 2: Write the manifest (QUOTE).

---

## 6. Official examples

### Gateway hook — `HOOK.yaml` + `handler.py` (long-task alert)

```yaml
# ~/.hermes/hooks/long-task-alert/HOOK.yaml
name: long-task-alert
description: Alert when agent is taking many steps
events:
  - agent:step
```

```python
# ~/.hermes/hooks/long-task-alert/handler.py
import os
import httpx

THRESHOLD = 10
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_HOME_CHANNEL")

async def handle(event_type: str, context: dict):
    iteration = context.get("iteration", 0)
    if iteration == THRESHOLD and BOT_TOKEN and CHAT_ID:
        tools = ", ".join(context.get("tool_names", []))
        text = f"⚠️ Agent has been running for {iteration} steps. Last tools: {tools}"
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": text},
            )
```

Source: Hooks page § Gateway Event Hooks § Examples (verbatim).

### Plugin hook — `pre_tool_call` audit log

```python
import json, logging
from datetime import datetime
logger = logging.getLogger(__name__)

def audit_tool_call(tool_name, args, task_id, **kwargs):
    logger.info("TOOL_CALL session=%s tool=%s args=%s",
                task_id, tool_name, json.dumps(args)[:200])

def register(ctx):
    ctx.register_hook("pre_tool_call", audit_tool_call)
```

Source: Hooks page § `pre_tool_call` § Examples (verbatim).

### Plugin hook — `pre_verify` scoped + one-shot pattern

```python
UI = (".tsx", ".jsx", ".css", ".scss")

def defer_ui_checks(coding, attempt, changed_paths, **kwargs):
    if attempt or not coding:
        return None  # one-shot, coding only
    if not all(p.endswith(UI) for p in changed_paths):
        return None  # only pure-UI edits
    return {
        "action": "continue",
        "message": "This is UI work — don't run tests/lints yet; ask the user to "
                   "eyeball it first, and clean the diff before any commit.",
    }

def register(ctx):
    ctx.register_hook("pre_verify", defer_ui_checks)
```

Source: Hooks page § `pre_verify` § Example (verbatim).

### Shell hook — block destructive terminal commands (config + script)

```yaml
hooks:
  pre_tool_call:
    - matcher: "terminal"
      command: "~/.hermes/agent-hooks/block-rm-rf.sh"
      timeout: 5
```

```bash
#!/usr/bin/env bash
# ~/.hermes/agent-hooks/block-rm-rf.sh
payload="$(cat -)"
cmd=$(echo "$payload" | jq -r '.tool_input.command // empty')
if echo "$cmd" | grep -qE 'rm[[:space:]]+-rf?[[:space:]]+/'; then
  printf '{"decision": "block", "reason": "blocked: rm -rf / is not permitted"}\n'
else
  printf '{}\n'
fi
```

Source: Hooks page § Shell Hooks § Worked examples (verbatim).

### Shell hook — manual allowlist entry

```json
{
  "approvals": [
    {
      "event": "post_llm_call",
      "command": "/home/hermes/.hermes/hooks/my-hook.py"
    }
  ]
}
```

Source: Hooks page § Manual allowlisting (verbatim).

### Outbound webhook — config + signature verification

```yaml
hooks:
  outbound:
    - name: ci-notify
      url: https://ci.example.com/hermes-events
      events: [on_session_end, subagent_stop]
      secret_env: HERMES_OUTBOUND_WEBHOOK_SECRET
      timeout: 10
    - name: tool-monitor
      url: https://metrics.example.com/hooks/hermes
      events: [post_tool_call]
      matcher: "terminal|delegate_task"
```

```python
import hashlib, hmac

def verify(body: bytes, header: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)
```

Source: Hooks page § Outbound Webhooks (verbatim, both blocks).

### Plugin — acting from inside a kanban lifecycle hook

```python
def register(ctx):
    def on_blocked(*, task_id, reason=None, **kw):
        # Runs in the worker process; ctx._cli_ref is None here.
        ctx.dispatch_tool("kanban_comment", {
            "task_id": task_id,
            "comment": f"[{ctx.profile_name}] auto-noted block: {reason}",
        })

    ctx.register_hook("kanban_task_blocked", on_blocked)
```

Source: Build a Hermes Plugin guide § Act from inside a hook (verbatim).

### Built-in plugin — disk-cleanup's hook table (worked production example)

| Hook | Behaviour |
| --- | --- |
| `post_tool_call` | "When `write_file`/`terminal`/`patch` creates a file matching `test_*`, `tmp_*`, or `*.test.*` inside `HERMES_HOME` or `/tmp/hermes-*`, track it silently as `test`/`temp`/`cron-output`." |
| `on_session_end` | "If any test files were auto-tracked during the turn, run the safe `quick` cleanup and log a one-line summary. Stays silent otherwise." |

Source: Built-in Plugins page § disk-cleanup (verbatim table).

---

## 7. Recommendations found

- "Only reference scripts you wrote or fully reviewed." (Hooks page § Security)
- "Keep scripts inside `~/.hermes/agent-hooks/` so the path is easy to audit." (Hooks page § Security)
- "Re-run `hermes hooks doctor` after you pull a shared config to spot newly-added hooks before they register." (Hooks page § Security)
- "If your config.yaml is version-controlled across a team, review PRs that change the `hooks:` section the same way you'd review CI config." (Hooks page § Security)
- "Set `fail_closed: true`... to invert that [fail-open default]" for security-gate-style hooks specifically — "That is the right default for observability hooks — but wrong for security gates. A crashed secret-scanner must not silently allow the tool call it was supposed to vet." (Hooks page § Fail-open vs fail-closed)
- "Non-TTY runs (gateway, cron, CI) need one of these three [escape hatches] — otherwise any newly-added hook silently stays un-registered." (Hooks page § Consent model) — operational recommendation for any automated/headless deployment (directly relevant to stage 080's dispatcher/worker processes).
- "prefer `secret_env`(the name of an environment variable...) over an inline `secret:` literal, so the config file stays free of credentials." (Hooks page § Outbound Webhooks Configuration)
- "Point the `url` at the final endpoint" for outbound webhooks, since "following a redirected POST would silently drop the signed payload." (Hooks page § Outbound Webhooks Delivery semantics)
- "Reject stale events by checking `timestamp` against your clock with a tolerance window (5 minutes is the common default)." (Hooks page § Outbound Webhooks Wire format) — receiver-side hardening recommendation.
- "Dedupe on `delivery_id`... Hermes retries failed deliveries once, so the same id can legitimately arrive twice." (Hooks page § Outbound Webhooks Wire format)
- "All callbacks should accept `**kwargs` for forward compatibility." (Build a Hermes Plugin guide § Hook reference — restates the Hooks page's own general rule)
- "Make it idempotent: the hook re-fires after each nudge, so gate on `attempt`" for `pre_verify` hooks specifically. (Hooks page § `pre_verify`)
- "Keep your callback fast; push expensive work to a background queue" for `subagent_stop` under heavy delegation. (Hooks page § `subagent_stop` info-box)
- "prefer sanitized `request`" over the legacy raw `user_message`/`conversation_history`/`request_messages` fields in `pre_api_request`. (Hooks page § Shipped plugin-hook catalog, `pre_api_request` row)
- "For events whose block directive is not honored... exit 2 is treated like any other non-zero exit" — implicit recommendation to only rely on exit-code-2 blocking for `pre_tool_call`. (Hooks page § Exit code 2 = block)

---

## 8. Boundary notes

- **`hermes-configuration`** — General `config.yaml` schema authority, including precedence rules for `plugins.enabled`/`plugins.disabled` keys and the `hooks.output_spill.*` keys beyond their hook-specific meaning captured here.
- **`hermes-kanban`** — Owns the three kanban hook names (`kanban_task_claimed`/`kanban_task_completed`/`kanban_task_blocked`) as board/task lifecycle semantics, the dispatcher-vs-worker process architecture itself, and any kanban-specific board/task/board-switching UI or CLI. This dossier captures only the *general* hook mechanics those three hooks sit on (payload shape, observer-only category, durability-after-commit guarantee, process-split as a firing-location fact).
- **`hermes-skills`** — Owns skills-system mechanics (progressive disclosure, Skills Hub, agent-managed skill authoring/curation) beyond the single `on_skill_lifecycle` hook point captured here.
- **`hermes-managed-scope`** — Owns admin-tier pins under `/etc/hermes` and fleet-wide secret/config precedence; not investigated for whether admin pins can force plugin/hook enablement — flagged as a gap for that skill's own research, not chased here.
- **`hermes-sessions`** — Owns session storage, resumption, search, and per-platform session tracking; this dossier captures only the *hook events* tied to the session lifecycle (`on_session_start`/`on_session_end`/`on_session_finalize`/`on_session_reset`), not the underlying `SessionStore`/SQLite persistence mechanics (only named in passing via the Gateway Internals Key Files table).
- **`hermes-cli`** — Owns the full CLI/slash-command reference; this dossier captures only the hooks-specific `hermes hooks <subcommand>` family and the `--safe-mode`/`--accept-hooks` flags as they relate to hooks.
- **General Plugin-system mechanics beyond hook registration** (no owning skill, per assignment — recorded, not chased): tool registration (`ctx.register_tool`), slash-command registration (`ctx.register_command`), CLI subcommand registration (`ctx.register_cli_command`), platform-adapter registration (`ctx.register_platform`), memory/context-engine/model-provider/image-gen/video-gen/TTS/STT provider registration, `ctx.inject_message()`, `ctx.llm.complete()`, and the general plugin discovery/opt-in system's non-hook aspects (tool override, `plugins.enabled` grandfathering for non-hook plugins). All of these are documented on the Plugins and Build a Hermes Plugin pages but are out of scope for a hooks-focused skill.

---

## 9. Gaps & open questions

1. **Event-count discrepancy (23 vs. 24).** The Plugins page states "Plugins can register the 24 lifecycle events currently accepted by `hermes_cli.plugins.VALID_HOOKS`," but the Hooks page's own "Shipped plugin-hook catalog" table — which the Hooks page calls the authoritative source for "exact timing, return handling, payload fields, and privacy notes" — lists exactly 23 distinct hook names (verified by direct count in §5b above). No official page I could reach names a 24th event. This could be an off-by-one in the prose count, a recently-added-but-undocumented event, or a hook documented elsewhere I did not locate (e.g. a fetch-only reference table I didn't check). **Do not guess the missing event's name or behavior.**
2. **Gateway-event-table divergence.** The Hooks page's "Available Events" table (10 rows + wildcard, including `session:compress`, `reaction:added`, `reaction:removed`) and the Gateway Internals page's "Gateway Hook Events" table (8 rows, missing those three, and phrasing `session:end` as "completes or times out" vs. the Hooks page's "ended (before reset)") disagree. I treated the Hooks page as authoritative per its role as the "canonical" hooks reference, but this is an unresolved conflict between two official pages, not a confirmed fact — flagged rather than silently resolved.
3. **`HERMES_SAFE_MODE` and gateway hooks.** The env-var reference states safe mode "skips plugin discovery, MCP server loading, and shell-hook registration" — it does not mention gateway hooks (`~/.hermes/hooks/`) at all. It is undocumented whether `--safe-mode`/`HERMES_SAFE_MODE` also disables gateway-hook discovery (`HookRegistry.discover_and_load()`) or only the three explicitly named systems. Do not assume either way.
4. **`gateway/builtin_hooks/` extension mechanics.** The Gateway Internals page states this directory is "an extension point — currently empty in the shipped distribution" with a no-op `_register_builtin_hooks()` stub, but no official page documents the manifest/registration format a maintainer would use to add a hook there (as opposed to the well-documented `~/.hermes/hooks/<name>/HOOK.yaml` user format). This is a source-code-only fact (`source: repository, not docs`) that I did not fetch (out of scope: the assignment only authorizes reading the repository "ONLY if the docs site links to it," and no such link was found on the pages I read).
5. **"Plugin middleware is a separate registry and surface, not another hook category."** This sentence appears twice (Hooks page general rules; Plugins page Available-hooks note) but no page I read (or was directed to) documents what plugin middleware actually is, how it's registered, or its relationship to `middleware_trace` (a payload field that appears on `pre_tool_call`/`post_tool_call`/`transform_tool_result`/`pre_api_request` in the event table). This looks like a real, documented-elsewhere-or-not-yet-documented subsystem with no owning skill per the assignment's explicit scope note — flagged for a future research pass, not chased here.
6. **`security-guidance` built-in plugin's exact hook name.** The Built-in Plugins page describes its behavior ("appends a `⚠️ Security guidance` block to the tool's result... file is still written") in a way that matches either `post_tool_call` (observer, append-only) or `transform_tool_result` (replaces the result string) — the page never names the hook explicitly, and I could not disambiguate without reading the plugin's source, which is out of scope. Recorded in §3 Page maps as PARAPHRASE, not asserted as fact anywhere else in this dossier.
7. **Exact behavior of `hermes hooks test` without flags vs. with `--for-tool`/`--payload-file`.** The Hooks page documents both flags; the CLI Commands reference states the subcommand more tersely as `test <event>` with no flag documentation. Whether `<event>` is a positional argument distinct from `--for-tool`, or whether the CLI reference is simply abbreviating, is not fully reconciled between the two pages — low-stakes gap, did not chase further.
8. **No live Hermes seat was available to this research run** (per assignment scope — this was documentation-only research, not implementation or live validation). All of the above is unvalidated against actual `hermes hooks doctor`/`hermes hooks test` output; the skill's "Validation" section should still require live-seat testing before landing a hook per the existing placeholder's `hermes-hooks/SKILL.md` validation bullet ("Hook tested on a live seat before landing where a seat is available").

---

## 10. Suggested SKILL.md inputs

*(Input for the reviewer, not an edit. Each line cites the table row or normative statement it derives from.)*

**Key concepts to state up front:**

- Hermes has four distinct hook/notification systems (gateway hooks, plugin hooks, shell hooks, outbound webhooks) with different languages, runtime scopes, and block/inject capabilities — pick the right one before writing any code. (§5a comparison table; Normative statements row 1.)
- Plugin `pre_tool_call` hooks always get first refusal over shell `pre_tool_call` hooks for the same event, because Python plugins register before shell hooks in the same dispatcher. (Normative statements, "Ordering and precedence" quote.)
- A `pre_llm_call` hook injects into the user message, never the system prompt, specifically to preserve the provider prompt cache across turns — and injected content is capped at 10,000 characters by default with overflow spilled to a file the model can `read_file`. (Normative statements, `pre_llm_call` context-injection rows; §5d config table.)
- `ctx._cli_ref` silently returns `None`/no-ops in gateway, headless `hermes chat -q`, and kanban-worker contexts — use `ctx.profile_name` and `ctx.dispatch_tool()` instead for anything that must work everywhere a stage-080 hook might run. (Normative statements, "act from inside a hook" rows.)
- Shell hooks are the only hook system that can silently stay unregistered in non-TTY (gateway/cron/CI) contexts unless one of three explicit escape hatches (`--accept-hooks`, `HERMES_ACCEPT_HOOKS=1`, `hooks_auto_accept: true`) is set — directly relevant to any stage-080 automated/headless deployment. (Normative statements, "Non-TTY runs" quote; §5g env var table.)

**Workflow steps (extending the placeholder's existing 3-step workflow):**

1. Read `references/source-capture.md`, then identify which of the four hook systems fits the use case using §5a's comparison table (block-capable? needs cross-process isolation? needs to run in CLI too, not just gateway?).
2. For plugin hooks, confirm the target event exists and its documented payload/category/timing in the shipped plugin-hook catalog (§5b) before writing the callback — never assume a payload field is present (`**kwargs` is mandatory).
3. For shell hooks in a headless/CI/cron/stage-080-dispatcher context, explicitly set one of the three consent escape hatches — otherwise the hook silently never registers. (Normative statements, "Non-TTY runs" quote.)
4. If the hook needs to act (not just observe) from inside a callback, use `ctx.dispatch_tool()`/`ctx.profile_name`, not `ctx._cli_ref`, unless the hook is verified to run only in an interactive CLI session.
5. Cite the official section relied on in the PR (existing placeholder rule) — use the per-hook `###` anchor on the Hooks page (e.g. `#pre_verify`) since each hook has its own addressable section.

**Validation commands to consider adding:**

- `hermes hooks list` — verify a shell/outbound hook is configured and its consent status, before claiming it's wired up. (§5f.)
- `hermes hooks test [--for-tool X] [--payload-file F]` — fire a synthetic payload against configured hooks to verify behavior without waiting for a live trigger. (§5f; Hooks page § The `hermes hooks` CLI.)
- `hermes hooks doctor` — check exec bit, allowlist status, mtime drift (script-edited-without-reapproval detection), JSON validity, and execution timing for every configured shell hook — recommended specifically "after you pull a shared config." (§5f; Recommendations §7.)
- For plugin hooks: `hermes plugins list` to confirm the hook's owning plugin is actually in `plugins.enabled` (a correctly-coded `ctx.register_hook()` call never fires if the plugin itself isn't enabled). (Normative statements, "General plugins and user-installed backends are disabled by default" quote.)

---

## Reviewer addendum (2026-08-12)

### Gap 1 RESOLVED: the event count is 24, and the docs agree with themselves

The dossier flagged "23 vs 24" as its biggest gap. Reviewer extracted
`VALID_HOOKS` from the shipped source
(https://raw.githubusercontent.com/NousResearch/hermes-agent/main/hermes_cli/plugins.py):
exactly 24 entries — api_request_error, kanban_task_blocked,
kanban_task_claimed, kanban_task_completed, on_session_end,
on_session_finalize, on_session_reset, on_session_start,
on_skill_lifecycle, post_api_request, post_approval_response,
post_llm_call, post_tool_call, pre_api_request, pre_approval_request,
pre_gateway_dispatch, pre_llm_call, pre_tool_call, pre_verify,
subagent_start, subagent_stop, transform_llm_output,
transform_terminal_output, transform_tool_result.

This matches the dossier's own §5b catalog table one-to-one — the table
itself contains 24 rows; the dossier's "23" was a summary count error, not
a documentation inconsistency. The Plugins page's "24 lifecycle events"
claim is CORRECT. (`source: repository` used only to adjudicate the count;
each event's semantics remain cited to the docs catalog.)

### Single-sourced Build-a-Plugin facts: verified from doc source

The rendered guide page returns empty content to the reviewer's fetch tool
(twice, plus trailing-slash variant) — the markdown source in the
repository verifies all four single-sourced facts verbatim, at these line
anchors (main branch, 2026-08-12): the kanban after-commit + process-split
paragraph (line ~683), the 10,000-char per-hook cap with
`$HERMES_HOME/hook_outputs/<session_id>/<uuid>.txt` spill and
`hooks.output_spill` config block (lines ~706-715), the `ctx._cli_ref`
None-in-gateway/headless/kanban-workers warning (line ~926), and
`ctx.dispatch_tool` portability + "no in-process slash-command bridge"
(lines ~929, 887-922). Operational note for future runs: fetch this
guide's content from the repo markdown, not the rendered page.

### Historical bug check (reviewer-initiated)

GitHub issue #2817 "[Bug]: Plugin hooks pre_llm_call, post_llm_call,
on_session_start, on_session_end are documented but never invoked" is
CLOSED (2026-04-27). The current docs' detailed per-hook firing sections
postdate the fix. No live caveat needed beyond the standing
"validate on a live seat" rule.

### Corroboration note

The kanban-hooks durability guarantee ("fire after the board DB change
commits") is now triple-sourced: the kanban feature page (hermes-kanban
capture), the Build-a-Plugin guide (this capture), and the repo markdown
(reviewer verification) — all verbatim-consistent.
