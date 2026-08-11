# Complete must enforce cmd-shaped exit_criteria (Class A)

**Architect BIND:** `E-20260811T175509Z` (elevate BANK-COMPLETE-CMD-1)

## Problem

Hermes `kanban_complete` accepts voluntary complete without evaluating
cmd-shaped `exit_criteria`. Product S-004 `t_98e3ed7b` completed while
post-hoc `evaluate-exit-criteria.py --trigger complete` reported
`overall_ok=False` (compile / test_compile / body_digest). Wall path already
evaluated exits; complete path did not.

## Rule

1. **Before** `kanban_complete`, worker MUST run:
   ```bash
   python3 .hermes/skills/validation-release-gates/scripts/assert-complete-exit-criteria.py \
     . --task-id <id> --body <typed body.json>
   ```
   rc≠0 → **REFUSE** complete; typed `needs_input` or fix. Do not invent N/A.
2. Green run writes `migration/runs/<id>/complete-exit-ok.json` (`ok=true`).
3. `compile` / `test_compile` checks use the **scoped** gate
   (`compile-scope-filtered.md`) — whole-tree rc=0 is not the criterion.
4. **Harness reclaim:** Lead/watchdog may run
   `.hermes/home/scripts/enforce-complete-exit-criteria.py --task <id>`
   (or `--sweep-done`) to revert `done` → `needs_input` when the receipt is
   missing/red. That is fail-closed after Hermes accepts the tool call.
5. Wall / soft-requeue continue via `wall-exit-eval.md` (unchanged).

## Scripts

| Script | Role |
|--------|------|
| `assert-complete-exit-criteria.py` | Pre-complete fail-closed eval + receipt |
| `evaluate-exit-criteria.py` | Shared cmd evaluator (scoped compile) |
| `enforce-complete-exit-criteria.py` | Post-complete reclaim without receipt |

## Related

- `wall-exit-eval.md` — wall path already wired
- `compile-scope-filtered.md` — mid-partition compile criterion
- `completion-na-reject.md` — no N/A rewrite of binding criteria
