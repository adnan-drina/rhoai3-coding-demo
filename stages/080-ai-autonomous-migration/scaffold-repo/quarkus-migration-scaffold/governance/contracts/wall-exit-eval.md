# Wall-as-terminal exit evaluation

**Status:** binding proving-min
**Basis:** in-tree harness obligations (sibling contracts + skills).

## Rule

A budget wall (`timed_out` / `timeout_kill`) **IS** a terminal. Terminals **MUST**
evaluate machine-checkable `exit_criteria` (cmd-shaped), or the run must have
refused in-loop before the wall.

Advisory prose + completion-only gates are **insufficient** for the S-010
failure mode (wall kill never reaches `kanban_complete`).

## Procedure

On wall / gave_up-after-timeout (dispatcher hook):

```bash
python3 .hermes/skills/gates/check-release-readiness/scripts/evaluate-exit-criteria.py \
 . --body evidence/bodies/m3-s-010.json --task-id t_xxx --trigger timed_out

python3 .hermes/skills/gates/check-release-readiness/scripts/check-wall-exit-eval.py \
 . --task-id t_xxx --trigger timed_out
```

Artifact: `evidence/runs/<task_id>/exit-eval.json` (`rhoai3.exit-eval/v1`).

Assert-only exits are recorded as `unevaluated_assert` (honest); cmd exits run
and must be present for wall terminals when the body declares them (especially
`test_compile`).

### AD-009 / incomplete checkpoint

| ID | Rule |
|----|------|
| **R-M3.28** | Ballot / exit-eval **notes** must credit AD-009 provider freeze + >300s stream latencies before calling a wall-fit PASS body a **sizing** defect |
| **R-M3.31** | `evaluate-exit-criteria.py` sets `overall_ok=false` when `wallish` **and** implementer checkpoint is incomplete — even if `compile` alone is green |

See `m3-security-write-first.md` (R-M3.29/30) for security-card remediations.

## Requeue

Unbounded silent requeue **REJECT**.

| Mode | Rule |
|------|------|
| Soft | At most **K=1** timed_out soft-requeue; **before resume** run exit-eval + `sync-checkpoint-from-test-writes.py` |
| Hard | Next timed_out after K → **block** (terminal) + exit-eval; do not soft-resume |

```bash
python3 .hermes/skills/gates/check-release-readiness/scripts/apply-wall-requeue-policy.py . \
 --task-id t_xxx --body evidence/bodies/m3-s-010.json --k-soft 1
```

Also F4 restore-or-refuse before intentional requeue (`workspace-recovery.md`).

Crash/reclaim loops are **not** covered here — see `crash-requeue.md`
(K_crash=1).
