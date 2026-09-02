---
name: hermes-hooks
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when designing or reviewing Hermes event hooks for stage 080: choosing
  among the four hook systems (gateway, plugin, shell, outbound webhooks),
  the 24-event plugin-hook catalog, firing semantics and ordering, blocking
  and context injection, consent for headless runs, and the hooks CLI. Do
  NOT use for kanban task semantics behind the kanban hooks (use
  hermes-kanban), skills mechanics behind on_skill_lifecycle (use
  hermes-skills), or hook config-key schema wiring (use
  hermes-configuration).
---

# Hermes Hooks

Use this skill for any stage 080 guard, stamper, watchdog trigger, or
observability wiring built on Hermes lifecycle events.

## Source Grounding

Read `references/source-capture.md` for provenance and
`references/official-doc-extraction.md` for the full validated extraction —
the complete 24-event catalog with timing/payload/privacy per event, all
config schemas, and verbatim examples. Official Hermes Agent documentation
(Nous Research) is the product authority.

## Key Concepts

### Four distinct hook systems — pick before you code

| | Language | Runs in | Can block | Can inject context |
|---|---|---|---|---|
| Plugin hooks | Python (in-process) | CLI + gateway | yes (`pre_tool_call`) | yes (`pre_llm_call`) |
| Shell hooks | any (subprocess) | CLI + gateway | yes (`pre_tool_call`) | yes (`pre_llm_call`) |
| Gateway hooks | Python (`HOOK.yaml`+`handler.py`) | gateway ONLY | no | no |
| Outbound webhooks | n/a (HTTP push) | wherever events fire | no — "they observe, never steer" | no |

"The CLI does not load gateway hooks" — anything that must also run in CLI
or worker sessions uses plugin or shell hooks. Hook callback errors are
isolated and logged, never crashing the agent; per-callback, so one bad
hook doesn't stop siblings.

### The plugin-hook event set (24 events)

Exactly 24 events in `VALID_HOOKS` (verified against the shipped source;
the docs catalog table lists all 24). Categories: directive/control
(`pre_tool_call`, `pre_llm_call`, `pre_verify`, `pre_gateway_dispatch`),
transforms (`transform_tool_result`, `transform_terminal_output`,
`transform_llm_output`), observers (everything else — returns ignored).
Every callback MUST accept `**kwargs`; correlation IDs (`turn_id`,
`task_id`, …) are hook-specific and may be absent — treat as opaque.
Shell hooks and outbound webhooks reuse this same event namespace.

### Firing semantics that get assumed wrong

- `pre_llm_call` fires ONCE PER TURN (not per API call), injects into the
  user message — never the system prompt (preserves the prompt cache) —
  capped at 10,000 chars/hook with overflow spilled to
  `$HERMES_HOME/hook_outputs/…` (tune via `hooks.output_spill`).
- `post_llm_call` / `transform_llm_output` fire only on successful,
  non-interrupted turns; `on_session_end` is the reliable always-fires
  cleanup point.
- Gateway session reset ordering: `on_session_finalize(old)` →
  `on_session_reset(new)` → `on_session_start(new)` on first inbound turn.
- `pre_verify` re-fires after each nudge — gate on `attempt` (idempotent),
  and it's bounded by `agent.max_verify_nudges` (default 3).
- `subagent_start`/`pre_approval_request` are observational — to block
  delegation or a command, the actionable point is `pre_tool_call`.
- Kanban hooks fire AFTER the board DB change commits (durable state,
  never holding the SQLite lock); `kanban_task_claimed` fires in the
  dispatcher process, completed/blocked in the worker.

### Blocking, ordering, and failure posture

Python plugin hooks register before shell hooks in the same dispatcher —
plugin block decisions win ties; "the first valid block wins". Shell exit
code 2 blocks `pre_tool_call` only (other events: warning, stdout still
parsed). Shell hooks are fail-open by default; set `fail_closed: true`
(`pre_tool_call` only) for security gates — "a crashed secret-scanner must
not silently allow the tool call it was supposed to vet".

