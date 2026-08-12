# Hooks

**Official page:** https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks

**CS-5 cross-pointer:**
`harness-refactoring/source-analysis/hermes/20260812-official-kanban-alignment.md`

## `pre_tool_call` + `fail_closed`

Official rationale (quote): a crashed secret-scanner must not silently allow
the tool call it was supposed to vet — set `fail_closed: true` so hook
failure blocks the call (exit 2).

This is the sanctioned enforcement point for write-set / command policy
(CS-5 #7). Policy content stays ours; mechanism hosts here.

## `pre_verify`

Official extension point for deterministic checks before verify-on-stop /
complete. Prefer hosting exit-criteria asserts here over forever wrappers.

## Consent + `--accept-hooks`

Non-TTY / profile workers need hook consent or new hooks silently unregister.
Dispatcher passes `--accept-hooks` for profile-scoped workers — one of the
documented escape hatches. Do not invent additional bypasses without an
AD-013 cite.

## Doctor caveat

Official: script edits are silently trusted after registration — run
`hermes hooks doctor` after hook changes. Allowlists key the command string,
not a script hash.
