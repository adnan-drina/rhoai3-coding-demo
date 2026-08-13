# M2b per-artifact Spec Kit resume ladder

**Status:** bound — (decision-complete cards)
**Supersedes:** `m2-resume-from-artifacts.md` (retired R-M2.6 inverted compound jump
`spec.md` → `/speckit-tasks`). Architect E-20260813T162123Z §B.

Under M2a/M2b split, M2a normally leaves `spec.md`. Jumping to `/speckit-tasks`
because `spec.md` exists **skips planning** and is a card defect.

## Ladder (each step owns precondition + skip)

| Step | Precondition | Skip iff | Else |
|------|--------------|----------|------|
| `/speckit-specify` | no `spec.md` | `spec.md` exists | run specify |
| `/speckit-plan` | `spec.md` present | `plan.md` exists | run plan |
| `/speckit-tasks` | `plan.md` present | never skip ahead of plan | run tasks (always last) |

Missing precondition → typed `needs_input` BLOCK. Never invent Spec Kit trees.

## Folded live constraints (ex-R-M2.6, still binding)

- Do **not** rewrite write-once `evidence/briefs/partition.json`.
- Do **not** mid-run digest-breaking body rewrite on a live task — tip body
  lands here; apply on next reclaim/redisp.
- Prefer R-M2.5 wall raise (3600s) over further M2a/M2b split unless 3600+resume
  still dies before `tasks.md`.

## Lint

`check-decision-complete-cards.py` fail-closes compound jump-over-plan language
on the M2b seed body (R0 create-path). Contract path:
`governance/contracts/m2b-resume-ladder.md`.
