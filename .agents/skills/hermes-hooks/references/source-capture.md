# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | no version marker on doc pages; "config schema v21+" cited for plugin opt-in migration |
| Chapter or page title | Event Hooks; Build a Hermes Plugin; Plugins; Gateway Internals; Built-in Plugins; Environment Variables / CLI Commands (hooks rows) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks |
| Source URL | https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin (renders empty to some fetch tools; markdown source: repository `website/docs/developer-guide/plugins/index.md`) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins |
| Source URL | https://hermes-agent.nousresearch.com/docs/developer-guide/gateway-internals (implementation facts only — its event table is stale) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/built-in-plugins (worked production hook examples) |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/environment-variables and /docs/reference/cli-commands (hooks rows) |
| Documentation category | Features / Guides / Developer Guide / Reference |
| Capture date | 2026-08-12 |
| Capture method | Research-agent dossier (`source-analysis/hermes/hermes-hooks-capture.md`, 607 lines); reviewer re-verified the four-system taxonomy, ordering/precedence, non-TTY consent, exit-code-2 scoping, and error-isolation quotes against the live Hooks page, and verified all single-sourced Build-a-Plugin facts (10k cap/spill, ctx._cli_ref contexts, dispatch_tool, kanban commit timing) verbatim against the guide's markdown source in the repository on 2026-08-12 |

## Captured Sections

- Event Hooks (primary): four hook systems, gateway hooks
  (HOOK.yaml/handler contract, 10+wildcard events), the complete plugin
  hook catalog with per-event timing/payload/privacy, per-hook deep dives,
  shell hooks (config schema, JSON wire protocol, exit-2, fail posture,
  consent model, CLI), outbound webhooks (config, HMAC wire format,
  delivery semantics).
- Build a Hermes Plugin: pre_llm_call injection cap/spill
  (`hooks.output_spill`), acting-from-hooks APIs, provides_hooks manifest.
- Plugins: opt-in gating (`plugins.enabled`/`disabled`, disabled wins),
  v21+ grandfathering.
- Built-in Plugins: production hook wirings (disk-cleanup, langfuse).

## Discrepancies resolved by this capture

- **Event count: 24 is correct.** The dossier flagged 23 vs the Plugins
  page's "24 lifecycle events"; reviewer extracted `VALID_HOOKS` from the
  shipped source (`hermes_cli/plugins.py`) — exactly 24 entries, matching
  the docs catalog table one-to-one. The "23" was a count error in the
  dossier's own summary, not a docs inconsistency.
- **Gateway event tables:** the Hooks page (10 events + `command:*`
  wildcard) is authoritative; Gateway Internals' 8-row table omits
  `session:compress` and `reaction:*` (stale subset).
- **Issue #2817** ("hooks documented but never invoked") is CLOSED
  (2026-04-27) — historical bug, fixed; current per-hook docs postdate it.

## Source Boundaries

This skill captures hook mechanics: systems, events, firing semantics,
ordering, blocking, consent, and the hooks CLI. Kanban task semantics
belong to `hermes-kanban`; skills mechanics to `hermes-skills`; config
schema wiring to `hermes-configuration`; full CLI reference to
`hermes-cli`. Plugin middleware is "a separate registry and surface, not
another hook category" — undocumented, no owning skill.

## Known Open Items

- Whether `HERMES_SAFE_MODE` also disables gateway-hook discovery is
  undocumented (only plugins/MCP/shell hooks are named).
- Plugin middleware (and the `middleware_trace` payload field) has no
  documentation page found.
- `gateway/builtin_hooks/` extension format is source-only (shipped empty,
  no-op stub).
- Whether Managed Scope can fleet-pin plugin/hook enablement — flagged to
  `hermes-managed-scope`.
- The `security-guidance` built-in's exact hook name is not stated in docs.
- Shell-hook `matcher` behavior on non-tool events is undocumented beyond
  the general ignore-unknown-keys rule.
