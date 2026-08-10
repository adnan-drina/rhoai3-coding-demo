# Wall-as-terminal exit evaluation (Architect E-20260810T110403Z)

**Status:** binding proving-min  
**Sources:** Deputy Gap 2 · Architect BIND wall-as-terminal · Lead land

## Rule

A budget wall (`timed_out` / `timeout_kill`) **IS** a terminal. Terminals **MUST**
evaluate machine-checkable `exit_criteria` (cmd-shaped), or the run must have
refused in-loop before the wall.

Advisory prose + completion-only gates are **insufficient** for the S-010
failure mode (wall kill never reaches `kanban_complete`).

## Procedure

On wall / gave_up-after-timeout (Lead, Monitor, or dispatcher hook):

```bash
python3 .hermes/skills/validation-release-gates/scripts/evaluate-exit-criteria.py \
  . --body migration/bodies/m3-s-010.json --task-id t_xxx --trigger timed_out

python3 .hermes/skills/validation-release-gates/scripts/check-wall-exit-eval.py \
  . --task-id t_xxx --trigger timed_out
```

Artifact: `migration/runs/<task_id>/exit-eval.json` (`rhoai3.exit-eval/v1`).

Assert-only exits are recorded as `unevaluated_assert` (honest); cmd exits run
and must be present for wall terminals when the body declares them (especially
`test_compile`).

## Requeue (Architect E-20260810T121300Z)

Unbounded silent requeue **REJECT**.

| Mode | Rule |
|------|------|
| Soft | At most **K=1** timed_out soft-requeue; **before resume** run exit-eval + `sync-checkpoint-from-test-writes.py` |
| Hard | Next timed_out after K → **block** (terminal) + exit-eval; do not soft-resume |

```bash
python3 .hermes/skills/validation-release-gates/scripts/apply-wall-requeue-policy.py . \
  --task-id t_xxx --body migration/bodies/m3-s-010.json --k-soft 1
```

Also F4 restore-or-refuse before intentional requeue (`workspace-recovery.md`).
