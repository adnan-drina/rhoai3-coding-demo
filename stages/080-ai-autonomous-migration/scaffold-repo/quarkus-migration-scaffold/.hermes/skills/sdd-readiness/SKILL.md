---
name: sdd-readiness
description: >
  Fail-closed SDD readiness: Non-Goals, open Q-*, task packet shape,
  mta-exception re_open_trigger, AD-S §S.6 identity/re-plan/plan_revision.
  Use before Kanban-ready / phase advance when specs or tasks exist.
---

# SDD readiness (pattern-steals + §S.6)

## Procedure

```bash
bash "${HERMES_SKILL_DIR}/scripts/check-readiness.sh"
# W2 §6.1 typed body vocabulary
python3 "${HERMES_SKILL_DIR}/scripts/check-kanban-body.py" /projects/modernized
```

Idle (pass) when no SDD / body artifacts exist yet.

## Contracts

- `migration/contracts/pattern-steals.md`
- `migration/contracts/sdd-ordering.md` (AD-S §S.6)
- `migration/schemas/mta-exception.md`
- `migration/schemas/kanban-body.md` (W2 §6.1)
