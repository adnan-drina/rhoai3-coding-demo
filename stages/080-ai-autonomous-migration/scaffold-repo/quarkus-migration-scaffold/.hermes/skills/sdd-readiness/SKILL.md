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
# AD-H §16.9 / AR-4.4 — surgical write sets + endpoint exits
python3 "${HERMES_SKILL_DIR}/scripts/check-surgical-scopes.py" /projects/modernized
# AR-2.3–2.7 — semantic product exits for REST/persistence stories
python3 "${HERMES_SKILL_DIR}/scripts/check-semantic-exits.py" /projects/modernized
# Architect E-104925Z / E-110403Z — measured operand_count (phase-name REJECT)
python3 "${HERMES_SKILL_DIR}/scripts/check-operand-count.py" /projects/modernized
```

Idle (pass) when no SDD / body artifacts exist yet.

## Contracts

- `migration/contracts/pattern-steals.md`
- `migration/contracts/sdd-ordering.md` (AD-S §S.6)
- `migration/contracts/surgical-scopes.md` (AR-4.4)
- `migration/contracts/semantic-exits.md` (AR-2.3–2.7)
- `migration/contracts/story-sizing.md` (operand_count)
- `migration/schemas/mta-exception.md`
- `migration/schemas/kanban-body.md` (W2 §6.1)