### Consent and headless operation (stage 080 critical)

Shell hooks need first-use consent per `(event, command)` pair, persisted
to `~/.hermes/shell-hooks-allowlist.json`. **Non-TTY runs (gateway, cron,
CI, kanban workers) silently skip registering new hooks** unless one of:
`--accept-hooks`, `HERMES_ACCEPT_HOOKS=1`, or `hooks_auto_accept: true`.
Script edits are silently trusted (allowlist keys on the command string,
not a hash) — run `hermes hooks doctor` after pulling shared config.
`HERMES_SAFE_MODE=1` kills plugin discovery, MCP, and shell-hook
registration. Plugin hooks only fire if their plugin is in
`plugins.enabled` (`disabled` wins on conflict).

### Acting from inside a hook

`ctx._cli_ref` is `None` in the gateway, in `hermes chat -q`, and in
kanban-spawned workers — logic reaching through it silently no-ops in
exactly the contexts stage 080 runs. Use `ctx.profile_name` and
`ctx.dispatch_tool(name, args)` (works in every process, including
`kanban_*` tools); shell out via `dispatch_tool("terminal", …)` to run
`hermes` subcommands — there is no in-process slash-command bridge.

## Workflow

1. Pick the hook system from the comparison table (block-capable? CLI too?
   process isolation? notify-only?).
2. Look up the target event's timing/payload/privacy row in the extraction
   catalog before writing the callback — never assume a payload field.
3. For headless/stage 080 contexts, set a consent escape hatch explicitly,
   or the shell hook never registers.
4. Security gates: `fail_closed: true`; observability: leave fail-open;
   keep `subagent_stop`-scale callbacks fast (they serialize on the parent
   thread).
5. Outbound webhooks: `secret_env` over inline `secret` (unsigned targets
   are flagged by `hermes hooks list`); receivers dedupe on `delivery_id`
   and reject stale timestamps.
6. Test with synthetic payloads before relying on live triggers; cite the
   official per-hook section anchor in the PR (stage 080 official-first
   rule).

## Validation

```shell
hermes hooks list                        # configured hooks + consent status
hermes hooks test --for-tool X --payload-file F   # synthetic-payload firing
hermes hooks doctor                      # exec bit, allowlist, mtime drift
hermes plugins list                      # owning plugin actually enabled?
```

Validate on a live seat before landing — docs-only review cannot confirm a
hook actually fires in the target context.

## Pitfalls

- A perfectly-coded plugin hook never fires if the plugin isn't in
  `plugins.enabled` — check that before debugging the callback.
- Gateway hooks silently don't exist in CLI/worker sessions.
- A newly added shell hook in a non-TTY context silently stays
  unregistered without a consent escape hatch — the #1 headless trap.
- `hermes hooks list` lists configured shell/outbound hooks, NOT the
  available event vocabulary.
- `transform_llm_output` treats `""` as "no change"; the other two
  transforms accept `""` as a valid replacement.
- The manual allowlist format is an `approvals` array keyed on
  `(event, command)` — a path-keyed object with `sha256` does not approve
  anything.
- Multiple `pre_llm_call` injections join in plugin-directory-name
  alphabetical order — not registration or config order.
- The Gateway Internals page's event table is stale (missing
  `session:compress`, `reaction:*`) — cite the Hooks page's table.
- Historical note: an early bug ("documented but never invoked" for four
  hooks) was fixed 2026-04 — current docs postdate it; still, verify
  firing on a live seat.

## Related Skills

- `hermes-kanban` — task/board semantics behind the three kanban hook
  events.
- `hermes-configuration` — schema wiring for `hooks.*` and `plugins.*`
  keys.
- `hermes-skills` — the skills system behind `on_skill_lifecycle`.
- `hermes-managed-scope` — whether hook/plugin enablement can be
  fleet-pinned (open question, see source-capture).

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
