---
name: role-authority
description: Enforce role allowlists and ACK gates
version: 1.1.0
author: rhoai3-harness-team
license: Apache-2.0
platforms: [linux]
metadata:
  hermes:
    tags:
    - harness
    - orchestration
    category: harness
---
## When to Use

Use this skill when its name matches the active phase or gate.


# Role authority (AD-H §16)

## Contracts

- `migration/contracts/role-authority.md`
- `migration/schemas/ack.md`
- Phase `role` + `skills[]`: `.hermes/phase-dispatch.yaml`

## Procedure

Run the checks below.

## Checks

```bash
# Ack presence for a target phase (from phase-dispatch requires_acks)
bash "${HERMES_SKILL_DIR}/scripts/check-acks.sh" M2

# Cross-role write refuse when task JSON declares role + writes/files_touched
python3 "${HERMES_SKILL_DIR}/scripts/check-role-writes.py" /projects/modernized

# AD-H §16.4 proving-min fence (ER#2 F2) — lock ACK/gate paths; probe; pre-complete refuse
bash "${HERMES_SKILL_DIR}/scripts/apply-write-fence.sh" /projects/modernized lock
python3 "${HERMES_SKILL_DIR}/scripts/probe-write-fence.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/check-write-fence.py" /projects/modernized

# AD-H §16.5 / AR-1.1 / AR-1.2 — self-ACK + comment-as-Lead refuse
python3 "${HERMES_SKILL_DIR}/scripts/check-ack-authority.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/check-comment-authority.py" /projects/modernized

# AD-H §16.8 / AR-1.3–1.6 — one-role, skill_manage, slim packet, untrusted boundary
python3 "${HERMES_SKILL_DIR}/scripts/check-one-role-dispatch.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/check-skill-manage-policy.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/../phase-dispatch/scripts/check-phase-attach-matrix.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/check-untrusted-boundary.py" /projects/modernized --as-gate
# Fixture self-test (expect exit 1): omit --as-gate
```

Contracts: `migration/contracts/role-authority.md`, `migration/contracts/write-fence.md`,
`migration/contracts/ack-authority.md`, `migration/contracts/slim-packet.md`.
Idle when no tasks / no phase advance requested.

## Roles (summary)

evidence-analyst · planner · spec-author · implementer · reviewer · validator  
One Kanban task ⇒ one role. Never `/speckit-implement`. Never edit
`.hermes/skills/**` from a worker. `skill_manage` unavailable / proposal-only.


## Verification

- Scripts under `scripts/` exit 0 on a healthy seat.
- Conformance lint passes for this skill.
