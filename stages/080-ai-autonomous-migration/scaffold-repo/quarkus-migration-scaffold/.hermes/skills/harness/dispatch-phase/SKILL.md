---
name: dispatch-phase
description: >
  Use at dest-init to mint M1 ANALYZE and M2 PLAN together with
  --idempotency-key so a repeated postStart is a no-op. Do not mint M3
  or M4. Do not kanban daemon --force. Do not restore a GitOps checkbox
  without this consumer. Do not use for story implementation.
license: Apache-2.0
compatibility: Linux seat; Hermes Kanban; dest-init postStart
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - harness
    - dest-init
    category: harness
    kind: guidance
---
## When the instructions do not work

If a command this skill names fails, a path it names is absent, or a tool cannot resolve something it names: **stop**. Do not substitute an equivalent command. Do not hand-author the artifact the command would have produced. Do not construct evidence that a step ran. (1) Record the defect: exactly what you ran, the exact error, and what this skill said to expect. (2) End with `kanban_block`, that report as the reason. **Blocking is a legal, successful outcome of a task.** A blocked task carrying an accurate defect report is worth more than a completed task built on a workaround — the skill then gets fixed, which is the point. Do not treat a gate as the thing to satisfy; gates catch mistakes, they do not define the job.

# Auto-start M1+M2 (dest-init consumer)

`scripts/autostart-migration.sh --root <project>` mints the T0 chain the
way dest-13 did by hand: M1 ANALYZE then M2 PLAN parented to M1.
Writes `.hermes/AUTOSTART-STATUS`. Must not fail the workspace start —
the destfile/GitOps hook is `|| echo WARN`.

M3 comes from `k4_mint` during M2. M4 is minted with the M3 stories as
parents. This script must not create those cards.
