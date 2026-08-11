# M2b per-artifact Spec Kit resume ladder

**Status:** bound — Architect E-20260811T122959Z (decision-complete cards)  
**Supersedes for M2b:** inverted v11 R-M2.6 compound jump (`spec.md` → `/speckit-tasks`)

Under M2a/M2b split, M2a normally leaves `spec.md`. Jumping to `/speckit-tasks`
because `spec.md` exists **skips planning** and is a card defect.

## Ladder (each step owns precondition + skip)

| Step | Precondition | Skip iff | Else |
|------|--------------|----------|------|
| `/speckit-specify` | no `spec.md` | `spec.md` exists | run specify |
| `/speckit-plan` | `spec.md` present | `plan.md` exists | run plan |
| `/speckit-tasks` | `plan.md` present | never skip ahead of plan | run tasks (always last) |

Missing precondition → typed `needs_input` BLOCK. Never invent Spec Kit trees.

## Lint

`check-decision-complete-cards.py` fail-closes compound jump-over-plan language
on the M2b seed body (R0 create-path).
