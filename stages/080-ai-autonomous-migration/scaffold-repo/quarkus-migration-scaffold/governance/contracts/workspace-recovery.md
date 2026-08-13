# Workspace recovery — proving min (AD-H §5.1 / ER#2 F4)

**Status:** binding for `validation_protocol_conformant` · **not** `release_qualified`
**Basis:** AD-H §5.1

**Fact:** Hermes **requeue restores the task record, not the workspace.**
Edits, commits, analyzer output, and state-changing gate calls are side effects.
Treating requeue as restore is a defect.

## Proving-campaign exit (a)

On terminals `crashed` / `gave_up` / `kill` / `timed_out`:

1. Run `restore-or-refuse-requeue.py` **before** unblock/requeue/dispatch.
2. If the workspace is dirty → **refuse** requeue (exit 1) **or** `--action restore`
 to a known baseline, then re-check `workspace_clean`.
3. Dirty-workspace fixture must fail the check (see validate-contracts smoke).
4. On **`timed_out` / wall**: also run `evaluate-exit-criteria.py` +
 `check-wall-exit-eval.py` (`wall-exit-eval.md`) — wall is a terminal.

## Commands

```bash
# Refuse silent requeue onto dirt
python3 .hermes/skills/gates/check-release-readiness/scripts/restore-or-refuse-requeue.py . \
 --terminal crashed

# Explicit restore then allow
python3 .hermes/skills/gates/check-release-readiness/scripts/restore-or-refuse-requeue.py . \
 --terminal gave_up --action restore --baseline HEAD

# Clean-only probe
python3 .hermes/skills/gates/check-release-readiness/scripts/check-workspace-clean.py .
```

## Deferred (release)

Full durable side-effect journal + chaos inject across every boundary.
Do not claim `release_qualified` on this procedure alone.
