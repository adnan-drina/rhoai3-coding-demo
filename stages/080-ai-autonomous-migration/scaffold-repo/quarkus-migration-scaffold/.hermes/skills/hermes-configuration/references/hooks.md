# Hooks

**Official sources (cite these):**
- Hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
  (also covered in kanban / configuration docs cross-links)
- CS-5 alignment:
  `harness-refactoring/source-analysis/hermes/20260812-official-kanban-alignment.md`

## Official enforcement points

| Hook / flag | Role |
|-------------|------|
| `pre_tool_call` + `fail_closed: true` | Sanctioned write-set / command gate (exit 2 blocks) |
| `pre_verify` | Deterministic policy before verify-on-stop / complete |
| verify-on-stop + `hermes verify` | Evidence ledger for post-edit verification |
| `--accept-hooks` | Hook consent bypass — dispatcher uses for profile workers; non-TTY needs it or new hooks silently unregister |

## Platform notes

- Write-set **policy** stays ours; **mechanism** should host on
  `pre_tool_call` fail_closed (CS-5 #7) rather than forever wrappers.
- Allowlist keys the command **string**, not script hash — run
  `hermes hooks doctor` after edits.
- OpenCode seats: prefer official `permission.edit` deny-by-default per path
  when that seat is in scope.

## Do not

- Invent a parallel hook runtime when official `pre_tool_call` /
  `pre_verify` covers the gate.
- Pass `--accept-hooks` outside the documented dispatcher/worker path
  without an AD-013 cite explaining why.
