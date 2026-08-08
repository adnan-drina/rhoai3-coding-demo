---
name: role-authority
description: >
  AD-H §16 role allowlists, human ack checkpoints, and cheap cross-role write
  refuses. Use before phase advance and when validating task packets against
  role bounds.
---

# Role authority (AD-H §16)

## Contracts

- `migration/contracts/role-authority.md`
- `migration/schemas/ack.md`
- Phase `role` + `skills[]`: `.hermes/phase-dispatch.yaml`

## Checks

```bash
# Ack presence for a target phase (from phase-dispatch requires_acks)
bash "${HERMES_SKILL_DIR}/scripts/check-acks.sh" M2

# Cross-role write refuse when task JSON declares role + writes/files_touched
python3 "${HERMES_SKILL_DIR}/scripts/check-role-writes.py" /projects/modernized
```

Idle when no tasks / no phase advance requested.

## Roles (summary)

evidence-analyst · planner · spec-author · implementer · reviewer · validator  
One Kanban task ⇒ one role. Never `/speckit.implement`. Never edit
`.hermes/skills/**` from a worker.
