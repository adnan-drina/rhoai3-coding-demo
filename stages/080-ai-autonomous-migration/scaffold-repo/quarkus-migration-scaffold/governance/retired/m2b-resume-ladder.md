# RETIRED — M2b Spec Kit resume ladder

**Status:** retired (GR2 / Lead E-20260814T114609Z).
**Superseded by:** `governance/contracts/sdd-ordering.md` (Spec Kit per-artifact resume ladder section).
**Why:** Operator removed the M2a/M2b split (E-20260813T211843Z); mint is orchestrator-owned (`mint-m3-wave.sh`). Ladder content survives under sdd-ordering; this file is attic-only.

---

# M2b per-artifact Spec Kit resume ladder

**Status:** retired — see header
**Supersedes:** `governance/retired/m2-resume-from-artifacts.md` (retired R-M2.6
inverted compound jump `spec.md` → `/speckit-tasks`). Architect
E-20260813T162123Z §B; attic move GR1 E-20260814T081104Z.

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
on the M2 seed body (R0 create-path). Live contract path:
`governance/contracts/sdd-ordering.md` (this attic file is historical only).
